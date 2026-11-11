# Changelog

## Unreleased

- Entry files with YAML-subset frontmatter, one per entry; per-branch handovers.
- Commands: `init` (`--write-agents`, `--claude`, `--hide-in-diffs`), `new`,
  `set`, `resolve`, `done`, `supersede`, `handover`, `brief`, `recall`, `list`,
  `show`, `changes`, `check`.
- Saving an entry no longer writes an `updated` stamp, so identical edits on
  two branches merge cleanly.
- Frontmatter accepts block-style lists (`tags:` then `- a` lines) on read.
- Entries take an optional one-line `summary` and `keywords`; `recall` prints
  the summary (or the first line of the main section) under each hit.
  `new` notes sections longer than 600 characters.
- `recall` stems words, ignores stopwords, weights rare terms, and shows
  labelled partial matches instead of "Nothing found" when no entry has
  every word. It no longer prints the type or the default status.
- `show` takes several ids and is compact by default; `--raw` prints the file.
- `set` can change `--summary` and `--keywords`; `--status` is optional.
- `author` falls back to `git config user.name`; a new `agent` field (from
  `--agent`, `MNEME_AGENT`, or detected) records the tool that wrote an entry
  or handover.
