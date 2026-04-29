---
name: wiki-plan
description: Use when discovering topics and generating a wiki structure plan for a code repository — reads the file tree and README, incorporates user-specified topics, and writes llm-gen-wiki/plan.yml. Invoked as a subagent by wiki-gen.
---

# Wiki Plan

## Overview

This skill is invoked as a subagent by the `wiki` orchestrator skill. It receives a repository root path and an optional list of extra topics, explores the codebase, and produces a structured plan file describing what wiki documents to generate. When the skill starts, it announces: "Planning wiki structure for repository at: [repo_root]".

## Inputs

| Parameter | Type | Description |
|---|---|---|
| `repo_root` | string | Absolute path to the root of the repository being documented |
| `extra_topics` | list of strings (optional) | Additional topic titles explicitly requested by the user; these MUST appear in the plan with `user_requested: true` |
| `scope_prefix` | string | Path of `repo_root` relative to the git root; empty string `""` when `repo_root` is the git root |

## Process

### Pass 1 — Broad Scan

1. **Discover the file tree (BFS)** — Use the BFS file discovery procedure below to build a structural picture of the repository before reading any files.
2. **Read the README** — Read `README.md` from `repo_root`. If it does not exist, fall back to `README.rst`, then `README.txt`. If none exist, proceed without a README.
3. **Read entry points and config files** — Using the file tree gathered in step 1, identify and read the following files from `repo_root` in priority order:
   - Entry points: `main.py`, `index.ts`, `app.py`, `app.ts`, `server.py`, `main.go`, `cmd/main.go`, `cli.py`, `index.js`, and similar top-level launchers visible in the tree.
   - Config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, `.env.example`, `Makefile`, `settings.py`, `config.py`, `application.yml`, `config.yml`, and any other top-level configuration files visible in the tree.
4. **Draft an internal topic outline** — From Pass 1 findings, produce a candidate list of 8–12 topic areas, each with a rough set of associated file paths. This draft is internal only — do not write it to disk.

---

### BFS File Discovery

Use `git ls-tree` to explore the repository structure level by level. All git commands must be run from `repo_root`. The command shows only the **immediate** contents of a directory (never recurses), with each entry classified as `blob` (file), `tree` (directory), or `commit` (submodule — treat as a leaf, do not explore further).

`scope_prefix` is provided as an input. Because `git ls-tree` output paths are always relative to the git root, they will naturally carry `scope_prefix` as a leading component when it is non-empty — so phases 1–5 need no special adjustment once Phase 0 is scoped correctly.

**Stop conditions** — stop as soon as any one of these is met:
- No important directories remain to explore
- Depth has reached level 5
- Running **entry count** (total lines across all `git ls-tree` outputs) reaches or exceeds **600**

#### Phase 0 — Root (always run)

```bash
# If scope_prefix is empty:
git ls-tree HEAD

# If scope_prefix is non-empty:
git ls-tree HEAD -- <scope_prefix>/
```

Record every line as one entry; add to running total. Identify:
- `blob` lines → root-level files (note important ones: READMEs, package manifests, entry points)
- `tree` lines → level-1 directory candidates

**All** level-1 directories proceed to Phase 1 — there is no content yet to judge importance on, so explore all of them.

#### Phase 1–5 — BFS Levels

Repeat for L = 1 to 5:

1. Take the set of directory paths selected for this level. If the set is empty, **stop**.
2. Issue **one Bash call** for the entire set. Directory paths come directly from the previous phase's `git ls-tree` output and already include `scope_prefix`:
   ```bash
   git ls-tree HEAD -- <dir1>/ <dir2>/ ... <dirN>/
   ```
3. Count the output lines; add to running total. If the running total now equals or exceeds 600, process this output and then **stop** — do not proceed to L+1.
4. From the output, collect all `tree` entries as candidate subdirectories for level L+1.
5. **Select important subdirectories** — mark a subdirectory as important if it is likely to contain source code, feature modules, data models, API handlers, infrastructure config, tests, or documentation. **Skip** directories whose names indicate generated or ephemeral output: `dist`, `build`, `out`, `.next`, `__pycache__`, `.cache`, `coverage`, `*.egg-info`, `tmp`, `logs`, `vendor` (skip unless the language idiom requires it, e.g. Go).
6. The selected paths become the input for level L+1.

---

### Pass 2 — Targeted Deep Read

5. **Read domain files per topic** — For each candidate topic from Pass 1, identify and read 3–5 files in that domain: core logic files, data models, key API handlers, service classes, or similar. The goals are to:
   - Populate accurate `relevant_files` lists
   - Understand what each feature does at the implementation level
   - Understand *why* each feature exists from a product/business perspective (signals come from comments, naming, README references, and the shape of the code)

   Total file budget across both passes: soft cap of **40 files**. Stop earlier for small repos.

### Finalise

6. **Generate and write the wiki plan** — Follow the Prompt section below to produce the final YAML. Create the `llm-gen-wiki/` directory inside `repo_root` if it does not already exist, then write the YAML to `llm-gen-wiki/plan.yml`.

## Prompt

<role>
You are an expert software architect and technical writer analysing a code repository to design the structure of a comprehensive wiki.
Your goal is to produce a well-organised, hierarchical wiki plan that covers every significant aspect of the codebase so that developers can understand, navigate, and contribute to it with ease.
</role>

<guidelines>
- Analyse the file tree, README, and entry-point files provided to you before generating the plan.
- Create between 8 and 12 top-level topics that together give COMPREHENSIVE coverage of the repository.
- Aim to cover all of the following areas where they are present in the repository:
  - Overall architecture and system design
  - Core features and key functionality
  - Data management, data flow, and state management
  - Frontend / UI components (if applicable)
  - Backend / server-side systems (if applicable)
  - AI / model integration (if applicable)
  - Deployment, infrastructure, and DevOps
  - Configuration and environment setup
  - Extensibility, customisation, and plugin systems
  - Testing strategy and quality assurance
- Prefer topics that will benefit from visual diagrams (architecture overviews, data flows, component relationships, process workflows, state machines, class hierarchies).
- Use importance levels to indicate priority:
  - `high` — foundational; understanding this topic is required before the others (e.g. overall architecture, core feature)
  - `medium` — important supporting topic (e.g. configuration, testing)
  - `low` — supplementary detail (e.g. minor utilities, changelog)
- Assign `subtopics` only when a topic is genuinely large and complex — spanning 10 or more files across 3 or more distinct directories. Simple, focused topics MUST have `subtopics: []`. Subtopics should not repeat information from their parent; each subtopic covers a distinct slice of the parent domain.
- Every `relevant_files` list MUST contain only actual file paths verified from the file tree you gathered. Do NOT invent or guess file paths.
- If `extra_topics` were provided, each extra topic MUST appear in the plan exactly as a top-level topic with `user_requested: true`. Extra topics must never be omitted or merged away — add them even if the repository does not appear to contain relevant files yet.
- All other topics generated by your own analysis MUST have `user_requested: false`.
- Generate a unique, descriptive `id` in kebab-case for every topic (e.g. `system-architecture`, `authentication-flow`, `data-pipeline`).
- Subtopic ids MUST follow the format `<parent-id>--<child-slug>` using a double hyphen separator (e.g. `data-pipeline--ingestion`, `data-pipeline--transformation`).
- The `repo` field should be the repository's directory name (the last component of `repo_root`).
- The `description` field at the top level should be a single sentence describing the repository's overall purpose derived from the README and entry-point files.
- Every topic and subtopic must have a concise single-sentence `description` field that accurately describes what that document will cover.
- Every **top-level topic** MUST include a `business_context` field: a single sentence answering "What problem does this feature solve for the product or its users?" Derive it from what you read in Pass 2 — never invent it. **Subtopics** MUST include `business_context` only when their business purpose is meaningfully distinct from their parent topic; otherwise omit the field on subtopics.
- Output ONLY the YAML content — no preamble, no commentary, no markdown code fences. The very first character of your output must be `r` (the start of `repo:`).
</guidelines>

### Required Output Schema

The output must conform exactly to the following YAML structure:

```
repo: <repository-directory-name>
description: <one-sentence description of the repository>
topics:
  - id: <kebab-case-id>
    title: <Display Title>
    description: <one-sentence description of what this document covers>
    business_context: <one-sentence answer to "what problem does this solve for users or the product?">
    importance: high|medium|low
    user_requested: false
    relevant_files:
      - path/to/file.py
      - path/to/other.ts
    subtopics:
      - id: <parent-id>--<child-kebab-id>
        title: <Subtopic Display Title>
        description: <one-sentence description>
        user_requested: false
        relevant_files:
          - path/to/specific/file.py
```

Topics with no subtopics must have `subtopics: []` (not an absent key).

### Formatting Rules

- Output ONLY the raw YAML. Do NOT wrap it in markdown code fences (no ``` or ```yaml).
- Do NOT include any explanation, preamble, or closing remarks — just the YAML.
- Start directly with `repo:` on the first line and end with the last line of the YAML.
- Ensure the YAML is valid and properly indented (2-space indentation).

## Output

After generating the plan, create the `llm-gen-wiki/` directory inside `repo_root` if it does not exist, then write the YAML to `llm-gen-wiki/plan.yml` using the Write tool. Do NOT print the YAML body to stdout — only write it to the file. After writing, output a single confirmation line: "Written: [repo_root]/llm-gen-wiki/plan.yml".
