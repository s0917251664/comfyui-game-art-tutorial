"""
穩定產圖核心腳本(不吃自然語言,只吃結構化參數)。

設計原則:
- 每個 task 對應一組鎖死大部分參數的 ComfyUI graph,只有明確列出的欄位可調
- 不靠 LLM 每次臨場組 JSON,參數集固定、行為可預期、可重複
- 上層(Skill/agent)的工作只是把自然語言整理成這裡要的結構化參數,不做生成邏輯本身

Usage:
    python generate.py --config local_config.json concept --prompt "a female game character concept art, fantasy armor" [--negative ...] [--seed N] [--width 1024] [--height 1024] [--remove-bg]
    python generate.py --config local_config.json flux2_concept --prompt "a readable game item concept" [--seed N] [--width 1024] [--height 1024]
    python generate.py --config local_config.json flux2_edit --prompt "turn the armor silver" --image path.png [--seed N]
    python generate.py --comfy-url http://127.0.0.1:8188 character_action --prompt "..." --character-ref path.png --pose-ref path.png [--pose-strength 1.0] [--remove-bg]
    python generate.py --config local_config.json inpaint --prompt "..." --image path.png --mask path.png [--denoise 1.0]
    python generate.py --config local_config.json img2video --image still.png --prompt "camera locked, idle motion" [--backend h3|wan] [--duration 2] [--timeout 1800]
    python generate.py --comfy-url http://127.0.0.1:8188 character_video --character-ref char.png --prompt "the same character running through a corridor" [--duration 2]
    python generate.py --config local_config.json camera_move --image still.png --camera zoom_in [--duration 2]
    python generate.py --config local_config.json pose_drive --image char.png --motion-ref motion.mp4 --prompt "the character performs the motion"
"""
import os
import sys

# 直接以 `python generate.py` 執行時 sys.path[0] 就是本檔所在資料夾;被其他腳本
# `import generate` 時它們也在同一資料夾,comfyui_pipeline 一律可 import。
from comfyui_pipeline import cli as _cli
# 其他腳本(face_swap / video_layers)以 generate.<名稱> 讀取的唯讀 re-export。
from comfyui_pipeline.client import (
    _fetch_comfy_object_info, download_outputs, resolve_comfy_url, submit_and_wait,
    upload_image, validate_timeout,
)
from comfyui_pipeline.image_capabilities import IMAGE_GRAPH_TASKS, check_image_graph_against_object_info
from comfyui_pipeline.video_catalog import VIDEO_BACKEND_SPECS, VIDEO_TASKS


def main(argv=None):
    _cli.run(argv)


if __name__ == "__main__":
    main()
