"""設定檔與機器快照的路徑解析(smoke、doctor 共用;第二階段 runner 也會用)。

規則(docs/knowledge/decisions/2026-10-07-phase2-template-runner.md 的 D3):

- 執行位置分兩種:
  - repo 模式:腳本在 ``<repo>/tools_src/``,而且 ``<repo>`` 有 ``AGENTS.md`` 和 ``tools_src/gameart.py``;
  - 部署模式:其他位置,通常是 ``<ComfyUI>/tools/``。
- ``--config``:絕對路徑照用;相對路徑在 repo 模式以 repo 根目錄解析(和 deploy.py 一致),
  部署模式以目前工作目錄解析。結果一律是絕對路徑,可以直接交給 cwd 不同的子程序。
- 沒給 ``--config``:repo 模式且 ``<repo>/local_config.json`` 存在就用它;部署模式不自動尋找。
- 機器快照(``device_config.json``、``image_capabilities.json``、指紋 sidecar)的資料夾:
  ``--snapshot-dir`` 優先;其次是 repo 模式下設定檔的 ``<comfyui_path>/tools``;最後是腳本所在資料夾。
  找不到 ``device_config.json`` 時丟 ``SnapshotNotFound``,訊息列出找過的路徑。

路徑函式都可以傳入 ``pathmod``(``ntpath``/``posixpath``),測試能在任何平台模擬 Windows 路徑。
"""
import json
import os

LOCAL_CONFIG_NAME = "local_config.json"
DEVICE_CONFIG_NAME = "device_config.json"
# 子程序(generate.py)用這個環境變數找快照資料夾;沒設時沿用腳本所在資料夾。
SNAPSHOT_DIR_ENV = "GAMEART_SNAPSHOT_DIR"

REPO_MODE = "repo"
DEPLOYED_MODE = "deployed"


class SnapshotNotFound(RuntimeError):
    """找不到機器快照;``searched`` 是找過的資料夾。"""

    def __init__(self, searched, hint=""):
        self.searched = list(searched)
        lines = [f"找不到 {DEVICE_CONFIG_NAME}。找過:"] + [f"  - {path}" for path in self.searched]
        if hint:
            lines.append(hint)
        super().__init__("\n".join(lines))


def find_repo_root(script_dir, isfile=os.path.isfile, pathmod=os.path):
    """``script_dir`` 是 ``<repo>/tools_src`` 時回傳 ``<repo>``,否則回傳 None。"""
    script_dir = pathmod.normpath(os.fspath(script_dir))
    if pathmod.basename(script_dir) != "tools_src":
        return None
    parent = pathmod.dirname(script_dir)
    if isfile(pathmod.join(parent, "AGENTS.md")) and isfile(pathmod.join(script_dir, "gameart.py")):
        return parent
    return None


def run_mode(repo_root):
    return REPO_MODE if repo_root else DEPLOYED_MODE


def _absolute(value, base, pathmod):
    value = pathmod.expanduser(os.fspath(value))
    if pathmod.isabs(value):
        return pathmod.normpath(value)
    return pathmod.normpath(pathmod.join(base, value))


def resolve_config_path(value, repo_root=None, cwd=None, pathmod=os.path):
    """把 ``--config`` 轉成絕對路徑(規則見模組說明)。``value`` 為空時回傳 None。"""
    if not value:
        return None
    base = repo_root if repo_root else (cwd if cwd is not None else os.getcwd())
    return _absolute(value, base, pathmod)


def default_config_path(repo_root, isfile=os.path.isfile, pathmod=os.path):
    """沒給 ``--config`` 時的自動選擇:只在 repo 模式、而且 ``<repo>/local_config.json`` 存在時回傳。"""
    if not repo_root:
        return None
    candidate = pathmod.join(repo_root, LOCAL_CONFIG_NAME)
    return candidate if isfile(candidate) else None


def choose_config_path(value, repo_root=None, cwd=None, isfile=os.path.isfile, pathmod=os.path):
    """回傳 (絕對路徑或 None, 來源):來源是 ``"cli"``、``"repo-default"`` 或 None。"""
    if value:
        return resolve_config_path(value, repo_root, cwd, pathmod), "cli"
    found = default_config_path(repo_root, isfile, pathmod)
    return (found, "repo-default") if found else (None, None)


def read_config(path):
    """讀設定 JSON;讀不到或不是 object 時回傳 {}(呼叫端自行決定要不要報錯)。"""
    if not path:
        return {}
    try:
        with open(path, encoding="utf-8") as handle:
            data = json.load(handle)
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def comfyui_path_from_config(config, config_path, pathmod=os.path):
    """設定檔的 ``comfyui_path`` 轉成絕對路徑;相對路徑以設定檔所在資料夾解析(和 deploy.py 一致)。"""
    value = (config or {}).get("comfyui_path")
    if not value or not config_path:
        return pathmod.normpath(value) if value and pathmod.isabs(value) else None
    return _absolute(value, pathmod.dirname(config_path), pathmod)


def snapshot_candidates(script_dir, explicit=None, repo_root=None, comfyui_path=None, cwd=None,
                        pathmod=os.path):
    """依優先順序回傳 [(資料夾, 來源)]。有 ``explicit`` 時只回傳它(明確指定就不退回其他位置)。"""
    if explicit:
        base = cwd if cwd is not None else os.getcwd()
        return [(_absolute(explicit, base, pathmod), "--snapshot-dir")]
    found = []
    if repo_root and comfyui_path:
        found.append((pathmod.join(comfyui_path, "tools"), "comfyui_path/tools"))
    found.append((pathmod.normpath(os.fspath(script_dir)), "script_dir"))
    unique, seen = [], set()
    for path, source in found:
        key = pathmod.normcase(path)
        if key not in seen:
            seen.add(key)
            unique.append((path, source))
    return unique


def find_snapshot_dir(script_dir, explicit=None, repo_root=None, comfyui_path=None, cwd=None,
                      isfile=os.path.isfile, pathmod=os.path):
    """回傳第一個有 ``device_config.json`` 的資料夾 (path, source);都沒有時丟 SnapshotNotFound。"""
    candidates = snapshot_candidates(script_dir, explicit, repo_root, comfyui_path, cwd, pathmod)
    for path, source in candidates:
        if isfile(pathmod.join(path, DEVICE_CONFIG_NAME)):
            return path, source
    if explicit:
        hint = "--snapshot-dir 要指向有機器快照的資料夾(通常是 <ComfyUI>/tools)。"
    elif repo_root and not comfyui_path:
        hint = ("從 repo 執行時,快照在 <ComfyUI>/tools;請準備 <repo>/local_config.json(含 comfyui_path)、"
                "用 --config 指定,或用 --snapshot-dir 指定快照資料夾。")
    else:
        hint = "請先在這台機器執行 `gameart.py doctor --refresh`(或 detect-device)建立快照。"
    raise SnapshotNotFound([path for path, _ in candidates], hint)
