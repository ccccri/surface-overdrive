// Voice Search for Google. The toolbar button opens Google with a marker, in a new tab (the empty tab it was pressed in
// is closed: a new-tab page would keep the focus in the address bar and bring up an on-screen keyboard). press-mic.js
// presses Google's own microphone there and, once the microphone is allowed, covers Google's page with a listening
// screen. Google has to run in the tab in front: in a background tab Firefox gives the microphone, but only silence.
const VOICE_URL = "https://www.google.com/?overdrive_voice=1";
const EMPTY = ["about:newtab", "about:home", "about:blank", "about:privatebrowsing"];

browser.browserAction.onClicked.addListener(async (tab) => {
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
