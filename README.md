# llm-gen-repo-wiki Skills

A set of Claude Code skills that generate structured markdown wiki documentation for any code repository. Given a repo root, the skills explore the codebase, propose a topic plan, let you review and edit it interactively, then write a complete set of wiki documents in parallel.

## Use Cases

- **Onboarding documentation** — generate a wiki for a new hire or open-source contributor so they can understand the codebase without reading every file.
- **Architecture review** — quickly map an unfamiliar codebase by letting the planning subagent surface its structure, entry points, and key modules.
- **Living reference** — regenerate the wiki after a large refactor to keep documentation in sync with the code.
- **Focused deep-dives** — specify the exact topics you care about at the start of the run; the planner will always include them alongside its own discoveries.

## Prerequisites

- [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and authenticated.
- The **Agent tool** permission must be enabled in your Claude Code settings (required for subagent dispatch).

## Installation

**Option A — Manual copy**

```bash
cp -r skills/wiki-gen skills/wiki-plan skills/wiki-write-topic \
      skills/wiki-crossref skills/wiki-lint \
      ~/.claude/skills/
```

**Option B — Plugin install**

Coming soon.

## Usage

### Full run — `/wiki-gen`

The entry-point skill that coordinates the entire pipeline. Run it from the root of the repository you want to document.

1. **Extra topics** — Claude asks whether you have specific topics to include. List them comma-separated, or press enter to skip.
2. **Planning** — a `wiki-plan` subagent explores the file tree, README, and key entry-point files, then writes `llm-gen-wiki/plan.yml` with 8–12 proposed topics.
3. **Interactive review** — Claude displays the proposed plan and accepts commands (`add`, `remove`, `rename`, `sub`, `importance`, or `ok`) so you can adjust it before any documents are written. You can also edit `llm-gen-wiki/plan.yml` directly in your editor and then type `ok`.
4. **Parallel writing** — once you approve the plan, all `wiki-write-topic` subagents are dispatched simultaneously, one per document.
5. **Index** — after all documents are written, Claude creates `llm-gen-wiki/index.md` linking the full contents, then confirms completion.

### Plan only — `/wiki-plan`

Runs just the planning subagent. Useful when you want to inspect or hand-edit `llm-gen-wiki/plan.yml` before committing to full generation.

```
/wiki-plan
```

Produces `llm-gen-wiki/plan.yml` and exits.

### Single topic — `/wiki-write-topic`

Regenerates one wiki document without re-running the full pipeline. Provide the topic title, description, list of relevant files, repo root, output file path, and whether the document is an overview.

```
/wiki-write-topic
```

## Output Structure

```
llm-gen-wiki/
├── index.md                   # table of contents, generated last
├── plan.yml                   # topic plan written by wiki-plan
├── 01-system-architecture.md  # overview doc (topic with subtopics)
├── 01a-frontend.md            # subtopic doc
├── 01b-backend.md             # subtopic doc
├── 02-configuration.md        # full doc (topic without subtopics)
└── 03-testing-strategy.md     # full doc (topic without subtopics)
```

Documents are numbered with zero-padded two-digit prefixes. Topics that have subtopics get a lightweight overview document (`01-`) plus one lettered document per subtopic (`01a-`, `01b-`, …). Topics without subtopics get a single full deep-dive document.

## Tips

- **Specify extra topics up front** — when `/wiki-gen` asks "Are there any specific topics you want the wiki to cover?", list them. The planner guarantees they appear in `plan.yml` with `user_requested: true` and will never drop them.
- **Edit the plan during confirmation** — type `add <title>`, `remove <id>`, `rename <id> <new title>`, `sub <parent-id> <title>`, or `importance <id> high|medium|low` at the confirmation prompt. Each command updates `llm-gen-wiki/plan.yml` and redisplays the plan before you type `ok`.
- **Regenerate a single document** — edit `llm-gen-wiki/plan.yml` to adjust a topic's `relevant_files` or description, then run `/wiki-write-topic` with the updated values to rewrite just that document without touching the rest.
- **Re-running after plan edits** — if `llm-gen-wiki/plan.yml` already exists when you invoke `/wiki-gen`, the skill skips the extra-topics question and the planning subagent and jumps straight to the interactive confirmation step, so you only pay for writing.

## Skills Reference

| Skill | Invocation | Role |
|---|---|---|
| `wiki-gen` | `/wiki-gen` | Full orchestrator and entry point — coordinates planning, interactive review, and parallel document generation |
| `wiki-plan` | `/wiki-plan` | Planning subagent — explores the repo and writes `llm-gen-wiki/plan.yml` |
| `wiki-write-topic` | `/wiki-write-topic` | Writing subagent — produces one complete wiki document per invocation |
| `wiki-crossref` | `/wiki-crossref` | *(Optional — token-intensive)* Adds inline cross-reference links between documents |
| `wiki-lint` | `/wiki-lint` | *(Optional — token-intensive)* Health check — flags thin docs, orphan concepts, and missing links |

## Prompt Architecture

The skills are built on the following prompt rules:

- **XML-tagged delimiters** — `<role>`, `<guidelines>`, and similar XML tags isolate distinct instruction blocks inside skill prompts, reducing ambiguity and improving instruction-following.
- **Evidence-grounded writing** — every factual claim in a generated document must be traced back to a specific source file and line range via inline `Sources:` citations, preventing hallucination.
- **Vertical Mermaid diagrams** — all flow diagrams use `graph TD` (top-down) exclusively; `graph LR` is explicitly forbidden, keeping diagrams readable at standard viewport widths.
- **Negative constraint emphasis** — critical prohibitions (never invent file paths, never print YAML to stdout, never use `graph LR`) are stated as explicit negative constraints, not just implied by positive rules.
- **Structured output schema** — `llm-gen-wiki/plan.yml` follows a fixed YAML schema (`repo`, `description`, `topics[].id/title/description/importance/user_requested/relevant_files/subtopics`) that the orchestrator and writing subagents can parse reliably without prompt-time negotiation.
