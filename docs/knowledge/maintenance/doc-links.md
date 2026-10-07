---
type: maintenance
status: current
---
# 文件連結規則

repo 內的 Markdown 要在 clean clone 上就能點得通。`tests/test_doc_links.py` 會檢查所有追蹤中的 `.md`（上游 vendor `third_party/claude-obsidian/` 除外）：

- 相對連結的目標要存在；
- 連到 `.md` 的 `#錨點` 要對得到 GitHub 風格的標題錨點（重複標題依序加 `-1`、`-2`）；
- 不可以連到 `output/`。

單獨執行這個測試（在 repo 根目錄）：

```
PYTHONPATH=tools_src:tests python -m unittest test_doc_links
```

Windows 的 `PYTHONPATH` 用 `;` 分隔；也可以直接 `python tests/test_doc_links.py`。在 ComfyUI venv 裡不要寫成 `tests.test_doc_links`，因為 venv 裡有套件（color_matcher）裝了頂層 `tests` 套件，會蓋掉 repo 的 `tests/`。

## 本機證據（`output/`）怎麼寫

`output/` 不進版控（`.gitignore`），裡面的實測證據只存在跑測試的那台機器上。文件引用這些證據時寫成純文字：

```text
validation（本機證據：`output/scail2-test/replace33/validation.json`）
```

- 路徑一律從 repo 根目錄寫起（`output/...`），不寫 `../../output/...`。
- 標籤本身就是路徑時，只寫 `` `output/xxx/`（本機證據） ``。
- 需要讓其他機器也看得到的小型證據（例如 smoke 報告），請複製進 repo 內的對應位置（例如 `docs/knowledge/validation/<platform>/`），再用一般相對連結指過去。

## 允許的例外

例外寫在 `tests/test_doc_links.py` 的 `ALLOWED_MISSING`，並附上原因。例外失效時（連結被修好或刪除）測試也會失敗，提醒移除。目標是 gitignore 的本機檔時（列在 `MACHINE_LOCAL_FILES`，目前只有 `local_config.json`），clean checkout 沒有、已設定的機器有，兩種情況都算通過。目前只有兩個：

| 來源 | 連結 | 原因 |
|---|---|---|
| `AGENTS.md` | `local_config.json` | 本機設定檔，刻意不進版控 |
| `third_party/claude-obsidian-skills/wiki/references/frontmatter.md` | `../../../WIKI.md` | 上游原文（原本指向上游 repo 根目錄）；修改會破壞 hash 紀錄 |

## 更正紀錄

- 2026-10-07：PR #1 的 commit `287acca`（`docs: fix broken links to files outside version control`）實際只修了 2 個連結（skye-repair 的 `protocol.md`、edit-brief `scenarios.md` 的 `reports/`）。當時還有 89 個連到 `output/` 的連結沒處理，標題說得比實際範圍大。這 89 個已在 1.5-A 改寫成上面的純文字標註，並由 `tests/test_doc_links.py` 防止再出現。
