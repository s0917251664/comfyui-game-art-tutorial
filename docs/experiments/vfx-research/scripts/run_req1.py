"""Requirement 1 measurement run (vfx-research-20261007). Writes into ./analysis/ (must not exist).

A. Real H3 clips: black-bg clip -> luma alpha / BiRefNet; green-bg clip -> chroma (baseline, unmix+despill) / BiRefNet.
B. Known-alpha synthetic control: the luma RGBA of the black clip is treated as ground truth, recomposited
   losslessly and through H.264 yuv420p onto black and green, then each method is scored against it.
"""
import json
import sys
import time
from fractions import Fraction
from pathlib import Path

import av
import numpy as np
from PIL import Image

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = T.new_directory(HERE / "analysis")
MODEL_ROOT = Path(r"C:\Users\XU\ComfyUI\models\background_removal_variants")
BLACK_POINT = 16 / 255
results = {"black_point": BLACK_POINT, "real": {}, "synthetic": {}}


def timed(fn, *a, **k):
    t = time.perf_counter()
    r = fn(*a, **k)
    return r, time.perf_counter() - t


def run_method(name, frames, fn, key=None, ref=None, bucket=None):
    if fn == "birefnet":
        (rgba, _), sec = timed(T.birefnet_alpha, frames, MODEL_ROOT, bucket_variant[name])
    else:
        rgba, sec = timed(lambda: [fn(f) for f in frames])
    d = OUT / bucket / name
    T.write_sequence(rgba, d)
    m = T.alpha_metrics(rgba, key=key, reference_alpha=[r[..., 3] for r in ref] if ref else None)
    m["seconds_per_frame"] = round(sec / len(frames), 4)
    m["frames_dir"] = str(d)
    print(bucket, name, json.dumps({k: m[k] for k in ("seconds_per_frame", "semi_transparent_fraction_of_visible")}),
          m["temporal"]["mean_second_difference_flicker"], m.get("against_reference", {}))
    return rgba, m


bucket_variant = {"birefnet_general": "general", "birefnet_hr_matting": "hr-matting"}
luma = lambda f: T.luma_alpha(f, black_point=BLACK_POINT)
chroma = lambda f: T.chroma_alpha(f)
chroma_fix = lambda f: T.chroma_alpha(f, unmix=True, despill=True)

# ---------------- A. real clips
black, _ = T.read_frames(HERE / "r1_fx_black_00001_.mp4")
green, _ = T.read_frames(HERE / "r1_fx_green_00001_.mp4")
real = {}
for name, frames, fn, key in [
    ("luma_on_black", black, luma, None),
    ("birefnet_general", black, "birefnet", None),
    ("chroma_baseline_on_green", green, chroma, "00FF00"),
    ("chroma_unmix_despill_on_green", green, chroma_fix, "00FF00"),
]:
    real[name], results["real"][name] = run_method(name, frames, fn, key, bucket="real")
# BiRefNet on the green clip as well (name clash avoided with explicit dict)
bucket_variant["birefnet_general_on_green"] = "general"
real["birefnet_general_on_green"], results["real"]["birefnet_general_on_green"] = run_method(
    "birefnet_general_on_green", green, "birefnet", "00FF00", bucket="real")
bucket_variant["birefnet_hr_matting_on_black"] = "hr-matting"
real["birefnet_hr_matting_on_black"], results["real"]["birefnet_hr_matting_on_black"] = run_method(
    "birefnet_hr_matting_on_black", black, "birefnet", None, bucket="real")

mid = len(black) // 2
T.comparison_board(black[mid], [("LUMA", real["luma_on_black"][mid]),
                                 ("BIREFNET", real["birefnet_general"][mid]),
                                 ("BIREFNET-HRM", real["birefnet_hr_matting_on_black"][mid])],
                   OUT / "board_real_black_clip_mid.png", 300)
T.comparison_board(green[mid], [("CHROMA BASE", real["chroma_baseline_on_green"][mid]),
                                 ("CHROMA UNMIX", real["chroma_unmix_despill_on_green"][mid]),
                                 ("BIREFNET", real["birefnet_general_on_green"][mid])],
                   OUT / "board_real_green_clip_mid.png", 300)

# ---------------- B. known-alpha control
gt = real["luma_on_black"]


def h264_roundtrip(frames, path):
    h, w = frames[0].shape[:2]
    with av.open(str(path), "w") as c:
        s = c.add_stream("libx264", rate=Fraction(24))
        s.width, s.height, s.pix_fmt = w, h, "yuv420p"
        s.options = {"crf": "18"}
        for f in frames:
            for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(f), format="rgb24")):
                c.mux(p)
        for p in s.encode():
            c.mux(p)
    return T.read_frames(path)[0]


comp_black = [T.over(f, (0, 0, 0)) for f in gt]
comp_green = [T.over(f, (0, 255, 0)) for f in gt]
variants = {
    "lossless": (comp_black, comp_green),
    "h264_crf18": (h264_roundtrip(comp_black, OUT / "synthetic_black_h264.mp4"),
                   h264_roundtrip(comp_green, OUT / "synthetic_green_h264.mp4")),
}
luma0 = lambda f: T.luma_alpha(f, black_point=0.0)
synth_boards = {}
for vname, (cb, cg) in variants.items():
    bucket = f"synthetic_{vname}"
    results["synthetic"][vname] = {}
    for name, frames, fn, key in [
        ("luma_on_black", cb, luma0, None),
        ("chroma_baseline_on_green", cg, chroma, "00FF00"),
        ("chroma_unmix_despill_on_green", cg, chroma_fix, "00FF00"),
    ]:
        rgba, results["synthetic"][vname][name] = run_method(name, frames, fn, key, ref=gt, bucket=bucket)
        synth_boards.setdefault(vname, []).append((name.split("_on_")[0].upper(), rgba[mid]))
    for name, frames in (("birefnet_general_on_black", cb), ("birefnet_general_on_green", cg)):
        bucket_variant[name] = "general"
        rgba, results["synthetic"][vname][name] = run_method(name, frames, "birefnet", "00FF00" if "green" in name else None,
                                                             ref=gt, bucket=bucket)
        synth_boards[vname].append((name.replace("birefnet_general", "BIREFNET").upper(), rgba[mid]))
    T.comparison_board(cg[mid], [("GROUND TRUTH", gt[mid])] + synth_boards[vname],
                       OUT / f"board_synthetic_{vname}_mid.png", 260)

T.save_json(OUT / "req1_results.json", results)
print("done", OUT)
