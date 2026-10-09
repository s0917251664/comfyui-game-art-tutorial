"""圖片 task 的 template 轉接測試。

第 5.1 階段：concept、icon_asset、refine、character_action、pose_only、style_lock。
第 5.2 階段：inpaint、guided_inpaint、upscale、layer_split、flux2_concept、flux2_edit。
送出的 graph 與 tests/fixtures/image_graphs_golden/ 凍結的 graph（舊 Python builder 的最後輸出）逐欄相同;
builder 已移除，fixture 不再重新產生。沒有凍結案例的組合只檢查結構（去背輸出、前綴、manifest）。
templates/ 是唯一來源:找不到 template 就停止，不退回其他路徑。
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_image_graphs as image_golden  # noqa: E402

from comfyui_pipeline import image_from_template, image_graphs, image_results, tasks  # noqa: E402
from comfyui_pipeline.context import RunContext  # noqa: E402
from comfyui_pipeline.tasks import control, flux2, image_basic, inpaint, layer, upscale  # noqa: E402

SEED = image_golden.SEED
LORA = "test_lora.safetensors"
STYLE_CKPT = "juggernautXL_ragnarok.safetensors"


def _ns(**kwargs):
    return SimpleNamespace(**kwargs)


def _ctx(device, profile=None):
    return RunContext(device=dict(device), active_image_profile=profile)


def _concept(**kwargs):
    values = dict(task="concept", prompt="p", negative=None, width=None, height=None,
                  seed=SEED, batch=1, lora=None, lora_strength=0.8, remove_bg=False)
    values.update(kwargs)
    return _ns(**values)


def _icon(**kwargs):
    values = dict(task="icon_asset", prompt="p", negative=None, width=None, height=None,
                  seed=SEED, batch=1, lora=None, lora_strength=0.8,
                  structure_ref=None, appearance_ref=None, appearance_weight=0.8)
    values.update(kwargs)
    return _ns(**values)


def _refine(**kwargs):
    values = dict(task="refine", prompt="p", negative=None, image="img.png",
                  denoise=0.6, seed=SEED, remove_bg=False)
    values.update(kwargs)
    return _ns(**values)


def _character(**kwargs):
    values = dict(task="character_action", prompt="p", negative=None, width=None, height=None,
                  seed=SEED, batch=1, lora=None, lora_strength=0.8, remove_bg=False,
                  character_ref="char.png", pose_ref="pose.png",
                  ip_weight=0.8, pose_strength=1.0, control_type="canny")
    values.update(kwargs)
    return _ns(**values)


def _pose(**kwargs):
    values = dict(task="pose_only", prompt="p", negative=None, width=None, height=None,
                  seed=SEED, batch=1, lora=None, lora_strength=0.8, remove_bg=False,
                  pose_ref="pose.png", pose_strength=1.0, control_type="canny",
                  control_backend="verified")
    values.update(kwargs)
    return _ns(**values)


def _style(**kwargs):
    values = dict(task="style_lock", prompt="p", negative=None, width=None, height=None,
                  seed=SEED, batch=1, lora=None, lora_strength=0.8, remove_bg=False,
                  character_ref="char.png", ip_weight=0.8)
    values.update(kwargs)
    return _ns(**values)


def _inpaint(**kwargs):
    values = dict(task="inpaint", prompt="p", negative=None, image="img.png", mask="mask.png",
                  denoise=1.0, seed=SEED)
    values.update(kwargs)
    return _ns(**values)


def _guided(**kwargs):
    values = dict(task="guided_inpaint", prompt="p", negative=None, image="img.png", mask="mask.png",
                  control_ref=None, control_type=None, control_strength=1.0, appearance_ref=None,
                  appearance_weight=0.8, denoise=1.0, seed=SEED)
    values.update(kwargs)
    return _ns(**values)


def _upscale(**kwargs):
    values = dict(task="upscale", prompt="p", negative=None, image="img.png",
                  scale=2.0, denoise=0.4, seed=SEED)
    values.update(kwargs)
    return _ns(**values)


def _layer(**kwargs):
    values = dict(task="layer_split", image="img.png", mask="mask.png", layer_name="frame")
    values.update(kwargs)
    return _ns(**values)


def _flux_concept(**kwargs):
    values = dict(task="flux2_concept", prompt="p", width=1024, height=1024, seed=SEED)
    values.update(kwargs)
    return _ns(**values)


def _flux_edit(**kwargs):
    values = dict(task="flux2_edit", prompt="p", image="img.png", seed=SEED)
    values.update(kwargs)
    return _ns(**values)


class ImageTaskTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ig = image_graphs
        cls.fixture = image_golden.load_fixture()

    def tearDown(self):
        self.ig.ACTIVE_PROFILE_ID = None

    def _submit(self, ctx, args, style_checkpoint=None):
        graph, image_node = tasks.build_image_task_graph(ctx, args, style_checkpoint, lambda path: path)
        download_id = None
        if image_from_template.wants_background_removal(args):
            download_id = image_from_template.background_removal_output(graph, image_node)
            # 第二次必須是 no-op，否則 -transparent 會再長一顆 RemoveBackground，sha256 就變了。
            again = image_from_template.background_removal_output(graph, image_node)
            self.assertEqual(download_id, again)
        return graph, image_node, download_id

    def _assert_same_submission(self, ctx, args, style_checkpoint=None, fixture=None):
        wants_bg = image_from_template.wants_background_removal(args)
        changed = []
        real_align = image_from_template._align_baked_sampling

        def spy(graph, sampling, _real=real_align):
            found = _real(graph, sampling)
            changed.append(found)
            return found

        with mock.patch.object(image_from_template, "_align_baked_sampling", spy):
            graph, image_node, download_id = self._submit(ctx, args, style_checkpoint)
        # template 路徑才會對齊烤進去的 sampler。目前是空清單：euler／normal 已相同，不必再改欄位。
        self.assertEqual([[]], changed)
        if wants_bg:
            transparent = [
                node_id for node_id, node in graph.items()
                if node.get("class_type") == "SaveImage"
                and (node.get("inputs") or {}).get("filename_prefix") == "transparent"
            ]
            self.assertEqual([download_id], transparent)
            self.assertEqual(1, sum(1 for node in graph.values() if node.get("class_type") == "RemoveBackground"))
        else:
            self.assertIsNone(download_id)
            self.assertIsNone(image_from_template.transparent_save_id(graph))
        prefixes = [
            (node.get("inputs") or {}).get("filename_prefix")
            for node in graph.values() if node.get("class_type") == "SaveImage"
        ]
        self.assertIn(image_from_template._filename_prefix(args), prefixes)
        if fixture is not None:
            fixture_graph, fixture_out = fixture
            self.assertEqual(fixture_graph, graph)
            self.assertEqual(fixture_out, download_id if wants_bg else image_node)
        manifest_kwargs = dict(
            task=args.task, profile_id=ctx.active_image_profile, backend="cuda",
            prompt_id="prompt-1", inputs=[], outputs=[], args=args,
        )
        right = image_results.make_manifest(graph=graph, **manifest_kwargs)
        self.assertEqual("image_generation_result", right["kind"])
        self.assertEqual("pending", right["content_review"])
        self.assertEqual(image_results.graph_sha256(graph), right["graph_sha256"])

    def test_sdxl_submissions_match_golden(self):
        # patch 後的 graph 已與 builder 逐欄相同，不另改欄位。原因寫在這個測試的檔頭。
        device = image_golden.TIER_DEVICES["sdxl"]
        ctx = _ctx(device)
        cases = [
            ("concept", _concept(), None),
            ("concept_lora_style_size", _concept(
                negative="n", width=832, height=1216, batch=2, lora=LORA, lora_strength=0.6,
            ), STYLE_CKPT),
            ("concept_remove_bg", _concept(remove_bg=True), None),
            ("refine", _refine(), None),
            ("style_lock", _style(), None),
            ("style_lock_lora", _style(lora=LORA, lora_strength=0.6), None),
            ("pose_only_union_depth", _pose(control_type="depth", control_backend="union"), None),
        ]
        for control_type in ("canny", "pose", "depth"):
            cases.append((f"character_action_{control_type}", _character(control_type=control_type), None))
            cases.append((f"pose_only_{control_type}", _pose(control_type=control_type), None))
        # icon 的 golden 是 builder、還沒接去背。CLI 一定去背，比對對象是 builder 再接去背。
        icon_cases = [
            _icon(),
            _icon(lora=LORA, lora_strength=0.6),
            _icon(structure_ref="tpl.png"),
            _icon(appearance_ref="look.png"),
            _icon(structure_ref="tpl.png", appearance_ref="look.png", lora=LORA, lora_strength=0.6),
            _icon(negative="n"),
            _icon(width=832),
            _icon(remove_bg=False),
        ]
        for name, args, style in cases:
            with self.subTest(case=name):
                self._assert_same_submission(ctx, args, style, self.fixture["sdxl"][name])
        for args in icon_cases:
            with self.subTest(task="icon_asset", structure=args.structure_ref, appearance=args.appearance_ref,
                              lora=args.lora, width=args.width, negative=args.negative):
                self._assert_same_submission(ctx, args, None)

    def test_omitted_seed_is_drawn_once(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        args = _concept(seed=None)
        with mock.patch.object(image_graphs, "seed_or_random", return_value=12345) as drawn:
            graph, _image_node = image_from_template.graph_from_template(ctx, args, None, lambda path: path)
        self.assertEqual(1, drawn.call_count)
        self.assertEqual([None], [call.args[0] for call in drawn.call_args_list])
        seeds = [
            node["inputs"]["seed"] for node in graph.values()
            if node.get("class_type") == "KSampler"
        ]
        self.assertEqual([12345], seeds)

    def test_seed_zero_and_partial_size(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        self._assert_same_submission(ctx, _concept(seed=0, width=640))
        self._assert_same_submission(ctx, _pose(seed=0, height=768))
        self._assert_same_submission(ctx, _refine(seed=0, denoise=0.35, remove_bg=True))
        self._assert_same_submission(ctx, _character(remove_bg=True, lora=LORA))
        self._assert_same_submission(ctx, _style(remove_bg=True))

    def test_sdxl_light_icon_stays_native_and_concept_uses_device_size(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl_light"])
        self._assert_same_submission(ctx, _concept())
        self._assert_same_submission(ctx, _icon())
        concept, _, _ = self._submit(ctx, _concept())
        icon, _, _ = self._submit(ctx, _icon())
        self.assertEqual((768, 768), (concept["4"]["inputs"]["width"], concept["4"]["inputs"]["height"]))
        latent = next(node for node in icon.values() if node["class_type"] == "EmptyLatentImage")
        self.assertEqual((1024, 1024), (latent["inputs"]["width"], latent["inputs"]["height"]))

    def test_missing_template_stops_instead_of_using_builder(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        missing = Path("missing-template.json")
        cases = [
            (control.build_graph, _pose()),
            (image_basic.build_graph, _concept()),
            (inpaint.build_graph, _inpaint()),
            (inpaint.build_graph, _guided(control_type="pose", appearance_ref="look.png")),
            (upscale.build_graph, _upscale()),
            (layer.build_graph, _layer(layer_name="border")),
            (flux2.build_graph, _flux_concept()),
            (flux2.build_graph, _flux_edit()),
        ]
        with mock.patch.object(image_from_template, "_template_json", return_value=missing):
            for build, args in cases:
                with self.subTest(task=args.task):
                    uploads = []

                    def upload(path, _uploads=uploads):
                        _uploads.append(path)
                        return path

                    with self.assertRaises(SystemExit):
                        build(ctx, args, None, upload)
                    self.assertEqual([], uploads)

    def test_phase52_submissions_match_golden(self):
        # 第 5.2 不再斷言這六個 task 會呼叫 image_runtime builder。
        # 送出的 graph 仍須與 builder(同等參數) 逐欄相同，所以舊斷言改成這件事。
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        fixture = self.fixture["sdxl"]
        cases = [
            (_inpaint(), "inpaint"),
            (_guided(), "guided_inpaint_plain"),
            (_guided(appearance_ref="look.png"), "guided_inpaint_appearance"),
            (_guided(control_type="pose", control_ref="ctl.png", appearance_ref="look.png"),
             "guided_inpaint_full"),
            (_upscale(), "upscale"),
            (_layer(), "layer_split"),
            (_flux_concept(), "flux2_concept"),
            (_flux_edit(), "flux2_edit"),
        ]
        for control_type in ("canny", "pose", "depth"):
            cases.append((_guided(control_type=control_type), f"guided_inpaint_control_{control_type}"))
        for args, name in cases:
            with self.subTest(case=name):
                self._assert_same_submission(ctx, args, None, fixture[name])
        extras = [
            _inpaint(negative="n", denoise=0.55, seed=0),
            _inpaint(seed=0),
            _guided(control_type="canny", control_strength=0.4, denoise=0.7),
            _guided(control_type="depth", control_ref="ctl.png", appearance_ref="look.png",
                    appearance_weight=0.3, control_strength=0.6, negative="n"),
            _upscale(scale=4.0, denoise=0.2, negative="n", seed=0),
            _layer(layer_name="center_hub"),
            _flux_concept(width=768, height=1280, seed=0),
            _flux_edit(seed=0),
        ]
        for args in extras:
            with self.subTest(task=args.task, layer=getattr(args, "layer_name", None),
                              control=getattr(args, "control_type", None),
                              width=getattr(args, "width", None)):
                self._assert_same_submission(ctx, args, STYLE_CKPT if args.task != "layer_split" else None)

    def test_none_seed_is_drawn_once(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        drawn = []

        def fake(seed):
            drawn.append(seed)
            return 424242

        specs = [
            (_inpaint(seed=None), "7", "seed"),
            (_guided(seed=None, control_type="pose"), "12", "seed"),
            (_upscale(seed=None), "9", "seed"),
            (_flux_concept(seed=None), "7", "noise_seed"),
            (_flux_edit(seed=None), "13", "noise_seed"),
        ]
        for args, node_id, field in specs:
            drawn.clear()
            with self.subTest(task=args.task):
                with mock.patch.object(image_graphs, "seed_or_random", fake):
                    graph, _out = tasks.build_image_task_graph(ctx, args, None, lambda path: path)
                self.assertEqual([None], drawn)
                self.assertEqual(424242, graph[node_id]["inputs"][field])
                filled = args
                filled.seed = 424242
                self._assert_same_submission(ctx, filled)

        drawn.clear()
        with mock.patch.object(image_graphs, "seed_or_random", fake):
            tasks.build_image_task_graph(ctx, _layer(), None, lambda path: path)
        self.assertEqual([], drawn)

    def test_uploaded_names_are_patched_and_control_reuses_source(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        seen = {}
        real_resolve = image_from_template.runner_template.resolve
        real_patch = image_from_template.runner_template.patch

        def spy_resolve(template, values=None, **kwargs):
            seen["resolve"] = dict(values or {})
            return real_resolve(template, values, **kwargs)

        def spy_patch(template, resolution, upload_paths=None, **kwargs):
            seen["uploads"] = dict(upload_paths or {})
            return real_patch(template, resolution, upload_paths, **kwargs)

        calls = []

        def upload(path):
            calls.append(path)
            return "input/" + path

        args = _guided(control_type="canny", appearance_ref="look.png")
        with mock.patch.object(image_from_template.runner_template, "resolve", spy_resolve), \
                mock.patch.object(image_from_template.runner_template, "patch", spy_patch):
            graph, out_id = inpaint.build_graph(ctx, args, None, upload)
        self.assertEqual(["img.png", "mask.png", "look.png"], calls)
        self.assertEqual("img.png", seen["resolve"]["image"])
        self.assertEqual("img.png", seen["resolve"]["control_ref"])
        self.assertEqual("look.png", seen["resolve"]["appearance_ref"])
        self.assertNotIn("input/", seen["resolve"]["image"])
        self.assertEqual({
            "image": "input/img.png",
            "mask": "input/mask.png",
            "control_ref": "input/img.png",
            "appearance_ref": "input/look.png",
        }, seen["uploads"])
        self.assertEqual("input/img.png", graph["4"]["inputs"]["image"])
        self.assertEqual("input/img.png", graph["8"]["inputs"]["image"])
        self.assertEqual("input/look.png", graph["7a"]["inputs"]["image"])
        self.assertEqual("13", out_id)

        calls.clear()
        plain = _guided(control_ref="ignored.png")
        inpaint.build_graph(ctx, plain, None, upload)
        self.assertEqual(["img.png", "mask.png"], calls)

    def test_flux2_ignores_style_checkpoint_and_keeps_pinned_models(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        self._assert_same_submission(ctx, _flux_concept(), STYLE_CKPT)
        self._assert_same_submission(ctx, _flux_edit(), STYLE_CKPT)
        graph, out_id = flux2.build_graph(ctx, _flux_concept(), STYLE_CKPT, lambda path: path)
        self.assertEqual("12", out_id)
        self.assertEqual("flux-2-klein-4b-fp8.safetensors", graph["1"]["inputs"]["unet_name"])
        self.assertNotIn(STYLE_CKPT, str(graph))
        edit, edit_id = flux2.build_graph(ctx, _flux_edit(), STYLE_CKPT, lambda path: path)
        self.assertEqual("18", edit_id)
        self.assertEqual("flux-2-klein-base-4b-fp8.safetensors", edit["1"]["inputs"]["unet_name"])

    def test_layer_split_prefix_follows_layer_name_and_output_node(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        graph, out_id = layer.build_graph(ctx, _layer(layer_name="border"), None, lambda path: path)
        self.assertEqual("4", out_id)
        self.assertEqual("layer_border", graph["5"]["inputs"]["filename_prefix"])
        self.assertEqual(["4", 0], graph["5"]["inputs"]["images"])

if __name__ == "__main__":
    unittest.main()
