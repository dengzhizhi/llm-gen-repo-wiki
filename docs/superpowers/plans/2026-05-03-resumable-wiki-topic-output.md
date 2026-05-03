# Resumable Wiki Topic Output Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make successful `wiki-write-topic` subagents leave durable chapter files so a later `wiki-gen` rerun can skip finished chapters and regenerate only unfinished ones.

**Architecture:** Keep the chapter markdown file as the durable artifact, not a sidecar manifest. Add one small helper in `wiki-gen` to classify pending jobs for same-plan reruns, and one small helper in `wiki-write-topic` to perform atomic file replacement so partial writes never masquerade as completed chapters.

**Tech Stack:** Markdown skill prompts, Python 3 helper scripts, Python `unittest`

---

## File Structure

- Modify: `skills/wiki-gen/SKILL.md`
  Responsibility: define rerun semantics, same-plan detection, and the “dispatch only pending jobs unless the approved plan changed” workflow.
- Create: `skills/wiki-gen/select_pending_docs.py`
  Responsibility: read `llm-gen-wiki/documents.json`, classify each job by `output_file` state, and print the pending job list for `wiki-gen` to dispatch.
- Modify: `skills/wiki-write-topic/SKILL.md`
  Responsibility: change the writer contract so the final file write is the primary success artifact and the confirmation line is emitted only after the atomic replace succeeds.
- Create: `skills/wiki-write-topic/atomic_write.py`
  Responsibility: write a completed markdown string to a sibling temp file and atomically replace the target path with `os.replace`.
- Create: `tests/test_resume_jobs.py`
  Responsibility: verify pending/completed classification, non-empty-file checks, and the “force all pending” path used after plan edits.
- Create: `tests/test_atomic_write.py`
  Responsibility: verify temp-file replacement semantics, directory creation behavior, and cleanup of the final output path on normal success.

## Chunk 1: Resume-Safe `wiki-gen` Dispatch

### Task 1: Add failing tests for pending-job selection

**Files:**
- Create: `tests/test_resume_jobs.py`
- Reference: `skills/wiki-gen/select_pending_docs.py`

- [ ] **Step 1: Write the failing test for skipping completed chapter files**

```python
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


SELECT_PENDING_DOCS = load_module(
    "skills/wiki-gen/select_pending_docs.py", "select_pending_docs"
)


class SelectPendingDocsTest(unittest.TestCase):
    def test_skips_non_empty_outputs_and_keeps_missing_or_empty_outputs(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            done_path = tmp_path / "01-done.md"
            empty_path = tmp_path / "02-empty.md"
            missing_path = tmp_path / "03-missing.md"
            done_path.write_text("# complete\n")
            empty_path.write_text("")
            jobs = [
                {"topic_title": "Done", "output_file": str(done_path)},
                {"topic_title": "Empty", "output_file": str(empty_path)},
                {"topic_title": "Missing", "output_file": str(missing_path)},
            ]

            pending = SELECT_PENDING_DOCS.select_pending_jobs(jobs)

        self.assertEqual([job["topic_title"] for job in pending], ["Empty", "Missing"])
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python3 -m unittest tests.test_resume_jobs -v`
Expected: `ERROR` because `skills/wiki-gen/select_pending_docs.py` does not exist yet.

- [ ] **Step 3: Add failing coverage for the force-all path**

```python
    def test_force_all_pending_when_resume_is_disabled(self):
        jobs = [
            {"topic_title": "Overview", "output_file": "/tmp/01-overview.md"},
            {"topic_title": "Lifecycle", "output_file": "/tmp/01a-lifecycle.md"},
        ]

        pending = SELECT_PENDING_DOCS.select_pending_jobs(jobs, force_all=True)

        self.assertEqual([job["topic_title"] for job in pending], ["Overview", "Lifecycle"])
```

- [ ] **Step 4: Run the test file again**

Run: `python3 -m unittest tests.test_resume_jobs -v`
Expected: still `ERROR` until the helper exists.

- [ ] **Step 5: Commit the failing tests**

```bash
git add tests/test_resume_jobs.py
git commit -m "test: cover resumable wiki job selection"
```

### Task 2: Implement the pending-job helper

**Files:**
- Create: `skills/wiki-gen/select_pending_docs.py`
- Test: `tests/test_resume_jobs.py`

- [ ] **Step 1: Write the minimal helper implementation**

```python
#!/usr/bin/env python3
"""Select pending wiki document jobs from llm-gen-wiki/documents.json."""

import json
import sys
from pathlib import Path


def is_complete_output(path_str: str) -> bool:
    path = Path(path_str)
    return path.exists() and path.is_file() and path.stat().st_size > 0


def select_pending_jobs(jobs, force_all=False):
    if force_all:
        return list(jobs)
    return [job for job in jobs if not is_complete_output(job["output_file"])]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force_all = "--force-all" in argv
    documents_path = Path("llm-gen-wiki/documents.json")
    jobs = json.loads(documents_path.read_text())
    pending = select_pending_jobs(jobs, force_all=force_all)
    print(json.dumps(pending, indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the targeted tests**

Run: `python3 -m unittest tests.test_resume_jobs -v`
Expected: `OK`

- [ ] **Step 3: Add a small CLI-oriented test for JSON output shape**

```python
    def test_main_prints_pending_jobs_as_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            wiki_dir = tmp_path / "llm-gen-wiki"
            wiki_dir.mkdir()
            jobs = [{"topic_title": "Overview", "output_file": str(tmp_path / "01-overview.md")}]
            (wiki_dir / "documents.json").write_text(json.dumps(jobs))
            original_cwd = Path.cwd()
            try:
                os = __import__("os")
                os.chdir(tmp_path)
                with unittest.mock.patch("sys.stdout.write") as write:
                    SELECT_PENDING_DOCS.main([])
            finally:
                os.chdir(original_cwd)

        rendered = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn('"topic_title": "Overview"', rendered)
```

- [ ] **Step 4: Re-run the test file**

Run: `python3 -m unittest tests.test_resume_jobs -v`
Expected: `OK`

- [ ] **Step 5: Commit the helper and passing tests**

```bash
git add skills/wiki-gen/select_pending_docs.py tests/test_resume_jobs.py
git commit -m "feat: add resumable wiki job selection helper"
```

### Task 3: Update `wiki-gen` to use same-plan resume rules

**Files:**
- Modify: `skills/wiki-gen/SKILL.md`
- Reference: `skills/wiki-gen/select_pending_docs.py`
- Test: `tests/test_resume_jobs.py`

- [ ] **Step 1: Update the skill instructions around re-run semantics**

Add explicit rules to `skills/wiki-gen/SKILL.md` covering:

```markdown
- Capture a hash of `llm-gen-wiki/plan.yml` immediately before entering the Step 3 review loop when the plan already exists.
- Recompute the hash after the user types `ok`.
- If the hash changed during review, disable resume skipping for this run and dispatch all jobs.
- If the hash did not change, use `select_pending_docs.py` to dispatch only jobs whose `output_file` is missing or empty.
```

- [ ] **Step 2: Update Step 5 from “dispatch all jobs” to “dispatch the pending job list”**

Add this exact command guidance, using the same `<wiki-gen-skill-dir>` placeholder convention that `skills/wiki-gen/SKILL.md` already uses for `compute_docs.py`, `render_index.py`, and `append_log.py`:

```bash
python3 <wiki-gen-skill-dir>/select_pending_docs.py
python3 <wiki-gen-skill-dir>/select_pending_docs.py --force-all
```

Expected behavior to describe in the prompt:
- unchanged approved plan: skip non-empty finished chapter files
- edited approved plan: regenerate all chapter jobs from the new `documents.json`

- [ ] **Step 3: Make the user-facing completion semantics explicit**

Document that:
- successful chapter files from earlier interrupted runs remain valid durable outputs
- `index.md` and `log.md` are still rebuilt only after the pending chapter jobs finish
- a rerun after interruption may write fewer topic subagents than the total document count

- [ ] **Step 4: Run the regression tests that cover current plan parsing behavior plus the new helper**

Run: `python3 -m unittest tests.test_plan_schema tests.test_resume_jobs -v`
Expected: `OK`

- [ ] **Step 5: Verify the plan-changed branch disables resume skipping**

Run:

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path

repo_root = Path.cwd()
module_path = repo_root / "skills/wiki-gen/select_pending_docs.py"
spec = importlib.util.spec_from_file_location("select_pending_docs", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
jobs = [{"topic_title": "Done", "output_file": str(repo_root / "README.md")}]
pending = module.select_pending_jobs(jobs, force_all=True)
print([job["topic_title"] for job in pending])
PY
```

Expected: prints `['Done']`, proving the changed-plan path dispatches all jobs even when the file already exists.

- [ ] **Step 6: Commit the prompt change**

```bash
git add skills/wiki-gen/SKILL.md tests/test_resume_jobs.py skills/wiki-gen/select_pending_docs.py
git commit -m "feat: add resumable wiki-gen dispatch flow"
```

## Chunk 2: Atomic `wiki-write-topic` Output

### Task 4: Add failing tests for atomic chapter writes

**Files:**
- Create: `tests/test_atomic_write.py`
- Reference: `skills/wiki-write-topic/atomic_write.py`

- [ ] **Step 1: Write the failing atomic-write success test**

```python
import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ATOMIC_WRITE = load_module(
    "skills/wiki-write-topic/atomic_write.py", "atomic_write"
)


class AtomicWriteTest(unittest.TestCase):
    def test_writes_via_temp_file_and_replaces_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            output_path = tmp_path / "chapter.md"
            output_path.write_text("old\n")

            ATOMIC_WRITE.write_text_atomically(output_path, "new\n")

            self.assertEqual(output_path.read_text(), "new\n")
            self.assertFalse((tmp_path / "chapter.md.tmp").exists())
```

- [ ] **Step 2: Run the new test to verify it fails**

Run: `python3 -m unittest tests.test_atomic_write -v`
Expected: `ERROR` because `skills/wiki-write-topic/atomic_write.py` does not exist yet.

- [ ] **Step 3: Add a failing nested-directory test**

```python
    def test_creates_parent_directory_before_replacing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "chapter.md"

            ATOMIC_WRITE.write_text_atomically(output_path, "# chapter\n")

            self.assertEqual(output_path.read_text(), "# chapter\n")
```

- [ ] **Step 4: Add a failing test that proves `os.replace` is part of the contract**

```python
    def test_uses_os_replace_for_atomic_swap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"
            with unittest.mock.patch("os.replace") as replace:
                ATOMIC_WRITE.write_text_atomically(output_path, "body\n")

        replace.assert_called_once()
        src_arg, dst_arg = replace.call_args.args
        self.assertTrue(str(src_arg).endswith(".tmp"))
        self.assertEqual(Path(dst_arg), output_path)
```

- [ ] **Step 5: Re-run the test file**

Run: `python3 -m unittest tests.test_atomic_write -v`
Expected: still `ERROR` until the helper exists.

- [ ] **Step 6: Commit the failing tests**

```bash
git add tests/test_atomic_write.py
git commit -m "test: cover atomic wiki chapter writes"
```

### Task 5: Implement the atomic write helper

**Files:**
- Create: `skills/wiki-write-topic/atomic_write.py`
- Test: `tests/test_atomic_write.py`

- [ ] **Step 1: Write the minimal helper**

```python
#!/usr/bin/env python3
"""Atomic file writing helper for wiki chapter output."""

from pathlib import Path
import os


def write_text_atomically(output_path, content):
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    temp_path.write_text(content)
    os.replace(temp_path, output_path)
```

- [ ] **Step 2: Run the targeted tests**

Run: `python3 -m unittest tests.test_atomic_write -v`
Expected: `OK`

- [ ] **Step 3: Add a regression test that an empty final string still produces a real file**

```python
    def test_allows_empty_content_for_callers_that_choose_it(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"

            ATOMIC_WRITE.write_text_atomically(output_path, "")

            self.assertTrue(output_path.exists())
            self.assertEqual(output_path.read_text(), "")
```

- [ ] **Step 4: Add a regression test for failure before replace**

```python
    def test_failed_replace_leaves_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"
            output_path.write_text("old\n")
            with unittest.mock.patch("os.replace", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    ATOMIC_WRITE.write_text_atomically(output_path, "new\n")

            self.assertEqual(output_path.read_text(), "old\n")
```

- [ ] **Step 5: Re-run the test file**

Run: `python3 -m unittest tests.test_atomic_write -v`
Expected: `OK`

- [ ] **Step 6: Commit the helper and passing tests**

```bash
git add skills/wiki-write-topic/atomic_write.py tests/test_atomic_write.py
git commit -m "feat: add atomic wiki chapter writer"
```

### Task 6: Update `wiki-write-topic` to use the atomic writer contract

**Files:**
- Modify: `skills/wiki-write-topic/SKILL.md`
- Reference: `skills/wiki-write-topic/atomic_write.py`
- Test: `tests/test_atomic_write.py`

- [ ] **Step 1: Rewrite the final write step in the skill prompt**

Change the process section so it says the writer must:

```markdown
8. Self-audit before writing
9. Persist the completed markdown using `atomic_write.py` so `output_file` is replaced only after the full document is ready
10. After the atomic replace succeeds, output exactly one confirmation line: `Written: [output_file]`
```

- [ ] **Step 2: Add durable-artifact and failure-model language**

Document explicitly in `skills/wiki-write-topic/SKILL.md`:
- the chapter file at `output_file` is the durable success artifact
- if the subagent fails before atomic replace, the final output file must not be treated as complete
- if the subagent fails after atomic replace, the final file is resumable and should be skipped by `wiki-gen` on an unchanged-plan rerun

- [ ] **Step 3: Update output instructions to forbid printing the document body**

Keep the existing “do not print the document body to stdout” rule, but anchor it to the new helper call so the final output path is the only persisted artifact required by the contract.

- [ ] **Step 4: Run all targeted tests for this feature slice**

Run: `python3 -m unittest tests.test_plan_schema tests.test_resume_jobs tests.test_atomic_write -v`
Expected: `OK`

- [ ] **Step 5: Verify the pre-replace failure contract directly**

Run:

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

module_path = Path("skills/wiki-write-topic/atomic_write.py")
spec = importlib.util.spec_from_file_location("atomic_write", module_path)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

with TemporaryDirectory() as tmpdir:
    output_path = Path(tmpdir) / "chapter.md"
    output_path.write_text("old\n")
    try:
        with patch("os.replace", side_effect=RuntimeError("boom")):
            module.write_text_atomically(output_path, "new\n")
    except RuntimeError:
        pass
    print(output_path.read_text())
PY
```

Expected: prints `old`, confirming a failure before replace does not clobber the durable file.

- [ ] **Step 6: Verify the post-replace success contract directly**

Run:

```bash
python3 - <<'PY'
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

def load(relative_path, module_name):
    module_path = Path(relative_path)
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module

atomic_write = load("skills/wiki-write-topic/atomic_write.py", "atomic_write")
select_pending = load("skills/wiki-gen/select_pending_docs.py", "select_pending_docs")

with TemporaryDirectory() as tmpdir:
    output_path = Path(tmpdir) / "chapter.md"
    atomic_write.write_text_atomically(output_path, "finished\n")
    pending = select_pending.select_pending_jobs(
        [{"topic_title": "Chapter", "output_file": str(output_path)}]
    )
    print(pending)
PY
```

Expected: prints `[]`, confirming a successful atomic replace leaves a resumable chapter file that `wiki-gen` will skip on an unchanged-plan rerun.

- [ ] **Step 7: Commit the prompt change**

```bash
git add skills/wiki-write-topic/SKILL.md skills/wiki-write-topic/atomic_write.py tests/test_atomic_write.py tests/test_resume_jobs.py
git commit -m "feat: make wiki topic output resumable"
```

### Task 7: Final verification

**Files:**
- Verify: `skills/wiki-gen/SKILL.md`
- Verify: `skills/wiki-gen/select_pending_docs.py`
- Verify: `skills/wiki-write-topic/SKILL.md`
- Verify: `skills/wiki-write-topic/atomic_write.py`
- Verify: `tests/test_resume_jobs.py`
- Verify: `tests/test_atomic_write.py`

- [ ] **Step 1: Run the focused test suite**

Run: `python3 -m unittest tests.test_plan_schema tests.test_resume_jobs tests.test_atomic_write -v`
Expected: all tests `OK`

- [ ] **Step 2: Run Python syntax verification on the new helpers**

Run: `python3 -m py_compile skills/wiki-gen/select_pending_docs.py skills/wiki-write-topic/atomic_write.py`
Expected: no output

- [ ] **Step 3: Review the final diff for scope control**

Run: `git diff --stat HEAD~5..HEAD`
Expected: changes limited to the two skill prompts, two helper scripts, and the new tests

- [ ] **Step 4: Commit any final cleanups**

```bash
git add skills/wiki-gen/SKILL.md skills/wiki-gen/select_pending_docs.py skills/wiki-write-topic/SKILL.md skills/wiki-write-topic/atomic_write.py tests/test_resume_jobs.py tests/test_atomic_write.py
git commit -m "chore: finalize resumable wiki generation"
```
