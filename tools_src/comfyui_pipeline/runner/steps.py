"""template 的 ``pre``／``post`` 步驟清單。

template 只能挑選這裡列出的步驟並設定參數,不能放任意程式。:func:`validate_steps` 驗證名稱與參數;
:func:`run_pre_checks`／:func:`run_post_checks` 實際讀媒體做檢查(``upload`` 由 run.py 執行)。
讀媒體的函式在 media.py,這裡只做比較與判斷;``media`` 參數可換成測試用的假物件。

參數值可以是字面值,或 ``"{slot}"``、``"{option}"``、``"{pre.<slot>.<frames|width|height|fps>}"``
這種只取值、不運算的引用。
"""
import os
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
    # PR 3.3:VACE 局部重繪的前後處理(實作在 vace_media.py,和 generate.py video_inpaint 共用)
    "vace_work_area": ("pre", {"video", "masks", "mask_object", "grow", "pad", "crop", "mode", "control", "mask"},
                       {"video", "masks", "control", "mask"}, set(), set()),
    "paste_back": ("post", {"output", "feather"}, set(), set(), {"output"}),
    "qa_outside_mask_unchanged": ("post", set(), set(), set(), set()),
    # 抽上一鏡尾幀、運鏡終點靜幀。只呼叫既有函式，參數是字面值或 {slot} 引用。
    "extract_last_frame": ("pre", {"video", "image"}, {"video", "image"}, set(), set()),
    "camera_end_still": ("pre", {"image", "camera", "width", "height", "still"}, {"image", "still"}, set(), set()),
}
PRE_FIELDS = ("frames", "width", "height", "fps")
# 會產生上傳檔的 pre 步驟:參數名 -> 這個參數指向的 slot 會拿到的檔案(slot 必須是 generated)
GENERATES = {"vace_work_area": ("control", "mask"), "extract_last_frame": ("image",), "camera_end_still": ("still",)}
# pre 步驟的結果可以用 {pre.<步驟>.<欄位>} 引用(例如 from_pre slot 的值)
STEP_RESULTS = {"vace_work_area": ("frames", "width", "height", "length")}
# 參數指向的 slot 必須是這些類型
SLOT_PARAM_TYPES = {("vace_work_area", "video"): ("video",), ("vace_work_area", "masks"): ("path",),
                    ("vace_work_area", "control"): ("video",), ("vace_work_area", "mask"): ("video",),
                    ("extract_last_frame", "video"): ("video",), ("extract_last_frame", "image"): ("image",),
                    ("camera_end_still", "image"): ("image",), ("camera_end_still", "still"): ("image",)}
# post 步驟需要的前置步驟:(階段, 步驟)
REQUIRES = {"paste_back": ("pre", "vace_work_area"), "qa_outside_mask_unchanged": ("post", "paste_back")}
REF_RE = re.compile(r"^\{([a-z0-9_]+(?:\.[a-z0-9_]+)*)\}$")


def is_step_result_ref(value):
    """``{pre.<步驟>.<欄位>}``,而且步驟與欄位在 STEP_RESULTS 裡。"""
    match = REF_RE.match(value) if isinstance(value, str) else None
    parts = match.group(1).split(".") if match else []
    return len(parts) == 3 and parts[0] == "pre" and parts[2] in STEP_RESULTS.get(parts[1], ())


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
    elif len(parts) == 3 and parts[0] == "pre" and parts[1] in STEP_RESULTS:
        if parts[2] not in STEP_RESULTS[parts[1]]:
            problems.append(f"{where}: {parts[1]} 的結果只能取 {', '.join(STEP_RESULTS[parts[1]])},不是 {parts[2]!r}")
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


def _steps_list(steps):
    return [s for s in steps if isinstance(s, dict) and isinstance(s.get("step"), str)] if isinstance(steps, list) else []


def _referenced_slots(steps):
    """步驟參數用到的 slot 名稱(slot 參數、slot 清單參數與 {slot} 引用)。"""
    found = set()
    for step in steps:
        spec = STEPS.get(step["step"])
        if not spec:
            continue
        for key, value in step.items():
            if key in spec[2] and isinstance(value, str):
                found.add(value)
            elif key in spec[3] and isinstance(value, list):
                found.update(v for v in value if isinstance(v, str))
            else:
                for item in value if isinstance(value, list) else [value]:
                    match = REF_RE.match(item) if isinstance(item, str) else None
                    if match and "." not in match.group(1):
                        found.add(match.group(1))
    return found


def validate_step_slots(pre, post, slots):
    """步驟與 slot 之間的交叉檢查(PR 3.3):generated slot 剛好由一個 pre 步驟產生、而且在上傳之前;
    不寫進 graph 的 slot 一定要有步驟使用;from_pre 引用的步驟要存在;post 步驟的前置步驟要存在。"""
    pre, post = _steps_list(pre), _steps_list(post)
    problems = []
    produced, upload_at = {}, {}
    for index, step in enumerate(pre):
        if step["step"] == "upload" and isinstance(step.get("slots"), list):
            for name in step["slots"]:
                upload_at.setdefault(name, index)
        for param in GENERATES.get(step["step"], ()):
            name = step.get(param)
            if name in slots:
                produced.setdefault(name, []).append(index)
    for index, step in enumerate(pre + post):
        for key, value in step.items():
            kinds = SLOT_PARAM_TYPES.get((step["step"], key))
            if kinds and value in slots and slots[value].get("type") not in kinds:
                problems.append(f"{step['step']}.{key}: slot {value} 必須是 {'／'.join(kinds)},不是 {slots[value].get('type')}")
    for name, indexes in produced.items():
        if not slots[name].get("generated"):
            problems.append(f"slot {name}: 由 pre 步驟產生,要寫 \"generated\": true")
        if len(indexes) > 1:
            problems.append(f"slot {name}: 被 {len(indexes)} 個 pre 步驟產生,只能一個")
        elif name in upload_at and upload_at[name] < indexes[0]:
            problems.append(f"slot {name}: upload 步驟排在產生它的 pre 步驟之前")
    for name, slot in slots.items():
        if isinstance(slot, dict) and slot.get("generated") and name not in produced:
            problems.append(f"slot {name}: generated,但沒有任何 pre 步驟產生它")
    used = _referenced_slots(pre + post)
    for name, slot in slots.items():
        if isinstance(slot, dict) and slot.get("targets") == [] and name not in used:
            problems.append(f"slot {name}: 沒有寫進 graph,也沒有任何 pre／post 步驟使用")
    pre_names = [s["step"] for s in pre]
    for name, slot in slots.items():
        ref = slot.get("from_pre") if isinstance(slot, dict) else None
        if isinstance(ref, str) and is_step_result_ref(ref) and ref[1:-1].split(".")[1] not in pre_names:
            problems.append(f"slot {name}: from_pre 引用的 {ref[1:-1].split('.')[1]} 不在 pre 步驟裡")
    for phase, steps in (("pre", pre), ("post", post)):
        for index, step in enumerate(steps):
            need = REQUIRES.get(step["step"])
            if not need:
                continue
            need_phase, need_step = need
            earlier = pre_names if need_phase == "pre" else [s["step"] for s in post[:index]]
            if need_step not in earlier:
                problems.append(f"{phase}[{index}]: {step['step']} 需要在它之前有 {need_phase} 步驟 {need_step}")
    return problems


# ---------- 執行 ----------

FPS_TOLERANCE = 0.01
MAX_LISTED = 5


def resolve_param(value, slot_values, options, pre_results):
    """把 ``{slot}``／``{option}``／``{pre.<slot>.<欄位>}`` 換成實際值;字面值原樣回傳。"""
    if isinstance(value, list):
        return [resolve_param(item, slot_values, options, pre_results) for item in value]
    if not isinstance(value, str):
        return value
    match = REF_RE.match(value)
    if not match:
        return value
    parts = match.group(1).split(".")
    if len(parts) == 1:
        if parts[0] in slot_values:
            return slot_values[parts[0]]
        if parts[0] in options:
            return options[parts[0]]
        raise KeyError(f"引用 {value} 沒有值")
    result = pre_results.get(parts[1])
    if not result or result.get(parts[2]) is None:
        raise KeyError(f"引用 {value} 沒有值(pre 步驟沒有量到 {parts[1]}.{parts[2]})")
    return result[parts[2]]


def _message(exc):
    if isinstance(exc, KeyError) and exc.args:
        return str(exc.args[0])
    return str(exc) or type(exc).__name__


def _record(step, target, problems, detail=None, warnings=None, status=None):
    return {"step": step, "target": target,
            "status": status or ("fail" if problems else "pass"),
            "problems": list(problems), "warnings": list(warnings or []), "detail": detail or {}}


def _fps_matches(measured, wanted):
    return measured is not None and abs(float(measured) - float(wanted)) <= FPS_TOLERANCE


def _check_video_input(step, path, params, media):
    problems = []
    info = media.probe_video(path)
    if "fps" in params and not _fps_matches(info["fps_value"], params["fps"]):
        problems.append(f"{path}: FPS 是 {info.get('fps_rational') or info['fps']}({info['fps_value']:g}),需要 {params['fps']}")
    if params.get("cfr") and info["pts_uniform"] is not True:
        problems.append(f"{path}: 不是固定幀率(pts 間隔不一致);請先轉成 CFR")
    if "frames_min" in params and info["frames"] < params["frames_min"]:
        problems.append(f"{path}: 只有 {info['frames']} 幀,至少需要 {params['frames_min']} 幀")
    if "frames_max" in params and info["frames"] > params["frames_max"]:
        problems.append(f"{path}: 有 {info['frames']} 幀,最多 {params['frames_max']} 幀")
    return info, problems, []


WORK_DIR = "work"
COMPOSITED_DIR = "composited"


def parse_crop(value):
    """``vace_work_area`` 的 crop:null／空字串＝自動;``"x0,y0,x1,y1"`` 或 4 個整數的陣列。"""
    if value in (None, ""):
        return None
    parts = value if isinstance(value, list) else [p.strip() for p in str(value).split(",")]
    try:
        crop = [int(p) for p in parts]
    except (TypeError, ValueError):
        crop = []
    if len(crop) != 4:
        raise ValueError(f"crop 要寫成 x0,y0,x1,y1(4 個整數),收到 {value!r}")
    return crop


def run_pre_checks(template, resolution, media, *, work_dir=None, context=None):
    """執行 ``upload`` 以外的 pre 步驟。回傳 (pre_results, checks, problems, warnings);
    pre_results 是 {slot: 量測值} 與 {步驟: 結果},給 ``{pre.<slot|步驟>.<欄位>}`` 引用。

    會產生檔案的步驟(``vace_work_area``)寫到 ``<work_dir>/work/``;產生的檔案放在
    ``context["generated"]``({slot: 路徑},run.py 拿去上傳),給 post 步驟用的中間資料放在 ``context[步驟]``。
    """
    slot_values, options = resolution["slot_values"], resolution["options"]
    inputs = resolution["inputs"]
    context = {} if context is None else context
    context.setdefault("generated", {})
    pre_results, checks, problems, warnings = {}, [], [], []
    for step in template.data.get("pre") or []:
        name = step["step"]
        if name == "upload":
            continue
        try:
            params = {k: resolve_param(v, slot_values, options, pre_results) for k, v in step.items() if k != "step"}
            if name == "vace_work_area":
                target = step["video"]
                if not work_dir:
                    raise ValueError("vace_work_area 需要 run 資料夾(work_dir)")
                info, state = media.vace_work_area(
                    inputs[params["video"]], inputs[params["masks"]], os.path.join(work_dir, WORK_DIR),
                    mask_object=params.get("mask_object", 1), grow=params.get("grow", 8), pad=params.get("pad", 48),
                    crop=parse_crop(params.get("crop")), mode=params.get("mode", "keep"))
                pre_results[name] = info
                context[name] = state
                context["generated"][params["control"]] = info["control"]
                context["generated"][params["mask"]] = info["mask"]
                step_problems, step_warnings = [], []
            elif name == "extract_last_frame":
                target = step["video"]
                if not work_dir:
                    raise ValueError("extract_last_frame 需要 run 資料夾(work_dir)")
                dest = os.path.join(work_dir, WORK_DIR, "last_frame.png")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                written = media.extract_last_frame(inputs[params["video"]], dest)
                context["generated"][params["image"]] = written
                info = {"path": written}
                step_problems, step_warnings = [], []
            elif name == "camera_end_still":
                target = step["image"]
                if not work_dir:
                    raise ValueError("camera_end_still 需要 run 資料夾(work_dir)")
                dest = os.path.join(work_dir, WORK_DIR, "camera_end.png")
                os.makedirs(os.path.dirname(dest), exist_ok=True)
                written = media.camera_end_still(
                    inputs[params["image"]], params["camera"], int(params["width"]), int(params["height"]), dest)
                info = {"path": written}
                step_problems, step_warnings = [], []
                if written:
                    context["generated"][params["still"]] = written
                else:
                    step_problems.append("這個運鏡沒有終點靜幀(orbit 做不出畫面外的像素)")
            elif name == "check_image":
                target = params["slot"]
                info = media.probe_image(inputs[target])
                pre_results[target] = info
                step_problems, step_warnings = [], []
            elif name == "check_video":
                target = params["slot"]
                info, step_problems, step_warnings = _check_video_input(name, inputs[target], params, media)
                pre_results[target] = info
            elif name == "check_mask_matches_video":
                target = params["mask"]
                video = pre_results.get(params["video"]) or media.probe_video(inputs[params["video"]])
                info = media.mask_stats(inputs[target], params.get("channel", "red"))
                step_problems, step_warnings = [], []
                if (info["width"], info["height"]) != (video["width"], video["height"]):
                    step_problems.append(f"{inputs[target]}: 遮罩 {info['width']}×{info['height']} 和影片 "
                                         f"{video['width']}×{video['height']} 尺寸不同(不會自動縮放)")
                if not info["nonzero"]:
                    step_problems.append(f"{inputs[target]}: 遮罩的{params.get('channel', 'red')}通道全黑,沒有選到物件")
                if info.get("has_transparency"):
                    step_warnings.append(f"{inputs[target]}: 遮罩有透明通道;graph 只讀"
                                         f"{params.get('channel', 'red')}通道,透明度會被忽略")
            else:
                raise KeyError(f"{name} 不是 pre 步驟")
        except Exception as exc:  # noqa: BLE001 - 讀檔／解碼／缺套件都轉成可讀訊息
            target = step.get("video") if name == "vace_work_area" else step.get("slot") or step.get("mask") or "-"
            checks.append(_record(name, target, [_message(exc)]))
            problems.append(f"{name}({target}): {_message(exc)}")
            continue
        checks.append(_record(name, target, step_problems, info, step_warnings))
        problems += [f"{name}({target}): {p}" for p in step_problems]
        warnings += step_warnings
    return pre_results, checks, problems, warnings


def _compare(problems, label, measured, wanted):
    if wanted is not None and measured != wanted:
        problems.append(f"{label}是 {measured},需要 {wanted}")


def run_post_checks(template, resolution, pre_results, outputs, dest_dir, media, *, context=None):
    """執行 post 步驟。``outputs``:{output id: [本機檔案路徑]}。回傳 (checks, problems, warnings, artifacts);
    artifacts 是 {output id: 量測值}、keyframes／mask_preview 的檔案,以及 post 步驟產生的檔案(``derived``)。
    ``context`` 是 :func:`run_pre_checks` 用過的同一個 dict(paste_back 需要 vace_work_area 的中間資料)。"""
    slot_values, options, inputs = resolution["slot_values"], resolution["options"], resolution["inputs"]
    context = {} if context is None else context
    checks, problems, warnings = [], [], []
    artifacts = {"media": {}, "keyframes": {}, "mask_preview": None, "derived": []}
    source_has_audio = any(r.get("has_audio") for r in pre_results.values() if isinstance(r, dict))
    for step in template.data.get("post") or []:
        name = step["step"]
        output_id = step.get("output")
        paths = outputs.get(output_id) or []
        step_problems, step_warnings, detail = [], [], {}
        try:
            params = {k: resolve_param(v, slot_values, options, pre_results) for k, v in step.items() if k != "step"}
            if name in ("check_video_output", "extract_keyframes") and len(paths) != 1:
                raise ValueError(f"output {output_id} 應該剛好 1 個檔案,實際 {len(paths)} 個")
            if name == "check_video_output":
                info = media.probe_video(paths[0])
                artifacts["media"][paths[0]] = info
                detail = info
                _compare(step_problems, "寬度", info["width"], params.get("width"))
                _compare(step_problems, "高度", info["height"], params.get("height"))
                _compare(step_problems, "幀數", info["frames"], params.get("frames"))
                if "fps" in params and not _fps_matches(info["fps_value"], params["fps"]):
                    step_problems.append(f"FPS 是 {info.get('fps_rational') or info['fps']},需要 {params['fps']}")
                if info["pts_uniform"] is False:
                    step_problems.append("pts 間隔不一致(不是固定幀率)")
                if "audio" in params:
                    want_audio = bool(params["audio"])
                    if want_audio and not source_has_audio:
                        step_warnings.append("keep_audio 開啟,但來源影片沒有音軌;輸出沒有音軌是正常的")
                        want_audio = False
                    if info["has_audio"] != want_audio:
                        step_problems.append(f"音軌:{'有' if info['has_audio'] else '沒有'},"
                                             f"預期{'有' if want_audio else '沒有'}")
            elif name == "check_png_sequence":
                if not paths:
                    raise ValueError(f"output {output_id} 沒有任何檔案")
                rows = [media.png_frame_stats(path) for path in paths]
                for path, row in zip(paths, rows):
                    artifacts["media"][path] = row
                _compare(step_problems, "張數", len(paths), params.get("count"))
                sizes = {(row["width"], row["height"]) for row in rows}
                wanted = (params.get("width"), params.get("height"))
                bad = [os.path.basename(p) for p, r in zip(paths, rows)
                       if wanted != (None, None) and (r["width"], r["height"]) != wanted]
                if bad:
                    step_problems.append(f"{len(bad)} 張尺寸不是 {wanted[0]}×{wanted[1]}: {', '.join(bad[:MAX_LISTED])}"
                                         + (" …" if len(bad) > MAX_LISTED else ""))
                if params.get("grayscale") == "rgb_equal":
                    color = [os.path.basename(p) for p, r in zip(paths, rows) if not r["grayscale"]]
                    if color:
                        step_problems.append(f"{len(color)} 張不是灰階(R=G=B): {', '.join(color[:MAX_LISTED])}"
                                             + (" …" if len(color) > MAX_LISTED else ""))
                detail = {"count": len(paths), "sizes": sorted(f"{w}x{h}" for w, h in sizes)}
            elif name == "extract_keyframes":
                frames = media.extract_keyframes(paths[0], params.get("which") or ["first", "middle", "last"],
                                                 os.path.join(dest_dir, "keyframes"))
                artifacts["keyframes"].update(frames)
                detail = frames
            elif name == "mask_preview":
                if not paths:
                    raise ValueError(f"output {output_id} 沒有任何檔案")
                path = media.mask_preview(inputs[params["video"]], paths,
                                          os.path.join(dest_dir, "keyframes", "mask_preview.png"))
                artifacts["mask_preview"] = path
                detail = {"path": path}
            elif name == "paste_back":
                if len(paths) != 1:
                    raise ValueError(f"output {output_id} 應該剛好 1 個檔案,實際 {len(paths)} 個")
                if "vace_work_area" not in context:
                    raise ValueError("vace_work_area 沒有完成,無法貼回")
                info = media.vace_composite(context["vace_work_area"], paths[0],
                                            os.path.join(dest_dir, COMPOSITED_DIR), feather=params.get("feather", 4))
                context[name] = info
                artifacts["derived"].append({"role": "composited_mp4", "path": info["mp4"]})
                artifacts["derived"].append({"role": "composited_frames",
                                             "path": os.path.dirname(info["frames"][0]) if info["frames"] else None,
                                             "count": len(info["frames"])})
                detail = {k: v for k, v in info.items() if k != "frames"}
                detail["frames_dir"] = artifacts["derived"][-1]["path"]
            elif name == "qa_outside_mask_unchanged":
                output_id = "paste_back"
                if "paste_back" not in context:
                    raise ValueError("paste_back 沒有完成,沒有可以檢查的貼回結果")
                info = context["paste_back"]
                counts = media.vace_outside_changes(context["vace_work_area"], info["frames"], info["feather"])
                total = sum(counts)
                detail = {"frames": len(counts), "outside_changed_pixels_total": total,
                          "frames_with_changes": [i for i, c in enumerate(counts) if c]}
                if total:
                    step_problems.append(f"遮罩外有 {total} 個像素和來源不同(應該是 0)")
            else:
                raise KeyError(f"{name} 不是 post 步驟")
        except Exception as exc:  # noqa: BLE001 - 單一步驟失敗不中斷其他檢查
            message = _message(exc)
            if step.get("optional"):
                checks.append(_record(name, output_id, [], {}, [message], status="skipped"))
                warnings.append(f"{name}(選用)沒有完成: {message}")
                continue
            checks.append(_record(name, output_id, [message]))
            problems.append(f"{name}({output_id}): {message}")
            continue
        checks.append(_record(name, output_id, step_problems, detail, step_warnings))
        problems += [f"{name}({output_id}): {p}" for p in step_problems]
        warnings += step_warnings
    return checks, problems, warnings, artifacts
