# Capped Subagent Waves For Chapter Generation Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Change `wiki-gen` and `wiki-update` so chapter-writing subagents run in sequential waves of at most 6 concurrent jobs, stopping later waves on any current-wave failure.

**Architecture:** Keep batching policy in the orchestrator layer rather than changing `wiki-write-topic`. Add one small shared helper to chunk job lists into wave-sized groups and update both orchestrator prompts to dispatch one batch per wave, wait for completion, and stop aggregate-output steps on any wave failure.

**Tech Stack:** Markdown skill prompts, Python 3 helper scripts, Python `unittest`

---

## File Structure

- Modify: `skills/wiki-gen/SKILL.md`
  Responsibility: replace “dispatch all selected jobs simultaneously” with wave-based chapter generation capped at 6 concurrent jobs, including same-plan resume jobs.
- Modify: `skills/wiki-update/SKILL.md`
  Responsibility: replace both add-mode and edit-mode all-at-once document regeneration with the same capped wave execution model.
- Create: `skills/wiki-gen/chunk_document_jobs.py`
  Responsibility: read a JSON job list and return ordered waves of at most 6 jobs, so orchestrator prompts can use a concrete local helper instead of hand-waving list chunking.
- Create: `tests/test_chunk_document_jobs.py`
  Responsibility: verify chunk sizing, ordering preservation, empty-input behavior, and exact final-wave sizing.

## Chunk 1: Shared Wave Chunking Helper

### Task 1: Add failing tests for job chunking

**Files:**
- Create: `tests/test_chunk_document_jobs.py`
- Reference: `skills/wiki-gen/chunk_document_jobs.py`

- [ ] **Step 1: Write the failing chunk-size test**

```python
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


CHUNK_DOCUMENT_JOBS = load_module(
    "skills/wiki-gen/chunk_document_jobs.py", "chunk_document_jobs"
)


class ChunkJobsTest(unittest.TestCase):
    def test_chunks_jobs_into_waves_of_at_most_six(self):
        jobs = [{"topic_title": f"Doc {i}"} for i in range(1, 15)]

        waves = CHUNK_DOCUMENT_JOBS.chunk_jobs(jobs, wave_size=6)

        self.assertEqual([len(wave) for wave in waves], [6, 6, 2])
```

- [ ] **Step 2: Run the new test file to verify it fails**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: module load fails because `skills/wiki-gen/chunk_document_jobs.py` does not exist yet, producing an import/discovery error rather than a passing test run.

- [ ] **Step 3: Add failing tests for ordering and empty input**

```python
    def test_preserves_job_order_across_waves(self):
        jobs = [{"topic_title": name} for name in ["A", "B", "C", "D", "E", "F", "G"]]

        waves = CHUNK_DOCUMENT_JOBS.chunk_jobs(jobs, wave_size=6)

        flattened = [job["topic_title"] for wave in waves for job in wave]
        self.assertEqual(flattened, ["A", "B", "C", "D", "E", "F", "G"])

    def test_empty_job_list_returns_no_waves(self):
        self.assertEqual(CHUNK_DOCUMENT_JOBS.chunk_jobs([], wave_size=6), [])
```

- [ ] **Step 4: Add a failing CLI-oriented test**

```python
    def test_main_prints_json_waves(self):
        jobs = [{"topic_title": "A"}, {"topic_title": "B"}]
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            input_path = tmp_path / "jobs.json"
            input_path.write_text(json.dumps(jobs))
            with mock.patch("builtins.print") as fake_print:
                exit_code = CHUNK_DOCUMENT_JOBS.main([str(input_path)])

        self.assertEqual(exit_code, 0)
        rendered = fake_print.call_args.args[0]
        self.assertIn('"topic_title": "A"', rendered)
        self.assertIn("[", rendered)
```

- [ ] **Step 5: Re-run the test file**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: still `ERROR` until the helper exists.

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/test_chunk_document_jobs.py
git commit -m "test: cover chapter generation job chunking"
```

### Task 2: Implement the chunking helper

**Files:**
- Create: `skills/wiki-gen/chunk_document_jobs.py`
- Test: `tests/test_chunk_document_jobs.py`

- [ ] **Step 1: Write the minimal chunking helper**

```python
#!/usr/bin/env python3
"""Chunk document jobs into capped concurrent waves."""

import json
import sys
from pathlib import Path


def chunk_jobs(jobs, wave_size=6):
    return [jobs[index:index + wave_size] for index in range(0, len(jobs), wave_size)]


def render_chunked_jobs(input_path: Path, wave_size=6):
    jobs = json.loads(input_path.read_text())
    return json.dumps(chunk_jobs(jobs, wave_size=wave_size), indent=2)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: chunk_document_jobs.py /absolute/path/to/jobs.json")
        return 2
    print(render_chunked_jobs(Path(argv[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Run the targeted tests**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: `OK`

- [ ] **Step 3: Add a regression test for an exact multiple of 6**

```python
    def test_exact_multiple_of_six_has_no_extra_empty_wave(self):
        jobs = [{"topic_title": f"Doc {i}"} for i in range(12)]

        waves = CHUNK_DOCUMENT_JOBS.chunk_jobs(jobs, wave_size=6)

        self.assertEqual([len(wave) for wave in waves], [6, 6])
```

- [ ] **Step 4: Re-run the test file**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: `OK`

- [ ] **Step 5: Commit the helper and passing tests**

```bash
git add skills/wiki-gen/chunk_document_jobs.py tests/test_chunk_document_jobs.py
git commit -m "feat: add capped document job chunking helper"
```

## Chunk 2: Orchestrator Prompt Integration

### Task 3: Update `wiki-gen` to use capped waves

**Files:**
- Modify: `skills/wiki-gen/SKILL.md`
- Reference: `skills/wiki-gen/chunk_document_jobs.py`
- Test: `tests/test_chunk_document_jobs.py`

- [ ] **Step 1: Replace the all-at-once Step 5 wording with wave-based dispatch**

Update `skills/wiki-gen/SKILL.md` so Step 5 says:

```markdown
- run `chunk_document_jobs.py` on the selected job list
- process the returned waves in order
- each wave contains at most 6 document jobs
- dispatch one Agent batch call per wave
- wait for the whole wave before starting the next
```

- [ ] **Step 2: Make failure and aggregate-output behavior explicit**

Add exact prompt rules that:

```markdown
- any failed, timed-out, canceled, or batch-level errored wave stops later waves
- the run surfaces which current-wave jobs succeeded and failed
- `index.md` and `log.md` are skipped on any failed wave
- the user receives a partial-success summary rather than a normal completion message
```

- [ ] **Step 3: Run focused regression tests**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: `OK`

- [ ] **Step 4: Commit the prompt change**

```bash
git add skills/wiki-gen/SKILL.md skills/wiki-gen/chunk_document_jobs.py tests/test_chunk_document_jobs.py
git commit -m "feat: cap wiki-gen chapter waves at six"
```

### Task 4: Update `wiki-update` to use capped waves

**Files:**
- Modify: `skills/wiki-update/SKILL.md`
- Reference: `skills/wiki-gen/chunk_document_jobs.py`
- Test: `tests/test_chunk_document_jobs.py`

- [ ] **Step 1: Replace add-mode all-at-once regeneration wording**

Update the add-mode chapter dispatch step in `skills/wiki-update/SKILL.md` so it uses:

```markdown
- chunk the selected job list into waves of at most 6
- dispatch one Agent batch call per wave
- wait for each wave before continuing
- stop later waves if the current wave fails
```

- [ ] **Step 2: Replace edit-mode all-at-once regeneration wording**

Update the edit-mode regeneration step in `skills/wiki-update/SKILL.md` with the same 6-job wave model and the same aggregate-output skip rules on failure.

- [ ] **Step 3: Run the focused regression tests again**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: `OK`

- [ ] **Step 4: Verify the edited skill prompts contain the capped-wave rules**

Run:

```bash
rg -n "at most 6|up to 6|stop.*wave|skip.*index.md|skip.*log.md|partial-success" skills/wiki-gen/SKILL.md skills/wiki-update/SKILL.md
```

Expected: matches in both skill files showing:
- capped concurrent writing waves of 6 or fewer jobs
- waiting for each wave before the next
- stopping later waves on failure
- skipping aggregate-output steps on failed waves

- [ ] **Step 5: Commit the prompt changes**

```bash
git add skills/wiki-update/SKILL.md skills/wiki-gen/chunk_document_jobs.py tests/test_chunk_document_jobs.py
git commit -m "feat: cap wiki-update chapter waves at six"
```

### Task 5: Final verification

**Files:**
- Verify: `skills/wiki-gen/SKILL.md`
- Verify: `skills/wiki-update/SKILL.md`
- Verify: `skills/wiki-gen/chunk_document_jobs.py`
- Verify: `tests/test_chunk_document_jobs.py`

- [ ] **Step 1: Run the focused test suite**

Run: `python3 -m unittest tests.test_chunk_document_jobs -v`
Expected: all tests `OK`

- [ ] **Step 2: Run Python syntax verification on the new helper**

Run: `python3 -m py_compile skills/wiki-gen/chunk_document_jobs.py`
Expected: no output

- [ ] **Step 3: Review the final diff for scope control**

Run:

```bash
git diff --stat -- skills/wiki-gen/SKILL.md skills/wiki-update/SKILL.md skills/wiki-gen/chunk_document_jobs.py tests/test_chunk_document_jobs.py
```

Expected: changes limited to the two orchestrator prompts, the new chunking helper, and the new tests

- [ ] **Step 4: Commit any final cleanups**

```bash
git add skills/wiki-gen/SKILL.md skills/wiki-update/SKILL.md skills/wiki-gen/chunk_document_jobs.py tests/test_chunk_document_jobs.py
git commit -m "chore: finalize capped chapter generation waves"
```
