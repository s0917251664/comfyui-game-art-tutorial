import argparse
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw
import comfyui_design as d


class DesignTests(unittest.TestCase):
    def icon(self):
        im=Image.new('RGBA',(100,100))
        ImageDraw.Draw(im).rectangle((30,10,69,89),fill=(200,50,20,128))
        return im

    def test_scene_preserves_aspect_uses_alpha_inverse_and_exact_canvas(self):
        graph,save,size,placements=d.build_graph('scene',['icon.png'],[self.icon()],background_filename='bg.png',
             background_size=(400,400),x=100,y=50,width=100,height=200)
        self.assertEqual(size,(400,400))
        self.assertEqual(placements,[{'input':0,'box':[100,50,100,200]}])
        kinds=[n['class_type'] for n in graph.values()]
        self.assertEqual(kinds.count('InvertMask'),1)
        crop=next(n for n in graph.values() if n['class_type']=='CropMask')['inputs']
        self.assertEqual((crop['x'],crop['y'],crop['width'],crop['height']),(30,10,40,80))
        self.assertEqual(graph[save]['class_type'],'SaveImage')
        self.assertFalse(any('Sampler' in k for k in kinds))

    def test_pattern_uses_one_scaled_motif_and_spacing_proves_no_edge_crossing(self):
        graph,_,size,placements=d.build_graph('pattern',['i.png'],[self.icon()],cell=128,columns=3,rows=2,padding=24)
        self.assertEqual(size,(384,256));self.assertEqual(len(placements),6)
        self.assertEqual(sum(n['class_type']=='LoadImage' for n in graph.values()),1)
        for p in placements:
            x,y,w,h=p['box'];self.assertGreaterEqual(x,24);self.assertGreaterEqual(y,24)
            self.assertLessEqual(x+w,size[0]-24);self.assertLessEqual(y+h,size[1]-24)

    def test_sheet_does_not_claim_style_or_generate_new_icons(self):
        g,_,size,p=d.build_graph('sheet',['a','b'],[self.icon(),self.icon()],cell=128,columns=2)
        self.assertEqual(size,(256,128));self.assertEqual([i['input'] for i in p],[0,1])
        self.assertTrue(all(n['class_type'] not in {'KSampler','CheckpointLoaderSimple'} for n in g.values()))

    def test_chinese_title_bad_color_and_overflow_rejected(self):
        with self.assertRaises(ValueError):d.build_graph('sheet',['a'],[self.icon()],title='藥水')
        with self.assertRaises(ValueError):d.rgb_color('#zzz000')
        with self.assertRaises(ValueError):d.build_graph('scene',['a'],[self.icon()],background_filename='b',background_size=(200,200),x=100,y=100,width=101,height=100)
        with self.assertRaises(ValueError):d.build_graph('pattern',['a','b'],[self.icon(),self.icon()])

    def test_canvas_resize_crops_background_only_and_centers_object_box(self):
        g,_,size,p=d.build_graph('scene',['i'],[self.icon()],background_filename='b',background_size=(400,400),
             canvas_width=800,canvas_height=600,x=500,y=50,width=200,height=400)
        self.assertEqual(size,(800,600));self.assertEqual(p[0]['box'],[500,50,200,400])
        scales=[n['inputs'] for n in g.values() if n['class_type']=='ImageScale']
        self.assertEqual(scales[0]['crop'],'center');self.assertEqual(scales[1]['crop'],'disabled')

    def test_missing_node_and_opaque_object_stop_before_upload_queue_or_output(self):
        with tempfile.TemporaryDirectory() as root:
            root=Path(root);image=root/'i.png';self.icon().save(image)
            args=argparse.Namespace(command='sheet',images=[str(image)],comfy_url='http://127.0.0.1:8188',config=None,
                timeout=30,background=None,x=0,y=0,width=128,height=128,cell=128,columns=2,padding=24,rows=2,
                color='#ffffff',title='',caption='',canvas_width=None,canvas_height=None,output_dir=str(root/'out'))
            with patch.object(d.generate,'_fetch_comfy_object_info',return_value={}),patch.object(d.generate,'upload_image') as upload,patch.object(d.generate,'submit_and_wait') as queue:
                with self.assertRaises(RuntimeError):d.run(args)
                upload.assert_not_called();queue.assert_not_called();self.assertFalse((root/'out').exists())
            Image.new('RGB',(64,64),'red').save(image)
            with patch.object(d.generate,'_fetch_comfy_object_info') as fetch:
                with self.assertRaises(ValueError):d.run(args)
                fetch.assert_not_called()


if __name__=='__main__':unittest.main()
