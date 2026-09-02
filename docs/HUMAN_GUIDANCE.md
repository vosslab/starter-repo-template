# Human guidance

<!-- VENDORED HEADER: START -->
Record the durable guidance Neil Voss states, or approves for preservation here, in his own words:
first person or close paraphrase, one to three lines per bullet. Material he supplies as a source
may inform [DESIGN_DECISIONS.md](DESIGN_DECISIONS.md) once it is settled, and an entry of uncertain
origin belongs there too. Rules: [REPO_STYLE.md](REPO_STYLE.md).
[PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

## Decision priority

## Review expectations

- Classify implementation checks separately from permanent tests. Keep permanent pytest cases that
  satisfy [PYTEST_STYLE.md](PYTEST_STYLE.md), and remove temporary proof checks after the rebuild.

## Working style

- Have single-repository propagation add a `devel/changelog_lib.py`-compatible changelog entry only
  when it makes real changes; recurring `.gitignore` churn must not create one.
- Keep one native application, library, or tool-helper package in a named root-level folder. Use a
  `packages/` grouping layer when multiple native products or packages need separation.
