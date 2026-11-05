// The toolbar button: Google in the tab that is empty, or in a new one, marked so that press-mic.js starts listening.
const VOICE_URL = "https://www.google.com/?overdrive_voice=1";
const EMPTY = ["about:newtab", "about:home", "about:blank"];

browser.browserAction.onClicked.addListener(async (tab) => {
  if (tab && EMPTY.includes(tab.url)) {
    await browser.tabs.update(tab.id, { url: VOICE_URL });
  } else {
    await browser.tabs.create({ url: VOICE_URL });
  }
});
