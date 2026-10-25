#!/bin/bash
# On the tablet: capture a raw frame and a preview from one camera, after the exposure has settled. Calibration tool.
# usage: capture.sh <1=rear|2=front> <name> [target]   writes /var/tmp/calib/<name>.raw and <name>.nv12 (last frame of a
# short run). With a target the automatic exposure aims at that mean luminance (0..1) with no shadow constraint instead of
# the image's tuning, which lifts the shadows and so clips the bright patches of a chart on a dark ground. The IPU3 IPA has
# no manual exposure.
set -euo pipefail
cam_index=$1; name=$2; target=${3:-}; out=/var/tmp/calib; mkdir -p $out
if [ -n "$target" ]; then
    cat > $out/tuning.yaml <<YAML
version: 1
algorithms:
  - Agc:
      relativeLuminanceTarget: [ 0, $target ]
  - Awb:
YAML
    export LIBCAMERA_IPU3_TUNING_FILE=$out/tuning.yaml
fi
systemctl --user stop wireplumber@video-capture wireplumber 2>/dev/null || true
rm -f $out/tmp-*
timeout 60 cam -c "$cam_index" -s role=viewfinder -s role=raw -C40 --file="$out/tmp-#.bin" >/dev/null 2>&1
mv "$(ls $out/tmp-*stream1-* | tail -1)" "$out/$name.raw"
mv "$(ls $out/tmp-*stream0-* | sort | tail -1)" "$out/$name.nv12"
rm -f $out/tmp-* $out/tuning.yaml
systemctl --user start wireplumber wireplumber@video-capture 2>/dev/null || true
ls -la "$out/$name".*
