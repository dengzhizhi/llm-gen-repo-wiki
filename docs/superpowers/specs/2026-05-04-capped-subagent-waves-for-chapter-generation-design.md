# Capped Subagent Waves For Chapter Generation Design

## Context

The local `wiki-gen` skill currently describes chapter generation as a single parallel batch of writing subagents, and `wiki-update` similarly regenerates multiple selected documents in one parallel batch.

That maximizes throughput, but it also amplifies failure blast radius. If the underlying model or harness hits a token-limit or related generation failure, too many chapter jobs can fail in the same run.

The desired behavior is operational containment: no more than 6 chapter-writing subagents should be in flight at once, so a failure wave can affect at most 6 jobs.

This repository is the source of truth for these skills, so the behavior change must be specified in the project-owned files under `skills/`.

## Goal

Change both `wiki-gen` and `wiki-update` so chapter-writing subagents are dispatched in sequential waves of at most 6 concurrent jobs.

## Non-Goals

- Do not change topic planning behavior.
- Do not change the `wiki-write-topic` contract.
- Do not add job prioritization or document-size heuristics.
- Do not dynamically tune the concurrency limit at runtime.
- Do not redesign the resume-skip artifact model.

## Design

### Wave Size

The maximum concurrency for chapter-writing subagents is 6.

This is a hard cap, not a target or recommendation. If fewer than 6 jobs remain, the final wave is smaller.

### `wiki-gen` Dispatch Behavior

After `wiki-gen` finishes its existing document-job selection step, including any resume-skip filtering, it should process the selected chapter jobs in sequential waves.

For each wave:

1. take the next up-to-6 document jobs from the selected job list
2. dispatch those jobs in one Agent batch call
3. wait for the entire wave to complete
4. only then decide whether to continue to the next wave

This replaces the current “dispatch all selected chapter jobs simultaneously” behavior.

### `wiki-update` Dispatch Behavior

After `wiki-update` determines which documents must be regenerated, it should use the same wave-based execution model.

For each wave:

1. take the next up-to-6 regeneration jobs
2. dispatch those jobs in one Agent batch call
3. wait for the wave to complete
4. only then decide whether to continue

This keeps update-time failure containment aligned with full-generation behavior.

### Failure Handling

If any chapter-writing subagent in the current wave fails, the orchestrator should stop before dispatching any later waves.

At that point it should surface:

- which jobs in the current wave succeeded
- which jobs in the current wave failed
- that later queued jobs were not started because wave execution stopped on failure

This preserves the intended containment boundary: at most 6 jobs are exposed to one failure wave.

### Durable Outputs

Successful chapter files from earlier waves remain valid durable artifacts under the existing chapter-output rules.

For `wiki-gen`, successful chapters from completed waves, and successful chapters within a partially failed wave, remain available on disk. Later waves are simply not started after the failure.

For `wiki-update`, the same rule applies to regenerated chapters: completed outputs remain written, but later queued jobs are not dispatched once a failure wave is detected.

### Aggregate Outputs

`index.md` and `log.md` generation should remain end-of-run aggregate steps.

If a failure occurs in any wave, the orchestrator should not proceed to aggregate output steps that assume chapter generation completed cleanly.

### Scope Of Changes

The design should stay narrowly scoped to the two orchestrator skills and any minimal helper support needed to express batching clearly:

- `skills/wiki-gen/SKILL.md`
- `skills/wiki-update/SKILL.md`
- optional helper code only if needed to support wave chunking cleanly

No planner, writer, or plan-schema changes are required for this feature.

## Files

- Modify `skills/wiki-gen/SKILL.md`.
- Modify `skills/wiki-update/SKILL.md`.
- Add helper code only if the implementation needs a shared local chunking utility.

## Testing

Verify the design by checking:

- `wiki-gen` no longer instructs dispatching all chapter jobs in one simultaneous batch
- `wiki-update` no longer instructs dispatching all regeneration jobs in one simultaneous batch
- both skills explicitly cap concurrent writing subagents at 6
- both skills describe waiting for each wave to complete before starting the next
- both skills describe stopping later waves when the current wave contains failures
- the aggregate-output steps are still gated on clean completion of all waves
