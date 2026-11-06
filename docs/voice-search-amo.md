# Voice Search for Google: publishing on addons.mozilla.org

The extension lives in
`image/rootfs/usr/share/mozilla/extensions/{ec8030f7-c20a-464f-9b0e-13a3a9e97384}/voice-search@surfaceoverdrive.org`;
the image installs it from there, and `tools/package-voice-search.sh` lints it with Mozilla's web-ext and zips it into
`build/voice-search-for-google-<version>.zip` for the store. The files are the same in both. The image adds two things
around it (Firefox's default permissions with the microphone for google.com, and a policy that runs it in private
windows); a user who installs it from the store answers Firefox's microphone prompt once and allows private windows in
Add-ons, as the welcome page explains.

## Uploading (the account holder's steps)

1. Sign in at https://addons.mozilla.org/developers/ with a Mozilla account and accept the developer agreement.
2. "Submit a New Add-on" → "On this site" → upload `build/voice-search-for-google-<version>.zip`.
3. "Do you need to submit source code?": **No** (nothing is generated, minified or bundled).
4. Fill in the listing with the texts below, category **Search Tools**, license **MIT**.
5. Paste the reviewer notes. Review usually takes a few days.

A new version: raise `version` in `manifest.json`, run `tools/package-voice-search.sh`, upload the zip under
"Upload a New Version".

## Listing

**Name:** Voice Search for Google

**Summary (en-US):**
A microphone beside the address bar that opens Google's own voice search straight away: a clean listening screen, your
words as you speak, then Google's results.

**Summary (it):**
Un microfono accanto alla barra degli indirizzi che apre subito la ricerca vocale di Google: una schermata di ascolto
pulita, le tue parole mentre parli, poi i risultati di Google.

**Description (en-US):**
Searching by voice in Firefox takes three steps: open Google, find the microphone, wait. This extension makes it one
tap.

- A microphone button sits beside the address bar.
- One tap opens Google's own voice search, already listening: Google's home page is never shown, only a simple
  listening screen.
- Your words appear as Google hears them; when you stop talking, Google's results open.
- It is Google's recognition, the same as the microphone on google.com, not an offline engine.
- Made for touch screens and tablets too: no on-screen keyboard pops up.

The first time, Firefox asks to allow the microphone for google.com: choose Allow and tick "Remember this decision".
To use it in private windows, allow it in Add-ons and themes.

Not affiliated with or endorsed by Google. Google is a trademark of Google LLC.

**Description (it):**
Cercare a voce in Firefox richiede tre passaggi: aprire Google, trovare il microfono, aspettare. Con questa estensione
basta un tocco.

- Un pulsante microfono accanto alla barra degli indirizzi.
- Un tocco apre la ricerca vocale di Google, già in ascolto: la home di Google non compare mai, solo una semplice
  schermata di ascolto.
- Le tue parole compaiono mentre Google le sente; quando smetti di parlare si aprono i risultati.
- È il riconoscimento di Google, lo stesso del microfono su google.com, non un motore offline.
- Pensata anche per touch screen e tablet: non spunta la tastiera su schermo.

La prima volta Firefox chiede il permesso del microfono per google.com: scegli Consenti e spunta "Ricorda questa
decisione". Per usarla nelle finestre anonime, abilitala in Componenti aggiuntivi e temi.

Non affiliata né approvata da Google. Google è un marchio di Google LLC.

**Support site:** https://github.com/ccccri/surface-overdrive/issues

**Privacy policy:** not needed (no data is collected; `data_collection_permissions` is `none`). If asked:
> Voice Search for Google collects, stores and sends no data. It opens https://www.google.com in a tab and presses
> Google's own voice search button there; what you say goes to Google exactly as when you press the microphone on
> google.com yourself, under Google's privacy policy. The extension keeps nothing.

## Notes for the reviewer

> The browser action opens https://www.google.com/?overdrive_voice=1 in a new tab (closing the empty tab it was pressed
> in). The content script (press-mic.js, google.com only) acts only on pages opened with that marker, kept in
> sessionStorage for the tab: it clicks Google's own "Search by voice" button and reads the text of Google's listening
> dialog to show it on a listening screen (a closed shadow root) that covers Google's page while Google listens. It
> covers the page only when navigator.permissions reports the microphone as granted, so Firefox's permission prompt is
> never hidden. When Google opens its results the script stops. No remote code, no network requests of its own, no
> data collection. The "tabs" permission is used to know whether the tab the button was pressed in is an empty new-tab
> page (then it is closed). welcome.html is shown once after a normal install.
