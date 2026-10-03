"""Bounded local MuseTalk v1.5 adapter; explicit runtime, models and input.

No downloads, ComfyUI graph, implicit motion looping, playback or acceptance.
Official shell commands receive only generated ASCII relative staging paths.
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time

import av
import numpy as np
from film_audio import (FPS, RATE, align_audio, encode_audio, file_record,
                        inspect_media, new_output, read_audio, save_wav,
                        temporary_for)

SOURCE_COMMIT = '0a89dec45a0192b824e3cf4daf96c239440c5ed8'
MODEL_FILES = (
    'models/musetalkV15/musetalk.json', 'models/musetalkV15/unet.pth',
    'models/sd-vae/config.json', 'models/sd-vae/diffusion_pytorch_model.bin',
    'models/whisper/config.json', 'models/whisper/preprocessor_config.json',
    'models/whisper/pytorch_model.bin', 'models/dwpose/dw-ll_ucoco_384.pth',
    'models/face-parse-bisent/79999_iter.pth',
    'models/face-parse-bisent/resnet18-5c106cde.pth',
    'musetalk/utils/face_detection/detection/sfd/s3fd.pth',
)


def validate_inputs(video, audio, replace_audio=False):
    meta = inspect_media(video)
    v = meta.get('video', {})
    if v.get('fps') != FPS or not v.get('constant_frame_rate'):
        raise ValueError('Source must be constant 24 FPS video')
    if not 0 < v['duration'] <= 30 or max(v['width'], v['height']) > 1280:
        raise ValueError('Source limit: 30 seconds and longest side 1280')
    if v['width'] % 2 or v['height'] % 2:
        raise ValueError('Source dimensions must be even')
    if 'audio' in meta and not replace_audio:
        raise ValueError('Source has audio; explicitly use --replace-audio')
    data = read_audio(audio)
    duration = data.shape[1] / RATE
    if not 0.5 <= duration <= 30 or float(np.sqrt(np.mean(data ** 2))) < 1e-6:
        raise ValueError('Speech must be non-silent and 0.5–30 seconds')
    if duration > v['duration'] + 1e-6:
        raise ValueError('Speech is longer than source; plan a longer source, no motion looping')
    return meta, data, math.ceil(duration * FPS)


def normalize_result(raw, dest, data, target_frames):
    meta = inspect_media(raw)
    v = meta.get('video', {})
    if v.get('fps') != FPS or not v.get('constant_frame_rate'):
        raise ValueError('MuseTalk did not produce constant 24 FPS')
    missing = target_frames - v['frames']
    if missing not in (0, 1):
        raise ValueError('Unexpected output frame count; possible missing face/frame')
    data, alignment = align_audio(data, target_frames * RATE // FPS, 'pad')
    with av.open(str(dest), 'w') as out:
        vs = out.add_stream('libx264', rate=FPS)
        vs.width, vs.height, vs.pix_fmt = v['width'], v['height'], 'yuv420p'
        aus = out.add_stream('aac', rate=RATE)
        with av.open(str(raw)) as src:
            for index, frame in enumerate(src.decode(video=0)):
                frame.pts, frame.time_base = index, Fraction(1, FPS)
                for packet in vs.encode(frame):
                    out.mux(packet)
            if missing:
                frame.pts, frame.time_base = target_frames - 1, Fraction(1, FPS)
                for packet in vs.encode(frame):
                    out.mux(packet)
        for packet in vs.encode(None):
            out.mux(packet)
        encode_audio(out, aus, data)
    return {'raw_frames': v['frames'], 'held_tail_frames': missing,
            'output_frames': target_frames, 'audio_alignment': alignment}


def run(args):
    dest = new_output(args.output, '.mp4')
    log_path = Path(str(dest) + '.log')
    if log_path.exists():
        raise FileExistsError(f'Use a new version path: {log_path}')
    root = Path(args.muse_root).resolve(strict=True)
    runtime = Path(args.muse_python).resolve(strict=True)
    video, audio = Path(args.video).resolve(strict=True), Path(args.audio).resolve(strict=True)
    source_meta, data, target_frames = validate_inputs(video, audio, args.replace_audio)
    for name in (*MODEL_FILES, 'scripts/inference.py'):
        p = root / name
        if not p.is_file() or not p.stat().st_size:
            raise FileNotFoundError(f'Missing local MuseTalk prerequisite: {p}')
    commit = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
    if commit != SOURCE_COMMIT:
        raise ValueError('MuseTalk source revision differs from tested adapter; review before use')
    if subprocess.run(['git', '-C', str(root), 'diff', '--quiet', 'HEAD', '--']).returncode:
        raise ValueError('MuseTalk tracked source was modified; review before use')
    check = "import sys,json,torch,numpy,transformers,mmcv,imageio_ffmpeg;print(json.dumps({'python':list(sys.version_info[:2]),'torch':torch.__version__,'numpy':numpy.__version__,'transformers':transformers.__version__,'mmcv':mmcv.__version__,'cuda':torch.cuda.is_available(),'ffmpeg':imageio_ffmpeg.get_ffmpeg_exe()}))"
    versions = json.loads(subprocess.check_output([str(runtime), '-c', check], text=True, timeout=60))
    if versions['python'] != [3, 10] or not versions['cuda'] or versions['torch'] != '2.0.1+cu118' or versions['numpy'] != '1.23.5' or versions['transformers'] != '4.39.2' or versions['mmcv'] != '2.0.1':
        raise ValueError('Isolated runtime differs from tested Windows CUDA baseline')
    env = os.environ.copy()
    env.update(PYTHONUTF8='1', HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1',
               PYTHONPATH=str(root) + os.pathsep + str(root / 'musetalk/utils'))
    started = time.monotonic()
    temp = temporary_for(dest)
    try:
        with tempfile.TemporaryDirectory(prefix='film_job_', dir=root) as folder:
            stage = Path(folder).resolve()
            if stage.parent != root:
                raise ValueError('Staging path is outside selected engine directory')
            relative = stage.name
            shutil.copyfile(video, stage / 'source.mp4')
            save_wav(stage / 'speech.wav', data)
            shutil.copyfile(versions.pop('ffmpeg'), stage / 'ffmpeg.exe')
            config = {'shot': {'video_path': f'{relative}/source.mp4',
                              'audio_path': f'{relative}/speech.wav', 'result_name': 'result.mp4'}}
            (stage / 'plan.json').write_text(json.dumps(config), encoding='utf-8')
            cmd = [str(runtime), '-m', 'scripts.inference', '--inference_config', f'{relative}/plan.json',
                   '--result_dir', f'{relative}/results', '--ffmpeg_path', relative,
                   '--unet_config', 'models/musetalkV15/musetalk.json',
                   '--unet_model_path', 'models/musetalkV15/unet.pth', '--batch_size', '4',
                   '--fps', '24', '--use_float16']
            with log_path.open('x', encoding='utf-8') as log:
                proc = subprocess.run(cmd, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT, timeout=600)
            raw = stage / 'results/v15/result.mp4'
            # Official script catches per-shot exceptions, so exit 0 alone is insufficient.
            if proc.returncode or not raw.is_file() or 'Error occurred during processing:' in log_path.read_text(encoding='utf-8'):
                raise RuntimeError(f'MuseTalk failed; inspect {log_path}')
            normalized = normalize_result(raw, temp, data, target_frames)
        actual = inspect_media(temp)
        if actual['video']['frames'] != target_frames or actual['video']['width'] != source_meta['video']['width'] or actual['video']['height'] != source_meta['video']['height']:
            raise ValueError('Output violated frame count or dimension contract')
        manifest = {'schema_version': 1, 'tool': 'film_lipsync', 'task': 'musetalk_v15',
                    'inputs': [file_record(video), file_record(audio)],
                    'engine': {'root': str(root), 'source_commit': commit, 'runtime': versions,
                               'files': [file_record(root / n) for n in (*MODEL_FILES, 'scripts/inference.py')]},
                    'parameters': {'fps': FPS, 'batch_size': 4, 'precision': 'float16',
                                   'source_audio_replaced': 'audio' in source_meta,
                                   'source_motion_policy': 'speech-length prefix, no looping',
                                   'normalization': normalized, 'elapsed_seconds': time.monotonic() - started},
                    'actual': actual, 'technical_status': 'pass', 'content_status': 'candidate',
                    'output': file_record(temp), 'log': file_record(log_path)}
        manifest['output']['path'] = str(dest)
        sidecar = Path(str(dest) + '.json')
        if dest.exists() or sidecar.exists():
            raise FileExistsError(str(dest))
        side_temp = temporary_for(sidecar)
        try:
            side_temp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
            os.replace(temp, dest)
            os.replace(side_temp, sidecar)
        finally:
            side_temp.unlink(missing_ok=True)
        return manifest
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('muse-root', 'muse-python', 'video', 'audio', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--replace-audio', action='store_true')
    args = parser.parse_args()
    try:
        print(json.dumps(run(args), ensure_ascii=False, indent=2))
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError, av.FFmpegError) as exc:
        parser.exit(2, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
