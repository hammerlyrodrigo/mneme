# Mneme

A small, dependency-free CLI for project memory that lives in a git repo
beside the code: decisions, learnings, questions, reminders, concepts and
per-branch handovers. It's built for AI-assisted and spec-driven development.

## Start every session here

Run `uv run mneme brief`. This repo keeps its own memory with Mneme: the
plan, the reasons behind the design, open questions and next steps are in
`.memory/`, read through the commands described below. In this repo, run
the tool as `uv run mneme ...`, or install it once with
`uv tool install -e .`.

`legacy/mneme_v0.py` is reference material to port from. Don't edit or run it
in this repo.

<!-- mneme:start -->
## Project memory (Mneme)

This repo keeps project memory in `.memory/`, managed with the `mneme` CLI.
Recall it when needed; don't read `.memory/` files directly.

- At session start, run `mneme brief`.
- Before changing a file, run `mneme recall --path <path>`; for a topic,
  `mneme recall <words>`; `mneme show <id>...` for entries in full.
- As you go, record decisions, learnings, open questions, deferred work and
  terms with `mneme new <type>` (see `mneme new --help`).
- Before you stop, run `mneme handover --summary ... --next ...`.
<!-- mneme:end -->
