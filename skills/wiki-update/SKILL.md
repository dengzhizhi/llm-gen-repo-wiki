---
name: wiki-update
description: Use when adding a new topic to an already-generated wiki, or editing one or more existing topics' descriptions or generation instructions and regenerating their document(s) — persists all changes to plan.yml.
---

# Wiki Update

## Overview

This skill handles topic-level operations on an existing wiki produced by `wiki-gen`. It supports two modes:

- **Add** — discover relevant files, draft a new topic YAML entry, confirm with user, append to `plan.yml`, and generate new document(s).
- **Edit** — select one or more existing topics, update each topic's metadata or generation instructions, batch-update `plan.yml`, and regenerate all selected topics' documents in a single parallel dispatch.

In both modes the skill refreshes repository metadata so regenerated documents carry the current commit hash and timestamp, then rebuilds `llm-gen-wiki/index.md` and appends to `llm-gen-wiki/log.md` when done.

**Important:** The main thread never reads source files directly. All codebase exploration is delegated to subagents.

When the skill starts, it announces: "Wiki update for: [current working directory]".

## Prerequisites

- Claude Code with the Agent tool available
- `llm-gen-wiki/plan.yml` must exist (run `/wiki-gen` first)
- `llm-gen-wiki/meta.yml` must exist
- The `wiki-write-topic` skill must be available

## Step 1 — Prerequisites Check

Check that both required files exist:

```bash
test -f llm-gen-wiki/plan.yml && echo "plan: ok" || echo "plan: MISSING"
test -f llm-gen-wiki/meta.yml && echo "meta: ok" || echo "meta: MISSING"
```

If either file is missing, stop immediately and tell the user:

> "Cannot proceed: `llm-gen-wiki/[missing-file]` does not exist. Run `/wiki-gen` first to generate the initial wiki."

## Step 2 — Confirm Language And Refresh Metadata

Read the current `llm-gen-wiki/meta.yml` first and extract its `language` field if present. Ask the user:

> "The current wiki language is [current-language-or-English]. Which language should regenerated documents use? Default: [current-language-or-English]."

If the user does not provide a clear replacement, keep the current language. If the existing `meta.yml` has no `language` field, treat the default as `English`.

Run the skill-local `gen_meta.py` script to capture the **current** git state and write `llm-gen-wiki/meta.yml`. Keep the current working directory at the repository root being updated, and invoke the script by its resolved path inside the `wiki-update` skill directory:

```bash
python3 <wiki-update-skill-dir>/gen_meta.py --language "<chosen-language>"
```

Read `llm-gen-wiki/meta.yml` and keep all seven values in memory for the rest of this session. Every writing subagent dispatched in this session receives these values, so all regenerated documents will carry the current branch, commit hash, generation timestamp, and chosen language — not stale values from the original wiki-gen run.

| Field | Purpose |
|---|---|
| `generated_at` | Embedded in every regenerated document's metadata header |
| `branch` | Embedded in every regenerated document's metadata header |
| `commit_hash` | Used in source-file hyperlinks in every regenerated document |
| `origin_url` | Used in source-file hyperlinks |
| `repo_type` | Controls hyperlink format (`github`, `bitbucket`, or `unknown`) |
| `scope_prefix` | Passed to writing subagents and the discovery subagent |
| `language` | Passed to writing subagents so regenerated documents use the selected human-readable language |

## Step 3 — Choose Mode

Ask the user:

> "What would you like to do?
>
> 1. **Add** a new topic to the wiki
> 2. **Edit** one or more existing topics (update description, instructions, or files) and regenerate their document(s)"

If the user answers **1** (or "add"), proceed to **Add Mode** (Steps A1–A7).
If the user answers **2** (or "edit"), proceed to **Edit Mode** (Steps E1–E6).

---

## Add Mode

### Step A1 — Gather Topic Input from User

Ask the user for all required information in a **single message**:

> "What topic do you want to add?
>
> - **Topic title** *(required)*:
> - **Description** *(optional — what this document should cover, one sentence)*:
> - **Importance** *(optional — high / medium / low, default: medium)*:
> - **Generation notes** *(optional — additional instructions for the writer, e.g. "include a section on error handling" or "focus on the public API")*:
> - **File or directory hints** *(optional — paths, module names, or keywords to guide file discovery)*:"

Capture all five responses. Defaults: `description` = empty, `importance` = `medium`, `generation_notes` = empty, `hints` = empty.

### Step A2 — Dispatch Discovery Subagent

Dispatch a **single** subagent with the following instructions. Substitute all bracketed values literally before dispatching.

---

<role>
You are a wiki topic discovery agent. Your job is to find the source files most relevant to a single new wiki topic, check the existing plan to avoid overlap, and draft the YAML entry for this topic. You do NOT write any files to disk — you print the YAML block to stdout.
</role>

<inputs>
- `repo_root`: [absolute path to the current working directory]
- `scope_prefix`: [value from meta.yml]
- `topic_title`: [value from Step A1]
- `topic_description`: [value from Step A1, may be empty string]
- `topic_importance`: [value from Step A1]
- `hints`: [value from Step A1, may be empty string]
- `plan_path`: [repo_root]/llm-gen-wiki/plan.yml
</inputs>

<guidelines>

**Phase 0 — Read the Existing Plan**

Read `plan_path`. Extract the `id`, `title`, and `relevant_files` for every existing topic. Keep this in memory to avoid assigning files already thoroughly covered by an existing topic, and to detect substantial overlap with an existing topic.

**Phase 1 — BFS File Discovery**

Use `git ls-tree` to explore the repository structure level by level. All git commands must be run from `repo_root`. Stop when any one of these is met:
- No important directories remain to explore
- Depth has reached level 5
- Running entry count reaches or exceeds **400**

Root (always run):
```bash
# scope_prefix empty:
git ls-tree HEAD
# scope_prefix non-empty:
git ls-tree HEAD -- <scope_prefix>/
```

All level-1 `tree` entries proceed to level 2. For levels 2–5: issue one Bash call per level for all selected directories, mark subdirectories as important if they likely contain source code, feature modules, data models, API handlers, config, tests, or documentation relevant to `topic_title` or `hints`. Skip: `dist`, `build`, `out`, `.next`, `__pycache__`, `.cache`, `coverage`, `*.egg-info`, `tmp`, `logs`, `vendor`.

**Phase 2 — Targeted File Reads**

Read up to **20 files** total that are likely related to `topic_title` and `hints`. Prioritise files whose names mention keywords from the title or hints, and core logic / model / API handler files for the topic area.

**Phase 3 — Draft YAML Entry**

- `id`: unique kebab-case slug from `topic_title`; append `-2` etc. if it collides with an existing id
- `title`: `topic_title` as provided
- `description`: use `topic_description` if non-empty; otherwise infer a one-sentence description from what you read
- `business_context`: one sentence answering "What problem does this solve for users?" — derive from source files only; empty string `""` if no clear signal
- `importance`: `topic_importance`
- `user_requested`: `true`
- `relevant_files`: 3–15 verified paths relative to `repo_root`
- `subtopics`: assign only if topic spans 10+ files across 3+ distinct directories; otherwise `subtopics: []`
- `generation_notes`: omit this field (the orchestrator carries it separately)

**Output Format**

Print to stdout, no preamble, no markdown fences:

```
DRAFT_TOPIC_YAML_START
id: <kebab-case-id>
title: <Display Title>
description: <one-sentence description>
business_context: <one sentence or empty string>
importance: high|medium|low
user_requested: true
relevant_files:
  - path/to/file.py
subtopics: []
DRAFT_TOPIC_YAML_END
```

If subtopics are present, format them as a YAML list. If you detected meaningful overlap with an existing topic, append:
```
OVERLAP_WARNING: This topic overlaps significantly with existing topic "<existing-title>" (<existing-id>).
```

</guidelines>

---

Wait for the subagent. Parse the YAML block between `DRAFT_TOPIC_YAML_START` and `DRAFT_TOPIC_YAML_END`. Keep any `OVERLAP_WARNING` for Step A3.

### Step A3 — Confirm/Edit Loop

Display the draft topic (inject the user's `generation_notes` into the display even though the subagent didn't include it in the YAML):

```
New topic draft:

  ID:               <id>
  Title:            <title>
  Description:      <description>
  Business context: <business_context>
  Importance:       <importance>
  Generation notes: <generation_notes from Step A1, or "(none)">
  Files ([N] relevant files):
    - path/to/file.py
    ...
  Subtopics:        none  [or list subtopic titles]

[OVERLAP WARNING: ...]   ← only shown if subagent returned OVERLAP_WARNING

Commands:
  ok
  title <new title>
  description <text>
  importance high|medium|low
  business-context <sentence>
  notes <text>                          — set or replace generation notes
  notes clear                           — remove generation notes
  add-file <path>
  remove-file <path>
  sub <title>                           — add a subtopic
  remove-sub <subtopic-id>              — remove a subtopic
  (plain-English edits also accepted)
```

Loop until `ok`. Do not write to disk during this loop.

### Command Processing (Add Mode)

- **`title <new title>`**: Update `title`; re-derive `id` (kebab slug, check collision); update subtopic ids to use new parent prefix.
- **`description <text>`**: Replace `description`.
- **`importance high|medium|low`**: Replace `importance`.
- **`business-context <sentence>`**: Replace `business_context`.
- **`notes <text>`**: Set `generation_notes` to `<text>`.
- **`notes clear`**: Set `generation_notes` to empty string.
- **`add-file <path>`**: Append to `relevant_files` if not already present.
- **`remove-file <path>`**: Remove from `relevant_files`.
- **`sub <title>`**: Append subtopic with `id`: `<parent-id>--<slug>`, `title`, empty `description`, `user_requested: false`, `relevant_files: []`.
- **`remove-sub <subtopic-id>`**: Remove matching subtopic.
- **Plain-English edits**: Apply to in-memory draft; describe the change before re-displaying.

### Step A4 — Update plan.yml

Read current `llm-gen-wiki/plan.yml`. Append the confirmed topic as the last entry in the `topics:` list using this field order: `id`, `title`, `description`, `business_context`, `importance`, `user_requested`, `relevant_files`, `subtopics`. If `generation_notes` is non-empty, append it as the final field:

```yaml
    generation_notes: "<text>"
```

If `generation_notes` is empty, omit the field entirely.

Write the complete updated YAML back to `llm-gen-wiki/plan.yml`.

### Step A5 — Compute Document Jobs

Run the skill-local `compute_docs.py` script after updating `plan.yml`. Keep the current working directory at the repository root being updated, and invoke the script by its resolved path inside the `wiki-update` skill directory:

```bash
python3 <wiki-update-skill-dir>/compute_docs.py
```

The script writes `llm-gen-wiki/documents.json` for the full current plan. Read that file and select jobs whose `topic_id` or `parent_topic_id` matches the newly added topic id. Each selected job contains `topic_title`, `topic_description` (including `generation_notes` when present), `relevant_files`, absolute `output_file`, `is_overview`, and `business_context`.

### Step A6 — Dispatch Writing Subagent(s)

Dispatch **all** writing subagents in a **single Agent batch call**.

Each subagent uses the `wiki-write-topic` skill. Use the selected document jobs from `llm-gen-wiki/documents.json` as the source of truth.

| Input | Value |
|---|---|
| `topic_title` | `topic_title` from the document job |
| `topic_description` | `topic_description` from the document job |
| `relevant_files` | `relevant_files` from the document job |
| `repo_root` | Absolute path to current working directory |
| `output_file` | Absolute `output_file` from the document job |
| `is_overview` | Boolean `is_overview` from the document job |
| `generated_at` | From Step 2 |
| `branch` | From Step 2 |
| `commit_hash` | From Step 2 |
| `origin_url` | From Step 2 |
| `repo_type` | From Step 2 |
| `scope_prefix` | From Step 2 |
| `language` | From Step 2 |
| `business_context` | `business_context` from the document job |

Wait for all subagents to complete.

### Step A7 — Finalize

Proceed to **Shared Steps** (Steps S1–S3) with mode = `add`, topic list = [the new topic].

---

## Edit Mode

### Step E1 — Select Topics

Read `llm-gen-wiki/plan.yml`. Display the full topic list:

```
Existing topics:

  1.  [id: system-architecture]       System Architecture          (high)
  2.  [id: authentication-flow]       Authentication Flow          (high)
  3.  [id: configuration]             Configuration                (medium)
  ...

Enter the numbers or ids of the topics to edit (comma- or space-separated; ranges like 1-3 accepted; "all" to select everything):
```

**Selection syntax:**
- Single: `2` or `authentication-flow`
- Multiple: `1,3,5` or `1 3 5`
- Range: `2-4` (topics 2, 3, and 4)
- All: `all`
- Mixed: `1,3-5,7`

Resolve the selection to an ordered list of topic entries. If any token doesn't match a position or id, report the unrecognised token and ask again. Proceed once at least one valid topic is resolved.

### Step E2 — Per-Topic Edit Loop

For each topic in the selection, in order, run an individual edit loop.

Display a progress header before each loop:

```
─────────────────────────────────────────────
Editing topic [X of Y]: <title>
─────────────────────────────────────────────

  ID:               <id>
  Title:            <title>  (not editable — changing id/title would orphan the existing file)
  Description:      <description>
  Business context: <business_context>
  Importance:       <importance>
  Generation notes: <generation_notes, or "(none)">
  Files ([N] relevant files):
    - path/to/file.py
    ...
  Subtopics:        none  [or list subtopic titles]

Commands:
  ok                                    — confirm edits to this topic, move to next
  description <text>
  importance high|medium|low
  business-context <sentence>
  notes <text>                          — set or replace generation notes
  notes clear                           — remove generation notes
  notes append <text>                   — append to existing generation notes
  add-file <path>
  remove-file <path>
  sub <title>                           — add a subtopic
  remove-sub <subtopic-id>              — remove a subtopic
  (plain-English edits also accepted)
```

When the user types `ok`, save the confirmed in-memory state for this topic and immediately advance to the next topic in the selection. Do not write to disk yet.

After all topics in the selection have been confirmed, continue to Step E3.

### Command Processing (Edit Mode)

`id` and `title` are not editable — changing them would orphan the existing file on disk. (To rename a topic, use Add Mode to add a new one and manually remove the old document.) All other commands:

- **`description <text>`**: Replace `description`.
- **`importance high|medium|low`**: Replace `importance`.
- **`business-context <sentence>`**: Replace `business_context`.
- **`notes <text>`**: Set `generation_notes` to `<text>`.
- **`notes clear`**: Set `generation_notes` to empty string.
- **`notes append <text>`**: Concatenate `<text>` to existing `generation_notes` (space-separated if non-empty).
- **`add-file <path>`**: Append to `relevant_files` if not already present.
- **`remove-file <path>`**: Remove from `relevant_files`.
- **`sub <title>`**: Append subtopic with `id`: `<parent-id>--<slug>`, `title`, empty `description`, `user_requested: false`, `relevant_files: []`.
- **`remove-sub <subtopic-id>`**: Remove matching subtopic.
- **Plain-English edits**: Apply to in-memory draft; describe the change before re-displaying.

### Step E3 — Batch Update plan.yml

Read current `llm-gen-wiki/plan.yml`. For **each** confirmed topic in the selection, find its entry by `id` and replace it in-place with the confirmed in-memory values. Apply all replacements before writing.

Field presence rule for `generation_notes`: write the field if non-empty; omit it entirely if empty.

Write the complete updated YAML back to `llm-gen-wiki/plan.yml` in a **single write** after all replacements are applied.

### Step E4 — Compute Document Jobs for All Selected Topics

Run the skill-local `compute_docs.py` script after the batch `plan.yml` update. Keep the current working directory at the repository root being updated:

```bash
python3 <wiki-update-skill-dir>/compute_docs.py
```

Read `llm-gen-wiki/documents.json` and collect jobs whose `topic_id` or `parent_topic_id` matches any selected topic id.

### Step E5 — Dispatch All Writing Subagents in One Parallel Batch

Dispatch **all** writing subagents for **all** selected topics in a **single Agent batch call** — one subagent per document, all sent simultaneously.

Pass the same 14 inputs as Step A6 to each `wiki-write-topic` subagent, using the selected document jobs and the fresh metadata values from Step 2 for `generated_at`, `branch`, `commit_hash`, `origin_url`, `repo_type`, `scope_prefix`, and `language`. The regenerated documents overwrite existing files at the same paths.

Wait for all subagents to complete.

### Step E6 — Finalize

Proceed to **Shared Steps** (Steps S1–S3) with mode = `edit`, topic list = [all confirmed topics].

---

## Shared Steps

### Step S1 — Rebuild index.md

After all writing subagents complete, run the skill-local `render_index.py` script to fully rebuild `llm-gen-wiki/index.md` from the current `llm-gen-wiki/plan.yml` and `llm-gen-wiki/meta.yml`. Keep the current working directory at the repository root being updated:

```bash
python3 <wiki-update-skill-dir>/render_index.py
```

### Step S2 — Append to log.md

Run the `append_log.py` script to create or repair `llm-gen-wiki/log.md` and append the correct add/edit record:

```bash
# Add mode
python3 <wiki-update-skill-dir>/append_log.py add <topic-id>

# Edit mode
python3 <wiki-update-skill-dir>/append_log.py edit <topic-id> [<topic-id> ...]
```

### Step S3 — Done

**Add mode:**

> "Topic added. [D] new document(s) written to `llm-gen-wiki/`:
> - `llm-gen-wiki/<NN>-<topic-id>.md`
> [  - `llm-gen-wiki/<NNa>-<subtopic-slug>.md`]
>
> `llm-gen-wiki/index.md` rebuilt with [T] total topics.
>
> Optional: run `/wiki-crossref` to update inline links, or `/wiki-lint` to check for issues."

**Edit mode — single topic:**

> "Topic updated. [D] document(s) regenerated in `llm-gen-wiki/`:
> - `llm-gen-wiki/<NN>-<topic-id>.md`
> [  - `llm-gen-wiki/<NNa>-<subtopic-slug>.md`]
>
> `llm-gen-wiki/index.md` rebuilt with [T] total topics.
>
> Optional: run `/wiki-crossref` to update inline links, or `/wiki-lint` to check for issues."

**Edit mode — multiple topics:**

> "Updated [Y] topics. [D] document(s) regenerated in `llm-gen-wiki/`:
> - `llm-gen-wiki/<NN>-<topic-id>.md`   ← [topic title]
> - `llm-gen-wiki/<NN>-<topic-id>.md`   ← [topic title]
> [  - `llm-gen-wiki/<NNa>-<subtopic-slug>.md`]
>
> `llm-gen-wiki/index.md` rebuilt with [T] total topics.
>
> Optional: run `/wiki-crossref` to update inline links, or `/wiki-lint` to check for issues."

where `[Y]` is the number of topics edited and `[D]` is the total document count across all of them.
