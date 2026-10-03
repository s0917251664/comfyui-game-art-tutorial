import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import av
import numpy as np
from PIL import Image
import film_audio as audio
import film_lipsync as lipsync


class LipSyncContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        Image.new('RGB', (64, 64), 'red').save(self.root / 'frame.png')
        t = np.arange(24000) / audio.RATE
        self.data = np.tile((np.sin(t * 2 * np.pi * 440) * .2).astype(np.float32), (2, 1))
        self.wav = self.root / 'speech.wav'
        audio.save_wav(self.wav, self.data)

    def tearDown(self):
        self.tmp.cleanup()

    def video(self, name, frames, sound=False):
        p = self.root / (name + '.json')
        plan = {'width': 64, 'height': 64,
                'shots': [{'id': 'test', 'image': 'frame.png', 'duration': frames / 24}]}
        if sound:
            plan.update(audio='speech.wav', audio_policy='pad')
        p.write_text(json.dumps(plan), encoding='utf8')
        output = self.root / (name + '.mp4')
        audio.animatic(SimpleNamespace(plan=str(p), output=str(output)))
        return output

    def test_speech_longer_than_source_never_loops_motion(self):
        with self.assertRaisesRegex(ValueError, 'longer than source'):
            lipsync.validate_inputs(self.video('short', 11), self.wav)

    def test_existing_source_audio_requires_explicit_replace(self):
        source = self.video('sound', 13, True)
        with self.assertRaisesRegex(ValueError, 'replace-audio'):
            lipsync.validate_inputs(source, self.wav)
        _, _, frames = lipsync.validate_inputs(source, self.wav, True)
        self.assertEqual(frames, 12)

    def test_only_one_missing_tail_frame_can_be_held(self):
        raw = self.video('raw', 11)
        output = self.root / 'normalized.mp4'
        info = lipsync.normalize_result(raw, output, self.data, 12)
        self.assertEqual(info['held_tail_frames'], 1)
        self.assertEqual(audio.inspect_media(output)['video']['frames'], 12)
        with av.open(str(output)) as c:
            frames = [f.to_ndarray(format='rgb24') for f in c.decode(video=0)]
        self.assertLess(np.abs(frames[-1].astype(float) - frames[-2]).mean(), 2)
        self.assertGreater(np.max(np.abs(audio.read_audio(output))), .15)

    def test_missing_face_frames_are_rejected_before_publish(self):
        raw = self.video('missing', 9)
        output = self.root / 'bad.mp4'
        with self.assertRaisesRegex(ValueError, 'missing face/frame'):
            lipsync.normalize_result(raw, output, self.data, 12)
        self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
