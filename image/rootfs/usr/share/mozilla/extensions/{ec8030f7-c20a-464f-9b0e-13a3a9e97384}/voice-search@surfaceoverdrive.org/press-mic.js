// On the page the button opened: press Google's own microphone ("Search by voice") once it is there.
(() => {
  if (!new URLSearchParams(location.search).has("overdrive_voice")) return;
  history.replaceState(null, "", location.pathname);   // a reload does not start listening again
  const label = /voice|vocale|voz|vocal|sprach|голос/i;
  const find = () => [...document.querySelectorAll("[aria-label][role=button], button[aria-label]")]
    .find((el) => label.test(el.getAttribute("aria-label")) && el.offsetParent !== null);
  let tries = 0;
  const timer = setInterval(() => {
    const mic = find();
    if (mic || ++tries > 50) {
      clearInterval(timer);
      if (mic) mic.click();
    }
  }, 100);
})();
