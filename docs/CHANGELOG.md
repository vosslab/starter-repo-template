## 2026-09-04

### Additions and New Features

- Added `devel/graphify_prune_tests.py`, removing Rust `#[cfg(test)]` symbols from `graph.json`
  between extraction and clustering. Spans come from tree-sitter rather than a brace scan, which
  would have to reason about strings, comments, and nested modules to be correct.
- Added `devel/graphify_docs_lib.py` and a `--page` mode writing `docs/GRAPHIFY.md`: a Mermaid
  community diagram GitHub renders natively, a size and language summary, a community table, and
  the most-connected symbols per area.
- Added `devel/graphify_clean_svg.py`, turning Graphify's 1.9 MB SVG export into a 435 KB
  committable figure by dropping per-symbol labels, collecting unreferenced definitions, and
  rounding coordinates.
- Added `devel/graphify_context_lib.py`, holding the Graphify artifact loaders and orientation
  formatting that `devel/graphify_map_repo.py` previously carried inline. The script was at 839 of
  its 1000-line budget, so the split ran before any feature work rather than after it. This follows
  the existing `changelog_lib.py` sibling-helper pattern and ships by folder with no manifest entry.
- Manager context now reports architectural hubs and map size. The `gods` field was already being
  validated by the analysis-sidecar loader and then discarded, so the hub data was parsed and thrown
  away on every run.
- Added `--reflect`, aggregating outcomes saved with `graphify save-result` into
  `graphify-out/reflections/LESSONS.md`. Manager context points at that file when it exists but
  never regenerates it, so building or printing context cannot rewrite reflections as a side effect.
- Added `--global`, merging a repository into the shared cross-repository graph and tagging it with
  the repository directory name. Useful only for a repo family, which is what this template seeds.
- Added `--deep` for aggressive inferred-edge semantic extraction, and `--force-shrink` so an update
  can write a smaller graph after code was deleted.
- Added a Graphify section to `devel/DEVEL_README.md` so downstream repositories learn that
  `graphify-out/MANAGER_CONTEXT.md` exists and that targeted queries beat a broad repository sweep.

### Behavior or Interface Changes

- Cross-area connectors now drop symbols spanning more than a quarter of the map, with a floor of
  three communities so small maps still report connectors. A `Timestamp` type joining 34 of about 40
  communities was being presented as a navigational bridge, which it is not.
- Notable relationships and architectural hubs now exclude test scaffolding and uninformative call
  targets. The whole surprises list is scanned before truncation, because filtering otherwise
  empties the section on a test-heavy repository.
- Incremental builds pass `--missing-only` when relabeling. A full relabel previously re-paid for an
  LLM call per community whenever `--update --include-docs` ran.
- Fresh builds now report same-endpoint edge collapse after benchmarking, and context mode warns
  when non-code changes are pending. Both are advisory and neither can fail a build or suppress
  orientation.

### Fixes and Maintenance

- The six-pass audit restored every visible major-area name in `docs/GRAPHIFY_map.svg` by moving
  legend glyph definitions to root SVG definitions before deleting node-label groups. The cleaner
  now rejects unresolved local references, and the committed figure was rendered at 1600 px and
  640 px to confirm all 26 group labels remain visible.
- Graphify page generation now treats malformed optional SVG exports as non-fatal, sanitizes LLM
  community names before placing them in Mermaid or Markdown, and writes detail sections for every
  community as planned. Architectural hubs now include their source paths.
- Removed the thin SVG file-round-trip pytest and strengthened the retained-label test around the
  actual cross-group glyph-reference failure that broke the rendered legend.
- A disposable real-Cargo run found that fresh, unclustered Graphify output stores relationships
  under `edges`, not the post-clustering `links` field used by the initial fixture. The pruner and
  its fixtures now follow the real extraction schema.
- A fresh build in a Cargo repository now extracts with `--no-cluster`, prunes Rust test symbols,
  then runs `cluster-only`, so community detection and hub ranking never see the test suite. The
  gate is `Cargo.toml`, so repositories without Rust run the original pipeline unchanged, and the
  run reports how many nodes and links were removed. Incremental updates deliberately do not
  prune: re-clustering renumbers communities and would strand the stored labels.
- `tests/meta/test_graphify_map_repo.py` now places `devel/` on `sys.path` itself. That test
  propagates to consumer repositories but `pytest.ini` does not, so the sibling import added by the
  module split would have failed downstream where nothing puts `devel/` on the path.
- Rotated `docs/CHANGELOG.md` past its 800-line threshold, moving 2026-08-10 through 2026-08-31
  into `docs/CHANGELOG-2026-08b.md` and keeping the two most recent day blocks active.
- Removed the temporary Cargo argv and lifecycle probes after the disposable real-Cargo rebuild
  proved the sequence end to end. The permanent pruning module now tests Rust span recognition and
  graph surgery, while `tests/meta/test_graphify_map_repo.py` is back to 829 lines.
- Applied the permanent-test checklist to all Graphify additions and removed 31 rebuild-only cases:
  exact CLI plumbing, output-count snapshots, file-wrapper round trips, duplicate predicates, and
  geometry-attribute inventories. Their useful implementation evidence remains in this changelog;
  only fast, deterministic tests of durable behavior remain in pytest.
- Refined maintainer guidance so adaptability comes from clear boundaries, stable domain concepts,
  and replaceable components, while speculative mechanisms wait for a concrete requirement or
  likely failure mode.

### Decisions and Failures

- Rejected `docs/USAGE.md` as the home for Graphify guidance. Files under `docs/` propagate by
  overwrite, so creating one in the template would have replaced every consumer's own usage
  document on the next sync. `AGENTS.md` and `README.md` were rejected for the opposite reason:
  the first ships only when absent, the second never ships.
- Rejected `graphify claude install` and `graphify codex install`. They write into `CLAUDE.md` and
  `AGENTS.md` and install a PreToolUse hook, contending with the merge and noexist routing those
  files already have.
- Rejected shelling out to `graphify check-update`. It only tests for a `needs_update` flag file and
  always exits zero, so a subprocess would have cost a process and broken context mode's documented
  promise to print orientation without running Graphify. The flag is read directly instead.
- Recorded `docs/GRAPHIFY.md` and `docs/GRAPHIFY_map.svg` as files that never transfer between
  repositories, using exact entries rather than a filename pattern. Link-bucket classification
  reads only the exact list, and the page must classify as non-shared so it may link to the
  `devel/` tooling that generates it. Rejected creating the page under a shared docs path, which
  would have overwritten each repository's page with a map of the wrong codebase.
- Rejected extracting Mermaid from Graphify's call-flow HTML. Its diagrams pin a dark theme and
  use HTML labels, which renders wrong in GitHub light mode and risks sanitization, and scraping
  generated markup would couple this repository to a presentation layer that changes often. The
  diagram is generated from `graph.json` instead.
- Measured, then kept, the unreferenced-definition pass in the SVG cleaner even though it removes
  nothing from current output: matplotlib nests each glyph definition inside the text group that
  uses it, so dropping the labels already collects them structurally. Kept because it is cheap and
  covers definitions emitted at the document root; it is exercised by unit tests, not by real
  output. Measured 42 definition blocks before label removal, 40 of them nested, 5 remaining after.
- Confirmed matplotlib is not a Graphify dependency and added none. It is only needed by
  `graphify export svg`, so a machine without it gets the page with no figure.
- Confirmed but did not fix an upstream defect: Graphify's Rust extractor indexes
  `#[cfg(test)] mod tests` contents as production symbols, because `walk()` in
  `graphify/extractors/rust.py` reaches `mod_item` through its generic fallback and never inspects
  an `attribute_item`. Graphify's own source is not modified; the prune step removes the symbols
  from this repository's copy of `graph.json` between two of Graphify's documented commands. An
  upstream fix would still be better, since it would reach every Graphify user and every build
  path, including the incremental updates that deliberately do not prune here.

### Developer Tests and Notes

- `source source_me.sh && python3 -m pytest tests/ -q` passes 2359 permanent fast-lane tests. The 60
  retained Graphify cases cover connector spread, test-symbol filtering, hub rendering, advisory
  staleness, Rust span pruning, safe page rendering, and SVG reference integrity across four
  focused modules.
- A disposable clone of `peptidyle-learning-engine` completed the real Rust pipeline: Graphify
  extracted 10,501 nodes and 31,376 edges; pruning removed 720 test nodes and 1,849 incident edges;
  and `cluster-only` completed with 9,781 nodes and 27,082 edges. The named denied-membership test
  symbol was absent from both `graph.json` and the generated orientation afterward.
- Measured on this repository: the figure cleaner reports 1934 KB to 435 KB, 452 node labels
  removed, 26 community labels kept.
- Two existing tests changed meaning rather than being loosened. The bridge test now asserts the god
  node never takes the connector slot instead of asserting it is absent entirely, since hubs are now
  rendered. The connector-bounding test now builds a map large enough that a ten-community connector
  is still a real bridge, since otherwise the spread filter rejects it before the display bound is
  reached.

## 2026-09-02

### Additions and New Features

- Added a commented `tests/source_file_line_limit_overrides.txt` seed through universal noexist
  propagation, giving new consumers exact-path instructions while preserving existing approvals.
- Added support-directory and root-script-budget pytest gates, plus `tools/TOOLS_README.md` and
  reciprocal devel guidance. Extracted the Gitignore and reset-finish owners into focused modules.
- Added a complete `~/nsh` tools/devel usage survey covering 109 Git roots and defining the
  user-utility, developer-command, application-CLI, and importable-package boundaries.
- Recorded the settled audience and input/output placement rule in the design-decision ledger.

### Behavior or Interface Changes

- The source-file line-limit gate now automatically excludes Markdown beneath any
  `docs/active_plans/` or `docs/archive/` tree while retaining coverage for other source types.
- Rendered `.gitignore` now places canonical propagated blocks before the consumer-owned LOCAL
  block, preserving the LOCAL body while replacing stale recognized managed blocks.
- Reset removes consumer `pytest.ini` and uses one default-Yes finish decision for stage, commit,
  and push; config keeps push off by default and reports explicit publication terminal outcomes.

### Fixes and Maintenance

- Preserved consumer `.gitignore` rules beneath the previous full LOCAL heading and moved that
  section after canonical managed blocks, including repositories where it appeared in the middle.
- The final six-pass audit aligned archive wording, propagation-ledger navigation, support-tool
  examples, positive changelog guidance, and the noexist-routing test description.
- Rephrased source-line-limit guidance around the required exact-path format and individual
  approvals, following the repository's positive-prompting policy.
- Restored the shipped human-guidance and design-decision files to neutral consumer seeds and moved
  starter-template-specific records into `meta/docs/`.
- Removed the reset `pytest.ini` leak while retaining that template-owned configuration for the
  non-shipping meta suite; trusted file-path loaders and a template-owned propagation changelog
  writer remove the remaining support-directory import drift.
- Removed real Git repository, commit, remote, and push implementation checks from permanent
  pytest; the excluded reset E2E harness owns those workflows and now covers every publication
  terminal outcome.
- Removed unused `repolib.files` and `repolib.reset` compatibility facades and the dead
  `replace_managed_block` helper; callers now use the focused owning modules directly.
- Review corrections preserved heading-like LOCAL comments, qualified no-finish stage wording,
  restored source-line budgets, and removed Bandit temporary-literal findings.
- Six-pass audit corrections refreshed the reset quick start, Gitignore ownership and rendering
  documentation, plan and survey timing, and Python comment structure.
- The final audit documented universal `tools/` routing and exact deprecated-path cleanup, aligned
  live pytest commands with the repository environment, and corrected a legacy LOCAL docstring.

### Decisions and Failures

- Recorded adaptability and good-enough stopping points as complementary template-maintainer design
  guidance; the Gitignore transition uses a focused compatibility rule for observed prior banners.
- Keep the disk-budget `du` check in the base pytest lane; it measures the checkout and the
  vendored file is restored after deletion. Rejected a footer-comment gate as comment-only policy.
- Use exact source-line-limit overrides for individually approved external files; universal
  planning/archive exclusions belong in the gate.
- The audit remains active in `meta/docs/active_plans/audit/`; completed planning artifacts move to
  `docs/archive/` under the repository convention. Its current survey corrects stale historical
  no-runtime-import claims; consumer repairs remain with their maintainers.
- Support-directory imports unconditionally reject `tools`, `devel`, and `tests` package roots;
  documented flat devel and test helpers remain allowed, while tools scripts never import tool
  siblings. The root-script budget counts tracked `.py` and `.sh` files plus executable-shebang
  launchers; five or six report and seven or more fail.
- The six-pass audit left coordinated design work open for destination-first deprecated-path
  migration and duplicated propagation-changelog parsing.
- The usage survey classifies Graphify and TypeScript dependency refresh as developer commands,
  keeps HTML-to-PDF as a user tool, and identifies nine identical stale devel PDF copies for
  propagation cleanup.
- Keep one native application, library, or tool-helper package in a named root-level folder. Use
  `packages/` as the grouping layer when a repository contains multiple native products or
  packages.
- Moved the universal Graphify launcher and typed TypeScript dependency refresh into `devel/`.
  Propagation now retires their former `tools/` paths and the obsolete duplicate
  `devel/html_to_pdf.mjs` path.

### Developer Tests and Notes

- `source source_me.sh && pytest tests/ -q` passes all 2,225 permanent fast-lane tests.
- Accepted focused gates cover Gitignore rendering, reset configuration and interview outcomes,
  support-directory imports, root-script thresholds, documentation hygiene, typing, and pyflakes.
- A disposable current-candidate clone passed the complete LOCAL reset E2E matrix, including a
  synthetic bare-origin publication check and a local push-failure outcome; no remote host was
  contacted. A disposable TypeScript consumer confirmed moved-path cleanup and a clean second
  propagation pass. Diff checks passed.
