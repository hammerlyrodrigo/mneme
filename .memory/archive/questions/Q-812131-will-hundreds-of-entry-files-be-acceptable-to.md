---
id: Q-812131
type: question
title: Will hundreds of entry files be acceptable to other developers?
status: resolved
created: 2026-11-02T13:05:18Z
author: claude
branch: main
tags: [storage, product]
keywords: [storage, files, scale, clutter, archive, compact]
resolved_by: D-099eb1
---

## Question

The user worries that a .memory/ folder with hundreds of files won't be acceptable to other developers. Planned answer: compact, run on the main branch only, folds inactive entries into one archive file per type (.memory/archive/<type>s.md); show and recall --all still find them. Decide after a few weeks of using Mneme here and on Demiurge.

## Answer

Yes, with archiving: mneme archive moves inactive entries to .memory/archive/<type>s/ unchanged, so live folders stay small. The folding compact was dropped.
