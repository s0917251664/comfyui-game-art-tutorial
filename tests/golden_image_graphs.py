"""圖片 graph 的凍結 golden:舊 Python builder 的最後輸出，現在只讀不寫。

``tests/fixtures/image_graphs_golden/<tier>.json`` 是 builder 移除前的 SDXL 各 tier graph。
builder 已刪除、templates/ 是唯一來源，所以這個檔案只提供 fixture 讀取與 tier 對照，
不再有重新產生 fixture 的流程；template 路徑送出的 graph 要和這些凍結 graph 逐欄相同
（見 test_image_task_template）。
"""

import contextlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_SRC = os.path.join(ROOT, "tools_src")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "image_graphs_golden")  # one <tier>.json per device tier

# Mirrors tools_src/detect_device.py TIERS (checkpoint and default resolution).
TIER_DEVICES = {
    "sdxl_high": {"tier": "sdxl_high", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024},
    "sdxl": {"tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024},
    "sdxl_light": {"tier": "sdxl_light", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 768, "default_height": 768},
}

SEED = 1234


def load_image_graphs():
    if TOOLS_SRC not in sys.path:
        sys.path.insert(0, TOOLS_SRC)
    with contextlib.redirect_stderr(io.StringIO()):
        from comfyui_pipeline import image_graphs
    return image_graphs


def tier_path(tier):
    return os.path.join(FIXTURE_DIR, f"{tier}.json")


def load_fixture():
    """Return {tier: {case: [graph, output_node]}} read from the per-tier files."""
    data = {}
    for tier in TIER_DEVICES:
        with open(tier_path(tier), encoding="utf-8") as handle:
            data[tier] = json.load(handle)
    return data
