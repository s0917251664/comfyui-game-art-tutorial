import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import av
import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('film_audio', ROOT / 'tools_src/film_audio.py')
film = importlib.util.module_from_spec(spec)
spec.loader.exec_module(film)


class FilmAudioTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.audio = self.root / 'tone.wav'
        t = np.arange(4800) / film.RATE
        data = np.tile((np.sin(t * 2 * np.pi * 440) * 0.2).astype(np.float32), (2, 1))
        film.save_wav(self.audio, data)
        Image.new('RGB', (64, 64), 'red').save(self.root / 'red.png')
        Image.new('RGB', (64, 64), 'blue').save(self.root / 'blue.png')

    def tearDown(self):
        self.tmp.cleanup()

    def plan(self, name, payload):
        path = self.root / name
        path.write_text(json.dumps(payload), encoding='utf-8')
        return str(path)

    def test_mix_places_track_at_measured_offset(self):
        args = SimpleNamespace(plan=self.plan('mix.json', {'duration':0.5,'tracks':[{'audio':'tone.wav','start':0.2}]}), output=str(self.root/'mix.wav'))
        result = film.mix(args)
        data = film.read_audio(args.output)
        self.assertEqual(data.shape[1], 24000)
        self.assertEqual(float(np.max(np.abs(data[:,:9600]))), 0)
        self.assertGreater(float(np.max(np.abs(data[:,9600:14400]))), 0.19)
        self.assertEqual(float(np.max(np.abs(data[:,14400:]))), 0)
        self.assertEqual(result['content_status'], 'candidate')

    def test_clipping_rejected_or_explicitly_normalized(self):
        payload={'tracks':[{'audio':'tone.wav','gain_db':12},{'audio':'tone.wav','gain_db':12}]}
        args=SimpleNamespace(plan=self.plan('clip.json',payload),output=str(self.root/'clip.wav'))
        with self.assertRaisesRegex(ValueError,'clip'):
            film.mix(args)
        self.assertFalse(Path(args.output).exists())
        payload['peak_policy']='normalize'
        args.plan=self.plan('clip.json',payload)
        film.mix(args)
        self.assertLessEqual(float(np.max(np.abs(film.read_audio(args.output)))),0.981)

    def test_too_short_mix_rejects_track_without_truncation(self):
        args=SimpleNamespace(plan=self.plan('mix.json',{'duration':0.05,'tracks':[{'audio':'tone.wav'}]}),output=str(self.root/'mix.wav'))
        with self.assertRaisesRegex(ValueError,'truncation'):
            film.mix(args)
        self.assertFalse(Path(args.output).exists())

    def test_animatic_measured_timing_and_real_image_change(self):
        plan={'width':64,'height':64,'audio':'tone.wav','audio_policy':'pad','shots':[
            {'id':'a','image':'red.png','timing_audio':'tone.wav','tail_pause':0.01},
            {'id':'b','image':'blue.png','duration':0.125}]}
        args=SimpleNamespace(plan=self.plan('shots.json',plan),output=str(self.root/'boards.mp4'))
        result=film.animatic(args)
        self.assertEqual(result['actual']['video']['frames'],6)
        self.assertEqual(result['parameters']['timeline'][1]['start_frame'],3)
        with av.open(args.output) as src:
            frames=[f.to_ndarray(format='rgb24') for f in src.decode(video=0)]
        self.assertGreater(frames[0][:,:,0].mean(),200)
        self.assertGreater(frames[-1][:,:,2].mean(),200)
        self.assertLess(abs(result['actual']['audio']['decoded_duration']-0.25),0.03)

    def test_audio_policy_does_not_silently_cut_or_pad(self):
        data=film.read_audio(self.audio)
        with self.assertRaisesRegex(ValueError,'longer'):
            film.align_audio(data,1000,'pad')
        with self.assertRaisesRegex(ValueError,'shorter'):
            film.align_audio(data,9600,'exact')
        trimmed,info=film.align_audio(data,1000,'trim')
        self.assertEqual(trimmed.shape[1],1000)
        self.assertEqual(info['trimmed_samples'],3800)

    def test_overwrite_protection_preserves_media_and_sidecar(self):
        path=self.root/'existing.wav'
        path.write_bytes(b'preserve')
        with self.assertRaises(FileExistsError):
            film.new_output(path,'.wav')
        self.assertEqual(path.read_bytes(),b'preserve')
        only_sidecar=self.root/'orphan.wav'
        Path(str(only_sidecar)+'.json').write_text('{}')
        with self.assertRaises(FileExistsError):
            film.new_output(only_sidecar,'.wav')

    def test_duplicate_shots_and_nonfinite_durations_rejected(self):
        plan={'shots':[{'id':'a','image':'red.png','duration':0.1},{'id':'a','image':'blue.png','duration':0.1}]}
        args=SimpleNamespace(plan=self.plan('bad.json',plan),output=str(self.root/'bad.mp4'))
        with self.assertRaisesRegex(ValueError,'Duplicate'):
            film.animatic(args)
        with self.assertRaises(ValueError):
            film.finite(float('nan'),'duration')

    def test_dub_preserves_frames_and_requires_replacement_opt_in(self):
        plan={'width':64,'height':64,'shots':[{'id':'a','image':'red.png','duration':0.25}]}
        args=SimpleNamespace(plan=self.plan('silent.json',plan),output=str(self.root/'silent.mp4'))
        film.animatic(args)
        dub=SimpleNamespace(video=args.output,audio=str(self.audio),output=str(self.root/'dub.mp4'),audio_policy='pad',replace_audio=False)
        result=film.dub(dub)
        self.assertEqual(result['actual']['video']['frames'],6)
        self.assertIn('audio',result['actual'])
        dub.video=dub.output
        dub.output=str(self.root/'overwrite-audio.mp4')
        with self.assertRaisesRegex(ValueError,'already has audio'):
            film.dub(dub)


if __name__=='__main__':
    unittest.main()
