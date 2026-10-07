"""Requirement 1, control C (independent of the luma extractor's assumptions). Writes ./analysis_c/.

Ground truth = luma RGBA from the real black clip with straight colour scaled by 0.75 (peak channel ~191),
alpha unchanged. Black-background extraction cannot tell "dimmer colour" from "lower alpha", so this
measures luma's systematic error for non-emissive / non-peak-white effects. Chroma and BiRefNet see the
same ground truth over green / black. Lossless composites only.
"""
import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = T.new_directory(HERE / "analysis_c")
MODEL_ROOT = Path(r"C:\Users\XU\ComfyUI\models\background_removal_variants")
src, _ = T.read_frames(HERE / "analysis" / "real" / "luma_on_black", mode="RGBA")
gt = [np.dstack([np.round(f[..., :3].astype(np.float32) * 0.75).astype(np.uint8), f[..., 3]]) for f in src]
T.write_sequence(gt, OUT / "ground_truth")
on_black = [T.over(f, (0, 0, 0)) for f in gt]
on_green = [T.over(f, (0, 255, 0)) for f in gt]
ref_alpha = [f[..., 3] for f in gt]
results, mid, boards = {}, len(gt) // 2, []
cases = [("luma_on_black", lambda: [T.luma_alpha(f) for f in on_black], None),
         ("chroma_baseline_on_green", lambda: [T.chroma_alpha(f) for f in on_green], "00FF00"),
         ("chroma_unmix_despill_on_green", lambda: [T.chroma_alpha(f, unmix=True, despill=True) for f in on_green], "00FF00"),
         ("birefnet_general_on_black", lambda: T.birefnet_alpha(on_black, MODEL_ROOT, "general")[0], None),
         ("birefnet_general_on_green", lambda: T.birefnet_alpha(on_green, MODEL_ROOT, "general")[0], "00FF00")]
for name, fn, key in cases:
    rgba = fn()
    T.write_sequence(rgba, OUT / name)
    m = T.alpha_metrics(rgba, key=key, reference_alpha=ref_alpha)
    # Visual error that matters for compositing: result over the light background vs ground truth over it.
    light_err = [float(np.abs(T.over(a, T.LIGHT_BG).astype(int) - T.over(b, T.LIGHT_BG).astype(int)).mean())
                 for a, b in zip(rgba, gt)]
    dark_err = [float(np.abs(T.over(a, T.DARK_BG).astype(int) - T.over(b, T.DARK_BG).astype(int)).mean())
                for a, b in zip(rgba, gt)]
    m["composite_mae_on_light_bg"] = float(np.mean(light_err))
    m["composite_mae_on_dark_bg"] = float(np.mean(dark_err))
    results[name] = m
    boards.append((name.upper().replace("_ON_", " / "), rgba[mid]))
    print(name, m["against_reference"], round(m["composite_mae_on_light_bg"], 3), round(m["composite_mae_on_dark_bg"], 3))
T.comparison_board(on_green[mid], [("GROUND TRUTH", gt[mid])] + boards, OUT / "board_control_c_mid.png", 240)
T.save_json(OUT / "req1_control_c.json", results)
