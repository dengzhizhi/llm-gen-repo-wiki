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

## Process

### Pass 1 — Broad Scan

1. **Gather the file tree** — Run `find . -type f | grep -v node_modules | grep -v .git | head -300` from `repo_root` to obtain a representative file listing.
2. **Read the README** — Read `README.md` from `repo_root`. If it does not exist, fall back to `README.rst`, then `README.txt`. If none exist, proceed without a README.
3. **Read entry points and config files** — Identify and read the following files from `repo_root` in priority order:
   - Entry points visible in the file tree: `main.py`, `index.ts`, `app.py`, `app.ts`, `server.py`, `main.go`, `cmd/main.go`, `cli.py`, `index.js`, and similar top-level launchers.
   - Config files visible in the file tree: `package.json`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, `.env.example`, `Makefile`, `settings.py`, `config.py`, `application.yml`, `config.yml`, and any other top-level configuration files.
4. **Draft an internal topic outline** — From Pass 1 findings, produce a candidate list of 8–12 topic areas, each with a rough set of associated file paths. This draft is internal only — do not write it to disk.

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
