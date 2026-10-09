"""comfyui_pipeline 不依賴 generate.py:可單獨 import,且 task graph 可用明確的 RunContext 組出來。"""
import os
import subprocess
import sys
import textwrap
import unittest

TOOLS_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools_src")


def run_fresh(code):
    """在全新的 Python process 跑 code(確保沒有其他測試先 import 過 generate)。"""
    return subprocess.run(
        [sys.executable, "-c", textwrap.dedent(code)],
        cwd=TOOLS_SRC, capture_output=True, text=True, check=False,
    )


class PipelineIndependenceTests(unittest.TestCase):
    def test_modules_import_without_generate(self):
        result = run_fresh(f"""
            import sys
            sys.path.insert(0, {TOOLS_SRC!r})
            import comfyui_pipeline.tasks.video
            import comfyui_pipeline.tasks.video_local
            import comfyui_pipeline.cli
            assert "generate" not in sys.modules, "pipeline 不該 import generate"
            assert not hasattr(comfyui_pipeline, "runtime")
            print("ok")
        """)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_task_graph_builds_from_explicit_context(self):
        result = run_fresh(f"""
            import sys
            from types import SimpleNamespace
            sys.path.insert(0, {TOOLS_SRC!r})
            from comfyui_pipeline import tasks
            from comfyui_pipeline.context import RunContext
            assert "generate" not in sys.modules

            ctx = RunContext(device={{"tier": "sdxl", "checkpoint": "explicit-ctx.safetensors",
                                      "default_width": 640, "default_height": 384}})
            args = SimpleNamespace(task="concept", prompt="x", negative=None, width=None, height=None,
                                   seed=1, batch=1, lora=None, lora_strength=0.8)
            graph, _ = tasks.build_image_task_graph(ctx, args, None, lambda p: p)
            assert graph["1"]["inputs"]["ckpt_name"] == "explicit-ctx.safetensors", graph["1"]
            latent = next(n for n in graph.values() if n["class_type"] == "EmptyLatentImage")
            assert (latent["inputs"]["width"], latent["inputs"]["height"]) == (640, 384), latent

            # 第二個 context 不受第一個影響(狀態不跨 context 殘留)
            other = RunContext(device={{"tier": "sdxl", "checkpoint": "other.safetensors",
                                        "default_width": 512, "default_height": 512}})
            graph2, _ = tasks.build_image_task_graph(other, args, None, lambda p: p)
            assert graph2["1"]["inputs"]["ckpt_name"] == "other.safetensors"

            # 影片 builder 已在 PR 8.3 刪除;影片 graph 由 templates/ 填值(模型檔名是 template 的 pin)
            print("ok")
        """)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn("ok", result.stdout)

    def test_runtime_facade_module_is_gone(self):
        self.assertFalse(os.path.exists(os.path.join(TOOLS_SRC, "comfyui_pipeline", "runtime.py")))


if __name__ == "__main__":
    unittest.main()
