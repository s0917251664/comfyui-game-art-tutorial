"""Three images must reach both sampler conditioning branches, in declared order."""
import hashlib
import unittest
from pathlib import Path

from comfyui_pipeline.runner import template as T

ROOT = Path(__file__).resolve().parents[1]
ID = 'image/flux2/edit-three-reference'


class ThreeReferenceTests(unittest.TestCase):
    def setUp(self):
        self.template = T.load_template(ROOT / 'templates', ID, repo_root=ROOT)

    def test_runner_uploads_three_distinct_inputs_without_swapping_roles(self):
        values = {'image': 'cover.png', 'identity_ref': 'character.png',
                  'object_ref': 'weapon.png', 'prompt': 'Edit image 1', 'seed': 123}
        uploads = {key: 'uploaded/' + values[key] for key in self.template.upload_slots()}
        resolved = T.resolve(self.template, values, {}, run_id='test')
        graph, _ = T.patch(self.template, resolved, uploads)
        self.assertEqual({'image', 'identity_ref', 'object_ref'}, set(uploads))
        for branch in ('positive', 'negative'):
            node = graph['14']['inputs'][branch][0]
            references = []
            while graph[node]['class_type'] == 'ReferenceLatent':
                latent = graph[node]['inputs']['latent'][0]
                self.assertEqual('VAEEncode', graph[latent]['class_type'])
                scale = graph[latent]['inputs']['pixels'][0]
                image = graph[scale]['inputs']['image'][0]
                references.append(graph[image]['inputs']['image'])
                node = graph[node]['inputs']['conditioning'][0]
            self.assertEqual(['uploaded/cover.png', 'uploaded/character.png',
                              'uploaded/weapon.png'], list(reversed(references)))
        self.assertEqual(['5', 0], graph['6']['inputs']['image'])

    def test_missing_reference_rejected_before_upload(self):
        for omitted in ('identity_ref', 'object_ref'):
            values = {'image': 'cover.png', 'identity_ref': 'character.png',
                      'object_ref': 'weapon.png', 'prompt': 'edit'}
            del values[omitted]
            with self.assertRaises(T.TemplateError):
                T.resolve(self.template, values, {}, run_id='test')

    def test_official_source_and_old_template_remain_pinned(self):
        source = self.template.directory / 'source/official-blueprint.json'
        raw = source.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        self.assertEqual('7f6fa7a4bcd0a6b7986a137d121ec62105fc64bf', blob)
        self.assertEqual(self.template.data['provenance']['tested_source_sha256'],
                         hashlib.sha256(raw).hexdigest())
        old = T.load_template(ROOT / 'templates', 'image/flux2/edit', repo_root=ROOT)
        self.assertEqual('b6b2785e96479a4510d6feef2c2405aee72ecee3ad2e1f2688915c297a63e836', old.graph_sha256)
        self.assertEqual(old.data['models'], self.template.data['models'])
        self.assertEqual('draft', self.template.data['status'])


if __name__ == '__main__':
    unittest.main()
