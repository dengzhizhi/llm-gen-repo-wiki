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

    def test_force_all_pending_when_resume_is_disabled(self):
        jobs = [
            {"topic_title": "Overview", "output_file": "/tmp/01-overview.md"},
            {"topic_title": "Lifecycle", "output_file": "/tmp/01a-lifecycle.md"},
        ]

        pending = SELECT_PENDING_DOCS.select_pending_jobs(jobs, force_all=True)

        self.assertEqual([job["topic_title"] for job in pending], ["Overview", "Lifecycle"])

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
                with mock.patch("sys.stdout.write") as write:
                    SELECT_PENDING_DOCS.main([])
            finally:
                os.chdir(original_cwd)

        rendered = "".join(call.args[0] for call in write.call_args_list)
        self.assertIn('"topic_title": "Overview"', rendered)


if __name__ == "__main__":
    unittest.main()
