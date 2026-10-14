#!/usr/bin/env bash
# Screen-sized copies of the default wallpaper, for each orientation of the Surface Go screen.
#
# Fedora's wallpaper is one 4096x4096 JPEG XL image. Plasma loads it again at every turn of the screen, and on the Surface Go's
# processor decoding it takes about a second, during which the desktop and the panel keep their old size. Measured: with a
# JPEG at the size of the screen, the desktop has its new size 70-190 ms after a turn instead of up to 1.5 s. Plasma picks the
# file whose name matches the screen size, so the copies only need to sit next to the original.
#
# usage: wallpaper_sizes.sh <output root>      (run in a stage built from the base image)
set -euo pipefail
out=${1:?usage: wallpaper_sizes.sh <output root>}
pkg=$(readlink -f /usr/share/wallpapers/Default)
for dir in images images_dark; do
    [ -d "$pkg/contents/$dir" ] || continue
    src=$(find "$pkg/contents/$dir" -maxdepth 1 -name '*.jxl' -print -quit)
    [ -n "$src" ] || { echo "no JPEG XL image in $pkg/contents/$dir: nothing to do"; continue; }
    src=$(readlink -f "$src")
    mkdir -p "$out$pkg/contents/$dir"
    djxl "$src" /tmp/wallpaper.png >/dev/null
    for size in 1800x1200 1200x1800; do
        vipsthumbnail /tmp/wallpaper.png --size "$size" --smartcrop centre -o "$out$pkg/contents/$dir/$size.jpg[Q=92,strip]"
    done
    ls -la "$out$pkg/contents/$dir"
done
