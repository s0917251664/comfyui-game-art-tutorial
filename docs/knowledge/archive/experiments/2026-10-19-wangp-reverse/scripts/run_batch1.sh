#!/usr/bin/env bash
# WanGP 逆向研究第一輪：E1 H3 取樣器、E5 鏡頭句型、E2 Wan 5B shift/steps、E3 VACE cfg/steps、E6 Animate 取樣器。
# 依序跑，每次一個 run 資料夾；失敗不重送，只記 exit code。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=/c/Users/XU/tools/comfyui-game-art-tutorial
OUT=$REPO/output/experiments/wangp-reverse-20261019
PY=/c/Users/XU/ComfyUI/.venv/Scripts/python.exe
AB="$HERE/ab_run.py"
VR=$REPO/output/experiments/vfx-research-20261007/inputs
export PYTHONIOENCODING=utf-8
mkdir -p "$OUT"
LOG=$OUT/batch1.log

run() {  # run <exp> <name> <template> [--patch ...] -- [gameart args]
  local exp=$1 name=$2; shift 2
  local dir=$OUT/$exp/$name
  if [ -f "$dir/run.result.json" ]; then echo "=== skip $exp/$name" | tee -a "$LOG"; return; fi
  rm -rf "$dir"; mkdir -p "$(dirname "$dir")"
  local t0=$(date +%s)
  echo "=== $exp/$name start $(date -Iseconds)" | tee -a "$LOG"
  "$PY" "$AB" "$@" --config "$REPO/local_config.json" --allow-unverified-platform --timeout 1800 --output-dir "$dir" >"$dir.stdout.log" 2>&1
  local code=$?
  echo "=== $exp/$name exit=$code elapsed=$(( $(date +%s)-t0 ))s" | tee -a "$LOG"
}

# ---------- E1 / E5：H3 首尾同圖（idle 錨定攻擊），56 幀 ----------
IDLE=$VR/skye_idle_square_1024.png
P_BASE="the chibi horse girl does a quick playful attack: she crouches, winds up and throws a fast forward punch with a small cyan ice spark, then recovers and settles back into exactly the same calm standing idle pose, feet return to the same spot, static locked camera, flat pure green chroma key background"
P_CAM="The chibi horse girl does a quick playful attack: she crouches, winds up and throws a fast forward punch with a small cyan ice spark, then recovers and settles back into exactly the same calm standing idle pose with her feet returning to the same spot. The camera stays completely still in a fixed wide full-body shot and her whole body remains inside the frame. Flat pure green chroma key background."
for s in 3002 3003; do
  H3ARGS=(-- --set start_image=$IDLE --set last_image=$IDLE --set seed=$s)
  run e1_h3_sampler res_multistep_s$s video/h3/img2video-last "${H3ARGS[@]}" --set "prompt=$P_BASE" --set filename_prefix=e1_resms_s$s
  run e1_h3_sampler euler_s$s video/h3/img2video-last --patch 17.sampler_name=euler "${H3ARGS[@]}" --set "prompt=$P_BASE" --set filename_prefix=e1_euler_s$s
  run e5_camera_sentence cam_sentence_s$s video/h3/img2video-last "${H3ARGS[@]}" --set "prompt=$P_CAM" --set filename_prefix=e5_cam_s$s
done

# ---------- E2：Wan 2.2 5B img2video，640x640、49 幀 ----------
P_IDLE="the chibi horse girl stands in place in a calm idle: gentle breathing, one blink, ears and tail sway slightly, feet stay planted, static locked camera, flat pure green chroma key background"
for s in 3001 3004; do
  WARGS=(-- --set start_image=$IDLE --set "prompt=$P_IDLE" --set width=640 --set height=640 --set seed=$s)
  run e2_wan5b shift8_20_s$s video/wan/img2video "${WARGS[@]}" --set filename_prefix=e2_s8_20_s$s
  run e2_wan5b shift5_20_s$s video/wan/img2video --patch 48.shift=5.0 "${WARGS[@]}" --set filename_prefix=e2_s5_20_s$s
  run e2_wan5b shift5_30_s$s video/wan/img2video --patch 48.shift=5.0 --patch 3.steps=30 "${WARGS[@]}" --set filename_prefix=e2_s5_30_s$s
  run e2_wan5b shift5_50_s$s video/wan/img2video --patch 48.shift=5.0 --patch 3.steps=50 "${WARGS[@]}" --set filename_prefix=e2_s5_50_s$s
done

# ---------- E3：VACE 1.3B keep 模式（錘子改色案例） ----------
SM=$REPO/output/experiments/vfx-video-inpaint-smoke-20261007
P_VACE="A cute chibi horse girl with light blue bob hair and horse ears lifts a big hammer. The hammer has a dark navy blue body, ornate gold end frames and glowing magenta purple crystal windows with a bright magenta purple magic glow. Flat pure green chroma key background, static camera, 2D anime game art."
for s in 202 203; do
  VARGS=(-- --set source_video=$VR/skye_hammer_ready_FINAL_1024.mp4 --set masks=$SM/masks_2keys --set mode=keep --set "prompt=$P_VACE" --set seed=$s)
  run e3_vace cfg6_20_s$s video/wan-vace/inpaint "${VARGS[@]}"
  run e3_vace cfg5_20_s$s video/wan-vace/inpaint --patch 3.cfg=5.0 "${VARGS[@]}"
  run e3_vace cfg5_30_s$s video/wan-vace/inpaint --patch 3.cfg=5.0 --patch 3.steps=30 "${VARGS[@]}"
done

# ---------- E6：Wan Animate Move 蒸餾 6 步，取樣器 ----------
WA=/c/Users/XU/ComfyUI/input/wan_animate_install
P_ANIM="The character turns its head and moves its hands exactly as in the source motion, same identity and outfit as the reference image."
for s in 42 43; do
  AARGS=(-- --set reference_image=$WA/reference.png --set source_video=$WA/source.mp4 --set "prompt=$P_ANIM" --set frames=17 --set seed=$s)
  run e6_animate euler_s$s video/wan-animate/move "${AARGS[@]}"
  run e6_animate unipc_s$s video/wan-animate/move --patch 63.sampler_name=uni_pc "${AARGS[@]}"
done

echo "=== ALL_DONE $(date -Iseconds)" | tee -a "$LOG"
