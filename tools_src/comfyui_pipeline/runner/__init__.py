"""固定 ComfyUI API graph 的 template runner(第二階段)。

- ``template``:載入 ``templates/<id>/template.json``、驗證、解析 slot 值、套進 graph(patch)。
- ``steps``:``pre``／``post`` 可用的步驟清單(2.1 只驗證名稱與參數,實作在 2.3)。
- ``cli``:``gameart.py run list|show|<id> --dry-run``。
- ``recipe``:``templates/recipes/<id>/recipe.json`` 的多步驟流程與確認點續跑(``gameart.py recipe``)。

格式與決策見 docs/knowledge/decisions/2026-10-07-phase2-template-runner.md。只用標準庫。
"""
