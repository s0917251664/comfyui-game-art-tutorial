"""Server-only source video checks and audio helpers shared by the video layer nodes and client.

Moved here from the retired face-swap package (the functions were not changed).
"""
from __future__ import annotations

from fractions import Fraction

import av
import numpy as np

RATE = 48000


def encode_audio(out, stream, data):
    for offset in range(0, data.shape[1], 1024):
        frame = av.AudioFrame.from_ndarray(np.ascontiguousarray(data[:, offset:offset+1024]),
                                          format='fltp', layout='stereo')
        frame.sample_rate = RATE
        frame.pts, frame.time_base = offset, Fraction(1, RATE)
        for packet in stream.encode(frame):
            out.mux(packet)
    for packet in stream.encode(None):
        out.mux(packet)


def inspect_video(path):
    with av.open(str(path)) as c:
        if len(c.streams.video) != 1 or len(c.streams.audio) > 1:
            raise ValueError('Exactly one video and at most one audio stream required')
        s = c.streams.video[0]
        fps = s.average_rate
        if fps is None or not 1 <= float(fps) <= 60:
            raise ValueError('Source FPS must be known and between 1 and 60')
        if max(s.width, s.height) > 1920 or s.width % 2 or s.height % 2:
            raise ValueError('Even source dimensions and longest side <=1920 required')
        tolerance = max(1e-5, float(s.time_base) * 1.1)
        first = last = None
        count = 0
        for frame in c.decode(video=0):
            if frame.pts is None:
                raise ValueError('Missing source video timestamp')
            t = float(frame.time)
            if last is not None and (t <= last or abs(t-last-1/float(fps)) > tolerance):
                raise ValueError('VFR / discontinuous timestamps unsupported')
            if first is None:
                first = t
            last = t
            count += 1
            if count / float(fps) > 60:
                raise ValueError('Source exceeds 60 seconds; split into shots')
        if not count:
            raise ValueError('Empty source video')
        return {'width': s.width, 'height': s.height, 'fps': str(Fraction(fps)), 'frames': count,
                'duration': count / float(fps), 'first_time': first,
                'audio_streams': len(c.streams.audio),
                'timestamp_tolerance': tolerance}


def audio_timeline(path, first_time, duration, start, count):
    """Place resampled audio using timestamps; retain original offset and gaps."""
    timeline = np.zeros((2, round(duration * RATE)), dtype=np.float32)
    resampler = av.AudioResampler(format='fltp', layout='stereo', rate=RATE)
    decoded = 0
    timestamps = []
    def place(frame):
        nonlocal decoded
        if frame.pts is None:
            raise ValueError('Audio requires timestamps')
        data = frame.to_ndarray()
        if not np.isfinite(data).all():
            raise ValueError('Nonfinite audio')
        offset = round((float(frame.time) - first_time) * RATE)
        if decoded + data.shape[1] > 61 * RATE or offset > 61 * RATE:
            raise ValueError('Audio exceeds bounded 61 second decode limit')
        timestamps.append(offset)
        lo, hi = max(0, offset), min(timeline.shape[1], offset + data.shape[1])
        if hi > lo:
            timeline[:, lo:hi] = data[:, lo-offset:hi-offset]
        decoded += data.shape[1]
    with av.open(str(path)) as c:
        for frame in c.decode(audio=0):
            for f in resampler.resample(frame):
                place(f)
        for f in resampler.resample(None):
            place(f)
    if not decoded:
        raise ValueError('Empty source audio')
    begin = round(start * RATE)
    data = timeline[:, begin:begin + count]
    if data.shape[1] < count:
        data = np.pad(data, ((0, 0), (0, count-data.shape[1])))
    return data, {'decoded_samples': decoded, 'first_offset_samples': timestamps[0],
                  'output_samples': count, 'sample_rate': RATE, 'channels': 2,
                  'policy': 'timestamp placement, clip to video interval, silence for gaps; AAC re-encode'}
