"""One maintained server graph node; client performs no media processing."""
import json
from pathlib import Path
import sys
import folder_paths
import comfy.model_management as management

# Reuse the CFR/audio primitives in source_media.py.
sys.path.insert(0, str(Path(folder_paths.base_path) / 'tools'))
from . import media
from .contracts import NODE_NAME, PACKAGE_FILES, record
LOADED_HASHES = {n: record(Path(__file__).parent / n)['sha256'] for n in PACKAGE_FILES}


class GameArtVideoLayers:
    @classmethod
    def INPUT_TYPES(cls):
        return {'required': {'plan_path': ('STRING', {'default': ''}),
                             'package_hashes': ('STRING', {'default': '{}'}),
                             'output_prefix': ('STRING', {'default': 'video_layers/candidate-v1'})}}
    RETURN_TYPES = ()
    OUTPUT_NODE = True
    FUNCTION = 'execute'
    CATEGORY = 'GameArt/Video'

    @classmethod
    def IS_CHANGED(cls, **kwargs):
        return float('nan')

    def execute(self, plan_path, package_hashes, output_prefix):
        expected = json.loads(package_hashes)
        actual = {n: record(Path(__file__).parent / n)['sha256'] for n in PACKAGE_FILES}
        if expected != actual or expected != LOADED_HASHES:
            raise ValueError('Loaded server package differs from preflight; restart/redeploy')
        prefix = Path(output_prefix)
        root = Path(folder_paths.get_output_directory()).resolve()
        dest = (root / prefix).resolve()
        if prefix.is_absolute() or '..' in prefix.parts or dest == root or not dest.is_relative_to(root):
            raise ValueError('Output prefix must remain below ComfyUI output')
        manifest = media.execute(plan_path, dest, management.throw_exception_if_processing_interrupted)
        subfolder = dest.relative_to(root).as_posix()
        def item(name):
            return {'filename': name, 'subfolder': subfolder, 'type': 'output'}
        return {'ui': {'images': [item('candidate.mp4')], 'animated': (True,),
                       'files': [item(n) for n in ('manifest.json', 'layers.zip', 'source.jpg', 'comparison.jpg')],
                       'text': [json.dumps({'actual': manifest['actual'], 'technical_status': manifest['technical_status'], 'server_manifest': str(dest / 'manifest.json')})]}}


NODE_CLASS_MAPPINGS = {NODE_NAME: GameArtVideoLayers}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: 'GameArt · SAM Video Masks / Ordered Layers'}
