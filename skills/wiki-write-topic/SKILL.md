---
name: wiki-write-topic
description: Use when writing a detailed wiki document for a single code repository topic — given a topic title, description, and relevant files, produces a comprehensive markdown document with Mermaid diagrams and source citations. Invoked as a subagent by wiki-gen.
---

# Wiki Write Topic

## Overview

This skill is invoked as a subagent by the `wiki-gen` orchestrator skill. It receives a single topic assignment and produces one comprehensive markdown wiki document for that topic. When the skill starts, it announces: "Writing wiki document for topic: [topic_title]".

## Inputs

| Parameter | Type | Description |
|---|---|---|
| `topic_title` | string | The title of the wiki page topic (e.g. "Authentication System") |
| `topic_description` | string | A brief description of what the topic covers |
| `relevant_files` | list of strings | Relative paths (from `repo_root`) to source files identified as relevant to this topic |
| `repo_root` | string | Absolute path to the root of the repository being documented |
| `output_file` | string | Absolute path where the completed markdown document must be written |
| `is_overview` | boolean | When `true`, produce a lightweight overview doc (intro + component table + Mermaid overview diagram + links to subtopic docs) instead of a full deep-dive |
| `generated_at` | string | ISO-8601 datetime when wiki generation started (e.g. `2026-04-29T14:30:00Z`) |
| `branch` | string | Git branch name at generation time |
| `commit_hash` | string | Full 40-character git commit SHA at generation time |
| `origin_url` | string | Canonical HTTPS root URL of the remote (e.g. `https://github.com/user/repo`) |
| `repo_type` | string | `github`, `bitbucket`, or `unknown` — controls code link format |
| `scope_prefix` | string | Path of `repo_root` relative to the git root; empty string `""` when `repo_root` is the git root. Prepend to file paths when building remote URLs. |
| `language` | string | Human-readable output language such as `English`, `Japanese`, or `Simplified Chinese`. |
| `business_context` | string | One sentence from `plan.yml` answering why this feature exists; used as the seed for the Purpose & Context section. Empty string `""` if absent on a subtopic. |

## Process

1. **Read source files with line numbers** — Read each file in `relevant_files` using the Read tool (resolve paths relative to `repo_root`). Preserve line numbers for citation planning.
2. **Expand if needed** — If fewer than 5 meaningfully relevant source files were provided or found, search the codebase for additional files closely related to `topic_title` and `topic_description` until at least 5 are available, or until the repository does not contain 5 relevant files.
3. **Filter weakly related files** — Exclude files that are not meaningfully related to the topic. Do not cite or list a file solely to satisfy the 5-file target.
4. **Build an internal evidence map** — Before drafting prose, identify the functions, classes, commands, config keys, data structures, entry points, workflows, error paths, and source line ranges that are directly relevant to the topic.
5. **Draft an internal outline** — Plan the H2/H3 structure before writing. Each planned section must have at least one supporting source file and, for full deep-dives, the outline should include a workflow or data-flow section when the sources support one.
6. **Generate the document** — Follow the Prompt section below exactly to produce the wiki markdown. If `is_overview` is `true`, follow the Overview Mode instructions instead of the full deep-dive.
7. **Validate Mermaid syntax when possible** — If the document contains Mermaid diagrams, check whether `mmdc` (mermaid-cli) is available. If it is available, dispatch a subagent to validate Mermaid syntax only. The subagent does not need to keep or return rendered image files; it only reports syntax errors that must be fixed before writing.
8. **Self-audit before writing** — Verify the completed document against the Quality Audit checklist below before writing it.
9. **Persist the completed chapter atomically** — Use the skill-local `atomic_write.py` helper to write the completed markdown document to a sibling temporary path and replace `output_file` only after the full document is ready.
10. **Confirm only after persistence succeeds** — After the atomic replace succeeds, output exactly one confirmation line: `Written: [output_file]`. Do NOT print the document body to stdout.

The file at `output_file` is the durable success artifact for this subagent.

- If the subagent fails before the atomic replace step, the final `output_file` must not be treated as completed.
- If the subagent fails after the atomic replace step, the final `output_file` is a valid completed chapter artifact and may be skipped by `wiki-gen` on a same-plan rerun.

## Prompt

You are an expert technical writer and software architect.
Your task is to generate a comprehensive and accurate technical wiki page in Markdown format about a specific feature, system, or module within a given software project.

You will be given:
1. The "[WIKI_PAGE_TOPIC]" for the page you need to create — this is `[topic_title]`.
2. A list of "[RELEVANT_SOURCE_FILES]" from the project that you MUST use as the sole basis for the content. You have access to the full content of these files. You MUST use AT LEAST 5 meaningfully relevant source files for comprehensive coverage — if fewer are provided, search for additional related files in the codebase. If the repository truly does not contain 5 relevant files for this topic, use all relevant files and keep the page evidence-bounded rather than padding it.

## Required Internal Preparation

Before writing the final markdown document, perform this preparation internally. Do NOT include these notes in the output unless a later rule explicitly asks for a visible section.

1. **Relevance filter** — Review every provided and discovered file. Keep only files that directly support the topic. Exclude weakly related files rather than citing them just to reach the 5-file target.
2. **Evidence map** — Identify the relevant functions, classes, commands, config keys, data structures, entry points, workflows, error paths, and line ranges. Use this map to decide what deserves prose, tables, diagrams, and citations.
3. **Outline** — Draft the H2/H3 outline before prose. Every planned section must be supported by at least one source file and should have a clear purpose in explaining this topic.
4. **Boundary check** — Decide whether the topic boundaries are ambiguous or overlap with adjacent topics. If they are, include the boundary section described below.

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a metadata header line, followed immediately by a `<details>` block listing all source files actually used as context.

**Metadata header** — a single blockquote line:

```
> **Branch:** `[branch]` · **Commit:** `[first 12 chars of commit_hash]` · **Generated:** [generated_at]
```

**`<details>` block** — list ALL and ONLY the source files you actually used as context for this page. There SHOULD be at least 5 meaningfully relevant files. If fewer than 5 relevant files exist, list the available relevant files and write a shorter, evidence-bounded page instead of adding unrelated files.

For `repo_type: github`, format file links as:
```
<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [path/to/file1.ext](https://github.com/user/repo/blob/COMMIT_HASH/path/to/file1.ext)
- [path/to/file2.ext](https://github.com/user/repo/blob/COMMIT_HASH/path/to/file2.ext)
</details>
```

For `repo_type: bitbucket`, format file links as:
```
<details>
<summary>Relevant source files</summary>

The following files were used as context for generating this wiki page:

- [path/to/file1.ext](https://bitbucket.org/project/repo/src/COMMIT_HASH/path/to/file1.ext)
- [path/to/file2.ext](https://bitbucket.org/project/repo/src/COMMIT_HASH/path/to/file2.ext)
</details>
```

If `repo_type` is neither `github` nor `bitbucket` (i.e. local repo with no remote, or unrecognised host), use plain relative links with no remote URL: `[path/to/file.ext](path/to/file.ext)`.

In all cases, substitute the actual `origin_url` and `commit_hash` values — do not use the placeholder strings above. When building any remote URL, the file path segment must be prefixed with `scope_prefix` if it is non-empty: use `<scope_prefix>/path/to/file.ext`; if `scope_prefix` is empty, use `path/to/file.ext` directly.

Remember, do not provide any acknowledgements, disclaimers, apologies, or any other preface before the metadata header. JUST START with the `>` blockquote line.

Immediately after the `<details>` block, the main title of the page should be a H1 Markdown heading: `# [topic_title]`.

Immediately after the H1 heading, add a Purpose & Context section:

```markdown
## Purpose & Context

[1–3 sentences explaining what business or product problem this feature solves and why it exists in the system. Use `business_context` as the seed — you may expand it with supporting evidence from the source files, but do not contradict it or invent claims beyond what the files support. If `business_context` is an empty string, derive the purpose solely from the source files.]
```

This section answers "why" — it is not a technical summary. The Introduction that follows covers "what and how".

Based ONLY on the content of the `[RELEVANT_SOURCE_FILES]`:

1. **Introduction:** Start with a concise introduction (1-2 paragraphs) explaining the purpose, scope, and high-level overview of "[topic_title]" within the context of the overall project. If relevant, and if information is available in the provided files, link to other potential wiki pages using the format `[Link Text](#page-anchor-or-id)`.

2. **Boundary Section (when needed):** If the topic overlaps with adjacent areas, include a short `## What This Page Covers` section and a short `## What This Page Does Not Cover` section after the Introduction. Use these sections only when they clarify ambiguous boundaries; omit them when the topic is already narrow and obvious.

3. **Detailed Sections:** Break down "[topic_title]" into logical sections using H2 (`##`) and H3 (`###`) Markdown headings. For each section:
   - Explain the architecture, components, data flow, or logic relevant to the section's focus, as evidenced in the source files.
   - Identify key functions, classes, data structures, API endpoints, or configuration elements pertinent to that section.
   - Do not create sections that are not directly supported by the evidence map.

4. **Workflow / Data Flow:** For full deep-dive pages, include at least one workflow-oriented H2 section when supported by the sources. Explain the main inputs, processing steps, outputs, side effects, and failure or fallback paths for the topic. If the files do not expose a meaningful workflow, omit this section rather than inventing one.

5. **Sparse Topic Handling:** If the available evidence is thin, produce a shorter page with only the sections the files support. Do NOT pad the page with generic architecture, best-practice commentary, speculative future behavior, or unsupported diagrams. It is acceptable for a sparse topic page to cite fewer than 5 source files only when fewer than 5 relevant source files exist.

6. **Mermaid Diagrams:**
   - EXTENSIVELY use Mermaid diagrams (e.g., `flowchart TD`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `graph TD`) to visually represent architectures, flows, relationships, and schemas found in the source files.
   - Ensure diagrams are accurate and directly derived from information in the `[RELEVANT_SOURCE_FILES]`.
   - Provide a brief explanation before or after each diagram to give context.
   - Every diagram MUST have a nearby `Sources:` citation that supports the relationships shown.
   - For diagrams with multiple component categories, use Mermaid `classDef` and `class` styling to apply distinct, readable colors by category. Useful categories include user-facing entry points, orchestration/control flow, data or storage, external services, configuration, and error or fallback paths.
   - Use color to clarify structure, not as decoration. Keep palettes restrained and high-contrast, explain category meaning through labels, grouping, or nearby prose, and do not rely on color alone for critical distinctions.
   - CRITICAL: All diagrams MUST follow strict vertical orientation:
     - Use "graph TD" (top-down) directive for flow diagrams
     - NEVER use "graph LR" (left-right)
     - Maximum node width should be 3-4 words
     - Quote Mermaid node labels and edge labels with double quotes (`"..."`) wherever Mermaid syntax supports it, especially labels containing spaces, punctuation, parentheses, slashes, colons, brackets, or other special characters.
     - For sequence diagrams:
       - Start with "sequenceDiagram" directive on its own line
       - Define ALL participants at the beginning using "participant" keyword
       - Optionally specify participant types: actor, boundary, control, entity, database, collections, queue
       - Use descriptive but concise participant names, or use aliases: "participant A as Alice"
       - Use the correct Mermaid arrow syntax (8 types available):
         - -> solid line without arrow (rarely used)
         - --> dotted line without arrow (rarely used)
         - ->> solid line with arrowhead (most common for requests/calls)
         - -->> dotted line with arrowhead (most common for responses/returns)
         - ->x solid line with X at end (failed/error message)
         - -->x dotted line with X at end (failed/error response)
         - -) solid line with open arrow (async message, fire-and-forget)
         - --) dotted line with open arrow (async response)
         - Examples: A->>B: Request, B-->>A: Response, A->xB: Error, A-)B: Async event
       - Use +/- suffix for activation boxes: A->>+B: Start (activates B), B-->>-A: End (deactivates B)
       - Group related participants using "box": box GroupName ... end
       - Use structural elements for complex flows:
         - loop LoopText ... end (for iterations)
         - alt ConditionText ... else ... end (for conditionals)
         - opt OptionalText ... end (for optional flows)
         - par ParallelText ... and ... end (for parallel actions)
         - critical CriticalText ... option ... end (for critical regions)
         - break BreakText ... end (for breaking flows/exceptions)
       - Add notes for clarification: "Note over A,B: Description", "Note right of A: Detail"
       - Use autonumber directive to add sequence numbers to messages
       - NEVER use flowchart-style labels like A--|label|-->B. Always use a colon for labels: A->>B: My Label

7. **Tables:**
   - Use Markdown tables to summarize information such as:
     - Key features or components and their descriptions.
     - API endpoint parameters, types, and descriptions.
     - Configuration options, their types, and default values.
     - Data model fields, types, constraints, and descriptions.
   - Every table MUST have a nearby `Sources:` citation that supports the entries.

8. **Code Snippets (ENTIRELY OPTIONAL):**
   - Include short, relevant code snippets (e.g., Python, Java, JavaScript, SQL, JSON, YAML) directly from the `[RELEVANT_SOURCE_FILES]` to illustrate key implementation details, data structures, or configurations.
   - Ensure snippets are well-formatted within Markdown code blocks. ALWAYS include an explicit language identifier on every fenced code block — including Mermaid diagrams (` ```mermaid `), YAML (` ```yaml `), JSON (` ```json `), shell commands (` ```bash `), etc. Never use a bare ` ``` ` fence without a language tag.

9. **Source Citations (EXTREMELY IMPORTANT):**
   - For EVERY piece of significant information, explanation, diagram, table entry, or code snippet, you MUST cite the specific source file(s) and relevant line numbers from which the information was derived.
   - Place citations at the end of the paragraph, under the diagram/table, or after the code snippet.
   - Prefer precise line ranges from the evidence map. Use whole-file citations only when the claim genuinely depends on the whole file structure rather than specific lines.
   - Citations MUST be hyperlinks to the exact location in the remote repository. Use the format that matches `repo_type`:

   **GitHub** (`repo_type: github`):
   - Line range: `Sources: [path/to/file.ext:12-15](https://github.com/user/repo/blob/COMMIT_HASH/path/to/file.ext#L12-L15)`
   - Single line: `Sources: [path/to/file.ext:42](https://github.com/user/repo/blob/COMMIT_HASH/path/to/file.ext#L42)`
   - Whole file: `Sources: [path/to/file.ext](https://github.com/user/repo/blob/COMMIT_HASH/path/to/file.ext)`

   **Bitbucket** (`repo_type: bitbucket`):
   - Line range: `Sources: [path/to/file.ext:12-15](https://bitbucket.org/project/repo/src/COMMIT_HASH/path/to/file.ext#lines-12:15)`
   - Single line: `Sources: [path/to/file.ext:42](https://bitbucket.org/project/repo/src/COMMIT_HASH/path/to/file.ext#lines-42)`
   - Whole file: `Sources: [path/to/file.ext](https://bitbucket.org/project/repo/src/COMMIT_HASH/path/to/file.ext)`

   **No remote / unrecognised host** (i.e. `repo_type` is neither `github` nor `bitbucket`): use plain format with an empty href — `Sources: [path/to/file.ext:12-15]()` — so the label is still informative but no broken URL is emitted.

   In all cases, substitute the actual `origin_url` and `commit_hash` — do not use placeholder strings. Prepend `scope_prefix` to each file path when it is non-empty (same rule as the `<details>` block above). Multiple files in one citation are comma-separated on the same `Sources:` line.
   - If an entire section is overwhelmingly based on one or two files, you can cite them under the section heading in addition to more specific citations within the section.
   - IMPORTANT: You MUST cite AT LEAST 5 different source files throughout the wiki page when at least 5 meaningfully relevant source files exist. If fewer than 5 relevant source files exist, cite every relevant source file and keep the page scoped to the available evidence.

10. **Technical Accuracy:** All information must be derived SOLELY from the `[RELEVANT_SOURCE_FILES]`. Do not infer, invent, or use external knowledge about similar systems or common practices unless it's directly supported by the provided code. If information is not present in the provided files, do not include it or explicitly state its absence if crucial to the topic.

11. **Clarity and Conciseness:** Use clear, professional, and concise technical language suitable for other developers working on or learning about the project. Avoid unnecessary jargon, but use correct technical terms where appropriate.

12. **Conclusion/Summary:** End with a brief summary paragraph if appropriate for "[topic_title]", reiterating the key aspects covered and their significance within the project.

IMPORTANT: Always generate the content in `[language]`. Treat `language` as the required output language for all prose, headings, captions, and explanations. Keep code, file paths, config keys, API names, and source citations in their original form unless translation is explicitly appropriate.

Remember:
- Ground every claim in the provided source files.
- Prioritize accuracy and direct representation of the code's functionality and structure.
- Structure the document logically for easy understanding by other developers.

### Quality Audit

Before writing the document to `output_file`, review it internally and fix any issue found:

- The `<details>` block lists only files that were actually used.
- Each H2 section has at least one supporting `Sources:` citation, unless the section is purely navigational.
- At least 5 distinct source files are cited when 5 relevant files exist; otherwise every relevant source file is cited.
- Every Mermaid diagram and Markdown table has a nearby citation.
- Complex Mermaid diagrams use category colors when they improve readability, and the category meaning is clear from labels, grouping, or nearby prose.
- If Mermaid diagrams are present and `mmdc` is available, a subagent has validated their syntax and any syntax errors have been fixed. Do not require or preserve image output from this check.
- Mermaid node labels and edge labels use double quotes where Mermaid syntax supports quoting, especially when labels contain spaces or special characters.
- Every fenced code block has an explicit language tag.
- Citation links use precise line ranges whenever possible.
- The document includes workflow or data-flow coverage when the sources support it.
- Sparse topics are short and evidence-bounded rather than padded.
- No paragraph, diagram, table entry, or code explanation makes an unsupported claim.

### Overview Mode

When `is_overview` is `true`, replace the full deep-dive above with a lightweight overview document structured as follows:

1. **Metadata header** — same blockquote line as above.
2. **`<details>` block** — same format (repo-type-aware hyperlinks) and source relevance rules as above.
3. **H1 title** — `# [topic_title]`
4. **Purpose & Context** — same `## Purpose & Context` section as the full deep-dive (see above).
5. **Introduction** — 1-2 paragraphs describing the repository's overall purpose and architecture at a high level.
6. **Component table** — A Markdown table listing the major subsystems/modules, their purpose, and a link to the corresponding subtopic wiki document (use relative links matching the output filenames generated by the orchestrator).
7. **Mermaid overview diagram** — A single `graph TD` diagram showing the top-level components and their relationships. Follow all Mermaid diagram rules above.
8. **Links to subtopic docs** — A bulleted list of links to each subtopic document.
9. **Source citations** — Cite at least 5 source files when 5 relevant files exist; otherwise cite every relevant source file using repo-type-aware hyperlinks as described in rule 9 above.

Do NOT produce full deep-dive sections (no detailed architecture breakdowns, no sequence diagrams, no code snippets) in overview mode.

## Output

Use the skill-local `atomic_write.py` helper to persist the completed markdown document to `output_file`. Do NOT print the document body to stdout. After the atomic replace succeeds, output a single confirmation line: "Written: [output_file]".
