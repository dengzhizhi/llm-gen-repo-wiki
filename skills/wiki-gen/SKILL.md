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

Run the `gen_meta.py` script from the skill directory to generate `llm-gen-wiki/meta.yml`:

```bash
python3 ~/.claude/skills/wiki-gen/gen_meta.py
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

Loop on this prompt — process each command, update `llm-gen-wiki/plan.yml`, re-display the updated plan, and repeat — until the user types `ok`.

### Command Processing Rules

- **`add <title>`**: Append a new top-level topic to `llm-gen-wiki/plan.yml` with:
  - `id`: auto-generated kebab-case slug derived from `<title>`
  - `title`: `<title>` as provided
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

After each command, write the updated YAML back to `llm-gen-wiki/plan.yml` and re-display the full updated plan with the command menu.

## Step 4 — Build Document List

Read the confirmed `llm-gen-wiki/plan.yml` and compute the full ordered list of documents to generate. Use a 1-based index zero-padded to 2 digits.

**Topic WITH subtopics** (the topic's `subtopics` list is non-empty):
- Overview doc: `llm-gen-wiki/<NN>-<topic-id>.md`, `is_overview: true`
- Per subtopic (letter sequence a, b, c, …): `llm-gen-wiki/<NN><letter>-<subtopic-slug>.md`, `is_overview: false`
  - `<subtopic-slug>` is the portion of the subtopic id **after** the `--` separator

**Topic WITHOUT subtopics** (`subtopics: []`):
- Full doc: `llm-gen-wiki/<NN>-<topic-id>.md`, `is_overview: false`

**Example** (3 topics; topic 1 has 2 subtopics, topics 2 and 3 have none):

```
llm-gen-wiki/01-system-architecture.md         is_overview: true
llm-gen-wiki/01a-frontend-architecture.md      is_overview: false
llm-gen-wiki/01b-backend-architecture.md       is_overview: false
llm-gen-wiki/02-prompt-engineering.md          is_overview: false
llm-gen-wiki/03-configuration.md               is_overview: false
```

## Step 5 — Dispatch Writing Subagents in Parallel

Dispatch **all** writing subagents in a **single Agent batch call** — one Agent tool invocation per document, all sent simultaneously (not sequentially).

Each subagent is invoked with the `wiki-write-topic` skill and receives:

| Input | Value |
|---|---|
| `topic_title` | Topic or subtopic title from `llm-gen-wiki/plan.yml` |
| `topic_description` | Topic or subtopic description from `llm-gen-wiki/plan.yml` |
| `relevant_files` | Topic-level `relevant_files` for overview docs; subtopic-level `relevant_files` for subtopic docs |
| `repo_root` | Absolute path to the current working directory |
| `output_file` | Absolute path computed in Step 4 (e.g. `/abs/path/llm-gen-wiki/01-system-architecture.md`) |
| `is_overview` | Boolean computed in Step 4 |
| `generated_at` | Value from Step 0 |
| `branch` | Value from Step 0 |
| `commit_hash` | Value from Step 0 |
| `origin_url` | Value from Step 0 |
| `repo_type` | Value from Step 0 |
| `scope_prefix` | Value from Step 0 |
| `business_context` | The topic's `business_context` from `llm-gen-wiki/plan.yml`; for subtopic docs, use the subtopic's `business_context` if present, otherwise fall back to the parent topic's `business_context`; empty string `""` if neither is present |

Wait for all subagents to complete before proceeding.

## Step 6 — Write `llm-gen-wiki/index.md`

After all subagents complete, write `llm-gen-wiki/index.md` with the following structure:

```markdown
# [repo] Wiki

| | |
|---|---|
| **Branch** | `[branch]` |
| **Commit** | `[first 12 chars of commit_hash]` |
| **Generated** | [generated_at] |

[description from plan.yml top-level `description` field]

## High Priority

1. **[Topic Title](01-topic-id.md)** *(N source files)* — [one-line synthesis note]
   - [Subtopic Title](01a-subtopic-slug.md) — [subtopic description]
   - [Subtopic Title](01b-subtopic-slug.md) — [subtopic description]

## Medium Priority

2. **[Topic Title](02-topic-id.md)** *(N source files)* — [one-line synthesis note]

## Low Priority

3. **[Topic Title](03-topic-id.md)** *(N source files)* — [one-line synthesis note]

---
*Generated by llm-gen-repo-wiki*
```

Rules:
- `[repo]` is the `repo` field from `llm-gen-wiki/plan.yml`
- Topics are grouped into `## High Priority`, `## Medium Priority`, `## Low Priority` H2 sections based on each topic's `importance` field. Omit a section heading entirely if no topics have that importance level.
- `*(N source files)*` is the count of paths in the topic's `relevant_files` list from `llm-gen-wiki/plan.yml`
- `[one-line synthesis note]` is the topic's `description` field from `llm-gen-wiki/plan.yml` (use as-is; do not invent a new description)
- Link hrefs use filenames only (no directory prefix), since `index.md` lives in the same `llm-gen-wiki/` directory
- Subtopics are indented under their parent topic as a sub-list
- Topics with no subtopics have no indented sub-list

## Step 7 — Append to `llm-gen-wiki/log.md`

After writing `llm-gen-wiki/index.md`, append a generation record to `llm-gen-wiki/log.md`.

If `llm-gen-wiki/log.md` does **not** exist, create it with:

```markdown
# Wiki Generation Log

<!-- append-only: newest entries at bottom -->

## [YYYY-MM-DD] Generation run

- Topics: N (M with subtopics → P documents total)
- Cross-references: none (run /wiki-crossref to add)
- Plan: llm-gen-wiki/plan.yml
```

If `llm-gen-wiki/log.md` **already exists**, append only the entry block (no header):

```markdown
## [YYYY-MM-DD] Generation run

- Topics: N (M with subtopics → P documents total)
- Cross-references: none (run /wiki-crossref to add)
- Plan: llm-gen-wiki/plan.yml
```

Where:
- `YYYY-MM-DD` is today's date
- `N` is the number of top-level topics in `plan.yml`
- `M` is the number of those topics that have at least one subtopic
- `P` is the total number of documents generated (same count used in the Done message)

## Done

After writing `llm-gen-wiki/log.md`, confirm to the user:

> "Wiki generation complete. [N] documents written to `llm-gen-wiki/`. Open `llm-gen-wiki/index.md` to start reading.
>
> Optional: run `/wiki-crossref` to add inline links between documents, or `/wiki-lint` to check for thin documents, orphan concepts, and missing cross-references."

where N is the total number of topic/subtopic documents generated (not counting `index.md`, `log.md`).
