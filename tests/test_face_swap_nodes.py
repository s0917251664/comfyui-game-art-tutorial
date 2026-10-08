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
            self.module.GameArtReActorVideo().execute({},0,-1,'[[0,1]]',0,4,'error','preserve','../outside')

    def test_loader_requires_absolute_server_paths(self):
        with self.assertRaisesRegex(ValueError,'absolute'):
            self.module.GameArtLoadFaceSwapVideo().load('relative.mkv',str(self.ref))

    def test_native_video_preview_does_not_treat_sidecars_as_images(self):
        manifest={'actual':{},'counts':{},'warnings':[]}
        with patch.object(self.module,'installation_provenance',return_value={}), \
             patch.object(self.module,'ReActorEngine'), \
             patch.object(self.module.media,'render',return_value=manifest):
            result=self.module.GameArtReActorVideo().execute(
                {'video':'input.mkv','reference':str(self.ref)},0,-1,'[[0,1]]',0,4,'error','preserve','test/candidate')
        self.assertEqual([v['filename'] for v in result['ui']['images']],['candidate.mp4'])
        self.assertEqual(result['ui']['animated'],(True,))
        self.assertEqual({v['filename'] for v in result['ui']['files']},
                         {'candidate.mp4.json','comparison.jpg','frames.json'})


    # --- 改名(D9):新名稱、隱藏的舊名稱別名、型別相容 ---
    def mappings(self):
        from comfyui_face_swap_video import contracts
        return contracts, self.module.NODE_CLASS_MAPPINGS, self.module.NODE_DISPLAY_NAME_MAPPINGS

    def test_new_names_category_and_socket_type(self):
        contracts,classes,names=self.mappings()
        load,reactor=classes['GameArtLoadFaceSwapVideo'],classes['GameArtReActorVideo']
        self.assertEqual((load.CATEGORY,reactor.CATEGORY),('GameArt/Video','GameArt/Video'))
        self.assertEqual(load.RETURN_TYPES,('GAMEART_FACE_SWAP_SOURCE',))
        self.assertEqual(reactor.INPUT_TYPES()['required']['source'],('GAMEART_FACE_SWAP_SOURCE',))
        self.assertFalse(getattr(load,'DEPRECATED',False) or getattr(reactor,'DEPRECATED',False))
        self.assertEqual(set(classes),{*contracts.LEGACY_NODE_NAMES,*contracts.LEGACY_NODE_NAMES.values()})
        self.assertEqual(set(names),set(classes))

    def test_legacy_aliases_are_hidden_subclasses_with_legacy_socket(self):
        contracts,classes,names=self.mappings()
        for new,old in contracts.LEGACY_NODE_NAMES.items():
            alias=classes[old]
            self.assertTrue(issubclass(alias,classes[new]))
            self.assertIs(alias.DEPRECATED,True)  # ComfyUI node_info → deprecated: true,前端搜尋預設隱藏
            for attr in ('FUNCTION','CATEGORY','RETURN_NAMES'):
                self.assertEqual(getattr(alias,attr,None),getattr(classes[new],attr,None),attr)
            self.assertEqual(bool(getattr(alias,'OUTPUT_NODE',False)),bool(getattr(classes[new],'OUTPUT_NODE',False)))
            self.assertIn('legacy',names[old])
        load_old=classes[contracts.LEGACY_NODE_NAMES['GameArtLoadFaceSwapVideo']]
        reactor_old=classes[contracts.LEGACY_NODE_NAMES['GameArtReActorVideo']]
        self.assertEqual(load_old.RETURN_TYPES,(contracts.LEGACY_SOURCE_TYPE,))
        old_inputs=reactor_old.INPUT_TYPES(); new_inputs=classes['GameArtReActorVideo'].INPUT_TYPES()
        self.assertEqual(old_inputs['required'].pop('source'),(contracts.LEGACY_SOURCE_TYPE,))
        self.assertEqual(new_inputs['required'].pop('source'),('GAMEART_FACE_SWAP_SOURCE',))
        self.assertEqual(old_inputs,new_inputs)
        # 別名的 INPUT_TYPES 不能改到新節點
        self.assertEqual(classes['GameArtReActorVideo'].INPUT_TYPES()['required']['source'],('GAMEART_FACE_SWAP_SOURCE',))

    def test_legacy_aliases_execute_like_new_nodes(self):
        contracts,classes,_=self.mappings()
        load_old=classes[contracts.LEGACY_NODE_NAMES['GameArtLoadFaceSwapVideo']]
        reactor_old=classes[contracts.LEGACY_NODE_NAMES['GameArtReActorVideo']]
        with self.assertRaisesRegex(ValueError,'absolute'):
            load_old().load('relative.mkv',str(self.ref))
        with self.assertRaisesRegex(ValueError,'within ComfyUI output'):
            reactor_old().execute({},0,-1,'[[0,1]]',0,4,'error','preserve','../outside')
        manifest={'actual':{},'counts':{},'warnings':[]}
        results=[]
        for cls in (classes['GameArtReActorVideo'],reactor_old):
            with patch.object(self.module,'installation_provenance',return_value={}), \
                 patch.object(self.module,'ReActorEngine'), \
                 patch.object(self.module.media,'render',return_value=manifest):
                results.append(cls().execute({'video':'input.mkv','reference':str(self.ref)},
                                             0,-1,'[[0,1]]',0,4,'error','preserve','test/candidate'))
        self.assertEqual(results[0],results[1])
        self.assertEqual(load_old.IS_CHANGED.__func__,classes['GameArtLoadFaceSwapVideo'].IS_CHANGED.__func__)


if __name__=='__main__': unittest.main()
