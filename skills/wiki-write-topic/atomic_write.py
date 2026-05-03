#!/usr/bin/env python3
"""Atomic file writing helper for wiki chapter output."""

import os
from pathlib import Path


def write_text_atomically(output_path, content):
    output_path = Path(output_path)
    if content == "":
        raise ValueError("content must be non-empty")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(output_path.name + ".tmp")
    temp_path.write_text(content)
    try:
        os.replace(temp_path, output_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
