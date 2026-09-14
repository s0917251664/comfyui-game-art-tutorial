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


class ImageProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ig = golden_image_graphs.load_image_graphs()
        cls.profiles = cls.ig._profiles

    def setUp(self):
        self._device = self.ig.DEVICE
        self._ckpt = self.ig.CKPT

    def tearDown(self):
        self.ig.DEVICE = self._device
        self.ig.CKPT = self._ckpt

    def test_graphs_match_pre_profile_golden_fixture(self):
        with open(golden_image_graphs.FIXTURE_PATH, encoding="utf-8") as handle:
            expected = json.load(handle)
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
            for platform_key, record in profile["validation"].items():
                with self.subTest(profile=profile_id, platform=platform_key):
                    self.assertLessEqual(set(record.get("tasks", ())), set(profile["tasks"]))

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
        self._broken(lambda p: p["validation"]["windows-cuda"].update(status="probably"))
        self._broken(lambda p: p["validation"]["windows-cuda"]["tasks"].append("img2video"))
        self._broken(lambda p: p["models"].pop("checkpoint"))


if __name__ == "__main__":
    unittest.main()
