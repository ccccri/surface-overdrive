// On the page the toolbar button opened: Google's page is covered from the first moment by a listening screen (the
// microphone and the words as Google hears them), Google's own microphone is pressed beneath it, and when Google
// searches, its results show. A Google page opened by hand is left alone.
(() => {
  const params = new URLSearchParams(location.search);
  if (params.has("overdrive_voice")) {
    sessionStorage.setItem("overdrive_voice", "1");
    history.replaceState(null, "", location.pathname);
  }
  if (!sessionStorage.getItem("overdrive_voice")) return;
  if (location.pathname !== "/") {                     // Google has searched: these are the results
    sessionStorage.removeItem("overdrive_voice");
    return;
  }

  // the listening screen, in a shadow root on <html> (Google's styles do not reach it; Google's page stays hidden)
  const host = document.createElement("overdrive-voice");
  const shadow = host.attachShadow({ mode: "closed" });
  shadow.innerHTML = `
    <style>
      :host { all: initial; position: fixed; inset: 0; z-index: 2147483647; display: block; visibility: visible; }
      .screen { position: absolute; inset: 0; background: #fff; color: #202124; font-family: system-ui, sans-serif;
                display: flex; align-items: center; justify-content: center; }
      @media (prefers-color-scheme: dark) { .screen { background: #1c1b22; color: #fbfbfe; } .status { color: #9e9ea6 !important; } }
      main { width: 100%; max-width: 900px; padding: 0 32px; box-sizing: border-box; display: flex; align-items: center;
             justify-content: space-between; gap: 32px; }
      p { margin: 0; flex: 1; font-size: clamp(24px, 4vw, 34px); line-height: 1.3; }
      .status { color: #70757a; }
      button { flex: none; width: 112px; height: 112px; border-radius: 50%; border: none; background: #ea4335;
               display: grid; place-items: center; cursor: pointer; padding: 0; }
      button svg { width: 44px; height: 44px; fill: #fff; }
      .live { animation: pulse 1.3s ease-in-out infinite; }
      @keyframes pulse { 0%, 100% { box-shadow: 0 0 0 0 #ea433555; } 50% { box-shadow: 0 0 0 22px #ea433500; } }
      @media (max-width: 560px) { main { flex-direction: column-reverse; text-align: center; } }
    </style>
    <div class="screen"><main>
      <p class="status">…</p>
      <button class="live" title="Google Voice Search"><svg viewBox="0 0 16 16"><path d="M8 1a2.5 2.5 0 0 0-2.5 2.5v4a2.5 2.5 0 0 0 5 0v-4A2.5 2.5 0 0 0 8 1zM3.5 7a.5.5 0 0 0-.5.5 5 5 0 0 0 4.5 4.97V14H5.5a.5.5 0 0 0 0 1h5a.5.5 0 0 0 0-1H8.5v-1.53A5 5 0 0 0 13 7.5a.5.5 0 0 0-1 0 4 4 0 0 1-8 0 .5.5 0 0 0-.5-.5z"/></svg></button>
    </main></div>`;
  const hide = document.createElement("style");
  // Google's listening page is a modal <dialog>: above everything, and the rest of the page inert. The screen moves into
  // it while it is open and the dialog's own content is made transparent, so Google works on unseen and the screen's
  // microphone can still be pressed.
  hide.textContent = `
    html { background: #fff !important; } body { visibility: hidden !important; }
    dialog:modal { background: transparent !important; border: 0 !important; box-shadow: none !important; }
    dialog:modal > :not(overdrive-voice) { opacity: 0 !important; }
    dialog::backdrop { background: transparent !important; }`;
  document.documentElement.append(hide, host);
  const follow = () => {
    const dialog = document.querySelector("dialog:modal");
    const home = dialog || document.documentElement;
    if (host.parentNode !== home) home.append(host);
  };
  new MutationObserver(follow).observe(document.documentElement, { childList: true, subtree: true, attributes: true, attributeFilter: ["open"] });
  const words = shadow.querySelector("p");
  const button = shadow.querySelector("button");
  const say = (text, isState, live) => {
    words.textContent = text;
    words.classList.toggle("status", isState);
    button.classList.toggle("live", live);
  };

  // Google's own words on its listening page, typed out letter by letter ("I", "In", "In a", ... "In ascolto...")
  const STATES = ["parla ora", "in attesa", "in ascolto", "speak now", "listening", "waiting"];
  const isState = (text) => {
    const t = text.toLowerCase().replace(/[.…\s]+$/, "");
    return t !== "" && STATES.some((s) => s.startsWith(t) || t.startsWith(s));
  };
  const failed = /non ho capito|riprova|controlla il microfono|didn.t get|try again|check your microphone|microfono|microphone|permesso|permission/i;
  const label = /voice|vocale|voz|vocal|sprach|голос/i;
  const findMic = () => [...document.querySelectorAll("[aria-label][role=button], button[aria-label]")]
    .find((el) => label.test(el.getAttribute("aria-label")));
  // the big line of Google's listening page: "Speak now" first, then the words as Google hears them
  const findLine = () => [...document.body.querySelectorAll("*")].find((el) =>
    el.childElementCount === 0 && el.getClientRects().length > 0 && isState((el.textContent || "").trim()));

  let line = null, last = "";
  const watch = () => {
    if (!line || !line.isConnected) line = findLine();
    if (!line) return;
    const text = (line.textContent || "").trim();
    if (text === last) return;
    last = text;
    if (isState(text)) say(text, true, true);
    else if (failed.test(text)) say(text, true, false);
    else if (text) say(text, false, true);
  };

  let pressed = false, watcher = null;
  const press = () => {
    if (pressed || !document.body) return;
    const mic = findMic();
    if (!mic) return;
    pressed = true;
    mic.click();
    if (!watcher) {
      watcher = new MutationObserver(watch);
      watcher.observe(document.body, { childList: true, subtree: true, characterData: true });
    }
  };
  new MutationObserver(press).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", press);

  // the microphone again: Google's listening page closed, its microphone pressed anew
  button.addEventListener("click", () => {
    document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
    line = null; last = "";
    say("…", true, true);
    setTimeout(() => { pressed = false; press(); }, 300);
  });
})();
