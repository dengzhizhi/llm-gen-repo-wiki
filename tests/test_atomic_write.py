import importlib.util
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

    def test_creates_parent_directory_before_replacing_target(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "chapter.md"

            ATOMIC_WRITE.write_text_atomically(output_path, "# chapter\n")

            self.assertEqual(output_path.read_text(), "# chapter\n")

    def test_uses_os_replace_for_atomic_swap(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"
            with mock.patch("os.replace") as replace:
                ATOMIC_WRITE.write_text_atomically(output_path, "body\n")

        replace.assert_called_once()
        src_arg, dst_arg = replace.call_args.args
        self.assertTrue(str(src_arg).endswith(".tmp"))
        self.assertEqual(Path(dst_arg), output_path)

    def test_rejects_empty_content(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"

            with self.assertRaises(ValueError):
                ATOMIC_WRITE.write_text_atomically(output_path, "")

            self.assertFalse(output_path.exists())

    def test_failed_replace_leaves_existing_output_unchanged(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "chapter.md"
            output_path.write_text("old\n")
            with mock.patch("os.replace", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    ATOMIC_WRITE.write_text_atomically(output_path, "new\n")

            self.assertEqual(output_path.read_text(), "old\n")
            self.assertFalse((output_path.parent / "chapter.md.tmp").exists())


if __name__ == "__main__":
    unittest.main()
