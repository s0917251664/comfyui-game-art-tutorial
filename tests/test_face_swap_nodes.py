"""Node isolation, upstream filter handling and output boundary tests."""
import optional_deps

optional_deps.require("PIL", "numpy", "torch")

import importlib.util
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

import numpy as np
import torch
from PIL import Image

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools_src'))
from comfyui_face_swap_video import media


class FaceSwapNodeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        folder=types.ModuleType('folder_paths')
        folder.get_output_directory=lambda: tempfile.gettempdir()
        mapping=types.ModuleType('nodes'); mapping.NODE_CLASS_MAPPINGS={}
        manager=types.ModuleType('comfy.model_management')
        manager.throw_exception_if_processing_interrupted=lambda: None
        comfy=types.ModuleType('comfy'); comfy.model_management=manager
        with patch.dict(sys.modules,{'folder_paths':folder,'nodes':mapping,
                                     'comfy':comfy,'comfy.model_management':manager}):
            spec=importlib.util.spec_from_file_location('comfyui_face_swap_video.test_nodes',
                    Path(__file__).resolve().parents[1]/'tools_src/comfyui_face_swap_video/nodes.py')
            cls.module=importlib.util.module_from_spec(spec); spec.loader.exec_module(cls.module)
        cls.folder,cls.mapping,cls.manager=folder,mapping,manager

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.ref=Path(self.temp.name)/'ref.png'; Image.new('RGB',(64,64),'white').save(self.ref)

    def engine(self,node):
        self.mapping.NODE_CLASS_MAPPINGS={'ReActorFaceSwap':lambda:node}
        return self.module.ReActorEngine(self.ref,1)

    def test_calls_registered_official_node_and_preserves_batch_order(self):
        calls=[]
        class Node:
            def execute(self,**args):
                calls.append(args)
                return (1-args['input_image'],None,args['input_image'])
        engine=self.engine(Node())
        images=[np.full((64,64,3),v,np.uint8) for v in (20,40)]
        result=engine.process(images,10,None)
        self.assertEqual(len(result),2)
        self.assertLessEqual(abs(int(result[0][0,0,0])-235),1)
        self.assertLessEqual(abs(int(result[1][0,0,0])-215),1)
        self.assertEqual(calls[0]['input_faces_index'],'1')
        self.assertEqual(calls[0]['face_restore_model'],'none')
        self.assertEqual(engine.jobs[0]['location'],'ComfyUI server')

    def test_filtered_partial_batch_is_rejected(self):
        class Node:
            def execute(self,**args):
                return (args['input_image'][:1],None,args['input_image'])
        engine=self.engine(Node())
        with self.assertRaisesRegex(ValueError,'filtered/partial'):
            engine.process([np.zeros((64,64,3),np.uint8)]*2,10,None)

    def test_all_filtered_black_fallback_cannot_pass_same_canvas(self):
        class Node:
            def execute(self,**args):
                black=torch.zeros_like(args['input_image'])
                return (black,None,black)
        engine=self.engine(Node())
        with self.assertRaisesRegex(ValueError,'filtered/partial'):
            engine.process([np.full((512,512,3),100,np.uint8)],10,None)

    def test_interruption_stops_before_upstream_call(self):
        class Node:
            def execute(self,**args): raise AssertionError('must not call')
        engine=self.engine(Node())
        with patch.object(self.manager,'throw_exception_if_processing_interrupted',side_effect=RuntimeError('cancelled')):
            with self.assertRaisesRegex(RuntimeError,'cancelled'):
                engine.process([np.zeros((64,64,3),np.uint8)],10,None)

    def test_output_traversal_rejected_before_installation_or_models(self):
        with self.assertRaisesRegex(ValueError,'within ComfyUI output'):
            self.module.SteveReActorVideo().execute({},0,-1,'[[0,1]]',0,4,'error','preserve','../outside')

    def test_loader_requires_absolute_server_paths(self):
        with self.assertRaisesRegex(ValueError,'absolute'):
            self.module.SteveLoadFaceSwapVideo().load('relative.mkv',str(self.ref))

    def test_native_video_preview_does_not_treat_sidecars_as_images(self):
        manifest={'actual':{},'counts':{},'warnings':[]}
        with patch.object(self.module,'installation_provenance',return_value={}), \
             patch.object(self.module,'ReActorEngine'), \
             patch.object(self.module.media,'render',return_value=manifest):
            result=self.module.SteveReActorVideo().execute(
                {'video':'input.mkv','reference':str(self.ref)},0,-1,'[[0,1]]',0,4,'error','preserve','test/candidate')
        self.assertEqual([v['filename'] for v in result['ui']['images']],['candidate.mp4'])
        self.assertEqual(result['ui']['animated'],(True,))
        self.assertEqual({v['filename'] for v in result['ui']['files']},
                         {'candidate.mp4.json','comparison.jpg','frames.json'})


if __name__=='__main__': unittest.main()
