---
name: wiki-crossref
description: Use when adding inline cross-reference links between wiki documents after generation — dispatches a manifest subagent to build crossref.yml then parallel rewrite subagents to insert first-mention links. Run manually after wiki-gen completes.
---

# Wiki Cross-Reference

## Overview

Two-phase skill that adds inline links between wiki documents. A manifest subagent reads all documents and writes `llm-gen-wiki/crossref.yml` mapping concepts to their home documents. Then one rewrite subagent per document is dispatched in parallel; each inserts a relative markdown link on the **first** mention of each concept whose home is a different document.

**Important:** This skill dispatches subagents for all heavy work. The main thread (this skill) only coordinates, reads `crossref.yml`, and dispatches rewrites.

## Prerequisites

- Claude Code with the Agent tool available
- Wiki documents already written to `llm-gen-wiki/` (run after `wiki-gen` completes)

## Inputs

| Input | Description |
|---|---|
| `repo_root` | Absolute path to the repository root |
| `document_files` | List of absolute paths to the wiki documents to cross-reference (excludes `index.md`, `log.md`, `lint-report.md`) |

## Phase 1 — Manifest Subagent

Dispatch a **single** subagent with the following instructions:

<role>
You are a cross-reference manifest builder. You read a set of wiki documents and identify named concepts that appear in more than one document, then write a YAML manifest mapping each concept to its home document.
</role>

<guidelines>
1. Read every document listed in `document_files`.
2. Identify named concepts — functions, modules, components, patterns, architectural terms — that appear **verbatim** in more than one document.
3. Assign each concept a "home" document: the one that covers it most deeply (most detailed explanation, dedicated section, or highest word count about it).
4. Generic words (`function`, `module`, `file`, `system`, `class`, `method`, `data`, `type`, `value`, `object`, `list`, `map`) are **never** concepts.
5. Write `llm-gen-wiki/crossref.yml` with this exact schema:

```yaml
concepts:
  - name: "ExactConceptName"
    home: llm-gen-wiki/NN-slug.md
    mentioned_in:
      - llm-gen-wiki/NN-other-slug.md
```

Use only paths relative to `repo_root` (e.g. `llm-gen-wiki/03-websocket-streaming.md`).
6. Do not print the YAML to stdout. Write it only to `llm-gen-wiki/crossref.yml`.
7. If no cross-cutting named concepts are found, write `concepts: []` to `llm-gen-wiki/crossref.yml` and stop.
</guidelines>

Wait for the manifest subagent to complete before proceeding to Phase 2.

## Phase 2 — Parallel Rewrite Subagents

Read `llm-gen-wiki/crossref.yml`. If `concepts` is empty, skip Phase 2 and report completion.

Dispatch **all** rewrite subagents in a **single parallel batch** — one Agent tool invocation per document in `document_files`.

Each rewrite subagent receives:

- The absolute path of its document (`target_file`)
- The full contents of `llm-gen-wiki/crossref.yml`

Each subagent's instructions:

<role>
You are a wiki document editor. You add inline cross-reference links to a single markdown document without changing any prose.
</role>

<guidelines>
1. Read your target document at `target_file`.
2. Read the provided `crossref.yml` contents.
3. For each concept in `crossref.yml` whose `home` is **not** your target document and whose `mentioned_in` list includes your target document:
   a. Find the **first verbatim occurrence** of the concept name in the document body (ignore headings, code blocks, and existing links).
   b. Wrap it as a relative markdown link: `[ConceptName](filename.md)` where `filename.md` is the basename of the home path (files share the same `llm-gen-wiki/` directory (relative links only)).
   c. Do **not** add a second link if the concept name appears again later in the document.
4. Rules — never violate these:
   - **First mention only** — one link per concept per document.
   - **Relative paths** — `[concept](03-websocket-streaming.md)`, never absolute.
   - **Verbatim match only** — if the exact concept name does not appear in the prose, do not add a link; no paraphrasing or synonym substitution.
   - **No self-links** — skip any concept whose home is the current document.
   - **Named concepts only** — generic words are never linked even if listed in crossref.yml.
   - **Skip code blocks** — do not add links inside fenced code blocks or inline code spans.
5. Write the updated document back to `target_file`. If no concepts match, write the file unchanged.
</guidelines>

Wait for all rewrite subagents to complete.

## Done

After Phase 2 completes, report:

> "Cross-reference pass complete. [N] concepts linked across [M] documents. `llm-gen-wiki/crossref.yml` written."

where N is the number of concepts that produced at least one link, and M is the number of documents that were modified.
