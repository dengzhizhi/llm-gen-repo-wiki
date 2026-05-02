# Wiki Plan Quality Design

## Context

The local `wiki-plan` skill is responsible for discovering repository topics and writing `llm-gen-wiki/plan.yml`, which then drives interactive review in `wiki-gen` and downstream topic writing.

The current planner is structurally useful, but it has several quality gaps:

- It does not explicitly audit whether important repository areas were covered.
- It relies too heavily on fixed topic counts and file-count heuristics.
- It mirrors directory structure more readily than developer onboarding needs.
- It does not preserve enough planning metadata for later stages.
- It does not surface uncertainty clearly before the user approves the plan.

This repository is the source of truth for these skills, so the changes must be made in the project-owned files under `skills/`.

## Goal

Improve the local `wiki-plan` skill so it produces higher-quality, onboarding-oriented wiki plans with stronger coverage checks, cleaner topic boundaries, richer plan metadata, and more useful human interaction before generation proceeds.

## Non-Goals

- Do not edit installed copies of these skills outside this repository.
- Do not redesign the end-user command surface for `/wiki-gen` or `/wiki-update`.
- Do not implement a separate planning service or external validator.
- Do not optimize primarily for architecture-review or operations-only use cases.
- Do not require fully interactive questioning inside `wiki-plan` itself.

## Design

### Planning Lens

`wiki-plan` should optimize primarily for onboarding documentation.

That means the planner should bias topic selection and descriptions toward:

- how a new contributor should understand the system
- where the main entry points and developer workflows begin
- how the major modules relate to each other
- what configuration, setup, testing, and debugging paths matter first
- what extension points or advanced concerns matter after the fundamentals

The planner should still include architecture, infrastructure, and advanced system concerns when they are significant, but those should not crowd out the onboarding path.

### Revised Planning Flow

Restructure the planner into five explicit stages:

1. **Broad structural scan**
   - Discover the repository tree with the existing BFS-style process.
   - Read top-level README and key entry-point/config files.
   - Collect evidence about important directories, launchers, runtimes, and system boundaries.

2. **Topic candidate synthesis**
   - Draft candidate top-level topics from the structural evidence.
   - Infer likely developer onboarding flows such as setup, request handling, command execution, core data flow, or testing workflow.
   - Infer likely primary audience per topic.

3. **Coverage audit**
   - Build an internal mapping from discovered repository aspects to candidate topic ids.
   - Check for uncovered major areas such as architecture, setup, core workflows, tests, deployment/runtime, and docs/tooling.
   - Add, merge, or justify omissions before finalizing the plan.

4. **Ambiguity capture**
   - Record unresolved planning risks as warnings.
   - Record high-value user decisions as explicit questions.
   - Preserve both in the plan output so `wiki-gen` can show them during review.

5. **Plan emission**
   - Write the enriched `plan.yml` schema.
   - Keep the planner output deterministic and evidence-grounded.

### Adaptive Topic Sizing

Replace the hard-coded "8-12 top-level topics" rule with an adaptive target.

The planner should estimate complexity using signals such as:

- number of important directories
- number of entry points
- number of distinct services or runtimes
- presence of multiple apps, packages, or subsystems
- presence of substantial tests, docs, and deployment configuration

The planner should still stay bounded for readability, but topic count should flex according to evidence rather than force filler topics or over-compress large repositories.

### Coverage Audit Requirements

Before writing the final plan, the planner should internally verify coverage for these categories when present:

- overall architecture and mental model
- main user-facing or developer-facing workflows
- configuration and local environment setup
- data flow and state management
- tests and quality strategy
- deployment and runtime operations
- internal tooling and documentation support
- user-requested extra topics

If an important category is present but not clearly represented, the planner should either:

- add a topic
- broaden an existing topic
- or explicitly justify why the category is intentionally folded into another topic

### Cross-Cutting Concern Discovery

The planner should not treat directory structure as the whole system model.

It should explicitly look for cross-cutting concerns such as:

- authentication and authorization
- configuration loading
- logging and observability
- error handling and recovery
- caching
- background jobs and asynchronous processing
- plugin or extension boundaries
- AI or model integration
- permissions, tenancy, or feature-flag behavior

When such a concern is architecturally important, the planner should elevate it into its own topic or make it a clearly named part of a broader topic.

### Topic Boundary Rules

The planner should improve topic quality by making boundaries more conceptual and less mechanical.

For top-level topics:

- each topic should have a distinct reason to exist
- sibling topics should not substantially overlap in purpose
- the planner should prefer names that help a new contributor navigate the system

For subtopics:

- split by distinct workflow, audience, or subsystem responsibility
- use file count and directory spread only as supporting evidence
- avoid creating subtopics that merely restate the parent topic with smaller file lists

The planner should also perform an anti-overlap check and merge or redraw topics when two candidates cover essentially the same slice of the system.

### Weak-README Fallback

When top-level documentation is weak, missing, or overly marketing-focused, the planner should fall back more aggressively to evidence from:

- tests
- route or handler definitions
- package manifests
- internal docs under `docs/`
- CI workflows
- deployment configuration
- migration names
- comments and docstrings in entry-point or core files

This allows the planner to derive a useful onboarding structure even from under-documented repositories.

### Plan Schema Extension

Extend `llm-gen-wiki/plan.yml` with additive planning metadata.

At the top level of the plan:

- `planning_warnings`: list of short evidence-grounded warnings about plan uncertainty
- `planning_questions`: list of short user-facing questions that would improve plan quality before approval

For each topic, add optional metadata:

- `primary_audience`: such as `new-contributor`, `maintainer`, `operator`, `plugin-author`, or `api-consumer`
- `doc_goal`: a short statement of what the document should help the reader accomplish
- `diagram_candidates`: a list of useful diagram types or relationships worth visualizing
- `coverage_tags`: short labels describing what system concerns this topic covers
- `open_questions`: optional unresolved topic-specific questions

These fields should be optional and additive so manual editing remains practical and downstream consumers can adopt them safely.

### `wiki-gen` Review Flow Changes

`wiki-gen` should continue to own the human approval loop, but it should present more planner context before the user types `ok`.

After reading `llm-gen-wiki/plan.yml`, `wiki-gen` should display:

- the proposed topic structure
- any `planning_warnings`
- any `planning_questions`
- the existing command menu for editing the plan

This preserves the current workflow while giving the user better leverage to improve the plan before document generation begins.

### Compatibility

Because `plan.yml` gains new fields, any local helpers that parse or transform the plan may need to tolerate and preserve additive metadata.

At minimum, the following project-owned components should be reviewed for compatibility:

- `skills/wiki-gen/compute_docs.py`
- `skills/wiki-update/compute_docs.py`
- any helper that reads, rewrites, or renders `llm-gen-wiki/plan.yml`

The desired behavior is additive compatibility, not a disruptive format break.

## Files

- Modify `skills/wiki-plan/SKILL.md`.
- Modify `skills/wiki-gen/SKILL.md`.
- Review and update plan-schema consumers as needed:
  - `skills/wiki-gen/compute_docs.py`
  - `skills/wiki-update/compute_docs.py`
  - related local helpers if they assume the older schema

## Testing

Verify the design by checking:

- the spec clearly states onboarding as the default planner lens
- the revised planner flow includes coverage audit and ambiguity capture
- the schema section includes both `planning_warnings` and `planning_questions`
- the design calls for `wiki-gen` to display those fields during plan review
- the file list includes both prompt files and any schema consumers that may require updates
