"""PR 8.4:templates/ 納入部署。

- 部署清單只收 image／video 底下的 template.json 與 graph.api.json(recipe、_schema、README、catalog 不部署)。
- 模擬部署端的資料夾(<ComfyUI>/tools/comfyui_pipeline 與 <ComfyUI>/tools/templates,沒有 docs/):
  圖片 task 與 video_inpaint 都找得到 template 並組出 graph;證據文件只在 repo 裡檢查。
"""
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools_src"))
import deploy_manifest as DM  # noqa: E402


class DeployTemplatesTests(unittest.TestCase):
    def test_manifest_includes_only_template_and_graph_files(self):
        entries = [e for e in DM.deploy_manifest(ROOT) if e.label.startswith("templates/")]
        self.assertTrue(entries)
        names = {e.src.name for e in entries}
        self.assertEqual({"template.json", "graph.api.json"}, names)
        for entry in entries:
            self.assertEqual(Path("tools/templates") / entry.src.relative_to("templates"), entry.dst)
            self.assertIn(entry.src.parts[1], ("image", "video"))
            self.assertFalse(any(part.startswith("_") for part in entry.src.parts))
        ids = {e.src.parent.relative_to("templates").as_posix() for e in entries}
        self.assertIn("video/wan-vace/inpaint", ids)
        self.assertIn("image/sdxl/concept", ids)
        self.assertNotIn("recipes", {e.src.parts[1] for e in entries})
        # 每份 template 兩個檔都在
        for template_id in ids:
            self.assertEqual({"template.json", "graph.api.json"},
                             {e.src.name for e in entries if e.src.parent.relative_to("templates").as_posix() == template_id})

    def test_stale_deployed_template_is_listed(self):
        with tempfile.TemporaryDirectory() as tmp:
            stale = Path(tmp) / "tools" / "templates" / "video" / "gone" / "template.json"
            stale.parent.mkdir(parents=True)
            stale.write_text("{}", encoding="utf-8")
            self.assertIn(Path("tools/templates/video/gone/template.json"), DM.stale_deployed_files(ROOT, tmp))

    def test_deployed_layout_finds_templates_without_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tools = Path(tmp) / "ComfyUI" / "tools"
            for entry in DM.deploy_manifest(ROOT):  # 照部署清單複製 tools/ 底下的所有項目
                if entry.dst.parts[0] == "tools":
                    target = Path(tmp) / "ComfyUI" / entry.dst
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(ROOT / entry.src, target)
            self.assertFalse((tools / "docs").exists())
            code = textwrap.dedent(f"""
                import sys
                sys.path.insert(0, {str(tools)!r})
                from pathlib import Path
                from comfyui_pipeline import image_from_template
                from comfyui_pipeline.runner import template as T
                from comfyui_pipeline.tasks import video_edit
                root = image_from_template._repo_root()
                assert Path(root) == Path({str(tools)!r}), root
                t = T.load_template(T.templates_root(root), "video/wan-vace/inpaint", repo_root=root)
                assert t.data["status"] == "technical_pass"
                t = T.load_template(T.templates_root(root), "image/sdxl/concept", repo_root=root)
                print("ok", len(t.graph))
            """)
            env = dict(os.environ, GAMEART_SNAPSHOT_DIR=tmp, PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env, capture_output=True, text=True,
                                    encoding="utf-8", errors="replace")
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertIn("ok", result.stdout)


if __name__ == "__main__":
    unittest.main()
