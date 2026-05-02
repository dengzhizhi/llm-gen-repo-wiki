#!/usr/bin/env python3
"""Append wiki-update add/edit records to llm-gen-wiki/log.md."""

import json
import sys
from datetime import date

from compute_docs import DOCUMENTS_PATH, WIKI_DIR, PlanError, build_documents, parse_plan


LOG_PATH = WIKI_DIR / "log.md"
LOG_HEADER = "# Wiki Generation Log\n\n<!-- append-only: newest entries at bottom -->\n\n"
LOG_TITLE = "# Wiki Generation Log\n"
LOG_COMMENT = "<!-- append-only: newest entries at bottom -->"


def usage():
    print(
        "Usage:\n"
        "  python3 append_log.py add <topic-id>\n"
        "  python3 append_log.py edit <topic-id> [<topic-id> ...]",
        file=sys.stderr,
    )


def documents_for_topics(plan, topic_ids):
    documents = load_documents(plan)
    selected = set(topic_ids)
    return [
        document
        for document in documents
        if document.get("topic_id") in selected
        or document.get("parent_topic_id") in selected
    ]


def load_documents(plan):
    if DOCUMENTS_PATH.exists():
        return json.loads(DOCUMENTS_PATH.read_text())
    documents = build_documents(plan)
    WIKI_DIR.mkdir(exist_ok=True)
    DOCUMENTS_PATH.write_text(json.dumps(documents, indent=2) + "\n")
    return documents


def topic_map(plan):
    return {topic.get("id", ""): topic for topic in plan.get("topics", [])}


def validate_topic_ids(plan, mode, topic_ids):
    if mode == "add" and len(topic_ids) != 1:
        raise PlanError("Add mode requires exactly one topic id")
    topics_by_id = topic_map(plan)
    unknown = [topic_id for topic_id in topic_ids if topic_id not in topics_by_id]
    if unknown:
        raise PlanError(f"Unknown topic id(s): {', '.join(unknown)}")
    return [topics_by_id[topic_id] for topic_id in topic_ids]


def file_count(topics):
    return sum(len(topic.get("relevant_files", [])) for topic in topics)


def render_add_entry(plan, topics, documents):
    topic = topics[0]
    return "\n".join(
        [
            f"## {date.today().isoformat()} Added topic: {topic.get('title', '')}",
            "",
            f"- New documents: {len(documents)}",
            f"- Total topics in plan: {len(plan.get('topics', []))}",
            f"- Files referenced: {file_count(topics)}",
            "- Plan: llm-gen-wiki/plan.yml",
            "",
        ]
    )


def render_edit_entry(plan, topics, documents):
    if len(topics) == 1:
        topic = topics[0]
        return "\n".join(
            [
                f"## {date.today().isoformat()} Updated topic: {topic.get('title', '')}",
                "",
                f"- Regenerated documents: {len(documents)}",
                f"- Total topics in plan: {len(plan.get('topics', []))}",
                f"- Files referenced: {file_count(topics)}",
                "- Plan: llm-gen-wiki/plan.yml",
                "",
            ]
        )
    titles = ", ".join(topic.get("title", "") for topic in topics)
    return "\n".join(
        [
            f"## {date.today().isoformat()} Updated topics: {titles}",
            "",
            f"- Regenerated documents: {len(documents)}",
            f"- Total topics in plan: {len(plan.get('topics', []))}",
            "- Plan: llm-gen-wiki/plan.yml",
            "",
        ]
    )


def normalize_log_content(content):
    if content.startswith(LOG_HEADER):
        return content
    if content.startswith(LOG_TITLE):
        body = content[len(LOG_TITLE) :].lstrip()
        if body.startswith(LOG_COMMENT):
            body = body[len(LOG_COMMENT) :].lstrip()
        return LOG_HEADER + body
    return LOG_HEADER + content.lstrip()


def append_entry(entry):
    WIKI_DIR.mkdir(exist_ok=True)
    if LOG_PATH.exists():
        content = normalize_log_content(LOG_PATH.read_text())
        separator = "" if content.endswith("\n") else "\n"
        LOG_PATH.write_text(content + separator + entry)
    else:
        LOG_PATH.write_text(LOG_HEADER + entry)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) < 2 or argv[0] not in {"add", "edit"}:
        usage()
        return 2

    mode = argv[0]
    topic_ids = argv[1:]
    try:
        plan = parse_plan()
        topics = validate_topic_ids(plan, mode, topic_ids)
        documents = documents_for_topics(plan, topic_ids)
        if mode == "add":
            entry = render_add_entry(plan, topics, documents)
        else:
            entry = render_edit_entry(plan, topics, documents)
        append_entry(entry)
        print(f"Updated {LOG_PATH}")
        return 0
    except PlanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
