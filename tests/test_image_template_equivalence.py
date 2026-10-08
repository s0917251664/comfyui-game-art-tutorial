"""圖片 template resolve+patch 與 image_graphs builder、golden fixture 逐欄位相同。

sdxl_light 只差寬高，由呼叫端傳入；template 預設仍是家族原生尺寸。
icon_asset 用原生 1024，即使 tier 是 sdxl_light。
sd15 底模不在磁碟上時，對應 template 不存在，這些案例列為略過。
"""

import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_image_graphs as image_golden  # noqa: E402

from comfyui_pipeline.image_graphs import ICON_ASSET_PROMPT_SUFFIX  # noqa: E402
from comfyui_pipeline.image_template_select import iter_variant_ids, variant_id  # noqa: E402
from comfyui_pipeline.runner import template as T  # noqa: E402

ROOT = Path(image_golden.ROOT)
TEMPLATES = ROOT / "templates"
SIZE_TASKS = frozenset({"concept", "character_action", "pose_only", "style_lock"})
SD15_BLOCKED = frozenset({
    "concept", "concept_lora_style_size", "icon_asset", "icon_asset_lora", "inpaint",
    "guided_inpaint_plain", "refine", "upscale", "concept_remove_bg",
})


def _template_path(template_id):
    return TEMPLATES.joinpath(*template_id.split("/")) / "template.json"


def _flux_present():
    return _template_path("image/flux2/concept").is_file()


def _spec_for(name):
    table = {
        "concept": {"task": "concept"},
        "concept_lora_style_size": {
            "task": "concept", "lora": True,
            "values": {
                "negative": "n", "width": 832, "height": 1216, "batch_size": 2,
                "checkpoint": "juggernautXL_ragnarok.safetensors",
                "lora_name": "test_lora.safetensors", "lora_strength": 0.6,
            },
        },
        "icon_asset": {"task": "icon_asset", "icon": True},
        "icon_asset_lora": {"task": "icon_asset", "icon": True, "lora": True},
        "inpaint": {"task": "inpaint"},
        "guided_inpaint_plain": {"task": "guided_inpaint"},
        "refine": {"task": "refine"},
        "upscale": {"task": "upscale"},
        "layer_split": {"task": "layer_split"},
        "concept_remove_bg": {"task": "concept", "remove_bg": True},
        "flux2_concept": {"task": "flux2_concept"},
        "flux2_edit": {"task": "flux2_edit"},
        "icon_asset_structure_ref": {"task": "icon_asset", "icon": True, "structure_ref": True},
        "icon_asset_appearance_ref": {"task": "icon_asset", "icon": True, "appearance_ref": True},
        "icon_asset_both_refs": {
            "task": "icon_asset", "icon": True, "structure_ref": True, "appearance_ref": True, "lora": True,
        },
        "style_lock": {"task": "style_lock"},
        "style_lock_lora": {"task": "style_lock", "lora": True},
        "guided_inpaint_appearance": {"task": "guided_inpaint", "appearance_ref": True},
        "guided_inpaint_full": {
            "task": "guided_inpaint", "control_type": "pose", "appearance_ref": True, "control_ref": "ctl.png",
        },
        "pose_only_union_depth": {"task": "pose_only", "control_type": "depth", "control_backend": "union"},
    }
    if name in table:
        spec = table[name]
    else:
        spec = None
        for prefix, task in (
            ("character_action_", "character_action"),
            ("pose_only_", "pose_only"),
            ("guided_inpaint_control_", "guided_inpaint"),
        ):
            if name.startswith(prefix):
                control = name[len(prefix):]
                if control in ("canny", "pose", "depth"):
                    spec = {"task": task, "control_type": control}
                    if task == "guided_inpaint":
                        spec["control_ref"] = "img.png"
                break
        if spec is None:
            raise AssertionError(f"沒有對應的 template 規格: {name}")
    if spec.get("lora"):
        spec.setdefault("values", {})
        spec["values"].setdefault("lora_name", "test_lora.safetensors")
        spec["values"].setdefault("lora_strength", 0.6)
    return spec


def _template_id(tier, spec):
    task = spec["task"]
    flags = {
        "lora": spec.get("lora", False),
        "remove_bg": spec.get("remove_bg", False),
        "control_type": spec.get("control_type"),
        "control_backend": spec.get("control_backend", "verified"),
        "structure_ref": spec.get("structure_ref", False),
        "appearance_ref": spec.get("appearance_ref", False),
    }
    if task in ("layer_split", "flux2_concept", "flux2_edit"):
        return variant_id(task)
    family = "sd15" if tier == "sd15" else "sdxl"
    return variant_id(task, family, **flags)


def _uploads(spec):
    task = spec["task"]
    uploads = {}
    if task in ("inpaint", "guided_inpaint", "refine", "upscale", "flux2_edit", "layer_split"):
        uploads["image"] = "img.png"
    if task in ("inpaint", "guided_inpaint", "layer_split"):
        uploads["mask"] = "mask.png"
    if task in ("character_action", "style_lock"):
        uploads["character_ref"] = "char.png"
    if task in ("character_action", "pose_only"):
        uploads["pose_ref"] = "pose.png"
    if spec.get("structure_ref"):
        uploads["structure_ref"] = "tpl.png"
    if spec.get("appearance_ref"):
        uploads["appearance_ref"] = "look.png"
    if spec.get("control_type") and task == "guided_inpaint":
        uploads["control_ref"] = spec.get("control_ref") or "img.png"
    return uploads


def _values(spec, device):
    prompt = "p" + ICON_ASSET_PROMPT_SUFFIX if spec.get("icon") else "p"
    values = {}
    if spec["task"] != "layer_split":
        values["prompt"] = prompt
        values["seed"] = image_golden.SEED
    if spec["task"] in SIZE_TASKS:
        values["width"] = device["default_width"]
        values["height"] = device["default_height"]
    values.update(spec.get("values") or {})
    return values


def _first_diff(actual, expected, path=""):
    if type(actual) is not type(expected):
        return f"{path}: 型別 {type(actual).__name__} vs {type(expected).__name__}（{actual!r} vs {expected!r}）"
    if isinstance(actual, dict):
        if set(actual) != set(expected):
            return f"{path}: 鍵不同 {sorted(set(actual) ^ set(expected))}"
        for key in actual:
            found = _first_diff(actual[key], expected[key], f"{path}.{key}")
            if found:
                return found
        return None
    if isinstance(actual, list):
        if len(actual) != len(expected):
            return f"{path}: 長度 {len(actual)} vs {len(expected)}"
        for index, (left, right) in enumerate(zip(actual, expected)):
            found = _first_diff(left, right, f"{path}[{index}]")
            if found:
                return found
        return None
    if actual != expected:
        return f"{path}: {actual!r} vs {expected!r}"
    return None


def _output_problem(template, builder_out):
    candidates = [item for item in template.data["outputs"] if item["role"] == "candidate"]
    if len(candidates) != 1:
        return f"candidate 數量 {len(candidates)}"
    node_id = candidates[0]["node"]
    if node_id == builder_out:
        return None
    images = template.graph[node_id]["inputs"].get("images")
    if images != [builder_out, 0]:
        return f"candidate {node_id} images={images!r}，builder 輸出 {builder_out}"
    return None


def _patch(template_id, values, uploads):
    template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
    resolution = T.resolve(template, {**uploads, **values}, run_id="image-eq")
    patched, _changes = T.patch(template, resolution, uploads)
    return template, patched


class ImageTemplateEquivalenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ig = image_golden.load_image_graphs()
        cls.fixture = image_golden.load_fixture()

    def test_selector_counts_and_required_directories(self):
        self.assertEqual(72, len(iter_variant_ids("sdxl")))
        self.assertEqual(13, len(iter_variant_ids("sd15")))
        self.assertEqual(1, len(iter_variant_ids("layer_split")))
        self.assertEqual(2, len(iter_variant_ids("flux2")))
        for template_id in iter_variant_ids("sdxl", "layer_split"):
            self.assertTrue(_template_path(template_id).is_file(), template_id)
        self.assertFalse(_template_path("image/sd15/concept").is_file())
        present = _flux_present()
        for template_id in iter_variant_ids("flux2"):
            self.assertEqual(present, _template_path(template_id).is_file(), template_id)

    def test_image_templates_keep_builder_prefix_and_null_alignment(self):
        for template_id in iter_variant_ids("sdxl", "layer_split") + (
            iter_variant_ids("flux2") if _flux_present() else []
        ):
            template = T.load_template(TEMPLATES, template_id, repo_root=ROOT)
            self.assertIsNone(template.data["frame_anchoring"]["time_alignment"], template_id)
            self.assertEqual("draft", template.data["status"], template_id)
            for name, slot in template.slots.items():
                self.assertNotEqual("output_prefix", slot["type"], f"{template_id}.{name}")
            prefix = template.slots["filename_prefix"]
            self.assertEqual("string", prefix["type"], template_id)
            self.assertFalse(str(prefix["default"]).startswith("gameart/"), template_id)

    def test_golden_cases_match_template_patch(self):
        matched, skipped = [], []
        for tier, device in image_golden.TIER_DEVICES.items():
            self.ig.DEVICE = dict(device)
            self.ig.CKPT = device["checkpoint"]
            self.ig.ACTIVE_PROFILE_ID = None
            base, sdxl_only = image_golden._cases(self.ig)
            cases = base + (sdxl_only if tier != "sd15" else [])
            for name, build in cases:
                spec = _spec_for(name)
                template_id = _template_id(tier, spec)
                if not _template_path(template_id).is_file():
                    if tier == "sd15" and name in SD15_BLOCKED:
                        skipped.append((tier, name))
                        continue
                    if name.startswith("flux2") and not _flux_present():
                        skipped.append((tier, name))
                        continue
                    self.fail(f"缺少 template {template_id}（{tier}/{name}）")
                graph, builder_out = build()
                values = _values(spec, device)
                uploads = _uploads(spec)
                template, patched = _patch(template_id, values, uploads)
                fixture_graph, fixture_out = self.fixture[tier][name]
                with self.subTest(tier=tier, case=name):
                    self.assertIsNone(_first_diff(patched, graph), _first_diff(patched, graph))
                    self.assertIsNone(_first_diff(patched, fixture_graph), _first_diff(patched, fixture_graph))
                    self.assertEqual(builder_out, fixture_out)
                    self.assertIsNone(_output_problem(template, builder_out))
                matched.append((tier, name))
        flux_skipped = [item for item in skipped if item[1].startswith("flux2")]
        sd15_skipped = [item for item in skipped if item[0] == "sd15" and item[1] in SD15_BLOCKED]
        if _flux_present():
            self.assertEqual([], flux_skipped)
        else:
            self.assertEqual(8, len(flux_skipped))
        self.assertEqual(9, len(sd15_skipped))
        self.assertEqual(len(matched) + len(skipped), 99)

    def test_every_written_variant_matches_builder_defaults(self):
        groups = ["sdxl", "layer_split"] + (["flux2"] if _flux_present() else [])
        from comfyui_pipeline.image_template_select import iter_variants

        for spec in iter_variants(*groups):
            family = spec["family"] or "sdxl"
            device = image_golden.TIER_DEVICES["sd15" if family == "sd15" else "sdxl"]
            self.ig.DEVICE = dict(device)
            self.ig.CKPT = device["checkpoint"]
            self.ig.ACTIVE_PROFILE_ID = None
            graph, builder_out = _build_default(self.ig, spec)
            case_spec = {
                "task": spec["task"],
                "lora": spec["lora"],
                "icon": spec["task"] == "icon_asset",
                "structure_ref": spec["structure_ref"],
                "appearance_ref": spec["appearance_ref"],
                "control_type": spec["control_type"],
                "control_ref": "ctl.png" if spec["control_type"] and spec["task"] == "guided_inpaint" else None,
            }
            if spec["lora"]:
                case_spec["values"] = {"lora_name": "test_lora.safetensors"}
            values = _values(case_spec, device)
            if spec["task"] in SIZE_TASKS:
                values.pop("width", None)
                values.pop("height", None)
            uploads = _uploads(case_spec)
            template, patched = _patch(spec["id"], values, uploads)
            with self.subTest(template=spec["id"]):
                self.assertIsNone(_first_diff(patched, graph))
                self.assertIsNone(_output_problem(template, builder_out))


def _build_default(ig, spec):
    task = spec["task"]
    lora_name = "test_lora.safetensors" if spec["lora"] else None
    seed = image_golden.SEED
    if task == "concept":
        graph, image_node = ig.build_concept("p", seed=seed, lora_name=lora_name)
    elif task == "icon_asset":
        graph, image_node = ig.build_icon_asset(
            "p", seed=seed, lora_name=lora_name,
            structure_ref_filename="tpl.png" if spec["structure_ref"] else None,
            appearance_ref_filename="look.png" if spec["appearance_ref"] else None,
        )
    elif task == "refine":
        graph, image_node = ig.build_refine("p", "img.png", seed=seed)
    elif task == "inpaint":
        graph, image_node = ig.build_inpaint("p", "img.png", "mask.png", seed=seed)
    elif task == "guided_inpaint":
        kwargs = {}
        if spec["control_type"]:
            kwargs["control_type"] = spec["control_type"]
            kwargs["control_ref_filename"] = "ctl.png"
        if spec["appearance_ref"]:
            kwargs["appearance_ref_filename"] = "look.png"
        graph, image_node = ig.build_guided_inpaint("p", "img.png", "mask.png", seed=seed, **kwargs)
    elif task == "character_action":
        graph, image_node = ig.build_character_action(
            "p", "char.png", "pose.png", seed=seed, control_type=spec["control_type"], lora_name=lora_name,
        )
    elif task == "pose_only":
        graph, image_node = ig.build_pose_only(
            "p", "pose.png", seed=seed, control_type=spec["control_type"],
            control_backend=spec["control_backend"], lora_name=lora_name,
        )
    elif task == "style_lock":
        graph, image_node = ig.build_style_lock("p", "char.png", seed=seed, lora_name=lora_name)
    elif task == "upscale":
        graph, image_node = ig.build_upscale("p", "img.png", seed=seed)
    elif task == "layer_split":
        graph, image_node = ig.build_layer_split("img.png", "mask.png", "frame")
    elif task == "flux2_concept":
        graph, image_node = ig.build_flux2_concept("p", seed=seed)
    elif task == "flux2_edit":
        graph, image_node = ig.build_flux2_edit("p", "img.png", seed=seed)
    else:
        raise AssertionError(task)
    if spec["remove_bg"]:
        image_node = ig.attach_bg_removal(graph, image_node)
    return graph, image_node


if __name__ == "__main__":
    unittest.main()
