---
name: project-knowledge
description: Read and maintain this project's Markdown knowledge vault, including Python, CLI, ComfyUI API, model, and workflow experience notes, without loading unrelated notes or turning observations into automatic generation changes.
---

# Project knowledge

Use this skill only for work in this repository. For path binding, read [runtime-binding.md](references/runtime-binding.md) and confirm that the active task belongs to the project before opening its knowledge vault.

Start with `docs/knowledge/TOOLS.md` to find the relevant topic and skill. Use `rg` to locate relevant notes, then read only the sections needed for the current request. Do not load the whole vault into the prompt. Standard Markdown files and ordinary repository file tools are the knowledge store; no dedicated vault CLI or Obsidian runtime is required. The upstream claude-obsidian skills stored under `third_party/claude-obsidian-skills/` (`wiki`, `wiki-query`, `wiki-ingest`, `save`, and the rest) are not part of this read/write path: they target a separately initialized claude-obsidian vault, and `docs/knowledge/` is not one. Do not load them to read or save project notes.

Use ordinary repository file editing to save Markdown notes; no dedicated CLI is needed. For every document added or changed in this project, have a smaller model draft it, then have the main agent inspect the actual diff and complete delivery. Review sources, links, and whether the text exceeds the evidence or changes a project rule. Routine saves within already authorized scope do not require asking the user again.

Experience notes may cover Python tools, CLI operation, ComfyUI HTTP API calls, model use, and workflow operation. Record common context (date, task, versions, environment, operation, result, evidence, scope, limitations, status) as applicable, then add only the details relevant to that route:

- CLI: command, working directory, exit code, and relevant error.
- HTTP API: endpoint, method, necessary request/response fields (`prompt_id` and history where relevant), timeout/recovery behavior, and output checks. Do not store secrets or large payloads; cite evidence files.
- Model: model and precision, node versions, hardware, prompt/seed when available, and measured quality/speed. Workflow: input order, mask meaning, fixed/adjustable parameters, and acceptance checks.

Omit fields that do not apply; for example, a model is not required for a CLI-only observation.

Keep stable operating contracts in skill files and their references. Put conditional, task-scoped observations in the knowledge vault and cite them when useful; do not turn an observation into a general rule.

Knowledge notes are references, not automatic policy. Do not change model profiles, generation parameters, or `accepted`/`rejected` asset decisions based only on a note. Promoting an observation into a rule or profile requires reproducible evidence and an explicit project decision, recorded through the existing project documentation process.
