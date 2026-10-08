"""統一入口:`python gameart.py <tool> [args...]` 轉發到既有 CLI,argv 原樣傳遞。

各工具仍可直接執行(`python generate.py ...`);本檔只是薄 dispatcher。
以 runpy 以 `__main__` 方式執行目標腳本,行為(含 --help、錯誤處理、結束碼)與直接執行一致,
且只載入被選工具的相依套件。`python gameart.py list` 列出所有工具。
"""
import runpy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 工具名 -> (腳本檔, 一行說明)
TOOLS = {
    "gen": ("generate.py", "圖片/影片生成 pipeline(concept、inpaint、video 等任務)"),
    "design": ("comfyui_design.py", "本機 Pillow 物件場景、檢視表與圖樣重複"),
    "edit": ("image_edit_tools.py", "本地圖片編輯工具(遮罩、裁切、合成等)"),
    "face-swap": ("face_swap.py", "影片換臉 preflight / swap"),
    "video-layers": ("video_layers.py", "影片分層 preflight / run"),
    "film-audio": ("film_audio.py", "影片配音/音訊處理"),
    "film-lipsync": ("film_lipsync.py", "MuseTalk 對嘴"),
    "film-qwen": ("film_qwen.py", "Qwen3-TTS worker(需獨立 qwen-tts 環境)"),
    "sam": ("sam_segment.py", "SAM 2.1 自動遮罩候選"),
    "mask-refine": ("mask_refine.py", "以圖像引導精修使用者繪製的選取遮罩"),
    "mask-session": ("mask_session.py", "本機簡易遮罩工具 session client"),
    "vfx": ("vfx_alpha_tools.py", "特效去背(黑底亮度/綠幕)、打包、影片物件標記與遮罩貼回、Idle 首尾量測"),
    "detect-device": ("detect_device.py", "偵測硬體並寫 device_config.json"),
    "detect-image": ("detect_image_capabilities.py", "偵測圖片能力並寫 image_capabilities.json"),
    "detect-video": ("detect_video_capabilities.py", "偵測影片能力並寫 video_capabilities.json"),
    "review": ("asset_review.py", "素材候選清單與人工 accept/reject 決定紀錄(綁輸出 hash)"),
    "doctor": ("doctor.py", "檢查三份機器快照是否過期;--refresh 重跑 detector"),
    "deploy": ("deploy.py", "把 repo 的 tools_src/ 部署到 ComfyUI(預設 dry run;--yes 寫入,含備份/驗證/自動還原)"),
    "smoke": ("smoke.py", "固定煙霧測試套件:跑固定 task 並寫技術驗證報告(--record 存入 repo;`smoke record` 事後記錄)"),
    "run": ("run_template.py", "固定 API graph template:run list／run show <id>／run <id> --dry-run／--preflight／實際執行(寫 run.result.json)"),
    "recipe": ("run_recipe.py", "多步驟 recipe:list／show <id>／run <id> --dry-run／run 到確認點停下／resume [--confirm];_drafts 要 --draft"),
    "validation": ("validation.py", "驗證證據升格:propose 列出、approve(僅使用者決定)寫入 profile、status 看 task×平台"),
    "verify-install": ("verify_portable_install.py", "驗證可攜式安裝與部署副本是否同步"),
    "benchmark-birefnet": ("benchmark_birefnet.py", "BiRefNet 各版本 A/B 基準測試"),
}
# 只能從 repo 的 tools_src/ 執行的工具(需要 repo 原始碼作比對基準,部署端可能只留有舊副本)
REPO_ONLY = {"deploy", "validation", "verify-install", "benchmark-birefnet", "run", "recipe"}


def _print_tools(stream):
    width = max(len(name) for name in TOOLS)
    for name, (script, desc) in TOOLS.items():
        print(f"  {name:<{width}}  {script:<30} {desc}", file=stream)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv or argv[0] in ("-h", "--help", "list"):
        print("用法: python gameart.py <tool> [args...]\n\n可用工具:")
        _print_tools(sys.stdout)
        print("\n`python gameart.py <tool> --help` 顯示該工具自己的說明。")
        return 0
    tool = argv[0]
    if tool not in TOOLS:
        print(f"gameart: 未知工具 {tool!r}\n可用工具:", file=sys.stderr)
        _print_tools(sys.stderr)
        return 2
    if tool in REPO_ONLY and HERE.name != "tools_src":
        print(f"gameart: {tool} 只能從 repo 的 tools_src/gameart.py 執行(例如 python tools_src/gameart.py {tool} ...)",
              file=sys.stderr)
        return 2
    script = HERE / TOOLS[tool][0]
    if not script.is_file():
        print(f"gameart: 找不到 {script.name}(此部署可能未包含該工具)", file=sys.stderr)
        return 2
    if str(HERE) not in sys.path:
        sys.path.insert(0, str(HERE))
    sys.argv = [str(script), *argv[1:]]
    runpy.run_path(str(script), run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
