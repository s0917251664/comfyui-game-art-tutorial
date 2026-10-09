"""影片 graph golden:鎖住 7 個影片 task 送出的 graph(第 6.1 階段建立)。

fixture 的 ``graph`` 是第 6.1 階段 5 個 Python builder 的輸出。第 6.3 階段起 task 改由 template 填值,
PR 8.3 刪掉了 builder,golden 改由 template 維護:``tasks.video.prepare`` 用假的上傳與媒體函式組出的 graph
必須逐節點、逐欄位等於這份凍結的 golden。fixture 的 ``builder`` 欄是當時呼叫的 builder 與參數紀錄。
"""

import contextlib
import io
import json
import os
import sys
import unittest
from types import SimpleNamespace
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import golden_video_graphs as G  # noqa: E402

COVERED_TASKS = {"img2video", "fx_loop", "transition", "clip_extend", "camera_move", "character_video", "pose_drive"}


def _jsonable(value):
    return json.loads(json.dumps(value))


class VideoGraphGoldenTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.modules = G.load_modules()
        cls.task_video, cls.image_results = cls.modules
        cls.expected = {G.fixture_name(t, b, c): G.load_fixture(G.fixture_name(t, b, c)) for t, b, c, _ in G.CASES}

    def assertGraphEqual(self, expected, actual, label):
        """逐節點、逐欄位比對,失敗時指出哪個節點的哪個欄位不同。"""
        self.assertEqual(sorted(expected), sorted(actual), f"{label}: 節點 id 不同")
        for node_id, node in expected.items():
            other = actual[node_id]
            self.assertEqual(node["class_type"], other["class_type"], f"{label}: 節點 {node_id} class_type")
            self.assertEqual(sorted(node["inputs"]), sorted(other["inputs"]), f"{label}: 節點 {node_id} 欄位")
            for key, value in node["inputs"].items():
                self.assertEqual(value, other["inputs"][key], f"{label}: 節點 {node_id}.{key}")
            self.assertEqual(node, other, f"{label}: 節點 {node_id}")

    def test_fixture_directory_matches_case_table(self):
        names = [G.fixture_name(t, b, c) for t, b, c, _ in G.CASES]
        self.assertEqual(len(names), len(set(names)), "案例名稱重複")
        on_disk = sorted(n for n in os.listdir(G.FIXTURE_DIR) if n.endswith(".json"))
        self.assertEqual(sorted(names), on_disk)
        for name, data in self.expected.items():
            with self.subTest(case=name):
                task, backend, case = name[:-len(".json")].split("__")
                self.assertEqual((task, backend, case), (data["task"], data["backend"], data["case"]))
                self.assertEqual(data["graph_sha256"], self.image_results.graph_sha256(data["graph"]))
                self.assertIn(data["output_node"], data["graph"])
                self.assertEqual("SaveVideo", data["graph"][data["output_node"]]["class_type"])

    def test_cases_cover_every_task_backend_builder_and_main_option(self):
        catalog = sys.modules["comfyui_pipeline.video_catalog"]
        # video_inpaint 是 VACE(build_video_inpaint_wan),由第 3.4 階段的 template golden 涵蓋。
        self.assertEqual(COVERED_TASKS, set(catalog.VIDEO_TASKS) - {"video_inpaint"})
        self.assertEqual(COVERED_TASKS, set(self.task_video.TASKS))
        datas = list(self.expected.values())
        self.assertEqual(COVERED_TASKS, {d["task"] for d in datas})
        self.assertEqual(set(G.BUILDERS), {d["builder"]["name"] for d in datas})
        pairs = {(d["task"], d["backend"]) for d in datas}
        for task in COVERED_TASKS:
            for backend in ("wan", "h3"):
                supported = all(cap in G.VIDEO_CONFIG["backends"][backend]["capabilities"]
                                for cap in self._task_caps(task))
                self.assertEqual(supported, (task, backend) in pairs, f"{task}/{backend}")
        cameras = {d["args"]["camera"] for d in datas if (d["task"], d["backend"]) == ("camera_move", "h3")}
        self.assertEqual(set(catalog.CAMERA_MOVES), cameras)
        for backend in ("wan", "h3"):
            controls = {d["args"]["control_type"] for d in datas if (d["task"], d["backend"]) == ("pose_drive", backend)}
            self.assertEqual({"canny", "pose", "depth"}, controls, backend)
        ref_counts = {len(d["args"]["character_ref"]) for d in datas if d["task"] == "character_video"}
        self.assertIn(1, ref_counts)
        self.assertIn(catalog.CHARACTER_REF_MAX, ref_counts)
        durations = {d["args"].get("duration", G.DEFAULT_ARGS["duration"]) for d in datas}
        self.assertTrue({2.0, 6.0} <= durations, durations)

    def _task_caps(self, task):
        catalog = sys.modules["comfyui_pipeline.video_catalog"]
        return (catalog.VIDEO_TASK_CAPS[task],) + tuple(catalog.VIDEO_TASK_EXTRA_CAPS.get(task, ()))

    def _prepare_task(self, task, backend, overrides):
        """跟 golden 的假上傳／假媒體相同,但不要求 prepare 再呼叫 builder。"""
        task_video = self.task_video
        args = G.task_args(task, backend, overrides)
        ctx = SimpleNamespace(active_video_config=G.VIDEO_CONFIG)
        patches = [
            mock.patch.object(task_video, "video_canvas", G._fake_canvas),
            mock.patch.object(task_video, "validate_transition_images", lambda *a, **k: None),
            mock.patch.object(task_video, "validate_motion_reference_fps", lambda *a, **k: None),
            mock.patch.object(task_video, "validate_video_input", lambda *a, **k: None),
            mock.patch.object(task_video, "extract_last_frame", lambda *a, **k: None),
            mock.patch.object(task_video, "build_camera_end_still", lambda *a, **k: None),
            mock.patch.object(task_video, "_make_temp_image_path", G._fake_temp_image_path),
            mock.patch.object(task_video, "_remove_temp_file", lambda *a, **k: None),
        ]
        with contextlib.ExitStack() as stack:
            for patcher in patches:
                stack.enter_context(patcher)
            stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            stack.enter_context(contextlib.redirect_stderr(io.StringIO()))
            return task_video.prepare(ctx, args, G._fake_upload)

    def test_video_tasks_reproduce_golden_graphs(self):
        for task, backend, case, overrides in G.CASES:
            name = G.fixture_name(task, backend, case)
            with self.subTest(case=name):
                data = self.expected[name]
                self.assertEqual(data["args"], _jsonable(overrides))
                plan = self._prepare_task(task, backend, overrides)
                self.assertEqual(data["output_node"], plan.out_id)
                self.assertEqual(backend, plan.backend)
                self.assertGraphEqual(data["graph"], _jsonable(plan.graph), name)

    def test_model_names_come_only_from_the_explicit_video_config(self):
        models = {backend: set(spec["models"].values()) for backend, spec in G.VIDEO_CONFIG["backends"].items()}
        loader_fields = {"UNETLoader": "unet_name", "CLIPLoader": "clip_name", "VAELoader": "vae_name"}
        for name, data in self.expected.items():
            with self.subTest(case=name):
                names = [node["inputs"][loader_fields[node["class_type"]]] for node in data["graph"].values()
                         if node["class_type"] in loader_fields]
                self.assertTrue(names)
                self.assertTrue(set(names) <= models[data["backend"]], names)

    def test_unsupported_task_backend_pairs_fail_fast(self):
        for task, overrides in (
                ("fx_loop", {}), ("transition", {"image": None, "start": "a.png", "end": "b.png"}),
                ("character_video", {"image": None, "character_ref": ["a.png"]})):
            with self.subTest(task=task):
                with self.assertRaises(SystemExit):
                    G.run_task(task, "wan", overrides, self.modules)


if __name__ == "__main__":
    unittest.main()
