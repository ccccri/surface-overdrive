// Google's voice search without Google's page: the toolbar button opens listen.html (ours, local, instant) in the empty
// tab or a new one; Google listens in a tab behind it (press-mic.js presses its microphone and reports what it hears),
// and when Google searches, its results tab takes the place of listen.html.
const VOICE_URL = "https://www.google.com/?overdrive_voice=1";
const LISTEN_URL = browser.runtime.getURL("listen.html");
const EMPTY = ["about:newtab", "about:home", "about:blank"];
let job = null;            // { google: tab id, listen: tab id, port, done }

async function stop() {
  const j = job;
  job = null;
  if (j && !j.done) await browser.tabs.remove(j.google).catch(() => {});
}

// a new tab for listen.html, the empty tab it was pressed in closed: loaded into a new-tab page, the address bar would
// keep the focus and bring up the on-screen keyboard
browser.browserAction.onClicked.addListener(async (tab) => {
  await browser.tabs.create({ url: LISTEN_URL, index: tab ? tab.index + 1 : undefined });
  if (tab && (EMPTY.includes(tab.url) || tab.url === LISTEN_URL)) browser.tabs.remove(tab.id).catch(() => {});
});

browser.runtime.onConnect.addListener(async (port) => {
  if (port.name !== "listen" || !port.sender.tab) return;
  let gone = false;
  port.onDisconnect.addListener(() => { gone = true; if (job && job.port === port) stop(); });
  await stop();
  const listen = port.sender.tab;
  const google = await browser.tabs.create({ url: VOICE_URL, active: false, index: listen.index + 1 });
  if (gone) { browser.tabs.remove(google.id).catch(() => {}); return; }     // listen.html closed meanwhile
  job = { google: google.id, listen: listen.id, port, done: false };
});

browser.runtime.onMessage.addListener(async (msg, sender) => {
  if (!job || !sender.tab || sender.tab.id !== job.google) return;
  if (msg.type === "results") {
    job.done = true;
    const { google, listen } = job;
    job = null;
    await browser.tabs.update(google, { active: true });
    browser.tabs.remove(listen).catch(() => {});
  } else {
    job.port.postMessage(msg);       // what Google hears, or its state: on to listen.html
  }
});
