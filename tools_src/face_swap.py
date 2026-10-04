"""Fixed ComfyUI ReActor graph orchestration; all model inference stays in ComfyUI.

Preserves the source canvas and CFR, re-encodes one audio track as AAC, and
publishes a new candidate directory only after full decoding validation.
The CLI only prepares frames, queues a fixed graph and handles media/results.
No model loading, downloads, temporal tracking or hair editing in this client.
"""
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
import generate

SOURCE_COMMIT = 'a12c5b19dcac9ae8b47e592da39c9711c8f8c756'
# Checked on disk for provenance; the client never imports this model code.
CORE_HASHES = {
    'inswap.py': '9f5457b96ce0863b24cdfd818807c7178b9ca2eebc520872d001e2ca105eabe3',
    'face_objects.py': '9604bab5ee9bebaab3cb9923a4b3e55a23021181baa798ea44412c2619590b25',
    'meanshape_68.py': 'ec26c48ab8ecf44d9bca3bf25f2ba0702be7a0209f0cdc687b49d7e40581436a',
}
MODEL_HASHES = {
    'inswapper_128.onnx': 'e4a3f08c753cb72d04e10aa0f7dbe3deebbf39567d4ead6dce08e98aa49e16af',
    'buffalo_l/det_10g.onnx': '5838f7fe053675b1c7a08b633df49e7af5495cee0493c7dcf6697200b85b5b91',
    'buffalo_l/w600k_r50.onnx': '4c06341c33c2ca1f86781dab0e829f88ad5b64be9fba56e56bc9ebdefc619e43',
}
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


def record(path):
    path = Path(path).resolve(strict=True)
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return {'path': str(path), 'sha256': h.hexdigest(), 'bytes': path.stat().st_size}


def checked(root, relative, expected):
    info = record(Path(root) / relative)
    if info['sha256'] != expected:
        raise ValueError(f'Pinned file hash mismatch: {info["path"]}')
    return info


REQUIRED_NODES = ('LoadImage','ImageBatch','ReActorFaceSwap','SaveImage','CreateVideo','SaveVideo')


def build_graph(filenames, source_filename, fps, prefix, face_index=0):
    if not 1 <= len(filenames) <= 8 or not 0 <= face_index <= 7:
        raise ValueError('Graph supports 1–8 frames and face index 0–7')
    graph = {'1': {'class_type':'LoadImage','inputs':{'image':source_filename}}}
    previous = None
    for i, filename in enumerate(filenames):
        node = str(10+i*2)
        graph[node]={'class_type':'LoadImage','inputs':{'image':filename}}
        current=[node,0]
        if previous:
            batch=str(11+i*2)
            graph[batch]={'class_type':'ImageBatch','inputs':{'image1':previous,'image2':current}}
            current=[batch,0]
        previous=current
    graph['100']={'class_type':'ReActorFaceSwap','inputs':{
        'enabled':True, 'input_image':previous, 'source_image':['1',0],
        'swap_model':'inswapper_128.onnx', 'facedetection':'retinaface_resnet50',
        'face_restore_model':'none', 'face_restore_visibility':1., 'codeformer_weight':.5,
        'detect_gender_input':'no', 'detect_gender_source':'no',
        'input_faces_index':str(face_index), 'source_faces_index':'0', 'console_log_level':1}}
    graph['200']={'class_type':'SaveImage','inputs':{'images':['100',0],'filename_prefix':prefix+'/frames'}}
    graph['201']={'class_type':'CreateVideo','inputs':{'images':['100',0],'fps':float(fps)}}
    graph['202']={'class_type':'SaveVideo','inputs':{'video':['201',0],
                  'filename_prefix':prefix+'/clip','format':'auto','codec':'auto'}}
    return graph


def preflight(config_path):
    path=Path(config_path).resolve(strict=True)
    config=json.loads(path.read_text(encoding='utf-8-sig'))
    url=config['comfyui_url'].rstrip('/')
    parsed=urlparse(url)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost','::1'):
        raise ValueError('This local tool requires a loopback ComfyUI URL')
    root=Path(config['comfyui_path'])
    if not root.is_absolute(): root=path.parent/root
    node_root=root/'custom_nodes/ComfyUI-ReActor'
    commit=subprocess.run(['git','-C',str(node_root),'rev-parse','HEAD'],check=True,
                          capture_output=True,text=True).stdout.strip()
    if commit!=SOURCE_COMMIT:
        raise ValueError('Unsupported ReActor commit; verify integration before updating')
    subprocess.run(['git','-C',str(node_root),'diff','--exit-code','HEAD','--'],
                   check=True,capture_output=True)
    core=[checked(node_root/'reactor_core',n,h) for n,h in CORE_HASHES.items()]
    models=[checked(root/'models/insightface',n.replace('buffalo_l/','models/buffalo_l/'),h)
            for n,h in MODEL_HASHES.items()]
    for name in ('2d106det.onnx','1k3d68.onnx','genderage.onnx'):
        models.append(record(root/'models/insightface/models/buffalo_l'/name))
    for name in ('config.json','model.safetensors','preprocessor_config.json'):
        models.append(record(root/'models/nsfw_detector/vit-base-nsfw-detector'/name))
    if not list((root/'models/facerestore_models').glob('*.onnx')):
        raise ValueError('ReActor requires a provisioned restorer to prevent automatic schema-time downloads')
    schema=generate._fetch_comfy_object_info(url)
    if any(n not in schema for n in REQUIRED_NODES):
        raise ValueError('Missing ComfyUI nodes: '+','.join(n for n in REQUIRED_NODES if n not in schema))
    fields=schema['ReActorFaceSwap']['input']['required']
    if 'inswapper_128.onnx' not in fields['swap_model'][0] or 'none' not in fields['face_restore_model'][0]:
        raise ValueError('Required ReActor model/options unavailable')
    template=build_graph(['input.png'],'source.png',24,'face_swap/preflight')
    for node in template.values():
        spec=schema[node['class_type']]['input']
        if set(spec.get('required',{}))-set(node['inputs']):
            raise ValueError('Node schema changed; required inputs missing')
    fingerprint=hashlib.sha256(json.dumps({n:schema[n] for n in REQUIRED_NODES},
                                         sort_keys=True).encode()).hexdigest()
    return url, {'backend':'comfyui_reactor','comfyui_url':url,'node_commit':commit,
                 'core_files':core,'models':models,'node_schema_fingerprint':fingerprint,
                 'inference_location':'ComfyUI server','model_provider':'See ComfyUI execution log; not asserted by client'}


class Client:
    def __init__(self,url,source,args):
        self.url,self.source,self.args=url,source,args
        self.source_filename=None
        self.jobs=[]

    def process(self,images,fps,directory):
        directory.mkdir()
        if self.source_filename is None:
            self.source_filename=generate.upload_image(self.source,comfy_url=self.url)
        tag=uuid.uuid4().hex
        filenames=[]
        for i,image in enumerate(images):
            path=directory/f'{tag}-{i:03d}.png'
            Image.fromarray(cv2.cvtColor(image,cv2.COLOR_BGR2RGB)).save(path)
            filenames.append(generate.upload_image(path,comfy_url=self.url))
        graph=build_graph(filenames,self.source_filename,fps,f'face_swap/{tag}',self.args.face_index)
        (directory/'workflow_api.json').write_text(json.dumps(graph,indent=2),encoding='utf-8')
        history=generate.submit_and_wait(graph,comfy_url=self.url,timeout=self.args.timeout)
        (directory/'history.json').write_text(json.dumps(history,ensure_ascii=False,indent=2),encoding='utf-8')
        paths=generate.download_outputs(history,output_dir=str(directory/'frames'),node_ids=['200'],comfy_url=self.url)
        if len(paths)!=len(images):
            raise ValueError('ComfyUI changed frame count; rejecting filtered/partial batch')
        videos=generate.download_outputs(history,output_dir=str(directory/'comfy-video'),node_ids=['202'],comfy_url=self.url)
        if len(videos)!=1 or inspect_video(videos[0])['frames']!=len(images):
            raise ValueError('ComfyUI SaveVideo output failed frame-count validation')
        result=[]
        for path, original in zip(paths,images):
            with Image.open(path) as im:
                image=cv2.cvtColor(np.array(im.convert('RGB')),cv2.COLOR_RGB2BGR)
            if image.shape!=original.shape:
                raise ValueError('ComfyUI changed canvas size')
            result.append(image)
        self.jobs.append({'prompt_id':history['_prompt_id'],'frames':len(images),
                          'graph':str(directory.name+'/workflow_api.json')})
        return result


def processed_frames(video,meta,start,end,ranges,client,staging,args):
    pending=[]
    batch=0
    def flush():
        nonlocal batch
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
        manifest = {'schema_version': 1, 'tool': 'face_swap', 'backend': 'comfyui_reactor',
                    'content_status': 'candidate', 'technical_status': 'warning' if warnings else 'pass',
                    'warnings': warnings, 'inputs': [record(p) for p in (video, source)],
                    'runtime': provenance, 'parameters': vars(args), 'source': meta, 'actual': actual,
                    'audio': audio_details, 'counts': counts, 'elapsed_seconds': time.monotonic()-started,
                    'output': record(output), 'tool_source': record(__file__),
                    'comfyui_jobs':client.jobs,
                    'observation':'Changed pixels are a technical difference, not proof of face detection or quality'}
        manifest['output']['path'] = str(dest/'candidate.mp4')
        (staging/'candidate.mp4.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
        if dest.exists(): raise FileExistsError(str(dest))
        os.rename(staging, dest)
        return manifest
    finally:
        # Only remove the uniquely created staging directory, never user paths.
        if staging.exists(): shutil.rmtree(staging)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('preflight', 'swap'))
    p.add_argument('--config', required=True)
    p.add_argument('--video'); p.add_argument('--source-image')
    p.add_argument('--output-dir')
    p.add_argument('--start', type=float, default=0)
    p.add_argument('--end', type=float)
    p.add_argument('--edit-range', type=parse_range, action='append', default=[])
    p.add_argument('--face-index', type=int, default=0, help='Per-frame large-to-small face index; no identity tracking')
    p.add_argument('--batch-size', type=int, default=4)
    p.add_argument('--timeout', type=float, default=600)
    p.add_argument('--on-unchanged', choices=('error','preserve'), default='error')
    p.add_argument('--audio', choices=('preserve','drop'), default='preserve')
    args = p.parse_args()
    if not math.isfinite(args.timeout) or not 1<=args.timeout<=3600:
        p.error('Timeout must be 1–3600 seconds')
    if args.command == 'swap' and not all((args.video,args.source_image,args.output_dir)):
        p.error('swap requires --video, --source-image, --output-dir')
    url, provenance = preflight(args.config)
    result = provenance if args.command == 'preflight' else render(
        args,Client(url,args.source_image,args),provenance)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'face_swap: {exc}', file=sys.stderr)
        sys.exit(1)
