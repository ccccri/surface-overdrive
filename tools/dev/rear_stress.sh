#!/usr/bin/env bash
# Stress test of the rear camera through PipeWire, as applications use it. Every run checks the frames themselves (not black, not
# frozen, not a flat colour), not only that the process ended. Run it on the Surface as the seat user.
#
# usage: rear_stress.sh [minutes of the long run, default 10]
set -u
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/run/user/$(id -u)}
long=${1:-10}
rear=libcamera_input.__SB_.PCI0.LNK0
front=libcamera_input.__SB_.PCI0.LNK1
sizes=(1536x1152 2048x1536 2560x1920 3200x2400)
out=/var/tmp/rear-stress; rm -rf "$out"; mkdir -p "$out"
start=$(date '+%Y-%m-%d %H:%M:%S')
fail=0
log() { echo "$(date +%T) $*" | tee -a "$out/log"; }

# <node> <WxH> <frames> <file>: frames scaled to 160x120 grey, one after the other in <file>; 0 when gst ended well
grab() {
    local w=${2%x*} h=${2#*x}
    timeout $(( 60 + $3 / 5 )) gst-launch-1.0 -q pipewiresrc target-object="$1" num-buffers="$3" ! "video/x-raw,width=$w,height=$h" \
        ! videoconvert ! videoscale ! "video/x-raw,format=GRAY8,width=160,height=120" ! filesink location="$4" >/dev/null 2>&1
}
# <file> <frames wanted>: "ok" or what is wrong (count, black, flat, frozen)
check() {
    python3 - "$1" "$2" <<'PY'
import sys, statistics as st
data = open(sys.argv[1], "rb").read(); n = len(data) // 19200; want = int(sys.argv[2])
if n < want: print("only %d of %d frames" % (n, want)); sys.exit()
frames = [data[i*19200:(i+1)*19200] for i in range(n)][3:]          # the first frames may still be settling
bad = []
for i, f in enumerate(frames):
    m = sum(f) / len(f); sd = st.pstdev(f[::7])
    if m < 8: bad.append("black frame %d" % i)
    elif sd < 2: bad.append("flat frame %d" % i)
frozen = sum(1 for a, b in zip(frames, frames[1:]) if a == b)
if frozen > len(frames) // 3: bad.append("%d identical frames in a row" % frozen)
print("ok" if not bad else "; ".join(bad[:3]))
PY
}
crashes() { coredumpctl list --no-pager --since "$start" 2>/dev/null | grep -c -E "wireplumber|pipewire|gst-launch"; }

# every size on offer: no smallest size in the camera's profile
python3 -c "
import sys; sys.path.insert(0, '/usr/lib/overdrive/python')
from overdrive import camera; camera.set_setting('rear', 'minWidth', 0); camera.set_setting('front', 'minWidth', 0)" >/dev/null 2>&1

log "phase 1: 40 start/stop at every size"
for i in $(seq 1 40); do
    s=${sizes[$((RANDOM % 4))]}; n=$((10 + RANDOM % 30))
    grab $rear $s $n "$out/p1.raw"; r=$(check "$out/p1.raw" $n)
    [ "$r" = ok ] || { log "  run $i ($s, $n frames): $r"; fail=1; }
done
log "  crashes so far: $(crashes)"

log "phase 2: 15 size changes through the camera service (as the Cameras page does)"
for i in $(seq 1 15); do
    s=${sizes[$((RANDOM % 4))]}
    python3 -c "
import sys; sys.path.insert(0, '/usr/lib/overdrive/python')
from overdrive import camera; w = ${s%x*}; camera.set_setting('rear', 'minWidth', 0 if w == 1536 else w)" >/dev/null 2>&1
    grab $rear $s 15 "$out/p2.raw"; r=$(check "$out/p2.raw" 15)
    [ "$r" = ok ] || { log "  change $i to $s: $r"; fail=1; }
done
python3 -c "
import sys; sys.path.insert(0, '/usr/lib/overdrive/python')
from overdrive import camera; camera.set_setting('rear', 'minWidth', 0)" >/dev/null 2>&1
log "  crashes so far: $(crashes)"

log "phase 3: two applications on the rear camera at once, 10 times"
for i in $(seq 1 10); do
    grab $rear 1536x1152 60 "$out/p3a.raw" & sleep 0.$((RANDOM % 9 + 1))
    grab $rear 1536x1152 30 "$out/p3b.raw"; wait
    for f in p3a:60 p3b:30; do r=$(check "$out/${f%:*}.raw" ${f#*:}); [ "$r" = ok ] || { log "  run $i ${f%:*}: $r"; fail=1; }; done
done
log "  crashes so far: $(crashes)"

log "phase 4: rear and front one after the other, 20 times, and overlapping 10 times"
for i in $(seq 1 20); do
    grab $rear 1536x1152 12 "$out/p4r.raw"; r=$(check "$out/p4r.raw" 12); [ "$r" = ok ] || { log "  rear $i: $r"; fail=1; }
    grab $front 1152x864 12 "$out/p4f.raw"; r=$(check "$out/p4f.raw" 12); [ "$r" = ok ] || { log "  front $i: $r"; fail=1; }
done
for i in $(seq 1 10); do
    grab $rear 1536x1152 60 "$out/p4a.raw" & sleep 0.5
    grab $front 1152x864 30 "$out/p4b.raw"; wait
    for f in p4a:60 p4b:30; do r=$(check "$out/${f%:*}.raw" ${f#*:}); [ "$r" = ok ] || { log "  overlap $i ${f%:*}: $r"; fail=1; }; done
done
log "  crashes so far: $(crashes)"

log "phase 5: $long minutes without stopping at 1536x1152"
mem0=$(ps -o rss= -C pipewire | head -1)
frames=$((long * 60 * 30))
t0=$(date +%s)
grab $rear 1536x1152 $frames "$out/p5.raw"; rc=$?
t1=$(date +%s)
got=$(( $(stat -c %s "$out/p5.raw") / 19200 ))
mem1=$(ps -o rss= -C pipewire | head -1)
log "  $got frames in $((t1 - t0)) s ($(python3 -c "print('%.1f' % ($got / max(1, $t1 - $t0)))") fps), gst exit $rc, pipewire memory ${mem0} -> ${mem1} KiB"
r=$(check "$out/p5.raw" $frames); [ "$r" = ok ] || { log "  long run: $r"; fail=1; }

log "phase 6: crashes and kernel messages"
log "  crashes since start: $(crashes)"
journalctl -k --since "$start" --no-pager -o cat | grep -i -E "ipu3|imgu|cio2|ov8865|error|fail" | sort | uniq -c | sort -rn | head -10 | tee -a "$out/log"
log "done: $([ $fail = 0 ] && echo PASS || echo FAIL)"
