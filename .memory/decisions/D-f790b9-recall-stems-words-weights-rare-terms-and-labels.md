---
id: D-f790b9
type: decision
title: Recall stems words, weights rare terms and labels partial matches
summary: "No more silent misses: if no entry has every word, the closest partial matches are shown with the words they lack"
status: accepted
created: 2026-11-11T09:11:00Z
author: Rodrigo Hammerly
agent: claude-code
branch: recall-and-format
tags: [recall]
keywords: [search, ranking, bm25, stemming, idf]
links: [src/mneme/recall.py]
---

## Context

Every query word had to match exactly or by prefix, so 'merge conflict' missed an entry titled '...always conflicts', and the agent read 'Nothing found' as 'no memory'. Design review 2026-11-11, item 1.

## Decision

A light suffix stemmer on query and entry words; stopwords dropped from queries; title/tags/keywords score 3, summary 2, body 1 (a prefix match one less), each term weighted by inverse document frequency across candidates. Full matches only if any exist; otherwise partial matches under a label, each with '(no: word)'. Still no index or embeddings.

## Consequences

Recall is a ranking, not a filter, when nothing matches fully. A BM25 cache or embeddings stay out of scope (D-956800, D-a79645).
