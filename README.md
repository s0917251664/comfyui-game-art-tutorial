# ComfyUI AI 產圖與視覺素材工作流

用 [ComfyUI](https://github.com/comfyanonymous/ComfyUI) 建立可控、可重複的 AI 圖像與短片產線，適用於概念圖、角色、UI 圖示與其他遊戲美術素材。

產圖流程鎖在固定的 CLI 腳本（`tools_src/generate.py`）裡，不靠每次臨時拉節點。主要操作方式是直接用自然語言告訴 AI agent 需求，例如：

- 「幫我做一個魔法水晶圖示，透明背景。」
- 「把這張圖的武器換掉，但手部握姿不要變。」
- 「讓這張角色靜圖動起來，做成 2 秒待機動畫。」

agent 會依 [`AGENTS.md`](AGENTS.md) 找到對應的技能文件，確認這台機器撐得起後，才呼叫固定流程，並把結果存到 `output/`。

## 可以做什麼

- **產圖**：文生圖、UI 圖示、草稿精緻化、局部重繪（可鎖結構）、姿勢／角色／風格控制、放大、去背、圖層拆分，以及實驗性的 FLUX.2 路線
- **產短片**：靜圖動起來、運鏡、角色動作、循環特效、轉場、接續與拼接、綠幕合成
- **遮罩工具**：瀏覽器手動畫遮罩（Simple Mask Tool），以及 SAM 2.1 自動候選分割

各 task 的選擇方式與參數見 [產圖流程](skills/comfyui-art-gen/SKILL.md) 與 [產影片流程](skills/comfyui-video-gen/SKILL.md)。

## 快速開始

1. **安裝**：請 AI agent 照 [安裝流程](skills/comfyui-install/SKILL.md) 在這台機器建置 ComfyUI、模型與設定。它會偵測硬體，選擇適合的模型設定檔，並寫出本機專用的 `local_config.json`。
2. **驗證部署**（不需要啟動 ComfyUI）：

   ```bash
   python tools_src/verify_portable_install.py --repo-root . --config local_config.json
   ```

3. **產第一張圖**（先啟動 ComfyUI，以下路徑與 URL 都用 `local_config.json` 裡的值）：

   ```bash
   <python_exe> <generate_script> concept --prompt "fantasy armor character concept art" --config local_config.json --output-dir output
   ```

換電腦或換顯卡時，不要複製舊機器的 `local_config.json`、`device_config.json`、`image_capabilities.json`、`video_capabilities.json`；要在新機器重新偵測。

## 開發檢查

```bash
python -m unittest discover -s tests -p 'test_*.py'
```

測試會 mock 掉 ComfyUI 與模型，不能取代實機 smoke test。

## 文件導覽

| 文件 | 內容 |
|---|---|
| [`教學.md`](教學.md) | 完整建置紀錄、功能地圖、設備選型 |
| [`AGENTS.md`](AGENTS.md) | agent 的入口與原則、各原始碼的職責 |
| [產圖流程](skills/comfyui-art-gen/SKILL.md) / [完整參數](skills/comfyui-art-gen/reference/full-params.md) / [已知限制](skills/comfyui-art-gen/reference/known-limitations.md) | 圖片 task 的判斷、參數與能力邊界 |
| [產影片流程](skills/comfyui-video-gen/SKILL.md) / [單角色動畫流程](skills/comfyui-character-animation-workflow/SKILL.md) | 短片 task、backend 與整組動作的製作驗收 |
| [安裝流程](skills/comfyui-install/SKILL.md) / [模型清單](skills/comfyui-install/reference/models.md) | 新機器環境與模型準備 |
| [模型設定檔設計](docs/model-profiles-design.md) | SDXL/SD1.5 設定檔與各平台的驗證狀態 |
| [已驗證版本](docs/tested-versions.md) | commit、套件版本、模型 SHA-256 與 smoke test 紀錄 |

## 授權

本 repository 沒有附 `LICENSE`，程式碼、文件與圖片不應視為可任意再利用。ComfyUI、custom nodes 與各模型請遵守各自上游的授權條款。
