#!/usr/bin/env bash
# WanGP 逆向研究第三輪：E5 補測（73 幀＝原 transition 條件），同時驗證 H3 音軌檢查修正。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=/c/Users/XU/tools/comfyui-game-art-tutorial
OUT=$REPO/output/experiments/wangp-reverse-20261019
PY=/c/Users/XU/ComfyUI/.venv/Scripts/python.exe
AB="$HERE/ab_run.py"
export PYTHONIOENCODING=utf-8
LOG=$OUT/batch3.log

run() {
  local exp=$1 name=$2; shift 2
  local dir=$OUT/$exp/$name
  if [ -f "$dir/run.result.json" ]; then echo "=== skip $exp/$name" | tee -a "$LOG"; return; fi
  rm -rf "$dir"; mkdir -p "$(dirname "$dir")"
  local t0=$(date +%s)
  echo "=== $exp/$name start $(date -Iseconds)" | tee -a "$LOG"
  "$PY" "$AB" "$@" --config "$REPO/local_config.json" --allow-unverified-platform --timeout 1800 --output-dir "$dir" >"$dir.stdout.log" 2>&1
  echo "=== $exp/$name exit=$? elapsed=$(( $(date +%s)-t0 ))s" | tee -a "$LOG"
}

VR=$REPO/output/experiments/vfx-research-20261007/inputs
IDLE=$VR/skye_idle_square_1024.png
P_BASE="the chibi horse girl does a quick playful attack: she crouches, winds up and throws a fast forward punch with a small cyan ice spark, then recovers and settles back into exactly the same calm standing idle pose, feet return to the same spot, static locked camera, flat pure green chroma key background"
P_CAM="The chibi horse girl does a quick playful attack: she crouches, winds up and throws a fast forward punch with a small cyan ice spark, then recovers and settles back into exactly the same calm standing idle pose with her feet returning to the same spot. The camera stays completely still in a fixed wide full-body shot and her whole body remains inside the frame. Flat pure green chroma key background."
for s in 3002 3003 3004; do
  A=(-- --set start_image=$IDLE --set last_image=$IDLE --set length=73 --set seed=$s)
  run e5b_camera_73f base_s$s video/h3/img2video-last "${A[@]}" --set "prompt=$P_BASE" --set filename_prefix=e5b_base_s$s
  run e5b_camera_73f cam_s$s video/h3/img2video-last "${A[@]}" --set "prompt=$P_CAM" --set filename_prefix=e5b_cam_s$s
done
echo "=== ALL_DONE $(date -Iseconds)" | tee -a "$LOG"
