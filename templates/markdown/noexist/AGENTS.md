## Writing and repository rules

Follow `docs/REPO_STYLE.md` and `docs/MARKDOWN_STYLE.md`.
Record edits in `docs/CHANGELOG.md`, human guidance in `docs/HUMAN_GUIDANCE.md`,
and settled design decisions in `docs/DESIGN_DECISIONS.md`.

## Validation

Run `source source_me.sh && python3 -m pytest tests/` for local links, ASCII/ISO-8859-1,
and whitespace checks in Markdown and Djot sources. Python supports validation only.
Install the checker dependency with `source source_me.sh && python3 -m pip install -r pip_requirements-dev.txt`.
