"""Local speech, measured timing, animatic, mixing and dubbing helpers.

Independent of ComfyUI graphs. Inputs are explicit; no implicit downloads,
voice substitution, playback, overwrite, audio truncation or quality approval.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import tempfile
import wave

import av
import numpy as np
from PIL import Image, ImageOps

RATE = 48000
FPS = 24
MAX_SECONDS = 600


def finite(value, label, minimum=0, maximum=MAX_SECONDS):
    value = float(value)
    if not math.isfinite(value) or value < minimum or value > maximum:
        raise ValueError(f"{label} must be between {minimum} and {maximum}")
    return value


def file_record(path):
    path = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with path.open('rb') as src:
        for block in iter(lambda: src.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(path), 'sha256': digest.hexdigest(), 'bytes': path.stat().st_size}


def load_plan(path):
    path = Path(path).resolve(strict=True)
    return json.loads(path.read_text(encoding='utf-8-sig')), path.parent


def source_path(base, value):
    return (base / value).resolve(strict=True)


def new_output(path, suffix):
    path = Path(path).resolve()
    if path.suffix.lower() != suffix:
        raise ValueError(f"Output requires {suffix}")
    if path.exists() or Path(str(path) + '.json').exists():
        raise FileExistsError(f"Use a new version path: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def temporary_for(path):
    fd, temp = tempfile.mkstemp(prefix='.' + path.stem + '-', suffix=path.suffix, dir=path.parent)
    os.close(fd)
    return Path(temp)


def publish(temp, dest, task, inputs, details):
    metadata = inspect_media(temp)
    if metadata.get('audio', {}).get('samples', 1) <= 0:
        raise ValueError('Empty audio output')
    manifest = {'schema_version': 1, 'tool': 'film_audio', 'task': task,
                'inputs': [file_record(p) for p in inputs], 'parameters': details,
                'actual': metadata, 'technical_status': 'pass', 'content_status': 'candidate',
                'output': file_record(temp)}
    manifest['output']['path'] = str(dest)
    manifest_temp = temporary_for(Path(str(dest) + '.json'))
    try:
        manifest_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        # Recheck before publishing. Existing accepted/candidate files are never replaced.
        if dest.exists() or Path(str(dest) + '.json').exists():
            raise FileExistsError(str(dest))
        os.replace(temp, dest)
        os.replace(manifest_temp, Path(str(dest) + '.json'))
    finally:
        manifest_temp.unlink(missing_ok=True)
    return manifest


def read_audio(path):
    chunks = []
    resampler = av.AudioResampler(format='fltp', layout='stereo', rate=RATE)
    with av.open(str(path)) as src:
        if len(src.streams.audio) != 1:
            raise ValueError(f'Expected exactly one audio stream: {path}')
        for frame in src.decode(audio=0):
            chunks.extend(f.to_ndarray() for f in resampler.resample(frame))
        chunks.extend(f.to_ndarray() for f in resampler.resample(None))
    if not chunks:
        raise ValueError(f'Empty audio: {path}')
    data = np.concatenate(chunks, axis=1)
    if data.shape[1] > RATE * MAX_SECONDS or not np.isfinite(data).all():
        raise ValueError('Audio exceeds ten minutes or contains nonfinite samples')
    return data


def inspect_media(path):
    result = {}
    with av.open(str(path)) as src:
        videos = len(src.streams.video)
        audios = len(src.streams.audio)
        if videos > 1 or audios > 1:
            raise ValueError('Multiple streams of the same type are unsupported')
        if videos:
            stream = src.streams.video[0]
            count = 0
            last_pts = None
            last_time = None
            is_cfr = True
            for frame in src.decode(video=0):
                if frame.pts is None or (last_pts is not None and frame.pts <= last_pts):
                    raise ValueError('Video timestamps are missing or nonmonotonic')
                last_pts = frame.pts
                if last_time is not None and stream.average_rate is not None:
                    is_cfr &= abs(float(frame.time) - last_time - 1 / float(stream.average_rate)) < 1e-5
                last_time = float(frame.time)
                count += 1
            if not count or stream.average_rate is None:
                raise ValueError('Empty video or unknown frame rate')
            result['video'] = {'width': stream.width, 'height': stream.height,
                               'fps': float(stream.average_rate), 'frames': count,
                               'duration': count / float(stream.average_rate),
                               'constant_frame_rate': bool(is_cfr),
                               'codec': stream.codec_context.name}
    if audios:
        data = read_audio(path)
        with av.open(str(path)) as src:
            native = src.streams.audio[0]
            native_metadata = {'sample_rate': native.codec_context.sample_rate,
                               'channels': native.codec_context.channels,
                               'codec': native.codec_context.name}
        result['audio'] = {'sample_rate': RATE, 'channels': 2, 'samples': data.shape[1],
                           'native': native_metadata,
                           'decoded_duration': data.shape[1] / RATE,
                           'peak': float(np.max(np.abs(data))),
                           'rms': float(np.sqrt(np.mean(data.astype(np.float64) ** 2)))}
    if not result:
        raise ValueError('No supported media streams')
    return result


def save_wav(path, data):
    if not np.isfinite(data).all() or np.max(np.abs(data)) > 1:
        raise ValueError('Audio would clip; lower gain or explicitly normalize')
    pcm = np.round(np.clip(data, -1, 1) * 32767).astype('<i2').T
    with wave.open(str(path), 'wb') as dst:
        dst.setnchannels(2)
        dst.setsampwidth(2)
        dst.setframerate(RATE)
        dst.writeframes(pcm.tobytes())


def encode_audio(out, stream, data):
    for offset in range(0, data.shape[1], 1024):
        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(data[:, offset:offset + 1024]),
                                          format='fltp', layout='stereo')
        frame.sample_rate = RATE
        frame.pts = offset
        frame.time_base = Fraction(1, RATE)
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)


def align_audio(data, count, policy):
    if policy not in ('exact', 'pad', 'trim'):
        raise ValueError('Unsupported audio_policy')
    if data.shape[1] > count:
        if policy != 'trim':
            raise ValueError('Audio is longer than video; choose trim explicitly or extend the plan')
        return data[:, :count], {'trimmed_samples': data.shape[1] - count}
    if data.shape[1] < count:
        if policy not in ('pad', 'trim'):
            raise ValueError('Audio is shorter than video; choose pad explicitly')
        return np.pad(data, ((0, 0), (0, count - data.shape[1]))), {'padded_samples': count - data.shape[1]}
    return data, {}


def sapi(request):
    script = Path(__file__).with_name('film_sapi.ps1')
    if os.name != 'nt' or not script.exists():
        raise RuntimeError('SAPI requires Windows and the deployed film_sapi.ps1')
    with tempfile.TemporaryDirectory(prefix='film-sapi-') as tempdir:
        request_path = Path(tempdir) / 'request.json'
        request_path.write_text(json.dumps(request, ensure_ascii=False), encoding='utf-8-sig')
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-File',
                                 str(script), '-RequestPath', str(request_path)],
                                capture_output=True, timeout=120)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
        return json.loads(result.stdout.decode('utf-8-sig'))


def tts(args):
    dest = new_output(args.output, '.wav')
    text_path = Path(args.text_file).resolve(strict=True)
    text = text_path.read_text(encoding='utf-8-sig').strip()
    if not text or len(text) > 5000:
        raise ValueError('Text requires 1–5000 characters; split long productions')
    temp = temporary_for(dest)
    inputs = [text_path]
    details = {'engine': args.engine, 'text': text, 'purpose': 'scratch narration; listen before accepting'}
    try:
        if args.engine == 'sapi':
            if not args.voice:
                raise ValueError('SAPI requires an explicit installed --voice')
            details.update(sapi({'action': 'speak', 'voice': args.voice, 'text': text,
                                 'output': str(temp), 'rate': args.rate}))
        elif args.engine == 'piper':
            if not args.piper_python or not args.model:
                raise ValueError('Piper requires --piper-python and --model; no automatic download')
            model = Path(args.model).resolve(strict=True)
            config = Path(str(model) + '.json').resolve(strict=True)
            inputs.extend([model, config])
            result = subprocess.run([args.piper_python, '-m', 'piper', '-m', str(model),
                                     '-f', str(temp), '--input-file', str(text_path)],
                                    capture_output=True, timeout=300,
                                    env={**os.environ, 'PYTHONUTF8': '1'})
            if result.returncode:
                raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
            details.update({'model': str(model), 'runtime': str(Path(args.piper_python).resolve())})
        else:
            if not args.qwen_python or not args.model or not args.speaker:
                raise ValueError('Qwen3 requires --qwen-python, --model and --speaker')
            if len(text) > 500:
                raise ValueError('Qwen3 clips are limited to 500 characters; split dialogue lines')
            model = Path(args.model).resolve(strict=True)
            if not model.is_dir():
                raise ValueError('Qwen3 requires a predownloaded model directory')
            inputs.extend(p for p in model.rglob('*') if p.is_file() and '.cache' not in p.parts)
            worker = Path(__file__).with_name('film_qwen.py')
            with tempfile.TemporaryDirectory(prefix='film-qwen-') as tmp:
                request_path, report_path = Path(tmp) / 'request.json', Path(tmp) / 'report.json'
                request_path.write_text(json.dumps({'model': str(model), 'text': text,
                    'speaker': args.speaker, 'instruction': args.instruction, 'seed': args.seed,
                    'output': str(temp), 'report': str(report_path)}, ensure_ascii=False), encoding='utf-8')
                result = subprocess.run([args.qwen_python, str(worker), '--request', str(request_path)],
                                        capture_output=True, timeout=900,
                                        env={**os.environ, 'PYTHONUTF8': '1'})
                if result.returncode:
                    raise RuntimeError(result.stderr.decode('utf-8', errors='replace').strip())
                details.update(json.loads(report_path.read_text(encoding='utf-8')))
            details.update({'model': str(model), 'runtime': str(Path(args.qwen_python).resolve())})
        raw = inspect_media(temp)
        details['original_synthesis_metadata'] = raw
        if raw['audio']['rms'] < 1e-6:
            raise ValueError('Synthesis produced silence')
        # Standardize downstream speech to 48 kHz stereo PCM16.
        data = read_audio(temp)
        save_wav(temp, data)
        return publish(temp, dest, 'tts', inputs, details)
    finally:
        temp.unlink(missing_ok=True)


def mix(args):
    plan, base = load_plan(args.plan)
    tracks = plan.get('tracks', [])
    if not 1 <= len(tracks) <= 32:
        raise ValueError('Mix requires 1–32 tracks')
    loaded = []
    inputs = [Path(args.plan)]
    end = 0
    for track in tracks:
        path = source_path(base, track['audio'])
        offset = round(finite(track.get('start', 0), 'start') * RATE)
        gain = 10 ** (finite(track.get('gain_db', 0), 'gain_db', -60, 12) / 20)
        data = read_audio(path) * gain
        loaded.append((offset, data))
        inputs.append(path)
        end = max(end, offset + data.shape[1])
    count = round(finite(plan.get('duration', end / RATE), 'duration', 1 / RATE) * RATE)
    if end > count:
        raise ValueError('A track exceeds mix duration; no implicit truncation')
    data = np.zeros((2, count), dtype=np.float32)
    for offset, track in loaded:
        data[:, offset:offset + track.shape[1]] += track
    peak = float(np.max(np.abs(data)))
    scale = 1.0
    if peak > 1:
        if plan.get('peak_policy', 'error') != 'normalize':
            raise ValueError('Mix would clip; use lower gain or explicit peak_policy=normalize')
        scale = 0.98 / peak
        data *= scale
    if plan.get('peak_policy', 'error') not in ('error', 'normalize'):
        raise ValueError('Unsupported peak_policy')
    dest = new_output(args.output, '.wav')
    temp = temporary_for(dest)
    try:
        save_wav(temp, data)
        return publish(temp, dest, 'mix', inputs, {'plan': plan, 'pre_scale_peak': peak, 'scale': scale})
    finally:
        temp.unlink(missing_ok=True)


def animatic(args):
    plan, base = load_plan(args.plan)
    width, height = int(plan.get('width', 768)), int(plan.get('height', 432))
    if min(width, height) < 32 or max(width, height) > 1920 or width % 2 or height % 2:
        raise ValueError('Even canvas dimensions required, 32–1920 pixels')
    shots = plan.get('shots', [])
    if not 1 <= len(shots) <= 200:
        raise ValueError('Animatic requires 1–200 shots')
    images, counts, timeline, inputs = [], [], [], [Path(args.plan)]
    frame_offset = 0
    ids = set()
    for shot in shots:
        shot_id = str(shot['id'])
        if shot_id in ids:
            raise ValueError('Duplicate shot id')
        ids.add(shot_id)
        path = source_path(base, shot['image'])
        if ('duration' in shot) == ('timing_audio' in shot):
            raise ValueError('Each shot requires duration OR timing_audio')
        if 'timing_audio' in shot:
            timing = source_path(base, shot['timing_audio'])
            duration = read_audio(timing).shape[1] / RATE
            duration += finite(shot.get('tail_pause', 0), 'tail_pause')
            inputs.append(timing)
        else:
            duration = finite(shot['duration'], 'duration', 1 / FPS)
        count = max(1, math.ceil(duration * FPS - 1e-8))
        frame_end = frame_offset + count
        if frame_end > MAX_SECONDS * FPS:
            raise ValueError('Animatic exceeds ten minutes; render scene batches')
        with Image.open(path) as img:
            images.append(ImageOps.pad(ImageOps.exif_transpose(img).convert('RGB'),
                                      (width, height), color='black'))
        counts.append(count)
        timeline.append({'id': shot_id, 'start_frame': frame_offset, 'end_frame_exclusive': frame_end,
                         'requested_duration': duration, 'actual_duration': count / FPS,
                         'start': frame_offset / FPS, 'end': frame_end / FPS})
        frame_offset = frame_end
        inputs.append(path)
    data, alignment = None, {}
    if plan.get('audio'):
        audio = source_path(base, plan['audio'])
        data, alignment = align_audio(read_audio(audio), frame_offset * (RATE // FPS),
                                      plan.get('audio_policy', 'exact'))
        inputs.append(audio)
    dest = new_output(args.output, '.mp4')
    temp = temporary_for(dest)
    try:
        with av.open(str(temp), 'w') as out:
            stream = out.add_stream('libx264', rate=FPS)
            stream.width, stream.height, stream.pix_fmt = width, height, 'yuv420p'
            audio_stream = out.add_stream('aac', rate=RATE) if data is not None else None
            index = 0
            for img, count in zip(images, counts):
                for _ in range(count):
                    frame = av.VideoFrame.from_image(img)
                    frame.pts, frame.time_base = index, Fraction(1, FPS)
                    index += 1
                    for packet in stream.encode(frame):
                        out.mux(packet)
            for packet in stream.encode(None):
                out.mux(packet)
            if audio_stream:
                encode_audio(out, audio_stream, data)
        metadata = inspect_media(temp)
        if metadata['video']['frames'] != frame_offset:
            raise ValueError('Encoded frame count differs from plan')
        return publish(temp, dest, 'animatic', inputs,
                       {'timeline': timeline, 'fps': FPS, 'fit': 'letterbox',
                        'audio_alignment': alignment, 'plan': plan})
    finally:
        temp.unlink(missing_ok=True)


def dub(args):
    video, audio = Path(args.video).resolve(strict=True), Path(args.audio).resolve(strict=True)
    meta = inspect_media(video)
    v = meta.get('video')
    if not v or not v['constant_frame_rate'] or abs(v['fps'] - FPS) > 1e-5 or v['duration'] > MAX_SECONDS:
        raise ValueError('Dub currently requires a 24 FPS video up to ten minutes')
    if 'audio' in meta and not args.replace_audio:
        raise ValueError('Video already has audio; mix it first or explicitly use --replace-audio')
    data, alignment = align_audio(read_audio(audio), v['frames'] * (RATE // FPS), args.audio_policy)
    dest = new_output(args.output, '.mp4')
    temp = temporary_for(dest)
    try:
        with av.open(str(temp), 'w') as out:
            stream = out.add_stream('libx264', rate=FPS)
            stream.width, stream.height, stream.pix_fmt = v['width'], v['height'], 'yuv420p'
            audio_stream = out.add_stream('aac', rate=RATE)
            with av.open(str(video)) as src:
                for index, frame in enumerate(src.decode(video=0)):
                    frame.pts, frame.time_base = index, Fraction(1, FPS)
                    for packet in stream.encode(frame):
                        out.mux(packet)
            for packet in stream.encode(None):
                out.mux(packet)
            encode_audio(out, audio_stream, data)
        actual = inspect_media(temp)
        if actual['video']['frames'] != v['frames']:
            raise ValueError('Dubbing changed frame count')
        return publish(temp, dest, 'dub', [video, audio],
                       {'audio_policy': args.audio_policy, 'alignment': alignment,
                        'replaced_audio': 'audio' in meta, 'video_encoding': 'H264 re-encode'})
    finally:
        temp.unlink(missing_ok=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('voices')
    probe = sub.add_parser('probe')
    probe.add_argument('path')
    speech = sub.add_parser('tts')
    speech.add_argument('--engine', choices=['sapi', 'piper', 'qwen3'], required=True)
    speech.add_argument('--text-file', required=True)
    speech.add_argument('--voice')
    speech.add_argument('--rate', type=int, choices=range(-10, 11), default=0)
    speech.add_argument('--piper-python')
    speech.add_argument('--qwen-python')
    speech.add_argument('--speaker')
    speech.add_argument('--instruction', default='')
    speech.add_argument('--seed', type=int, default=42)
    speech.add_argument('--model')
    speech.add_argument('--output', required=True)
    for name in ['mix', 'animatic']:
        cmd = sub.add_parser(name)
        cmd.add_argument('--plan', required=True)
        cmd.add_argument('--output', required=True)
    cmd = sub.add_parser('dub')
    cmd.add_argument('--video', required=True)
    cmd.add_argument('--audio', required=True)
    cmd.add_argument('--audio-policy', choices=['exact', 'pad', 'trim'], default='exact')
    cmd.add_argument('--replace-audio', action='store_true')
    cmd.add_argument('--output', required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'voices':
            result = sapi({'action': 'voices'})
        elif args.command == 'probe':
            result = {'input': file_record(args.path), 'actual': inspect_media(args.path)}
        else:
            result = {'tts': tts, 'mix': mix, 'animatic': animatic, 'dub': dub}[args.command](args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (ValueError, FileNotFoundError, FileExistsError, RuntimeError, subprocess.TimeoutExpired,
            KeyError, av.FFmpegError) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
