# 圖片 template 結構變化的原型（PR 4.1）

這裡是 [ADR 草稿：圖片 template 的結構變化](../../../docs/knowledge/decisions/2026-10-08-image-template-variants.md) 的原型，**不是正式 template**：
- 資料夾以 `_` 開頭，`gameart.py run list` 不會列出，runner 也不會載入；
- 全部是 `draft`，模型沒有 sha256 pin；
- 不要從技能或流程引用這裡的檔案。

| 路徑 | 內容 |
|---|---|
| `a/image/<family>/<variant>/` | 方案 A：每種結構組合一份固定 graph（concept 8 份、pose_only 12 份），只用現有 runner |
| `b/image/<family>/<task>/` | 方案 B：一份 base graph（和方案 A 的無變化版本位元組相同），加上 `variants.json` 宣告可以插入／替換節點的 option |
| `option_ops.py` | 方案 B 需要的 runner 擴充原型（獨立 helper，不改 `tools_src/`） |
| `build_drafts.py` | 產生上面所有檔案：用代表值只讀呼叫 builder 一次，再換成占位 |

等價測試是 [`tests/test_image_variant_drafts.py`](../../../tests/test_image_variant_drafts.py)：用 99 組圖片 golden 的子集（24 組），以及全部組合直接和 builder 比（52 組）。

```text
python templates/_drafts/image-variants/build_drafts.py           # 檢查檔案是不是最新
python templates/_drafts/image-variants/build_drafts.py --write   # 只在刻意改原型時執行
python tests/test_image_variant_drafts.py --report                # 印出案例數
```

這些檔案在 `templates/**` 底下，`.gitattributes` 已經設 `-text`，位元組不會被換行轉換。
