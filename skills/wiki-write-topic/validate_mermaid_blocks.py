#!/usr/bin/env python3
"""Validate Mermaid code blocks inside one Markdown document."""

import subprocess
import sys
import tempfile
from pathlib import Path


def extract_mermaid_blocks(markdown_text: str):
    blocks = []
    lines = markdown_text.splitlines()
    in_block = False
    block_lines = []
    line_start = 0
    index = 0
    for lineno, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_block and stripped == "```mermaid":
            in_block = True
            block_lines = []
            line_start = lineno + 1
            continue
        if in_block and stripped == "```":
            index += 1
            blocks.append(
                {
                    "index": index,
                    "line_start": line_start,
                    "line_end": lineno - 1,
                    "source": "\n".join(block_lines),
                }
            )
            in_block = False
            block_lines = []
            continue
        if in_block:
            block_lines.append(line)
    return blocks


def format_success(block_count: int) -> str:
    return f"ok mermaid_blocks={block_count}"


def format_failures(failures) -> str:
    lines = [f"fail mermaid_blocks={len(failures)}"]
    for failure in failures:
        lines.extend(
            [
                f"block_index={failure['index']}",
                f"line_range={failure['line_start']}-{failure['line_end']}",
                "source:",
                failure["source"],
                "error:",
                failure["error"],
            ]
        )
    return "\n".join(lines)


def validate_block_source(source: str):
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        input_path = tmp_path / "diagram.mmd"
        output_path = tmp_path / "diagram.svg"
        input_path.write_text(source)
        try:
            result = subprocess.run(
                ["mmdc", "-i", str(input_path), "-o", str(output_path)],
                capture_output=True,
                text=True,
            )
        except OSError as exc:
            return f"validator_invocation_failed: {exc}"
    if result.returncode == 0:
        return None
    return (result.stderr or result.stdout or "Unknown Mermaid validation error").strip()


def validate_markdown_file(markdown_path: Path):
    try:
        markdown_text = markdown_path.read_text()
    except OSError as exc:
        return 2, f"error reading_markdown path={markdown_path} reason={exc}"
    blocks = extract_mermaid_blocks(markdown_text)
    failures = []
    for block in blocks:
        error = validate_block_source(block["source"])
        if error:
            failures.append({**block, "error": error})
    if failures:
        return 1, format_failures(failures)
    return 0, format_success(len(blocks))


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: validate_mermaid_blocks.py /absolute/path/to/chapter.md")
        return 2
    exit_code, output = validate_markdown_file(Path(argv[0]))
    print(output)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
