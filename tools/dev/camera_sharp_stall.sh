#!/bin/bash
# Reproduction of the camera stall of 2026-11-11, to run ON THE TABLET in its desktop session (ssh: after exporting the
# session's environment). A front camera stream at 2560x1920 is started and, three seconds in, "sharpness" is changed in
# the camera's profile. Healthy: about 10 seconds of frames, a count for every second. The stall: the counts stop at
# second 3 and the camera stays dead until `systemctl --user restart wireplumber@video-capture`.
#
#   camera_sharp_stall.sh <new sharpness, 0 to 2>      (run it twice, e.g. 2 then 0: the stall needs sharpness > 0 before)
#
# The profile is put back at the end. The front camera's light is on while it runs.
set -u
P=~/.config/surface-overdrive/camera/ov5693.profile
mkdir -p "$(dirname "$P")"; touch "$P"
cp "$P" /var/tmp/ov5693.profile.bak
ID=$(pw-dump | python3 -c '
import json, sys
print([o["id"] for o in json.load(sys.stdin)
       if (o.get("info") or {}).get("props", {}).get("api.libcamera.location") == "front" and o.get("type", "").endswith("Node")][0])')
( sleep 3; grep -v "^sharpness" /var/tmp/ov5693.profile.bak > "$P.tmp"; echo "sharpness ${1:?new sharpness}" >> "$P.tmp"; mv "$P.tmp" "$P" ) &
timeout 10 gst-launch-1.0 pipewiresrc target-object="$ID" stream-properties=props,media.type=Video,media.category=Capture,media.role=Camera always-copy=true \
    ! video/x-raw,width=2560,height=1920 ! identity silent=false ! fakesink -v 2>&1 \
    | grep "identity0.*chain" | grep -oE "pts: [0-9:.]+" | awk -F"[: ]+" '{t=$3*60+$4; print int(t)}' | uniq -c | tr "\n" " "
echo
wait
cp /var/tmp/ov5693.profile.bak "$P"
