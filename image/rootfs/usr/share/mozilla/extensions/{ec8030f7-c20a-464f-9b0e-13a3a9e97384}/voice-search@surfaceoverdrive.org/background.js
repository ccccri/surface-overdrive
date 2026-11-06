// Voice Search for Google. The toolbar button opens Google with a marker, in a new tab (the empty tab it was pressed in
// is closed: a new-tab page would keep the focus in the address bar and bring up an on-screen keyboard). press-mic.js
// presses Google's own microphone there and, once the microphone is allowed, covers Google's page with a listening
// screen. Google has to run in the tab in front: in a background tab Firefox gives the microphone, but only silence.
const VOICE_URL = "https://www.google.com/?overdrive_voice=1";
const EMPTY = ["about:newtab", "about:home", "about:blank", "about:privatebrowsing"];

// Firefox has no sounds of its own for listening (Chrome's speech engine has them, Google's page does not): a short
// rising chime when Google starts listening, a falling one when it stops. The audio context is made and resumed in the
// click on the button, so that later chimes are not held back as autoplay.
let audio = null;
function chime(rising) {
  if (!audio) return;
  const notes = rising ? [660, 880] : [880, 587];
  notes.forEach((freq, i) => {
    const start = audio.currentTime + i * 0.11;
    const osc = audio.createOscillator();
    const gain = audio.createGain();
    osc.type = "sine";
    osc.frequency.value = freq;
    gain.gain.setValueAtTime(0, start);
    gain.gain.linearRampToValueAtTime(0.22, start + 0.015);
    gain.gain.exponentialRampToValueAtTime(0.001, start + 0.1);
    osc.connect(gain).connect(audio.destination);
    osc.start(start);
    osc.stop(start + 0.11);
  });
}
// tabs where Google listens: the falling chime once, when Google stops with an error (press-mic.js says so) or opens its
// results (seen here: a message from a page that is going away would be lost)
const listening = new Set();
browser.runtime.onMessage.addListener((msg, sender) => {
  if (!msg || msg.type !== "chime" || !sender.tab) return;
  if (msg.rising) {
    listening.add(sender.tab.id);
    chime(true);
  } else if (listening.delete(sender.tab.id)) {
    chime(false);
  }
});
browser.tabs.onUpdated.addListener((tabId, info) => {
  if (info.url && listening.has(tabId) && new URL(info.url).pathname === "/search") {
    listening.delete(tabId);
    chime(false);
  }
});
browser.tabs.onRemoved.addListener((tabId) => listening.delete(tabId));

browser.browserAction.onClicked.addListener(async (tab) => {
  if (!audio) audio = new AudioContext();
  audio.resume();
  await browser.tabs.create({ url: VOICE_URL, index: tab ? tab.index + 1 : undefined });
  if (tab && EMPTY.includes(tab.url)) browser.tabs.remove(tab.id).catch(() => {});
});

// installed from addons.mozilla.org: a page on allowing the microphone and private windows (not when it comes with a
// system image, where both are set up already)
browser.runtime.onInstalled.addListener(async ({ reason }) => {
  if (reason !== "install") return;
  const self = await browser.management.getSelf().catch(() => null);
  if (self && self.installType === "normal") browser.tabs.create({ url: browser.runtime.getURL("welcome.html") });
});
