"""`mneme dream`: a consolidation prompt for an agent. It never changes memory.

The prompt carries the real commands, generated from the CLI's own field
tables, and the active entries, with likely overlaps grouped first. Two
entries overlap when the words of their titles, summaries, tags and keywords
mostly agree, each word weighted by how rare it is, so that words every entry
uses ("entry", "file") don't chain everything into one group. Shared links
don't group entries: most entries in a small project link the same core files.
The agent acts by running ordinary `mneme` commands, reviewed in a PR like any
other memory change.
"""

from __future__ import annotations

import math

from mneme.model import STATUSES, Entry
from mneme.recall import STOPWORDS, stem, tokens

DREAM_TYPES = ("decision", "learning", "concept", "note")
# Weighted overlap above which two entries are shown as a likely overlap.
# Distinct entries in this repo score up to about 0.2.
OVERLAP = 0.3

INSTRUCTIONS = """\
# Consolidate project memory

Below are {count} active entries from this repo's memory. Propose changes that
make it smaller and clearer, then make them with the commands listed. Nothing
changes until you run them, and the result is reviewed in a pull request.

Look for:

- duplicates and near-duplicates: record one entry that supersedes them;
- several learnings that point to one rule: record a decision or concept for
  the rule and retire the learnings;
- entries that no longer hold: give them an inactive status;
- entries whose gist (the line under each one) says little: add a summary and
  keywords.

Rules:

- Read entries in full with `mneme show <id> [<id>...]` before changing them.
- Use only facts the entries state. Leave an entry alone when unsure.
- `--supersedes` only takes entries of the new entry's own type. To retire an
  entry of another type, run `mneme set <id> --status archived` (a decision:
  `deprecated`) and mention its id in the new entry's context.
- Settled entries can then be moved out of the way with `mneme archive <id>...`.
- Report what you changed and why, in a few lines.
"""


def describing_words(entry: Entry, written: dict[str, str]) -> set[str]:
    """Stemmed words of the title, summary, tags and keywords; `written` maps each back."""
    found = set()
    for text in [entry.title, entry.summary, *entry.tags, *entry.keywords]:
        for token in tokens(text):
            if token not in STOPWORDS and len(token) > 2:
                found.add(stem(token))
                written.setdefault(stem(token), token)
    return found


def overlap_groups(entries: list[Entry]) -> list[tuple[list[Entry], list[str]]]:
    """(entries, shared words) for each group of likely overlaps, largest first."""
    written: dict[str, str] = {}
    words = [describing_words(e, written) for e in entries]
    df: dict[str, int] = {}
    for found in words:
        for word in found:
            df[word] = df.get(word, 0) + 1
    idf = {w: math.log(len(entries) / d) for w, d in df.items()}

    def similarity(a: set[str], b: set[str]) -> float:
        union = sum(idf[w] for w in a | b)
        return sum(idf[w] for w in a & b) / union if union else 0.0

    parent = list(range(len(entries)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(len(entries)):
        for j in range(i + 1, len(entries)):
            if similarity(words[i], words[j]) >= OVERLAP:
                parent[find(i)] = find(j)

    members: dict[int, list[int]] = {}
    for i in range(len(entries)):
        members.setdefault(find(i), []).append(i)
    groups = []
    for indexes in members.values():
        if len(indexes) > 1:
            shared = set.intersection(*(words[i] for i in indexes))
            # Name the group by the words its entries share, rarest first, as written.
            names = [written[w] for w in sorted(shared, key=lambda w: (-idf[w], w))[:5]]
            groups.append(([entries[i] for i in indexes], names))
    return sorted(groups, key=lambda g: len(g[0]), reverse=True)


def entry_line(entry: Entry, width: int = 140) -> str:
    line = f"- {entry.id} {entry.type}: {entry.title}"
    gist = entry.gist()
    if gist:
        gist = gist if len(gist) <= width else gist[: width - 3].rstrip() + "..."
        line += f"\n  {gist}"
    return line


def build_dream(entries: list[Entry], commands: list[str], limit: int) -> str:
    """The prompt; `commands` are usage lines for the commands the agent may run."""
    pool = [e for e in entries if e.type in DREAM_TYPES and e.active]
    shown = pool[-limit:] if limit else pool
    out = [INSTRUCTIONS.format(count=len(shown))]
    if len(shown) < len(pool):
        out.append(f"Only the newest {len(shown)} of {len(pool)} are shown; narrow with --tag or --path.\n")

    out.append("## Commands\n")
    out.append("```")
    out += commands
    out.append("```\n")
    out.append("Statuses:\n")
    out += [f"- {t}: {', '.join(STATUSES[t])}" for t in DREAM_TYPES]
    out.append("")

    groups = overlap_groups(shown)
    grouped = {id(e) for group, _ in groups for e in group}
    if groups:
        out.append("## Likely overlaps\n")
        for n, (group, shared) in enumerate(groups, start=1):
            out.append(f"### Group {n}" + (f" (shared words: {', '.join(shared)})" if shared else "") + "\n")
            out += [entry_line(e) for e in group]
            out.append("")
    rest = [e for e in shown if id(e) not in grouped]
    if rest:
        out.append("## Other entries\n" if groups else "## Entries\n\nNo two entries look alike; "
                   "check for entries that no longer hold or that point to one rule.\n")
        out += [entry_line(e) for e in rest]
        out.append("")
    return "\n".join(out).rstrip() + "\n"
