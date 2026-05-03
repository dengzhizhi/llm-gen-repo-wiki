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
| `language` | string | Human-readable language for all wiki content, e.g. `English`, `Japanese`, `Simplified Chinese`. Default: `English` |

## Process

### Pass 1 — Meta Scan and Topic Formation

**Step 1 — Run the meta scan.**  Keep the current working directory at `repo_root`:

```bash
python3 <wiki-plan-skill-dir>/scan_meta.py --scope-prefix "<scope_prefix>"
```

Omit `--scope-prefix` when `scope_prefix` is empty. The script does BFS tree exploration, counts line sizes for every file, ranks files by git activity, and reads up to 5 key entry-point / manifest files. It writes `llm-gen-wiki/scan_meta.json`.

**Step 2 — Read `llm-gen-wiki/scan_meta.json`.** This is your structural knowledge base.

| Field | Contents |
|---|---|
| `repo` | Repository directory name |
| `detected_language` | Primary language detected from root manifests |
| `tree` | Flat list of all discovered `{path, type}` entries |
| `file_sizes` | Line count per file path |
| `git_activity` | Top 40 files ranked by commit count (last 6 months) |
| `git_ranks` | Rank position (1 = most active) per file path |
| `key_file_contents` | Full content of up to 5 manifest / entry-point files |
| `key_files_read` | Which key files were included |
| `jvm_source_fallback` | Flat source list for JVM projects when BFS missed source |

**Step 3 — Read the README.**  Read `README.md` from `repo_root`. Fall back to `README.rst`, then `README.txt` if absent.

**Step 4 — Fallback when README is weak.**  If docs are sparse or marketing-only:
- From `tree` in scan_meta.json, find integration or e2e test files (names containing `integration`, `e2e`, or `acceptance`, or paths under `test/` / `tests/`). Read up to 3 — they reveal system boundaries better than any README.
- From `git_activity`, identify the top 5 most-committed files. Read any with `file_sizes ≤ 150` that you have not already examined.

**Step 5 — Form candidate topics and select files for deep analysis.**

Using the `tree`, `git_ranks`, `file_sizes`, and `key_file_contents` from scan_meta.json, produce an internal draft topic set (do not write to disk). For each draft topic, select **3–7 candidate files** using this priority order:

1. Files with the lowest `git_rank` within the topic's directory domain
2. Files whose names most closely match the topic (e.g. `auth.py` for an authentication topic)
3. Files in the topic's directory with `file_sizes ≤ 150` (cheapest to read fully)
4. Data model or schema files in the topic's domain
5. Supporting files

Collect all selected paths across all topics into a **flat deduplicated list**. Aim for 20–40 paths total; exclude files already read as key files.

---

### Pass 2 — Targeted Deep Read

**Step 6 — Run the detail scan** with the candidate file list from Step 5:

```bash
python3 <wiki-plan-skill-dir>/scan_detail.py <file1> <file2> <file3> ...
```

The script reads `llm-gen-wiki/scan_meta.json` for the detected language, then for each file applies the appropriate strategy based on line count and writes `llm-gen-wiki/scan_detail.json`.

**Step 7 — Read `llm-gen-wiki/scan_detail.json`.**  For each file the `strategy` field determines what is available:

| `strategy` | What the entry contains | How to use it |
|---|---|---|
| `full` | Complete file content in `content` | Read directly — no Read tool call needed |
| `signatures` | Class/function/type declarations in `signatures` | Use signatures to understand structure; sufficient for `relevant_files` and most `business_context` |
| `signatures_only` | Signatures only; file > 500 lines | Add to topic's `open_questions` for writer subagent to read in full |
| `not_found` | File did not exist | Remove from `relevant_files` |

**Step 8 — Targeted supplemental reads.** For any file where `scan_detail.json` provides signatures but not enough detail to write a confident `business_context`, issue a Read call. Budget: **at most 10 additional Read calls** total across all topics. Prioritise high-importance topics first.

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
- All human-readable string fields — `description` (repo-level and per-topic), `title`, `business_context`, `planning_warnings` entries, `planning_questions` entries, and subtopic `description` — MUST be written in `{language}`. Technical identifiers (`id`, `relevant_files` paths, `coverage_tags` labels, field keys) remain in English regardless of language.
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
