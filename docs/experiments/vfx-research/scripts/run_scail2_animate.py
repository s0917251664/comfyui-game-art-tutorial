"""SCAIL-2 animation mode (replacement_mode=false) with the wood-mallet master as reference.

Uses the fixed template skills/comfyui-wan-animate/assets/scail2-api.json unchanged except the documented
dynamic fields. Source is resampled locally 24 -> 16 FPS (nearest frame) and cut to the template's 33 frames.
"""
import copy
import json
import sys
from fractions import Fraction
from pathlib import Path

import av
import numpy as np

REPO = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPO / "tools_src"))
import vfx_alpha_tools as T  # noqa: E402
from comfyui_pipeline import client  # noqa: E402

HERE = Path(__file__).resolve().parent
URL = "http://127.0.0.1:8188"
SRC = REPO / "output/experiments/vfx-research-20261007/inputs/skye_hammer_ready_FINAL_1024.mp4"
MASTER = HERE.parent / "master_wood_mallet_v3.png"
label = sys.argv[1]
video_obj, image_obj = sys.argv[2], sys.argv[3]
out = T.new_directory(HERE / f"scail2_{label}")

frames, _ = T.read_frames(SRC)
picks = [min(len(frames) - 1, round(i * 24 / 16)) for i in range(33)]
src16 = out / "source_16fps_33f.mp4"
with av.open(str(src16), "w") as c:
    s = c.add_stream("libx264", rate=Fraction(16))
    s.width = s.height = 1024
    s.pix_fmt = "yuv420p"
    s.options = {"crf": "12"}
    for i in picks:
        for p in s.encode(av.VideoFrame.from_ndarray(np.ascontiguousarray(frames[i]), format="rgb24")):
            c.mux(p)
    for p in s.encode():
        c.mux(p)

tpl = json.loads((REPO / "skills/comfyui-wan-animate/assets/scail2-api.json").read_text(encoding="utf-8"))
g = copy.deepcopy(tpl)
g["1"]["inputs"]["image"] = client.upload_image(str(MASTER), comfy_url=URL)
g["2"]["inputs"]["file"] = client.upload_image(str(src16), comfy_url=URL)
g["20"]["inputs"]["text"] = ("A cute chibi horse girl with light blue bob hair and horse ears lifts her big plain wooden mallet "
                             "(a solid block of light brown wood with wood grain on a wooden handle with a brown leather grip) "
                             "from the ground up over her shoulder and holds it ready. Flat pure green chroma key background, "
                             "static camera, 2D anime game art with thick dark outlines.")
g["31"]["inputs"]["text"] = video_obj
g["32"]["inputs"]["text"] = image_obj
g["43"]["inputs"]["noise_seed"] = 404
g["61"]["inputs"]["filename_prefix"] = f"vfx_scail2/{label}"
g["35"]["inputs"]["replacement_mode"] = False
g["40"]["inputs"]["replacement_mode"] = False
leftover = [k for k, v in g.items() for x in v["inputs"].values() if isinstance(x, str) and x.startswith("__")]
assert not leftover, leftover
(out / "workflow_api.json").write_text(json.dumps(g, ensure_ascii=False, indent=1), encoding="utf-8")
history = client.submit_and_wait(g, timeout=1800, comfy_url=URL)
paths = client.download_outputs(history, output_dir=str(out), node_ids=["61"], comfy_url=URL, allow_overwrite=False)
(out / "run.json").write_text(json.dumps({"prompt_id": history.get("_prompt_id"), "outputs": paths,
                                          "sam3": [video_obj, image_obj]}, ensure_ascii=False, indent=1), encoding="utf-8")
print(paths)
