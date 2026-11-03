"""`python gameart.py pose-edit ...`:用動作選單，對一張角色圖改姿勢（FLUX.2 單圖編修）。

這是本機包裝工具，不是新的 graph：每個 seed 各用固定 template `image/flux2/edit` 跑一次（走 runner，
有 preflight、上傳、下載、run.result.json），再把候選圖拼成對照圖，讓使用者挑。
提示句型是 2026-11-02 實測過的寫法，使用者只選動作與來源圖。不自動 accept；`review` 由使用者決定。

只能從 repo 的 tools_src/ 執行（需要 templates/）。
"""
import argparse
import hashlib
import io
import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

TEMPLATE_ID = "image/flux2/edit"
DEFAULT_SEEDS = (7, 21, 99)
MAX_SEEDS = 6
PREFIX = "Change only the pose: "
SUFFIX = (" Keep the face, hairstyle, accessories, clothes, art style and the plain background unchanged.")
RESULT_FILE = "pose_edit.result.json"
SHEET_FILE = "contact_sheet.png"

# 動作 id -> (中文名, 提示句型, 這個動作的逐張檢查提醒)。句型是實測過的寫法（見 external-asset-libraries 頁），
# 不要隨手改寫；改寫要先實測並更新該頁。
ACTIONS = {
    "raise_hand": (
        "舉手",
        "the character raises the right arm straight up with an open palm.",
        ["另一隻手有沒有也跟著舉起來", "舉起的手五指與掌心朝向"]),
    "walk": (
        "走路",
        "the character walks forward, mid-stride, one leg stepping forward, arms swinging.",
        ["雙腳與手臂數量是否正常", "鞋與褲管是否被重畫"]),
    "cross_arms": (
        "抱胸",
        "the character crosses the arms over the chest.",
        ["手臂交疊是否自然、手指數量", "胸前配件、圍巾是否被蓋掉或改形"]),
    "look_back_wave": (
        "回頭揮手",
        "the character turns to a three-quarter side view looking back over the shoulder, "
        "one hand waving with the palm facing the camera.",
        ["轉側面或背面時臉被擋，身分是否保持無法判斷，要人工看髮型與臉型", "揮的手掌心是否朝鏡頭、五指是否正常"]),
    "hold_staff": (
        "雙手持杖（持物）",
        "the character holds a long wooden staff in both hands in front of the body.",
        ["持物數量：原本畫面裡的道具是否留著，造成兩根", "兩手是否都握在物件上"]),
    "point": (
        "單手指向",
        "the character points forward to the side with the right index finger, arm straight.",
        ["食指是否只有一根伸出", "另一隻手是否也跟著動"]),
    "look_down": (
        "低頭",
        "the character lowers the head and looks down at the ground, hands at the sides.",
        ["臉、髮型是否保持", "眼睛、表情是否被改"]),
    "palm_to_camera": (
        "掌心朝鏡頭",
        "the character bends both elbows and pushes both hands toward the camera at chest height, palms flat "
        "facing the viewer, like a stop gesture. The arms are in front of the body, not spread to the sides.",
        ["常見失敗：變成雙手合十、心形手勢或雙臂橫伸", "掌心是否真的朝鏡頭、五指是否正常"]),
}

COMMON_CHECKS = [
    "手：數量與五指是否正常（這個流程沒有逐指檢查）",
    "持物：數量是否重複或消失",
    "髮型、配件、服裝是否被重畫（厚塗風格最容易漂移）",
    "畫風與背景色是否漂移",
]
NOTICE = ("技術通過不等於美術接受（R1）。這是候選圖，沒有 accept／reject；"
          "請逐張放大檢查後由使用者自行決定。")


class PoseEditError(Exception):
    pass


def build_prompt(action, note=None):
    """動作選單 -> 英文提示。``note`` 是使用者額外補充（會接在固定尾句之前）。"""
    if action not in ACTIONS:
        raise PoseEditError(f"沒有這個動作 {action!r}；可用：{', '.join(ACTIONS)}")
    _, sentence, _ = ACTIONS[action]
    extra = f" {note.strip()}" if note and note.strip() else ""
    return f"{PREFIX}{sentence}{extra}{SUFFIX}"


def parse_seeds(text):
    try:
        seeds = [int(part) for part in str(text).split(",") if part.strip() != ""]
    except ValueError:
        raise PoseEditError(f"--seeds 要用逗號分隔的整數，收到 {text!r}")
    if not seeds:
        raise PoseEditError("--seeds 至少要一個")
    if len(seeds) > MAX_SEEDS:
        raise PoseEditError(f"--seeds 最多 {MAX_SEEDS} 個，收到 {len(seeds)} 個")
    if len(set(seeds)) != len(seeds):
        raise PoseEditError("--seeds 不可重複")
    if any(seed < 0 for seed in seeds):
        raise PoseEditError("--seeds 必須是非負整數")
    return seeds


def runner_argv(action, image, seed, seed_dir, mode, args):
    """組出單一 seed 傳給 ``gameart.py run image/flux2/edit`` 的 argv（runner 內部呼叫，不另寫 HTTP）。"""
    argv = [TEMPLATE_ID, "--set", f"prompt={build_prompt(action, args.note)}", "--set", f"image={image}",
            "--set", f"seed={seed}", "--output-dir", str(seed_dir)]
    if mode == "dry-run":
        argv.append("--dry-run")
    elif mode == "preflight":
        argv.append("--preflight")
    for flag, value in (("--config", args.config), ("--comfy-url", args.comfy_url),
                        ("--timeout", args.timeout)):
        if value is not None:
            argv += [flag, str(value)]
    if args.allow_unverified_platform:
        argv.append("--allow-unverified-platform")
    return argv


def default_output_dir(action):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return HERE.parent / "output" / "pose-edit" / f"{stamp}-{action}-{uuid.uuid4().hex[:6]}"


def first_output_image(seed_dir):
    """從 run.result.json 找候選圖路徑；沒有就回 None。"""
    path = Path(seed_dir) / "run.result.json"
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None
    if data.get("status") != "completed":
        return None
    for item in data.get("outputs") or []:
        if item.get("kind") == "image" and item.get("path") and Path(item["path"]).is_file():
            return Path(item["path"])
    return None


def _font(size):
    from PIL import ImageFont
    for name in ("C:/Windows/Fonts/msjh.ttc", "/System/Library/Fonts/PingFang.ttc",
                 "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def make_contact_sheet(source, candidates, out_path, title, cell=(360, 480)):
    """左邊原圖、右邊各 seed 候選，標 seed。純 Pillow，不連 ComfyUI。"""
    from PIL import Image, ImageDraw
    cells = [("原圖", source)] + [(f"seed {seed}", path) for seed, path in candidates]
    width, height = cell
    sheet = Image.new("RGB", (len(cells) * width, height + 70), "white")
    draw = ImageDraw.Draw(sheet)
    draw.text((8, 6), title, font=_font(22), fill="black")
    for index, (label, path) in enumerate(cells):
        image = Image.open(path).convert("RGB")
        image.thumbnail((width - 8, height - 4))
        sheet.paste(image, (index * width + 4, 66))
        draw.text((index * width + 8, 38), label, font=_font(18), fill=(30, 30, 160))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_path)
    return Path(out_path)


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_result(out_dir, action, image, seeds, prompt, runs, sheet, mode):
    label, _, checks = ACTIONS[action]
    completed = [run for run in runs if run["status"] == "completed"]
    result = {
        "schema_version": 1,
        "kind": "pose_edit_result",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "template": TEMPLATE_ID,
        "action": action,
        "action_label": label,
        "prompt": prompt,
        "source_image": {"path": str(image), "sha256": sha256_file(image)},
        "seeds": seeds,
        "runs": runs,
        "contact_sheet": str(sheet) if sheet else None,
        "status": "completed" if len(completed) == len(seeds) else ("partial" if completed else "failed"),
        "review_checks": list(checks) + COMMON_CHECKS,
        "notice": NOTICE,
        "content_review": "pending",
        "acceptance": "none",
    }
    path = Path(out_dir) / RESULT_FILE
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result, path


def cmd_list(out):
    print("動作選單（--action 後面接 id）：", file=out)
    for action, (label, _, _) in ACTIONS.items():
        print(f"  {action:<16} {label}", file=out)
    return 0


def cmd_run(args, out, err, runner_main=None):
    if runner_main is None:
        from comfyui_pipeline.runner.cli import main as runner_main
    image = Path(args.image)
    if not image.is_file():
        raise PoseEditError(f"找不到來源圖 {image}")
    seeds = parse_seeds(args.seeds)
    prompt = build_prompt(args.action, args.note)
    mode = "dry-run" if args.dry_run else "preflight" if args.preflight else "run"
    out_dir = Path(args.output_dir) if args.output_dir else default_output_dir(args.action)
    if out_dir.exists() and any(out_dir.iterdir()):
        raise PoseEditError(f"輸出資料夾必須不存在或是空的：{out_dir}")
    out_dir.mkdir(parents=True, exist_ok=True)
    runs = []
    for seed in seeds:
        seed_dir = out_dir / f"seed_{seed}"
        code = runner_main(runner_argv(args.action, image, seed, seed_dir, mode, args),
                           out=io.StringIO(), err=err)
        entry = {"seed": seed, "dir": str(seed_dir), "exit_code": code, "status": "failed", "output": None}
        if mode != "run":
            entry["status"] = "completed" if code == 0 else "failed"
        else:
            found = first_output_image(seed_dir)
            if code == 0 and found:
                entry.update(status="completed", output=str(found), output_sha256=sha256_file(found))
        runs.append(entry)
        print(f"[pose-edit] seed {seed}: {entry['status']}", file=err)
    sheet = None
    if mode == "run":
        candidates = [(run["seed"], run["output"]) for run in runs if run["output"]]
        if candidates:
            sheet = make_contact_sheet(image, candidates, out_dir / SHEET_FILE,
                                       f"{ACTIONS[args.action][0]}（{args.action}）  候選，未驗收")
    result, path = write_result(out_dir, args.action, image, seeds, prompt, runs, sheet, mode)
    print(f"[pose-edit] 狀態 {result['status']}；說明與檢查提醒寫在 {path}", file=out)
    if sheet:
        print(f"[pose-edit] 對照圖 {sheet}", file=out)
    print(f"[pose-edit] {NOTICE}", file=out)
    return 0 if result["status"] == "completed" else 1


def build_parser():
    p = argparse.ArgumentParser(
        prog="gameart.py pose-edit",
        description="選動作＋給一張角色圖，用固定 template image/flux2/edit 一次出多個 seed 候選並拼對照圖。"
                    "不自動 accept。先 `pose-edit list` 看動作選單。",
        epilog="結束碼：0 全部 seed 完成；1 有 seed 失敗或 preflight 擋下；2 參數錯誤")
    p.add_argument("command", choices=["list", "run"], help="list＝動作選單；run＝執行")
    p.add_argument("--action", choices=list(ACTIONS), help="動作 id（run 必填）")
    p.add_argument("--image", help="來源角色圖（全身、單人、背景單純效果最好）")
    p.add_argument("--seeds", default=",".join(str(s) for s in DEFAULT_SEEDS),
                   help=f"逗號分隔的 seed，最多 {MAX_SEEDS} 個；預設 {','.join(str(s) for s in DEFAULT_SEEDS)}")
    p.add_argument("--note", help="補充說明（英文），會接在動作句型後面、固定尾句之前；改寫效果未實測")
    p.add_argument("--output-dir", help="預設 <repo>/output/pose-edit/<時間>-<動作>-<碼>；必須不存在或是空的")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只驗證 graph，不連線")
    mode.add_argument("--preflight", action="store_true", help="檢查平台、ComfyUI 與模型檔，不 queue")
    p.add_argument("--config", help="local_config.json（同 gameart.py run）")
    p.add_argument("--comfy-url", help="覆寫 ComfyUI URL")
    p.add_argument("--timeout", type=float, help="每個 seed 等待 ComfyUI 的秒數")
    p.add_argument("--allow-unverified-platform", action="store_true",
                   help="template 平台尚未 technical_pass 時仍放行；結果只能當技術試驗")
    return p


def main(argv=None, *, out=None, err=None, runner_main=None):
    out, err = out or sys.stdout, err or sys.stderr
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "list":
            return cmd_list(out)
        if not args.action or not args.image:
            raise PoseEditError("run 需要 --action 與 --image")
        return cmd_run(args, out, err, runner_main=runner_main)
    except PoseEditError as exc:
        print(f"pose-edit: {exc}", file=err)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
