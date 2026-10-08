"""固定 API graph template 的 golden patched-graph 案例,給 ``test_templates`` 用。

每個案例用固定的 run_id、seed 與假的上傳路徑(模擬 ComfyUI 回傳的 ``subfolder/name``)跑
``resolve`` → ``patch``,把完整 graph 與「改到的欄位」(diff 白名單)寫進
``tests/fixtures/template_graphs_golden/<template id 以 - 連接>__<case>.json``。

只有在 template.json 或 graph 是刻意修改時才執行 ``python tests/golden_template_graphs.py --write``。
"""

import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_SRC = os.path.join(ROOT, "tools_src")
TEMPLATES = os.path.join(ROOT, "templates")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "template_graphs_golden")
if TOOLS_SRC not in sys.path:
    sys.path.insert(0, TOOLS_SRC)

from comfyui_pipeline.runner import template as T  # noqa: E402
from comfyui_pipeline.video_catalog import CHARACTER_REF_MAX  # noqa: E402

RUN_ID = "golden"
SEED = 20261006
UPLOADS = {"reference_image": "run/reference.png", "source_video": "run/source.mp4", "seed_mask": "run/seed_mask.png",
           "control_video": "run/control.mkv", "mask_video": "run/mask.mkv",
           "image": "run/image.png", "mask": "run/mask.png", "pose_ref": "run/pose_ref.png",
           "character_ref": "run/character_ref.png", "structure_ref": "run/structure_ref.png",
           "appearance_ref": "run/appearance_ref.png", "control_ref": "run/control_ref.png",
           "start_image": "run/start.png", "last_image": "run/last.png", "motion_video": "run/motion.mp4"}
UPLOADS.update({f"ref_image_{index}": f"run/ref_{index}.png" for index in range(1, CHARACTER_REF_MAX + 1)})
PROMPT = "the robot from the reference image dances, same pose as the source video"
POINTS = [{"x": 192, "y": 192}]
WAN_BASE = {"prompt": PROMPT, "seed": SEED}
SCAIL_BASE = {"prompt": PROMPT, "seed": SEED, "sam3_video_object": "person", "sam3_image_object": "robot"}
VACE_PROMPT = "a glowing blue crystal hammer, game art, clean edges"
VACE_BASE = {"prompt": VACE_PROMPT, "seed": SEED, "source_video": "local/source.mp4", "masks": "local/masks"}
# 有 from_pre slot 的 template:pre 步驟的結果(實際執行時由 vace_work_area 量出)
VACE_1024 = {"vace_work_area": {"frames": 56, "width": 544, "height": 560, "length": 57}}
VACE_SMALL = {"vace_work_area": {"frames": 9, "width": 192, "height": 128, "length": 9}}
VACE_WIDE = {"vace_work_area": {"frames": 81, "width": 832, "height": 480, "length": 81}}

# (template id, case 名稱, slot 值, options)
VIDEO_CASES = [
    ("video/wan-animate/mix", "default17", dict(WAN_BASE, positive_points=POINTS), {}),
    ("video/wan-animate/mix", "frames33", dict(WAN_BASE, positive_points=POINTS, frames=33), {}),
    ("video/wan-animate/mix", "audio", dict(WAN_BASE, positive_points=POINTS), {"keep_audio": True}),
    ("video/wan-animate/mix", "portrait384x640_points", dict(
        WAN_BASE, width=384, height=640, positive_points=[{"x": 192, "y": 320}, {"x": 192, "y": 120}],
        negative_points=[{"x": 10, "y": 630}]), {}),
    ("video/wan-animate/move", "default17", dict(WAN_BASE), {}),
    ("video/wan-animate/move", "portrait384x640", dict(WAN_BASE, height=640), {}),
    ("video/wan-animate/move", "audio", dict(WAN_BASE), {"keep_audio": True}),
    ("video/wan-animate/mix-extend", "same_seed", dict(WAN_BASE, positive_points=POINTS), {}),
    ("video/wan-animate/mix-extend", "seed2_differs", dict(WAN_BASE, positive_points=POINTS, seed_segment2=7), {}),
    ("video/wan-animate/mix-extend", "audio", dict(WAN_BASE, positive_points=POINTS), {"keep_audio": True}),
    ("video/wan-animate/move-extend", "default", dict(WAN_BASE), {}),
    ("video/wan-animate/scail2", "replace", dict(SCAIL_BASE), {}),
    ("video/wan-animate/scail2", "animate_mode", dict(SCAIL_BASE, replacement_mode=False), {}),
    ("video/wan-animate/scail2", "object_indices_0_2", dict(SCAIL_BASE, object_indices="0,2"), {}),
    ("video/wan-animate/scail2", "audio", dict(SCAIL_BASE), {"keep_audio": True}),
    ("video/wan-animate/scail2", "w832x448", dict(SCAIL_BASE, width=832, height=448), {}),
    ("video/wan-animate/scail2-extend", "replace", dict(SCAIL_BASE), {}),
    ("video/wan-animate/scail2-extend", "animate_mode", dict(SCAIL_BASE, replacement_mode=False), {}),
    ("video/sam3/track-mask", "default", {}, {}),
    ("video/sam3/track-text", "mallet", {"track_text": "mallet"}, {}),
    ("video/wan-vace/inpaint", "keep_1024", dict(VACE_BASE), {}),
    ("video/wan-vace/inpaint", "replace_small", dict(VACE_BASE, mode="replace", grow=4, feather=0), {}),
    ("video/wan-vace/inpaint", "strength_negative", dict(VACE_BASE, strength=0.6, negative="blurry, flicker"), {}),
    ("video/wan-vace/inpaint", "wide81_crop", dict(VACE_BASE, crop="0,0,832,480", pad=0), {}),
]
# 第 6.2 階段：每個影片 template 至少一個案例。上傳檔名來自 UPLOADS，不進 values。
VIDEO_TEMPLATE_IDS = [
    "video/wan/img2video",
    "video/h3/img2video",
    "video/h3/img2video-last",
    *[f"video/{backend}/pose-drive-{control}" for backend in ("wan", "h3") for control in ("canny", "pose", "depth")],
    *[f"video/h3/character-video-{count}" for count in range(1, CHARACTER_REF_MAX + 1)],
]
VIDEO_PROMPT = "the character breathes slowly in an idle stance"


def _image_case_values(template):
    values = {}
    if "prompt" in template.slots:
        values["prompt"] = "p"
    if "seed" in template.slots:
        values["seed"] = SEED
    if "lora_name" in template.slots:
        values["lora_name"] = "test_lora.safetensors"
        values["lora_strength"] = 0.6
    return values


def _image_cases():
    """每個已落地的圖片 template 一個案例。sd15 目錄不在時就不列入。"""
    cases = []
    for template_id in T.discover(TEMPLATES):
        if not template_id.startswith("image/"):
            continue
        template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
        cases.append((template_id, "defaults", _image_case_values(template), {}))
    return cases


CASES = VIDEO_CASES + [
    (template_id, "default", {"prompt": VIDEO_PROMPT, "seed": SEED}, {}) for template_id in VIDEO_TEMPLATE_IDS
] + _image_cases()
PRE_RESULTS = {("video/wan-vace/inpaint", "keep_1024"): VACE_1024, ("video/wan-vace/inpaint", "replace_small"): VACE_SMALL,
               ("video/wan-vace/inpaint", "strength_negative"): VACE_1024,
               ("video/wan-vace/inpaint", "wide81_crop"): VACE_WIDE}


def fixture_name(template_id, case):
    return f"{template_id.replace('/', '-')}__{case}.json"


def build_case(template_id, case, values, options, root=TEMPLATES):
    template = T.load_template(root, template_id, repo_root=ROOT)
    uploads = {name: path for name, path in UPLOADS.items() if name in template.upload_slots()}
    local = {name: f"local/{os.path.basename(path)}" for name, path in uploads.items()  # resolve 只記錄本機路徑
             if not template.slots[name].get("generated")}  # generated 由 pre 步驟產生,不能指定
    resolution = T.resolve(template, dict(local, **values), options, run_id=RUN_ID)
    pre = PRE_RESULTS.get((template_id, case))
    if pre:
        T.fill_from_pre(template, resolution, pre)
    graph, changes = T.patch(template, resolution, uploads)
    changed = {key: graph[key.split(".", 1)[0]]["inputs"][key.split(".", 1)[1]] for key in changes}
    return {
        "template": template_id, "case": case, "template_version": template.version,
        "graph_canonical_sha256": template.graph_canonical_sha256,
        "values": values, "options": resolution["options"], "uploads": uploads,
        **({"pre_results": pre} if pre else {}),
        "changed": changed, "patched_graph_sha256": T.canonical_sha256(graph), "graph": graph,
    }


def build_all():
    return {fixture_name(tid, case): build_case(tid, case, values, options) for tid, case, values, options in CASES}


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--write"]:
        print("用法: python tests/golden_template_graphs.py --write(只在刻意修改 template 時執行)")
        return 2
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    built = build_all()
    for name in os.listdir(FIXTURE_DIR):
        if name.endswith(".json") and name not in built:
            os.remove(os.path.join(FIXTURE_DIR, name))
    for name, data in built.items():
        with open(os.path.join(FIXTURE_DIR, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    print(f"寫入 {len(built)} 個 golden 案例到 {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
