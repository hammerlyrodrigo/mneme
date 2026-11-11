This repo keeps project memory in `.memory/`, managed with the `mneme` CLI.
Memory is recalled when needed, not read in bulk. Don't read `.memory/`
files directly; the commands keep context small.

## Recall

- At the start of a session, run `mneme brief`.
- Before changing a file or area, run `mneme recall --path <path>`. For a
  topic, run `mneme recall <words>`. Each hit prints a one-line gist; run
  `mneme show <id> [<id>...]` only for entries you need in full.
- If recall prints partial matches, try other words before concluding that
  nothing is known.

## Record

Record things briefly as they happen. Give every entry a `--summary` (one
line stating the outcome), `--keywords` for words a later search might use
that the text doesn't (synonyms, the general term), and `--links <paths>` to
the code or spec it is about, so `recall --path` finds it.

- `mneme new decision --title ... --context ... --decision ... --consequences ...`
  for a non-obvious choice and why;
- `mneme new learning --title ... --tried ... --result ... --takeaway ...`
  for something tried and what it taught, especially failed approaches;
- `mneme new question --text ...` for something deliberately left open;
- `mneme new reminder --trigger ... --action ...` for something decided but
  deferred until a trigger;
- `mneme new concept --term ... --definition ...` for a project term.

`--stdin` takes the same fields as a JSON object. Keep each section short.
A decision made inside a feature's spec or plan becomes a `decision` entry
when it outlives the feature.

## Close loops

- `mneme resolve <id> --answer ...`, `mneme done <id>`,
  `mneme supersede <old> --by <new>`.
- `mneme set <id> --summary ... --keywords ...` to improve an entry that
  recall described badly.

## Hand over

- Before ending a session, run
  `mneme handover --summary ... --done ... --next ... [--blockers ...]`.
- `mneme changes --markdown` prints this branch's memory for a PR description.
