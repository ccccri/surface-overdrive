#!/usr/bin/python3
"""serve.py <dir> <result.json>: serves camera-test.html on http://127.0.0.1:8765 and writes the POSTed result."""
import http.server, sys
root, result = sys.argv[1], sys.argv[2]
class H(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *a, **k): super().__init__(*a, directory=root, **k)
    def do_POST(self):
        data = self.rfile.read(int(self.headers.get("Content-Length", 0)))
        with open(result, "wb") as f: f.write(data)
        self.send_response(204); self.end_headers()
    def log_message(self, *a): pass
http.server.ThreadingHTTPServer(("127.0.0.1", 8765), H).serve_forever()
