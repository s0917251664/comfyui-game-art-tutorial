"""PR 4.1 原型的等價測試:方案 A(variant template)與方案 B(option ops)產生的 graph,
要和 99 組圖片 golden 的相關子集逐欄位相同(D13 的判準)。

原型放在 templates/_drafts/image-variants/(runner 不收錄);方案 A 只用現有 runner,
方案 B 用同資料夾的 option_ops.py(runner 擴充的原型)。``python tests/test_image_variant_drafts.py --report``
印出案例數。
"""
import copy
import itertools
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DRAFTS = ROOT / "templates" / "_drafts" / "image-variants"
for path in (ROOT / "tools_src", ROOT / "tests", DRAFTS):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from comfyui_pipeline.runner import template as T  # noqa: E402
import build_drafts  # noqa: E402
import golden_image_graphs as golden  # noqa: E402
import option_ops  # noqa: E402

A_ROOT, B_ROOT = DRAFTS / "a", DRAFTS / "b"
TEMPLATES = ROOT / "templates"
POSE = {"pose_ref": "pose.png"}
LORA = {"lora_name": "test_lora.safetensors", "lora_strength": 0.6}

# golden case → (task, 結構參數, slot 值, 上傳)。值和 tests/golden_image_graphs.py 的 _cases 相同。
GOLDEN_CASES = {
    "concept": ("concept", {}, {"prompt": "p"}, {}),
    "concept_lora_style_size": ("concept", {"lora": True}, dict(
        prompt="p", negative="n", width=832, height=1216, batch_size=2,
        checkpoint="juggernautXL_ragnarok.safetensors", **LORA), {}),
    "concept_remove_bg": ("concept", {"remove_bg": True}, {"prompt": "p"}, {}),
    "pose_only_canny": ("pose_only", {"control_type": "canny"}, {"prompt": "p"}, POSE),
    "pose_only_pose": ("pose_only", {"control_type": "pose"}, {"prompt": "p"}, POSE),
    "pose_only_depth": ("pose_only", {"control_type": "depth"}, {"prompt": "p"}, POSE),
    "pose_only_union_depth": ("pose_only", {"control_type": "depth", "control_backend": "union"}, {"prompt": "p"}, POSE),
}
EXPECTED_GOLDEN_CASES = 24  # concept 3 案例 × 4 tier + pose_only 4 案例 × 3 個 SDXL tier


def family(tier):
    return "sd15" if tier == "sd15" else "sdxl"


def with_tier_values(tier, values):
    """呼叫端(第 5 階段的薄轉接)把 tier 的預設解析度明確傳入;seed 和 golden 一樣固定。"""
    device = golden.TIER_DEVICES[tier]
    merged = {"seed": golden.SEED, "width": device["default_width"], "height": device["default_height"]}
    merged.update(values)
    return merged


def b_choices(task, params):
    if task == "concept":
        return {"lora": "on" if params.get("lora") else "off", "remove_bg": "on" if params.get("remove_bg") else "off"}
    control = ("union_" if params.get("control_backend") == "union" else "") + params.get("control_type", "canny")
    return {"control": control, "lora": "on" if params.get("lora") else "off"}


def b_id(fam, task):
    return f"image/{fam}/" + ("concept" if task == "concept" else "pose-only")


def build_a(fam, task, params, values, uploads):
    template = T.load_template(A_ROOT, build_drafts.a_id(fam, task, **params), repo_root=ROOT)
    # 上傳 slot 的值是本機路徑(resolve 用),upload_paths 是上傳後 ComfyUI 端的名稱(patch 用);這裡兩者相同
    resolution = T.resolve(template, {**values, **uploads}, run_id="golden")
    graph, _ = T.patch(template, resolution, uploads)
    return graph, template.data["outputs"], template


def build_b(fam, task, params, values, uploads):
    vt = option_ops.load(B_ROOT, b_id(fam, task), ROOT)
    built = option_ops.build(vt, {**values, **uploads}, b_choices(task, params), uploads, run_id="golden")
    return built["graph"], built["outputs"], built


def output_matches(graph, outputs, builder_out):
    """builder 回傳的是「圖片節點」;template 宣告的是要下載的 SaveImage。兩者要指向同一張圖。"""
    node = next(o["node"] for o in outputs if o["role"] == "candidate")
    if node == builder_out:
        return True
    save = graph[node]
    return save["class_type"] == "SaveImage" and save["inputs"]["images"] == [builder_out, 0]


def canonical(graph):
    """逐欄位比較(含 int/float 型別):JSON 字串化後比對。"""
    return json.dumps(graph, sort_keys=True, ensure_ascii=False)


class ImageGraphs:
    """暫時切換 image_graphs 的 DEVICE,結束後還原(和 golden_image_graphs.build_all 相同的做法)。"""

    @classmethod
    def setUpClass(cls):
        cls.ig = golden.load_image_graphs()
        cls._saved = (copy.deepcopy(cls.ig.DEVICE), cls.ig.CKPT)

    @classmethod
    def tearDownClass(cls):
        cls.ig.DEVICE, cls.ig.CKPT = cls._saved

    def builder(self, tier, task, params, values, uploads):
        ig = self.ig
        device = golden.TIER_DEVICES[tier]
        ig.DEVICE, ig.CKPT = dict(device), device["checkpoint"]
        kwargs = {k: values[k] for k in ("negative", "width", "height", "seed", "steps", "cfg") if k in values}
        if "batch_size" in values:
            kwargs["batch_size"] = values["batch_size"]
        if "checkpoint" in values:
            kwargs["checkpoint"] = values["checkpoint"]
        if params.get("lora"):
            kwargs.update(lora_name=values["lora_name"], lora_strength=values["lora_strength"])
        if task == "concept":
            graph, out = ig.build_concept(values["prompt"], **kwargs)
        else:
            graph, out = ig.build_pose_only(values["prompt"], uploads["pose_ref"], control_type=params.get("control_type", "canny"),
                                            control_backend=params.get("control_backend", "verified"), **kwargs)
        if params.get("remove_bg"):
            out = ig.attach_bg_removal(graph, out)
        return graph, out


def golden_subset():
    fixture = golden.load_fixture()
    for tier, cases in fixture.items():
        for case, (task, params, values, uploads) in GOLDEN_CASES.items():
            if case in cases:
                yield tier, case, task, params, with_tier_values(tier, values), uploads, cases[case]


class DraftLayoutTests(unittest.TestCase):
    def test_drafts_are_not_discovered_by_runner(self):
        self.assertFalse([tid for tid in T.discover(TEMPLATES) if "_drafts" in tid or tid.startswith("image/")])

    def test_drafts_match_generator(self):
        files = build_drafts.render()
        self.assertEqual(49, len(files))
        for rel, raw in files.items():
            with self.subTest(rel):
                self.assertEqual(raw, (DRAFTS / rel).read_bytes(), f"{rel} 和 build_drafts.py 產生的不同")

    def test_drafts_are_byte_exact_in_git(self):
        self.assertIn("templates/** -text", (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines())

    def test_scheme_a_templates_load_with_current_runner(self):
        ids = [tid for tid, *_ in build_drafts.a_variants()]
        self.assertEqual(sorted(ids), T.discover(A_ROOT))
        self.assertEqual(20, len(ids))
        for template_id in ids:
            with self.subTest(template_id):
                template = T.load_template(A_ROOT, template_id, repo_root=ROOT)
                self.assertEqual({}, template.options)

    def test_scheme_b_base_graph_is_scheme_a_plain_graph(self):
        for base_id, *_ in build_drafts.b_specs():
            a_id = base_id.replace("pose-only", "pose-only-canny")
            with self.subTest(base_id):
                self.assertEqual((A_ROOT / a_id / "graph.api.json").read_bytes(),
                                 (B_ROOT / base_id / "graph.api.json").read_bytes())


class GoldenEquivalenceTests(ImageGraphs, unittest.TestCase):
    """判準:99 組 golden 的相關子集,兩個方案都要逐欄位相同。"""

    def check(self, build):
        count = 0
        for tier, case, task, params, values, uploads, (want_graph, want_out) in golden_subset():
            with self.subTest(tier=tier, case=case):
                graph, outputs, _ = build(family(tier), task, params, values, uploads)
                self.assertEqual(canonical(want_graph), canonical(graph))
                self.assertTrue(output_matches(graph, outputs, want_out))
                count += 1
        self.assertEqual(EXPECTED_GOLDEN_CASES, count)

    def test_scheme_a_matches_golden(self):
        self.check(build_a)

    def test_scheme_b_matches_golden(self):
        self.check(build_b)

    def test_profile_as_slot_values_also_matches_but_loses_pins(self):
        """Q2 的另一案:sd15 不另做 template,用 sdxl template 加 checkpoint／解析度的值。graph 相同,
        但 template 的模型 pin 仍是 SDXL 底模,preflight 會檢查錯的檔案(見 ADR)。"""
        count = 0
        for tier, case, task, params, values, uploads, (want_graph, _out) in golden_subset():
            if tier != "sd15":
                continue
            values = dict(values)
            values.setdefault("checkpoint", golden.TIER_DEVICES["sd15"]["checkpoint"])
            graph, _outputs, template = build_a("sdxl", task, params, values, uploads)
            self.assertEqual(canonical(want_graph), canonical(graph))
            pinned = {m["role"]: m["filename"] for m in template.data["models"]}
            self.assertEqual(golden.TIER_DEVICES["sdxl"]["checkpoint"], pinned["checkpoint"])
            self.assertNotEqual(pinned["checkpoint"], graph["1"]["inputs"]["ckpt_name"])
            count += 1
        self.assertEqual(3, count)


class FullCombinationTests(ImageGraphs, unittest.TestCase):
    """golden 沒涵蓋的組合(例如 LoRA＋去背、Union＋LoRA)也直接和 builder 比。"""

    VALUES = dict(prompt="p", negative="n", batch_size=2, steps=30, cfg=6.5, **LORA)

    def tiers(self, fam):
        return ["sd15"] if fam == "sd15" else ["sdxl_high", "sdxl", "sdxl_light"]

    def values_for(self, tier, params):
        values = with_tier_values(tier, self.VALUES)
        if not params.get("lora"):
            values.pop("lora_name"), values.pop("lora_strength")
        return values

    def test_every_scheme_a_variant_matches_builder(self):
        count = 0
        for _tid, fam, task, params in build_drafts.a_variants():
            uploads = POSE if task == "pose_only" else {}
            for tier in self.tiers(fam):
                values = self.values_for(tier, params)
                with self.subTest(tier=tier, task=task, **params):
                    want, out = self.builder(tier, task, params, values, uploads)
                    graph, outputs, _ = build_a(fam, task, params, values, uploads)
                    self.assertEqual(canonical(want), canonical(graph))
                    self.assertTrue(output_matches(graph, outputs, out))
                    count += 1
        self.assertEqual(4 * 3 + 4 * 1 + 12 * 3, count)

    def test_every_scheme_b_combination_matches_builder(self):
        count = 0
        for base_id, fam, task, options in build_drafts.b_specs():
            uploads = POSE if task == "pose_only" else {}
            names = list(options)
            for combo in itertools.product(*(options[n].items() for n in names)):
                params = {}
                for _choice, choice_params in combo:
                    params.update(choice_params)
                for tier in self.tiers(fam):
                    values = self.values_for(tier, params)
                    with self.subTest(base=base_id, tier=tier, combo=[c for c, _ in combo]):
                        want, out = self.builder(tier, task, params, values, uploads)
                        graph, outputs, built = build_b(fam, task, params, values, uploads)
                        self.assertEqual(canonical(want), canonical(graph))
                        self.assertTrue(output_matches(graph, outputs, out))
                        self.assertEqual(build_a(fam, task, params, values, uploads)[2].data["models"], built["models"])
                        count += 1
        self.assertEqual(4 * 3 + 4 * 1 + 12 * 3, count)


class OptionOpsGuardTests(unittest.TestCase):
    """方案 B 的 helper 要守住 R2:沒宣告的結構變化一律拒絕。"""

    def setUp(self):
        self.vt = option_ops.load(B_ROOT, "image/sdxl/concept", ROOT)

    def test_unknown_choice_rejected(self):
        with self.assertRaises(T.TemplateError):
            option_ops.build(self.vt, {"prompt": "p"}, {"lora": "maybe"})

    def test_option_slot_required_only_when_chosen(self):
        option_ops.build(self.vt, {"prompt": "p"}, {"lora": "off"})
        with self.assertRaises(T.TemplateError) as ctx:
            option_ops.build(self.vt, {"prompt": "p"}, {"lora": "on"})
        self.assertIn("lora_name", str(ctx.exception))

    def test_two_options_touching_same_input_rejected(self):
        spec = copy.deepcopy(self.vt.spec)
        spec["options"]["remove_bg"]["choices"]["on"]["ops"].append(
            {"op": "relink", "node": "5", "input": "model", "from": ["1", 0]})
        problems = option_ops.validate_spec(self.vt.base, spec)
        self.assertTrue(any("衝突" in p for p in problems), problems)

    def test_replace_node_conflict_found_regardless_of_order(self):
        vt = option_ops.load(B_ROOT, "image/sdxl/pose-only", ROOT)
        for first in ("lora", "control"):
            spec = copy.deepcopy(vt.spec)
            # LoRA 改 5.image(先或後於 control 的 replace_node 5)
            spec["options"]["lora"]["choices"]["on"]["ops"].append(
                {"op": "relink", "node": "5", "input": "image", "from": ["4", 0]})
            order = [first] + [o for o in spec["options"] if o != first]
            spec["options"] = {o: spec["options"][o] for o in order}
            with self.subTest(first=first):
                problems = option_ops.validate_spec(vt.base, spec)
                self.assertTrue(any("衝突" in p for p in problems), problems)

    def test_set_value_link_to_other_option_node_rejected(self):
        spec = copy.deepcopy(self.vt.spec)
        spec["options"]["remove_bg"]["choices"]["on"]["ops"].append(
            {"op": "set_value", "node": "7", "input": "images", "value": ["1b", 0]})
        problems = option_ops.validate_spec(self.vt.base, spec)
        self.assertTrue(any("1b" in p for p in problems), problems)

    def test_two_options_replacing_outputs_rejected(self):
        spec = copy.deepcopy(self.vt.spec)
        spec["options"]["lora"]["choices"]["on"]["outputs"] = self.vt.base.data["outputs"]
        problems = option_ops.validate_spec(self.vt.base, spec)
        self.assertTrue(any("outputs" in p for p in problems), problems)

    def test_fragment_placeholder_must_be_claimed(self):
        spec = copy.deepcopy(self.vt.spec)
        del spec["options"]["lora"]["choices"]["on"]["slots"]["lora_name"]
        problems = option_ops.validate_spec(self.vt.base, spec)
        self.assertTrue(any("__LORA_NAME__" in p for p in problems), problems)

    def test_undeclared_node_rejected_after_patch(self):
        graph = option_ops.build(self.vt, {"prompt": "p"})["graph"]
        graph["99"] = {"class_type": "SaveImage", "inputs": {"images": ["6", 0], "filename_prefix": "x"}}
        with self.assertRaises(T.TemplateError) as ctx:
            option_ops._check(self.vt, graph, None, set(), set(), set())
        self.assertIn("沒有宣告的節點", str(ctx.exception))


def report():
    """案例數摘要(給證據檔用)。"""
    fixture = golden.load_fixture()
    total = sum(len(cases) for cases in fixture.values())
    subset = list(golden_subset())
    return {"golden_total": total, "golden_subset": len(subset),
            "subset_cases": sorted({case for _t, case, *_ in subset}),
            "scheme_a_templates": len(build_drafts.a_variants()),
            "scheme_b_templates": len(build_drafts.b_specs())}


if __name__ == "__main__":
    if "--report" in sys.argv:
        print(json.dumps(report(), ensure_ascii=False, indent=2))
        sys.exit(0)
    unittest.main()
