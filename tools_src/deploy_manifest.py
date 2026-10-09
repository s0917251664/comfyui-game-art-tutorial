"""部署清單的單一來源:`deploy.py`(寫入)與 `verify_portable_install.py`(核對)共用。

清單列出「repo 的哪個檔案 → <ComfyUI>/ 底下的哪個位置」。兩個工具都從這裡取,
所以部署了什麼、驗證什麼不可能分歧。本檔只描述檔案對應,不做任何 I/O 寫入。

不在清單內(永遠不由 deploy 碰觸):device_config.json、image_capabilities.json、
video_capabilities.json、capability_fingerprint.json 等機器快照,以及 generated/ 輸出。
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PIPELINE_REPO_DIR = Path("tools_src/comfyui_pipeline")
PIPELINE_DEPLOYED_DIR = Path("tools/comfyui_pipeline")
PROFILES_REPO_DIR = Path("tools_src/comfyui_pipeline/profiles")
PROFILES_DEPLOYED_DIR = Path("tools/comfyui_pipeline/profiles")

# 這些檔名是各機器自己的快照,任何情況都不得被部署覆蓋或移除。
PROTECTED_NAMES = frozenset({
    "device_config.json", "image_capabilities.json", "video_capabilities.json", "capability_fingerprint.json",
})

_TOOL_FILES = (
    "video_layers.py", "face_swap.py", "film_audio.py", "film_sapi.ps1", "film_qwen.py", "film_lipsync.py",
    "generate.py", "detect_device.py", "sam_segment.py", "image_edit_tools.py", "comfyui_design.py",
    "mask_refine.py", "mask_session.py", "detect_image_capabilities.py", "detect_video_capabilities.py",
    "gameart.py", "doctor.py", "asset_review.py", "smoke.py", "vfx_alpha_tools.py", "local_pixels.py",
)
_NODE_PACKAGE_FILES = ("__init__.py", "contracts.py", "media.py", "nodes.py")
# (label 前綴, repo 套件資料夾, 部署位置們)。第二個位置是 custom_nodes,安裝與否由使用者決定。
_NODE_PACKAGES = (
    ("face-swap-video", "comfyui_face_swap_video", ("tools/comfyui_face_swap_video", "custom_nodes/comfyui-face-swap-video")),
    ("video-layers", "comfyui_video_layers", ("tools/comfyui_video_layers", "custom_nodes/comfyui-video-layers")),
)
SIMPLE_MASK_REPO_DIR = Path("tools_src/simple_mask_tool")
SIMPLE_MASK_LOCATIONS = ("tools/simple_mask_tool", "custom_nodes/comfyui-simple-mask-tool")
# vfx 實作套件只進 tools/，不進 custom_nodes。門面 vfx_alpha_tools.py 仍在 _TOOL_FILES。
VFX_ALPHA_REPO_DIR = Path("tools_src/vfx_alpha")
VFX_ALPHA_DEPLOYED_DIR = Path("tools/vfx_alpha")
# PR 8.4:generate.py 的圖片／影片 task 改由 template 填 graph,部署端也要有 template。
# 只部署 image/ 與 video/ 底下的 template.json 與 graph.api.json(位元組不變)。recipe、_schema、
# README、catalog 不部署:gameart.py run／recipe 仍然只能從 repo 執行。
TEMPLATES_REPO_DIR = Path("templates")
TEMPLATES_DEPLOYED_DIR = Path("tools/templates")
TEMPLATE_GROUPS = ("image", "video")
TEMPLATE_FILE_NAMES = frozenset({"template.json", "graph.api.json"})


@dataclass(frozen=True)
class Entry:
    label: str
    src: Path  # 相對 repo 根目錄
    dst: Path  # 相對 ComfyUI 安裝路徑
    profile: bool = False  # 模型設定檔:verify 另有「部署集合必須與 repo 完全一致」的專屬檢查

    @property
    def custom_node_dir(self):
        """部署在 custom_nodes/<name>/ 底下時回傳該資料夾(相對路徑),否則 None。"""
        return Path(*self.dst.parts[:2]) if self.dst.parts[0] == "custom_nodes" else None


def _package_files(repo_root, repo_dir, suffixes):
    base = Path(repo_root) / repo_dir
    for path in sorted(base.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix in suffixes:
            yield path.relative_to(base)


def _template_files(repo_root):
    base = Path(repo_root) / TEMPLATES_REPO_DIR
    for group in TEMPLATE_GROUPS:
        for path in sorted((base / group).rglob("*")):
            rel = path.relative_to(base)
            if path.is_file() and path.name in TEMPLATE_FILE_NAMES and not any(p.startswith("_") for p in rel.parts):
                yield rel


def deploy_manifest(repo_root):
    """回傳完整的 Entry 清單(依 repo 實際檔案動態展開 pipeline、simple_mask_tool 與 vfx_alpha)。"""
    entries = [Entry(name, Path("tools_src") / name, Path("tools") / name) for name in _TOOL_FILES]
    for prefix, package, locations in _NODE_PACKAGES:
        for location in locations:
            for name in _NODE_PACKAGE_FILES:
                entries.append(Entry(f"{prefix}/{location}/{name}", Path("tools_src") / package / name, Path(location) / name))
    for location in SIMPLE_MASK_LOCATIONS:
        for rel in _package_files(repo_root, SIMPLE_MASK_REPO_DIR, {".py", ".html", ".js", ".css", ".json"}):
            entries.append(Entry(f"simple-mask-tool/{location}/{rel.as_posix()}", SIMPLE_MASK_REPO_DIR / rel, Path(location) / rel))
    for rel in _package_files(repo_root, VFX_ALPHA_REPO_DIR, {".py"}):
        entries.append(Entry(f"vfx_alpha/{rel.as_posix()}", VFX_ALPHA_REPO_DIR / rel, VFX_ALPHA_DEPLOYED_DIR / rel))
    for rel in _package_files(repo_root, PIPELINE_REPO_DIR, {".py", ".json"}):
        entries.append(Entry(f"comfyui_pipeline/{rel.as_posix()}", PIPELINE_REPO_DIR / rel, PIPELINE_DEPLOYED_DIR / rel,
                             profile=rel.parts[0] == "profiles"))
    for rel in _template_files(repo_root):
        entries.append(Entry(f"templates/{rel.as_posix()}", TEMPLATES_REPO_DIR / rel, TEMPLATES_DEPLOYED_DIR / rel))
    return entries


def stale_deployed_files(repo_root, comfyui_path):
    """部署端 comfyui_pipeline/ 與 templates/ 內 repo 已不存在的 .py/.json(相對 ComfyUI 路徑)。忽略 __pycache__。"""
    wanted = {entry.dst for entry in deploy_manifest(repo_root)}
    stale = []
    for deployed_dir in (PIPELINE_DEPLOYED_DIR, TEMPLATES_DEPLOYED_DIR):
        deployed = Path(comfyui_path) / deployed_dir
        if not deployed.is_dir():
            continue
        for path in sorted(deployed.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts or path.suffix not in {".py", ".json"}:
                continue
            rel = deployed_dir / path.relative_to(deployed)
            if rel not in wanted:
                stale.append(rel)
    return stale
