# The Surface as a screen of the PC

The PC (Bazzite) streams a virtual screen to the Surface with Sunshine; the Surface shows it with Moonlight (preinstalled by
the image), touch and pen going back to the PC. The virtual screen is made when the Surface connects, at the size it asks for,
and goes when the Surface disconnects. Two apps in Moonlight:
- **Extended Display** (at home, the Surface as a second screen): below the PC's main monitor and centred; the monitor
  stays on. Away from home (surface-screen-where: not on the PC's networks, or Tailscale not reaching it on them) the
  Surface shows a dialog over Moonlight: open the remote Desktop instead, Extended Display anyway, or cancel; another
  client is refused.
- **Desktop** (remote): from the Surface, the only screen, every window on it, Plasma's tablet mode (bigger targets, the
  on-screen keyboard on text fields, started again at the Surface's width); the PC's monitors go off for the session and
  come back when it ends, or by themselves 2 minutes after the client went away without quitting (the PC is not left
  dark). From any other client (a phone, another PC, games) it is the PC's main monitor as it is, with touch and pen
  mapped to it. The Surface is told by its Tailscale addresses or by asking for a 3:2 screen (its Wi-Fi address is random;
  surface-screen-is-surface).

Sunshine's touch screen, pen tablet and absolute mouse are kept mapped to the screen for the whole session (KWin would put
them on the first monitor, and a device may appear only when first used).

The virtual screen is always at 100%: the portal hands Sunshine a scaled screen at its logical size, and the picture came
out cropped (150%) or shrunk in a corner (125%). Bigger text is a smaller screen that the Surface enlarges (1440x960 for
125%): a scale set in System Settings during a session is turned into that within 2 s, and kept per app for the next
session (`~/.local/state/surface-screen/zoom-extend`, `zoom-only`). Sunshine follows the change without reconnecting.
Panels follow Plasma's own rules: the virtual screen keeps the panels added to it (Plasma knows it by its name), and with
Desktop the main monitor's panel moves to it.

Other clients and games: before every app, Sunshine's global prep runs surface-screen-stop, which clears whatever a session
of ours left behind (monitors off, the virtual screen) and does nothing otherwise. Sunshine captures by name
(`output_name = Virtual-surface`, set once): the Surface's screen when it is there, the first monitor otherwise. Starting another app while
one is running makes Moonlight quit the running one first, which undoes it. A client that resumes a running app gets that
app as it is: to stream the PC's monitor from a phone right after the Surface left without quitting, quit it in Moonlight
(long press on the app) and open it again. When Sunshine itself stops mid-session, an ExecStopPost drop-in undoes it too.

Capture is the XDG portal (`capture = portal`): KWin 6.8 never gives its own screencast to Flatpak apps, and the alternative,
KWIN_WAYLAND_NO_PERMISSION_CHECKS, would open it to every Flatpak. The first connection asks on the PC to allow
Sunshine to see the screen and control input ("allow without asking next time").

PC, once:
1. `ujust setup-sunshine enable-flatpak` (Bazzite's own setup of Sunshine).
2. `tools/pc-companion/install.sh`: the scripts to `~/.local/bin`, portal capture, the global prep, "Extended Display"
   and "Desktop" in Sunshine (Sunshine restarts, or is left for later while a client is connected).
3. https://localhost:47990: the Sunshine user and password (first visit), then the PIN that Moonlight shows when pairing.

Surface: Moonlight, add the PC (found by itself at home; elsewhere by its Tailscale name `dsktp`), pair, open "Extended Display" or "Desktop".
In Moonlight's settings: resolution 1800x1200 (native), 60 fps, and "Optimize mouse for remote desktop instead of games"
on: Moonlight sends the Surface pen as a mouse, which without it moves relative to where the pointer was. On the Surface, Moonlight opens on a
virtual desktop of its own (KWin script overdrive_stream_desktop): a three-finger swipe sideways goes back to the
Surface's desktop, with the stream still running. Opening Moonlight again from the menu replaces the running one (its
stream ends cleanly, the app keeps running on the PC): from there, the tile resumes it or its stop button quits it.


## Camera and microphone

During a session from the Surface (Extended Display or Desktop) the PC has the Surface's front camera and microphone,
used only on demand (surface-av, started and ended with the session):
- camera: the v4l2loopback device ("OBS Virtual Camera" on Bazzite) always shows something, so that apps list it: black
  while no app has it open, the Surface's camera from a second after one opens it until 5 s after it closes it (opens are
  counted with inotify on the device, which sees Flatpak apps and needs no permissions). Only then is the Surface's camera,
  and its light, on: H.264 on its graphics chip (1280x960, 30 fps, 4 Mbit/s), through ssh to the host "surface", decoded
  on the PC's; started again when frames stop (the camera taken by another app on the Surface).
- microphone: "Surface Microphone" is a PulseAudio tunnel to the Surface's microphone for the session (it follows the two
  machines' clocks). With nobody recording it is suspended and its stream on the Surface corked, so the microphone is
  used only while an app records. The Surface listens for it on its Tailscale address, for the PC's only, during the
  session.
- the camera stream says it is video (stream properties and caps): as "Stream/Input/Unknown", WirePlumber's linking did
  not find the camera once it had been restarted ("target not found"), and the PC got black frames.

Sound. Sunshine makes its own sink the default when a stream starts, records whatever sink is the default, and at the
end puts back the default it found when it started. With Extended Display (at home) its switch is undone once, and then
the user's choice stands: with a sink of the PC chosen Sunshine records its own silent stereo sink (the sound came out of
the Surface too), with one of Sunshine's (stereo, 5.1, 7.1) it records that one and the sound goes to the Surface. With
Desktop (remote) the sound goes to the Surface. At the end the sink in use before the session comes back (Sunshine's
own restore lost Bluetooth headphones).

On-screen keyboard: plasma-keyboard takes the width of the screen it starts on; in Extended Display that is the monitor,
and on the narrower Surface its sides were cut off. For the session it does not fill the screen width (three times its
height, about 1150 px), which fits; put back at the end.

Panels and wallpaper: with Desktop the main screen's panel moves to the Surface; there it goes to the left (3:2 screen)
and back to the bottom of the monitor at the end, each use remembering the position and thickness it was left with
(surface-screen-panel, ~/.local/state/surface-screen/panel-*). The wallpaper is the same on every screen (set once with
plasma-apply-wallpaperimage). Plasma's scripting interface is used for the panel; a script reading the desktops'
wallpaper settings made plasmashell crash once (it came back by itself), so only panels are touched.

Windows between the screens (KWin script `kwin/overdrive_screen_swap`, installed by install.sh): Meta+Shift+Down sends
the active window to the Surface, Meta+Shift+Up to the monitor, and a swipe in from the right edge of the Surface sends
it to the other screen.

Portal permission: the portal replaces Sunshine's restore token when it is used, and a stream that hung (the capture
never answered and Sunshine killed itself after 10 s) left the file with a token the portal no longer knew; KDE then
asked again on the PC, with every stream waiting on it. surface-screen-token (before Sunshine starts and before every
stream) writes the grant the user gave, found in the permission store, back into Sunshine's file. It grants nothing.

`touch-test.html`: a page that draws every finger the PC thinks is down (and a held mouse button). Open it on the PC
during a stream, swipe with three fingers on the Surface and back: no circle may stay on screen. To run it without
hands, a virtual touch screen on the Surface (uinput, as root) can tap and swipe like fingers.

In Discord/Vesktop: camera "OBS Virtual Camera", input "Surface Microphone". What it does goes to
`$XDG_RUNTIME_DIR/surface-screen.log` ("av:" lines).

`sunshine-open` replaces the Flatpak's menu entry (`~/.local/share/applications/dev.lizardbyte.app.Sunshine.desktop`):
Sunshine runs as a user service from login, and the original entry started a second copy beside it. Every Sunshine start
tests the encoders with about ten screen-sharing sessions (one "Started Remote Desktop" notification each, until KDE
throttles them): install.sh turns that popup off (`Event/remotedesktopstarted` in `xdg-desktop-portal-kde.notifyrc`,
for every app; the owner's choice), and `encoder = vaapi` (set when there is no NVIDIA card) skips the two tests that always fail here.
