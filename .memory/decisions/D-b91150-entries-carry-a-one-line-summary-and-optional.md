---
id: D-b91150
type: decision
title: Entries carry a one-line summary and optional keywords
summary: summary states the outcome and is printed under each recall hit; keywords hold search words the text doesn't use
status: accepted
created: 2026-11-11T09:11:00Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
tags: [format, recall]
keywords: [gist, synonyms, context]
links: [src/mneme/model.py, src/mneme/cli.py]
---

## Context

A recall hit was id, title and status, so learning what was decided took one show call (~1,000 chars) per entry. Synonyms (database vs SQLite) never matched. Design review 2026-11-11, items 2-3.

## Decision

Optional frontmatter keys summary (one line) and keywords (list). Without a summary, the first line of the type's main section stands in (Decision, Takeaway, Answer, Trigger, Definition; a note's body). show is compact by default (title, status, summary, links, body), takes several ids, and --raw prints the whole file. new warns when a section passes 600 characters.

## Consequences

Most recall hits need no follow-up show. Old and migrated entries get a gist without backfill. Agents should fill keywords with synonyms when they record an entry.
