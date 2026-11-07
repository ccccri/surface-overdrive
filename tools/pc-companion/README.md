# The Surface as a screen of the PC

The PC (Bazzite) streams a virtual screen to the Surface with Sunshine; the Surface shows it with Moonlight (preinstalled by
the image), touch and pen going back to the PC. The virtual screen is made when the Surface connects, at the size it asks for,
at the right of the PC's monitors (they stay on), at 150% like the Surface; it goes when the Surface disconnects.

PC, once:
1. `ujust setup-sunshine enable-flatpak` (Bazzite's own setup of Sunshine).
2. `tools/pc-companion/install.sh`: the scripts to `~/.local/bin`, KWin capture, the "Surface Screen" app in Sunshine.
3. https://localhost:47990: the Sunshine user and password (first visit), then the PIN that Moonlight shows when pairing.

Surface: Moonlight, add the PC (found by itself at home; elsewhere by its Tailscale name `dsktp`), pair, open "Surface Screen".
In Moonlight's settings: resolution 1800x1200 (native), 60 fps.
