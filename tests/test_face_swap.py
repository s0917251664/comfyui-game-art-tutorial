"""Media contract tests with generated video/audio and a deterministic fake engine."""
import argparse
from fractions import Fraction
from pathlib import Path
import sys
import tempfile
import unittest

import av
import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools_src'))
import face_swap as tool


class FakeClient:
    def __init__(self, unchanged=False, truncated=False):
        self.jobs=[]
        self.unchanged,self.truncated=unchanged,truncated

    def process(self,images,fps,directory):
        self.jobs.append({'prompt_id':'fake','frames':len(images)})
        result=images if self.unchanged else [255-image for image in images]
        return result[:-1] if self.truncated else result


class FaceSwapTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.video = self.root/'input.mkv'
        with av.open(str(self.video), 'w') as out:
            vs = out.add_stream('libx264', rate=10)
            vs.width, vs.height, vs.pix_fmt = 64,64,'yuv420p'
            aus = out.add_stream('pcm_s16le', rate=48000)
            aus.layout = 'stereo'
            for n in range(20):
                f = av.VideoFrame.from_ndarray(np.full((64,64,3), n, np.uint8), format='rgb24')
                f.pts, f.time_base = n, Fraction(1,10)
                for p in vs.encode(f): out.mux(p)
            for p in vs.encode(None): out.mux(p)
            # Tone begins 0.2 seconds after video. Test timestamp alignment.
            values = (.2*np.sin(2*np.pi*440*np.arange(86400)/48000)).astype(np.float32)
            data = np.stack((values,values))
            for offset in range(0,86400,1024):
                f = av.AudioFrame.from_ndarray(np.ascontiguousarray(data[:,offset:offset+1024]), format='fltp',layout='stereo')
                f.sample_rate=48000; f.pts=9600+offset; f.time_base=Fraction(1,48000)
                for p in aus.encode(f): out.mux(p)
            for p in aus.encode(None): out.mux(p)
        self.ref = self.root/'ref.png'
        Image.new('RGB',(64,64),'white').save(self.ref)

    def args(self, **kwargs):
        values = dict(video=str(self.video),source_image=str(self.ref),
                      output_dir=str(self.root/'result'),start=0.,end=2.,edit_range=[(0.,1.)],
                      batch_size=8,face_index=0,on_unchanged='error',audio='preserve')
        values.update(kwargs)
        return argparse.Namespace(**values)

    def test_frame_contract_audio_offset_and_selection(self):
        m = tool.render(self.args(),FakeClient(),{})
        self.assertEqual(m['actual']['frames'],20)
        self.assertEqual(m['actual']['fps'],'10')
        self.assertEqual(m['counts'],{'changed':10,'outside_edit_ranges':10})
        self.assertEqual(m['technical_status'],'pass')
        self.assertGreater(m['actual']['audio_rms'],.05)
        data, _ = tool.audio_timeline(self.root/'result/candidate.mp4',0,2,0,96000)
        self.assertLess(np.max(np.abs(data[:,:8000])),.01)
        self.assertGreater(np.sqrt(np.mean(data[:,12000:24000]**2)),.1)
        self.assertTrue((self.root/'result/candidate.mp4.json').exists())

    def test_unchanged_selected_frame_does_not_publish(self):
        with self.assertRaisesRegex(ValueError,'Unchanged'):
            tool.render(self.args(),FakeClient(unchanged=True),{})
        self.assertFalse((self.root/'result').exists())
        self.assertFalse(list(self.root.glob('.result-*')))

    def test_no_swap_does_not_publish_even_with_preserve(self):
        with self.assertRaisesRegex(ValueError,'No changed frames'):
            tool.render(self.args(on_unchanged='preserve'),FakeClient(unchanged=True),{})
        self.assertFalse((self.root/'result').exists())

    def test_overwrite_rejected(self):
        (self.root/'result').mkdir()
        sentinel=self.root/'result/keep.txt'; sentinel.write_text('keep')
        with self.assertRaises(FileExistsError):
            tool.render(self.args(),FakeClient(),{})
        self.assertEqual(sentinel.read_text(),'keep')

    def test_filtered_comfy_batch_rejected(self):
        with self.assertRaisesRegex(ValueError,'Batch frame count mismatch'):
            tool.render(self.args(),FakeClient(truncated=True),{})
        self.assertFalse((self.root/'result').exists())

    def test_fixed_graph_routes_inference_and_video_to_comfy(self):
        graph=tool.build_graph(['a.png','b.png'],'steve.png',60,'test',face_index=1)
        self.assertEqual(graph['100']['class_type'],'ReActorFaceSwap')
        self.assertEqual(graph['100']['inputs']['source_image'],['1',0])
        self.assertEqual(graph['100']['inputs']['input_faces_index'],'1')
        self.assertEqual(graph['201']['inputs']['images'],['100',0])
        self.assertEqual(graph['202']['class_type'],'SaveVideo')
        for node in graph.values():
            for value in node['inputs'].values():
                if isinstance(value,list): self.assertIn(value[0],graph)
        with self.assertRaises(ValueError): tool.build_graph(['a']*9,'b',24,'bad')

    def test_pinned_hash_mismatch(self):
        with self.assertRaisesRegex(ValueError,'hash mismatch'):
            tool.checked(self.root,'ref.png','0'*64)

    def test_invalid_ranges_rejected(self):
        for value in ('nan:1','0:inf','2:1','-1:2','bad'):
            with self.assertRaises(argparse.ArgumentTypeError): tool.parse_range(value)
        self.assertEqual(tool.parse_range('0:1.5'),(0.,1.5))
        with self.assertRaisesRegex(ValueError,'overlap'):
            tool.render(self.args(edit_range=[(0.,1.),(.5,1.5)]),FakeClient(),{})

    def test_audio_drop_is_explicit(self):
        m = tool.render(self.args(audio='drop'),FakeClient(),{})
        self.assertEqual(m['actual']['audio_streams'],0)


if __name__ == '__main__':
    unittest.main()
