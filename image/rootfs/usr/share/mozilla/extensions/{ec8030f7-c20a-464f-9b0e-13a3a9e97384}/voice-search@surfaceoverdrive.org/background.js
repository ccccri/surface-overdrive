// The toolbar button: Google with the voice search marker, in a new tab. press-mic.js covers Google's
// page with the listening screen from the first moment and drives Google's own voice search beneath it. Google has to
// run in the tab in front: in a background tab Firefox gives the microphone, but only silence.
const VOICE_URL = "https://www.google.com/?overdrive_voice=1";
const EMPTY = ["about:newtab", "about:home", "about:blank", "about:privatebrowsing"];

// always a new tab, the empty tab it was pressed in closed: loaded into a new-tab page, the address bar would keep the
// focus and bring up the on-screen keyboard
browser.browserAction.onClicked.addListener(async (tab) => {
  await browser.tabs.create({ url: VOICE_URL, index: tab ? tab.index + 1 : undefined });
  if (tab && EMPTY.includes(tab.url)) browser.tabs.remove(tab.id).catch(() => {});
});
