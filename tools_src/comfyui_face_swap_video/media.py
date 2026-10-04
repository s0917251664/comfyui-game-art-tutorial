"""Server-only video decoding, bounded streaming, encoding and verification."""
from __future__ import annotations

import argparse
from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import subprocess
import uuid
from urllib.parse import urlparse

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw

from .contracts import record
RATE = 48000

def encode_audio(out, stream, data):
    for offset in range(0, data.shape[1], 1024):
        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(data[:, offset:offset+1024]),
                                          format='fltp', layout='stereo')
        frame.sample_rate = RATE
        frame.pts, frame.time_base = offset, Fraction(1, RATE)
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)


def processed_frames(video,meta,start,end,ranges,client,staging,args):
    pending=[]
    batch=0
    def flush():
        nonlocal batch
        client.check_cancelled() if hasattr(client, "check_cancelled") else None
        originals=[p[1] for p in pending]
        candidates=client.process(originals,Fraction(meta['fps']),staging/f'batch-{batch:04d}')
        batch+=1
        if len(candidates)!=len(originals): raise ValueError('Batch frame count mismatch')
        result=[]
        for (t,original),candidate in zip(pending,candidates):
            if candidate.shape!=original.shape or candidate.dtype!=np.uint8:
                raise ValueError('Invalid ComfyUI output canvas/type')
            changed=int(np.count_nonzero(np.max(np.abs(candidate.astype(np.int16)-original.astype(np.int16)),axis=2)>2))
            status='changed' if changed else 'unchanged'
            if not changed and args.on_unchanged=='error':
                raise ValueError(f'Unchanged selected frame at {t:.3f}s; inspect detection/content')
            result.append((t,original,candidate,status,changed))
        pending.clear()
        return result
    with av.open(str(video)) as c:
        for frame_index,frame in enumerate(c.decode(video=0)):
            # Matroska timestamps may be rounded to milliseconds. After CFR
            # validation, use the frame grid for exact clip/range boundaries.
            t=frame_index/float(Fraction(meta['fps']))
            if t+1e-7<start: continue
            if t>=end-1e-7: break
            if hasattr(client, 'check_cancelled'): client.check_cancelled()
            image=frame.to_ndarray(format='bgr24')
            if any(a<=t<b for a,b in ranges):
                pending.append((t,image))
                if len(pending)>=args.batch_size: yield from flush()
            else:
                if pending: yield from flush()
                yield t,image,image,'outside_edit_ranges',0
        if pending: yield from flush()


def inspect_video(path):
    with av.open(str(path)) as c:
        if len(c.streams.video) != 1 or len(c.streams.audio) > 1:
            raise ValueError('Exactly one video and at most one audio stream required')
        s = c.streams.video[0]
        fps = s.average_rate
        if fps is None or not 1 <= float(fps) <= 60:
            raise ValueError('Source FPS must be known and between 1 and 60')
        if max(s.width, s.height) > 1920 or s.width % 2 or s.height % 2:
            raise ValueError('Even source dimensions and longest side <=1920 required')
        tolerance = max(1e-5, float(s.time_base) * 1.1)
        first = last = None
        count = 0
        for frame in c.decode(video=0):
            if frame.pts is None:
                raise ValueError('Missing source video timestamp')
            t = float(frame.time)
            if last is not None and (t <= last or abs(t-last-1/float(fps)) > tolerance):
                raise ValueError('VFR / discontinuous timestamps unsupported')
            if first is None:
                first = t
            last = t
            count += 1
            if count / float(fps) > 60:
                raise ValueError('Source exceeds 60 seconds; split into shots')
        if not count:
            raise ValueError('Empty source video')
        return {'width': s.width, 'height': s.height, 'fps': str(Fraction(fps)), 'frames': count,
                'duration': count / float(fps), 'first_time': first,
                'audio_streams': len(c.streams.audio),
                'timestamp_tolerance': tolerance}


def parse_range(value):
    try:
        start, end = map(float, value.split(':'))
    except (ValueError, TypeError):
        raise argparse.ArgumentTypeError('Range requires START:END seconds')
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= 60:
        raise argparse.ArgumentTypeError('Range must satisfy 0 <= START < END <= 60')
    return start, end


def audio_timeline(path, first_time, duration, start, count):
    """Place resampled audio using timestamps; retain original offset and gaps."""
    timeline = np.zeros((2, round(duration * RATE)), dtype=np.float32)
    resampler = av.AudioResampler(format='fltp', layout='stereo', rate=RATE)
    decoded = 0
    timestamps = []
    def place(frame):
        nonlocal decoded
        if frame.pts is None:
            raise ValueError('Audio requires timestamps')
        data = frame.to_ndarray()
        if not np.isfinite(data).all():
            raise ValueError('Nonfinite audio')
        offset = round((float(frame.time) - first_time) * RATE)
        if decoded + data.shape[1] > 61 * RATE or offset > 61 * RATE:
            raise ValueError('Audio exceeds bounded 61 second decode limit')
        timestamps.append(offset)
        lo, hi = max(0, offset), min(timeline.shape[1], offset + data.shape[1])
        if hi > lo:
            timeline[:, lo:hi] = data[:, lo-offset:hi-offset]
        decoded += data.shape[1]
    with av.open(str(path)) as c:
        for frame in c.decode(audio=0):
            for f in resampler.resample(frame):
                place(f)
        for f in resampler.resample(None):
            place(f)
    if not decoded:
        raise ValueError('Empty source audio')
    begin = round(start * RATE)
    data = timeline[:, begin:begin + count]
    if data.shape[1] < count:
        data = np.pad(data, ((0, 0), (0, count-data.shape[1])))
    return data, {'decoded_samples': decoded, 'first_offset_samples': timestamps[0],
                  'output_samples': count, 'sample_rate': RATE, 'channels': 2,
                  'policy': 'timestamp placement, clip to video interval, silence for gaps; AAC re-encode'}


def comparison(original, candidate, t, reason):
    pair = Image.new('RGB', (960, 300), '#222222')
    for j, array in enumerate((original, candidate)):
        im = Image.fromarray(cv2.cvtColor(array, cv2.COLOR_BGR2RGB))
        im.thumbnail((480, 270))
        pair.paste(im, (480*j, 25))
    ImageDraw.Draw(pair).text((8, 5), f'{t:.3f}s | SOURCE / CANDIDATE | {reason}', fill='white')
    return pair


def render(args, client, provenance):
    dest = Path(args.output_dir).resolve()
    if dest.exists():
        raise FileExistsError(f'Use a new output directory: {dest}')
    video = Path(args.video).resolve(strict=True)
    source = Path(args.source_image).resolve(strict=True)
    if any(p.is_relative_to(dest) for p in (video, source)):
        raise ValueError('Output directory must not contain input files')
    meta = inspect_video(video)
    fps = Fraction(meta['fps'])
    start = args.start
    end = args.end if args.end is not None else meta['duration']
    if not math.isfinite(start) or not math.isfinite(end) or not 0 <= start < end <= meta['duration'] + 1e-6:
        raise ValueError('Clip bounds must lie inside source duration')
    ranges = args.edit_range
    if not ranges or any(a < start or b > end+1e-6 for a, b in ranges):
        raise ValueError('Explicit edit ranges must lie inside clip bounds')
    for (a,b), (c,d) in zip(sorted(ranges), sorted(ranges)[1:]):
        if b > c:
            raise ValueError('Edit ranges must not overlap')
    with Image.open(source) as image:
        if max(image.size)>4096:
            raise ValueError('Reference longest side must be <=4096')
        image.verify()
    if not 1 <= args.batch_size <= 8 or not 0 <= args.face_index <= 7:
        raise ValueError('Batch size must be 1–8; face index 0–7')
    dest.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.'+dest.name+'-', dir=dest.parent))
    started = time.monotonic()
    try:
        output = staging/'candidate.mp4'
        records, previews = [], []
        with av.open(str(output), 'w') as out:
            vs = out.add_stream('libx264', rate=fps)
            vs.width, vs.height, vs.pix_fmt = meta['width'], meta['height'], 'yuv420p'
            vs.options = {'crf': '18', 'preset': 'fast'}
            aus = out.add_stream('aac', rate=RATE) if args.audio == 'preserve' and meta['audio_streams'] else None
            if aus is not None:
                aus.layout = 'stereo'
            for t, original, candidate, reason, changed in processed_frames(
                    video,meta,start,end,ranges,client,staging,args):
                    n = len(records)
                    if not records: actual_start = t
                    rec = {'frame': n, 'source_time': t, 'status': reason,'changed_pixels':changed}
                    records.append(rec)
                    if reason!='outside_edit_ranges' and len(previews)<12 and (not previews or t-previews[-1][0] >= .5):
                        previews.append((t, comparison(original, candidate, t, reason)))
                    vf = av.VideoFrame.from_ndarray(candidate, format='bgr24')
                    vf.pts, vf.time_base = n, 1/fps
                    for packet in vs.encode(vf): out.mux(packet)
                    if n % 120 == 0:
                        print(f'{t:.2f}s / {end:.2f}s, frames={n+1}', flush=True)
            for packet in vs.encode(None): out.mux(packet)
            if not records:
                raise ValueError('Clip contains no frames')
            audio_details = {'policy': args.audio, 'source_audio_streams': meta['audio_streams']}
            if aus is not None:
                data, audio_details = audio_timeline(video, meta['first_time'], meta['duration'],
                                                     actual_start, round(len(records)/float(fps)*RATE))
                encode_audio(out, aus, data)
        actual = inspect_video(output)
        if actual['frames'] != len(records) or actual['fps'] != str(fps) or any(
                actual[k] != meta[k] for k in ('width','height')):
            raise ValueError(f'Output video contract failed: expected {len(records)} frames at {fps}, '
                             f'{meta["width"]}x{meta["height"]}; actual={actual}')
        expected_audio = int(args.audio == 'preserve' and bool(meta['audio_streams']))
        if actual['audio_streams'] != expected_audio:
            raise ValueError('Output audio stream contract failed')
        if expected_audio:
            data, _ = audio_timeline(output, 0, actual['duration'], 0, round(actual['duration']*RATE))
            actual['audio_rms'] = float(np.sqrt(np.mean(data.astype(np.float64)**2)))
        counts = dict(Counter(r['status'] for r in records))
        if not counts.get('changed'):
            raise ValueError('No changed frames returned; candidate not published')
        sheet = Image.new('RGB',(960,300*len(previews)), '#222222')
        for i, (_, im) in enumerate(previews): sheet.paste(im, (0,300*i))
        sheet.save(staging/'comparison.jpg')
        (staging/'frames.json').write_text(json.dumps(records, indent=2), encoding='utf-8')
        warnings = [f'{k}: {v} selected frames preserved' for k,v in counts.items()
                    if k not in ('changed', 'outside_edit_ranges')]
        manifest = {'schema_version': 2, 'tool': 'face_swap', 'backend': 'comfyui_reactor_video_node',
                    'content_status': 'candidate', 'technical_status': 'warning' if warnings else 'pass',
                    'warnings': warnings, 'inputs': [record(p) for p in (video, source)],
                    'runtime': provenance, 'parameters': vars(args), 'source': meta, 'actual': actual,
                    'audio': audio_details, 'counts': counts, 'elapsed_seconds': time.monotonic()-started,
                    'output': record(output), 'tool_source': record(__file__),
                    'reactor_batches':client.jobs, 'processing_location':'ComfyUI server', 'server_pid':os.getpid(),
                    'observation':'Changed pixels are a technical difference, not proof of face detection or quality'}
        manifest['output']['path'] = str(dest/'candidate.mp4')
        (staging/'candidate.mp4.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        if dest.exists(): raise FileExistsError(str(dest))
        os.rename(staging, dest)
        return manifest
    finally:
        # Only remove the uniquely created staging directory, never user paths.
        if staging.exists(): shutil.rmtree(staging)
