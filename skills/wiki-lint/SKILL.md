---
name: wiki-lint
description: Use when checking a generated wiki for health issues — flags thin documents, orphan concepts, missing cross-references, and stale file paths. Reads llm-gen-wiki/*.md plus plan.yml and crossref.yml, writes llm-gen-wiki/lint-report.md. Never dispatched automatically; always user-invoked.
---

# Wiki Lint

## Overview

Optional post-generation health check. Reads all wiki documents plus `llm-gen-wiki/plan.yml` and `llm-gen-wiki/crossref.yml` (if present) and produces `llm-gen-wiki/lint-report.md` with issues and suggestions. Never auto-dispatched — always invoked manually with `/wiki-lint`.

**Important:** This skill performs all checks directly (no subagents needed — it reads a bounded set of files and writes one report).

## Prerequisites

- Wiki documents already written to `llm-gen-wiki/`
- `llm-gen-wiki/plan.yml` must exist
- `llm-gen-wiki/crossref.yml` is optional; if absent the missing-cross-reference check is skipped

## Checks Performed

| Check | Description |
|---|---|
| Orphan concepts | Named concepts appearing in 3+ documents with no dedicated document |
| Missing cross-references | Concepts listed in `crossref.yml` that still appear unlinked in documents that mention them |
| Thin documents | Documents with fewer than 3 H2 sections (`## `) **or** fewer than 5 `Sources:` citation blocks |
| Stale `relevant_files` | Paths listed in `plan.yml` `relevant_files` that no longer exist in the repo |
| Suggested expansions | Named concepts recurring in 5+ documents that might warrant a dedicated page |

## Process

1. List all files matching `llm-gen-wiki/*.md` excluding `index.md`, `log.md`, `lint-report.md`.
2. Read each document. Count H2 sections (`## ` prefix) and `Sources:` occurrences.
3. Read `llm-gen-wiki/plan.yml`. Extract all `relevant_files` paths across all topics and subtopics, then check each path against the filesystem relative to the repo root.
4. If `llm-gen-wiki/crossref.yml` exists, read it. For each concept, check each document in `mentioned_in` for an existing markdown link whose href matches the concept's home basename.
5. Scan all documents for named noun phrases (proper names, quoted terms, or title-cased multi-word terms) appearing in 5+ documents with no dedicated document.
6. Aggregate results into issues (fix recommended) and suggestions (optional).

## Output — `llm-gen-wiki/lint-report.md`

Write `llm-gen-wiki/lint-report.md` with this structure:

```markdown
# Wiki Lint Report — YYYY-MM-DD

## Issues (fix recommended)

- **Thin document**: `06-configuration.md` — only 2 H2 sections and 3 source citations
- **Stale file**: `plan.yml` references `api/old_handler.py` which no longer exists

## Suggestions (optional)

- **Orphan concept**: "token budget" appears in 5 documents — consider a dedicated page
- **Missing cross-reference**: "data pipeline" is unlinked in `02-prompt-engineering.md`

## Healthy

- 11/14 documents: sufficient depth and citations
- Cross-reference coverage: 47 links across 14 documents
```

Rules:
- If no issues exist, write `_No issues found._` under Issues.
- If no suggestions exist, write `_No suggestions._` under Suggestions.
- If `llm-gen-wiki/crossref.yml` does not exist, add a note under Suggestions: `_Cross-reference check skipped — llm-gen-wiki/crossref.yml not found. Run /wiki-crossref first to enable this check._`
- Always include the Healthy section with counts even when issues exist.

## Done

After writing `llm-gen-wiki/lint-report.md`, confirm:

> "Lint complete. [N] issues, [M] suggestions. Report written to `llm-gen-wiki/lint-report.md`."
