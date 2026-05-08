## 2026-05-08

### Additions and New Features

- Added **Finish the obvious** to `docs/REPO_STYLE.md` as a fifth core philosophy, clarifying that agents should continue through obvious safe follow-on work (defined by the plan, implied by the current task, or required to verify the work) and stop only at real blockers: missing information that cannot be inferred, a risky or irreversible action, or work that changes the user's requested outcome. Updated the section intro from "Four principles" to "Five principles". Pairs with "Atomic task decomposition": end-of-atomic-task is a checkpoint, not a stop, when the next atom is defined and unblocked.
- Added a `## Core philosophies` section to `docs/REPO_STYLE.md` naming four canonical principles that were previously implicit or absent in the repo: "Long-term over short-term", "Fix the design, not the symptom", "Fresh subagent per task", and "Atomic task decomposition". REPO_STYLE.md is the single canonical home for all four; sibling docs (`docs/PYTHON_STYLE.md`, `docs/PYTEST_STYLE.md`, `docs/TYPESCRIPT_STYLE.md`) thread short cross-references back rather than duplicating prose, and `AGENTS.md` carries only a one-line operational pointer. Working rule: one canonical definition, many short cross-references. The first two principles were already encoded implicitly (no try/except, no defensive defaults, "delete fragile tests rather than rewrite") but were never named; the two execution principles were entirely new. This set is intended to serve as the canonical foundation for later skill-corpus cleanup; downstream skill and propagated-doc work should apply these principles, not redefine them.
- Added a new `## AGENTS.md files` section to `docs/REPO_STYLE.md` codifying as a repo rule that `AGENTS.md` should be concise and operational (target 100-150 lines), focused on specific tasks/workflows/constraints, and must not host long philosophical prose or duplicated style guidance. Canonical explanations live in `docs/*.md` and are linked from `AGENTS.md`. Reason: concise `AGENTS.md` files help coding agents scan, prioritize, and follow instructions more reliably.

### Behavior or Interface Changes

- Added `tests/test_test_naming_conventions.py` to lint the test folder layout. Five rules: no `test_*.py` under `tests/playwright/` or `tests/e2e/` (collect_ignore would silently skip them, mismatching the name); Python files in `tests/e2e/` must use the `e2e_*.py` prefix; shell files there must use `e2e_*.sh`; any `.mjs` file with a Playwright import must live under `tests/playwright/`.
- Added `tests/TESTS_README.md` as a navigational quick-reference to the test folder layout, how to run each tier, the `collect_ignore` guard, and the difference between the Playwright tier and the non-browser E2E tier. Cross-links the deeper docs.
- Added `tests/conftest.py` (was empty) with `collect_ignore = ["e2e", "playwright"]` so pytest does not collect anything in those subtrees regardless of filename.

### Behavior or Interface Changes

- Added a one-line changelog-mode rule to `AGENTS.md` `## Coding Style`: standalone edits update `docs/CHANGELOG.md` directly; manager-driven multi-subagent work assigns one docs subagent to write a consolidated changelog entry, keeping the changelog coherent and avoiding parallel-edit churn.
- Reframed the intro of `## DO NOT HIDE BUGS WITH DEFAULTS` in `docs/PYTHON_STYLE.md` to name the umbrella principle ("fix the design, not the symptom") and link to its canonical home, so the section's role as the Python expression of that philosophy is on the page rather than implicit.
- Adopted a two-tier test layout convention to replace the prior `tests_e2e/` top-level folder. Browser-driven tests (Playwright today) live in `tests/playwright/`, with an optional `tests/playwright/e2e/` sub-grouping for full-path walkthroughs. Non-browser whole-system E2E (CLI round trips, build pipelines, shell or Python orchestration) lives in `tests/e2e/`. Reason: Playwright is a tool, E2E is a scope; not every Playwright test is end-to-end (a layout or single-interaction smoke check is browser-driven but not E2E). Naming the folders by execution model (browser vs. non-browser) keeps each test discoverable by what it actually is. Updated `docs/E2E_TESTS.md`, `docs/PLAYWRIGHT_USAGE.md`, `docs/PYTEST_STYLE.md`, `docs/PYTHON_STYLE.md`, `AGENTS.md`, and `README.md` to match.
- Pytest fast-lane safety now lives in active config: `tests/conftest.py` declares `collect_ignore = ["e2e", "playwright"]`. The filename conventions inside each subfolder remain as a readability layer on top of the active guard, not as the safety mechanism. Note: `collect_ignore` only affects pytest test collection; the repo's other lint tests (ASCII compliance, whitespace, pyflakes, etc.) still scan files in those subfolders via `git ls-files`.

### Fixes and Maintenance

- Extended `propagate_style_guides.py` to ship the new Playwright/test-tier infrastructure to consumer repos in three related changes. (1) Registered `tests/TESTS_README.md` (overwrite-always, matching its role as a centrally-maintained navigational README) by adding it to `TEST_SCRIPTS` with an inline comment explaining why a `.md` doc lives in a list otherwise full of test scripts. (2) Registered `devel/setup_playwright.sh` (added to `DEVEL_SCRIPTS`) and `tests/playwright/repo_root.mjs` (added to `TEST_SCRIPTS` as `playwright/repo_root.mjs` -- the subdir prefix is the new convention for tests/ subfolder entries, documented in `build_source_maps`). The test-script copy loop now mkdirs the destination parent so subdir entries land correctly. (3) Added `merge_conftest()` so the propagator injects `collect_ignore = ["e2e", "playwright"]` into each consumer's `tests/conftest.py` when missing -- mirroring the `merge_claude_md` pattern: the canonical line is added, but any custom content (imports, fixtures, hooks) the repo has is preserved. Empty conftests get the source verbatim; non-empty conftests with no `collect_ignore` token get the canonical block prepended; conftests that already have any `collect_ignore` line are left alone. New `updated_conftest` counter surfaces in the summary. Also updated `docs/PLAYWRIGHT_USAGE.md` to document `setup_playwright.sh` (quick install) and `tests/playwright/repo_root.mjs` (shared helper, do not edit per-repo), and updated `tests/TESTS_README.md`'s layout diagram to list `repo_root.mjs`. Verified via `--dry-run`: all 28 consumer repos receive the new files; 26 conftests get `collect_ignore` injected and 1 is created from scratch; source repo is correctly skipped throughout.
- Applied review-driven cleanup to the same change. In `propagate_style_guides.py`, removed an unreachable inner branch in `merge_conftest`'s empty-dest path (source always contains `collect_ignore`, so it can never equal an empty dest); switched the prepend path from `dest_text.lstrip()` to verbatim `dest_text` so a consumer repo's leading license header or blank lines survive the merge; added comments on the missing-dest early return, the source-repo abspath guard, and the subdir mkdir block. In `docs/PLAYWRIGHT_USAGE.md`, fixed a stale `collect_ignore = ["playwright"]` snippet (now `["e2e", "playwright"]`, matching `tests/conftest.py`) and replaced the repo-specific `cell_culture_game.html` example with a generic `index.html`. In `tests/playwright/repo_root.mjs`, added a comment explaining why `.trim()` is required (git rev-parse appends a trailing newline that would break path joins).

### Decisions and Failures

- Considered three competing layouts before settling on two distinct top-level folders. Rejected `tests_e2e/` (extra top-level), `tests/e2e/` as the single home for Playwright (conflated tool with scope, mislabeled smoke and layout checks as E2E), and `tests_browser/` (extra top-level). Adopted `tests/playwright/` plus `tests/e2e/` because each folder names what unifies its files. Initial dispatches landed `tests/e2e/` as the single Playwright home and had to be reverted before final docs landed.

## 2026-05-06

### Additions and New Features

- Added `docs/E2E_TESTS.md` documenting the convention that end-to-end tests live in `tests_e2e/` outside pytest. Pytest stays the fast lane under `tests/`; E2E scripts run via their own shell or Python runners. Cross-linked from `docs/PYTHON_STYLE.md` and `docs/PYTEST_STYLE.md`.

### Behavior or Interface Changes

- Established a hard boundary on `assert` placement: `assert` statements are forbidden in plain scripts and library modules and must live only in `tests/test_*.py` or in `tests_e2e/` end-to-end scripts. Reason: module-level asserts run at import time and slow script startup. Rewrote the `## ASSERT` section in `docs/PYTHON_STYLE.md` (removed inline-assert examples), added a "No `assert` in plain scripts" bullet to `## Common misconceptions`, and updated `docs/PYTEST_STYLE.md` `## Test structure` to allow asserts in `tests/` and `tests_e2e/` and to point slow tests at `docs/E2E_TESTS.md`.
- Added `@docs/E2E_TESTS.md` to `CLAUDE.md` so agents auto-load the E2E rule.
- Updated `AGENTS.md` to note that slow E2E tests live in `tests_e2e/` and run outside pytest.
- Updated `README.md` Quick Start to split fast (`pytest tests/`) and slow (`bash tests_e2e/run_all.sh`) test commands, and listed `docs/PYTEST_STYLE.md` and `docs/E2E_TESTS.md` in the Documentation section.
- Added a GitHub-link compatibility rule to `docs/MARKDOWN_STYLE.md` `## Links`: relative URLs must resolve against the file containing the link (not the repo root). Documented when to use the `docs/` prefix (linking from repo root into `docs/`) versus a bare filename (linking between siblings inside `docs/`).
- Removed an orphaned editor note from `docs/PYTHON_STYLE.md` that read "Here is a tightened version that keeps the rule and examples, without extra explanation."
- Split pytest-specific testing guidance out of `docs/PYTHON_STYLE.md` into the new `docs/PYTEST_STYLE.md`, matching the existing pattern of separate tool and language docs.
- Replaced duplicated pytest failure triage details in `docs/REPO_STYLE.md` with a link to `docs/PYTEST_STYLE.md`.
- Clarified `docs/PLAYWRIGHT_USAGE.md` so Playwright `.mjs` scripts live in `tests/`, can coexist with pytest `test_*.py` files, and follow the `docs/TYPESCRIPT_STYLE.md` testing convention.
- Updated `docs/PYTEST_STYLE.md` to make `conftest.py` the home for pytest setup and set `pytest tests/` as the default pytest command.
- Standardized repo-owned pytest command examples to use `pytest tests/`, while keeping `source source_me.sh && python...` for normal Python script execution.
- Documented `docs/CLAUDE_HOOK_USAGE_GUIDE.md` as a generated hook behavior reference instead of a repo style source of truth.
- Added `docs/PYTEST_STYLE.md` to the centrally maintained docs list in `docs/REPO_STYLE.md`.
- Added rule to `docs/PYTEST_STYLE.md` against creating permanent pytest files for temporary or scratch code (`_temp.*`, debugging scripts); `tests/` is reserved for code that stays in the repo.

## 2026-04-18

### Behavior or Interface Changes

- `propagate_style_guides.py` now auto-discovers `docs/*.md` files in the source repo and propagates them with overwrite semantics, mirroring the existing `test_*.py` auto-discovery in `tests/`. Picks up `docs/PLAYWRIGHT_USAGE.md` and `docs/TYPESCRIPT_STYLE.md` without needing to edit `STYLE_FILES`. `AUTHORS.md` and `CHANGELOG.md` are excluded via the new `AUTO_DISCOVER_DOCS_EXCLUDE` set so they remain per-repo.
- `docs/PLAYWRIGHT_USAGE.md` now directs Playwright test scripts to `tests/` at the repo root instead of `devel/`, matching `docs/TYPESCRIPT_STYLE.md` and `docs/REPO_STYLE.md` pytest conventions. `devel/` is reserved for one-off developer tools, not bulk test files. Python and Node test files may coexist in `tests/`.
- Expanded the Install section of `docs/PLAYWRIGHT_USAGE.md` to show `npm init -y` and `npm install --save-dev playwright` for repos that do not yet have a `package.json`, so setup from a fresh clone is explicit.

## 2026-04-01

### Additions and New Features

- Added "Common misconceptions" section at the top of `docs/PYTHON_STYLE.md` highlighting frequently violated rules for AI agents.
- Added "DO NOT HIDE BUGS WITH DEFAULTS" section to `docs/PYTHON_STYLE.md` covering `dict.get()` misuse, `value or fallback` patterns, and silent exception swallowing.
- Added "IMPORT REQUIREMENTS" section to `docs/PYTHON_STYLE.md` documenting that all imports must come from stdlib, repo-local modules, or declared pip dependencies.
- Added explicit ban on relative imports (`from . import`) to the IMPORTING section of `docs/PYTHON_STYLE.md`.

### Behavior or Interface Changes

- Clarified shebang rules in `docs/PYTHON_STYLE.md` to explicitly state shebangs belong only on runnable scripts with main guards, not on library modules, test files, or helpers.

## 2026-03-13

### Additions and New Features

- Added `docs/CLAUDE_HOOK_USAGE_GUIDE.md` to `STYLE_FILES` in `propagate_style_guides.py` so it is copied to target repos.
- Added `@docs/CLAUDE_HOOK_USAGE_GUIDE.md` reference to template `CLAUDE.md`.

### Behavior or Interface Changes

- Changed `propagate_style_guides.py` to merge `CLAUDE.md` instead of overwriting, preserving repo-specific `@` reference lines in target repos.

## 2026-02-25

### Fixes and Maintenance

- Fixed `devel/commit_changelog.py` to detect staged (`git add`) changelog changes by falling back to `git diff --cached` when the unstaged diff is empty.

## 2026-02-22

- Updated `docs/REPO_STYLE.md` to require consistent section headings for each changelog day block (`Added`, `Changed`, `Fixed`, `Failures`, `Decisions`) and to keep empty sections with `- None.`.
- Updated `docs/REPO_STYLE.md` section names for changelog day blocks to `Additions`, `Updates`, `Removals`, `Failures`, and `Validations`.
- Updated `docs/REPO_STYLE.md` changelog day template to also require `Fixes` and `Decisions` sections.
- Updated `docs/REPO_STYLE.md` changelog policy language: empty categories are optional, every entry must be categorized, entries are never removed (only rephrased), and day category names are now the six longer labels.

## 2026-02-20

- Added `tests/test_init_files.py` to enforce surface-level `__init__.py` style rules from `docs/PYTHON_STYLE.md`, including checks for non-docstring implementation, imports, exports/maps, global assignments, and `__version__` assignments.
- Scoped `tests/test_init_files.py` to analyze only substantial `__init__.py` files and write violations to `report_init.txt` with stale report cleanup at test startup.
- Updated `propagate_style_guides.py` and `.gitignore` to include `test_init_files.py`.
- Simplified gitignore management to require `report_*.txt` and clean up legacy per-report entries in `propagate_style_guides.py`.
- Updated `tests/test_init_files.py` so the no-`__init__.py` case reports pass instead of skip.
- Updated `propagate_style_guides.py` to skip propagating `source_me.sh` into repositories that are already present on `PATH` (for example `junk-drawer`).
- Optimized `tests/test_pyflakes_code_lint.py` to run `pyflakes` once per pytest session and reuse indexed results for per-file tests, preserving one-dot-per-file output while reducing runtime overhead.
- Updated `docs/REPO_STYLE.md` to clarify that changelog entries should capture notable failures and key implementation choices, not only successful changes.

## 2026-02-19

- Added `tests/test_import_dot.py` to fail on relative from-import statements such as `from . import x` and `from .module import x`.
- Updated `propagate_style_guides.py` so `test_import_dot.py` is included in propagated test scripts.
- Updated `tests/test_import_star.py` and `tests/test_import_dot.py` to write per-test report files (`report_import_star.txt` and `report_import_dot.txt`), remove stale reports at test start, and include report paths in assertion failures.
- Renamed `tests/test_import_requirements.py` output to `report_import_requirements.txt` (from `report_imports.txt`) while preserving existing report generation and stale-file cleanup behavior.
- Added import report files to `.gitignore` and `propagate_style_guides.py` required ignore entries: `report_import_star.txt`, `report_import_dot.txt`, and `report_import_requirements.txt`.
- Restored per-file parametrized execution in `tests/test_import_star.py` and `tests/test_import_dot.py` so pytest shows one dot/failure per scanned file while still writing per-test report files.

## 2026-02-16

- Fixed false positives in `tests/test_shebangs.py` where Rust inner attributes (`#![...]`) were misidentified as shebangs, causing `.rs` files to be flagged under `shebang_not_executable`.

## 2026-02-14

- Trimmed `propagate_style_guides.py` to stop editing existing `AGENTS.md` files in target repositories while keeping a no-overwrite bootstrap copy when `AGENTS.md` is missing.
- Added a no-overwrite style file category in `propagate_style_guides.py` so `AGENTS.md` and `docs/AUTHORS.md` are copied only when absent and never updated in-place.
- Updated `propagate_style_guides.py` style destination routing so `CLAUDE.md` is propagated with overwrite to repo root while standard style guides continue to copy into `docs/`.
- Refactored `propagate_style_guides.py` file lists to explicit `(source_name, target_path)` mappings for overwrite and no-overwrite categories, removing special-case destination branching.
- Simplified `propagate_style_guides.py` file lists again to target-relative paths only, deriving source filenames from basename while preserving overwrite/no-overwrite behavior.
- Updated `propagate_style_guides.py` default source lookup/help text to use `<base>/starter_repo_template` instead of `<base>/junk-drawer`.
- Clarified in `README.md` that only `README.md` and `docs/CHANGELOG.md` are repo-specific, while other files are intended to remain generic template infrastructure.
- Standardized `README.md` with a concise infrastructure-focused overview, curated `docs/` links, and a verifiable quick-start test command.
- Updated `AGENTS.md` to direct AI agents to run commands with `bash -lc` (not Zsh) so `source_me.sh` works with expected shell semantics.
