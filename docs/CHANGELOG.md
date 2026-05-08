## 2026-05-08

### Additions and New Features

- Added `tests/test_test_naming_conventions.py` to lint the test folder layout. Five rules: no `test_*.py` under `tests/playwright/` or `tests/e2e/` (collect_ignore would silently skip them, mismatching the name); Python files in `tests/e2e/` must use the `e2e_*.py` prefix; shell files there must use `e2e_*.sh`; any `.mjs` file with a Playwright import must live under `tests/playwright/`.
- Added `tests/TESTS_README.md` as a navigational quick-reference to the test folder layout, how to run each tier, the `collect_ignore` guard, and the difference between the Playwright tier and the non-browser E2E tier. Cross-links the deeper docs.
- Added `tests/conftest.py` (was empty) with `collect_ignore = ["e2e", "playwright"]` so pytest does not collect anything in those subtrees regardless of filename.

### Behavior or Interface Changes

- Adopted a two-tier test layout convention to replace the prior `tests_e2e/` top-level folder. Browser-driven tests (Playwright today) live in `tests/playwright/`, with an optional `tests/playwright/e2e/` sub-grouping for full-path walkthroughs. Non-browser whole-system E2E (CLI round trips, build pipelines, shell or Python orchestration) lives in `tests/e2e/`. Reason: Playwright is a tool, E2E is a scope; not every Playwright test is end-to-end (a layout or single-interaction smoke check is browser-driven but not E2E). Naming the folders by execution model (browser vs. non-browser) keeps each test discoverable by what it actually is. Updated `docs/E2E_TESTS.md`, `docs/PLAYWRIGHT_USAGE.md`, `docs/PYTEST_STYLE.md`, `docs/PYTHON_STYLE.md`, `AGENTS.md`, and `README.md` to match.
- Pytest fast-lane safety now lives in active config: `tests/conftest.py` declares `collect_ignore = ["e2e", "playwright"]`. The filename conventions inside each subfolder remain as a readability layer on top of the active guard, not as the safety mechanism. Note: `collect_ignore` only affects pytest test collection; the repo's other lint tests (ASCII compliance, whitespace, pyflakes, etc.) still scan files in those subfolders via `git ls-files`.

### Fixes and Maintenance

- Fixed `propagate_style_guides.py` so the new `tests/TESTS_README.md` actually ships to consumer repos. The file was added earlier today but not registered with the propagator, so a `propagate_style_guides.py` run would have left consumer repos without it. Added `'TESTS_README.md'` to `TEST_SCRIPTS` (overwrite-always semantics, matching its role as a centrally-maintained navigational README) with an inline comment explaining why a `.md` doc lives in a list otherwise full of test scripts. Verified via `--dry-run` that 28 consumer repos receive the file and the source repo is correctly skipped.

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
