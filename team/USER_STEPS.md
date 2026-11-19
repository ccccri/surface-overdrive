# Steps only the owner can do

Plain steps, in order. An agent that needs one of them done says so in chat (Italian) and points here; it never does them itself (D-023).

## 1. Bring the tablet back and update it

1. Wake or switch on the Surface and connect it to the charger for a while (an agent will not charge it for you; the charger's light is why it is not left on charge at night).
2. Open a terminal and run `sudo rpm-ostree upgrade` (it downloads the latest image; you do not need to restart yet).
3. Restart when convenient. After the restart the tablet runs the image with the new on-screen keyboard and PySide6 again. The hand-made test files on it disappear at the restart, by design.
4. Tell the agent. It checks: `rpm-ostree status`, `rpm -q plasma-keyboard` (ends `.overdrive1`), the camera app opens, `overdrivectl status` is green.

## 2. Try the on-screen keyboard

- Tap a text field: the keyboard comes up as before. **Hold the space bar**: a strip opens (Float, Split, Extra keys, Clipboard, Emoji, Settings); slide onto an entry and lift your finger.
  **Slide on the space bar**: the text cursor moves. **Float**: the bar at the top moves it, the corner at the top right resizes it (width and height). **Split**: two halves for the thumbs (landscape only).
  **Fn** on the extra row goes through the keys, the digits and F1-F12; Ctrl/Alt/Meta arm with a tap and work for the next key (Ctrl, then A).
- What nobody has seen yet: **the lock screen**. Lock the tablet and tap the password field: the keyboard must come up *docked*, with no clipboard key, and its menu must have no Float, Clipboard or Settings entries.
  Also try: a long press on an accented letter, the Italian layout (System Settings > On-Screen Keyboard > languages), a terminal (Ctrl+C, arrows), an app that runs under XWayland (the keyboard may not appear: known, T-10).
- Report what is wrong in a few words; screenshots of your own screen are fine to send to the agent (never commit them).

## 3. Test the camera stall fix (needs daylight)

The agent cannot do this while you sleep (the camera's light). In daylight, with the tablet awake: tell the agent "run the stall test"; it runs `tools/dev/camera_sharp_stall.sh 2` then `0` on the tablet.
Healthy output: a frame count for every second for about ten seconds. If the counts stop, the camera needs `systemctl --user restart wireplumber@video-capture` and the agent has more to do (T-12).

## 4. Later, when you want to

- **KDE defaults** (T-05): send the list of Plasma/KDE settings you want as defaults of the image (any form: names of the settings, screenshots, a `~/.config` diff). The agent writes them as defaults in `image/rootfs`.
- **Firefox voice search on addons.mozilla.org** (T-06): `docs/voice-search-amo.md` has the listing text and the package (`tools/package-voice-search.sh` builds the zip). You need your Mozilla account to submit it.
- **Delete old material on the PC** (T-15): `build-dal-duplicato/` in the repository folder holds about 24 GB of old capture data. Only you decide whether it goes.
- **GitHub**: the CI uses repository secrets `MOK_KEY` and `MOK_CERT_B64`; the push token must have the `workflow` scope (`gh auth refresh -h github.com -s workflow`) if a push is refused for touching workflows.

## 5. Things you may be asked in chat

- The **temporary administrator password** of the tablet, when a step needs root. It is used from the conversation only and is never stored; change it when the work is finished if you like.
- A restart of the tablet, a lock-screen check, a charge: whatever needs hands.
