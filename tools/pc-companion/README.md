# The Surface as a screen of the PC

The PC (Bazzite) streams a virtual screen to the Surface with Sunshine; the Surface shows it with Moonlight (preinstalled by
the image), touch and pen going back to the PC. The virtual screen is made when the Surface connects, at the size it asks for,
below the PC's main monitor and centred (where the Surface stands as the second screen; the monitor stays on), at 100%; it goes when the Surface disconnects. Sunshine's touch screen and
pen tablet are mapped to it at every session (KWin would put them on the first monitor).

Capture is the XDG portal (`capture = portal`): KWin 6.8 never gives its own screencast to Flatpak apps, and the alternative,
KWIN_WAYLAND_NO_PERMISSION_CHECKS, would open it to every Flatpak. The portal captures a screen at its logical size, which is
why the virtual screen is at 100% (at 150% only its top left two thirds came through). For bigger text on the Surface, ask
Moonlight for 1200x800: less sharp, the size of the Surface's own 150%. The first connection asks on the PC to allow
Sunshine to see the screen and control input ("allow without asking next time").

PC, once:
1. `ujust setup-sunshine enable-flatpak` (Bazzite's own setup of Sunshine).
2. `tools/pc-companion/install.sh`: the scripts to `~/.local/bin`, portal capture, the "Surface Screen" app in Sunshine.
3. https://localhost:47990: the Sunshine user and password (first visit), then the PIN that Moonlight shows when pairing.

Surface: Moonlight, add the PC (found by itself at home; elsewhere by its Tailscale name `dsktp`), pair, open "Surface Screen".
In Moonlight's settings: resolution 1800x1200 (native), 60 fps.
