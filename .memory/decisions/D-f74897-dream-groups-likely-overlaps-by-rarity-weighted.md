---
id: D-f74897
type: decision
title: dream groups likely overlaps by rarity-weighted words, not shared links or tags
summary: dream prints the real commands and the active entries, grouping pairs whose title/summary/tag/keyword words overlap by 0.3 or more
status: accepted
created: 2026-11-11T13:23:26Z
author: Rodrigo Hammerly
agent: claude-code
branch: archive-dream-migrate
tags: [dream]
keywords: [consolidation, duplicates, clustering, prompt]
links: [src/mneme/dream.py, src/mneme/cli.py]
---

## Context

D-464a61 fixed dream's scope (print a prompt, change nothing). Grouping by shared links or two shared tags chained 13 of 31 entries here into one group, because most entries link store.py or model.py.

## Decision

Command lines come from the CLI's FIELDS table, so the prompt can't drift from the real flags. Entries are grouped when the IDF-weighted Jaccard overlap of their stemmed title, summary, tag and keyword words reaches 0.3 (distinct entries here score up to ~0.2). The agent acts with new --supersedes, set, supersede and archive; there is no JSON apply step. --tag, --path and --limit (default 80, newest) bound the prompt.

## Consequences

A small, distinct memory gets one flat list and a note that nothing looks alike. The threshold is a guess from one repo; revisit it after dreaming on Demiurge.
