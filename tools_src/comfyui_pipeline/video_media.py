"""影片/圖片媒體工具:畫布、輸入驗證、抽幀、concat、chroma key composite。

從 generate.py 抽出。
"""
import math
import os
import re
import shutil
import tempfile
from fractions import Fraction

from .runtime import facade as rt
from .video_catalog import (
    VIDEO_AUDIO_DRIFT_TOLERANCE, VIDEO_DURATION_MAX, VIDEO_DURATION_MIN, VIDEO_FPS,
    VIDEO_FPS_TOLERANCE, VIDEO_INPUT_MIN_DURATION, VIDEO_MAX_SIDE,
)


def _require_video_duration(duration):
    if not (VIDEO_DURATION_MIN <= duration <= VIDEO_DURATION_MAX):
        raise SystemExit(
            f"--duration 鎖在 {VIDEO_DURATION_MIN}~{VIDEO_DURATION_MAX} 秒,"
            f"更長請拆成多個鏡頭(目前給的是 {duration})。"
        )
    return duration


def _require_wh_pair(args):
    if (getattr(args, "width", None) is None) ^ (getattr(args, "height", None) is None):
        raise SystemExit("--width 跟 --height 要一起給,或兩個都不給(跟來源圖比例走)。")


def video_canvas(image_path, width=None, height=None):
    rt._require_pillow()
    """把輸出畫布收到 VIDEO_MAX_SIDE 以內、且寬高都是 32 的倍數。
    不給寬高就跟來源圖比例走(先縮最長邊)。16GB 實測只鎖到 768,再大要另測。"""
    if width and height:
        src_w, src_h = width, height
    else:
        with rt.PILImage.open(image_path) as im:
            src_w, src_h = im.size
    long_side = max(src_w, src_h)
    scale = min(1.0, VIDEO_MAX_SIDE / float(long_side))
    w = max(32, int(src_w * scale) // 32 * 32)
    h = max(32, int(src_h * scale) // 32 * 32)
    return w, h


def _image_size(image_path):
    rt._require_pillow()
    try:
        with rt.PILImage.open(image_path) as image:
            return image.size
    except (OSError, ValueError) as exc:
        raise ValueError(f"無法讀取影片輸入圖片: {image_path}") from exc


def validate_transition_images(start_path, end_path):
    """Reject incompatible A/B aspect ratios before either image is uploaded."""
    start_width, start_height = rt._image_size(start_path)
    end_width, end_height = rt._image_size(end_path)
    start_ratio = start_width / float(start_height)
    end_ratio = end_width / float(end_height)
    if not math.isclose(start_ratio, end_ratio, rel_tol=0.0, abs_tol=0.01):
        raise ValueError(
            "transition 的 --start/--end 必須有相近畫布比例；"
            f"目前是 {start_width}x{start_height} 與 {end_width}x{end_height}，"
            "避免尾幀被錯誤拉伸後才送進模型。"
        )
    return (start_width, start_height), (end_width, end_height)


def _make_temp_image_path(output_dir, prefix):
    """在指定輸出目錄建立唯一的暫存 PNG 路徑，並關閉 mkstemp 的 fd。

    呼叫端會在上傳到 ComfyUI 後刪除這個檔案；使用 ``mkstemp`` 避免同時執行
    多個影片 task 時共用固定檔名，也避免 Windows 上開啟中的 NamedTemporaryFile
    無法被 Pillow/ffmpeg 重新開啟。
    """
    output_dir = os.fspath(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    fd, path = tempfile.mkstemp(prefix=prefix, suffix=".png", dir=output_dir)
    os.close(fd)
    return path


def _remove_temp_file(path):
    if not path:
        return
    try:
        os.unlink(path)
    except FileNotFoundError:
        pass


def _video_streams(container):
    streams = getattr(container, "streams", None)
    video = getattr(streams, "video", ()) if streams is not None else ()
    if not video:
        raise RuntimeError("影片沒有 video stream")
    return video


def _fps_fraction(rate):
    """將 PyAV 的 Fraction/數值 frame rate 正規化成可精確比較的 Fraction。"""
    if rate is None:
        return None
    if isinstance(rate, Fraction):
        return rate
    try:
        numerator, denominator = rate.numerator, rate.denominator
    except AttributeError:
        numerator = denominator = None
    if numerator is not None and denominator is not None:
        try:
            return Fraction(numerator, denominator)
        except (TypeError, ValueError, ZeroDivisionError):
            pass
    try:
        return Fraction(str(rate))
    except (TypeError, ValueError, ZeroDivisionError):
        try:
            return Fraction(str(float(rate)))
        except (TypeError, ValueError, ZeroDivisionError, OverflowError) as exc:
            raise ValueError(f"無法辨識影片 FPS: {rate!r}") from exc


def _read_motion_fps(video_path):
    """讀取動作參考片的平均 FPS；未知或無法解析時不猜測。"""
    try:
        import av
    except ImportError as exc:
        raise RuntimeError("pose_drive 需要 PyAV 才能驗證 --motion-ref 的 FPS") from exc
    container = av.open(video_path)
    try:
        stream = _video_streams(container)[0]
        rate = getattr(stream, "average_rate", None)
    finally:
        container.close()
    if rate is None:
        raise ValueError(f"--motion-ref 無法辨識 FPS: {video_path}")
    try:
        fps = float(rate)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError(f"--motion-ref 無法辨識 FPS: {rate!r}") from exc
    if not math.isfinite(fps):
        raise ValueError(f"--motion-ref 無法辨識 FPS: {rate!r}")
    return fps


def validate_motion_reference_fps(video_path):
    """pose_drive 不做重採樣，只接受接近產線 24 FPS 的動作參考影片。"""
    fps = _read_motion_fps(video_path)
    if not math.isclose(fps, float(VIDEO_FPS), rel_tol=0.0, abs_tol=VIDEO_FPS_TOLERANCE):
        raise ValueError(
            f"--motion-ref 必須是接近 {VIDEO_FPS} FPS 的影片，目前是 {fps:g} FPS；"
            "產線不會靜默重採樣，請先轉成 24 FPS。"
        )
    return fps


def validate_video_input(video_path, label="影片輸入", min_duration=VIDEO_INPUT_MIN_DURATION,
                         require_fps=None):
    """Decode an input before upload/queue; never let a corrupt/empty video reach ComfyUI."""
    try:
        import av
    except ImportError as exc:
        raise RuntimeError(f"{label} 需要 PyAV 才能驗證可解碼性") from exc
    path = os.path.abspath(os.fspath(video_path))
    if not os.path.isfile(path):
        raise ValueError(f"{label} 不存在: {path}")
    try:
        container = av.open(path)
    except Exception as exc:
        raise ValueError(f"{label} 無法解碼: {path}: {exc}") from exc
    try:
        stream = _video_streams(container)[0]
        fps_fraction = _fps_fraction(getattr(stream, "average_rate", None))
        if fps_fraction is None or fps_fraction <= 0:
            raise ValueError(f"{label} 缺少有效 FPS: {path}")
        frames = 0
        for _ in container.decode(video=0):
            frames += 1
        if frames < 1:
            raise ValueError(f"{label} 沒有影格: {path}")
        duration = frames / float(fps_fraction)
        if duration < float(min_duration):
            raise ValueError(
                f"{label} 時長不足: {duration:.3f}s < {float(min_duration):.3f}s: {path}"
            )
        fps = float(fps_fraction)
        if require_fps is not None and not math.isclose(
                fps, float(require_fps), rel_tol=0.0, abs_tol=VIDEO_FPS_TOLERANCE):
            raise ValueError(
                f"{label} 必須接近 {require_fps} FPS，目前是 {fps:g} FPS: {path}"
            )
        return {
            "path": path, "width": int(stream.width), "height": int(stream.height),
            "fps": fps, "frames": frames, "duration_seconds": round(duration, 6),
            "audio": bool(getattr(container.streams, "audio", ()) or ()),
        }
    except (ValueError, RuntimeError):
        raise
    except Exception as exc:
        raise ValueError(f"{label} 解碼失敗: {path}: {exc}") from exc
    finally:
        container.close()


def extract_video_frames(video_path, output_dir=None):
    """Transactional mp4 -> png extraction; a failed run keeps the previous set."""
    import av
    output_dir = output_dir or os.path.dirname(os.path.abspath(video_path))
    # SaveVideo 常吐 foo_00001_.mp4,直接加 _frames 會變成 foo_00001__frames。
    stem = os.path.splitext(os.path.basename(video_path))[0].rstrip("_")
    frame_dir = os.path.join(output_dir, stem + "_frames")
    if os.path.islink(frame_dir):
        raise RuntimeError(f"抽幀目錄是 symlink，拒絕清理: {frame_dir}")
    parent = os.path.dirname(frame_dir) or "."
    os.makedirs(parent, exist_ok=True)
    if os.path.islink(frame_dir):
        raise RuntimeError(f"抽幀目錄是 symlink，拒絕清理: {frame_dir}")
    staging = tempfile.mkdtemp(prefix=f".{os.path.basename(frame_dir)}.", dir=parent)
    paths = []
    try:
        # Preserve user-owned non-frame files from the previous directory, but
        # never follow links or copy an unexpected directory into the staging set.
        if os.path.isdir(frame_dir):
            for entry in os.scandir(frame_dir):
                if re.fullmatch(r"\d+\.png", entry.name):
                    if entry.is_symlink() or not entry.is_file(follow_symlinks=False):
                        raise RuntimeError(f"抽幀輸出檔不是安全的一般檔案: {entry.path}")
                    continue
                if entry.is_symlink():
                    raise RuntimeError(f"抽幀保留項目是 symlink，拒絕複製: {entry.path}")
                destination = os.path.join(staging, entry.name)
                if entry.is_file(follow_symlinks=False):
                    shutil.copy2(entry.path, destination)
                elif entry.is_dir(follow_symlinks=False):
                    shutil.copytree(entry.path, destination, symlinks=False)
                else:
                    raise RuntimeError(f"抽幀保留項目不是一般檔案或目錄: {entry.path}")
        container = av.open(video_path)
        try:
            for i, frame in enumerate(container.decode(video=0)):
                p = os.path.join(staging, f"{i:03d}.png")
                frame.to_image().save(p)
                paths.append(p)
        finally:
            container.close()
        if not paths:
            raise RuntimeError(f"影片沒有影格，未更新既有抽幀目錄: {video_path}")
        old_dir = None
        if os.path.lexists(frame_dir):
            old_dir = tempfile.mkdtemp(prefix=f".{os.path.basename(frame_dir)}.old.", dir=parent)
            os.rmdir(old_dir)
            os.replace(frame_dir, old_dir)
        try:
            os.replace(staging, frame_dir)
        except Exception:
            if old_dir is not None and not os.path.lexists(frame_dir):
                os.replace(old_dir, frame_dir)
            raise
        if old_dir is not None:
            shutil.rmtree(old_dir)
        paths = [os.path.join(frame_dir, os.path.basename(path)) for path in paths]
    except Exception:
        if os.path.isdir(staging):
            shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"[抽幀] {len(paths)} 張 -> {frame_dir}")
    return paths, frame_dir


def extract_last_frame(video_path, dest_path):
    """clip_extend:上一鏡最後一幀當下一鏡靜幀。"""
    import av
    os.makedirs(os.path.dirname(os.path.abspath(dest_path)) or ".", exist_ok=True)
    container = av.open(video_path)
    last = None
    try:
        for frame in container.decode(video=0):
            last = frame
    finally:
        container.close()
    if last is None:
        raise RuntimeError(f"影片沒有畫面: {video_path}")
    last.to_image().save(dest_path)
    return dest_path


def _resize_video_image(image, width, height, mode):
    if image.size == (width, height):
        return image
    if mode == "stretch":
        return image.resize((width, height), rt.PILImage.Resampling.LANCZOS)
    source_ratio = image.width / float(image.height)
    target_ratio = width / float(height)
    if mode == "fit":
        scale = min(width / image.width, height / image.height)
        resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), rt.PILImage.Resampling.LANCZOS)
        canvas = rt.PILImage.new("RGB", (width, height), (0, 0, 0))
        canvas.paste(resized, ((width - resized.width) // 2, (height - resized.height) // 2))
        return canvas
    if mode == "fill":
        scale = max(width / image.width, height / image.height)
        resized = image.resize((max(1, round(image.width * scale)), max(1, round(image.height * scale))), rt.PILImage.Resampling.LANCZOS)
        left = max(0, (resized.width - width) // 2)
        top = max(0, (resized.height - height) // 2)
        return resized.crop((left, top, left + width, top + height))
    raise ValueError(f"未知 resize_mode: {mode!r}")


def concat_videos(video_paths, dest_path, allow_overwrite=False, resize_mode="strict",
                  audio_policy="require-consistent"):
    """Basic local concatenation with explicit geometry/audio policies."""
    if len(video_paths) < 2:
        raise RuntimeError("video_concat 至少要兩支影片")
    if resize_mode not in ("strict", "fit", "fill", "stretch"):
        raise ValueError("resize_mode 必須是 strict/fit/fill/stretch")
    if audio_policy not in ("require-consistent", "drop", "silence-missing"):
        raise ValueError("audio_policy 必須是 require-consistent/drop/silence-missing")
    dest_path = os.fspath(dest_path)
    dest_canonical = os.path.normcase(os.path.realpath(os.path.abspath(dest_path)))
    for source in video_paths:
        source_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(source))))
        if source_canonical == dest_canonical:
            raise ValueError(f"video_concat 輸入影片不可與輸出路徑相同: {source!r}")
    if os.path.lexists(dest_path) and not allow_overwrite:
        raise RuntimeError(
            f"拒絕覆寫既有 video_concat 輸出: {dest_path!r}；"
            "請換 --name，或明確使用 --overwrite"
        )
    rt._require_pillow()
    import av

    stream_specs = []
    audio_present = []
    input_durations = []
    for source in video_paths:
        try:
            inp = av.open(source)
        except Exception as exc:
            raise ValueError(f"video_concat 無法解碼輸入影片 {source!r}: {exc}") from exc
        try:
            vs = _video_streams(inp)[0]
            # 保留原本無 average_rate 時採 24 FPS 的行為；有明確 rate 時則用
            # Fraction 精確比較，避免 24/25 或 23.976/24 被靜默混接。
            fps = _fps_fraction(getattr(vs, "average_rate", None))
            if fps is None:
                fps = Fraction(VIDEO_FPS, 1)
            elif fps <= 0:
                raise ValueError(f"影片 FPS 必須大於 0: {source!r}")
            stream_specs.append((vs.width, vs.height, fps))
            audio_present.append(bool(getattr(inp.streams, "audio", ()) or ()))
            decoder = getattr(inp, "decode", None)
            input_durations.append(
                sum(1 for _ in decoder(video=0)) / float(fps) if decoder is not None else None
            )
        finally:
            inp.close()

    expected_fps = stream_specs[0][2]
    mismatched = [
        (source, spec[2])
        for source, spec in zip(video_paths, stream_specs)
        if spec[2] != expected_fps
    ]
    if mismatched:
        details = ", ".join(f"{source!r}={float(rate):g} FPS" for source, rate in mismatched)
        raise ValueError(
            f"video_concat 所有輸入影片必須使用相同 FPS；"
            f"第一支={float(expected_fps):g} FPS，{details}"
        )
    if expected_fps != Fraction(VIDEO_FPS, 1):
        raise ValueError(
            f"video_concat 只接受產線 {VIDEO_FPS} FPS 影片，目前第一支是 {float(expected_fps):g} FPS"
        )

    width, height = stream_specs[0][0], stream_specs[0][1]
    mismatched_dimensions = [
        (source, spec[0], spec[1])
        for source, spec in zip(video_paths, stream_specs)
        if (spec[0], spec[1]) != (width, height)
    ]
    if mismatched_dimensions and resize_mode == "strict":
        details = ", ".join(f"{source!r}={w}x{h}" for source, w, h in mismatched_dimensions)
        raise ValueError(
            "video_concat 輸入影片尺寸不同，預設拒絕以免默默 stretch；"
            f"第一支={width}x{height}，{details}。請明確給 --resize-mode fit/fill/stretch"
        )
    fps = expected_fps
    all_audio = all(audio_present)
    any_audio = any(audio_present)
    if audio_policy == "require-consistent" and any_audio and not all_audio:
        raise ValueError(
            "video_concat 輸入音訊不一致；預設拒絕混合有聲/無聲。"
            "請明確給 --audio-policy drop 或 silence-missing"
        )
    keep_audio = all_audio if audio_policy == "require-consistent" else (
        any_audio if audio_policy == "silence-missing" else False
    )
    if keep_audio:
        for src, has_audio, video_duration in zip(video_paths, audio_present, input_durations):
            if not has_audio:
                continue
            if video_duration is None:
                continue
            inp = av.open(src)
            try:
                audio_stream = list(getattr(inp.streams, "audio", ()) or ())[0]
                a_duration = getattr(audio_stream, "duration", None)
                a_base = getattr(audio_stream, "time_base", None)
                if a_duration is not None and a_base is not None:
                    actual = float(a_duration * a_base)
                    if abs(actual - video_duration) > VIDEO_AUDIO_DRIFT_TOLERANCE:
                        raise ValueError(
                            f"video_concat 音畫 duration drift 超過 {VIDEO_AUDIO_DRIFT_TOLERANCE}s: "
                            f"{src!r} video={video_duration:.3f}s audio={actual:.3f}s"
                        )
            finally:
                inp.close()
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    fd, temp_dest = tempfile.mkstemp(
        prefix=f".{os.path.basename(dest_path)}.", suffix=".mp4", dir=dest_dir
    )
    os.close(fd)
    out = None
    try:
        out = av.open(temp_dest, "w")
        out_v = out.add_stream("libx264", rate=fps)
        out_v.width = width
        out_v.height = height
        out_v.pix_fmt = "yuv420p"
        # 兩個 stream 都要在寫任何 packet 之前建好,不然 mp4 mux 會 EINVAL
        out_a = out.add_stream("aac", rate=32000) if keep_audio else None
        for src in video_paths:
            inp = av.open(src)
            try:
                for frame in inp.decode(video=0):
                    img = frame.to_image()
                    if img.size != (width, height):
                        img = _resize_video_image(img, width, height, resize_mode)
                    of = av.VideoFrame.from_image(img)
                    for packet in out_v.encode(of):
                        out.mux(packet)
            finally:
                inp.close()
        for packet in out_v.encode():
            out.mux(packet)
        if out_a:
            resampler = av.AudioResampler(format="fltp", layout="stereo", rate=32000)
            sample_i = 0
            sample_rate = 32000
            for src, has_audio, video_duration in zip(video_paths, audio_present, input_durations):
                ain = av.open(src)
                try:
                    frames_in = list(ain.decode(audio=0)) if has_audio else []
                finally:
                    ain.close()
                if not has_audio and audio_policy == "silence-missing" and video_duration is not None:
                    silence_samples = max(1, round(video_duration * sample_rate))
                    silence = av.AudioFrame(format="fltp", layout="stereo", samples=silence_samples)
                    silence.sample_rate = sample_rate
                    for plane in silence.planes:
                        plane.update(bytes(plane.buffer_size))
                    frames_in = [silence]
                frames_in.append(None)
                for frame in frames_in:
                    resampled = resampler.resample(frame) or []
                    if not isinstance(resampled, (list, tuple)):
                        resampled = [resampled]
                    for rf in resampled:
                        if rf is None:
                            continue
                        rf.pts = sample_i
                        sample_i += rf.samples
                        for packet in out_a.encode(rf) or []:
                            out.mux(packet)
            for packet in out_a.encode(None) or []:
                out.mux(packet)
        out.close()
        out = None
        os.replace(temp_dest, dest_path)
    except Exception:
        if out is not None:
            try:
                out.close()
            except Exception:
                pass
        try:
            os.unlink(temp_dest)
        except FileNotFoundError:
            pass
        raise
    note = "含立體聲" if keep_audio else "無聲(有鏡頭沒有音軌,整段不接聲音)"
    print(f"[接片] {len(video_paths)} 支 -> {dest_path} ({note})")
    return dest_path


VIDEO_COMPOSITE_BACKGROUND_EXTS = (".mp4", ".mov", ".mkv", ".webm", ".m4v")


def composite_videos(foreground_path, background_path, dest_path, chroma_color="00FF00",
                     tolerance=60.0, softness=40.0, resize_mode="fill", allow_overwrite=False):
    """Chroma-key 前景疊到背景(影片或靜態圖)上，純本機 PyAV+numpy 逐幀合成，不經 ComfyUI。

    只吃前景本身的音軌(背景音軌一律丟棄)——這條產線目前只有一個會有音軌的來源
    (h3 backend 生成的前景)，混兩條音軌的取捨留給外部剪接軟體，不在這裡猜。
    """
    if resize_mode not in ("strict", "fit", "fill", "stretch"):
        raise ValueError("resize_mode 必須是 strict/fit/fill/stretch")
    if not (0.0 <= tolerance <= 255.0):
        raise ValueError(f"--tolerance 必須介於 0..255: {tolerance!r}")
    if not (0.0 < softness <= 255.0):
        raise ValueError(f"--softness 必須介於 0(不含)..255: {softness!r}")
    chroma_color = str(chroma_color).strip().lstrip("#")
    if not re.fullmatch(r"[0-9a-fA-F]{6}", chroma_color or ""):
        raise ValueError(f"--chroma-color 必須是 6 碼十六進位色碼(例如 00FF00): {chroma_color!r}")
    chroma_rgb = tuple(int(chroma_color[i:i + 2], 16) for i in (0, 2, 4))

    dest_path = os.fspath(dest_path)
    dest_canonical = os.path.normcase(os.path.realpath(os.path.abspath(dest_path)))
    for source in (foreground_path, background_path):
        source_canonical = os.path.normcase(os.path.realpath(os.path.abspath(os.fspath(source))))
        if source_canonical == dest_canonical:
            raise ValueError(f"video_composite 輸入不可與輸出路徑相同: {source!r}")
    if os.path.lexists(dest_path) and not allow_overwrite:
        raise RuntimeError(
            f"拒絕覆寫既有 video_composite 輸出: {dest_path!r}；"
            "請換 --name，或明確使用 --overwrite"
        )
    rt._require_pillow()
    import numpy as np
    import av

    try:
        fg_in = av.open(foreground_path)
    except Exception as exc:
        raise ValueError(f"video_composite 無法解碼 --foreground {foreground_path!r}: {exc}") from exc
    try:
        fg_vs = _video_streams(fg_in)[0]
        fps = _fps_fraction(getattr(fg_vs, "average_rate", None)) or Fraction(VIDEO_FPS, 1)
        if fps != Fraction(VIDEO_FPS, 1):
            raise ValueError(
                f"video_composite --foreground 只接受產線 {VIDEO_FPS} FPS 影片，"
                f"目前是 {float(fps):g} FPS"
            )
        width, height = fg_vs.width, fg_vs.height
        fg_audio_present = bool(getattr(fg_in.streams, "audio", ()) or ())
    except Exception:
        fg_in.close()
        raise

    background_is_video = os.path.splitext(background_path)[1].lower() in VIDEO_COMPOSITE_BACKGROUND_EXTS
    bg_in = None
    bg_image = None
    if background_is_video:
        try:
            bg_in = av.open(background_path)
        except Exception as exc:
            fg_in.close()
            raise ValueError(f"video_composite 無法解碼 --background {background_path!r}: {exc}") from exc
        try:
            bg_vs = _video_streams(bg_in)[0]
            bg_fps = _fps_fraction(getattr(bg_vs, "average_rate", None)) or Fraction(VIDEO_FPS, 1)
            if bg_fps != Fraction(VIDEO_FPS, 1):
                raise ValueError(
                    f"video_composite --background 只接受產線 {VIDEO_FPS} FPS 影片，"
                    f"目前是 {float(bg_fps):g} FPS"
                )
            bg_size = (bg_vs.width, bg_vs.height)
        except Exception:
            bg_in.close()
            fg_in.close()
            raise
    else:
        try:
            with rt.PILImage.open(background_path) as im:
                bg_image = im.convert("RGB")
                bg_size = bg_image.size
        except Exception as exc:
            fg_in.close()
            raise ValueError(f"video_composite 無法讀取 --background 圖片 {background_path!r}: {exc}") from exc

    if resize_mode == "strict" and bg_size != (width, height):
        fg_in.close()
        if bg_in is not None:
            bg_in.close()
        raise ValueError(
            "video_composite 背景尺寸跟前景不同，--resize-mode strict 拒絕縮放；"
            f"前景={width}x{height}，背景={bg_size}。"
            "請明確給 --resize-mode fit/fill/stretch"
        )

    key_rgb = np.array(chroma_rgb, dtype=np.int16)
    dest_dir = os.path.dirname(os.path.abspath(dest_path)) or "."
    os.makedirs(dest_dir, exist_ok=True)
    fd, temp_dest = tempfile.mkstemp(
        prefix=f".{os.path.basename(dest_path)}.", suffix=".mp4", dir=dest_dir
    )
    os.close(fd)
    out = None
    try:
        out = av.open(temp_dest, "w")
        out_v = out.add_stream("libx264", rate=fps)
        out_v.width = width
        out_v.height = height
        out_v.pix_fmt = "yuv420p"
        out_a = out.add_stream("aac", rate=32000) if fg_audio_present else None
        bg_decoder = bg_in.decode(video=0) if bg_in is not None else None
        frame_count = 0
        for fg_frame in fg_in.decode(video=0):
            fg_im = fg_frame.to_image().convert("RGB")
            if bg_in is None:
                bg_im = bg_image
            else:
                try:
                    bg_frame = next(bg_decoder)
                except StopIteration:
                    # PyAV/FFmpeg seek behavior varies by container. Reopening is slower than
                    # seek but deterministic, and keeps memory constant while looping a short
                    # background underneath a longer foreground.
                    bg_in.close()
                    bg_in = av.open(background_path)
                    bg_decoder = bg_in.decode(video=0)
                    try:
                        bg_frame = next(bg_decoder)
                    except StopIteration as exc:
                        raise ValueError(
                            f"video_composite --background 沒有畫面: {background_path}"
                        ) from exc
                bg_im = bg_frame.to_image().convert("RGB")
            bg_im = _resize_video_image(bg_im, width, height, resize_mode)
            fg_arr = np.asarray(fg_im, dtype=np.int16)
            bg_arr = np.asarray(bg_im, dtype=np.uint8).astype(np.float32)
            dist = np.abs(fg_arr - key_rgb).max(axis=2).astype(np.float32)
            alpha = np.clip((dist - tolerance) / softness, 0.0, 1.0)[:, :, None]
            composited = fg_arr.astype(np.float32) * alpha + bg_arr * (1.0 - alpha)
            of = av.VideoFrame.from_ndarray(np.clip(composited, 0, 255).astype(np.uint8), format="rgb24")
            for packet in out_v.encode(of):
                out.mux(packet)
            frame_count += 1
        if not frame_count:
            raise ValueError(f"video_composite --foreground 沒有畫面: {foreground_path}")
        for packet in out_v.encode():
            out.mux(packet)
        if out_a:
            ain = av.open(foreground_path)
            try:
                resampler = av.AudioResampler(format="fltp", layout="stereo", rate=32000)
                sample_i = 0
                for frame in ain.decode(audio=0):
                    resampled = resampler.resample(frame) or []
                    if not isinstance(resampled, (list, tuple)):
                        resampled = [resampled]
                    for rf in resampled:
                        if rf is None:
                            continue
                        rf.pts = sample_i
                        sample_i += rf.samples
                        for packet in out_a.encode(rf) or []:
                            out.mux(packet)
                for rf in resampler.resample(None) or []:
                    rf.pts = sample_i
                    sample_i += rf.samples
                    for packet in out_a.encode(rf) or []:
                        out.mux(packet)
            finally:
                ain.close()
            for packet in out_a.encode(None) or []:
                out.mux(packet)
        out.close()
        out = None
        os.replace(temp_dest, dest_path)
    except Exception:
        if out is not None:
            try:
                out.close()
            except Exception:
                pass
        try:
            os.unlink(temp_dest)
        except FileNotFoundError:
            pass
        raise
    finally:
        fg_in.close()
        if bg_in is not None:
            bg_in.close()
    note = "含前景音軌" if fg_audio_present else "無聲"
    print(f"[合成] {foreground_path} + {background_path} -> {dest_path} ({note})")
    return dest_path
