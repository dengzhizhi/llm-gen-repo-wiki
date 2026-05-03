#!/usr/bin/env python3
"""
Phase A repository scan for the wiki-plan skill.

BFS tree exploration, file sizing, git activity ranking, and key file reads.
Does NOT read or analyse individual source files beyond the key entry points —
that is deferred to scan_detail.py once the model has identified which files
are relevant to each candidate topic.

Writes llm-gen-wiki/scan_meta.json.
Run from the repository root being documented.
Usage: python3 scan_meta.py [--scope-prefix <prefix>]
"""

import argparse
import json
import os
import subprocess
from pathlib import Path

WIKI_DIR = Path("llm-gen-wiki")
OUTPUT_PATH = WIKI_DIR / "scan_meta.json"

SKIP_DIRS = {
    "node_modules", ".git", ".svn", ".hg", "target", ".terraform",
    "third_party", "dist", "build", "out", ".next", ".nuxt",
    "__pycache__", ".cache", "coverage", ".nyc_output",
    "tmp", "logs", "storybook-static", ".idea", ".vscode",
    ".github", ".circleci", ".husky",
}

LANGUAGE_MANIFESTS = {
    "tsconfig.json":    "typescript",
    "package.json":     "javascript",
    "pyproject.toml":   "python",
    "setup.py":         "python",
    "requirements.txt": "python",
    "Cargo.toml":       "rust",
    "go.mod":           "go",
    "pom.xml":          "java",
    "build.gradle":     "java",
    "build.gradle.kts": "kotlin",
}

DEPTH_CAPS = {"java": 8, "kotlin": 8, "go": 7}

KEY_MANIFESTS = [
    "package.json", "pyproject.toml", "Cargo.toml", "go.mod",
    "pom.xml", "build.gradle", "build.gradle.kts",
]
KEY_ENTRY_POINTS = [
    "main.py", "app.py", "app.ts", "index.ts", "server.py",
    "main.go", "cli.py", "index.js",
]
KEY_DEPLOY_CONFIGS = [
    "docker-compose.yml", "serverless.yml", "Makefile", "application.yml",
]


def run(cmd):
    return subprocess.run(cmd, shell=True, capture_output=True, text=True).stdout


def should_skip(name):
    return name in SKIP_DIRS or name.endswith(".egg-info")


def detect_language(root_names):
    for manifest, lang in LANGUAGE_MANIFESTS.items():
        if manifest in root_names:
            return lang
    return "unknown"


def bfs_explore(scope_prefix, depth_cap, tree_budget=300):
    entries = []
    root_names = set()

    root_cmd = f"git ls-tree HEAD -- {scope_prefix}/" if scope_prefix else "git ls-tree HEAD"
    level_dirs = []

    for line in run(root_cmd).splitlines():
        parts = line.split(None, 3)
        if len(parts) < 4:
            continue
        etype, path = parts[1], parts[3]
        name = Path(path).name
        if etype == "blob":
            root_names.add(name)
            entries.append({"path": path, "type": "file"})
        elif etype == "tree" and not should_skip(name):
            level_dirs.append(path)
            entries.append({"path": path, "type": "dir"})

    tree_count = 0
    for _ in range(depth_cap):
        if not level_dirs or tree_count >= tree_budget:
            break
        batch = " ".join(f"{d}/" for d in level_dirs)
        next_dirs = []
        for line in run(f"git ls-tree HEAD -- {batch}").splitlines():
            parts = line.split(None, 3)
            if len(parts) < 4:
                continue
            etype, path = parts[1], parts[3]
            name = Path(path).name
            if etype == "blob":
                entries.append({"path": path, "type": "file"})
            elif etype == "tree":
                tree_count += 1
                if not should_skip(name):
                    next_dirs.append(path)
                    entries.append({"path": path, "type": "dir"})
        level_dirs = next_dirs
        if tree_count >= tree_budget:
            break

    return entries, root_names


def line_count(path):
    try:
        with open(path, errors="replace") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


def read_file(path, max_lines=200):
    lines = []
    try:
        with open(path, errors="replace") as f:
            for i, line in enumerate(f):
                if i >= max_lines:
                    lines.append("...(truncated at 200 lines)\n")
                    break
                lines.append(line)
    except OSError:
        pass
    return "".join(lines)


def git_activity():
    raw = run('git log --since="6 months ago" --name-only --pretty=format:')
    counts = {}
    for line in raw.splitlines():
        line = line.strip()
        if line:
            counts[line] = counts.get(line, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: -x[1])[:40]
    return [{"path": p, "commits": c} for p, c in ranked]


def select_key_files(root_names):
    selected = []
    for name in KEY_MANIFESTS:
        if name in root_names:
            selected.append(name)
            break
    for name in KEY_ENTRY_POINTS:
        if name in root_names and name not in selected:
            selected.append(name)
            break
    for name in KEY_DEPLOY_CONFIGS:
        if name in root_names and name not in selected:
            selected.append(name)
            break
    return selected[:5]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--scope-prefix", default="")
    args = parser.parse_args()
    scope_prefix = args.scope_prefix.strip("/")

    root_cmd = f"git ls-tree HEAD -- {scope_prefix}/" if scope_prefix else "git ls-tree HEAD"
    quick_root_names = set()
    for line in run(root_cmd).splitlines():
        parts = line.split(None, 3)
        if len(parts) >= 4 and parts[1] == "blob":
            quick_root_names.add(Path(parts[3]).name)

    language = detect_language(quick_root_names)
    if language != "go":
        SKIP_DIRS.add("vendor")

    depth_cap = DEPTH_CAPS.get(language, 5)
    entries, root_names = bfs_explore(scope_prefix, depth_cap)

    file_paths = [e["path"] for e in entries if e["type"] == "file"]
    sizes = {p: line_count(p) for p in file_paths}

    try:
        activity = git_activity()
    except Exception:
        activity = []
    activity_rank = {item["path"]: i + 1 for i, item in enumerate(activity)}
    git_ranks = {p: r for p, r in activity_rank.items() if p in set(file_paths)}

    key_file_names = select_key_files(root_names)
    key_file_contents = {}
    for name in key_file_names:
        content = read_file(name)
        if content:
            key_file_contents[name] = content

    jvm_fallback = []
    if language in ("java", "kotlin"):
        ext = "*.java" if language == "java" else "*.kt"
        if not any(p.endswith((".java", ".kt")) for p in file_paths):
            raw = run(f'git ls-files -- "{ext}"')
            jvm_fallback = [l.strip() for l in raw.splitlines() if l.strip()][:200]

    output = {
        "repo": Path(os.getcwd()).name,
        "detected_language": language,
        "depth_cap_used": depth_cap,
        "tree": entries,
        "file_sizes": sizes,
        "git_activity": activity,
        "git_ranks": git_ranks,
        "key_file_contents": key_file_contents,
        "key_files_read": key_file_names,
        "jvm_source_fallback": jvm_fallback,
    }

    WIKI_DIR.mkdir(exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, ensure_ascii=False))

    n_files = len(file_paths)
    n_dirs = len([e for e in entries if e["type"] == "dir"])
    print(f"Wrote {OUTPUT_PATH}")
    print(f"  {n_dirs} dirs, {n_files} files | language: {language} | depth cap: {depth_cap}")
    print(f"  {len(git_ranks)} git-ranked files | key files: {key_file_names}")
    if jvm_fallback:
        print(f"  JVM fallback: {len(jvm_fallback)} source files")


if __name__ == "__main__":
    main()
