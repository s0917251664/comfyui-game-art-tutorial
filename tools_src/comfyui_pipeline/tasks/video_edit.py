"""ComfyUI 影片 task:video_inpaint(Wan2.1 VACE 遮罩局部重繪,只改遮罩內,貼回原片)。

PR 8.3b 起整個交給 template runner 執行(``video/wan-vace/inpaint``):runner 的 pre 步驟讀來源片與遮罩、
擴張遮罩、算工作區、編成無損 FFV1 上傳;送出固定 graph;post 步驟檢查輸出、貼回原片、逐幀檢查遮罩外
不變。CLI 名稱與旗標不變。輸出改在 ``<output-dir>/<名稱>_run/``(runner 的 run 資料夾,含 ``run.result.json``),
貼回結果在 ``composited/``,並另外寫一份和舊版欄位相同的 ``composited/result.json``
(kind ``video_inpaint_paste_back``)。
"""
import json
import os
import tempfile
from pathlib import Path

from ..client import OUTPUT_DIR
from ..runner import template as runner_template
from ..video_catalog import VIDEO_FPS
from ..video_config import require_video_backend
from ..video_contract import _safe_identifier, video_filename_prefix

VACE_TEMPLATE_ID = "video/wan-vace/inpaint"

TASKS = ("video_inpaint",)


def add_parser(sub, parents, task):
    summary = ("影片局部重繪(VACE):只重畫遮罩內,遮罩外貼回原片且逐 byte 不變。"
               "遮罩(白色=重畫)預設來自 SAM3 固定 graph;SAM3 不可用時用 SAM2.1 的 video_layers segment。")
    p = sub.add_parser(task, help=summary, description=summary, parents=[parents["video"]])
    p.add_argument("--video", required=True, help="來源影片(24 FPS,最多 81 幀)")
    p.add_argument("--masks", required=True,
                   help="逐幀遮罩:白色=重畫的 PNG 資料夾(SAM3 graph 下載的遮罩可直接用),或 video_layers segment(SAM2.1 備用)的 layers.zip")
    p.add_argument("--mask-object", type=int, default=1, help="--masks 是 layers.zip 時取哪個物件 id,預設 1")
    p.add_argument("--prompt", required=True, help="描述整個畫面、特別是遮罩內要變成什麼(英文較穩)")
    p.add_argument("--mode", choices=["keep", "replace"], default="keep",
                   help="keep=保留遮罩內原內容當引導(改顏色/光效/材質,造型較能保住);"
                        "replace=遮罩內清空重畫(換成新物件,官方模板做法)")
    p.add_argument("--grow", type=int, default=8, help="遮罩向外擴張像素,預設 8")
    p.add_argument("--feather", type=int, default=4, help="貼回時邊緣羽化像素,預設 4;0=硬邊")
    p.add_argument("--pad", type=int, default=48, help="自動工作區在遮罩外留的邊,預設 48")
    p.add_argument("--crop", help="手動工作區 x0,y0,x1,y1(來源像素座標);不給就依遮罩自動算")
    p.add_argument("--strength", type=float, default=1.0, help="VACE 控制強度,預設 1.0")
    p.add_argument("--negative", help="負向詞;不給就用官方模板的預設負向詞")
    p.add_argument("--seed", type=int)


def _parse_crop(value):
    if value is None:
        return None
    parts = [p.strip() for p in str(value).split(",")]
    if len(parts) != 4:
        raise ValueError("--crop 格式是 x0,y0,x1,y1")
    try:
        return tuple(int(p) for p in parts)
    except ValueError as exc:
        raise ValueError("--crop 必須是 4 個整數") from exc


def validate(args):
    _safe_identifier(getattr(args, "shot_id", None), "--shot-id")
    _safe_identifier(getattr(args, "name", None), "--name")
    if getattr(args, "resume", False) and not (getattr(args, "shot_id", None) or getattr(args, "name", None)):
        raise ValueError("--resume 需要 --name 或 --shot-id 才能精確定位輸出")
    for label, value, upper in (("--grow", args.grow, 64), ("--feather", args.feather, 32), ("--pad", args.pad, 512)):
        if not 0 <= value <= upper:
            raise ValueError(f"{label} 必須介於 0..{upper}")
    if not 0.0 < args.strength <= 10.0:
        raise ValueError("--strength 必須介於 (0, 10]")
    if not 1 <= args.mask_object <= 999:
        raise ValueError("--mask-object 必須介於 1..999")
    _parse_crop(args.crop)


def _repo_with_vace_template():
    """從這個檔案往上找含 VACE template 的 repo 根目錄；部署端是 <ComfyUI>/tools(PR 8.4 起 templates/ 跟著部署)。"""
    for parent in Path(__file__).resolve().parents:
        marker = parent / "templates" / "video" / "wan-vace" / "inpaint" / "template.json"
        if marker.is_file():
            return parent
    raise SystemExit(
        "video_inpaint 的 graph 在 templates/video/wan-vace/inpaint（固定 template，由 runner 填值）。"
        "請從 repo 執行 python tools_src/generate.py video_inpaint。"
        "部署端要先用 gameart.py deploy 把 templates/ 部署到 ComfyUI/tools。"
    )


def _slot_values(args):
    """CLI 參數 → template slot 值(和舊 graph_from_vace_template 相同的對應)。seed 已由 cli 定好(只抽一次)。"""
    values = {
        "source_video": os.path.abspath(args.video),
        "masks": os.path.abspath(args.masks),
        "prompt": args.prompt,
        "mode": args.mode,
        "grow": args.grow,
        "pad": args.pad,
        "feather": args.feather,
        "mask_object": args.mask_object,
        "strength": args.strength,
    }
    if args.crop:
        values["crop"] = args.crop
    if args.negative:
        values["negative"] = args.negative
    if args.seed is not None:
        values["seed"] = args.seed
    return values


def run_folder(args):
    out_dir = getattr(args, "output_dir", None) or OUTPUT_DIR
    prefix = video_filename_prefix(args.task, getattr(args, "shot_id", None), getattr(args, "name", None))
    return Path(out_dir) / f"{prefix}_run"


def run_with_runner(ctx, args, comfy_url, *, runner_main=None):
    """整個交給 ``gameart.py run video/wan-vace/inpaint``(同一個 runner,先 preflight)。回傳結束碼。"""
    require_video_backend(args.task, args.backend, ctx.active_video_config)
    if getattr(args, "resume", False):
        raise SystemExit("video_inpaint 改由 template runner 執行後不支援 --resume;runner 失敗時不會重送,"
                         "請看 <名稱>_run/run.result.json,用新的 --name 重跑")
    root = _repo_with_vace_template()
    folder = run_folder(args)
    if folder.exists() and any(folder.iterdir()):
        raise SystemExit(f"拒絕覆寫既有輸出: {folder}(換一個 --name 或 --output-dir)")
    if runner_main is None:
        from ..runner import cli as runner_cli
        runner_main = runner_cli.main
    fd, values_path = tempfile.mkstemp(prefix="video_inpaint_values_", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(_slot_values(args), handle, ensure_ascii=False)
        argv = [VACE_TEMPLATE_ID, "--values", values_path, "--output-dir", str(folder),
                "--comfy-url", comfy_url, "--timeout", str(args.timeout)]
        if getattr(args, "config_path", None):
            argv += ["--config", os.path.abspath(args.config_path)]
        code = runner_main(argv, root=runner_template.templates_root(root))
    finally:
        os.unlink(values_path)
    manifest_path = folder / "run.result.json"
    if code == 0 and manifest_path.is_file():
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        out = write_compat_result(args, folder, manifest)
        print(f"[貼回] {out['source']['frames']} 幀 -> {folder / 'composited'}"
              f"(遮罩外變動 {out['outside_changed_pixels_total']})")
    return code


def _check_detail(manifest, step):
    for check in (manifest.get("technical_validation") or {}).get("checks") or []:
        if check.get("step") == step:
            return check.get("detail") or {}
    raise RuntimeError(f"run.result.json 沒有 {step} 的檢查結果")


def write_compat_result(args, folder, manifest):
    """寫 ``composited/result.json``:和 PR 8.3b 之前 finalize 寫的欄位相同(kind video_inpaint_paste_back)。"""
    work = _check_detail(manifest, "vace_work_area")
    paste = _check_detail(manifest, "paste_back")
    raw = next(o for o in manifest["outputs"] if o.get("output_id") == "raw")
    source = next(i for i in manifest["inputs"] if i.get("role") == "source_video")
    report = {
        "schema_version": 1, "kind": "video_inpaint_paste_back", "status": "candidate",
        "raw_output": {"path": raw["path"], "sha256": raw["sha256"],
                       "frames": paste["raw_frames"], "used_frames": paste["used_frames"]},
        "source": {"path": source["path"], "sha256": source["sha256"],
                   "frames": work["frames"], "size": [work["source_width"], work["source_height"]]},
        "masks": os.path.abspath(args.masks), "mask_object": args.mask_object,
        "mode": args.mode, "grow": args.grow, "feather": args.feather, "crop": work["crop"],
        "processing_size": [work["width"], work["height"]], "vace_length": work["length"],
        "seed": (manifest.get("slot_values") or {}).get("seed", args.seed),
        "outside_changed_pixels_total": paste["outside_changed_pixels_total"],
        "per_frame": paste["per_frame"], "fps": VIDEO_FPS, "audio": "dropped",
        "outputs": {"frames_dir": "frames/ (PNG, lossless master)",
                    "mp4": "composited.mp4 (H.264 crf 18, re-encoded, not lossless)"},
        "acceptance": "pending human review; outside-mask preservation does not judge the edit",
        "template_run_result": str(Path(folder) / "run.result.json"),
    }
    target = Path(folder) / "composited" / "result.json"
    with open(target, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    return report
