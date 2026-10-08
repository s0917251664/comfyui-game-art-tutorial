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
        problems.append(f"{path}: FPS 是 {info['fps']}({info['fps_value']}),需要 {params['fps']}")
    if params.get("cfr") and info["pts_uniform"] is not True:
        problems.append(f"{path}: 不是固定幀率(pts 間隔不一致);請先轉成 CFR")
    if "frames_min" in params and info["frames"] < params["frames_min"]:
        problems.append(f"{path}: 只有 {info['frames']} 幀,至少需要 {params['frames_min']} 幀")
    if "frames_max" in params and info["frames"] > params["frames_max"]:
        problems.append(f"{path}: 有 {info['frames']} 幀,最多 {params['frames_max']} 幀")
    return info, problems, []


def run_pre_checks(template, resolution, media):
    """執行 ``upload`` 以外的 pre 步驟。回傳 (pre_results, checks, problems, warnings);
    pre_results 是 {slot: 量測值},給 ``{pre.<slot>.<欄位>}`` 引用。"""
    slot_values, options = resolution["slot_values"], resolution["options"]
    inputs = resolution["inputs"]
    pre_results, checks, problems, warnings = {}, [], [], []
    for step in template.data.get("pre") or []:
        name = step["step"]
        if name == "upload":
            continue
        try:
            params = {k: resolve_param(v, slot_values, options, pre_results) for k, v in step.items() if k != "step"}
            if name == "check_image":
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
            target = step.get("slot") or step.get("mask") or "-"
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


def run_post_checks(template, resolution, pre_results, outputs, dest_dir, media):
    """執行 post 步驟。``outputs``:{output id: [本機檔案路徑]}。回傳 (checks, problems, warnings, artifacts);
    artifacts 是 {output id: 量測值} 與 keyframes／mask_preview 的檔案。"""
    slot_values, options, inputs = resolution["slot_values"], resolution["options"], resolution["inputs"]
    checks, problems, warnings = [], [], []
    artifacts = {"media": {}, "keyframes": {}, "mask_preview": None}
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
                    step_problems.append(f"FPS 是 {info['fps']},需要 {params['fps']}")
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
