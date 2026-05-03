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


SCAN_META = load_module("skills/wiki-plan/scan_meta.py", "scan_meta")


class ShouldSkipTest(unittest.TestCase):
    def test_skips_known_noise_dirs(self):
        for name in ("node_modules", ".git", "target", "dist", "build", "__pycache__"):
            self.assertTrue(SCAN_META.should_skip(name), f"Expected {name!r} to be skipped")

    def test_skips_egg_info(self):
        self.assertTrue(SCAN_META.should_skip("mypackage.egg-info"))

    def test_does_not_skip_src(self):
        self.assertFalse(SCAN_META.should_skip("src"))

    def test_does_not_skip_tests(self):
        self.assertFalse(SCAN_META.should_skip("tests"))

    def test_does_not_skip_skills(self):
        self.assertFalse(SCAN_META.should_skip("skills"))


class DetectLanguageTest(unittest.TestCase):
    def test_detects_typescript(self):
        self.assertEqual(SCAN_META.detect_language({"tsconfig.json", "package.json"}), "typescript")

    def test_detects_javascript_when_no_tsconfig(self):
        self.assertEqual(SCAN_META.detect_language({"package.json", "index.js"}), "javascript")

    def test_detects_python_from_pyproject(self):
        self.assertEqual(SCAN_META.detect_language({"pyproject.toml", "README.md"}), "python")

    def test_detects_python_from_setup_py(self):
        self.assertEqual(SCAN_META.detect_language({"setup.py"}), "python")

    def test_detects_go(self):
        self.assertEqual(SCAN_META.detect_language({"go.mod", "main.go"}), "go")

    def test_detects_rust(self):
        self.assertEqual(SCAN_META.detect_language({"Cargo.toml"}), "rust")

    def test_detects_java(self):
        self.assertEqual(SCAN_META.detect_language({"pom.xml"}), "java")

    def test_detects_kotlin(self):
        self.assertEqual(SCAN_META.detect_language({"build.gradle.kts"}), "kotlin")

    def test_unknown_when_no_manifest(self):
        self.assertEqual(SCAN_META.detect_language({"README.md", "Makefile"}), "unknown")


class LineCountTest(unittest.TestCase):
    def test_counts_lines(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("line1\nline2\nline3\n")
            tmp = f.name
        try:
            self.assertEqual(SCAN_META.line_count(tmp), 3)
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_zero(self):
        self.assertEqual(SCAN_META.line_count("/nonexistent/path/file.py"), 0)

    def test_empty_file_returns_zero(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            tmp = f.name
        try:
            self.assertEqual(SCAN_META.line_count(tmp), 0)
        finally:
            os.unlink(tmp)


class ReadFileTest(unittest.TestCase):
    def test_reads_content(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as f:
            f.write("# Hello\nworld\n")
            tmp = f.name
        try:
            content = SCAN_META.read_file(tmp)
            self.assertIn("# Hello", content)
            self.assertIn("world", content)
        finally:
            os.unlink(tmp)

    def test_truncates_at_200_lines(self):
        lines = [f"line{i}\n" for i in range(300)]
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.writelines(lines)
            tmp = f.name
        try:
            content = SCAN_META.read_file(tmp)
            self.assertIn("truncated", content)
            result_lines = content.splitlines()
            self.assertLessEqual(len(result_lines), 201)
        finally:
            os.unlink(tmp)

    def test_missing_file_returns_empty_string(self):
        content = SCAN_META.read_file("/nonexistent/file.md")
        self.assertEqual(content, "")


class SelectKeyFilesTest(unittest.TestCase):
    def test_selects_manifest(self):
        selected = SCAN_META.select_key_files({"pyproject.toml", "main.py", "Makefile"})
        self.assertIn("pyproject.toml", selected)

    def test_selects_entry_point(self):
        selected = SCAN_META.select_key_files({"main.py", "Makefile"})
        self.assertIn("main.py", selected)

    def test_selects_deploy_config(self):
        selected = SCAN_META.select_key_files({"Makefile"})
        self.assertIn("Makefile", selected)

    def test_selects_at_most_five(self):
        all_names = {
            "package.json", "pyproject.toml", "Cargo.toml",
            "main.py", "app.py", "index.ts", "docker-compose.yml",
        }
        selected = SCAN_META.select_key_files(all_names)
        self.assertLessEqual(len(selected), 5)

    def test_no_duplicates_across_categories(self):
        selected = SCAN_META.select_key_files({"package.json", "index.js", "docker-compose.yml"})
        self.assertEqual(len(selected), len(set(selected)))

    def test_empty_root_returns_empty(self):
        selected = SCAN_META.select_key_files(set())
        self.assertEqual(selected, [])


class GitActivityTest(unittest.TestCase):
    def test_parses_commit_log(self):
        fake_log = "\nauth.py\nauth.py\nmodels.py\nauth.py\nmodels.py\n"
        with patch.object(SCAN_META, "run", return_value=fake_log):
            activity = SCAN_META.git_activity()
        paths = [item["path"] for item in activity]
        self.assertEqual(paths[0], "auth.py")
        self.assertEqual(activity[0]["commits"], 3)
        self.assertEqual(activity[1]["commits"], 2)

    def test_returns_at_most_40(self):
        lines = [f"file{i}.py\n" for i in range(100)]
        fake_log = "\n".join(lines)
        with patch.object(SCAN_META, "run", return_value=fake_log):
            activity = SCAN_META.git_activity()
        self.assertLessEqual(len(activity), 40)

    def test_empty_log_returns_empty_list(self):
        with patch.object(SCAN_META, "run", return_value=""):
            activity = SCAN_META.git_activity()
        self.assertEqual(activity, [])


class BfsExploreTest(unittest.TestCase):
    def _make_ls_tree_line(self, etype, path):
        mode = "040000" if etype == "tree" else "100644"
        return f"{mode} {etype} abc1234\t{path}"

    def test_discovers_files_and_dirs(self):
        root_output = "\n".join([
            self._make_ls_tree_line("blob", "README.md"),
            self._make_ls_tree_line("tree", "src"),
        ])
        src_output = "\n".join([
            self._make_ls_tree_line("blob", "src/main.py"),
        ])

        def fake_run(cmd):
            if "src/" in cmd:
                return src_output
            return root_output

        with patch.object(SCAN_META, "run", side_effect=fake_run):
            entries, root_names = SCAN_META.bfs_explore("", depth_cap=5)

        paths = [e["path"] for e in entries]
        self.assertIn("README.md", paths)
        self.assertIn("src", paths)
        self.assertIn("src/main.py", paths)
        self.assertIn("README.md", root_names)

    def test_skips_node_modules(self):
        root_output = "\n".join([
            self._make_ls_tree_line("blob", "index.js"),
            self._make_ls_tree_line("tree", "node_modules"),
        ])

        def fake_run(cmd):
            return root_output if "node_modules" not in cmd else ""

        with patch.object(SCAN_META, "run", side_effect=fake_run):
            entries, _ = SCAN_META.bfs_explore("", depth_cap=5)

        paths = [e["path"] for e in entries]
        self.assertIn("index.js", paths)
        self.assertNotIn("node_modules", paths)

    def test_returns_empty_on_no_output(self):
        with patch.object(SCAN_META, "run", return_value=""):
            entries, root_names = SCAN_META.bfs_explore("", depth_cap=5)
        self.assertEqual(entries, [])
        self.assertEqual(root_names, set())

    def test_pass_through_dirs_do_not_consume_depth(self):
        # src/ has only a subdir (no files) → pass-through.
        # src/core/ has actual files.
        # With depth_cap=1, the old behaviour would stop at src/ and never
        # reach src/core/. The new behaviour folds src/ into the same depth
        # level, so src/core/engine.py is discovered within depth_cap=1.
        root_output = self._make_ls_tree_line("tree", "src")
        src_output = self._make_ls_tree_line("tree", "src/core")
        core_output = self._make_ls_tree_line("blob", "src/core/engine.py")

        def fake_run(cmd):
            if "src/core/" in cmd:
                return core_output
            if "src/" in cmd:
                return src_output
            return root_output

        with patch.object(SCAN_META, "run", side_effect=fake_run):
            entries, _ = SCAN_META.bfs_explore("", depth_cap=1)

        paths = [e["path"] for e in entries]
        self.assertIn("src/core/engine.py", paths)

    def test_dir_with_files_and_subdirs_is_not_pass_through(self):
        # src/ has both a file and a subdir — it is NOT pass-through.
        # Its subdir (src/util) should be deferred to the next depth level,
        # so with depth_cap=1 it will not be explored.
        root_output = self._make_ls_tree_line("tree", "src")
        src_output = "\n".join([
            self._make_ls_tree_line("blob", "src/app.py"),
            self._make_ls_tree_line("tree", "src/util"),
        ])
        util_output = self._make_ls_tree_line("blob", "src/util/helper.py")

        def fake_run(cmd):
            if "src/util/" in cmd:
                return util_output
            if "src/" in cmd:
                return src_output
            return root_output

        with patch.object(SCAN_META, "run", side_effect=fake_run):
            entries, _ = SCAN_META.bfs_explore("", depth_cap=1)

        paths = [e["path"] for e in entries]
        self.assertIn("src/app.py", paths)
        # src/util/helper.py requires depth 2 and must not appear
        self.assertNotIn("src/util/helper.py", paths)


class MainIntegrationTest(unittest.TestCase):
    """Integration test for scan_meta.main() via subprocess with a temp repo."""

    def test_main_writes_scan_meta_json(self):
        import subprocess
        import sys

        script = REPO_ROOT / "skills/wiki-plan/scan_meta.py"

        root_output = "100644 blob abc1234\tREADME.md\n040000 tree abc1234\tsrc\n"
        src_output = "100644 blob abc1234\tsrc/app.py\n"
        log_output = "\nsrc/app.py\nsrc/app.py\nREADME.md\n"

        def fake_run(cmd):
            if "src/" in cmd:
                return src_output
            if "log" in cmd:
                return log_output
            return root_output

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            (tmp_path / "README.md").write_text("# Test repo\n")
            (tmp_path / "src").mkdir()
            (tmp_path / "src/app.py").write_text("def main(): pass\n")

            original_cwd = Path.cwd()
            try:
                os.chdir(tmp_path)
                with patch.object(SCAN_META, "run", side_effect=fake_run):
                    with patch("sys.argv", ["scan_meta.py"]):
                        try:
                            SCAN_META.main()
                        except SystemExit:
                            pass

                output_path = tmp_path / "llm-gen-wiki/scan_meta.json"
                self.assertTrue(output_path.exists(), "scan_meta.json was not written")
                data = json.loads(output_path.read_text())
                self.assertIn("tree", data)
                self.assertIn("file_sizes", data)
                self.assertIn("git_activity", data)
                self.assertIn("detected_language", data)
            finally:
                os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
