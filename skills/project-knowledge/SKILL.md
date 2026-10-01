---
name: project-knowledge
description: Read and maintain this project's Markdown knowledge vault without loading unrelated notes or turning observations into automatic generation changes.
---

# Project knowledge

Use this skill only for work in this repository. For path binding, read [runtime-binding.md](references/runtime-binding.md) and confirm that the active task belongs to the project before opening its knowledge vault.

Start with `docs/knowledge/TOOLS.md` to find the relevant topic and skill. Use `rg` to locate relevant notes, then read only the sections needed for the current request. Do not load the whole vault into the prompt. Standard Markdown files and ordinary repository file tools are the knowledge store; no dedicated vault CLI or Obsidian runtime is required.

Use ordinary repository file editing to save Markdown notes; no dedicated CLI is needed. For every document added or changed in this project, have a smaller model draft it, then have the main agent inspect the actual diff and complete delivery. Review sources, links, and whether the text exceeds the evidence or changes a project rule. Routine saves within already authorized scope do not require asking the user again.

When adding an experience note, include its date, model and task when known, applicable platform or hardware, source or evidence, scope, limitations, and status. Keep a single observation within its demonstrated scope.

Knowledge notes are references, not automatic policy. Do not change model profiles, generation parameters, or `accepted`/`rejected` asset decisions based only on a note. Promoting an observation into a rule or profile requires reproducible evidence and an explicit project decision, recorded through the existing project documentation process.
