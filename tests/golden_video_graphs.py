"""7 個影片 task(img2video、fx_loop、transition、clip_extend、camera_move、character_video、
pose_drive)的 golden graph 案例,給 ``test_video_graph_golden`` 用。

每個案例用 task 層的 ``tasks.video.prepare`` 組 graph:上傳、畫布、媒體驗證、抽尾幀與運鏡終點圖都換成
假的固定值,所以不需要 ComfyUI、Pillow、PyAV 或真的素材。模型檔名一律來自下面明確傳入的
``VIDEO_CONFIG``(不讀這台機器的 ``video_capabilities.json``),seed 固定。

每個案例寫一份 ``tests/fixtures/video_graphs_golden/<task>__<backend>__<case>.json``,內容有:
- ``args``:task 的 CLI 參數(只列和預設不同的)。
- ``builder``:第 6.1 階段 task 呼叫的 5 個 graph builder 之一,以及它收到的參數(``video_config`` 省略,
  固定是 ``VIDEO_CONFIG``)。PR 8.3 刪掉了 builder,這一欄是當時凍結的紀錄:``--write`` 會原樣保留,
  ``test_video_template_equiv`` 用它選 template。
- ``graph``、``output_node``、``graph_sha256``(和 result manifest 的 ``graph_sha256`` 同一個算法)。

graph 從第 6.3 階段起由 task 層填 template 產生,PR 8.3 起 golden 改由 template 維護(``graph`` 是 builder
時代凍結的值,template 變了才需要重寫)。只有在影片 template 是刻意修改時才執行
``python tests/golden_video_graphs.py --write``,並確認 graph 的 diff。
"""

import contextlib
import io
import json
import os
import sys
from types import SimpleNamespace
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_SRC = os.path.join(ROOT, "tools_src")
FIXTURE_DIR = os.path.join(ROOT, "tests", "fixtures", "video_graphs_golden")
if TOOLS_SRC not in sys.path:
    sys.path.insert(0, TOOLS_SRC)

SEED = 20261008
UPLOAD_SUBFOLDER = "golden"
# 沒給 --width/--height 時,假的 video_canvas 回傳的「跟來源圖比例走」畫布(16:9 來源縮到最長邊 768)。
SOURCE_CANVAS = (768, 448)

# 明確傳入的 machine capability config。檔名和 video_catalog 的內建 catalog 相同,
# 但 builder 只從這份 config 讀,不會碰這台機器的偵測快照。
VIDEO_CONFIG = {
    "schema_version": 1,
    "backends": {
        "h3": {
            "available": True,
            "capabilities": ["audio", "character_ref", "control_video", "i2v", "last_frame"],
            "models": {
                "i2v_unet": "minimax_h3_fl2va_pruned_int8_convrot.safetensors",
                "ref_unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
                "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
                "video_vae": "minimax_h3_video_vae_fp16.safetensors",
                "audio_vae": "minimax_h3_audio_vae_fp32.safetensors",
            },
        },
        "wan": {
            "available": True,
            "capabilities": ["control_video", "i2v"],
            "models": {
                "i2v_unet": "wan2.2_ti2v_5B_fp16.safetensors",
                "control_unet": "wan2.2_fun_control_5B_bf16.safetensors",
                "clip": "umt5_xxl_fp8_e4m3fn_scaled.safetensors",
                "vae": "wan2.2_vae.safetensors",
            },
        },
    },
}

BUILDERS = (
    "build_img2video_wan", "build_pose_drive_wan", "build_img2video_h3",
    "build_character_video_h3", "build_pose_drive_h3",
)

DEFAULT_ARGS = {
    "prompt": "the character breathes slowly in an idle stance", "image": "still.png",
    "duration": 2.0, "width": None, "height": None, "negative": None, "seed": SEED,
    "shot_id": None, "name": None, "output_dir": "out",
}

# (task, backend, case 名稱, 和 DEFAULT_ARGS 不同的參數)
CASES = [
    ("img2video", "wan", "default", {}),
    ("img2video", "wan", "negative_3s_512_shot", {
        "negative": "blurry, extra fingers", "duration": 3.0, "width": 512, "height": 512, "shot_id": "s01"}),
    ("img2video", "wan", "6s_portrait_named", {"duration": 6.0, "width": 448, "height": 768, "name": "hero_idle"}),
    ("img2video", "h3", "default", {}),
    ("img2video", "h3", "negative_ignored_3s_512", {"negative": "blurry", "duration": 3.0, "width": 512, "height": 512}),
    ("img2video", "h3", "6s_portrait_named", {"duration": 6.0, "width": 448, "height": 768, "name": "hero_idle"}),

    ("fx_loop", "h3", "loop_suffix_added", {"prompt": "flames flicker on the torch"}),
    ("fx_loop", "h3", "loop_word_kept", {"prompt": "a looping swirl of magic sparks", "duration": 4.0}),
    ("fx_loop", "h3", "negative_ignored_512", {
        "prompt": "water ripples", "negative": "text", "width": 512, "height": 512}),

    ("transition", "h3", "start_to_end", {
        "prompt": "the character draws a sword", "image": None, "start": "idle.png", "end": "attack.png"}),
    ("transition", "h3", "idle_action_idle_4s", {
        "prompt": "the character waves then returns to idle", "image": None, "start": "idle.png", "end": "idle.png",
        "duration": 4.0, "width": 512, "height": 512}),

    ("clip_extend", "wan", "from_image", {"prompt": "the character keeps walking", "image": "prev_last.png"}),
    ("clip_extend", "wan", "from_video_negative", {
        "prompt": "the character keeps walking", "image": None, "video": "prev.mp4", "negative": "blurry"}),
    ("clip_extend", "h3", "from_image", {"prompt": "the character keeps walking", "image": "prev_last.png"}),
    ("clip_extend", "h3", "from_video_3s", {
        "prompt": "the character keeps walking", "image": None, "video": "prev.mp4", "duration": 3.0}),

    ("camera_move", "wan", "static", {"prompt": "", "camera": "static"}),
    ("camera_move", "wan", "zoom_in_scene", {"prompt": "a quiet forest clearing", "camera": "zoom_in"}),
    ("camera_move", "wan", "orbit_cw_negative", {"prompt": "", "camera": "orbit_cw", "negative": "blurry"}),
]
# h3 有 last_frame:static 用原圖當尾幀、pan/zoom 上傳終點靜幀、orbit 只走 prompt。九種運鏡全部列出。
for _camera in ("static", "pan_up", "pan_down", "pan_left", "pan_right", "zoom_in", "zoom_out", "orbit_cw", "orbit_ccw"):
    CASES.append(("camera_move", "h3", _camera, {"prompt": "", "camera": _camera}))
CASES += [
    ("camera_move", "h3", "pan_right_scene_512", {
        "prompt": "a castle gate at dusk", "camera": "pan_right", "width": 512, "height": 512}),

    ("character_video", "h3", "one_ref", {
        "prompt": "the character jumps over a crate", "image": None, "character_ref": ["front.png"]}),
    ("character_video", "h3", "three_refs_4s", {
        "prompt": "the character jumps over a crate", "image": None,
        "character_ref": ["front.png", "side.png", "back.png"], "duration": 4.0}),
    ("character_video", "h3", "nine_refs_max", {
        "prompt": "the character spins around", "image": None,
        "character_ref": [f"ref{i}.png" for i in range(1, 10)]}),
    ("character_video", "h3", "explicit_picture_tag_512", {
        "prompt": "<Picture 1> jumps while <Picture 2> shows the back", "image": None,
        "character_ref": ["front.png", "back.png"], "width": 512, "height": 512}),
]
for _backend in ("wan", "h3"):
    for _control in ("pose", "canny", "depth"):
        CASES.append(("pose_drive", _backend, _control, {
            "prompt": "the character performs the dance", "motion_ref": "dance.mp4", "control_type": _control}))
CASES += [
    ("pose_drive", "wan", "pose_negative_3s_512", {
        "prompt": "the character performs the dance", "motion_ref": "dance.mp4", "control_type": "pose",
        "negative": "two people", "duration": 3.0, "width": 512, "height": 512}),
    ("pose_drive", "h3", "pose_explicit_video_tag", {
        "prompt": "<Picture 1> follows <Video 1>", "motion_ref": "dance.mp4", "control_type": "pose",
        "negative": "ignored by h3"}),
]


def fixture_name(task, backend, case):
    return f"{task}__{backend}__{case}.json"


def load_modules():
    """載入 task 模組。image_graphs 找不到 device_config 時會提醒,這裡吞掉。回傳 (task_video, image_results)。"""
    with contextlib.redirect_stderr(io.StringIO()):
        from comfyui_pipeline import image_results
        from comfyui_pipeline.tasks import video as task_video
    return task_video, image_results


def _fake_canvas(_path, width=None, height=None):
    return (width, height) if width and height else SOURCE_CANVAS


def _fake_upload(path):
    return f"{UPLOAD_SUBFOLDER}/{os.path.basename(os.fspath(path))}"


def _fake_temp_image_path(_out_dir, prefix):
    return f"{prefix}golden.png"


def task_args(task, backend, overrides):
    values = dict(DEFAULT_ARGS, task=task, backend=backend)
    values.setdefault("camera", None)
    values.update({"start": None, "end": None, "video": None, "character_ref": None,
                   "motion_ref": None, "control_type": "pose"})
    values.update(overrides)
    return SimpleNamespace(**values)


def run_task(task, backend, overrides, modules=None):
    """用 task 層組一次 graph(task 填 template),回傳 plan。"""
    task_video, _ = modules or load_modules()
    args = task_args(task, backend, overrides)
    ctx = SimpleNamespace(active_video_config=VIDEO_CONFIG)
    patches = [
        mock.patch.object(task_video, "video_canvas", _fake_canvas),
        mock.patch.object(task_video, "validate_transition_images", lambda *a, **k: None),
        mock.patch.object(task_video, "validate_motion_reference_fps", lambda *a, **k: None),
        mock.patch.object(task_video, "validate_video_input", lambda *a, **k: None),
        mock.patch.object(task_video, "extract_last_frame", lambda *a, **k: None),
        mock.patch.object(task_video, "build_camera_end_still", lambda *a, **k: None),
        mock.patch.object(task_video, "_make_temp_image_path", _fake_temp_image_path),
        mock.patch.object(task_video, "_remove_temp_file", lambda *a, **k: None),
    ]
    with contextlib.ExitStack() as stack:
        for patcher in patches:
            stack.enter_context(patcher)
        stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
        return task_video.prepare(ctx, args, _fake_upload)


def build_case(task, backend, case, overrides, modules=None):
    modules = modules or load_modules()
    plan = run_task(task, backend, overrides, modules)
    graph = json.loads(json.dumps(plan.graph))
    name = fixture_name(task, backend, case)
    builder = load_fixture(name)["builder"] if os.path.exists(os.path.join(FIXTURE_DIR, name)) else None
    return {
        "task": task, "backend": backend, "case": case, "args": overrides,
        "builder": builder,
        "output_node": plan.out_id, "graph_sha256": modules[1].graph_sha256(graph), "graph": graph,
    }


def build_all():
    modules = load_modules()
    return {fixture_name(task, backend, case): build_case(task, backend, case, overrides, modules)
            for task, backend, case, overrides in CASES}


def load_fixture(name):
    with open(os.path.join(FIXTURE_DIR, name), encoding="utf-8") as handle:
        return json.load(handle)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv != ["--write"]:
        print("用法: python tests/golden_video_graphs.py --write(只在刻意修改影片 graph 時執行)")
        return 2
    os.makedirs(FIXTURE_DIR, exist_ok=True)
    built = build_all()
    for name in os.listdir(FIXTURE_DIR):
        if name.endswith(".json") and name not in built:
            os.remove(os.path.join(FIXTURE_DIR, name))
    for name, data in built.items():
        with open(os.path.join(FIXTURE_DIR, name), "w", encoding="utf-8", newline="\n") as handle:
            handle.write(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(f"寫入 {len(built)} 個 golden 案例到 {FIXTURE_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
