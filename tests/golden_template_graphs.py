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

RUN_ID = "golden"
SEED = 20261006
UPLOADS = {"reference_image": "run/reference.png", "source_video": "run/source.mp4", "seed_mask": "run/seed_mask.png"}
PROMPT = "the robot from the reference image dances, same pose as the source video"
POINTS = [{"x": 192, "y": 192}]
WAN_BASE = {"prompt": PROMPT, "seed": SEED}
SCAIL_BASE = {"prompt": PROMPT, "seed": SEED, "sam3_video_object": "person", "sam3_image_object": "robot"}

# (template id, case 名稱, slot 值, options)
CASES = [
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
]


def fixture_name(template_id, case):
    return f"{template_id.replace('/', '-')}__{case}.json"


def build_case(template_id, case, values, options, root=TEMPLATES):
    template = T.load_template(root, template_id, repo_root=ROOT)
    uploads = {name: path for name, path in UPLOADS.items() if name in template.upload_slots()}
    local = {name: f"local/{os.path.basename(path)}" for name, path in uploads.items()}  # resolve 只記錄本機路徑
    resolution = T.resolve(template, dict(local, **values), options, run_id=RUN_ID)
    graph, changes = T.patch(template, resolution, uploads)
    changed = {key: graph[key.split(".", 1)[0]]["inputs"][key.split(".", 1)[1]] for key in changes}
    return {
        "template": template_id, "case": case, "template_version": template.version,
        "graph_canonical_sha256": template.graph_canonical_sha256,
        "values": values, "options": resolution["options"], "uploads": uploads,
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
