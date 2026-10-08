"""Offline runtime contract shared by the thin client and server."""
import hashlib
import importlib.metadata
from pathlib import Path

MODEL_ID = 'facebook/sam2.1-hiera-small'
MODEL_REVISION = 'ee5bba1d82bb8749febdf90f45e84b687142ba03'
PINS = {'av': '18.1.0', 'opencv-python': '5.0.0.93',
        'torch': '2.13.0+cu130', 'transformers': '5.15.0'}
PACKAGE_FILES = ('__init__.py', 'contracts.py', 'media.py', 'nodes.py')
# ComfyUI class name (D9). The legacy name stays registered as a hidden,
# deprecated alias so saved workflows keep loading; removal is phase 8.
NODE_NAME = 'GameArtVideoLayers'
LEGACY_NODE_NAMES = {NODE_NAME: 'SteveVideoLayers'}
MODEL_HASHES = {
    'config.json': '97ff9f65b76d107acda4247885f0a5555d0048850ae3c5f97183df289aaecde9',
    'model.safetensors': '0a4067b11ce1e23d5229203f11c718a823060d15a4b23fa2372a7d4b77cbbc60',
    'preprocessor_config.json': '6ebf229ee259368ce4a8d4f2fe893a72b053023710853e257253939e601f583d'}


def record(path):
    p = Path(path).resolve(strict=True)
    digest = hashlib.sha256()
    with p.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            digest.update(block)
    return {'path': str(p), 'sha256': digest.hexdigest(), 'bytes': p.stat().st_size}


def runtime():
    versions = {name: importlib.metadata.version(name) for name in PINS}
    if versions != PINS:
        raise ValueError(f'Runtime changed; revalidate before queue: {versions}')
    return versions


def model_path():
    from huggingface_hub import snapshot_download
    p = Path(snapshot_download(MODEL_ID, revision=MODEL_REVISION, local_files_only=True))
    for name in ('config.json', 'model.safetensors', 'preprocessor_config.json'):
        if not (p / name).is_file():
            raise ValueError(f'Offline SAM model file missing: {name}')
        if record(p / name)['sha256'] != MODEL_HASHES[name]:
            raise ValueError(f'Offline SAM model pin mismatch: {name}')
    return p
