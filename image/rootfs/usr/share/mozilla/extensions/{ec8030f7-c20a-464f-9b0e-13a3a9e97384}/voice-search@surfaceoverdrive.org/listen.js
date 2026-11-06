// The listening page: Google's state and the words it hears; the microphone starts again; closing the tab stops.
const port = browser.runtime.connect({ name: "listen" });
const words = document.getElementById("words");
const mic = document.getElementById("mic");
const say = (text, isStatus) => { words.textContent = text; words.classList.toggle("status", isStatus); };

port.onMessage.addListener((msg) => {
  if (msg.type === "state") { say(msg.text || "…", true); mic.classList.add("live"); }
  else if (msg.type === "words") { say(msg.text, false); mic.classList.add("live"); }
  else if (msg.type === "error") { say(msg.text, true); mic.classList.remove("live"); }
});
mic.addEventListener("click", () => location.reload());     // again: the page connects anew, Google listens anew
