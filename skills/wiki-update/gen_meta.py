#!/usr/bin/env python3
"""Generate llm-gen-wiki/meta.yml from git repository metadata."""

import argparse
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return result.stdout.strip()


def normalize_origin_url(raw):
    if not raw:
        return ""
    url = raw.strip()
    # Convert SSH to HTTPS
    ssh_match = re.match(r"git@([^:]+):(.+)", url)
    if ssh_match:
        host, path = ssh_match.group(1), ssh_match.group(2)
        url = f"https://{host}/{path}"
    # Strip trailing .git
    if url.endswith(".git"):
        url = url[:-4]
    return url


def derive_repo_type(origin_url):
    if not origin_url:
        return "unknown"
    if "github.com" in origin_url:
        return "github"
    if "bitbucket.org" in origin_url:
        return "bitbucket"
    return "unknown"


def derive_scope_prefix(git_root, cwd):
    git_root_path = Path(git_root).resolve()
    cwd_path = Path(cwd).resolve()
    if git_root_path == cwd_path:
        return ""
    try:
        return str(cwd_path.relative_to(git_root_path))
    except ValueError:
        return ""


def write_meta(cwd, language):
    cwd = str(Path(cwd).resolve())

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    branch = run("git branch --show-current")
    commit_hash = run("git rev-parse HEAD")
    raw_remote = run("git remote get-url origin 2>/dev/null")
    git_root = run("git rev-parse --show-toplevel")

    origin_url = normalize_origin_url(raw_remote)
    repo_type = derive_repo_type(origin_url)
    scope_prefix = derive_scope_prefix(git_root, cwd)

    output_dir = Path(cwd) / "llm-gen-wiki"
    output_dir.mkdir(exist_ok=True)
    meta_path = output_dir / "meta.yml"

    meta_content = f"""generated_at: "{generated_at}"
branch: "{branch}"
commit_hash: "{commit_hash}"
origin_url: "{origin_url}"
repo_type: "{repo_type}"
scope_prefix: "{scope_prefix}"
language: "{language}"
"""

    meta_path.write_text(meta_content)
    return meta_path


def parse_args(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--language",
        default="English",
        help="Human-readable wiki language written into meta.yml.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    meta_path = write_meta(os.getcwd(), args.language)
    print(f"Wrote {meta_path}")


if __name__ == "__main__":
    main()
