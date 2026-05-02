# Skill Source Of Truth Design

## Context

This repository is the source project for the `llm-gen-repo-wiki` skills. The project-owned skill files live under `skills/`, while user-level installed copies can exist under directories such as `~/.codex/skills/`.

Contributors and agents need a clear project-level rule so skill changes are made in the repository source files rather than only in an installed copy.

## Goal

Document a global contributor rule that any skill change must land in the project-owned files under `skills/`.

## Non-Goals

- Do not change individual skill prompts.
- Do not edit installed copies under user-level skill directories.
- Do not change the user-facing README usage flow.
- Do not add install or sync automation.

## Design

Create a repository-root `CONTRIBUTING.md` with a short "Skill Source of Truth" section.

The document will state:

- `skills/` is the authoritative source for all skills in this project.
- Any skill change must be made in the corresponding project file, usually `skills/<skill-name>/SKILL.md`.
- Installed copies under user-level directories, such as `~/.codex/skills/`, are deployment artifacts and should not be edited as the authoritative version.
- Installed copies may be refreshed after the project files are updated.

## Files

- Create `CONTRIBUTING.md`.

## Testing

Verify the repository diff includes only the intended documentation changes and that `CONTRIBUTING.md` contains the source-of-truth rule.
