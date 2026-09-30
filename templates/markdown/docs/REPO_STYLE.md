# Repository style

> This file is vendored. Local changes can and will be overwritten by propagation.

Conventions for repositories focused on Markdown and Djot content.

## Core principles

- Focus on important issues. Prioritize useful, correct content and clear writing.
- Use the scientific method. Check rendered output when presentation matters.
- Fix the design, not the symptom. Correct sources and keep generated outputs reproducible.
- Ground requirements in actual needs. Keep tooling small and add it when the work requires it.
- Finish the obvious. Complete edits and their relevant checks before handing work back.

## Files and folders

- Keep `README.md` and `AGENTS.md` at the repository root.
- Group related content in shallow topic folders when useful.
- Use descriptive filenames, uppercase snake case for Markdown documentation, and lowercase
  snake case for other files. Use `.djot` for Djot sources.
- Preserve editable sources and distinguish them from rendered outputs.
- Follow `docs/MARKDOWN_STYLE.md` for Markdown and shared writing conventions.
- Keep renderer-specific syntax and commands in the repository's own documentation.

## Guidance and history

- Record human-stated guidance in `docs/HUMAN_GUIDANCE.md`, using close paraphrases.
- Record settled design choices in `docs/DESIGN_DECISIONS.md`, with `Decision`,
  `Why`, `Consequence`, and `Owner` fields under a level-three heading.
- Record edits in `docs/CHANGELOG.md`, newest date first. Keep repository history local.
- Keep agent instructions concise and link to their authoritative guides.
- Only humans run `git commit`. Use `git mv` for moves; check Git-directory write permission
  first. Stop if an index lock exists and report it without deleting it.

## Validation

Run `source source_me.sh && python3 -m pytest tests/` from the repository root.
The three checks cover local links, ASCII/ISO-8859-1 compliance, and whitespace in `.md` and
`.djot` files. Shared helpers and fixers support those checks; pytest is the only required package.

A link failure means a target is missing, escapes the repository, or has mismatched path text.
Correct the source link or restore the intended target. Character and whitespace failures report
the affected files; inspect the automatic fixes and correct remaining violations before rerunning.
External URLs and document anchors are outside the local-link check.

## Licensing

Keep complete license texts in root `LICENSE.<SPDX>` files. Explain their scope in `README.md`,
especially when text, figures, and code have different licenses.
