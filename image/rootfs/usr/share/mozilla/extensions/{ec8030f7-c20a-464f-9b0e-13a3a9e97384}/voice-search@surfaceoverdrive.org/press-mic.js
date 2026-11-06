// On the page the button opened: straight to Google's own voice search ("Search by voice"). The home page stays hidden
// from the first moment; the microphone is pressed as soon as it exists, and the page shows once listening has begun.
(() => {
  if (!new URLSearchParams(location.search).has("overdrive_voice")) return;
  history.replaceState(null, "", location.pathname);   // a reload does not start listening again

  const hide = document.createElement("style");
  hide.textContent = "html { background: #fff !important; } body { visibility: hidden !important; }";
  (document.head || document.documentElement).appendChild(hide);
  let shown = false;
  const show = () => { if (!shown) { shown = true; hide.remove(); } };
  setTimeout(show, 4000);                               // never a blank page: whatever happens, Google shows by then

  const label = /voice|vocale|voz|vocal|sprach|голос/i;
  const find = () => [...document.querySelectorAll("[aria-label][role=button], button[aria-label]")]
    .find((el) => label.test(el.getAttribute("aria-label")));
  let pressed = false;
  const press = () => {
    if (pressed) return;
    const mic = find();
    if (!mic) return;
    pressed = true;
    observer.disconnect();
    mic.click();
    // the listening page is drawn over the home page: show it once it is there
    const start = Date.now();
    const wait = setInterval(() => {
      const listening = [...document.querySelectorAll("body *")].some((el) =>
        el.childElementCount === 0 && el.getClientRects().length > 0 &&      // laid out, not a hidden template
        /ascolto|parla ora|listening|speak now|attesa|waiting/i.test(el.textContent || ""));
      if (listening || Date.now() - start > 1500) { clearInterval(wait); show(); }
    }, 30);
  };
  const observer = new MutationObserver(press);
  observer.observe(document.documentElement, { childList: true, subtree: true });
  document.addEventListener("DOMContentLoaded", press);
})();
