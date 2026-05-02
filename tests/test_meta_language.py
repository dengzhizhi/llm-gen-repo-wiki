import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


WIKI_GEN_GEN_META = load_module("skills/wiki-gen/gen_meta.py", "wiki_gen_gen_meta")
WIKI_UPDATE_GEN_META = load_module(
    "skills/wiki-update/gen_meta.py", "wiki_update_gen_meta"
)


class MetaLanguageTest(unittest.TestCase):
    def test_wiki_gen_meta_defaults_to_english(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch.object(WIKI_GEN_GEN_META, "run") as run_mock:
                run_mock.side_effect = [
                    "main",
                    "1234567890abcdef1234567890abcdef12345678",
                    "git@example.test/repo.git",
                    str(tmp_path),
                ]
                WIKI_GEN_GEN_META.write_meta(tmp_path, "English")

            meta = (tmp_path / "llm-gen-wiki" / "meta.yml").read_text()

        self.assertIn('language: "English"', meta)
        self.assertIn('branch: "main"', meta)

    def test_wiki_update_meta_writes_human_readable_language(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            with patch.object(WIKI_UPDATE_GEN_META, "run") as run_mock:
                run_mock.side_effect = [
                    "main",
                    "abcdefabcdefabcdefabcdefabcdefabcdefabcd",
                    "git@example.test/repo.git",
                    str(tmp_path),
                ]
                WIKI_UPDATE_GEN_META.write_meta(tmp_path, "Simplified Chinese")

            meta = (tmp_path / "llm-gen-wiki" / "meta.yml").read_text()

        self.assertIn('language: "Simplified Chinese"', meta)
        self.assertIn('repo_type: "unknown"', meta)


if __name__ == "__main__":
    unittest.main()
