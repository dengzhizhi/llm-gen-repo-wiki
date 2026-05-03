import importlib.util
import json
import os
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


SCAN_DETAIL = load_module("skills/wiki-plan/scan_detail.py", "scan_detail")


def write_lines(path: Path, n: int, line_template: str = "line {i}\n"):
    path.write_text("".join(line_template.format(i=i) for i in range(n)))


class LineCountTest(unittest.TestCase):
    def test_counts_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("a\nb\nc\n")
            tmp = f.name
        try:
            self.assertEqual(SCAN_DETAIL.line_count(tmp), 3)
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_zero(self):
        self.assertEqual(SCAN_DETAIL.line_count("/nonexistent/path.py"), 0)


class ReadFullTest(unittest.TestCase):
    def test_reads_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("hello world\n")
            tmp = f.name
        try:
            content = SCAN_DETAIL.read_full(tmp)
            self.assertEqual(content, "hello world\n")
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_empty_string(self):
        self.assertEqual(SCAN_DETAIL.read_full("/nonexistent/path.py"), "")


class ExtractSignaturesTest(unittest.TestCase):
    def _tmpfile(self, content: str, suffix: str = ".py") -> str:
        with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as f:
            f.write(content)
            return f.name

    def tearDown(self):
        # Cleanup handled per test; nothing to do globally
        pass

    def test_python_class_and_def(self):
        tmp = self._tmpfile(
            "class Foo:\n"
            "    def bar(self):\n"
            "        pass\n"
            "async def baz():\n"
            "    pass\n"
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "python")
            self.assertIn("class Foo:", sigs)
            self.assertIn("    def bar(self):", sigs)
            self.assertIn("async def baz():", sigs)
        finally:
            os.unlink(tmp)

    def test_typescript_export_and_interface(self):
        tmp = self._tmpfile(
            "export function greet(name: string): void {}\n"
            "interface Config { key: string; }\n"
            "const VERSION = '1.0';\n"
            "type ID = number;\n",
            suffix=".ts",
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "typescript")
            self.assertTrue(any("export function greet" in s for s in sigs))
            self.assertTrue(any("interface Config" in s for s in sigs))
            self.assertTrue(any("type ID" in s for s in sigs))
        finally:
            os.unlink(tmp)

    def test_go_func_and_type(self):
        tmp = self._tmpfile(
            "type Server struct {\n"
            "    port int\n"
            "}\n"
            "func (s *Server) Start() error {\n"
            "    return nil\n"
            "}\n",
            suffix=".go",
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "go")
            self.assertTrue(any("type Server struct" in s for s in sigs))
            self.assertTrue(any("func (s *Server) Start()" in s for s in sigs))
        finally:
            os.unlink(tmp)

    def test_java_public_class(self):
        # Java pattern matches lines starting at column 0 (top-level declarations only).
        # Indented class members are not captured because they don't start with the keywords.
        tmp = self._tmpfile(
            "public class UserService {\n"
            "    private String name;\n"
            "    public void save() {}\n"
            "}\n"
            "interface Repo {}\n",
            suffix=".java",
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "java")
            self.assertTrue(any("public class UserService" in s for s in sigs))
            self.assertTrue(any("interface Repo" in s for s in sigs))
            # Indented members do not match the top-level pattern
            self.assertFalse(any("private String name" in s for s in sigs))
        finally:
            os.unlink(tmp)

    def test_rust_pub_fn_and_struct(self):
        tmp = self._tmpfile(
            "pub struct Config {\n"
            "    pub timeout: u64,\n"
            "}\n"
            "pub fn parse(input: &str) -> Config {\n"
            "    todo!()\n"
            "}\n"
            "fn internal() {}\n",
            suffix=".rs",
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "rust")
            sig_text = " ".join(sigs)
            self.assertIn("pub struct Config", sig_text)
            self.assertIn("pub fn parse", sig_text)
        finally:
            os.unlink(tmp)

    def test_generic_fallback(self):
        tmp = self._tmpfile(
            "class MyClass:\n"
            "    pass\n"
            "function helper() {\n"
            "    return 1;\n"
            "}\n",
            suffix=".rb",
        )
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "generic")
            self.assertTrue(any("class MyClass" in s for s in sigs))
            self.assertTrue(any("function helper" in s for s in sigs))
        finally:
            os.unlink(tmp)

    def test_deduplicates_signatures(self):
        content = "def foo():\n    pass\ndef foo():\n    pass\n"
        tmp = self._tmpfile(content)
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "python")
            self.assertEqual(sigs.count("def foo():"), 1)
        finally:
            os.unlink(tmp)

    def test_caps_at_60_signatures(self):
        lines = "".join(f"def fn_{i}():\n    pass\n" for i in range(80))
        tmp = self._tmpfile(lines)
        try:
            sigs = SCAN_DETAIL.extract_signatures(tmp, "python")
            self.assertLessEqual(len(sigs), 60)
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_empty(self):
        sigs = SCAN_DETAIL.extract_signatures("/nonexistent/file.py", "python")
        self.assertEqual(sigs, [])


class AnalyzeFileTest(unittest.TestCase):
    def _create_file(self, tmpdir: Path, name: str, n_lines: int) -> Path:
        p = tmpdir / name
        write_lines(p, n_lines)
        return p

    def test_strategy_full_for_small_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = self._create_file(Path(tmpdir), "small.py", 50)
            result = SCAN_DETAIL.analyze_file(str(f), "python")
        self.assertEqual(result["strategy"], "full")
        self.assertIn("content", result)
        self.assertEqual(result["lines"], 50)

    def test_strategy_full_at_boundary_150(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = self._create_file(Path(tmpdir), "boundary.py", 150)
            result = SCAN_DETAIL.analyze_file(str(f), "python")
        self.assertEqual(result["strategy"], "full")

    def test_strategy_signatures_for_medium_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            p = Path(tmpdir) / "medium.py"
            lines = "".join(
                f"def fn_{i}():\n    pass\n" if i % 5 == 0 else f"    x = {i}\n"
                for i in range(200)
            )
            p.write_text(lines)
            result = SCAN_DETAIL.analyze_file(str(p), "python")
        self.assertEqual(result["strategy"], "signatures")
        self.assertIn("signatures", result)
        self.assertNotIn("content", result)

    def test_strategy_signatures_at_boundary_151(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = self._create_file(Path(tmpdir), "over_boundary.py", 151)
            result = SCAN_DETAIL.analyze_file(str(f), "python")
        self.assertEqual(result["strategy"], "signatures")

    def test_strategy_signatures_only_for_large_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = self._create_file(Path(tmpdir), "large.py", 600)
            result = SCAN_DETAIL.analyze_file(str(f), "python")
        self.assertEqual(result["strategy"], "signatures_only")
        self.assertIn("signatures", result)
        self.assertIn("note", result)
        self.assertNotIn("content", result)

    def test_strategy_signatures_only_at_boundary_501(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            f = self._create_file(Path(tmpdir), "just_over.py", 501)
            result = SCAN_DETAIL.analyze_file(str(f), "python")
        self.assertEqual(result["strategy"], "signatures_only")

    def test_empty_file_returns_empty_strategy(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            tmp = f.name
        try:
            result = SCAN_DETAIL.analyze_file(tmp, "python")
            self.assertEqual(result["strategy"], "empty")
        finally:
            os.unlink(tmp)


class MainIntegrationTest(unittest.TestCase):
    """Integration test for scan_detail.main() with a populated temp directory."""

    def test_main_writes_scan_detail_json(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            wiki_dir = tmp_path / "llm-gen-wiki"
            wiki_dir.mkdir()

            meta = {"detected_language": "python"}
            (wiki_dir / "scan_meta.json").write_text(json.dumps(meta))

            small_py = tmp_path / "small.py"
            small_py.write_text("def hello():\n    pass\n")

            medium_py = tmp_path / "medium.py"
            write_lines(medium_py, 200)

            large_py = tmp_path / "large.py"
            write_lines(large_py, 600)

            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                with patch(
                    "sys.argv",
                    ["scan_detail.py", str(small_py), str(medium_py), str(large_py)],
                ):
                    SCAN_DETAIL.main()

                output = json.loads((wiki_dir / "scan_detail.json").read_text())
                self.assertEqual(output["language"], "python")
                files = output["files"]
                self.assertEqual(files[str(small_py)]["strategy"], "full")
                self.assertEqual(files[str(medium_py)]["strategy"], "signatures")
                self.assertEqual(files[str(large_py)]["strategy"], "signatures_only")
            finally:
                os.chdir(original_cwd)

    def test_main_marks_missing_file_as_not_found(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            wiki_dir = tmp_path / "llm-gen-wiki"
            wiki_dir.mkdir()
            (wiki_dir / "scan_meta.json").write_text(json.dumps({"detected_language": "python"}))

            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                with patch(
                    "sys.argv",
                    ["scan_detail.py", "/nonexistent/file.py"],
                ):
                    SCAN_DETAIL.main()

                output = json.loads((wiki_dir / "scan_detail.json").read_text())
                self.assertEqual(output["files"]["/nonexistent/file.py"]["strategy"], "not_found")
            finally:
                os.chdir(original_cwd)

    def test_main_falls_back_to_generic_when_no_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "llm-gen-wiki").mkdir()

            small_py = tmp_path / "tiny.py"
            small_py.write_text("def x(): pass\n")

            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                with patch("sys.argv", ["scan_detail.py", str(small_py)]):
                    SCAN_DETAIL.main()

                output = json.loads(
                    (tmp_path / "llm-gen-wiki/scan_detail.json").read_text()
                )
                self.assertEqual(output["language"], "generic")
            finally:
                os.chdir(original_cwd)

    def test_main_exits_when_no_files_given(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "llm-gen-wiki").mkdir()
            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                with patch("sys.argv", ["scan_detail.py"]):
                    with self.assertRaises(SystemExit):
                        SCAN_DETAIL.main()
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
