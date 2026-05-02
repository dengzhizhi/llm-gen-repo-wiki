---
name: wiki-gen
description: Use when generating a complete wiki documentation set for the current code repository — orchestrates topic discovery, interactive plan confirmation, and parallel per-topic document generation. Entry point for the llm-wiki-skills package.
---

# Wiki

## Overview

This is the orchestrator skill for the `llm-wiki-skills` package. It coordinates the full wiki generation pipeline: planning, interactive review, and parallel document writing. When the skill starts, it announces: "Generating wiki for repository at: [current working directory]".

**Important:** The main thread (this skill) never reads source files directly. All codebase exploration is delegated to subagents.

## Prerequisites

- Claude Code with the Agent tool available
- The `wiki-plan` and `wiki-write-topic` skills must be available
- Run from the repository root (the directory you want to document)

## Step 0 — Acquire Repository Metadata

Run the skill-local `gen_meta.py` script to generate `llm-gen-wiki/meta.yml`. Keep the current working directory at the repository root being documented, and invoke the script by its resolved path inside the `wiki-gen` skill directory:

```bash
python3 <wiki-gen-skill-dir>/gen_meta.py
```

The script writes `llm-gen-wiki/meta.yml` with these six fields:
- `generated_at` — UTC ISO-8601 timestamp
- `branch` — current git branch name
- `commit_hash` — full 40-character commit SHA
- `origin_url` — canonical HTTPS remote URL (SSH normalized; `.git` stripped; empty string if no remote)
- `repo_type` — `github`, `bitbucket`, or `unknown`
- `scope_prefix` — path from git root to cwd (empty string if cwd is the git root)

Read `llm-gen-wiki/meta.yml` and keep all six values in memory for the rest of this session — they are passed to every subagent in Steps 2 and 5.

## Re-run Behaviour

Before doing anything else, check whether `llm-gen-wiki/plan.yml` already exists:

```bash
test -f llm-gen-wiki/plan.yml && echo "exists" || echo "not found"
```

- If it **exists**: skip Steps 1 and 2, go directly to Step 3
- If it **does not exist**: proceed from Step 1

## Step 1 — Ask for Extra Topics

Ask the user exactly once:

> "Are there any extra specific topics or aspects you want the wiki to cover? List them (comma-separated), or answer 'no' to skip."

Capture the response as `extra_topics` (may be empty). Do not explore the codebase here — keep this step brief.

## Step 2 — Dispatch Planning Subagent

Dispatch a subagent using the `wiki-plan` skill with the following inputs:

| Input | Value |
|---|---|
| `repo_root` | Absolute path to the current working directory |
| `extra_topics` | The list collected in Step 1 (empty if the user skipped) |
| `scope_prefix` | Value from Step 0 |

Wait for the subagent to complete. It will write `llm-gen-wiki/plan.yml`.

## Step 3 — Read Plan and Present to User

Read `llm-gen-wiki/plan.yml`.

Present the plan to the user in the following format:

```
Wiki plan generated. Here is the proposed structure:

1. [Topic Title] ([importance])
   1a. [Subtopic Title]
   1b. [Subtopic Title]
2. [Topic Title] ([importance])
3. [Topic Title] ([importance])
   3a. [Subtopic Title]
...

Planning warnings:
  - [warning]
  - [warning]

Planning questions:
  - [question]
  - [question]

Total documents to generate: N

Commands:
  ok                               — approve and start generation
  add <title>                      — add a new top-level topic
  remove <id>                      — remove a topic or subtopic by id
  rename <id> <new title>          — rename a topic or subtopic
  sub <parent-id> <title>          — add a subtopic under a parent topic
  importance <id> high|medium|low  — change importance level
  (you can also edit llm-gen-wiki/plan.yml directly in your editor before typing ok)
```

If `planning_warnings` is empty, show `Planning warnings: none`.
If `planning_questions` is empty, show `Planning questions: none`.

Preserve any existing additive metadata in `plan.yml`, including `planning_warnings`, `planning_questions`, and optional topic-level metadata on untouched topics.

When presenting `planning_questions`, assume the user may not know the codebase well yet. Do not paraphrase them into shorter but less informative wording. Preserve the planner's context, rationale, and option structure so the user can answer from the review screen alone.

If a `planning_questions` entry offers explicit options, present those options clearly and encourage the user to answer by selecting one of them. Prefer concise selection-style follow-up over asking the user to invent an answer from scratch.

Treat `planning_questions` primarily as architecture-shaping and depth-allocation decisions. The review step should help the user steer which subsystems, runtime paths, or technical concerns deserve the deepest treatment before document generation starts.

Loop on this prompt — process each command, update `llm-gen-wiki/plan.yml`, re-display the updated plan, and repeat — until the user types `ok`.

### Command Processing Rules

- **`add <title>`**: Append a new top-level topic to `llm-gen-wiki/plan.yml` with:
  - `id`: auto-generated kebab-case slug derived from `<title>`
  - `title`: `<title>` as provided
  - `description`: empty string (or omit)
  - `business_context`: empty string (or omit)
  - `importance`: `medium`
  - `user_requested`: `false`
  - `relevant_files: []`
  - `subtopics: []`

- **`remove <id>`**: Remove the topic or subtopic whose `id` matches `<id>` from `llm-gen-wiki/plan.yml`. If a subtopic, remove it from its parent's `subtopics` list.

- **`rename <id> <new title>`**: Update the `title` field for the topic or subtopic whose `id` matches `<id>`.

- **`sub <parent-id> <title>`**: Add a new subtopic under the topic with id `<parent-id>` with:
  - `id`: `<parent-id>--<slug>` where `<slug>` is the kebab-case slug of `<title>`
  - `title`: `<title>` as provided
  - `description`: empty string (or omit)
  - `user_requested`: `false`
  - `relevant_files: []`

- **`importance <id> high|medium|low`**: Update the `importance` field for the topic or subtopic whose `id` matches `<id>`.

- When editing by command, preserve all unrelated optional metadata fields already present in the plan, such as `primary_audience`, `doc_goal`, `diagram_candidates`, `coverage_tags`, `open_questions`, `planning_warnings`, and `planning_questions`, unless the user explicitly changes them by editing the YAML directly.

After each command, write the updated YAML back to `llm-gen-wiki/plan.yml` and re-display the full updated plan with the command menu.

## Step 4 — Build Document List

Run the skill-local `compute_docs.py` script to build the full ordered document job list. Keep the current working directory at the repository root being documented, and invoke the script by its resolved path inside the `wiki-gen` skill directory:

```bash
python3 <wiki-gen-skill-dir>/compute_docs.py
```

The script reads `llm-gen-wiki/plan.yml`, validates topic ids, and writes `llm-gen-wiki/documents.json`. Read that JSON file and use it as the source of truth for Step 5. Each document job contains `topic_title`, `topic_description`, `relevant_files`, absolute `output_file`, `is_overview`, and `business_context`.

## Step 5 — Dispatch Writing Subagents in Parallel

Dispatch **all** writing subagents in a **single Agent batch call** — one Agent tool invocation per document job in `llm-gen-wiki/documents.json`, all sent simultaneously (not sequentially).

Each subagent is invoked with the `wiki-write-topic` skill and receives:

| Input | Value |
|---|---|
| `topic_title` | `topic_title` from the document job |
| `topic_description` | `topic_description` from the document job |
| `relevant_files` | `relevant_files` from the document job |
| `repo_root` | Absolute path to the current working directory |
| `output_file` | Absolute `output_file` from the document job |
| `is_overview` | Boolean `is_overview` from the document job |
| `generated_at` | Value from Step 0 |
| `branch` | Value from Step 0 |
| `commit_hash` | Value from Step 0 |
| `origin_url` | Value from Step 0 |
| `repo_type` | Value from Step 0 |
| `scope_prefix` | Value from Step 0 |
| `business_context` | `business_context` from the document job |

Wait for all subagents to complete before proceeding.

## Step 6 — Write `llm-gen-wiki/index.md`

After all subagents complete, run the skill-local `render_index.py` script to rebuild `llm-gen-wiki/index.md` from `llm-gen-wiki/plan.yml` and `llm-gen-wiki/meta.yml`. Keep the current working directory at the repository root being documented:

```bash
python3 <wiki-gen-skill-dir>/render_index.py
```

## Step 7 — Append to `llm-gen-wiki/log.md`

After writing `llm-gen-wiki/index.md`, run the skill-local `append_log.py` script to create or repair `llm-gen-wiki/log.md` and append the generation record. Keep the current working directory at the repository root being documented:

```bash
python3 <wiki-gen-skill-dir>/append_log.py
```

## Done

After writing `llm-gen-wiki/log.md`, confirm to the user:

> "Wiki generation complete. [N] documents written to `llm-gen-wiki/`. Open `llm-gen-wiki/index.md` to start reading.
>
> Optional: run `/wiki-crossref` to add inline links between documents, or `/wiki-lint` to check for thin documents, orphan concepts, and missing cross-references."

where N is the total number of topic/subtopic documents generated (not counting `index.md`, `log.md`).
