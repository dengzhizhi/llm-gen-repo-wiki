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


VALIDATE = load_module(
    "skills/wiki-write-topic/validate_mermaid_blocks.py",
    "validate_mermaid_blocks",
)


class ExtractMermaidBlocksTest(unittest.TestCase):
    def test_extracts_multiple_mermaid_blocks_and_ignores_other_fences(self):
        markdown = """# Title

```mermaid
graph TD
A["Start"] --> B["End"]
```

```python
print("ignore")
```

```mermaid
sequenceDiagram
participant A
participant B
A->>B: Ping
```
"""

        blocks = VALIDATE.extract_mermaid_blocks(markdown)

        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["index"], 1)
        self.assertIn("graph TD", blocks[0]["source"])
        self.assertEqual(blocks[1]["index"], 2)
        self.assertIn("sequenceDiagram", blocks[1]["source"])

    def test_whitespace_only_markdown_extracts_zero_blocks(self):
        blocks = VALIDATE.extract_mermaid_blocks(" \n\t\n")
        self.assertEqual(blocks, [])

    def test_unterminated_mermaid_fence_is_ignored_deterministically(self):
        markdown = "```mermaid\ngraph TD\nA-->B\n"
        blocks = VALIDATE.extract_mermaid_blocks(markdown)
        self.assertEqual(len(blocks), 1)
        self.assertTrue(blocks[0]["unterminated"])
        self.assertIn("graph TD", blocks[0]["source"])


class ValidateOutputShapeTest(unittest.TestCase):
    def test_no_mermaid_blocks_returns_terse_success(self):
        result = VALIDATE.format_success(block_count=0)
        self.assertEqual(result, "ok mermaid_blocks=0")

    def test_all_passing_blocks_return_terse_success(self):
        result = VALIDATE.format_success(block_count=3)
        self.assertEqual(result, "ok mermaid_blocks=3")

    def test_formats_only_failed_blocks_in_failure_output(self):
        failures = [
            {
                "index": 2,
                "line_start": 10,
                "line_end": 14,
                "source": 'graph TD\nA["bad"] -->',
                "error": "Parse error on line 2",
            }
        ]

        rendered = VALIDATE.format_failures(failures)

        self.assertIn("fail mermaid_blocks=1", rendered)
        self.assertIn("block_index=2", rendered)
        self.assertIn("line_range=10-14", rendered)
        self.assertIn("source:", rendered)
        self.assertIn('A["bad"] -->', rendered)
        self.assertIn("error:", rendered)
        self.assertIn("Parse error on line 2", rendered)


class ValidateMarkdownFileEdgeCasesTest(unittest.TestCase):
    def test_whitespace_only_markdown_returns_zero_block_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_text(" \n\t\n")

            exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertEqual(exit_code, 0)
        self.assertEqual(output, "ok mermaid_blocks=0")

    def test_unreadable_input_returns_controlled_failure(self):
        missing_path = Path("/tmp/does-not-exist-chapter.md")

        exit_code, output = VALIDATE.validate_markdown_file(missing_path)

        self.assertNotEqual(exit_code, 0)
        self.assertIn("error", output.lower())

    def test_invalid_utf8_input_returns_controlled_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_bytes(b"\xff\xfe\xfd")

            exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertNotEqual(exit_code, 0)
        self.assertIn("error", output.lower())

    def test_missing_mmdc_returns_controlled_failure(self):
        markdown = """```mermaid
graph TD
A-->B
```"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_text(markdown)
            with mock.patch.object(
                VALIDATE.subprocess, "run", side_effect=FileNotFoundError("mmdc not found")
            ):
                exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertNotEqual(exit_code, 0)
        self.assertIn("mmdc", output)

    def test_validates_all_blocks_and_reports_only_failures(self):
        markdown = """```mermaid
graph TD
A-->B
```

```mermaid
graph TD
A-->
```"""

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_text(markdown)

            def fake_run(cmd, capture_output, text):
                input_path = Path(cmd[2])
                source = input_path.read_text()
                if "A-->" in source and "A-->B" not in source:
                    return mock.Mock(returncode=1, stderr="Parse error")
                return mock.Mock(returncode=0, stderr="", stdout="")

            with mock.patch.object(VALIDATE.subprocess, "run", side_effect=fake_run):
                exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertEqual(exit_code, 1)
        self.assertIn("block_index=2", output)
        self.assertNotIn("block_index=1", output)

    def test_unterminated_mermaid_fence_returns_controlled_failure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_text("```mermaid\ngraph TD\nA-->B\n")

            exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertEqual(exit_code, 1)
        self.assertIn("unterminated", output.lower())
        self.assertIn("block_index=1", output)

    def test_empty_mermaid_block_reports_forward_line_range(self):
        markdown = "```mermaid\n```"

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "chapter.md"
            path.write_text(markdown)

            def fake_run(cmd, capture_output, text):
                return mock.Mock(returncode=1, stderr="Empty diagram")

            with mock.patch.object(VALIDATE.subprocess, "run", side_effect=fake_run):
                exit_code, output = VALIDATE.validate_markdown_file(path)

        self.assertEqual(exit_code, 1)
        self.assertIn("line_range=2-2", output)


class ValidateMainTest(unittest.TestCase):
    def test_main_requires_exactly_one_path_argument(self):
        with mock.patch("builtins.print") as fake_print:
            exit_code = VALIDATE.main([])

        self.assertEqual(exit_code, 2)
        fake_print.assert_called_once()


if __name__ == "__main__":
    unittest.main()
