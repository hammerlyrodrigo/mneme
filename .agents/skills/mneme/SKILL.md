---
name: mneme
description: Project memory for this repo. Use at session start (mneme brief), before
  changing code (mneme recall --path), when making a decision, learning something,
  leaving a question open or deferring work, and before ending a session (mneme handover).
---

# Project memory (Mneme)

This repo keeps project memory in `.memory/`, managed with the `mneme` CLI.
Memory is recalled when needed, not read in bulk:

- At the start of a session, run `mneme brief`.
- Before changing a file or area, run `mneme recall --path <path>`. For a
  topic, run `mneme recall <words>`. Run `mneme show <id>` only for entries
  you need in full.
- Don't read `.memory/` files directly. The commands keep context small.
- Record things briefly as they happen:
  - `mneme new decision --title ... --context ... --decision ... --consequences ...`
    for a non-obvious choice and why;
  - `mneme new learning --title ... --tried ... --result ... --takeaway ...`
    for something tried and what it taught, especially failed approaches;
  - `mneme new question --text ...` for something deliberately left open;
  - `mneme new reminder --trigger ... --action ...` for something decided but
    deferred until a trigger;
  - `mneme new concept --term ... --definition ...` for a project term.

  Add `--links <paths>` to tie an entry to the code or spec it is about, so
  `recall --path` finds it. `--stdin` takes the same fields as JSON.
- Close loops with `mneme resolve <id> --answer ...`, `mneme done <id>` and
  `mneme supersede <old> --by <new>`.
- A decision made inside a feature's spec or plan becomes a `decision` entry
  when it outlives the feature.
- Before ending a session, run
  `mneme handover --summary ... --done ... --next ... [--blockers ...]`.
- `mneme changes --markdown` prints this branch's memory for a PR description.
