#!/usr/bin/env python3
"""Append a wiki generation record to llm-gen-wiki/log.md."""

import json
import sys
from datetime import date

from compute_docs import DOCUMENTS_PATH, WIKI_DIR, PlanError, build_documents, parse_plan


LOG_PATH = WIKI_DIR / "log.md"
LOG_HEADER = "# Wiki Generation Log\n\n<!-- append-only: newest entries at bottom -->\n\n"


def document_count(plan):
    if DOCUMENTS_PATH.exists():
        return len(json.loads(DOCUMENTS_PATH.read_text()))
    return len(build_documents(plan))


def render_entry(plan, total_documents):
    topics = plan.get("topics", [])
    topics_with_subtopics = sum(1 for topic in topics if topic.get("subtopics", []))
    return "\n".join(
        [
            f"## {date.today().isoformat()} Generation run",
            "",
            (
                f"- Topics: {len(topics)} ({topics_with_subtopics} with subtopics → "
                f"{total_documents} documents total)"
            ),
            "- Cross-references: none (run /wiki-crossref to add)",
            "- Plan: llm-gen-wiki/plan.yml",
            "",
        ]
    )


def main():
    try:
        plan = parse_plan()
        total_documents = document_count(plan)
        WIKI_DIR.mkdir(exist_ok=True)
        entry = render_entry(plan, total_documents)
        if LOG_PATH.exists():
            content = LOG_PATH.read_text()
            if not content.startswith("# Wiki Generation Log\n"):
                content = LOG_HEADER + content
            separator = "" if content.endswith("\n") else "\n"
            LOG_PATH.write_text(content + separator + entry)
        else:
            LOG_PATH.write_text(LOG_HEADER + entry)
        print(f"Updated {LOG_PATH}")
    except PlanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
