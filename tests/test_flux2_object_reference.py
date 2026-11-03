"""Two independent references retain target-first conditioning without identity."""
import unittest
from pathlib import Path

from comfyui_pipeline.runner import template as T

ROOT = Path(__file__).resolve().parents[1]
ID = 'image/flux2/edit-object-reference'


class ObjectReferenceTests(unittest.TestCase):
    def setUp(self):
        self.template = T.load_template(ROOT / 'templates', ID, repo_root=ROOT)

    def test_two_uploads_reach_both_branches_in_order(self):
        values = {'image': 'cover.png', 'object_ref': 'weapon.png',
                  'prompt': 'Repair image 1 using object in image 2', 'seed': 123}
        uploads = {k: 'uploaded/' + values[k] for k in self.template.upload_slots()}
        resolved = T.resolve(self.template, values, {}, run_id='test')
        graph, _ = T.patch(self.template, resolved, uploads)
        self.assertEqual({'image', 'object_ref'}, set(uploads))
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
            self.assertEqual(['uploaded/cover.png', 'uploaded/weapon.png'],
                             list(reversed(references)))
        self.assertNotIn('identity_ref', self.template.data['slots'])
        self.assertTrue({'20', '21', '22', '26', '28'}.isdisjoint(graph))
        self.assertEqual(2, sum(n['class_type'] == 'LoadImage' for n in graph.values()))
        self.assertEqual(['5', 0], graph['6']['inputs']['image'])
        self.assertEqual(['6', 0], graph['12']['inputs']['width'])
        self.assertEqual(['6', 1], graph['12']['inputs']['height'])

    def test_missing_object_rejected_before_upload(self):
        with self.assertRaises(T.TemplateError):
            T.resolve(self.template, {'image': 'cover.png', 'prompt': 'edit'},
                      {}, run_id='test')

    def test_original_three_reference_and_model_pins_unchanged(self):
        original = T.load_template(ROOT / 'templates',
                                   'image/flux2/edit-three-reference', repo_root=ROOT)
        self.assertEqual('513a23b6592901d72a7a5e0861cc9cee9a38cc0bdb6f59cdfdc0d13e35b0af6e',
                         original.graph_sha256)
        self.assertEqual({'image', 'identity_ref', 'object_ref'},
                         set(original.upload_slots()))
        self.assertEqual(original.data['models'], self.template.data['models'])
        self.assertEqual(original.data['provenance']['upstream']['blob'],
                         self.template.data['provenance']['upstream']['blob'])
        self.assertEqual('draft', self.template.data['status'])
        for platform in self.template.data['capability_gate']['platforms'].values():
            self.assertEqual('untested', platform['status'])
        for node in ('1', '2', '3', '5', '12', '15', '16', '24'):
            self.assertEqual(original.graph[node], self.template.graph[node])
        self.assertEqual(5.0, self.template.graph['14']['inputs']['cfg'])


if __name__ == '__main__':
    unittest.main()
