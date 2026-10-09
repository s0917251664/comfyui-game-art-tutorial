import contextlib
import importlib.util
import io
import os
import sys
import unittest

TOOLS_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools_src")


def load_generate():
    if TOOLS_SRC not in sys.path:
        sys.path.insert(0, TOOLS_SRC)
    with contextlib.redirect_stderr(io.StringIO()):
        spec = importlib.util.spec_from_file_location(
            "generate_registry_under_test", os.path.join(TOOLS_SRC, "generate.py"))
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


class TaskRegistryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.generate = load_generate()
        from comfyui_pipeline import cli, tasks
        cls.cli = cli
        cls.tasks = tasks

    def test_task_sets_match_generate_constants(self):
        self.assertEqual(self.generate.IMAGE_GRAPH_TASKS, self.tasks.IMAGE_TASKS)
        self.assertEqual(self.generate.VIDEO_TASKS, self.tasks.VIDEO_TASKS)
        self.assertEqual(
            set(self.tasks.TASK_ORDER),
            self.tasks.IMAGE_TASKS | self.tasks.VIDEO_TASKS | self.tasks.LOCAL_TASKS,
        )
        self.assertEqual({"video_concat", "video_composite"}, set(self.tasks.LOCAL_TASKS))

    def test_each_task_has_exactly_one_runner(self):
        for task in self.tasks.TASK_ORDER:
            module = self.tasks.owner(task)
            runners = [name for name in ("build_graph", "prepare", "run_local", "run_with_runner") if hasattr(module, name)]
            self.assertTrue(runners, task)
            self.assertIn(task, module.TASKS)

    def test_subcommands_follow_task_order(self):
        parser = self.cli.build_parser()
        choices = next(
            action.choices for action in parser._actions if getattr(action, "dest", None) == "task"
        )
        self.assertEqual(list(self.tasks.TASK_ORDER), list(choices))

    def test_generate_keeps_entry_points_and_pipeline_modules_hold_the_rest(self):
        for name in ("main", "resolve_comfy_url", "validate_timeout", "submit_and_wait",
                     "download_outputs", "upload_image", "_fetch_comfy_object_info",
                     "check_image_graph_against_object_info"):
            self.assertTrue(callable(getattr(self.generate, name)), name)
        for module, name in ((self.tasks, "build_image_task_graph"),
                             (self.tasks, "preflight_image_task"),
                             (self.cli, "validate_cli_args"),
                             (self.cli, "validate_task_capabilities"),
                             (self.cli, "run")):
            self.assertTrue(callable(getattr(module, name)), name)
        from comfyui_pipeline.tasks import _common
        self.assertTrue(callable(_common.add_runtime_arguments))


if __name__ == "__main__":
    unittest.main()
