"""Dependency-free shared version pins and file provenance."""
import hashlib
from pathlib import Path

SOURCE_COMMIT = 'a12c5b19dcac9ae8b47e592da39c9711c8f8c756'
# ComfyUI class names and socket type (D9). Old class names were removed in
# phase 8.2; the only remaining spelling is the migration note.
LOAD_NODE = 'GameArtLoadFaceSwapVideo'
REACTOR_NODE = 'GameArtReActorVideo'
SOURCE_TYPE = 'GAMEART_FACE_SWAP_SOURCE'
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
