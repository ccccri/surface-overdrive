#!/usr/bin/env python3
"""The laptop screen as a light source driven from here (calibration tool).

  screen.py serve [--port 8765]     serve the page; open http://<this PC>:<port>/ on the laptop, press Full screen
  screen.py set R G B               show that sRGB colour (0-255) on the whole screen
  screen.py set white               the same as 255 255 255

The page asks for the colour a few times a second, so a change shows within half a second; `set` waits for the page to
report it before returning, so a capture right after sees the new colour. The laptop needs True Tone and Night Shift off
and a fixed brightness (the brightest setting), so that the screen's white is its own D65 white and does not drift.
"""
import argparse
import json
import sys
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PAGE = """<!doctype html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Calibration Screen</title>
<style>
  html, body { margin: 0; height: 100%; background: #000; color: #8c8c8c; font: 16px system-ui, sans-serif; cursor: none; }
  #go { position: fixed; inset: 0; margin: auto; width: 240px; height: 64px; font: 600 18px system-ui, sans-serif;
        color: #e8e8e8; background: #1c1c1c; border: 1px solid #3a3a3a; border-radius: 8px; cursor: pointer; }
  body.full #go { display: none; }
</style></head>
<body><button id="go" type="button">Full screen</button>
<script>
let shown = "";
document.getElementById("go").addEventListener("click", async () => {
  document.body.classList.add("full");
  try { await document.documentElement.requestFullscreen(); } catch (e) {}
});
async function poll() {
  try {
    const s = await (await fetch("/state", { cache: "no-store" })).json();
    if (s.colour !== shown) {
      document.body.style.background = s.colour;
      shown = s.colour;
    }
    await fetch("/shown?c=" + encodeURIComponent(shown), { cache: "no-store" });
  } catch (e) {}
  setTimeout(poll, 200);
}
poll();
</script></body></html>
"""


def serve(port):
    state = {"colour": "rgb(0, 0, 0)", "shown": ""}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass

        def reply(self, body, kind):
            data = body.encode()
            self.send_response(200)
            self.send_header("Content-Type", kind)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            if self.path == "/":
                self.reply(PAGE, "text/html; charset=utf-8")
            elif self.path == "/state":
                self.reply(json.dumps(state), "application/json")
            elif self.path.startswith("/shown?c="):
                state["shown"] = urllib.request.unquote(self.path[9:])
                self.reply("ok", "text/plain")
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/set":
                state["colour"] = self.rfile.read(int(self.headers["Content-Length"])).decode()
                self.reply("ok", "text/plain")
            else:
                self.send_error(404)

    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


def set_colour(port, colour, timeout=10.0):
    base = "http://127.0.0.1:%d" % port
    urllib.request.urlopen(urllib.request.Request(base + "/set", data=colour.encode(), method="POST")).read()
    end = time.time() + timeout
    while time.time() < end:
        if json.load(urllib.request.urlopen(base + "/state"))["shown"] == colour:
            time.sleep(0.3)                     # one more frame of the screen
            return True
        time.sleep(0.1)
    print("the page did not show %s within %.0f s (is it open?)" % (colour, timeout), file=sys.stderr)
    return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("command", choices=("serve", "set"))
    ap.add_argument("values", nargs="*")
    ap.add_argument("--port", type=int, default=8765)
    a = ap.parse_args()
    if a.command == "serve":
        serve(a.port)
    else:
        v = [255, 255, 255] if a.values == ["white"] else [int(x) for x in a.values]
        sys.exit(0 if set_colour(a.port, "rgb(%d, %d, %d)" % tuple(v)) else 1)


if __name__ == "__main__":
    main()
