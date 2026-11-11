# Mneme: design review and improvement report

Nov 11, 2026 · @Rodrigo

## Verdict

The approach is right and worth continuing: Markdown entries in git, recalled on demand, beat both a local SQL database and a vector database for shared project memory. The storage needs small repairs; the retrieval needs real work.

- **Storage:** keep one file per entry. It merges cleanly across branches, needs no sync, and people can read it. Its human side is weaker than its agent side: folders have no order and hand edits break easily.
- **Biggest weakness:** recall misses entries that use different words. `recall database` returns nothing, though a decision about SQLite exists. An agent that is told "nothing found" repeats old work.
- **Context use:** already small, at about 1,800 tokens for a typical session. A one-line summary per entry would remove most follow-up reads.
- **Naming:** keep `decision`, `learning` and the other working names as the interface. Use the human-memory model to explain and guide the design, not as a second set of names.
- **Databases:** neither as the source of truth. A gitignored SQLite cache becomes useful only past a few thousand entries. A vector database costs more than the problem it solves here.
- **Teams and agents:** parallel branches already work. Fix handovers on shared branches, edits that agree but still conflict, and contradicting decisions that merge silently.
- **Prior art:** nothing does the same job. Letta's Context Repositories and Claude Code's auto memory are the closest, and both confirm the files-plus-on-demand design.

The five changes to make first are small: better matching in recall, a summary line per entry, a compact `show`, no `updated` stamp, and tolerant frontmatter parsing.

## How memory is stored today

The storage model is sound: one Markdown file per entry, committed to git, with nothing generated. I would keep it.

Each entry lives at `.memory/<type>s/<id>-<slug>.md`. A short frontmatter block holds the id, type, title, status, dates, author, branch, tags and links. The body uses fixed `##` sections per type, for example Context, Decision and Consequences for a decision. Each branch also has one handover file at `.memory/handover/<branch>.md`. This repo holds 29 entries and 1 handover in 31 files, 18 KB in total.

**Why it makes sense**

- New entries from different branches never conflict, including in GitHub's web merge, which ignores custom merge drivers. That was the main failure of the v0 JSONL log.
- Nothing is derived, so nothing goes stale. v0's SQLite index and generated views both drifted.
- History, blame and review come from git for free. A branch's decisions show up in its PR diff.
- Files on disk cost no tokens. Only what a command prints reaches the agent's context.

**How friendly it is for a person**

| Aspect | Verdict | Detail |
| --- | --- | --- |
| Reading one entry | Good | Plain Markdown; GitHub renders the frontmatter as a table. |
| Finding an entry by browsing | Weak | Files sort by random id (`D-04f13c`, `D-0a1f83`), so a folder shows no order and no overview. |
| Referring to an entry | Fair | `D-6b7078` is hard to remember or say aloud. Prefix lookup and the slug in the filename help. |
| Editing by hand | Fragile | The frontmatter parser rejects block lists (`tags:` followed by `- a` lines), the style most editors and formatters write. A rejected file drops out of recall. |
| Seeing the whole picture | Missing | No index page or viewer yet. A person has only `mneme list <type>`, one type at a time. |
| Writing an entry | Good for agents, heavy for people | `mneme new decision` needs four long flags. There is no `--edit` that opens a template in an editor. |

## Weaknesses

The weakest part is retrieval, not storage: recall misses relevant entries, and its results say too little to act on. The table lists every problem I found, most serious first. Evidence comes from running the commands in this repo on 2026-11-11.

| # | Weakness | Evidence | Effect |
| --- | --- | --- | --- |
| W1 | Recall misses on different wording | Every query word must match, with no stemming or synonyms (recall.py:43). `recall database` finds nothing, though D-956800 is about SQLite. `recall merge conflict` omits D-6538b2, "Editing one entry on two branches always conflicts". | An agent that reads "Nothing found" concludes there is no memory and repeats old work. |
| W2 | Results carry no gist | A recall line is id, title and status. Learning what was decided takes one `show` call per entry, about 1,000 characters each, a third of it frontmatter. | More tool calls and more tokens than the answer needs. |
| W3 | Capture depends on discipline | Recording and handover happen only if the agent follows the instruction text. Nothing prompts it at session end or before context compaction. | A skipped handover leaves the next session stale. This is the usual way such systems die. |
| W4 | No staleness signal | `check` confirms that a linked file exists, not that it still matches the entry. No entry has a last-verified date. | Decisions rot silently and are recalled as current. |
| W5 | Contradictions merge cleanly | Two branches that record opposite decisions write two different files. Git and `check` both stay silent. | The team learns of the clash only when someone reads both. |
| W6 | Identical edits conflict | `save()` stamps `updated` to the second (store.py:157). Two branches that both mark one reminder done conflict, though they agree. | Merge noise that teaches people to resent `.memory/`. |
| W7 | Handover is one overwritten file per branch | Two people or agents on one branch replace each other's handover. Each merged branch leaves a file on main that `check` asks someone to fold in by hand. | Lost context on shared branches; a chore on every merge. |
| W8 | Strict frontmatter | Block-style lists and multi-line values are parse errors (model.py:265). | A formatter or an Obsidian edit can remove an entry from recall. |
| W9 | Folders have no order | Filenames start with a random id. | People cannot browse by date or see what is new. |
| W10 | Brief shows the newest decisions, not the relevant ones | "Recent decisions (3 of 16)" is chosen by date alone (brief.py:117). | On a feature branch the three lines are usually unrelated to the work. |
| W11 | Fixed instruction cost | The AGENTS.md block is 25 lines (1.5 KB) and loads in every session, used or not. | A permanent cost of roughly 400 tokens per session. |
| W12 | The planned `compact` adds a second format | Folding inactive entries into one archive file per type needs a second parser, breaks per-file history, and conflicts with any branch still editing an archived entry. | More code and a new conflict source, to solve a problem not yet seen. |
| W13 | No write lock inside one working tree | `save()` reads, changes and replaces a file with no lock. | Two agents in one checkout can lose a status change. Rare. |
| W14 | Weak provenance | `author` is free text ("claude" on all 29 entries) and `branch` goes stale after merge. | No way to tell which person or agent session wrote an entry. |

## Similar approaches

No existing tool does the same job, but three come close, and several pieces should be borrowed instead of rebuilt. Mneme's distinct ground is narrow: typed entries with a lifecycle, shared through git and reviewed in PRs, branch-aware, and independent of any one agent.

| Tool | How it stores memory | How it finds memory | Shared with the team | What to borrow | Where Mneme differs |
| --- | --- | --- | --- | --- | --- |
| [Letta Context Repositories](https://letta.com/blog/context-repositories) | Markdown files with frontmatter in a git repo; every change is a commit | The file tree is always in the prompt; files are opened on demand; no vector index | Per agent; shared repositories need Letta's cloud | A one-line `description` per file; a git worktree per subagent, merged back | Memory belongs to the agent, not the project; tied to Letta Code |
| [Claude Code auto memory](https://code.claude.com/docs/en/memory) | Markdown topic files plus a `MEMORY.md` index under `~/.claude/projects/` | The first 200 lines or 25 KB of the index load each session; topic files are read on demand | No, it is local to one machine | The index-plus-detail split | Not in the repo, not reviewed, Claude only |
| [Beads](https://github.com/steveyegge/beads) | A Dolt database, synced through a git ref; a JSONL export for viewers | Queries; `bd prime` injects context | Yes | Hash ids against collisions (already done); "memory decay" that summarises old closed items | Tasks first; a database, not readable files; much heavier |
| [Basic Memory](https://github.com/basicmachines-co/basic-memory) | Markdown files as the source of truth, plus a local SQLite index | Full-text and vector ranking combined, served over MCP | Through git, by hand | Files as truth with a local index beside them | A personal knowledge graph; no status lifecycle or handover; AGPL-3.0; needs Python 3.12 and an MCP server |
| [Serena memories](https://oraios.github.io/serena/02-usage/045_memories.html) | Free-form Markdown in `.serena/memories/`, committed | The agent lists names and reads files | Yes | Small focused files over one large one | No types, status or links to code |
| [claude-mem](https://github.com/thedotmack/claude-mem) | SQLite plus a Chroma vector store, filled by hooks | Keyword and semantic search | No, local | Automatic capture at session events | Not in git; a background service; Claude only |
| [MADR](https://adr.github.io/madr/) and adr-tools | One Markdown file per decision, usually in `docs/adr/` | Browsing and grep | Yes | The decision template people already know; numbered, ordered filenames | Decisions only; no agent retrieval |
| Cline Memory Bank | A fixed set of Markdown files | All files are read in full at each session start | Yes | Nothing; it is the context-heavy pattern Mneme avoids | Bulk loading |

Hosted memory layers such as Mem0, Zep and LangMem solve a different problem: remembering facts about users across chat sessions, in a vector or graph database. They are not project memory and do not live in the repo.

Two honest cautions. A solo developer who uses only Claude Code gets much of this from `CLAUDE.md` plus auto memory, so Mneme earns its place only with a team, several agents or several tools. And Letta's move to Markdown in git, announced in February 2026, shows the same design from a funded vendor; it confirms the direction and is the one to watch.

Sources: the Letta, Claude Code, Beads and Basic Memory pages were opened on 2026-11-11. The Serena and claude-mem rows come from search summaries. The MADR and Cline rows are from memory and should be treated as approximate.

## Naming

Keep the current working names for types, folders and commands, and use the human-memory model as the frame that explains them. Do not offer both as interchangeable names.

The v0 script mapped its types onto five kinds of human memory. The mapping is appealing but not one-to-one:

| Current name | Human-memory kind | Fit |
| --- | --- | --- |
| handover | Working memory (a checkpoint of the live session) | Good |
| concept | Semantic memory (what things mean) | Good |
| reminder | Prospective memory (remembering to do something later) | Good |
| learning | Episodic (what happened) that becomes semantic (the takeaway) | Straddles two |
| decision | Recorded as an event, then acts as a standing rule | Straddles two |
| question | None; it is a known gap | No counterpart |
| note | None | No counterpart |
| AGENTS.md and skills | Procedural memory (how to do things) | Good, but stored outside `.memory/` |

**Why the working names should stay the interface**

- They explain themselves. An agent picks `decision` or `learning` correctly with no gloss. `episodic` needs a definition in every instruction block, which costs tokens in every session.
- The memory kinds are too coarse. Decisions and learnings would share one name, and questions and notes would have none.
- People who know architecture decision records already know what a decision entry is.
- Two vocabularies double what people and agents must learn, and reviews would mix them.

**Where the human-memory model earns its place**

- In the README and the viewer, as the one-table explanation of why these types exist. The four-part split into working, episodic, semantic and procedural memory is the standard vocabulary in agent research ([CoALA, 2023](https://arxiv.org/abs/2309.02427)), so readers will recognise it.
- As a design guide for behaviour. Consolidation turns many learnings into one concept or decision, which is the job of `dream`. Forgetting retires what is no longer used. Prospective memory needs triggers that can be checked. Working memory is small, which is why `brief` is capped.
- In the command names, which already carry the theme: Mneme, `recall`, `brief`, `dream`.

## Context economy

The active-recall design already keeps context small; the remaining waste is in follow-up `show` calls and in the fixed instruction text. A session that briefs, recalls twice and shows three entries spends about 7 KB, close to 1,800 tokens, and nearly half of that is the three `show` calls.

| Where context is spent | Measured size | When |
| --- | --- | --- |
| Instruction block in AGENTS.md | 1.5 KB | Every session, always |
| `mneme brief` | 1.8 KB | Every session start |
| `mneme recall` with 5 hits | 0.4 KB | Per query |
| `mneme show` for one decision | 1.0 KB, about a third frontmatter | Per entry |

**Changes that cut the most, in order**

1. Give each entry a one-line `summary` that states the outcome, and print it under each recall hit. About 100 characters then replace a 1,000-character `show` for most hits.
2. Make `show` compact by default: id, title, status, links and body. Leave the path, dates, author, branch and tags to `show --raw`.
3. Let `show` take several ids, so three entries cost one tool call.
4. In `brief`, print the handover's Summary, Next and Blockers but not Done, which is history. Replace "recent decisions" with entries linked to the files this branch has changed.
5. Cut the AGENTS.md block to about six lines: brief at start, recall before changes, record as you go, handover at the end. Move the flag details to `mneme help` or the skill, which load only when needed.
6. Drop the type word and the default status from recall lines; the id letter already gives the type.
7. Warn at write time when a section runs past about 600 characters, so entries stay short at the source.

A missed recall costs more context than any of these, because the agent then re-derives the answer from code. Fixing W1 is therefore also a context saving.

## Storage and search

Plain files in git are the better source of truth for this job, and neither database should replace them. A database is only worth adding later as a disposable local cache, and SQLite would be the choice, not a vector store.

| Criterion | Markdown files in git (today) | Local SQLite | Local vector database |
| --- | --- | --- | --- |
| Merging across branches | Git merges files; new entries never conflict | A binary file cannot be merged or reviewed | Same, plus embeddings differ by model version |
| Readable by people | Yes, in any editor and on GitHub | Only through a tool | Only through a tool |
| Staying in sync | Nothing to sync | Must be rebuilt after every pull, checkout and hand edit | Same, and re-embedding is slow |
| Search quality | Keyword only; misses different wording (W1) | Keyword with proper ranking (FTS5, BM25) | Finds meaning, not only words |
| Dependencies | None | None (in Python's standard library) | An embedding model of hundreds of MB, or a paid API |
| Repeatable results | Yes | Yes | Varies with model and index settings |
| Speed | Measured below | Milliseconds | Milliseconds after indexing |

**Measured speed of the current approach.** I copied this repo's entries to make test sets. Loading 2,000 entries took 0.2 s once the files were in the operating system's cache, and a recall over them took 0.03 s. The first read of freshly written files was far slower on this Windows machine: 6.8 to 8.2 s for 2,000 files and 39.6 s for 10,000, most likely antivirus scanning. So the in-memory scan is fine into the low thousands, with one caveat: the first command after a large checkout on Windows may pause.

**Why not a vector database.** Its one real advantage is matching by meaning, which is the W1 problem. That problem has cheaper fixes for a store of this size and kind:

- The reader is a language model, which can rephrase a query and try again if the tool tells it what almost matched.
- The writer is also a language model, which can add search keywords and synonyms at capture time. That gives most of the benefit of embeddings with no index.
- Entries are short, curated and titled, unlike raw chat logs, so ranked keyword search works well on them.

The evidence points the same way. Letta's Markdown-in-git memory ships with no vector index by default ([announcement](https://letta.com/blog/context-repositories)). Letta also reported 74.0% on the LoCoMo benchmark for an agent using file tools, above Mem0's reported 68.5% ([post](https://www.letta.com/blog/benchmarking-ai-agent-memory)); that run did include embedded file search and both figures are vendor-reported, so treat it as suggestive only.

**What to do instead**

1. Rank partial matches with BM25 scoring and show the best ones when no entry matches every word, labelled as partial.
2. Add light stemming so `conflict` matches `conflicts` in the body as well as the title.
3. Add an optional `keywords` field that the agent fills when it records an entry.
4. Add a gitignored SQLite FTS5 cache only if memory passes a few thousand entries or the first-read pause becomes a complaint. Rebuild it from the files whenever their modification times change; never commit it.

This keeps decision D-956800 intact. Its claim that a scan is "fast enough for thousands of small files" holds for warm reads and should note the cold-read caveat.

## Concurrency

One file per entry already handles the common case, where branches add entries in parallel. The gaps are in handovers, in edits that agree but still conflict, and in contradictions that git cannot see.

The rule to keep: memory travels with the branch and is reviewed in its PR. Merging the PR is the moment a decision becomes the team's. Nothing should write to shared memory outside that path.

| Situation | What happens today | Recommendation |
| --- | --- | --- |
| Two branches each add entries | Merges cleanly, also in web merges | Keep |
| Two branches edit one entry differently | A normal git conflict in one small file | Keep; a person should look |
| Two branches make the same change to one entry | Conflict, because each stamps a different `updated` time (W6) | Stop writing `updated`; git log already has it. Identical edits then merge cleanly |
| Two branches record opposite decisions in separate files | Silent (W5) | In `changes` and `check`, list entries added on main since the branch point whose links overlap this branch's entries or changed files. Flag any entry superseded by two different entries. Run `mneme check` in CI on PRs |
| A long-lived branch misses new memory on main | Unseen until main is merged in | `brief` prints one line: "main has N new entries since you branched" |
| Two people or agents on one branch | Each handover replaces the last; two commits conflict (W7) | One writer per branch for the handover. Others record entries only. If shared branches are common, split to one handover per branch and author |
| A merged branch leaves its handover on main | `check` asks someone to fold it in by hand | Add `mneme handover --close` as the PR's last commit: it turns open Next items into reminders or questions and deletes the branch file |
| Several agents in one working tree | New entries are safe: creation is exclusive and ids are checked. Edits to one entry can race (W13) | A lock file around `save()`. Subagents record entries; only the lead agent writes the handover |
| Several agents in parallel worktrees | Each has its own branch and its own copy of `.memory/`; behaves like branches | Recommend this as the pattern for parallel agents. Letta uses the same approach |
| Two branches draw the same id | About 0.007% when 50 unmerged entries of one type exist at once; `check` reports duplicates | Keep |
| Archiving on main while a branch edits the entry | Would conflict if entries are folded into one archive file (W12) | Move inactive files to `.memory/archive/<type>s/` unchanged; git follows the rename |

**Who wrote it.** Default `author` to the git user name, and add an `agent` field for the tool that wrote the entry on that person's behalf. A team needs to tell a colleague's decision from an agent's guess, and all 29 entries here say only "claude".

## Recommended improvements

Do items 1 to 5 before migrating Demiurge: each is small, and the migration multiplies whatever the entry format lacks. Effort is my estimate: small is under half a day, medium is one to two days.

| # | Improvement | Fixes | Effort | Payoff |
| --- | --- | --- | --- | --- |
| 1 | Recall shows ranked partial matches when no entry matches every word, and stems words | W1 | Small | High |
| 2 | Add a one-line `summary` and optional `keywords` to entries; recall prints the summary | W1, W2 | Small | High |
| 3 | Compact `show` by default, `--raw` for everything, several ids per call | W2 | Small | Medium |
| 4 | Stop writing `updated` on every save | W6 | Small | Medium |
| 5 | Accept block-style lists in frontmatter on read | W8 | Small | Medium |
| 6 | `brief` shows entries linked to the branch's changed files, drops the handover's Done section, and reports new entries on main | W10 | Medium | High |
| 7 | Cut the AGENTS.md block to about six lines | W11 | Small | Medium |
| 8 | `mneme handover --close` to fold and delete a branch handover before merge | W7 | Medium | Medium |
| 9 | Overlap warnings in `changes` and `check`, plus a CI recipe for PRs | W5 | Medium | High for teams |
| 10 | Opt-in Claude Code hooks from `init --claude`: run `brief` at session start, prompt for a handover before compaction and at stop | W3 | Medium | High |
| 11 | `check --stale`: list entries whose linked files changed heavily since the entry was written | W4 | Medium | Medium |
| 12 | Default `author` to the git user; add an `agent` field | W14 | Small | Medium for teams |
| 13 | Archive by moving inactive files to `.memory/archive/`, in place of the planned folding `compact` | W12 | Small | Medium |
| 14 | A way for people to browse: `mneme list` across all types, `new --edit`, then the viewer planned for v0.2 | W9 | Medium | Medium |
| 15 | A lock file around `save()` | W13 | Small | Low |
| 16 | A gitignored SQLite FTS5 cache | Speed | Medium | None until thousands of entries |

**Not recommended:** a vector database, renaming the types to memory kinds, and folding entries into archive files.

**Decisions these touch.** Item 4 revises D-6538b2: different edits would still conflict, identical ones would not. Item 13 answers the open question Q-812131 differently from the planned answer. Item 10 stays within D-956800 and D-c16827 only if it remains opt-in. Each should be recorded as a new decision when taken.
