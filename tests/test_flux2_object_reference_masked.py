"""Masked img2img must use target pixels and carry the selected noise region."""
import unittest
from pathlib import Path

from comfyui_pipeline.runner import template as T

ROOT = Path(__file__).resolve().parents[1]
ID = 'image/flux2/edit-object-reference-masked'


class MaskedObjectReferenceTests(unittest.TestCase):
    def setUp(self):
        self.template = T.load_template(ROOT / 'templates', ID, repo_root=ROOT)

    def patched(self, **extra):
        values = dict(image='target.png', object_ref='weapon.png', mask='mask.png',
                      prompt='repair image 1', seed=123, **extra)
        uploads = {k: 'uploaded/' + values[k] for k in self.template.upload_slots()}
        resolved = T.resolve(self.template, values, {}, run_id='test')
        return T.patch(self.template, resolved, uploads)[0]

    def test_sampler_receives_target_vae_latent_with_loaded_mask(self):
        g = self.patched()
        self.assertEqual({'image', 'object_ref', 'mask'}, set(self.template.upload_slots()))
        sample_latent = g[g['17']['inputs']['latent_image'][0]]
        self.assertEqual('SetLatentNoiseMask', sample_latent['class_type'])
        target_latent = g[sample_latent['inputs']['samples'][0]]
        self.assertEqual('VAEEncode', target_latent['class_type'])
        self.assertEqual(['5', 0], target_latent['inputs']['pixels'])
        self.assertEqual(['3', 0], target_latent['inputs']['vae'])
        self.assertEqual(16, g['5']['inputs']['resolution_steps'])
        self.assertEqual(1, g['24']['inputs']['resolution_steps'])
        self.assertFalse(any(n['class_type'] == 'EmptyFlux2LatentImage' for n in g.values()))
        mask = g[sample_latent['inputs']['mask'][0]]
        self.assertEqual('ImageToMask', mask['class_type'])
        self.assertEqual('red', mask['inputs']['channel'])
        scale = g[mask['inputs']['image'][0]]
        self.assertEqual('ImageScale', scale['class_type'])
        self.assertEqual(['6', 0], scale['inputs']['width'])
        self.assertEqual(['6', 1], scale['inputs']['height'])
        self.assertEqual('disabled', scale['inputs']['crop'])
        to_image = g[scale['inputs']['image'][0]]
        self.assertEqual('MaskToImage', to_image['class_type'])
        self.assertEqual(['30', 1], to_image['inputs']['mask'])
        self.assertEqual('uploaded/mask.png', g['30']['inputs']['image'])

    def test_partial_schedule_uses_low_sigmas_and_resolves_denoise(self):
        g = self.patched(denoise=0.8)
        sigma_node, output = g['17']['inputs']['sigmas']
        self.assertEqual(1, output)
        self.assertEqual('SplitSigmasDenoise', g[sigma_node]['class_type'])
        self.assertEqual(['16', 0], g[sigma_node]['inputs']['sigmas'])
        self.assertEqual(0.8, g[sigma_node]['inputs']['denoise'])
        self.assertEqual(0.65, self.patched()[sigma_node]['inputs']['denoise'])
        for invalid in (0, 0.04, 1.01):
            with self.assertRaises(T.TemplateError):
                self.patched(denoise=invalid)

    def test_missing_mask_rejected_before_upload(self):
        with self.assertRaises(T.TemplateError):
            T.resolve(self.template, dict(image='target.png', object_ref='weapon.png',
                                         prompt='repair'), {}, run_id='test')

    def test_reference_order_and_original_model_pins_remain(self):
        original = T.load_template(ROOT / 'templates', 'image/flux2/edit-object-reference', repo_root=ROOT)
        self.assertEqual(original.data['models'], self.template.data['models'])
        g = self.patched()
        for branch, top, first in [('positive', '27', '10'), ('negative', '29', '11')]:
            self.assertEqual([top, 0], g['14']['inputs'][branch])
            self.assertEqual([first, 0], g[top]['inputs']['conditioning'])
            self.assertEqual(['25', 0], g[top]['inputs']['latent'])
            self.assertEqual(['9', 0], g[first]['inputs']['latent'])
        for node in ('1', '2', '3', '15', '16', '24'):
            self.assertEqual(original.graph[node], self.template.graph[node])
        self.assertEqual('draft', self.template.data['status'])
        self.assertTrue(all(p['status'] == 'untested' for p in self.template.data['capability_gate']['platforms'].values()))


if __name__ == '__main__':
    unittest.main()
