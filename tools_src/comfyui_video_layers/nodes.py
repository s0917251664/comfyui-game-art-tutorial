"""One maintained server graph node; client performs no media processing."""
import json
from pathlib import Path
import sys
import folder_paths
import comfy.model_management as management

# Reuse the deployed, already tested CFR/audio primitives, not ReActor itself.
sys.path.insert(0, str(Path(folder_paths.base_path) / 'tools'))
from . import media
from .contracts import LEGACY_NODE_NAMES, NODE_NAME, PACKAGE_FILES, record
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


def legacy_alias(cls, name):
    """Same node under its old class name. DEPRECATED hides it from the node
    search/library (ComfyUI reports `deprecated: true`); old workflows still run."""
    return type(name, (cls,), {'DEPRECATED': True, '__module__': cls.__module__})


NODE_CLASS_MAPPINGS = {NODE_NAME: GameArtVideoLayers}
NODE_DISPLAY_NAME_MAPPINGS = {NODE_NAME: 'GameArt · SAM Video Masks / Ordered Layers'}
for _new, _old in LEGACY_NODE_NAMES.items():
    NODE_CLASS_MAPPINGS[_old] = legacy_alias(NODE_CLASS_MAPPINGS[_new], _old)
    NODE_DISPLAY_NAME_MAPPINGS[_old] = 'SAM Video Masks / Ordered Layers (legacy node name)'
