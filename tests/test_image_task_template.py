"""第 5.1 階段：concept 等 6 個圖片 task 送出的 graph 與 builder 逐欄相同。

sampler／scheduler 烤在 template 裡，目前設定檔是 euler／normal。
checkpoint、尺寸、seed、steps、cfg、filename_prefix 都是 slot。
這些案例在 patch 之後不需要再改任何欄位才對得上 builder 與 golden。
sd15 的 template 目錄不存在時，concept／icon_asset／refine 仍走 builder。
"""
import os
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golden_image_graphs as image_golden  # noqa: E402

from comfyui_pipeline import image_from_template, image_graphs, image_results, image_runtime, tasks  # noqa: E402
from comfyui_pipeline.context import RunContext  # noqa: E402
from comfyui_pipeline.tasks import control, flux2, image_basic, inpaint, layer, upscale  # noqa: E402

SEED = image_golden.SEED
LORA = "test_lora.safetensors"
STYLE_CKPT = "juggernautXL_ragnarok.safetensors"
PHASE_51 = frozenset({
    "concept", "icon_asset", "refine", "character_action", "pose_only", "style_lock",
})


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


def _builder(ig, args, style_checkpoint):
    """舊路徑：image_graphs builder。icon 與 --remove-bg 再接一次去背，跟 CLI 送出的相同。"""
    task = args.task
    if task == "concept":
        graph, image_node = ig.build_concept(
            args.prompt, args.negative, args.width, args.height, args.seed,
            batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
            checkpoint=style_checkpoint)
    elif task == "icon_asset":
        graph, image_node = ig.build_icon_asset(
            args.prompt, args.negative, args.width, args.height, args.seed,
            batch_size=args.batch, lora_name=args.lora, lora_strength=args.lora_strength,
            structure_ref_filename=args.structure_ref, checkpoint=style_checkpoint,
            appearance_ref_filename=args.appearance_ref, appearance_weight=args.appearance_weight)
    elif task == "refine":
        graph, image_node = ig.build_refine(
            args.prompt, args.image, args.negative, denoise=args.denoise,
            seed=args.seed, checkpoint=style_checkpoint)
    elif task == "character_action":
        graph, image_node = ig.build_character_action(
            args.prompt, args.character_ref, args.pose_ref, args.negative,
            args.width, args.height, args.seed, ip_weight=args.ip_weight,
            pose_strength=args.pose_strength, batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint)
    elif task == "pose_only":
        graph, image_node = ig.build_pose_only(
            args.prompt, args.pose_ref, args.negative, args.width, args.height, args.seed,
            pose_strength=args.pose_strength, batch_size=args.batch, control_type=args.control_type,
            lora_name=args.lora, lora_strength=args.lora_strength, checkpoint=style_checkpoint,
            control_backend=args.control_backend)
    elif task == "style_lock":
        graph, image_node = ig.build_style_lock(
            args.prompt, args.character_ref, args.negative, args.width, args.height, args.seed,
            ip_weight=args.ip_weight, batch_size=args.batch, lora_name=args.lora,
            lora_strength=args.lora_strength, checkpoint=style_checkpoint)
    else:
        raise AssertionError(task)
    return graph, image_node


def _sync(ig, ctx):
    ig.DEVICE = ctx.device
    ig.CKPT = ctx.device.get("checkpoint", ig.CKPT)
    ig.ACTIVE_PROFILE_ID = ctx.active_image_profile


class ImageTaskTemplateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ig = image_golden.load_image_graphs()
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
        _sync(self.ig, ctx)
        expected, expected_node = _builder(self.ig, args, style_checkpoint)
        wants_bg = image_from_template.wants_background_removal(args)
        attached_id = self.ig.attach_bg_removal(expected, expected_node) if wants_bg else None
        _sync(self.ig, ctx)
        changed = []
        real_align = image_from_template._align_baked_sampling

        def spy(graph, sampling, _real=real_align):
            found = _real(graph, sampling)
            changed.append(found)
            return found

        with mock.patch.object(image_from_template, "_align_baked_sampling", spy):
            graph, image_node, download_id = self._submit(ctx, args, style_checkpoint)
        # template 路徑才會對齊烤進去的 sampler。目前是空清單：euler／normal 已相同，不必再改欄位。
        if changed:
            self.assertEqual([[]], changed)
        else:
            self.assertEqual("sd15", self.ig._active_profile()["family"])
        self.assertEqual(expected_node, image_node)
        self.assertEqual(list(expected), list(graph))
        self.assertEqual(expected, graph)
        if wants_bg:
            transparent = [
                node_id for node_id, node in graph.items()
                if node.get("class_type") == "SaveImage"
                and (node.get("inputs") or {}).get("filename_prefix") == "transparent"
            ]
            self.assertEqual([download_id], transparent)
            self.assertEqual(attached_id, download_id)
            self.assertEqual(1, sum(1 for node in graph.values() if node.get("class_type") == "RemoveBackground"))
        else:
            self.assertIsNone(download_id)
            self.assertIsNone(image_from_template.transparent_save_id(graph))
        prefixes = [
            (node.get("inputs") or {}).get("filename_prefix")
            for node in graph.values() if node.get("class_type") == "SaveImage"
        ]
        self.assertIn(image_from_template.FILENAME_PREFIX[args.task], prefixes)
        if fixture is not None:
            fixture_graph, fixture_out = fixture
            self.assertEqual(fixture_graph, graph)
            self.assertEqual(fixture_out, download_id if wants_bg else image_node)
        manifest_kwargs = dict(
            task=args.task, profile_id=ctx.active_image_profile, backend="cuda",
            prompt_id="prompt-1", inputs=[], outputs=[], args=args,
        )
        left = image_results.make_manifest(graph=expected, **manifest_kwargs)
        right = image_results.make_manifest(graph=graph, **manifest_kwargs)
        self.assertEqual(left, right)
        self.assertEqual("image_generation_result", right["kind"])
        self.assertEqual("pending", right["content_review"])
        self.assertEqual(image_results.graph_sha256(expected), right["graph_sha256"])

    def test_sdxl_submissions_match_builder_and_golden(self):
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

    def test_omitted_seed_uses_builder_draw_once(self):
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

    def test_seed_zero_and_partial_size_match_builder(self):
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

    def test_sd15_falls_back_to_builder_without_uploading(self):
        device = image_golden.TIER_DEVICES["sd15"]
        self.assertFalse(Path(image_golden.ROOT, "templates", "image", "sd15", "concept", "template.json").is_file())
        for profile in (None, "sd15_light"):
            ctx = _ctx(device, profile)
            uploads = []

            def upload(path, _uploads=uploads):
                _uploads.append(path)
                return path

            concept_args = _concept(negative="n", width=832, height=1216, batch=2, lora=LORA, lora_strength=0.6)
            self.assertIsNone(image_from_template.graph_from_template(ctx, concept_args, STYLE_CKPT, upload))
            self.assertEqual([], uploads)
            graph, image_node = image_basic.build_graph(ctx, concept_args, STYLE_CKPT, upload)
            self.assertEqual([], uploads)
            _sync(self.ig, ctx)
            expected, expected_node = _builder(self.ig, concept_args, STYLE_CKPT)
            self.assertEqual(expected_node, image_node)
            self.assertEqual(expected, graph)
            self.assertEqual(self.fixture["sd15"]["concept_lora_style_size"][0], graph)

            for args in (_concept(remove_bg=True), _icon(), _icon(lora=LORA, lora_strength=0.6), _refine(remove_bg=True)):
                with self.subTest(profile=profile, task=args.task, remove_bg=getattr(args, "remove_bg", False)):
                    self._assert_same_submission(ctx, args)

    def test_missing_sdxl_template_stops_instead_of_using_builder(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        missing = Path("missing-template.json")
        with mock.patch.object(image_from_template, "_template_json", return_value=missing):
            with self.assertRaises(SystemExit):
                control.build_graph(ctx, _pose(), None, lambda path: path)
            with self.assertRaises(SystemExit):
                image_from_template.graph_from_template(ctx, _concept(), None, lambda path: path)

    def test_other_image_tasks_still_use_builders(self):
        ctx = _ctx(image_golden.TIER_DEVICES["sdxl"])
        spec = [
            (_ns(task="inpaint", prompt="p", negative=None, image="img.png", mask="mask.png",
                 denoise=1.0, seed=SEED),
             lambda fn: image_runtime.build_inpaint(ctx, "p", fn["img.png"], fn["mask.png"], None,
                                                     denoise=1.0, seed=SEED)),
            (_ns(task="guided_inpaint", prompt="p", negative=None, image="img.png", mask="mask.png",
                 control_ref=None, control_type=None, control_strength=1.0, appearance_ref=None,
                 appearance_weight=0.8, denoise=1.0, seed=SEED),
             lambda fn: image_runtime.build_guided_inpaint(
                 ctx, "p", fn["img.png"], fn["mask.png"], None, denoise=1.0, seed=SEED)),
            (_ns(task="upscale", prompt="p", negative=None, image="img.png", scale=2.0, denoise=0.4, seed=SEED),
             lambda fn: image_runtime.build_upscale(ctx, "p", fn["img.png"], None, scale=2.0,
                                                     denoise=0.4, seed=SEED)),
            (_ns(task="layer_split", image="img.png", mask="mask.png", layer_name="frame"),
             lambda fn: image_runtime.build_layer_split(ctx, fn["img.png"], fn["mask.png"], "frame")),
            (_ns(task="flux2_concept", prompt="p", width=1024, height=1024, seed=SEED),
             lambda fn: image_runtime.build_flux2_concept(ctx, "p", width=1024, height=1024, seed=SEED)),
            (_ns(task="flux2_edit", prompt="p", image="img.png", seed=SEED),
             lambda fn: image_runtime.build_flux2_edit(ctx, "p", fn["img.png"], seed=SEED)),
        ]
        owners = {
            "inpaint": inpaint, "guided_inpaint": inpaint, "upscale": upscale,
            "layer_split": layer, "flux2_concept": flux2, "flux2_edit": flux2,
        }
        for args, build in spec:
            with self.subTest(task=args.task):
                self.assertNotIn(args.task, PHASE_51)
                seen = {}

                def upload(path, _seen=seen):
                    _seen[path] = path
                    return path

                graph, out_id = owners[args.task].build_graph(ctx, args, None, upload)
                expected, expected_id = build(seen)
                self.assertEqual(expected_id, out_id)
                self.assertEqual(expected, graph)


if __name__ == "__main__":
    unittest.main()
