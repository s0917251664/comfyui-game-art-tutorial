"""Contract tests: identity, occlusion, tracking failure, provenance, media output."""
import json
import importlib.util
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import types
import cv2
import numpy as np
import torch
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools_src'))
from comfyui_video_layers import media
import video_layers


class VideoLayersTests(unittest.TestCase):
    def test_affine_maps_three_points(self):
        a = [[5, 8], [60, 9], [9, 65]]
        b = [[20, 25], [110, 20], [30, 90]]
        m = media.affine(a, b)
        np.testing.assert_allclose(np.column_stack((a, np.ones(3))) @ m.T, b, atol=1e-5)

    def test_degenerate_anchors_rejected(self):
        with self.assertRaisesRegex(ValueError, 'degenerate'):
            media.affine([[0, 0], [1, 1], [2, 2]], [[1, 0], [2, 1], [3, 2]])

    def test_nonfinite_anchors_rejected(self):
        with self.assertRaises(ValueError):
            media.affine([[0, 0], [1, 1], [np.nan, 2]], [[1, 0], [2, 1], [3, 2]])

    def test_alpha_zero_preserves_exact_base(self):
        rng = np.random.default_rng(42)
        base = rng.integers(0, 256, (16, 16, 3), dtype=np.uint8)
        rgb = rng.integers(0, 256, base.shape, dtype=np.uint8)
        for mode in ('over', 'screen'):
            np.testing.assert_array_equal(media.blend(base, rgb, np.zeros((16, 16)), mode), base)

    def test_alpha_full_copies_original_prop_pixels(self):
        base = np.zeros((8, 8, 3), np.uint8)
        prop = np.random.default_rng(4).integers(0, 256, base.shape, dtype=np.uint8)
        np.testing.assert_array_equal(media.blend(base, prop, np.full((8, 8), 255), 'over'), prop)

    def test_keyframes_interpolate_and_require_endpoints(self):
        p = [[3, 3], [20, 3], [3, 20]]
        q = [[7, 7], [24, 7], [7, 24]]
        tracks = media.keyframe_track([{'frame': 0, 'points': p}, {'frame': 4, 'points': q}], 5)
        np.testing.assert_array_equal(tracks[2], np.asarray(p) + 2)
        with self.assertRaises(ValueError):
            media.keyframe_track([{'frame': 0, 'points': p}], 5)

    def test_lk_known_translation(self):
        rng = np.random.default_rng(3)
        frame = cv2.GaussianBlur(rng.integers(0, 256, (256, 256, 3), dtype=np.uint8), (5, 5), 0)
        shifted = cv2.warpAffine(frame, np.array([[1., 0, 2], [0, 1, 3]]), (256, 256))
        anchors = [[80, 80], [160, 80], [80, 160]]
        track = media.anchor_track([frame, shifted], anchors, lambda: None)
        np.testing.assert_allclose(track[1], np.asarray(anchors) + [2, 3], atol=.15)

    def test_lk_lost_rejects_no_freeze(self):
        frame = np.zeros((100, 100, 3), np.uint8)
        with self.assertRaisesRegex(ValueError, 'lost'):
            media.anchor_track([frame, frame], [[20, 20], [50, 20], [20, 50]], lambda: None)

    def test_prompt_invalid_labels_and_boxes_rejected(self):
        for prompt in ({'frame': 0, 'box': [0, 0, 200, 100]},
                       {'frame': 0, 'points': [[20, 20]], 'labels': [2]},
                       {'frame': 1, 'box': [0, 0, 10, 10]}):
            with self.assertRaises(ValueError):
                media.validate_prompts([{'id': 1, 'prompts': [prompt]}], 4, (100, 100))

    def test_mask_contract_rejects_rgba_seed(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'mask.png'
            Image.new('RGBA', (100, 100)).save(p)
            with self.assertRaisesRegex(ValueError, 'selected-white'):
                media.validate_prompts([{'id': 1, 'prompts': [{'frame': 0, 'mask': str(p)}]}], 4, (100, 100))

    def test_order_and_occlusion_keep_background_bytes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            base = np.full((64, 64, 3), 37, np.uint8)
            Image.fromarray(base).save(root / 'bg.png')
            Image.new('RGBA', (64, 64), (200, 10, 20, 255)).save(root / 'prop.png')
            occlusion = np.zeros((64, 64), np.uint8)
            occlusion[:, :32] = 255
            Image.fromarray(occlusion).save(root / 'occlusion.png')
            points = [[0, 0], [63, 0], [0, 63]]
            plan = {'background': str(root / 'bg.png'), 'layers': [{'kind': 'image', 'image': str(root / 'prop.png'),
                    'image_points': points, 'keyframes': [{'frame': 0, 'points': points}, {'frame': 1, 'points': points}],
                    'occlusion_mask': str(root / 'occlusion.png')}]}
            frames, details = media.compose(plan, [base, base], root, lambda: None)
            np.testing.assert_array_equal(frames[0][:, :32], base[:, :32])
            np.testing.assert_array_equal(frames[0][:, 32:], np.broadcast_to([200, 10, 20], (64, 32, 3)))
            self.assertTrue(all(s['outside_mask_changed_pixels'] == 0 for s in details['layer_stats']))

    def test_source_mask_provenance_mismatch_rejects(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            Image.new('RGB', (64, 64)).save(root / 'bg.png')
            (root / 'manifest.json').write_text(json.dumps({'operation': 'segment', 'source': {'sha256': 'wrong'}}))
            plan = {'background': str(root / 'bg.png'), 'video': str(root / 'bg.png'), 'layers': [
                {'kind': 'source', 'segmentation': str(root / 'manifest.json'), 'object': 1}]}
            with self.assertRaisesRegex(ValueError, 'provenance'):
                media.compose(plan, [np.zeros((64, 64, 3), np.uint8)], root, lambda: None)

    def test_image_tracking_maps_source_motion_to_target_placement(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            Image.new('RGB', (64, 64)).save(root / 'bg.png')
            Image.new('RGBA', (4, 4), (200, 10, 20, 255)).save(root / 'prop.png')
            anchors = np.array([[80, 80], [160, 80], [80, 160]])
            plan = {'background': str(root / 'bg.png'), 'layers': [{'kind': 'image', 'image': str(root / 'prop.png'),
                    'image_points': [[0, 0], [4, 0], [0, 4]], 'track': anchors.tolist(),
                    'destination': [[4, 4], [20, 4], [4, 20]]}]}
            tracks = [anchors.tolist(), (anchors + [2, 3]).tolist()]
            with patch.object(media, 'anchor_track', return_value=tracks):
                _, result = media.compose(plan, [np.zeros((256, 256, 3), np.uint8)] * 2, root, lambda: None)
            matrices = [np.array(s['matrix']) for s in result['layer_stats']]
            np.testing.assert_allclose(matrices[0][:, 2], [4, 4])
            np.testing.assert_allclose(matrices[1][:, 2], [4.4, 4.6], atol=1e-5)

    def test_encode_audio_full_decode(self):
        with tempfile.TemporaryDirectory() as d:
            frames = [np.full((64, 64, 3), i * 20, np.uint8) for i in range(12)]
            info = media.encode(frames, Path(d) / 'test.mp4', '24', np.zeros((2, 24000), np.float32))
            self.assertEqual(info['frames'], 12)
            self.assertEqual(info['full_decode'], 'pass')
            self.assertLess(abs(info['audio_decoded_samples'] - 24000), 2049)

    def test_preflight_remote_url_stops_queue(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config.json'
            p.write_text(json.dumps({'comfyui_path': str(ROOT), 'comfyui_url': 'https://example.com'}))
            with patch.object(video_layers.generate, 'submit_and_wait') as submit:
                with self.assertRaisesRegex(ValueError, 'loopback'):
                    video_layers.preflight(p, 'compose')
                submit.assert_not_called()

    def test_preflight_missing_node_schema_stops_queue(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / 'config.json'
            p.write_text(json.dumps({'comfyui_path': d, 'comfyui_url': 'http://127.0.0.1:8188'}))
            with patch.object(video_layers, 'runtime', return_value={}), \
                 patch.object(video_layers, 'record', return_value={'sha256': 'same'}), \
                 patch.object(video_layers.generate, '_fetch_comfy_object_info', return_value={}), \
                 patch.object(video_layers.generate, 'submit_and_wait') as submit:
                with self.assertRaisesRegex(ValueError, 'absent or incompatible'):
                    video_layers.preflight(p, 'compose')
                submit.assert_not_called()

    def test_sam_keyframe_injected_when_reached_and_all_ids_retained(self):
        # Pinned processor replaces obj_with_new_inputs on every add call.
        # The regression used to consume all future prompt flags at frame 0.
        import transformers
        class Processor:
            def init_video_session(self, **kwargs):
                return SimpleNamespace(obj_ids=[], obj_with_new_inputs=[])
            def add_inputs_to_inference_session(self, session, frame_idx, obj_ids, **kwargs):
                if obj_ids not in session.obj_ids:
                    session.obj_ids.append(obj_ids)
                session.obj_with_new_inputs = [obj_ids]
            def post_process_masks(self, masks, **kwargs):
                return masks
        class Model:
            def to(self, device): return self
            def eval(self): return self
            def __call__(self, inference_session, frame_idx):
                expected = {0: [1, 2], 1: [1], 2: [2]}
                self_test.assertEqual(inference_session.obj_with_new_inputs, expected[frame_idx])
                inference_session.obj_with_new_inputs = []
                return SimpleNamespace(pred_masks=torch.ones((2, 1, 64, 64), dtype=torch.bool))
        self_test = self
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            for name in ('config.json', 'model.safetensors', 'preprocessor_config.json'):
                (root / name).write_bytes(b'test')
            objects = [{'id': 1, 'prompts': [{'frame': f, 'box': [0, 0, 60, 60]} for f in (0, 1)]},
                       {'id': 2, 'prompts': [{'frame': f, 'box': [0, 0, 60, 60]} for f in (0, 2)]}]
            with patch.object(media, 'model_path', return_value=root), \
                 patch.object(torch.cuda, 'is_available', return_value=False), \
                 patch.object(transformers.Sam2VideoModel, 'from_pretrained', return_value=Model()), \
                 patch.object(transformers.Sam2VideoProcessor, 'from_pretrained', return_value=Processor()):
                frames = [np.zeros((64, 64, 3), np.uint8)] * 3
                _, details = media.segment({'objects': objects}, frames, root, lambda: None)
                self.assertEqual(len(details['mask_stats']), 6)


class VideoLayerNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder = types.ModuleType('folder_paths')
        folder.base_path = str(ROOT)
        folder.get_output_directory = lambda: str(ROOT / 'output')
        manager = types.ModuleType('comfy.model_management')
        manager.throw_exception_if_processing_interrupted = lambda: None
        comfy = types.ModuleType('comfy')
        comfy.model_management = manager
        with patch.dict(sys.modules, {'folder_paths': folder, 'comfy': comfy, 'comfy.model_management': manager}):
            spec = importlib.util.spec_from_file_location('comfyui_video_layers.test_nodes', ROOT / 'tools_src/comfyui_video_layers/nodes.py')
            cls.module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(cls.module)

    def test_stale_package_rejected_before_media(self):
        with patch.object(self.module.media, 'execute') as execute:
            with self.assertRaisesRegex(ValueError, 'differs'):
                self.module.SteveVideoLayers().execute('plan.json', '{}', 'video_layers/test')
            execute.assert_not_called()

    def test_output_escape_rejected_before_media(self):
        hashes = json.dumps(self.module.LOADED_HASHES)
        for prefix in ('../escape', str(ROOT / 'escape'), '.'):
            with patch.object(self.module.media, 'execute') as execute:
                with self.assertRaisesRegex(ValueError, 'below'):
                    self.module.SteveVideoLayers().execute('plan.json', hashes, prefix)
                execute.assert_not_called()

    def test_video_and_sidecar_preview_contract(self):
        manifest = {'actual': {'frames': 10}, 'technical_status': 'warning'}
        with patch.object(self.module.media, 'execute', return_value=manifest):
            result = self.module.SteveVideoLayers().execute('plan.json', json.dumps(self.module.LOADED_HASHES), 'video_layers/test')
        self.assertEqual(result['ui']['animated'], (True,))
        self.assertEqual([x['filename'] for x in result['ui']['images']], ['candidate.mp4'])
        self.assertEqual({x['filename'] for x in result['ui']['files']}, {'manifest.json', 'layers.zip', 'source.jpg', 'comparison.jpg'})


if __name__ == '__main__':
    unittest.main()
