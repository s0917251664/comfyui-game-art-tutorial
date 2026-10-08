"""`python gameart.py recipe ...` 的進入點。

只能從 repo 的 tools_src/ 執行(templates/recipes 不部署)。說明見 comfyui_pipeline/runner/recipe_cli.py。
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from comfyui_pipeline.runner.recipe_cli import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
