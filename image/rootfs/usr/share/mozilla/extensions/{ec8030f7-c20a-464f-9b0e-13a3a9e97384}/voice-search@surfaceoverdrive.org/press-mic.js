// In the hidden tab the toolbar button opened: press Google's own microphone, report what it hears to the extension,
// and say when Google has searched. A tab opened by hand is left alone.
(() => {
  const params = new URLSearchParams(location.search);
  if (params.has("overdrive_voice")) {
    sessionStorage.setItem("overdrive_voice", "1");
    history.replaceState(null, "", location.pathname);
  }
  if (!sessionStorage.getItem("overdrive_voice")) return;

  if (location.pathname === "/search") {               // Google has searched: show these results
    sessionStorage.removeItem("overdrive_voice");
    browser.runtime.sendMessage({ type: "results", query: params.get("q") || "" });
    return;
  }

  const send = (msg) => browser.runtime.sendMessage(msg).catch(() => {});
  // Google's own words on the listening page, typed out letter by letter ("I", "In", "In a", ... "In ascolto...")
  const STATES = ["parla ora", "in attesa", "in ascolto", "speak now", "listening", "waiting"];
  const isState = (text) => {
    const t = text.toLowerCase().replace(/[.…\s]+$/, "");
    return t !== "" && STATES.some((s) => s.startsWith(t) || t.startsWith(s));
  };
  const failed = /non ho capito|riprova|didn.t get|try again|nessun|microfono|microphone|permesso|permission/i;
  const label = /voice|vocale|voz|vocal|sprach|голос/i;
  const findMic = () => [...document.querySelectorAll("[aria-label][role=button], button[aria-label]")]
    .find((el) => label.test(el.getAttribute("aria-label")));
  // the big line of the listening page: it reads "Speak now", then the words as Google hears them
  const findLine = () => [...document.querySelectorAll("body *")].find((el) =>
    el.childElementCount === 0 && el.getClientRects().length > 0 && isState((el.textContent || "").trim()));

  let line = null, last = "";
  const watch = () => {
    if (!line || !line.isConnected) line = findLine();
    if (!line) return;
    const text = (line.textContent || "").trim();
    if (text === last) return;
    last = text;
    if (isState(text)) send({ type: "state", text });
    else if (failed.test(text)) send({ type: "error", text });
    else if (text) send({ type: "words", text });
  };

  let pressed = false;
  const press = () => {
    if (pressed) return;
    const mic = findMic();
    if (!mic) return;
    pressed = true;
    mic.click();
    send({ type: "state", text: "" });
    new MutationObserver(watch).observe(document.documentElement, { childList: true, subtree: true, characterData: true });
  };
  new MutationObserver(press).observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", press);
})();
