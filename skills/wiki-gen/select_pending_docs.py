#!/usr/bin/env python3
"""Select pending wiki document jobs from llm-gen-wiki/documents.json."""

import json
import sys
from pathlib import Path


def is_complete_output(path_str: str) -> bool:
    path = Path(path_str)
    return path.exists() and path.is_file() and path.stat().st_size > 0


def select_pending_jobs(jobs, force_all=False):
    if force_all:
        return list(jobs)
    return [job for job in jobs if not is_complete_output(job["output_file"])]


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    force_all = "--force-all" in argv
    documents_path = Path("llm-gen-wiki/documents.json")
    jobs = json.loads(documents_path.read_text())
    pending = select_pending_jobs(jobs, force_all=force_all)
    print(json.dumps(pending, indent=2))


if __name__ == "__main__":
    main()
