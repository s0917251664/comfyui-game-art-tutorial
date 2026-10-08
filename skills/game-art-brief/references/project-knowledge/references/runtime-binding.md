# Project path binding

This reference is copied with the project skill so the skill can locate the repository without relying on the current working directory.

Resolve `third_party/claude-obsidian-source.json` relative to this reference file at `../../../third_party/claude-obsidian-source.json`. In that JSON file, resolve `project_root` and `knowledge_root` relative to the manifest's parent directory. Confirm that the active task belongs to the resolved `project_root` before using the resolved `knowledge_root`; otherwise do not use this project skill to search another repository.

These manifest paths identify project files only. They do not imply that the upstream `claude-obsidian` runtime is required, or that it supports native Windows writes.
