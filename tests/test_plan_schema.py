import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def load_module(relative_path: str, module_name: str):
    module_path = REPO_ROOT / relative_path
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


WIKI_GEN_COMPUTE_DOCS = load_module(
    "skills/wiki-gen/compute_docs.py", "wiki_gen_compute_docs"
)
WIKI_UPDATE_COMPUTE_DOCS = load_module(
    "skills/wiki-update/compute_docs.py", "wiki_update_compute_docs"
)


PLAN_YAML = """\
repo: demo-repo
description: Demo repository for planner schema coverage.
planning_warnings:
  - README is sparse; plan inferred from tests and entry points.
planning_questions:
  - Should onboarding prioritize CLI usage or internal architecture?
topics:
  - id: system-overview
    title: System Overview
    description: Introduces the main entry points and contributor mental model.
    business_context: Helps new contributors understand where to start.
    importance: high
    user_requested: false
    primary_audience: new-contributor
    doc_goal: Help a new contributor trace the main workflow end to end.
    diagram_candidates:
      - request-flow
      - component-map
    coverage_tags:
      - architecture
      - onboarding
    open_questions:
      - Should runtime lifecycle be split into its own topic?
    relevant_files:
      - src/app.py
      - src/router.py
    subtopics:
      - id: system-overview--request-lifecycle
        title: Request Lifecycle
        description: Follows a request from entry point through handlers.
        user_requested: false
        business_context: Helps contributors debug runtime behavior safely.
        relevant_files:
          - src/router.py
"""


class PlanSchemaCompatibilityTest(unittest.TestCase):
    def write_plan(self, directory: Path) -> Path:
        wiki_dir = directory / "llm-gen-wiki"
        wiki_dir.mkdir()
        plan_path = wiki_dir / "plan.yml"
        plan_path.write_text(PLAN_YAML)
        return plan_path

    def test_wiki_gen_compute_docs_accepts_additive_plan_metadata(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            plan_path = self.write_plan(tmp_path)
            original_cwd = Path.cwd()
            try:
                os = __import__("os")
                os.chdir(tmp_path)
                plan = WIKI_GEN_COMPUTE_DOCS.parse_plan(plan_path)
                documents = WIKI_GEN_COMPUTE_DOCS.build_documents(plan)
            finally:
                os.chdir(original_cwd)

        self.assertEqual(
            plan["planning_warnings"],
            ["README is sparse; plan inferred from tests and entry points."],
        )
        self.assertEqual(
            plan["planning_questions"],
            ["Should onboarding prioritize CLI usage or internal architecture?"],
        )
        self.assertEqual(plan["topics"][0]["primary_audience"], "new-contributor")
        self.assertEqual(plan["topics"][0]["coverage_tags"], ["architecture", "onboarding"])
        self.assertEqual(len(documents), 2)
        self.assertTrue(documents[0]["is_overview"])
        self.assertEqual(documents[0]["topic_title"], "System Overview")
        self.assertEqual(documents[1]["topic_title"], "Request Lifecycle")

    def test_wiki_update_compute_docs_preserves_generation_notes_behavior(self):
        plan_with_notes = PLAN_YAML.replace(
            "    subtopics:\n",
            '    generation_notes: "Include debugging tips for new contributors."\n'
            "    subtopics:\n",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = Path(tmpdir)
            wiki_dir = tmp_path / "llm-gen-wiki"
            wiki_dir.mkdir()
            plan_path = wiki_dir / "plan.yml"
            plan_path.write_text(plan_with_notes)
            original_cwd = Path.cwd()
            try:
                os = __import__("os")
                os.chdir(tmp_path)
                plan = WIKI_UPDATE_COMPUTE_DOCS.parse_plan(plan_path)
                documents = WIKI_UPDATE_COMPUTE_DOCS.build_documents(plan)
            finally:
                os.chdir(original_cwd)

        self.assertEqual(len(documents), 2)
        self.assertIn(
            "Additional generation instructions: Include debugging tips for new contributors.",
            documents[0]["topic_description"],
        )
        self.assertIn(
            "Additional generation instructions: Include debugging tips for new contributors.",
            documents[1]["topic_description"],
        )


if __name__ == "__main__":
    unittest.main()
