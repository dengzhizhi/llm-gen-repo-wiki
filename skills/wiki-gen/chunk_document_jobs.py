#!/usr/bin/env python3
"""Chunk document jobs into capped concurrent waves."""

import json
import sys
from pathlib import Path


def chunk_jobs(jobs, wave_size=6):
    return [jobs[index:index + wave_size] for index in range(0, len(jobs), wave_size)]


def render_chunked_jobs(input_path: Path, wave_size=6):
    jobs = json.loads(input_path.read_text())
    return json.dumps(chunk_jobs(jobs, wave_size=wave_size), indent=2)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: chunk_document_jobs.py /absolute/path/to/jobs.json")
        return 2
    print(render_chunked_jobs(Path(argv[0])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
