"""template 的 ``pre``／``post`` 步驟清單。

template 只能挑選這裡列出的步驟並設定參數,不能放任意程式。2.1 只做名稱與參數的驗證;
實際執行(讀媒體、上傳、檢查輸出)在 2.3 實作。

參數值可以是字面值,或 ``"{slot}"``、``"{option}"``、``"{pre.<slot>.<frames|width|height|fps>}"``
這種只取值、不運算的引用。
"""
import re

# 名稱 -> (所在階段, 允許的參數, 指向 slot 的參數, 指向 slot 清單的參數, 指向 outputs 的參數)
STEPS = {
    "check_image": ("pre", {"slot"}, {"slot"}, set(), set()),
    "check_video": ("pre", {"slot", "fps", "cfr", "frames_min", "frames_max"}, {"slot"}, set(), set()),
    "check_mask_matches_video": ("pre", {"mask", "video", "channel"}, {"mask", "video"}, set(), set()),
    "upload": ("pre", {"slots"}, set(), {"slots"}, set()),
    "check_video_output": ("post", {"output", "width", "height", "frames", "fps", "audio"}, set(), set(), {"output"}),
    "check_png_sequence": ("post", {"output", "count", "width", "height", "grayscale"}, set(), set(), {"output"}),
    "extract_keyframes": ("post", {"output", "which"}, set(), set(), {"output"}),
    "mask_preview": ("post", {"output", "video", "optional"}, {"video"}, set(), {"output"}),
}
PRE_FIELDS = ("frames", "width", "height", "fps")
REF_RE = re.compile(r"^\{([a-z0-9_]+(?:\.[a-z0-9_]+)*)\}$")


def _check_ref(value, where, slots, options, problems):
    if not isinstance(value, str):
        return
    match = REF_RE.match(value)
    if not match:
        if "{" in value or "}" in value:
            problems.append(f"{where}: 引用格式錯誤 {value!r}(只支援 {{slot}} 或 {{pre.<slot>.<欄位>}})")
        return
    parts = match.group(1).split(".")
    if len(parts) == 1:
        if parts[0] not in slots and parts[0] not in options:
            problems.append(f"{where}: 引用了不存在的 slot／option {parts[0]!r}")
    elif len(parts) == 3 and parts[0] == "pre":
        if parts[1] not in slots:
            problems.append(f"{where}: 引用了不存在的 slot {parts[1]!r}")
        if parts[2] not in PRE_FIELDS:
            problems.append(f"{where}: pre 結果只能取 {', '.join(PRE_FIELDS)},不是 {parts[2]!r}")
    else:
        problems.append(f"{where}: 不支援的引用 {value!r}")


def validate_steps(steps, phase, slots, options, output_ids):
    """回傳問題清單。``slots`` 是 {名稱: slot 定義}。"""
    problems = []
    if not isinstance(steps, list):
        return [f"{phase} 必須是陣列"]
    for index, step in enumerate(steps):
        where = f"{phase}[{index}]"
        if not isinstance(step, dict) or "step" not in step:
            problems.append(f"{where}: 每一項都要有 step")
            continue
        name = step["step"]
        spec = STEPS.get(name)
        if spec is None:
            problems.append(f"{where}: 不在步驟清單內的 {name!r}(可用: {', '.join(sorted(STEPS))})")
            continue
        want_phase, allowed, slot_params, slot_list_params, output_params = spec
        if want_phase != phase:
            problems.append(f"{where}: {name} 只能放在 {want_phase}")
        for key, value in step.items():
            if key == "step":
                continue
            if key not in allowed:
                problems.append(f"{where}: {name} 不接受參數 {key!r}")
                continue
            if key in slot_params and value not in slots:
                problems.append(f"{where}: {key} 指向不存在的 slot {value!r}")
            elif key in slot_list_params:
                if not isinstance(value, list) or not value:
                    problems.append(f"{where}: {key} 必須是非空的 slot 名稱陣列")
                    continue
                for item in value:
                    if item not in slots:
                        problems.append(f"{where}: {key} 指向不存在的 slot {item!r}")
            elif key in output_params and value not in output_ids:
                problems.append(f"{where}: {key} 指向不存在的 output {value!r}")
            elif isinstance(value, list):
                for item in value:
                    _check_ref(item, f"{where}.{key}", slots, options, problems)
            else:
                _check_ref(value, f"{where}.{key}", slots, options, problems)
    return problems


def uploaded_slots(steps):
    """pre 裡所有 upload 步驟列出的 slot 名稱。"""
    found = []
    for step in steps if isinstance(steps, list) else []:
        if isinstance(step, dict) and step.get("step") == "upload" and isinstance(step.get("slots"), list):
            found.extend(step["slots"])
    return found
