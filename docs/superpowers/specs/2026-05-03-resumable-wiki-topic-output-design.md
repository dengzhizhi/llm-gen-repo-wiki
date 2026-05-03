# Resumable Wiki Topic Output Design

## Context

The local `wiki-gen` skill dispatches one `wiki-write-topic` subagent per chapter document. Today the workflow assumes the batch completes cleanly before the generated wiki is considered usable.

That is fragile when subagents hard-break mid-run, for example due to rate limits or harness interruptions. In that failure mode, the broken subagent cannot be recovered gracefully in-session, so the practical recovery path is to rerun generation and avoid redoing chapters that were already completed successfully.

This repository is the source of truth for these skills, so the behavior change must be specified in the project-owned files under `skills/`.

## Goal

Make successful topic-writing subagents leave durable chapter artifacts so a later `wiki-gen` rerun can regenerate only unfinished chapters.

## Non-Goals

- Do not add a separate checkpoint manifest or done-file format.
- Do not redesign the user-facing approval flow for `wiki-gen`.
- Do not attempt graceful recovery of a subagent after a hard break.
- Do not change `index.md` or `log.md` into independently checkpointed artifacts.
- Do not require partial-document recovery.

## Design

### Primary Durability Contract

`wiki-write-topic` should treat writing the final chapter document to `output_file` as its primary success contract.

The subagent should:

1. generate the full markdown document
2. persist that document to the assigned `output_file`
3. emit its one-line success confirmation only after the final file is in place

This makes the chapter file itself the durable artifact. A successful subagent leaves behind a completed document even if a sibling subagent or the parent `wiki-gen` run fails later.

### Rerun Resume Behavior

`wiki-gen` should treat the filesystem as the source of truth for finished chapter jobs.

Before dispatching Step 5 writing subagents, `wiki-gen` should inspect each job in `llm-gen-wiki/documents.json` and classify it as:

- complete: `output_file` already exists and is non-empty
- pending: `output_file` is missing or empty

Only pending jobs should receive a new `wiki-write-topic` subagent dispatch.

This allows a later rerun of `wiki-gen` to resume from previously written chapter files without introducing a second state-tracking mechanism.

Resume semantics are intentionally narrow:

- they apply when rerunning generation for the same already-approved plan
- they are meant to recover from interrupted chapter generation, not to preserve outputs across plan edits

If the user edits `llm-gen-wiki/plan.yml` before approving the rerun, `wiki-gen` should conservatively treat all chapter jobs in the newly computed `llm-gen-wiki/documents.json` as pending, even if matching output files already exist. That avoids incorrectly reusing stale chapter files after topic, scope, or output-path changes.

### Atomic Chapter Writes

`wiki-write-topic` should write chapter files atomically.

The write flow should be:

1. write the completed document to a temporary file in the same directory as `output_file`
2. replace the final `output_file` path with the temporary file only after the document is complete

This prevents a hard break during the write from leaving a truncated chapter file at the final path, which would otherwise be misclassified as finished on rerun.

The implementation should use a helper that performs:

1. create a sibling temporary path derived from `output_file`, for example `output_file + ".tmp"`
2. write the full document content to that temporary path
3. atomically replace `output_file` with the temporary path using a filesystem-level replace operation such as Python `os.replace(...)`

The helper should own the atomic write so the skill contract is precise and does not depend on an interactive editor-style tool behavior.

### Failure Model

The intended behavior under failure is:

- if a subagent hard-breaks before the atomic replace step, no completed chapter artifact exists, so the job is retried on rerun
- if a subagent hard-breaks after the atomic replace step, the final chapter file already exists and should be skipped on rerun
- if the parent `wiki-gen` run breaks after some topic subagents have succeeded, those completed chapter files remain valid durable outputs

This design does not attempt to salvage partial work. It only guarantees that fully completed chapter documents survive independently of batch completion.

### End-Of-Run Aggregates

`llm-gen-wiki/index.md` and `llm-gen-wiki/log.md` should remain end-of-run aggregate outputs owned by `wiki-gen`.

If the orchestrator hard-breaks before those steps, rerunning `wiki-gen` should be sufficient to:

- skip already completed chapter documents
- generate only missing chapter documents
- rebuild `index.md`
- append or repair `log.md`

This keeps durable recovery scoped to the chapter documents that actually require expensive subagent work.

`log.md` should remain append-only for completed generation runs. An interrupted run that never reaches the final logging step should leave no new completed-run entry. A successful recovery rerun may append a new completion record for that rerun after all required chapter jobs, `index.md`, and log generation steps succeed.

### Scope Of Changes

The design should stay narrowly scoped to project-owned skill definitions:

- `skills/wiki-gen/SKILL.md`
- `skills/wiki-write-topic/SKILL.md`

If the implementation needs helper code changes to support atomic writes or pre-dispatch skip checks, those helpers should remain minimal and directly in service of this recovery behavior.

## Files

- Modify `skills/wiki-gen/SKILL.md`.
- Modify `skills/wiki-write-topic/SKILL.md`.
- Review helper scripts used by `wiki-gen` only if needed to keep rerun behavior consistent with the updated skill contracts.

## Testing

Verify the design by checking:

- the spec makes chapter files, not subagent return status, the durable success artifact
- rerun behavior skips chapter jobs whose `output_file` already exists and is non-empty
- the write path requires atomic replacement rather than writing directly to the final file
- the failure model distinguishes pre-write and post-write hard breaks
- the scope stays limited to topic output durability and rerun behavior
