"""`python gameart.py pose-edit ...`:對一張角色圖改姿勢（FLUX.2 單圖編修）：動作選單、自訂動作、零件組裝、連續編修。

這是本機包裝工具，不是新的 graph：每個 seed 各用固定 template `image/flux2/edit` 跑一次（走 runner，
有 preflight、上傳、下載、run.result.json），再把候選圖拼成對照圖，讓使用者挑。
提示句型是 2026-11-02 實測過的寫法，工具自動套固定前綴與保留尾句，使用者只描述動作。
不自動 accept；`review` 由使用者決定。

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
SEED_POOL = (7, 21, 99, 123, 256, 314)   # 預設前 3 個；--count N 取前 N 個
DEFAULT_COUNT = 3
MAX_SEEDS = 6
MAX_STEPS = 4
PREFIX = "Change only the pose: "
SUFFIX = " Keep the face, hairstyle, accessories, clothes, art style and the plain background unchanged."
RESULT_FILE = "pose_edit.result.json"
SHEET_FILE = "contact_sheet.png"
USER_ACTIONS_FILE = "pose_edit_actions.local.json"   # 使用者自訂選單，放 repo 根目錄，不進版控

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

# --part 零件：欄位 -> 句子模板。值可寫英文，或用下面的中文別名（常見說法會換成實測過的英文）。
PARTS = {
    "left_hand": "the character's left hand {v}",
    "right_hand": "the character's right hand {v}",
    "palm": "the palms {v}",
    "head": "the head {v}",
    "gaze": "the character looks {v}",
    "feet": "the feet {v}",
    "legs": "the legs {v}",
    "body": "the body {v}",
}
PART_ALIASES = {
    "左手": "left_hand", "右手": "right_hand", "手掌": "palm", "掌心": "palm", "頭": "head", "視線": "gaze",
    "腳步": "feet", "腳": "feet", "腿": "legs", "身體": "body",
}
VALUE_ALIASES = {
    "舉高": "raised straight up with an open palm", "放下": "hanging relaxed at the side",
    "叉腰": "placed on the hip", "指向前方": "pointing forward with the index finger, arm straight",
    "揮手": "waving", "握拳": "closed into a fist", "朝鏡頭": "facing the camera", "朝下": "facing down",
    "朝前": "facing forward", "朝上": "facing up", "朝左": "turned to the left", "朝右": "turned to the right",
    "看鏡頭": "straight at the camera", "往下看": "down at the ground", "往左看": "to the left",
    "往右看": "to the right", "往上看": "up at the sky", "向前跨步": "stepping forward, mid-stride",
    "並腳": "together, standing still", "分開站": "apart in a wide stance",
}

COMMON_CHECKS = [
    "手：數量與五指是否正常（這個流程沒有逐指檢查）",
    "持物：數量是否重複或消失",
    "髮型、配件、服裝是否被重畫（厚塗風格最容易漂移）",
    "畫風與背景色是否漂移",
]
FREEFORM_CHECKS = ["動作是否真的符合描述（一次只改一個大動作效果最好）", "沒寫到的部位有沒有被順便改掉"]
CHAIN_CHECKS = ["連續編修每多一步偏移會累積，建議不超過 2～3 步；每一步的對照圖都要看"]
NOTICE = ("技術通過不等於美術接受（R1）。這是候選圖，沒有 accept／reject；"
          "請逐張放大檢查後由使用者自行決定。")


class PoseEditError(Exception):
    pass


# ---------- 使用者自訂選單 ----------

def user_actions_path(path=None):
    return Path(path) if path else HERE.parent / USER_ACTIONS_FILE


def load_user_actions(path=None):
    """讀使用者自訂選單；沒有檔案回空。格式 {"actions": {id: {"label", "sentence", "checks"?}}}。"""
    file = user_actions_path(path)
    if not file.is_file():
        return {}
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
        raw = data["actions"]
        assert isinstance(raw, dict)
    except (ValueError, KeyError, AssertionError):
        raise PoseEditError(f"{file} 格式不對：要 {{\"actions\": {{\"id\": {{\"label\": ..., \"sentence\": ...}}}}}}")
    actions = {}
    for key, item in raw.items():
        if not isinstance(item, dict) or not str(item.get("sentence", "")).strip():
            raise PoseEditError(f"{file} 的動作 {key!r} 缺 sentence")
        if key in ACTIONS:
            raise PoseEditError(f"{file} 的動作 id {key!r} 與內建動作重複，請換名字")
        actions[key] = (str(item.get("label") or key), normalize_sentence(item["sentence"]),
                        [str(c) for c in item.get("checks", [])] or list(FREEFORM_CHECKS))
    return actions


def all_actions(path=None):
    merged = dict(ACTIONS)
    merged.update(load_user_actions(path))
    return merged


def save_user_action(action_id, label, sentence, path=None):
    if not action_id or not all(ch.isalnum() or ch in "_-" for ch in action_id):
        raise PoseEditError("--id 只能用英數字、底線與減號")
    if action_id in ACTIONS:
        raise PoseEditError(f"id {action_id!r} 與內建動作重複")
    file = user_actions_path(path)
    data = {"actions": {}}
    if file.is_file():
        try:
            data = json.loads(file.read_text(encoding="utf-8"))
            data.setdefault("actions", {})
        except ValueError:
            raise PoseEditError(f"{file} 不是合法 JSON，請先修好或移走")
    data["actions"][action_id] = {"label": label or action_id, "sentence": sentence, "checks": list(FREEFORM_CHECKS)}
    file.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return file


# ---------- 提示組裝 ----------

def normalize_sentence(text):
    text = " ".join(str(text).split())
    if not text:
        raise PoseEditError("動作描述不可為空")
    return text if text[-1] in ".!" else text + "."


def part_phrase(part, value):
    key = PART_ALIASES.get(part, part)
    if key not in PARTS:
        raise PoseEditError(f"不認得的零件 {part!r}；可用：{', '.join(PARTS)}（或中文：{'、'.join(PART_ALIASES)}）")
    value = " ".join(str(value).split())
    if not value:
        raise PoseEditError(f"零件 {part!r} 的內容不可為空")
    return PARTS[key].format(v=VALUE_ALIASES.get(value, value))


def parts_sentence(parts):
    """parts: [(零件, 值), ...] -> 一句英文，例如 'the character's right hand raised ...; the head turned to the left.'"""
    if not parts:
        raise PoseEditError("沒有任何 --part")
    return normalize_sentence("; ".join(part_phrase(k, v) for k, v in parts))


def build_prompt_from_sentence(sentence, keep_extra=None, avoid=None, note=None):
    extra = f" {note.strip()}" if note and note.strip() else ""
    tail = ""
    if keep_extra and keep_extra.strip():
        tail += f" Also keep {keep_extra.strip().rstrip('.')} exactly as it is."
    if avoid and avoid.strip():
        tail += f" Do not add {avoid.strip().rstrip('.')}."
    return f"{PREFIX}{sentence}{extra}{SUFFIX}{tail}"


def build_prompt(action, note=None, keep_extra=None, avoid=None, actions=None):
    """動作選單（或使用者選單）-> 英文提示。``note`` 是額外補充（接在固定尾句之前）。"""
    table = actions if actions is not None else all_actions()
    if action not in table:
        raise PoseEditError(f"沒有這個動作 {action!r}；可用：{', '.join(table)}")
    return build_prompt_from_sentence(table[action][1], keep_extra=keep_extra, avoid=avoid, note=note)


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


def resolve_seeds(args):
    if args.seeds is not None and args.count is not None:
        raise PoseEditError("--seeds 與 --count 只能擇一")
    if args.count is not None:
        if not 1 <= args.count <= MAX_SEEDS:
            raise PoseEditError(f"--count 要在 1～{MAX_SEEDS}")
        return list(SEED_POOL[:args.count])
    return parse_seeds(args.seeds) if args.seeds is not None else list(SEED_POOL[:DEFAULT_COUNT])


def resolve_steps(args, actions):
    """把命令列依出現順序的 --action／--custom／--part／--then 轉成步驟清單。"""
    steps, open_parts = [], None

    def close_parts():
        nonlocal open_parts
        if open_parts:
            sentence = parts_sentence(open_parts)
            steps.append({"id": f"parts{sum(1 for s in steps if s['kind'] == 'parts') + 1}", "kind": "parts",
                          "label": "零件組裝", "sentence": sentence, "checks": list(FREEFORM_CHECKS)})
        open_parts = None

    for kind, value in args.step_tokens:
        if kind == "action":
            close_parts()
            for action in [part.strip() for part in value.split(",") if part.strip()]:
                if action not in actions:
                    raise PoseEditError(f"沒有這個動作 {action!r}；可用：{', '.join(actions)}")
                label, sentence, checks = actions[action]
                steps.append({"id": action, "kind": "menu" if action in ACTIONS else "user", "label": label,
                              "sentence": sentence, "checks": list(checks)})
        elif kind == "custom":
            close_parts()
            steps.append({"id": f"custom{sum(1 for s in steps if s['kind'] == 'custom') + 1}", "kind": "custom",
                          "label": "自訂動作", "sentence": normalize_sentence(value), "checks": list(FREEFORM_CHECKS)})
        elif kind == "part":
            if "=" not in value:
                raise PoseEditError(f"--part 要寫成 零件=內容（例如 右手=舉高），收到 {value!r}")
            name, content = value.split("=", 1)
            open_parts = (open_parts or []) + [(name.strip(), content.strip())]
        elif kind == "then":
            close_parts()
    close_parts()
    if not steps:
        raise PoseEditError("run 需要至少一個 --action、--custom 或 --part")
    if len(steps) > MAX_STEPS:
        raise PoseEditError(f"連續編修最多 {MAX_STEPS} 步，收到 {len(steps)} 步")
    for step in steps:
        step["prompt"] = build_prompt_from_sentence(step["sentence"], keep_extra=args.keep_extra,
                                                    avoid=args.avoid, note=args.note)
    return steps


def parse_picks(text, steps_count):
    if text is None:
        return []
    picks = parse_seeds(text) if text.strip() else []
    if len(picks) > max(steps_count - 1, 0):
        raise PoseEditError(f"--pick 最多 {max(steps_count - 1, 0)} 個（最後一步不需要挑）")
    return picks


# ---------- 執行 ----------

def runner_argv(prompt, image, seed, seed_dir, mode, args):
    """組出單一 seed 傳給 ``gameart.py run image/flux2/edit`` 的 argv（runner 內部呼叫，不另寫 HTTP）。"""
    argv = [TEMPLATE_ID, "--set", f"prompt={prompt}", "--set", f"image={image}",
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


def default_output_dir(label):
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return HERE.parent / "output" / "pose-edit" / f"{stamp}-{label}-{uuid.uuid4().hex[:6]}"


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
        with Image.open(path) as opened:
            image = opened.convert("RGB")
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


def run_step(step, index, total, source, seeds, out_dir, mode, args, runner_main, err):
    """一個步驟：每個 seed 各跑一次 template，回傳 (步驟紀錄, 對照圖路徑)。"""
    step_dir = Path(out_dir) if total == 1 else Path(out_dir) / f"step_{index}_{step['id']}"
    runs = []
    for seed in seeds:
        seed_dir = step_dir / f"seed_{seed}"
        code = runner_main(runner_argv(step["prompt"], source, seed, seed_dir, mode, args),
                           out=io.StringIO(), err=err)
        entry = {"seed": seed, "dir": str(seed_dir), "exit_code": code, "status": "failed", "output": None}
        if mode != "run":
            entry["status"] = "completed" if code == 0 else "failed"
        else:
            found = first_output_image(seed_dir)
            if code == 0 and found:
                entry.update(status="completed", output=str(found), output_sha256=sha256_file(found))
        runs.append(entry)
        print(f"[pose-edit] 步驟 {index}/{total} seed {seed}: {entry['status']}", file=err)
    sheet = None
    if mode == "run":
        candidates = [(run["seed"], run["output"]) for run in runs if run["output"]]
        if candidates:
            sheet = make_contact_sheet(source, candidates, step_dir / SHEET_FILE,
                                       f"步驟 {index}/{total} {step['label']}  候選，未驗收")
    record = {"index": index, "id": step["id"], "kind": step["kind"], "label": step["label"],
              "sentence": step["sentence"], "prompt": step["prompt"], "source_image": str(source),
              "runs": runs, "contact_sheet": str(sheet) if sheet else None, "picked_seed": None,
              "pick_reason": None}
    return record, sheet


def choose_pick(record, wanted, is_last):
    """決定下一步的來源：--pick 指定的 seed；沒指定就用第一張成功的（只是接續用，不是接受）。"""
    ok = {run["seed"]: run for run in record["runs"] if run["status"] == "completed" and run["output"]}
    if not ok:
        return None
    if is_last:
        return None
    if wanted is not None:
        if wanted not in ok:
            raise PoseEditError(f"步驟 {record['index']} 的 --pick {wanted} 沒有成功的候選（成功的 seed：{sorted(ok)}）")
        record["picked_seed"], record["pick_reason"] = wanted, "user"
        return Path(ok[wanted]["output"])
    first = next(iter(ok))
    record["picked_seed"], record["pick_reason"] = first, "auto-first（只是接續用，不是接受；要自己挑請加 --pick）"
    return Path(ok[first]["output"])


def write_result(out_dir, image, seeds, steps, records, sheet, mode, chain_notes):
    any_ok = any(any(r["status"] == "completed" for r in rec["runs"]) for rec in records)
    full = len(records) == len(steps) and all(all(r["status"] == "completed" for r in rec["runs"]) for rec in records)
    checks = []
    for step in steps:
        checks += [c for c in step["checks"] if c not in checks]
    checks += COMMON_CHECKS + (CHAIN_CHECKS if len(steps) > 1 else [])
    result = {
        "schema_version": 2,
        "kind": "pose_edit_result",
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "mode": mode,
        "template": TEMPLATE_ID,
        "action": steps[0]["id"],
        "action_label": steps[0]["label"],
        "prompt": steps[0]["prompt"],
        "source_image": {"path": str(image), "sha256": sha256_file(image)},
        "seeds": seeds,
        "runs": records[0]["runs"] if records else [],
        "steps": records,
        "contact_sheet": str(sheet) if sheet else None,
        "status": "completed" if full else ("partial" if any_ok else "failed"),
        "review_checks": checks,
        "chain_notes": chain_notes,
        "notice": NOTICE,
        "content_review": "pending",
        "acceptance": "none",
    }
    path = Path(out_dir) / RESULT_FILE
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result, path


# ---------- 指令 ----------

def cmd_list(out, actions_path=None):
    print("動作選單（--action 後面接 id；可用逗號串接成連續編修）：", file=out)
    for action, (label, _, _) in ACTIONS.items():
        print(f"  {action:<16} {label}", file=out)
    user = load_user_actions(actions_path)
    if user:
        print(f"自訂選單（{user_actions_path(actions_path).name}）：", file=out)
        for action, (label, sentence, _) in user.items():
            print(f"  {action:<16} {label}（自訂）  {sentence}", file=out)
    print("也可以不用選單：--custom \"<英文描述動作>\"，或用 --part 零件=內容 組裝"
          f"（零件：{', '.join(PARTS)}）。", file=out)
    return 0


def cmd_save(args, out):
    actions = all_actions(args.actions_file)
    tokens = list(args.step_tokens)
    steps = resolve_steps(argparse.Namespace(step_tokens=tokens, keep_extra=None, avoid=None, note=None), actions)
    if len(steps) != 1 or steps[0]["kind"] not in ("custom", "parts"):
        raise PoseEditError("save 需要剛好一個 --custom 或一組 --part（不要用 --action 或串接）")
    file = save_user_action(args.id, args.label, steps[0]["sentence"], args.actions_file)
    print(f"[pose-edit] 已存成自訂動作 {args.id}，寫在 {file}（不進版控）。`pose-edit list` 會列出。", file=out)
    return 0


def cmd_run(args, out, err, runner_main=None):
    if runner_main is None:
        from comfyui_pipeline.runner.cli import main as runner_main
    image = Path(args.image)
    if not image.is_file():
        raise PoseEditError(f"找不到來源圖 {image}")
    actions = all_actions(args.actions_file)
    steps = resolve_steps(args, actions)
    seeds = resolve_seeds(args)
    picks = parse_picks(args.pick, len(steps))
    mode = "dry-run" if args.dry_run else "preflight" if args.preflight else "run"
    out_dir = Path(args.output_dir) if args.output_dir else default_output_dir(steps[0]["id"])
    if out_dir.exists() and any(out_dir.iterdir()):
        raise PoseEditError(f"輸出資料夾必須不存在或是空的：{out_dir}")
    print(f"[pose-edit] 共 {len(steps)} 步，每步 seed {seeds}", file=err)
    for index, step in enumerate(steps, 1):
        print(f"[pose-edit] 步驟 {index} 提示：{step['prompt']}", file=out)
    out_dir.mkdir(parents=True, exist_ok=True)
    records, source, chain_notes, sheet = [], image, [], None
    for index, step in enumerate(steps, 1):
        record, step_sheet = run_step(step, index, len(steps), source, seeds, out_dir, mode, args, runner_main, err)
        records.append(record)
        sheet = sheet or step_sheet
        if index == len(steps):
            break
        if mode != "run":   # 沒有真的輸出，後面的步驟用同一張來源圖驗證 graph
            continue
        source = choose_pick(record, picks[index - 1] if index - 1 < len(picks) else None, False)
        if source is None:
            chain_notes.append(f"步驟 {index} 沒有任何成功的候選，後面的步驟未執行。")
            break
        chain_notes.append(f"步驟 {index} 採用 seed {record['picked_seed']} 當步驟 {index + 1} 的來源："
                           f"{record['pick_reason']}")
    result, path = write_result(out_dir, image, seeds, steps, records, sheet, mode, chain_notes)
    print(f"[pose-edit] 狀態 {result['status']}；說明與檢查提醒寫在 {path}", file=out)
    for record in records:
        if record["contact_sheet"]:
            print(f"[pose-edit] 步驟 {record['index']} 對照圖 {record['contact_sheet']}", file=out)
    for note in chain_notes:
        print(f"[pose-edit] {note}", file=out)
    print(f"[pose-edit] {NOTICE}", file=out)
    return 0 if result["status"] == "completed" else 1


class _StepToken(argparse.Action):
    """依命令列出現順序收集 --action／--custom／--part／--then。"""

    def __call__(self, parser, namespace, values, option_string=None):
        tokens = list(getattr(namespace, "step_tokens", None) or [])
        tokens.append((self.dest.replace("step_", ""), values if values is not None else True))
        namespace.step_tokens = tokens


def build_parser():
    p = argparse.ArgumentParser(
        prog="gameart.py pose-edit",
        description="給一張角色圖，用固定 template image/flux2/edit 改姿勢：選單動作、自訂描述、零件組裝或連續編修；"
                    "一次出多個 seed 候選並拼對照圖。不自動 accept。先 `pose-edit list` 看選單。",
        epilog="結束碼：0 全部 seed 完成；1 有 seed 失敗或 preflight 擋下；2 參數錯誤。"
               "先加 --dry-run 看組好的完整提示句，可以微調再執行。")
    p.add_argument("command", choices=["list", "run", "save"], help="list＝選單；run＝執行；save＝把自訂動作存成自己的選單")
    p.add_argument("--action", dest="step_action", action=_StepToken, metavar="ID[,ID...]",
                   help="選單動作 id，可逗號串接或重複＝連續編修（上一步挑出的圖當下一步來源）")
    p.add_argument("--custom", dest="step_custom", action=_StepToken, metavar="TEXT",
                   help="自由描述肢體（英文一句，例如 \"the character waves with the left hand and looks to the right\"）；"
                        "工具自動加固定前綴與保留尾句")
    p.add_argument("--part", dest="step_part", action=_StepToken, metavar="零件=內容",
                   help=f"零件組裝，可重複：{', '.join(PARTS)}（也可用中文 左手、右手、手掌、頭、視線、腳步）；"
                        "內容寫英文，或常見中文（舉高、放下、叉腰、朝鏡頭、朝左、往下看、向前跨步…）")
    p.add_argument("--then", dest="step_then", action=_StepToken, nargs=0,
                   help="結束目前這組 --part，後面的 --part／--action／--custom 變成下一步")
    p.add_argument("--image", help="來源角色圖（全身、單人、背景單純效果最好）")
    p.add_argument("--seeds", help=f"逗號分隔的 seed，最多 {MAX_SEEDS} 個；預設 {','.join(str(s) for s in SEED_POOL[:DEFAULT_COUNT])}")
    p.add_argument("--count", type=int, help=f"改用 seed 池前 N 個（1～{MAX_SEEDS}），和 --seeds 擇一")
    p.add_argument("--pick", help="連續編修時每一步（最後一步除外）挑哪個 seed 當下一步來源，逗號分隔；"
                                  "沒給就自動用第一張成功的（只是接續用，不是接受）")
    p.add_argument("--keep-extra", help="額外要保留的東西（英文片語，例如 \"the wooden staff in the hand\"）")
    p.add_argument("--avoid", help="不要出現的東西（英文片語，例如 \"a second staff\"）")
    p.add_argument("--note", help="補充說明（英文），接在動作句型後面、固定尾句之前；改寫效果未實測")
    p.add_argument("--actions-file", help=f"使用者自訂選單 JSON，預設 <repo>/{USER_ACTIONS_FILE}（不進版控）")
    p.add_argument("--id", help="save 用：自訂動作 id")
    p.add_argument("--label", help="save 用：自訂動作的中文名")
    p.add_argument("--output-dir", help="預設 <repo>/output/pose-edit/<時間>-<動作>-<碼>；必須不存在或是空的")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="只驗證 graph、印出組好的完整提示句，不連線")
    mode.add_argument("--preflight", action="store_true", help="檢查平台、ComfyUI 與模型檔，不 queue")
    p.add_argument("--config", help="local_config.json（同 gameart.py run）")
    p.add_argument("--comfy-url", help="覆寫 ComfyUI URL")
    p.add_argument("--timeout", type=float, help="每個 seed 等待 ComfyUI 的秒數")
    p.add_argument("--allow-unverified-platform", action="store_true",
                   help="template 平台尚未 technical_pass 時仍放行（例如 macos-mps）；結果只能當技術試驗")
    p.set_defaults(step_tokens=[])
    return p


def main(argv=None, *, out=None, err=None, runner_main=None):
    out, err = out or sys.stdout, err or sys.stderr
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    try:
        if args.command == "list":
            return cmd_list(out, args.actions_file)
        if args.command == "save":
            if not args.id:
                raise PoseEditError("save 需要 --id（以及 --custom 或 --part）")
            return cmd_save(args, out)
        if not args.image:
            raise PoseEditError("run 需要 --image")
        return cmd_run(args, out, err, runner_main=runner_main)
    except PoseEditError as exc:
        print(f"pose-edit: {exc}", file=err)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
