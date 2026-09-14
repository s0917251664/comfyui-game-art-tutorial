"""Build the image-graph golden cases used by ``test_image_profiles``.

Run ``python tests/golden_image_graphs.py --write`` only when a graph change is
intentional; the fixture otherwise locks the profile refactor to the graphs the
pipeline produced before model/sampler values moved into profile JSON.
"""

import contextlib
import io
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TOOLS_SRC = os.path.join(ROOT, "tools_src")
FIXTURE_PATH = os.path.join(ROOT, "tests", "fixtures", "image_graphs_golden.json")

# Mirrors tools_src/detect_device.py TIERS (checkpoint and default resolution).
TIER_DEVICES = {
    "sdxl_high": {"tier": "sdxl_high", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024},
    "sdxl": {"tier": "sdxl", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 1024, "default_height": 1024},
    "sdxl_light": {"tier": "sdxl_light", "checkpoint": "sd_xl_base_1.0.safetensors", "default_width": 768, "default_height": 768},
    "sd15": {"tier": "sd15", "checkpoint": "dreamshaper_8.safetensors", "default_width": 512, "default_height": 512},
}

SEED = 1234


def _cases(ig):
    lora = {"lora_name": "test_lora.safetensors", "lora_strength": 0.6}
    base = [
        ("concept", lambda: ig.build_concept("p", seed=SEED)),
        ("concept_lora_style_size", lambda: ig.build_concept(
            "p", negative="n", width=832, height=1216, seed=SEED, batch_size=2,
            checkpoint="juggernautXL_ragnarok.safetensors", **lora)),
        ("icon_asset", lambda: ig.build_icon_asset("p", seed=SEED)),
        ("icon_asset_lora", lambda: ig.build_icon_asset("p", seed=SEED, **lora)),
        ("inpaint", lambda: ig.build_inpaint("p", "img.png", "mask.png", seed=SEED)),
        ("guided_inpaint_plain", lambda: ig.build_guided_inpaint("p", "img.png", "mask.png", seed=SEED)),
        ("refine", lambda: ig.build_refine("p", "img.png", seed=SEED)),
        ("upscale", lambda: ig.build_upscale("p", "img.png", seed=SEED)),
        ("layer_split", lambda: ig.build_layer_split("img.png", "mask.png", "frame")),
        ("concept_remove_bg", lambda: _with_bg_removal(ig, ig.build_concept("p", seed=SEED))),
        ("flux2_concept", lambda: ig.build_flux2_concept("p", seed=SEED)),
        ("flux2_edit", lambda: ig.build_flux2_edit("p", "img.png", seed=SEED)),
    ]
    sdxl_only = [
        ("icon_asset_structure_ref", lambda: ig.build_icon_asset("p", seed=SEED, structure_ref_filename="tpl.png")),
        ("icon_asset_appearance_ref", lambda: ig.build_icon_asset("p", seed=SEED, appearance_ref_filename="look.png")),
        ("icon_asset_both_refs", lambda: ig.build_icon_asset(
            "p", seed=SEED, structure_ref_filename="tpl.png", appearance_ref_filename="look.png", **lora)),
        ("style_lock", lambda: ig.build_style_lock("p", "char.png", seed=SEED)),
        ("style_lock_lora", lambda: ig.build_style_lock("p", "char.png", seed=SEED, **lora)),
        ("guided_inpaint_appearance", lambda: ig.build_guided_inpaint(
            "p", "img.png", "mask.png", seed=SEED, appearance_ref_filename="look.png")),
        ("guided_inpaint_full", lambda: ig.build_guided_inpaint(
            "p", "img.png", "mask.png", seed=SEED, control_type="pose", control_ref_filename="ctl.png",
            appearance_ref_filename="look.png")),
        ("pose_only_union_depth", lambda: ig.build_pose_only(
            "p", "pose.png", seed=SEED, control_type="depth", control_backend="union")),
    ]
    for control_type in ("canny", "pose", "depth"):
        sdxl_only.extend([
            (f"character_action_{control_type}", lambda c=control_type: ig.build_character_action(
                "p", "char.png", "pose.png", seed=SEED, control_type=c)),
            (f"pose_only_{control_type}", lambda c=control_type: ig.build_pose_only(
                "p", "pose.png", seed=SEED, control_type=c)),
            (f"guided_inpaint_control_{control_type}", lambda c=control_type: ig.build_guided_inpaint(
                "p", "img.png", "mask.png", seed=SEED, control_type=c)),
        ])
    return base, sdxl_only


def _with_bg_removal(ig, built):
    graph, image_node = built
    save_id = ig.attach_bg_removal(graph, image_node)
    return graph, save_id


def build_all(ig):
    """Return {tier: {case: [graph, output_node]}} using ``ig`` (image_graphs module)."""
    result = {}
    for tier, device in TIER_DEVICES.items():
        ig.DEVICE = dict(device)
        ig.CKPT = device["checkpoint"]
        base, sdxl_only = _cases(ig)
        cases = base + (sdxl_only if tier != "sd15" else [])
        result[tier] = {name: list(fn()) for name, fn in cases}
    return result


def load_image_graphs():
    if TOOLS_SRC not in sys.path:
        sys.path.insert(0, TOOLS_SRC)
    with contextlib.redirect_stderr(io.StringIO()):
        from comfyui_pipeline import image_graphs
    return image_graphs


def main(argv):
    if "--write" not in argv:
        print("用 --write 覆寫 golden fixture；只在刻意改變 graph 時執行。", file=sys.stderr)
        return 2
    data = build_all(load_image_graphs())
    os.makedirs(os.path.dirname(FIXTURE_PATH), exist_ok=True)
    with open(FIXTURE_PATH, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write("\n")
    print(f"wrote {FIXTURE_PATH}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
