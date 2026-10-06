"""Bounded server-only SAM mask propagation, affine tracking and layer render.

Masks are selected-white L PNG, not the inverted ComfyUI edit-alpha contract.
No semantic FX unmixing is claimed: over copies baked source RGB; screen is
an explicitly approximate brightness overlay and carries source contamination.
"""
from fractions import Fraction
import json
import math
import os
from pathlib import Path
import shutil
import time
import uuid
import zipfile

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw
import torch

from .contracts import MODEL_ID, MODEL_REVISION, PACKAGE_FILES, model_path, record, runtime


def local_file(value):
    p = Path(value)
    if not p.is_absolute() or not p.is_file():
        raise ValueError('Inputs must be existing absolute local files')
    return p.resolve()


def decode_clip(plan):
    from comfyui_face_swap_video.media import inspect_video
    path = local_file(plan['video'])
    meta = inspect_video(path)
    start, end = plan['start'], plan['end']
    if not all(isinstance(v, (float, int)) and math.isfinite(v) for v in (start, end)):
        raise ValueError('Finite clip bounds required')
    if not 0 <= start < end <= meta['duration'] or end - start > 5:
        raise ValueError('Clip must be within source and at most 5 seconds')
    fps = Fraction(meta['fps'])
    # Exact CFR grid, including millisecond-rounded Matroska timestamps.
    begin, finish = math.ceil(start * float(fps) - 1e-7), math.ceil(end * float(fps) - 1e-7)
    width = plan.get('width', 960)
    if isinstance(width, bool) or not isinstance(width, int) or not 256 <= width <= 1280 or width % 2:
        raise ValueError('Working width must be an even integer 256..1280')
    height = round(meta['height'] * width / meta['width'] / 2) * 2
    if max(width, height) > 1280 or finish - begin > 300 or (finish - begin) * width * height > 150_000_000:
        raise ValueError('Working longest side <=1280, <=300 frames')
    frames = []
    with av.open(str(path)) as c:
        for i, f in enumerate(c.decode(video=0)):
            if i < begin:
                continue
            if i >= finish:
                break
            frames.append(cv2.resize(f.to_ndarray(format='rgb24'), (width, height)))
    if len(frames) != finish - begin or not frames:
        raise ValueError('Source clip frame count mismatch')
    return frames, meta, begin / float(fps)


def encode(frames, destination, fps, audio_data=None):
    from comfyui_face_swap_video.media import encode_audio
    with av.open(str(destination), 'w') as c:
        stream = c.add_stream('libx264', rate=Fraction(fps))
        stream.width, stream.height = frames[0].shape[1], frames[0].shape[0]
        stream.pix_fmt = 'yuv420p'
        stream.options = {'crf': '18', 'preset': 'medium'}
        audio = c.add_stream('aac', rate=48000) if audio_data is not None else None
        if audio:
            audio.layout = 'stereo'
        for i, rgb in enumerate(frames):
            f = av.VideoFrame.from_ndarray(np.ascontiguousarray(rgb), format='rgb24')
            f.pts, f.time_base = i, 1 / Fraction(fps)
            for packet in stream.encode(f):
                c.mux(packet)
        for packet in stream.encode(None):
            c.mux(packet)
        if audio:
            encode_audio(c, audio, audio_data)
    with av.open(str(destination)) as c:
        saved_stream = c.streams.video[0]
        decoded = list(c.decode(video=0))
        if len(decoded) != len(frames) or any(f.width != stream.width or f.height != stream.height for f in decoded):
            raise ValueError('Output full decode failed')
        if saved_stream.average_rate != Fraction(fps) or saved_stream.codec_context.name != 'h264':
            raise ValueError('Output FPS/codec mismatch')
        if any(f.pts is None or abs(float(f.time) - i / float(Fraction(fps))) > 1e-5 for i, f in enumerate(decoded)):
            raise ValueError('Output timestamps do not match CFR frame grid')
    audio_samples = 0
    if audio_data is not None:
        with av.open(str(destination)) as c:
            audio_stream = c.streams.audio[0]
            if audio_stream.codec_context.name != 'aac' or audio_stream.rate != 48000 or len(audio_stream.layout.channels) != 2:
                raise ValueError('Output audio codec/rate/layout mismatch')
            for f in c.decode(audio=0):
                audio_samples += f.samples
        if abs(audio_samples - audio_data.shape[1]) > 2048:
            raise ValueError('Encoded audio duration mismatch')
    return {'frames': len(decoded), 'width': stream.width, 'height': stream.height,
            'fps': str(fps), 'duration': len(decoded) / float(Fraction(fps)),
            'video_codec': 'h264', 'audio_codec': 'aac' if audio_data is not None else None,
            'audio_decoded_samples': audio_samples, 'full_decode': 'pass'}


def sheet(images, labels, path):
    thumb_w, thumb_h = 360, 230
    out = Image.new('RGB', (thumb_w * 3, thumb_h * math.ceil(len(images) / 3)), '#222222')
    draw = ImageDraw.Draw(out)
    for i, array in enumerate(images):
        im = Image.fromarray(array)
        im.thumbnail((thumb_w, thumb_h - 24))
        x, y = i % 3 * thumb_w, i // 3 * thumb_h
        out.paste(im, (x, y + 24))
        draw.text((x + 4, y + 4), labels[i], fill='white')
    out.save(path, quality=92)


def validate_prompts(objects, n, size):
    if not isinstance(objects, list) or not 1 <= len(objects) <= 4:
        raise ValueError('Require 1..4 explicitly prompted objects')
    ids = [o['id'] for o in objects]
    if any(not isinstance(i, int) or isinstance(i, bool) or not 1 <= i <= 999 for i in ids) or len(set(ids)) != len(ids):
        raise ValueError('Object ids must be unique integers 1..999')
    for obj in objects:
        prompts = obj['prompts']
        if not prompts or prompts[0]['frame'] != 0:
            raise ValueError('Each object needs a frame-0 prompt')
        seen = set()
        for p in prompts:
            f = p['frame']
            if not isinstance(f, int) or isinstance(f, bool) or not 0 <= f < n or f in seen:
                raise ValueError('Prompt frames must be unique within clip')
            seen.add(f)
            if 'mask' in p:
                if any(k in p for k in ('box', 'points', 'labels')):
                    raise ValueError('Mask and point/box prompts cannot be mixed')
                with Image.open(local_file(p['mask'])) as im:
                    if im.mode != 'L' or im.size != size:
                        raise ValueError('Seed mask must be selected-white L PNG at working size')
            else:
                box = p.get('box')
                points, labels = p.get('points', []), p.get('labels', [])
                if not box and not points:
                    raise ValueError('Prompt needs box, points or selected-white mask')
                if box is not None:
                    if len(box) != 4 or not np.isfinite(box).all() or not 0 <= box[0] < box[2] <= size[0] or not 0 <= box[1] < box[3] <= size[1]:
                        raise ValueError('Invalid prompt box')
                if len(points) != len(labels) or any(v not in (0, 1) for v in labels):
                    raise ValueError('Points require matching 0/1 labels')
                if points:
                    coords = np.asarray(points)
                    if coords.shape != (len(points), 2) or not np.isfinite(coords).all() or np.any(coords < 0) or np.any(coords[:, 0] >= size[0]) or np.any(coords[:, 1] >= size[1]):
                        raise ValueError('Invalid prompt point coordinates')


def segment(plan, frames, stage, cancel):
    from transformers import Sam2VideoModel, Sam2VideoProcessor
    size = (frames[0].shape[1], frames[0].shape[0])
    validate_prompts(plan['objects'], len(frames), size)
    root = model_path()
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    model = Sam2VideoModel.from_pretrained(root, local_files_only=True, dtype=torch.float32).to(device).eval()
    processor = Sam2VideoProcessor.from_pretrained(root, local_files_only=True)
    session = processor.init_video_session(video=[Image.fromarray(f) for f in frames],
                inference_device=device, inference_state_device='cpu', video_storage_device='cpu', dtype=torch.float32)
    masks = {o['id']: {} for o in plan['objects']}
    overlays, stats, previous_masks = [], [], {}
    colors = np.array([[255, 70, 70], [70, 255, 70], [70, 70, 255], [255, 255, 70]])
    with torch.inference_mode():
        for i in range(len(frames)):
            cancel()
            prompted = []
            for obj in plan['objects']:
                for prompt in obj['prompts']:
                    if prompt['frame'] != i:
                        continue
                    kwargs = {}
                    if 'mask' in prompt:
                        with Image.open(prompt['mask']) as im:
                            kwargs['input_masks'] = np.asarray(im) > 127
                    else:
                        if 'box' in prompt:
                            kwargs['input_boxes'] = [[prompt['box']]]
                        if 'points' in prompt:
                            kwargs['input_points'] = [[prompt['points']]]
                            kwargs['input_labels'] = [[prompt['labels']]]
                    processor.add_inputs_to_inference_session(session, frame_idx=i, obj_ids=obj['id'], **kwargs)
                    prompted.append(obj['id'])
            # In pinned Transformers 5.15 the processor replaces this list on
            # each add call. Preloading future prompts loses their flags when
            # frame 0 consumes them. Inject just in time and retain all IDs.
            session.obj_with_new_inputs = prompted
            output = model(inference_session=session, frame_idx=i)
            post = processor.post_process_masks([output.pred_masks], original_sizes=[size[::-1]], binarize=True)[0]
            overlay = frames[i].copy()
            for j, oid in enumerate(session.obj_ids):
                mask = post[j].detach().cpu().numpy().squeeze().astype(np.uint8) * 255
                name = f'masks/object-{oid:03d}/{i:06d}.png'
                p = stage / name
                p.parent.mkdir(parents=True, exist_ok=True)
                Image.fromarray(mask).save(p)
                masks[oid][i] = name
                selected = mask > 127
                overlay[selected] = (overlay[selected] * .55 + colors[j] * .45).astype(np.uint8)
                previous = previous_masks.get(oid)
                union = np.logical_or(previous, selected).sum() if previous is not None else 0
                iou = float(np.logical_and(previous, selected).sum() / union) if union else None
                ys, xs = np.where(selected)
                box = [int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1] if len(xs) else None
                stats.append({'frame': i, 'object': oid, 'area': int(selected.sum()), 'empty': not bool(selected.any()),
                              'previous_iou': iou, 'bbox': box})
                previous_masks[oid] = selected
            overlays.append(overlay)
    if any(len(v) != len(frames) for v in masks.values()):
        raise ValueError('SAM did not return every frame/object')
    del model, session
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return overlays, {'objects': {str(k): [v[i] for i in range(len(frames))] for k, v in masks.items()},
                       'mask_stats': stats, 'model': MODEL_ID, 'revision': MODEL_REVISION,
                       'model_files': [record(root / n) for n in ('config.json', 'model.safetensors', 'preprocessor_config.json')],
                       'device': device, 'mask_contract': 'L PNG: white selected, black excluded; NOT inverted edit alpha'}


def affine(source, destination):
    a, b = np.asarray(source, np.float32), np.asarray(destination, np.float32)
    if a.shape != (3, 2) or b.shape != (3, 2) or not np.isfinite(a).all() or not np.isfinite(b).all():
        raise ValueError('Affine alignment requires three finite source/destination points')
    def area(p):
        return abs(float(np.linalg.det(np.column_stack((p, np.ones(3))))))
    if area(a) < 1 or area(b) < 1:
        raise ValueError('Anchor triangle is degenerate')
    return cv2.getAffineTransform(a, b)


def anchor_track(frames, anchors, cancel):
    """Sparse LK with forward/backward check. Reject loss; never silently freeze."""
    initial = np.asarray(anchors, np.float32)
    if initial.shape != (3, 2) or not np.isfinite(initial).all():
        raise ValueError('Tracking requires three finite anchors')
    height, width = frames[0].shape[:2]
    if np.any(initial < 0) or np.any(initial[:, 0] >= width) or np.any(initial[:, 1] >= height):
        raise ValueError('Tracking anchors outside working canvas')
    pts = initial.reshape(-1, 1, 2)
    tracks = [pts[:, 0].tolist()]
    previous = cv2.cvtColor(frames[0], cv2.COLOR_RGB2GRAY)
    for i, frame in enumerate(frames[1:], 1):
        cancel()
        gray = cv2.cvtColor(frame, cv2.COLOR_RGB2GRAY)
        nxt, status, _ = cv2.calcOpticalFlowPyrLK(previous, gray, pts, None, winSize=(31, 31), maxLevel=2)
        if nxt is None or not status.all():
            raise ValueError(f'Anchor tracking lost at frame {i}; provide explicit keyframes')
        # Seed the reverse search at the known previous location. OpenCV 5's
        # unseeded reverse search can diverge even on translated textured frames.
        back, valid, _ = cv2.calcOpticalFlowPyrLK(gray, previous, nxt, pts.copy(),
                         winSize=(31, 31), maxLevel=2, flags=cv2.OPTFLOW_USE_INITIAL_FLOW)
        if back is None or not valid.all() or np.max(np.linalg.norm(back - pts, axis=2)) > 2:
            raise ValueError(f'Anchor forward/backward check failed at frame {i}')
        if np.any(nxt < 0) or np.any(nxt[:, 0, 0] >= width) or np.any(nxt[:, 0, 1] >= height):
            raise ValueError(f'Anchor left canvas at frame {i}')
        affine(initial, nxt[:, 0])
        tracks.append(nxt[:, 0].tolist())
        previous, pts = gray, nxt
    return tracks


def keyframe_track(keys, n):
    if not isinstance(keys, list) or not keys or keys[0]['frame'] != 0 or keys[-1]['frame'] != n - 1:
        raise ValueError('Explicit anchors must include first and last frame')
    times = [k['frame'] for k in keys]
    if any(not isinstance(t, int) or isinstance(t, bool) for t in times) or any(a >= b for a, b in zip(times, times[1:])):
        raise ValueError('Anchor frames must be increasing integers')
    for k in keys:
        affine(k['points'], k['points'])
    points = np.array([k['points'] for k in keys])
    result = np.stack([np.interp(np.arange(n), times, points[:, j, d]) for j in range(3) for d in range(2)], axis=1)
    return result.reshape(n, 3, 2).tolist()


def blend(base, rgb, alpha, mode):
    a = alpha.astype(np.float32)[:, :, None] / 255
    if mode == 'over':
        result = rgb * a + base * (1 - a)
    elif mode == 'screen':
        screened = 255 - (255 - base.astype(np.float32)) * (255 - rgb.astype(np.float32)) / 255
        result = screened * a + base * (1 - a)
    else:
        raise ValueError('Only over or screen blend supported')
    return np.rint(result).clip(0, 255).astype(np.uint8)


def compose(plan, frames, stage, cancel):
    background = local_file(plan['background'])
    with Image.open(background) as im:
        canvas = np.asarray(im.convert('RGB'))
    height, width = canvas.shape[:2]
    if max(width, height) > 1280 or width % 2 or height % 2 or len(frames) * width * height > 150_000_000:
        raise ValueError('Background even dimensions, longest side <=1280 required')
    layers = plan['layers']
    if not isinstance(layers, list) or not 1 <= len(layers) <= 8:
        raise ValueError('Require 1..8 ordered layers')
    prepared, provenance = [], [record(background)]
    warning = []
    for layer in layers:
        kind = layer['kind']
        rgb_static = alpha_static = mask_paths = None
        if kind == 'source':
            manifest_path = local_file(layer['segmentation'])
            manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
            if manifest.get('operation') != 'segment' or manifest['source']['sha256'] != record(plan['video'])['sha256'] or manifest['actual']['frames'] != len(frames) or manifest['clip_start'] != plan['_clip_start'] or manifest['actual']['width'] != frames[0].shape[1] or manifest['actual']['height'] != frames[0].shape[0]:
                raise ValueError('Segmentation provenance/time/canvas mismatch')
            names = manifest['objects'][str(layer['object'])]
            if len(names) != len(frames):
                raise ValueError('Mask sequence length mismatch')
            mask_paths = [local_file(str(manifest_path.parent / p)) for p in names]
            for p in mask_paths:
                if not p.is_relative_to(manifest_path.parent):
                    raise ValueError('Mask artifact escapes segmentation directory')
                if record(p)['sha256'] != manifest['artifacts'][p.relative_to(manifest_path.parent).as_posix()]['sha256']:
                    raise ValueError('Mask changed after segmentation; rerun segmentation')
            provenance.append(record(manifest_path))
            warning.append('Source layer includes baked material/lighting/background within its mask; no independent VFX matte')
        elif kind == 'image':
            image = local_file(layer['image'])
            with Image.open(image) as im:
                if im.mode != 'RGBA' or max(im.size) > 4096:
                    raise ValueError('Image layer must be RGBA, longest side <=4096')
                arr = np.asarray(im)
            rgb_static, alpha_static = arr[:, :, :3], arr[:, :, 3]
            provenance.append(record(image))
        else:
            raise ValueError('Layer kind must be source or image')
        if ('track' in layer) == ('keyframes' in layer):
            raise ValueError('Choose exactly one of track or keyframes')
        tracks = anchor_track(frames, layer['track'], cancel) if 'track' in layer else keyframe_track(layer['keyframes'], len(frames))
        if kind == 'image' and 'track' in layer and 'destination' in layer:
            placement = affine(tracks[0], layer['destination'])
            tracks = [(np.column_stack((t, np.ones(3))) @ placement.T).tolist() for t in tracks]
        # Source anchors move with source; destination stays fixed on target.
        # Image anchors are fixed in the prop; destination moves with source.
        fixed = layer['destination'] if kind == 'source' else layer['image_points']
        matrices = [affine(t, fixed) if kind == 'source' else affine(fixed, t) for t in tracks]
        opacity = layer.get('opacity', 1)
        if not isinstance(opacity, (int, float)) or not math.isfinite(opacity) or not 0 <= opacity <= 1:
            raise ValueError('Opacity must be finite 0..1')
        mode = layer.get('blend', 'over')
        if mode not in ('over', 'screen'):
            raise ValueError('Unsupported blend')
        if mode == 'screen':
            warning.append('Screen is an approximate brightness overlay, not source FX extraction')
        occlusion = None
        if 'occlusion_mask' in layer:
            p = local_file(layer['occlusion_mask'])
            with Image.open(p) as im:
                if im.mode != 'L' or im.size != (width, height):
                    raise ValueError('Occlusion must be target-sized selected-white L PNG')
                occlusion = np.asarray(im)
            provenance.append(record(p))
        prepared.append((layer, rgb_static, alpha_static, mask_paths, matrices, occlusion))
    rendered, diagnostics = [], []
    png_root = stage / 'frames'
    png_root.mkdir()
    for i, source in enumerate(frames):
        cancel()
        base = canvas.copy()
        for index, (layer, rgb_static, alpha_static, mask_paths, matrices, occlusion) in enumerate(prepared):
            rgb = source if rgb_static is None else rgb_static
            if mask_paths:
                with Image.open(mask_paths[i]) as im:
                    if im.mode != 'L' or im.size != (source.shape[1], source.shape[0]):
                        raise ValueError('Invalid sequence mask')
                    alpha = np.asarray(im)
            else:
                alpha = alpha_static
            # Premultiplied warp prevents black/foreign RGB leaking at alpha edges.
            premult = rgb.astype(np.float32) * alpha[:, :, None] / 255
            a = cv2.warpAffine(alpha.astype(np.float32), matrices[i], (width, height))
            color = cv2.warpAffine(premult, matrices[i], (width, height))
            color = np.divide(color * 255, a[:, :, None], out=np.zeros_like(color), where=a[:, :, None] > 1e-5)
            a *= layer.get('opacity', 1)
            if occlusion is not None:
                a *= 1 - occlusion.astype(np.float32) / 255
            before = base.copy()
            base = blend(base, color, a, layer.get('blend', 'over'))
            diagnostics.append({'frame': i, 'layer': index, 'matrix': matrices[i].tolist(),
                                'selected_pixels': int(np.count_nonzero(a)),
                                'outside_mask_changed_pixels': int(np.count_nonzero(np.any(base[a == 0] != before[a == 0], axis=1)))})
        Image.fromarray(base).save(png_root / f'{i:06d}.png')
        rendered.append(base)
    return rendered, {'layers': layers, 'inputs': provenance, 'layer_stats': diagnostics,
                       'warnings': sorted(set(warning)), 'alignment': '2D affine; no 3D body, relighting or hidden-surface reconstruction'}


def execute(plan_path, destination, cancel):
    started = time.monotonic()
    path = local_file(plan_path)
    plan = json.loads(path.read_text(encoding='utf-8-sig'))
    if plan.get('schema_version') != 1 or plan.get('operation') not in ('segment', 'compose'):
        raise ValueError('Require schema_version=1 and segment/compose operation')
    versions = runtime()
    dest = Path(destination)
    if dest.exists():
        raise FileExistsError('Output exists; use a new prefix')
    frames, meta, start = decode_clip(plan)
    plan['_clip_start'] = start
    dest.parent.mkdir(parents=True, exist_ok=True)
    stage = dest.parent / ('.' + dest.name + '-' + uuid.uuid4().hex)
    stage.mkdir()  # Inherit parent ACL; Windows 0700 tempdirs retain a private DACL after rename.
    try:
        if plan['operation'] == 'segment':
            rendered, details = segment(plan, frames, stage, cancel)
        else:
            rendered, details = compose(plan, frames, stage, cancel)
        fps = Fraction(meta['fps'])
        audio_data = None
        audio_info = {'policy': 'drop'}
        if plan.get('audio', 'drop') not in ('preserve', 'drop'):
            raise ValueError('Audio policy must be preserve/drop')
        if plan.get('audio') == 'preserve' and meta['audio_streams']:
            from comfyui_face_swap_video.media import audio_timeline
            audio_data, audio_info = audio_timeline(plan['video'], meta['first_time'], meta['duration'], start, round(len(frames) / float(fps) * 48000))
        actual = encode(rendered, stage / 'candidate.mp4', fps, audio_data)
        indices = sorted(set(np.linspace(0, len(frames) - 1, 6).astype(int).tolist()))
        sheet([frames[i] for i in indices], [f'SOURCE {start + i / float(fps):.3f}s' for i in indices], stage / 'source.jpg')
        sheet([rendered[i] for i in indices], [f'CANDIDATE frame {i}' for i in indices], stage / 'comparison.jpg')
        (stage / 'plan.json').write_text(json.dumps(plan, indent=2), encoding='utf-8')
        artifacts = {p.relative_to(stage).as_posix(): {'sha256': record(p)['sha256'], 'bytes': p.stat().st_size} for p in stage.rglob('*.png')}
        manifest = {'schema_version': 1, 'operation': plan['operation'], 'processing_location': 'ComfyUI server',
                    'server_pid': os.getpid(), 'runtime': versions, 'source': record(plan['video']),
                    'server_package': [record(Path(__file__).parent / n) for n in PACKAGE_FILES],
                    'plan': record(path), 'clip_start': start, 'actual': actual, 'audio': audio_info,
                    'artifacts': artifacts, **details, 'content_status': 'candidate',
                    'technical_status': 'warning' if plan['operation'] == 'compose' or any(s['empty'] for s in details.get('mask_stats', [])) else 'pass',
                    'output': {**record(stage / 'candidate.mp4'), 'path': str(dest / 'candidate.mp4')},
                    'seconds': time.monotonic() - started}
        (stage / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        with zipfile.ZipFile(stage / 'layers.zip', 'w', compression=zipfile.ZIP_DEFLATED) as z:
            for p in stage.rglob('*.png'):
                z.write(p, p.relative_to(stage).as_posix())
        cancel()
        if dest.exists():
            raise FileExistsError(str(dest))
        os.rename(stage, dest)
        return manifest
    finally:
        if stage.exists():
            shutil.rmtree(stage)
