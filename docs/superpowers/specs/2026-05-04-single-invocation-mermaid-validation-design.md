# Single Invocation Mermaid Validation Design

## Context

The local `wiki-write-topic` skill generates chapter documents that often contain multiple Mermaid diagrams. Its current prompt only says that if `mmdc` is available, a subagent should validate Mermaid syntax before the chapter is written.

That leaves the validation path underspecified and inefficient:

- there is no shared extractor for multiple Mermaid blocks in one document
- there is no single local validation entry point for one chapter
- there is no standard failure report that gives the model the exact broken Mermaid source and parser error
- a successful validation does not have a clearly defined minimal success response

This repository is the source of truth for these skills, so the behavior change must be specified in the project-owned files under `skills/`.

## Goal

Add a repo-local helper that validates every Mermaid code block in one generated chapter document during a single script invocation, returning a minimal success state when all blocks pass and a structured per-block failure report when any block fails.

## Non-Goals

- Do not change the authoring rules for Mermaid diagrams themselves.
- Do not validate Mermaid across multiple chapter files in one run.
- Do not concatenate separate diagrams into one synthetic Mermaid document.
- Do not preserve rendered image files from `mmdc`.
- Do not redesign the overall wiki generation pipeline outside the chapter-writer validation step.

## Design

### Validation Unit

The validation unit is one generated Markdown chapter file.

The new helper should accept the path to one Markdown document, scan it for all fenced code blocks tagged as `mermaid`, and validate every Mermaid block found in that file during the same helper execution.

One script invocation may validate many Mermaid diagrams, but it is still one document-scoped validation run.

### Extraction Behavior

The helper should parse the chapter Markdown in source order and extract every block that uses a fenced code block header of ` ```mermaid `.

For each extracted block, the helper should record enough context to make failures debuggable:

- a 1-based block index within the document
- the Mermaid source code for that block
- if practical, the source line range in the Markdown file

Non-Mermaid code fences must be ignored.

### Validation Strategy

The helper should validate each extracted Mermaid block independently by writing it to a temporary `.mmd` file and running `mmdc` against that temporary input.

All validations for the document should happen inside the same helper process. The helper may invoke `mmdc` once per Mermaid block internally, but the chapter-writing workflow should call the helper only once per validation pass over the document.

This avoids cross-diagram contamination and keeps error attribution precise.

### Success Output

If every Mermaid block in the document passes validation, the helper should emit only a simple success state.

The success output should be intentionally terse, for example a single machine-friendly line indicating success plus the number of validated Mermaid blocks.

The goal is that a clean chapter does not flood the model with noise.

### Failure Output

If one or more Mermaid blocks fail validation, the helper should emit a structured failure report for each failing block.

Each failure entry should include:

- the block index
- the line range in the source Markdown file if available
- the Mermaid source code that failed
- the `mmdc` error output or parser failure reason

The output should be designed for immediate model debugging: when the validator fails, the writing agent should be able to inspect the reported block source and error message, repair the broken Mermaid code, and rerun validation.

### No-Diagram Case

If the document contains no Mermaid blocks, the helper should return a simple success state rather than failing.

The validator exists to check Mermaid syntax, not to require Mermaid content in every file.

### Temporary File Handling

The helper should create any temporary Mermaid input files and `mmdc` outputs in a temporary workspace and clean them up after validation finishes.

Rendered artifacts are not part of the contract and must not be preserved.

### `wiki-write-topic` Integration

Replace the current “dispatch a subagent to validate Mermaid syntax” behavior in `skills/wiki-write-topic/SKILL.md` with a local helper-driven flow.

The updated writer flow should be:

1. draft the chapter markdown
2. if Mermaid diagrams are present and `mmdc` is available, run the new validator helper once against the draft document
3. if validation succeeds, continue
4. if validation fails, use the reported block source and error output to repair the broken Mermaid code, then rerun the same validator helper
5. only after validation passes should the document proceed to final atomic persistence

If `mmdc` is unavailable, the skill may still skip validation as it does today.

### Scope Of Changes

The design should stay narrowly scoped to the chapter writer and its local helper surface:

- `skills/wiki-write-topic/SKILL.md`
- a new helper under `skills/wiki-write-topic/`
- tests for Mermaid extraction and validation reporting

No orchestrator-level resume or planning changes are required for this feature.

## Files

- Modify `skills/wiki-write-topic/SKILL.md`.
- Create a Mermaid validation helper under `skills/wiki-write-topic/`.
- Add tests for multi-block extraction, success reporting, and failure reporting.

## Testing

Verify the design by checking:

- one helper invocation validates all Mermaid blocks in one chapter document
- non-Mermaid code fences are ignored
- successful validation returns only a terse success state
- failed validation reports the broken Mermaid source and the error reason per block
- multiple Mermaid blocks in one document are validated independently
- temporary validation artifacts are not kept after the run
