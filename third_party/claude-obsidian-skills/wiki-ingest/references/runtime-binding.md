# Codex runtime binding

This adapter applies only to the independently installed Codex skill copy. It does not alter the upstream skill or product files.

## Resolve the product root

For this project skill copy (stored at `third_party/claude-obsidian-skills/<skill>/references/`), resolve `PRODUCT_ROOT` from this reference file's location using `../../../claude-obsidian`, which is the vendored `third_party/claude-obsidian` product tree. Confirm that `scripts/claude-obsidian.py` exists before invoking it. Use only the upstream scripts and paths documented by the skill. In each shell command, explicitly set `PRODUCT_ROOT` to the resolved absolute path or pass the complete absolute script path; this file does not set a process environment variable automatically. Do not infer the root from the current working directory.

## Project knowledge and platform boundary

This repository's native project knowledge entry point is `docs/knowledge/` under its project-knowledge instructions. It is a scoped Markdown knowledge area, not a full claude-obsidian vault adapter and does not share the upstream ledgers or ingest schema. Upstream ledger, capture, ingest, and other vault-write operations require an explicitly selected, initialized user vault and the upstream preview/apply workflow. On native Windows, use only supported inspection, dry-run, and retrieval operations; upstream vault writes fail closed and require WSL. Do not describe the project knowledge area as implementing the upstream vault schema or write capabilities.
