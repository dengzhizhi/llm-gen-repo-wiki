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

    def test_preserves_job_order_across_waves(self):
        jobs = [{"topic_title": name} for name in ["A", "B", "C", "D", "E", "F", "G"]]

        waves = CHUNK_DOCUMENT_JOBS.chunk_jobs(jobs, wave_size=6)

        flattened = [job["topic_title"] for wave in waves for job in wave]
        self.assertEqual(flattened, ["A", "B", "C", "D", "E", "F", "G"])

    def test_empty_job_list_returns_no_waves(self):
        self.assertEqual(CHUNK_DOCUMENT_JOBS.chunk_jobs([], wave_size=6), [])

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

    def test_exact_multiple_of_six_has_no_extra_empty_wave(self):
        jobs = [{"topic_title": f"Doc {i}"} for i in range(12)]

        waves = CHUNK_DOCUMENT_JOBS.chunk_jobs(jobs, wave_size=6)

        self.assertEqual([len(wave) for wave in waves], [6, 6])


if __name__ == "__main__":
    unittest.main()
