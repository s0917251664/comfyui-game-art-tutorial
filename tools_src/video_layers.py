"""Thin client for the fixed ComfyUI server-side video layer workflow."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import uuid
from urllib.parse import urlparse
import generate
from comfyui_video_layers.contracts import PACKAGE_FILES, model_path, record, runtime


def preflight(config_path, operation):
    config = json.loads(Path(config_path).read_text(encoding='utf-8-sig'))
    root = Path(config['comfyui_path']).resolve(strict=True)
    url = config['comfyui_url'].rstrip('/')
    parsed = urlparse(url)
    if parsed.scheme != 'http' or parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
        raise ValueError('Require loopback ComfyUI URL')
    versions = runtime()
    hashes = {}
    for n in PACKAGE_FILES:
        local = record(Path(__file__).parent / 'comfyui_video_layers' / n)
        for target in (root / 'tools/comfyui_video_layers' / n, root / 'custom_nodes/comfyui-video-layers' / n):
            if record(target)['sha256'] != local['sha256']:
                raise ValueError(f'Package deployment mismatch: {target}')
        hashes[n] = local['sha256']
    dependencies = []
    for relative in ('comfyui_face_swap_video/media.py', 'comfyui_face_swap_video/contracts.py'):
        source = Path(__file__).parent / relative
        target = root / 'tools' / relative
        if record(source)['sha256'] != record(target)['sha256']:
            raise ValueError('Shared media dependency deployment mismatch')
        dependencies.append(record(target))
    models = []
    if operation == 'segment':
        model = model_path()
        models = [record(model / n) for n in ('config.json', 'model.safetensors', 'preprocessor_config.json')]
    schema = generate._fetch_comfy_object_info(url)
    spec = schema.get('SteveVideoLayers', {})
    fields = spec.get('input', {}).get('required', {})
    if set(fields) != {'plan_path', 'package_hashes', 'output_prefix'} or any(fields[k][0] != 'STRING' for k in fields):
        raise ValueError('Live SteveVideoLayers node absent or incompatible; deploy/restart before queue')
    return url, {'runtime': versions, 'package_hashes': hashes, 'shared_media': dependencies,
                 'models': models, 'processing_location': 'ComfyUI server',
                 'schema_fingerprint': hashlib.sha256(json.dumps(spec, sort_keys=True).encode()).hexdigest()}


def run(args):
    plan_path = Path(args.plan).resolve(strict=True)
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    if plan.get('operation') not in ('segment', 'compose') or plan.get('schema_version') != 1:
        raise ValueError('Invalid plan operation/schema')
    fields = [plan.get('video')]
    if plan['operation'] == 'compose':
        fields.append(plan.get('background'))
        for layer in plan.get('layers', []):
            fields.extend(layer[k] for k in ('image', 'segmentation', 'occlusion_mask') if k in layer)
    else:
        for obj in plan.get('objects', []):
            fields.extend(p['mask'] for p in obj.get('prompts', []) if 'mask' in p)
    for value in fields:
        if not isinstance(value, str) or not Path(value).is_absolute() or not Path(value).is_file():
            raise ValueError(f'Missing/nonabsolute input; refusing queue: {value}')
    url, provenance = preflight(args.config, plan['operation'])
    # No upload: local source inputs remain on this machine.
    if args.command == 'preflight':
        return provenance
    dest = Path(args.output_dir).resolve()
    if dest.exists():
        raise FileExistsError('Use a new output directory')
    graph = {'1': {'class_type': 'SteveVideoLayers', 'inputs': {
        'plan_path': str(plan_path), 'package_hashes': json.dumps(provenance['package_hashes']),
        'output_prefix': 'video_layers/' + uuid.uuid4().hex}}}
    dest.parent.mkdir(parents=True, exist_ok=True)
    # Python 3.13 Windows mkdtemp uses a private DACL (mode 0700). Renaming
    # that directory retains the ACL and can make artifacts unreadable to
    # the desktop user after a sandboxed run. Inherit the output parent's ACL.
    stage = dest.parent / ('.' + dest.name + '-' + uuid.uuid4().hex)
    stage.mkdir()
    try:
        (stage / 'workflow_api.json').write_text(json.dumps(graph, indent=2), encoding='utf-8')
        history = generate.submit_and_wait(graph, comfy_url=url, timeout=args.timeout)
        (stage / 'history.json').write_text(json.dumps(history, indent=2), encoding='utf-8')
        downloadable = dict(history)
        downloadable['outputs'] = dict(history['outputs'])
        output = dict(history['outputs']['1'])
        output['images'] = output.get('images', []) + output.get('files', [])
        downloadable['outputs']['1'] = output
        paths = generate.download_outputs(downloadable, output_dir=str(stage), node_ids=['1'], comfy_url=url, allow_overwrite=False)
        required = {'candidate.mp4', 'manifest.json', 'layers.zip', 'source.jpg', 'comparison.jpg'}
        if {Path(p).name for p in paths} != required:
            raise ValueError('Server artifact contract failed')
        manifest = json.loads((stage / 'manifest.json').read_text(encoding='utf-8'))
        if manifest['processing_location'] != 'ComfyUI server' or record(stage / 'candidate.mp4')['sha256'] != manifest['output']['sha256']:
            raise ValueError('Server provenance/download hash mismatch')
        (stage / 'receipt.json').write_text(json.dumps({'preflight': provenance, 'prompt_id': history['_prompt_id'],
           'server_manifest': history['outputs']['1']['text'], 'client': record(__file__)}, indent=2), encoding='utf-8')
        if dest.exists():
            raise FileExistsError(str(dest))
        os.rename(stage, dest)
        return {'output_dir': str(dest), 'actual': manifest['actual'], 'technical_status': manifest['technical_status'],
                'content_status': manifest['content_status'], 'server': history['outputs']['1']['text']}
    finally:
        if stage.exists():
            shutil.rmtree(stage)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=('preflight', 'run'))
    p.add_argument('--config', required=True)
    p.add_argument('--plan', required=True)
    p.add_argument('--output-dir')
    p.add_argument('--timeout', type=int, default=600, choices=range(1, 3601), metavar='1..3600')
    args = p.parse_args()
    if args.command == 'run' and not args.output_dir:
        p.error('run requires --output-dir')
    print(json.dumps(run(args), ensure_ascii=False, indent=2))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, RuntimeError) as exc:
        print(f'video_layers: {exc}', file=sys.stderr)
        sys.exit(1)
