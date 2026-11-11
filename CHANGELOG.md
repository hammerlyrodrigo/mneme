# Changelog

## Unreleased

- Entry files with YAML-subset frontmatter, one per entry; per-branch handovers.
- Commands: `init` (`--write-agents`, `--claude`, `--hide-in-diffs`), `new`,
  `set`, `resolve`, `done`, `supersede`, `handover`, `brief`, `recall`, `list`,
  `show`, `changes`, `check`.
- Saving an entry no longer writes an `updated` stamp, so identical edits on
  two branches merge cleanly.
- Frontmatter accepts block-style lists (`tags:` then `- a` lines) on read.
