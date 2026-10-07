#!/usr/bin/env bash
# Start and stop the two cameras through PipeWire many times, alone and overlapping, and count WirePlumber crashes.
# Run it on the Surface from a graphical session (the camera nodes only exist for the seat user).
#
# usage: camera_stress.sh [cycles, default 40]
set -u

cycles=${1:-40}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
nodes=(libcamera_input.__SB_.PCI0.LNK0 libcamera_input.__SB_.PCI0.LNK1)   # rear, front
sizes=("320x240" "640x480" "1280x720" "1536x1152" "1152x864")

crashes() { coredumpctl list --no-pager --since "$start" 2>/dev/null | grep -c wireplumber; }
nodes_up() { pw-cli ls Node 2>/dev/null | grep -c 'libcamera_input'; }

run_one() {   # <node> <frames> <size>
    local w=${3%x*} h=${3#*x}
    timeout 40 gst-launch-1.0 -q pipewiresrc target-object="$1" num-buffers="$2" ! videoconvert ! videoscale \
        ! "video/x-raw,width=$w,height=$h" ! fakesink >/dev/null 2>&1
}

start=$(date '+%Y-%m-%d %H:%M:%S')
failed=0
for i in $(seq 1 "$cycles"); do
    a=$((RANDOM % 2)); b=$((1 - a))
    frames=$((5 + RANDOM % 40))
    size=${sizes[$((RANDOM % ${#sizes[@]}))]}
    case $((RANDOM % 3)) in
        0) run_one "${nodes[$a]}" "$frames" "$size" ;;                                  # one camera
        1) run_one "${nodes[$a]}" "$frames" "$size"; run_one "${nodes[$b]}" "$frames" "$size" ;;   # switch camera
        2) run_one "${nodes[$a]}" "$((frames + 30))" "$size" &                          # overlapping start and stop
           sleep "0.$((RANDOM % 9 + 1))"; run_one "${nodes[$b]}" "$frames" "$size"; wait ;;
    esac
    n=$(crashes)
    if [ "$n" -gt 0 ] || [ "$(nodes_up)" -lt 2 ]; then
        echo "cycle $i: crashes=$n camera nodes=$(nodes_up) (size $size, $frames frames)"
        failed=1
        break
    fi
    sleep 1
done
echo "cycles run: $i of $cycles; WirePlumber crashes since start: $(crashes)"
exit $failed
