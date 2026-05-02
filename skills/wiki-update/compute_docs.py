#!/usr/bin/env python3
"""Compute wiki-update document jobs from llm-gen-wiki/plan.yml."""

import json
import re
import sys
from pathlib import Path


WIKI_DIR = Path("llm-gen-wiki")
PLAN_PATH = WIKI_DIR / "plan.yml"
DOCUMENTS_PATH = WIKI_DIR / "documents.json"
SAFE_KEBAB_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PlanError(ValueError):
    """Raised when plan.yml does not match the expected wiki schema."""


def parse_scalar(value):
    value = value.strip()
    if value == "[]":
        return []
    if value == "":
        return ""
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    if value == "true":
        return True
    if value == "false":
        return False
    return value


def split_key_value(text):
    if ":" not in text:
        return text.strip(), ""
    key, value = text.split(":", 1)
    return key.strip(), parse_scalar(value)


def count_indent(line):
    return len(line) - len(line.lstrip(" "))


def strip_inline_comment(line):
    in_single = False
    in_double = False
    escaped = False
    for index, char in enumerate(line):
        if escaped:
            escaped = False
            continue
        if char == "\\" and in_double:
            escaped = True
            continue
        if char == "'" and not in_double:
            in_single = not in_single
            continue
        if char == '"' and not in_single:
            in_double = not in_double
            continue
        if (
            char == "#"
            and not in_single
            and not in_double
            and (index == 0 or line[index - 1].isspace())
        ):
            return line[:index].rstrip()
    return line.rstrip()


def normalized_lines(text):
    lines = []
    for raw_line in text.splitlines():
        line = strip_inline_comment(raw_line)
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return lines


def parse_string_list(lines, start, indent):
    values = []
    index = start
    while index < len(lines):
        line = lines[index]
        line_indent = count_indent(line)
        stripped = line.strip()
        if line_indent < indent or not stripped.startswith("- "):
            break
        values.append(parse_scalar(stripped[2:]))
        index += 1
    return values, index


def parse_subtopics(lines, start, indent):
    subtopics = []
    index = start
    current = None
    while index < len(lines):
        line = lines[index]
        line_indent = count_indent(line)
        stripped = line.strip()
        if line_indent < indent:
            break
        if line_indent == indent and stripped.startswith("- "):
            current = {}
            subtopics.append(current)
            remainder = stripped[2:].strip()
            if remainder:
                key, value = split_key_value(remainder)
                current[key] = value
            index += 1
            continue
        if current is None or line_indent <= indent:
            break
        key, value = split_key_value(stripped)
        if key == "relevant_files" and value == "":
            current[key], index = parse_string_list(lines, index + 1, line_indent + 2)
            continue
        current[key] = value
        index += 1
    return subtopics, index


def parse_topics(lines, start, indent):
    topics = []
    index = start
    current = None
    while index < len(lines):
        line = lines[index]
        line_indent = count_indent(line)
        stripped = line.strip()
        if line_indent < indent:
            break
        if line_indent == indent and stripped.startswith("- "):
            current = {}
            topics.append(current)
            remainder = stripped[2:].strip()
            if remainder:
                key, value = split_key_value(remainder)
                current[key] = value
            index += 1
            continue
        if current is None or line_indent <= indent:
            break
        key, value = split_key_value(stripped)
        if key == "relevant_files" and value == "":
            current[key], index = parse_string_list(lines, index + 1, line_indent + 2)
            continue
        if key == "subtopics" and value == "":
            current[key], index = parse_subtopics(lines, index + 1, line_indent + 2)
            continue
        current[key] = value
        index += 1
    return topics, index


def parse_plan(path=PLAN_PATH):
    if not path.exists():
        raise PlanError(f"Missing required file: {path}")
    lines = normalized_lines(path.read_text())
    plan = {"topics": []}
    index = 0
    while index < len(lines):
        line = lines[index]
        if count_indent(line) != 0:
            index += 1
            continue
        key, value = split_key_value(line.strip())
        if key == "topics" and value == "":
            plan["topics"], index = parse_topics(lines, index + 1, 2)
            continue
        plan[key] = value
        index += 1
    for topic in plan.get("topics", []):
        if not isinstance(topic, dict):
            raise PlanError("Invalid topic entry in plan.yml: expected mapping")
        topic.setdefault("relevant_files", [])
        topic.setdefault("subtopics", [])
        validate_topic_id(topic.get("id", ""))
        if not isinstance(topic.get("subtopics", []), list):
            raise PlanError(
                f"Invalid subtopics for topic id {topic.get('id', '')!r}: expected list"
            )
        for subtopic in topic.get("subtopics", []):
            if not isinstance(subtopic, dict):
                raise PlanError(
                    f"Invalid subtopic entry for topic id {topic.get('id', '')!r}: "
                    "expected mapping"
                )
            subtopic.setdefault("relevant_files", [])
            validate_subtopic_id(subtopic.get("id", ""))
    return plan


def is_safe_kebab(value):
    return bool(SAFE_KEBAB_RE.fullmatch(value))


def validate_topic_id(topic_id):
    if not isinstance(topic_id, str) or not is_safe_kebab(topic_id):
        raise PlanError(
            "Invalid topic id in plan.yml: expected safe kebab-case like "
            f"'system-architecture', got {topic_id!r}"
        )


def validate_subtopic_id(subtopic_id):
    if not isinstance(subtopic_id, str) or "--" not in subtopic_id:
        raise PlanError(
            "Invalid subtopic id in plan.yml: expected '<topic-id>--<slug>' "
            f"with safe kebab-case, got {subtopic_id!r}"
        )
    parent_id, slug = subtopic_id.split("--", 1)
    if not is_safe_kebab(parent_id) or not is_safe_kebab(slug):
        raise PlanError(
            "Invalid subtopic id in plan.yml: expected '<topic-id>--<slug>' "
            f"with safe kebab-case, got {subtopic_id!r}"
        )


def subtopic_slug(subtopic_id):
    return subtopic_id.split("--", 1)[1] if "--" in subtopic_id else subtopic_id


def letter_for(index):
    letters = ""
    number = index
    while True:
        number, remainder = divmod(number, 26)
        letters = chr(ord("a") + remainder) + letters
        if number == 0:
            return letters
        number -= 1


def output_path(filename):
    return str((Path.cwd() / WIKI_DIR / filename).resolve())


def build_documents(plan):
    documents = []
    for topic_index, topic in enumerate(plan.get("topics", []), start=1):
        prefix = f"{topic_index:02d}"
        topic_id = topic.get("id", "")
        subtopics = topic.get("subtopics", [])
        has_subtopics = bool(subtopics)
        documents.append(
            {
                "topic_id": topic_id,
                "parent_topic_id": None,
                "topic_title": topic.get("title", ""),
                "topic_description": topic.get("description", ""),
                "relevant_files": topic.get("relevant_files", []),
                "output_file": output_path(f"{prefix}-{topic_id}.md"),
                "is_overview": has_subtopics,
                "business_context": topic.get("business_context", ""),
            }
        )
        for subtopic_index, subtopic in enumerate(subtopics):
            letter = letter_for(subtopic_index)
            slug = subtopic_slug(subtopic.get("id", ""))
            business_context = subtopic.get(
                "business_context", topic.get("business_context", "")
            )
            documents.append(
                {
                    "topic_id": subtopic.get("id", ""),
                    "parent_topic_id": topic_id,
                    "topic_title": subtopic.get("title", ""),
                    "topic_description": subtopic.get("description", ""),
                    "relevant_files": subtopic.get("relevant_files", []),
                    "output_file": output_path(f"{prefix}{letter}-{slug}.md"),
                    "is_overview": False,
                    "business_context": business_context,
                }
            )
    return documents


def main():
    try:
        plan = parse_plan()
        documents = build_documents(plan)
        WIKI_DIR.mkdir(exist_ok=True)
        DOCUMENTS_PATH.write_text(json.dumps(documents, indent=2) + "\n")
        print(f"Wrote {DOCUMENTS_PATH} ({len(documents)} documents)")
    except PlanError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
