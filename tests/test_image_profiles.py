import contextlib
import copy
import importlib.util
import io
import json
import os
import sys
import unittest

TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
if TESTS_DIR not in sys.path:
    sys.path.insert(0, TESTS_DIR)

import golden_image_graphs  # noqa: E402

DETECT_DEVICE_PATH = os.path.join(golden_image_graphs.TOOLS_SRC, "detect_device.py")


def load_detect_device():
    with contextlib.redirect_stderr(io.StringIO()):
        spec = importlib.util.spec_from_file_location("detect_device_for_profiles", DETECT_DEVICE_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


EVIDENCE = {
    "report": "docs/knowledge/validation/macos-mps/r.json", "report_sha256": "a" * 64, "tasks": ["concept"],
    "profile_sha256": "b" * 64,
    "env": {"comfyui_version": "0.34.0", "comfyui_commit": "c" * 40, "models_hash": "m1", "custom_nodes_hash": "n1"},
    "min_memory_mb": 16000, "approved_by": "user", "approved_at": "2026-10-06T10:00:00+00:00",
}


class ImageProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ig = golden_image_graphs.load_image_graphs()
        cls.profiles = cls.ig._profiles

    def setUp(self):
        self._device = self.ig.DEVICE
        self._ckpt = self.ig.CKPT
        self.ig.ACTIVE_PROFILE_ID = None

    def tearDown(self):
        self.ig.DEVICE = self._device
        self.ig.CKPT = self._ckpt
        self.ig.ACTIVE_PROFILE_ID = None

    def test_active_profile_overrides_tier_for_checkpoint_size_and_addons(self):
        self.ig.DEVICE = dict(golden_image_graphs.TIER_DEVICES["sdxl_high"], usable_memory_mb=24576)
        self.ig.CKPT = self.ig.DEVICE["checkpoint"]
        self.ig.ACTIVE_PROFILE_ID = "sd15_light"
        graph, _ = self.ig.build_concept("p", seed=1)
        self.assertEqual("dreamshaper_8.safetensors", graph["1"]["inputs"]["ckpt_name"])
        self.assertEqual((512, 512), (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))
        with self.assertRaisesRegex(RuntimeError, "sd15_light"):
            self.ig.build_style_lock("p", "c.png", seed=1)

    def test_icon_asset_defaults_to_profile_native_canvas(self):
        for tier, profile_id, expected in (("sdxl_light", None, (1024, 1024)), ("sdxl_high", "sd15_light", (512, 512))):
            with self.subTest(tier=tier, profile=profile_id):
                self.ig.DEVICE = dict(golden_image_graphs.TIER_DEVICES[tier], usable_memory_mb=8192)
                self.ig.ACTIVE_PROFILE_ID = profile_id
                graph, _ = self.ig.build_icon_asset("p", seed=1)
                self.assertEqual(expected, (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))

    def test_active_sdxl_profile_picks_resolution_from_usable_memory(self):
        self.ig.ACTIVE_PROFILE_ID = "sdxl_standard"
        for usable, expected in ((24576, (1024, 1024)), (12000, (1024, 1024)), (10240, (768, 768))):
            with self.subTest(usable=usable):
                self.ig.DEVICE = dict(golden_image_graphs.TIER_DEVICES["sdxl"], usable_memory_mb=usable)
                graph, _ = self.ig.build_concept("p", seed=1)
                self.assertEqual(expected, (graph["4"]["inputs"]["width"], graph["4"]["inputs"]["height"]))
                self.assertEqual("sd_xl_base_1.0.safetensors", graph["1"]["inputs"]["ckpt_name"])

    def test_graphs_match_pre_profile_golden_fixture(self):
        expected = golden_image_graphs.load_fixture()
        actual = json.loads(json.dumps(golden_image_graphs.build_all(self.ig)))
        self.assertEqual(sorted(expected), sorted(actual))
        for tier, cases in expected.items():
            self.assertEqual(sorted(cases), sorted(actual[tier]), tier)
            for name, graph in cases.items():
                with self.subTest(tier=tier, case=name):
                    self.assertEqual(graph, actual[tier][name])

    def test_every_profile_file_validates_and_id_matches_filename(self):
        ids = self.profiles.list_profile_ids()
        self.assertIn("sdxl_standard", ids)
        self.assertIn("sd15_light", ids)
        for profile_id in ids:
            with self.subTest(profile=profile_id):
                self.assertEqual(profile_id, self.profiles.load_profile(profile_id)["id"])

    def test_profile_notes_ref_points_to_existing_document(self):
        for profile_id in self.profiles.list_profile_ids():
            notes_ref = self.profiles.load_profile(profile_id).get("notes_ref")
            with self.subTest(profile=profile_id):
                self.assertTrue(notes_ref, "每份設定檔都要有調校經驗文件")
                self.assertTrue(os.path.isfile(os.path.join(golden_image_graphs.ROOT, notes_ref)), notes_ref)

    def test_each_tier_maps_to_exactly_one_profile(self):
        seen = {}
        for profile_id in self.profiles.list_profile_ids():
            for tier in self.profiles.load_profile(profile_id)["tiers"]:
                self.assertNotIn(tier, seen, f"{tier} 同時出現在 {seen.get(tier)} 與 {profile_id}")
                seen[tier] = profile_id
        self.assertEqual("sdxl_standard", self.profiles.profile_id_for_tier("sdxl_light"))
        self.assertEqual("sd15_light", self.profiles.profile_id_for_tier("sd15"))
        self.assertIsNone(self.profiles.profile_id_for_tier("unknown"))

    def test_detect_device_tiers_agree_with_profiles(self):
        detect_device = load_detect_device()
        for min_vram, tier, checkpoint, width, height, _torch in detect_device.TIERS:
            with self.subTest(tier=tier):
                profile_id = self.profiles.profile_id_for_tier(tier)
                self.assertIsNotNone(profile_id, f"detect_device tier {tier} 沒有對應設定檔")
                profile = self.profiles.load_profile(profile_id)
                self.assertEqual(checkpoint, self.profiles.model_file(profile, "checkpoint"))
                self.assertEqual((width, height), self.profiles.default_resolution(profile, min_vram))

    def test_golden_tier_devices_agree_with_detect_device(self):
        detect_device = load_detect_device()
        for _min_vram, tier, checkpoint, width, height, _torch in detect_device.TIERS:
            device = golden_image_graphs.TIER_DEVICES[tier]
            self.assertEqual((checkpoint, width, height),
                             (device["checkpoint"], device["default_width"], device["default_height"]))

    # ComfyUI Core 內建、不屬於任何模型的 node;其餘 node 必須由設定檔某個模型的 nodes 宣告,
    # detect_image_capabilities.py 才能在沒跑 graph 的情況下判斷缺哪個 custom node。
    CORE_NODES = frozenset((
        "CLIPTextEncode", "EmptyLatentImage", "KSampler", "VAEDecode", "VAEEncode",
        "VAEEncodeForInpaint", "SaveImage", "LoadImage", "LoraLoader",
    ))
    FLUX_CASES = frozenset(("flux2_concept", "flux2_edit"))

    def test_every_graph_node_is_core_or_declared_by_profile_models(self):
        fixture = golden_image_graphs.load_fixture()
        for tier, cases in fixture.items():
            profile = self.profiles.load_profile(self.profiles.profile_id_for_tier(tier))
            declared = set(self.CORE_NODES)
            for entry in profile["models"].values():
                declared.update(entry.get("nodes", ()))
            for name, (graph, _out) in cases.items():
                if name in self.FLUX_CASES:
                    continue
                undeclared = {node["class_type"] for node in graph.values()} - declared
                with self.subTest(tier=tier, case=name):
                    self.assertFalse(undeclared, f"{tier}/{name} 用到設定檔沒宣告的 node: {sorted(undeclared)}")

    def test_task_requirements_expand_groups_without_experimental_members(self):
        profile = self.profiles.load_profile("sdxl_standard")
        requirement = self.profiles.task_requirements(profile, "pose_only")
        self.assertIn(["controlnet.canny", "controlnet.depth", "controlnet.pose"], requirement["required"])
        self.assertIn("controlnet.union", requirement["optional"])
        with self.assertRaises(self.profiles.ProfileError):
            self.profiles.task_requirements(self.profiles.load_profile("sd15_light"), "style_lock")

    def test_effective_validation_and_eligibility(self):
        profile = self.profiles.load_profile("sdxl_standard")
        self.assertEqual(("verified", None),
                         self.profiles.effective_validation(profile, "windows-cuda", 16376, "concept"))
        self.assertEqual("unverified",
                         self.profiles.effective_validation(profile, "windows-cuda", 8192, "concept")[0])
        self.assertEqual("unverified",
                         self.profiles.effective_validation(profile, "macos-mps", 36000, "concept")[0])
        ok = {"backend": "mps", "usable_memory_mb": 18432, "precision_support": ["fp32", "fp16"]}
        self.assertEqual([], self.profiles.platform_eligibility(profile, ok))
        self.assertTrue(self.profiles.platform_eligibility(profile, dict(ok, backend="cpu")))
        self.assertTrue(self.profiles.platform_eligibility(profile, dict(ok, usable_memory_mb=4096)))
        self.assertTrue(self.profiles.platform_eligibility(profile, dict(ok, precision_support=["fp32"])))
        self.assertTrue(self.profiles.platform_eligibility(profile, {"backend": "mps"}))

    def test_profile_hash_excludes_validation_block(self):
        profile = copy.deepcopy(self.profiles.load_profile("sdxl_standard"))
        base = self.profiles.profile_content_sha256(profile)
        profile["validation"]["macos-mps"] = [dict(EVIDENCE)]
        self.assertEqual(base, self.profiles.profile_content_sha256(profile), "記錄證據不能讓自己綁的雜湊失效")
        profile["sampling"]["steps"] += 1
        self.assertNotEqual(base, self.profiles.profile_content_sha256(profile))

    def test_legacy_windows_entry_migrated_and_still_verified(self):
        profile = self.profiles.load_profile("sdxl_standard")
        entry = self.profiles.validation_entries(profile, "windows-cuda")[0]
        self.assertTrue(entry["legacy"])
        self.assertIsNone(entry["report"])
        self.assertEqual("docs/tested-versions.md", entry["evidence"])
        outcome = self.profiles.evaluate_validation(profile, "windows-cuda", 16376, "concept", env={"models_hash": "any"})
        self.assertEqual(("verified", "legacy"), (outcome["status"], outcome["basis"]))

    def test_old_dict_form_is_still_read(self):
        profile = copy.deepcopy(self.profiles.load_profile("sdxl_standard"))
        profile["validation"]["windows-cuda"] = {
            "status": "verified", "tasks": ["concept"], "min_verified_memory_mb": 16000, "evidence": "docs/tested-versions.md"}
        self.profiles.validate_profile(profile)
        self.assertEqual(("verified", None), self.profiles.effective_validation(profile, "windows-cuda", 16376, "concept"))
        self.assertEqual("unverified", self.profiles.effective_validation(profile, "windows-cuda", 16376, "refine")[0])
        self.assertEqual("unverified", self.profiles.effective_validation(profile, "windows-cuda", 8000, "concept")[0])

    def _profile_with_evidence(self, **overrides):
        profile = copy.deepcopy(self.profiles.load_profile("sdxl_standard"))
        entry = dict(EVIDENCE, profile_sha256=self.profiles.profile_content_sha256(profile), **overrides)
        profile["validation"]["macos-mps"] = [entry]
        self.profiles.validate_profile(profile)
        return profile

    def test_evidence_verified_when_environment_matches(self):
        profile = self._profile_with_evidence()
        env = dict(EVIDENCE["env"])
        outcome = self.profiles.evaluate_validation(profile, "macos-mps", 18432, "concept", env)
        self.assertEqual(("verified", "evidence"), (outcome["status"], outcome["basis"]))
        self.assertEqual("unverified", self.profiles.effective_validation(profile, "macos-mps", 18432, "refine", env)[0])
        self.assertEqual("unverified", self.profiles.effective_validation(profile, "macos-mps", 8000, "concept", env)[0])
        # 目前環境未知時不比對,不降級
        self.assertEqual("verified", self.profiles.effective_validation(profile, "macos-mps", 18432, "concept", None)[0])

    def test_evidence_in_other_environment_is_verified_other_env(self):
        profile = self._profile_with_evidence()
        env = dict(EVIDENCE["env"], comfyui_version="0.35.0")
        status, reason = self.profiles.effective_validation(profile, "macos-mps", 18432, "concept", env)
        self.assertEqual("verified_other_env", status)
        self.assertIn("已在 2026-10-06 的環境驗證", reason)
        self.assertIn("目前環境不同", reason)
        self.assertIn("comfyui 版本 0.34.0→0.35.0", reason)
        status, reason = self.profiles.effective_validation(
            profile, "macos-mps", 18432, "concept", dict(EVIDENCE["env"], models_hash="m2"))
        self.assertEqual("verified_other_env", status)
        self.assertIn("模型庫內容已變動", reason)

    def test_profile_content_change_makes_evidence_other_env(self):
        profile = self._profile_with_evidence()
        profile["sampling"]["steps"] += 1
        status, reason = self.profiles.effective_validation(profile, "macos-mps", 18432, "concept", dict(EVIDENCE["env"]))
        self.assertEqual("verified_other_env", status)
        self.assertIn("設定檔內容已變動", reason)

    def test_legacy_entry_beats_other_env_evidence(self):
        profile = self._profile_with_evidence()
        profile["validation"]["macos-mps"].append(
            {"legacy": True, "report": None, "status": "verified", "tasks": ["concept"], "evidence": "docs/x.md"})
        env = dict(EVIDENCE["env"], comfyui_version="9")
        outcome = self.profiles.evaluate_validation(profile, "macos-mps", 18432, "concept", env)
        self.assertEqual(("verified", "legacy"), (outcome["status"], outcome["basis"]))

    def test_sd15_profile_has_no_sdxl_addons(self):
        self.ig.DEVICE = dict(golden_image_graphs.TIER_DEVICES["sd15"])
        for key in ("ipadapter", "clip_vision", "controlnet.canny", "controlnet.union"):
            with self.subTest(model=key):
                with self.assertRaises(self.profiles.ProfileError):
                    self.ig._model(key)

    def test_explicit_steps_and_cfg_still_override_profile(self):
        self.ig.DEVICE = dict(golden_image_graphs.TIER_DEVICES["sdxl"])
        graph, _ = self.ig.build_concept("p", seed=1, steps=12, cfg=4.5)
        self.assertEqual((12, 4.5), (graph["5"]["inputs"]["steps"], graph["5"]["inputs"]["cfg"]))

    def test_validation_tasks_are_declared_tasks(self):
        for profile_id in self.profiles.list_profile_ids():
            profile = self.profiles.load_profile(profile_id)
            for platform_key in profile["validation"]:
                for entry in self.profiles.validation_entries(profile, platform_key):
                    with self.subTest(profile=profile_id, platform=platform_key):
                        self.assertLessEqual(set(entry.get("tasks") or ()), set(profile["tasks"]))

    def _broken(self, mutate):
        profile = copy.deepcopy(self.profiles.load_profile("sdxl_standard"))
        mutate(profile)
        with self.assertRaises(self.profiles.ProfileError):
            self.profiles.validate_profile(profile)

    def test_validator_rejects_malformed_profiles(self):
        self._broken(lambda p: p.pop("sampling"))
        self._broken(lambda p: p["resolution"]["by_memory"].reverse())
        self._broken(lambda p: p["resolution"]["by_memory"][0].update(default=[1000, 1001]))
        self._broken(lambda p: p["tasks"]["concept"]["requires"].append("missing_model"))
        self._broken(lambda p: p["tasks"]["pose_only"]["requires"].append("lora.*"))
        self._broken(lambda p: p["validation"]["windows-cuda"][0].update(status="probably"))
        self._broken(lambda p: p["validation"]["windows-cuda"][0]["tasks"].append("img2video"))
        # 舊式 dict 寫法仍可讀,且同樣被驗證
        self._broken(lambda p: p["validation"].update({"x": {"status": "probably"}}))
        self._broken(lambda p: p["validation"].update({"x": {"status": "verified", "tasks": ["img2video"]}}))
        # 新式證據項目缺必要欄位/env 含未知欄位
        self._broken(lambda p: p["validation"].update({"x": [{"tasks": ["concept"], "report": "r.json"}]}))
        self._broken(lambda p: p["validation"].update({"x": [dict(EVIDENCE, env={"gpu": "x"})]}))
        self._broken(lambda p: p["models"].pop("checkpoint"))


if __name__ == "__main__":
    unittest.main()
