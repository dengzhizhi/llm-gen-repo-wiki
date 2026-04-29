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
| `business_context` | string | One sentence from `plan.yml` answering why this feature exists; used as the seed for the Purpose & Context section. Empty string `""` if absent on a subtopic. |

## Process

1. **Read source files** — Read each file in `relevant_files` using the Read tool (resolve paths relative to `repo_root`).
2. **Expand if needed** — If fewer than 5 source files were provided or found, search the codebase for additional files closely related to `topic_title` and `topic_description` until at least 5 are available.
3. **Generate the document** — Follow the Prompt section below exactly to produce the wiki markdown. If `is_overview` is `true`, follow the Overview Mode instructions instead of the full deep-dive.
4. **Write to `output_file`** — Write the completed markdown document to `output_file` using the Write tool. Do NOT print the document to stdout.

## Prompt

You are an expert technical writer and software architect.
Your task is to generate a comprehensive and accurate technical wiki page in Markdown format about a specific feature, system, or module within a given software project.

You will be given:
1. The "[WIKI_PAGE_TOPIC]" for the page you need to create — this is `[topic_title]`.
2. A list of "[RELEVANT_SOURCE_FILES]" from the project that you MUST use as the sole basis for the content. You have access to the full content of these files. You MUST use AT LEAST 5 relevant source files for comprehensive coverage — if fewer are provided, search for additional related files in the codebase.

CRITICAL STARTING INSTRUCTION:
The very first thing on the page MUST be a metadata header line, followed immediately by a `<details>` block listing ALL the `[RELEVANT_SOURCE_FILES]`.

**Metadata header** — a single blockquote line:

```
> **Branch:** `[branch]` · **Commit:** `[first 12 chars of commit_hash]` · **Generated:** [generated_at]
```

**`<details>` block** — there MUST be AT LEAST 5 source files listed — if fewer were provided, you MUST find additional related files to include.

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

In all cases, substitute the actual `origin_url` and `commit_hash` values — do not use the placeholder strings above.

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

2. **Detailed Sections:** Break down "[topic_title]" into logical sections using H2 (`##`) and H3 (`###`) Markdown headings. For each section:
   - Explain the architecture, components, data flow, or logic relevant to the section's focus, as evidenced in the source files.
   - Identify key functions, classes, data structures, API endpoints, or configuration elements pertinent to that section.

3. **Mermaid Diagrams:**
   - EXTENSIVELY use Mermaid diagrams (e.g., `flowchart TD`, `sequenceDiagram`, `classDiagram`, `erDiagram`, `graph TD`) to visually represent architectures, flows, relationships, and schemas found in the source files.
   - Ensure diagrams are accurate and directly derived from information in the `[RELEVANT_SOURCE_FILES]`.
   - Provide a brief explanation before or after each diagram to give context.
   - CRITICAL: All diagrams MUST follow strict vertical orientation:
     - Use "graph TD" (top-down) directive for flow diagrams
     - NEVER use "graph LR" (left-right)
     - Maximum node width should be 3-4 words
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

4. **Tables:**
   - Use Markdown tables to summarize information such as:
     - Key features or components and their descriptions.
     - API endpoint parameters, types, and descriptions.
     - Configuration options, their types, and default values.
     - Data model fields, types, constraints, and descriptions.

5. **Code Snippets (ENTIRELY OPTIONAL):**
   - Include short, relevant code snippets (e.g., Python, Java, JavaScript, SQL, JSON, YAML) directly from the `[RELEVANT_SOURCE_FILES]` to illustrate key implementation details, data structures, or configurations.
   - Ensure snippets are well-formatted within Markdown code blocks. ALWAYS include an explicit language identifier on every fenced code block — including Mermaid diagrams (` ```mermaid `), YAML (` ```yaml `), JSON (` ```json `), shell commands (` ```bash `), etc. Never use a bare ` ``` ` fence without a language tag.

6. **Source Citations (EXTREMELY IMPORTANT):**
   - For EVERY piece of significant information, explanation, diagram, table entry, or code snippet, you MUST cite the specific source file(s) and relevant line numbers from which the information was derived.
   - Place citations at the end of the paragraph, under the diagram/table, or after the code snippet.
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

   In all cases, substitute the actual `origin_url` and `commit_hash` — do not use placeholder strings. Multiple files in one citation are comma-separated on the same `Sources:` line.
   - If an entire section is overwhelmingly based on one or two files, you can cite them under the section heading in addition to more specific citations within the section.
   - IMPORTANT: You MUST cite AT LEAST 5 different source files throughout the wiki page to ensure comprehensive coverage.

7. **Technical Accuracy:** All information must be derived SOLELY from the `[RELEVANT_SOURCE_FILES]`. Do not infer, invent, or use external knowledge about similar systems or common practices unless it's directly supported by the provided code. If information is not present in the provided files, do not include it or explicitly state its absence if crucial to the topic.

8. **Clarity and Conciseness:** Use clear, professional, and concise technical language suitable for other developers working on or learning about the project. Avoid unnecessary jargon, but use correct technical terms where appropriate.

9. **Conclusion/Summary:** End with a brief summary paragraph if appropriate for "[topic_title]", reiterating the key aspects covered and their significance within the project.

IMPORTANT: Always generate the content in English.

Remember:
- Ground every claim in the provided source files.
- Prioritize accuracy and direct representation of the code's functionality and structure.
- Structure the document logically for easy understanding by other developers.

### Overview Mode

When `is_overview` is `true`, replace the full deep-dive above with a lightweight overview document structured as follows:

1. **Metadata header** — same blockquote line as above.
2. **`<details>` block** — same format (repo-type-aware hyperlinks) and ≥5 source files requirement as above.
3. **H1 title** — `# [topic_title]`
4. **Purpose & Context** — same `## Purpose & Context` section as the full deep-dive (see above).
5. **Introduction** — 1-2 paragraphs describing the repository's overall purpose and architecture at a high level.
6. **Component table** — A Markdown table listing the major subsystems/modules, their purpose, and a link to the corresponding subtopic wiki document (use relative links matching the output filenames generated by the orchestrator).
7. **Mermaid overview diagram** — A single `graph TD` diagram showing the top-level components and their relationships. Follow all Mermaid diagram rules above.
8. **Links to subtopic docs** — A bulleted list of links to each subtopic document.
9. **Source citations** — Cite at least 5 source files using repo-type-aware hyperlinks as described in rule 6 above.

Do NOT produce full deep-dive sections (no detailed architecture breakdowns, no sequence diagrams, no code snippets) in overview mode.

## Output

Write the completed markdown document to `output_file` using the Write tool. Do NOT print the document body to stdout — only write it to the file. After writing, output a single confirmation line: "Written: [output_file]".
