---
name: wiki-plan
description: Use when discovering topics and generating an architecture-first wiki structure plan for a code repository, especially when the planner needs to audit technical coverage, capture uncertainty, and write llm-gen-wiki/plan.yml for wiki-gen review.
---

# Wiki Plan

## Overview

This skill is invoked as a subagent by the `wiki` orchestrator skill. It receives a repository root path and an optional list of extra topics, explores the codebase, and produces a structured plan file describing what wiki documents to generate. Its default lens is architectural overview and technical deep search: map the system boundaries, major execution paths, component relationships, and technically significant internals before lighter onboarding concerns. When the skill starts, it announces: "Planning wiki structure for repository at: [repo_root]".

## Inputs

| Parameter | Type | Description |
|---|---|---|
| `repo_root` | string | Absolute path to the root of the repository being documented |
| `extra_topics` | list of strings (optional) | Additional topic titles explicitly requested by the user; these MUST appear in the plan with `user_requested: true` |
| `scope_prefix` | string | Path of `repo_root` relative to the git root; empty string `""` when `repo_root` is the git root |

## Process

### Pass 1 — Broad Structural Scan

1. **Discover the file tree (BFS)** — Use the BFS file discovery procedure below to build a structural picture of the repository before reading any files.
2. **Read the README** — Read `README.md` from `repo_root`. If it does not exist, fall back to `README.rst`, then `README.txt`. If none exist, proceed without a README.
3. **Read entry points and config files** — Using the file tree gathered in step 1, identify and read the following files from `repo_root` in priority order:
   - Entry points: `main.py`, `index.ts`, `app.py`, `app.ts`, `server.py`, `main.go`, `cmd/main.go`, `cli.py`, `index.js`, and similar top-level launchers visible in the tree.
   - Config files: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, `.env.example`, `Makefile`, `settings.py`, `config.py`, `application.yml`, `config.yml`, and any other top-level configuration files visible in the tree.
4. **Fallback when README is weak** — If top-level docs are sparse, absent, or overly marketing-focused, lean more heavily on tests, route or handler definitions, package manifests, docs under `docs/`, CI workflows, deployment config, migration names, and comments/docstrings in entry-point or core files.
5. **Draft an internal topic outline** — From Pass 1 findings, produce an internal candidate topic set sized to repository complexity. Prioritise architecture-first topics such as system boundaries, runtime paths, key modules, data flow, infrastructure/runtime configuration, integrations, testing strategy, and major cross-cutting concerns. This draft is internal only — do not write it to disk.

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

6. **Read domain files per topic** — For each candidate topic from Pass 1, identify and read 3–5 files in that domain: core logic files, data models, key API handlers, service classes, or similar. The goals are to:
   - Populate accurate `relevant_files` lists
   - Understand what each feature does at the implementation level
   - Understand *why* each feature exists from a product/business perspective (signals come from comments, naming, README references, and the shape of the code)
   - Infer the likely technical audience and document goal for each topic

   Total file budget across both passes: soft cap of **40 files**. Stop earlier for small repos.

### Pass 3 — Coverage Audit And Boundary Check

7. **Audit plan coverage internally** — Before writing YAML, build an internal mapping from discovered repository aspects to candidate topic ids. Check whether the plan covers, when present:
   - overall architecture and system boundaries
   - main runtime paths and technically important workflows
   - configuration, runtime setup, and operational environment
   - data flow and state management
   - tests and quality strategy
   - deployment and runtime operations
   - internal tooling, extensions, and docs support
   - all `extra_topics`

   If an important area is uncovered, add a topic, broaden an existing topic, or explicitly justify folding it into another topic.

8. **Discover cross-cutting concerns** — Look explicitly for concerns that span directories or modules: authentication, authorization, configuration loading, logging, observability, error handling, caching, background jobs, plugin seams, AI/model integration, tenancy, permissions, and feature flags. Elevate these into their own topics when they are architecturally significant.

9. **Refine boundaries and capture uncertainty** — Merge or redraw overlapping topics. A topic must have a distinct reason to exist. Record any unresolved planning risks in `planning_warnings` and any high-value human decisions in `planning_questions`.

   When you record `planning_questions`, assume the human may know very little about the codebase. Each question should therefore:
   - include enough repository-specific context for the human to make the choice without reading code
   - explain why the choice matters for the wiki structure
   - prefer a small set of explicit options over open-ended wording
   - use open-ended questions only when the decision cannot be expressed meaningfully as a bounded selection

### Finalise

10. **Generate and write the wiki plan** — Follow the Prompt section below to produce the final YAML. Create the `llm-gen-wiki/` directory inside `repo_root` if it does not already exist, then write the YAML to `llm-gen-wiki/plan.yml`.

## Prompt

<role>
You are an expert software architect and technical writer analysing a code repository to design the structure of a comprehensive wiki.
Your goal is to produce a well-organised, hierarchical wiki plan that covers every significant aspect of the codebase so that developers can understand, navigate, and contribute to it with ease. Optimise primarily for architectural overview and technical deep search, while still including onboarding-oriented material only when it materially supports understanding the system.
</role>

<guidelines>
- Analyse the file tree, README, and entry-point files provided to you before generating the plan.
- Size the number of top-level topics to repository complexity. Small repositories may need fewer topics; large repositories may need more. Keep the plan concise, but do not force filler topics or over-compress distinct subsystems.
- Bias topic naming and ordering toward architecture and technical depth: system boundaries, execution paths, major modules, component relationships, data flow, integrations, runtime behavior, infrastructure, testing strategy, and extension points.
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
- Perform an internal coverage audit before finalising the plan. If an important discovered area is not clearly represented, add a topic, broaden an existing topic, or intentionally fold it into another topic with a clear reason.
- Explicitly look for cross-cutting concerns that may not map cleanly to a single directory, such as authentication, configuration loading, logging, observability, error handling, caching, async work, plugin seams, permissions, tenancy, feature flags, or AI/model integration.
- Prefer architecture-first grouping over lightweight onboarding grouping when the two compete. When in doubt, explain how the system is built and behaves before explaining how a newcomer should approach it.
- Prefer topics that will benefit from visual diagrams (architecture overviews, data flows, component relationships, process workflows, state machines, class hierarchies).
- Use importance levels to indicate priority:
  - `high` — foundational; understanding this topic is required before the others (e.g. overall architecture, core feature)
  - `medium` — important supporting topic (e.g. configuration, testing)
  - `low` — supplementary detail (e.g. minor utilities, changelog)
- Each top-level topic must have a distinct reason to exist. Merge or redraw candidate topics that substantially overlap in files, workflow coverage, or reader purpose.
- Assign `subtopics` when a topic contains distinct workflows, audiences, or subsystem responsibilities. File count and directory spread are supporting signals, not the primary split rule. Simple, focused topics MUST have `subtopics: []`. Subtopics should not repeat information from their parent; each subtopic covers a distinct slice of the parent domain.
- Every `relevant_files` list MUST contain only actual file paths verified from the file tree you gathered. Do NOT invent or guess file paths.
- If `extra_topics` were provided, each extra topic MUST appear in the plan exactly as a top-level topic with `user_requested: true`. Extra topics must never be omitted or merged away — add them even if the repository does not appear to contain relevant files yet.
- All other topics generated by your own analysis MUST have `user_requested: false`.
- Generate a unique, descriptive `id` in kebab-case for every topic (e.g. `system-architecture`, `authentication-flow`, `data-pipeline`).
- Subtopic ids MUST follow the format `<parent-id>--<child-slug>` using a double hyphen separator (e.g. `data-pipeline--ingestion`, `data-pipeline--transformation`).
- The `repo` field should be the repository's directory name (the last component of `repo_root`).
- The `description` field at the top level should be a single sentence describing the repository's overall purpose derived from the README and entry-point files.
- Include `planning_warnings` when you have evidence-grounded uncertainty or weak signals that the human should keep in mind during review.
- Include `planning_questions` when a human decision would materially improve the plan before generation starts.
- `planning_questions` must be low-context and user-friendly. Assume the human may not know the repository internals yet.
- Each `planning_questions` entry should be a complete prompt, not a fragment. It should briefly name the relevant repo area, describe the observed ambiguity, explain why the choice affects the plan, and then offer 2-4 concrete options when possible.
- Prefer selection wording such as `Choose one: ...` or `Which of these should the wiki emphasize first: ...` over broad open-ended questions.
- Good example: `The repo appears to have both an HTTP request lifecycle under api/ and a background processing pipeline under worker/. Which subsystem should receive the deeper architectural treatment in the first pass? Choose one: API-first, worker-first, or equal depth.`
- Avoid questions like `What do you want this wiki to focus on?` unless there is no narrower evidence-grounded technical choice available.
- Every topic and subtopic must have a concise single-sentence `description` field that accurately describes what that document will cover.
- Every **top-level topic** MUST include a `business_context` field: a single sentence answering "What problem does this feature solve for the product or its users?" Derive it from what you read in Pass 2 — never invent it. **Subtopics** MUST include `business_context` only when their business purpose is meaningfully distinct from their parent topic; otherwise omit the field on subtopics.
- Topic-level optional metadata:
  - `primary_audience` — use labels such as `maintainer`, `operator`, `plugin-author`, `api-consumer`, `new-contributor`, or other technically meaningful audiences
  - `doc_goal` — a short sentence describing what the document should help the reader accomplish
  - `diagram_candidates` — optional list of diagram ideas worth rendering later
  - `coverage_tags` — optional list of short labels for the system concerns this topic covers
  - `open_questions` — optional list of unresolved topic-specific questions
- Output ONLY the YAML content — no preamble, no commentary, no markdown code fences. The very first character of your output must be `r` (the start of `repo:`).
</guidelines>

### Required Output Schema

The output must conform exactly to the following YAML structure:

```
repo: <repository-directory-name>
description: <one-sentence description of the repository>
planning_warnings:
  - <short evidence-grounded warning>
planning_questions:
  - <context-rich user-facing question with explicit options when possible>
topics:
  - id: <kebab-case-id>
    title: <Display Title>
    description: <one-sentence description of what this document covers>
    business_context: <one-sentence answer to "what problem does this solve for users or the product?">
    importance: high|medium|low
    user_requested: false
    primary_audience: <optional audience label>
    doc_goal: <optional one-sentence document goal>
    diagram_candidates:
      - <optional diagram idea>
    coverage_tags:
      - <optional short label>
    open_questions:
      - <optional unresolved topic-specific question>
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
If there are no meaningful plan-level warnings or questions, use `planning_warnings: []` and `planning_questions: []`.

### Formatting Rules

- Output ONLY the raw YAML. Do NOT wrap it in markdown code fences (no ``` or ```yaml).
- Do NOT include any explanation, preamble, or closing remarks — just the YAML.
- Start directly with `repo:` on the first line and end with the last line of the YAML.
- Ensure the YAML is valid and properly indented (2-space indentation).

## Output

After generating the plan, create the `llm-gen-wiki/` directory inside `repo_root` if it does not exist, then write the YAML to `llm-gen-wiki/plan.yml` using the Write tool. Do NOT print the YAML body to stdout — only write it to the file. After writing, output a single confirmation line: "Written: [repo_root]/llm-gen-wiki/plan.yml".
