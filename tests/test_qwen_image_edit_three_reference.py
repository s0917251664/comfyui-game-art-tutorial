"""Qwen-Image-Edit 2511: three images reach both text encoders in declared order; source pinned."""
import hashlib
import unittest
from pathlib import Path

from comfyui_pipeline.runner import template as T

ROOT = Path(__file__).resolve().parents[1]
ID = 'image/qwen-image-edit/three-reference'


class QwenThreeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.template = T.load_template(ROOT / 'templates', ID, repo_root=ROOT)

    def test_runner_uploads_three_inputs_in_order_on_both_branches(self):
        values = {'image': 'layout.png', 'identity_ref': 'cover.png',
                  'object_ref': 'character.png', 'prompt': 'Picture 1 ...', 'seed': 123}
        uploads = {key: 'uploaded/' + values[key] for key in self.template.upload_slots()}
        resolved = T.resolve(self.template, values, {}, run_id='test')
        graph, _ = T.patch(self.template, resolved, uploads)
        self.assertEqual({'image', 'identity_ref', 'object_ref'}, set(uploads))
        sampler = graph['15']['inputs']
        for branch in ('positive', 'negative'):
            method = graph[sampler[branch][0]]
            self.assertEqual('FluxKontextMultiReferenceLatentMethod', method['class_type'])
            encoder = graph[method['inputs']['conditioning'][0]]
            self.assertEqual('TextEncodeQwenImageEditPlus', encoder['class_type'])
            scaled = graph[encoder['inputs']['image1'][0]]
            self.assertEqual('FluxKontextImageScale', scaled['class_type'])
            refs = [graph[scaled['inputs']['image'][0]]['inputs']['image'],
                    graph[encoder['inputs']['image2'][0]]['inputs']['image'],
                    graph[encoder['inputs']['image3'][0]]['inputs']['image']]
            self.assertEqual(['uploaded/layout.png', 'uploaded/cover.png', 'uploaded/character.png'], refs)
        self.assertEqual('Picture 1 ...', graph[graph['6']['inputs']['conditioning'][0]]['inputs']['prompt'])
        self.assertEqual('', graph[graph['5']['inputs']['conditioning'][0]]['inputs']['prompt'])
        self.assertEqual(['16', 0], graph['14']['inputs']['pixels'])
        self.assertEqual(123, sampler['seed'])

    def test_missing_reference_rejected_before_upload(self):
        for omitted in ('identity_ref', 'object_ref'):
            values = {'image': 'a.png', 'identity_ref': 'b.png', 'object_ref': 'c.png', 'prompt': 'edit'}
            del values[omitted]
            with self.assertRaises(T.TemplateError):
                T.resolve(self.template, values, {}, run_id='test')

    def test_official_source_pinned_and_experimental_status(self):
        raw = (self.template.directory / 'source/official-blueprint.json').read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.assertEqual('1aa7e576587331be9afb2ab61f1bcc9915b94fe7', blob)
        self.assertEqual(self.template.data['provenance']['tested_source_sha256'],
                         hashlib.sha256(raw).hexdigest())
        self.assertEqual('draft', self.template.data['status'])
        for model in self.template.data['models']:
            self.assertEqual(40, len(model['source']['revision']))
            self.assertIn(model['source']['revision'], model['url'])


if __name__ == '__main__':
    unittest.main()
