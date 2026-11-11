This repo keeps project memory in `.memory/`, managed with the `mneme` CLI.
Recall it when needed; don't read `.memory/` files directly.

- At session start, run `mneme brief`.
- Before changing a file, run `mneme recall --path <path>`; for a topic,
  `mneme recall <words>`; `mneme show <id>...` for entries in full.
- As you go, record decisions, learnings, open questions, deferred work and
  terms with `mneme new <type>` (see `mneme new --help`).
- Before you stop, run `mneme handover --summary ... --next ...`.
