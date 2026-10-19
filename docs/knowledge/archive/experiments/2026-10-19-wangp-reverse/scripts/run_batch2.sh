#!/usr/bin/env bash
# WanGP 逆向研究第二輪：E4 VACE 參考圖注入（白底置中的冰錘母版）。等第一輪 ALL_DONE 才開始。
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=/c/Users/XU/tools/comfyui-game-art-tutorial
OUT=$REPO/output/experiments/wangp-reverse-20261019
PY=/c/Users/XU/ComfyUI/.venv/Scripts/python.exe
AB="$HERE/ab_run.py"
export PYTHONIOENCODING=utf-8
LOG=$OUT/batch2.log
until grep -q ALL_DONE "$OUT/batch1.log" 2>/dev/null; do sleep 20; done

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

# 參考圖由研究前處理放在 ComfyUI/input/wangp_research/hammer_ref_white.png（560x560 白底、母版置中縮到 90%）
REF='90={"class_type":"LoadImage","inputs":{"image":"wangp_research/hammer_ref_white.png"}}'
SRC=$REPO/output/experiments/vfx-research-20261007/inputs/skye_hammer_ready_FINAL_1024.mp4
MASKS=$REPO/output/experiments/vfx-video-inpaint-smoke-20261007/masks_2keys
P_HAM="A cute chibi horse girl with light blue bob hair and horse ears lifts a big war hammer. The hammer head is dark navy blue with ornate gold end caps set with round red gems, tall glowing cyan ice crystal windows on both ends, and a white ice lightning emblem in the center; the handle is wrapped in brown leather with gold rings and a navy blue pommel. Flat pure green chroma key background, static camera, 2D anime game art."
for s in 202 203; do
  A=(-- --set source_video=$SRC --set masks=$MASKS --set "prompt=$P_HAM" --set seed=$s)
  run e4_vace_ref replace_noref_s$s video/wan-vace/inpaint "${A[@]}" --set mode=replace
  run e4_vace_ref replace_ref_s$s video/wan-vace/inpaint --add-node "$REF" --patch 55.reference_image=@link:90:0 "${A[@]}" --set mode=replace
  run e4_vace_ref keep_noref_s$s video/wan-vace/inpaint "${A[@]}" --set mode=keep
  run e4_vace_ref keep_ref_s$s video/wan-vace/inpaint --add-node "$REF" --patch 55.reference_image=@link:90:0 "${A[@]}" --set mode=keep
done
echo "=== ALL_DONE $(date -Iseconds)" | tee -a "$LOG"
