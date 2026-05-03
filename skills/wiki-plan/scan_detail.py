#!/usr/bin/env python3
"""
Phase B targeted scan for the wiki-plan skill.

Given the file paths the model identified as relevant to candidate topics
(selected after reading scan_meta.json), reads or extracts signatures for
each file based on size. The model decides what to pass; this script decides
how to read it.

  ≤ 150 lines  → full content included (no Read tool call needed)
  151-500 lines → language-specific signature extraction
  > 500 lines   → signature extraction only + note for writer subagent

Reads llm-gen-wiki/scan_meta.json for the detected language.
Writes llm-gen-wiki/scan_detail.json.
Run from the repository root being documented.
Usage: python3 scan_detail.py <file1> <file2> ...
"""

import argparse
import json
import re
import sys
from pathlib import Path

WIKI_DIR = Path("llm-gen-wiki")
META_PATH = WIKI_DIR / "scan_meta.json"
OUTPUT_PATH = WIKI_DIR / "scan_detail.json"

SIGNATURE_PATTERNS = {
    "python":     r"^(class |def |async def |    def )",
    "javascript": r"^(export |class |function |const \w+ =|interface |type )",
    "typescript": r"^(export |class |function |const \w+ =|interface |type )",
    "go":         r"^(type |func )",
    "java":       r"^(public |private |protected |class |interface )",
    "kotlin":     r"^(class |fun |suspend fun |interface |object |data class )",
    "rust":       r"^(pub |fn |struct |enum |trait |impl )",
    "generic":    r"^(class |def |func |function |export |pub )",
}


def line_count(path):
    try:
        with open(path, errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def read_full(path):
    try:
        return Path(path).read_text(errors="replace")
    except OSError:
        return ""


def extract_signatures(path, language):
    pattern = SIGNATURE_PATTERNS.get(language, SIGNATURE_PATTERNS["generic"])
    sigs = []
    try:
        with open(path, errors="replace") as f:
            for line in f:
                if re.match(pattern, line):
                    s = line.rstrip()
                    if s not in sigs:
                        sigs.append(s)
                    if len(sigs) >= 60:
                        break
    except OSError:
        pass
    return sigs


def analyze_file(path, language):
    n = line_count(path)
    if n == 0:
        return {"lines": 0, "strategy": "empty"}

    if n <= 150:
        return {
            "lines": n,
            "strategy": "full",
            "content": read_full(path),
        }
    elif n <= 500:
        return {
            "lines": n,
            "strategy": "signatures",
            "signatures": extract_signatures(path, language),
        }
    else:
        return {
            "lines": n,
            "strategy": "signatures_only",
            "signatures": extract_signatures(path, language),
            "note": (
                f"File has {n} lines — too large for full read during planning. "
                "If this file is central to a topic, add it to that topic's "
                "open_questions so the writer subagent reads it in full."
            ),
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="*", help="File paths to analyse (relative to cwd)")
    args = parser.parse_args()

    file_paths = args.files
    if not file_paths:
        print("No files specified. Pass file paths as arguments.", file=sys.stderr)
        sys.exit(1)

    # Read language from scan_meta.json
    language = "generic"
    if META_PATH.exists():
        try:
            meta = json.loads(META_PATH.read_text())
            language = meta.get("detected_language", "generic")
        except Exception:
            pass

    results = {}
    for path in file_paths:
        if Path(path).exists():
            results[path] = analyze_file(path, language)
        else:
            results[path] = {"lines": 0, "strategy": "not_found"}

    output = {
        "language": language,
        "files": results,
    }

    WIKI_DIR.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    strategies = {}
    for v in results.values():
        s = v.get("strategy", "unknown")
        strategies[s] = strategies.get(s, 0) + 1

    print(f"Wrote {OUTPUT_PATH}")
    print(f"  {len(results)} files analysed: {strategies}")


if __name__ == "__main__":
    main()
