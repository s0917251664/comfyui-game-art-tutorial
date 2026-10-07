#!/usr/bin/env bash
# Sequential H3/Wan generation for vfx-research-20261007. Logs elapsed per job.
set -u
cd /c/Users/XU/tools/comfyui-game-art-tutorial
OUT=output/experiments/vfx-research-20261007
PY=/c/Users/XU/ComfyUI/.venv/Scripts/python.exe
GEN=/c/Users/XU/ComfyUI/tools/generate.py
export PYTHONIOENCODING=utf-8
run() { local name=$1; shift; local t0=$(date +%s); echo "=== $name start $(date -Iseconds)"; "$PY" "$GEN" "$@" --config local_config.json --timeout 1800 2>&1 | tail -8; echo "=== $name exit=${PIPESTATUS[0]} elapsed=$(( $(date +%s)-t0 ))s"; }
FXP="the icy frost burst flickers and swirls in place, glowing cyan ice particles drift slowly upward and fade, soft pulsing glow, static locked camera"
run r1_fx_black fx_loop --backend h3 --image $OUT/inputs/fx_ice_burst_black.png --seed 1001 --duration 2 --name r1_fx_black --output-dir $OUT/req1 --prompt "$FXP, the background stays solid pure black"
run r1_fx_green fx_loop --backend h3 --image $OUT/inputs/fx_ice_burst_green.png --seed 1001 --duration 2 --name r1_fx_green --output-dir $OUT/req1 --prompt "$FXP, the background stays a flat uniform pure green chroma key screen"
IDLE=$OUT/inputs/skye_idle_square_1024.png
IDP="the chibi horse girl stands in place in a calm idle: gentle breathing, one blink, ears and tail sway slightly, feet stay planted, static locked camera, flat pure green chroma key background"
run r3_idle_loop_fx fx_loop --backend h3 --image $IDLE --seed 3001 --duration 2 --name r3_idle_loop_fxloop --output-dir $OUT/req3 --prompt "$IDP"
run r3_attack_transition transition --backend h3 --start $IDLE --end $IDLE --seed 3002 --duration 3 --extract-frames --name r3_attack_idle_transition --output-dir $OUT/req3 --prompt "the chibi horse girl does a quick playful attack: she crouches, winds up and throws a fast forward punch with a small cyan ice spark, then recovers and settles back into exactly the same calm standing idle pose, feet return to the same spot, static locked camera, flat pure green chroma key background"
run r3_idle_img2video_h3 img2video --backend h3 --image $IDLE --seed 3001 --duration 2 --extract-frames --name r3_idle_img2video_h3 --output-dir $OUT/req3 --prompt "$IDP"
run r3_idle_img2video_wan img2video --backend wan --image $IDLE --seed 3001 --duration 2 --extract-frames --name r3_idle_img2video_wan --output-dir $OUT/req3 --prompt "$IDP"
echo ALL_DONE
