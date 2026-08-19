## 2026-08-19

### Behavior or Interface Changes

- Updated `tools/graphify_map_repo.sh context` output to be strictly Graphify-focused.
  The context now defines what Graphify is, the key commands for query/explain/affected/path,
  and a manager delegation template that uses Graphify evidence to minimize prompt/context
  size when assigning subagent tasks.

## 2026-08-12

### Behavior or Interface Changes

- `templates/rust/docs/RUST_STYLE.md`: defined a security-focused Cargo version policy. New direct
  dependencies use the manager-selected repository form: wildcard `*` for every stable version,
  or `>=LATEST` for an explicit security floor with newer versions eligible. Dependency refreshes
  advance major, minor, and patch components. The guide treats application repositories as the
  normal case, keeps `Cargo.lock` as their exact tested graph, records the future crates.io wildcard
  constraint, and reserves exact requirements for documented temporary constraints.
- Set the Rust toolchain policy to the latest stable compiler with the current manifest floor
  written as `rust-version = "1.97.1"`, matching the installed
  `rustc 1.97.1 (8bab26f4f 2026-07-14)`. Documented that Cargo requires a bare version, so
  `rust-version = ">=1.97.1"` is invalid, and that this MSRV field does not update dependencies.

### Fixes and Maintenance

- Reformatted the Rust examples in `templates/rust/docs/RUST_STYLE.md` with rustfmt's four-space
  indentation instead of tabs, aligning the examples with the guide's own formatting rule.
- Rephrased Rust directives around the desired implementation behavior: explicit imports, safe
  Rust boundaries, concrete library errors, lifetime elision, and behavior-focused tests.
- Baked the repository's source-file ceiling into `templates/rust/docs/RUST_STYLE.md`: use 999
  physical lines as the inclusive maximum and keep generic crate roots, module roots, and test
  indexes as concise routing stubs for descriptively named implementation files.
- Applied the six-pass audit corrections: added a canonical Rust filename map, identified
  `docs.rs` as the hosted documentation service, directed reusable binary behavior into focused
  library modules, reserved generic Cargo filenames for thin entry stubs, made `Cargo.toml` the
  direct source for the selected dependency form, and expressed the quick-start and public-
  documentation rules as positive implementation guidance.
- Condensed the new toolchain and dependency policy to its executable contract: current compiler,
  latest stable direct dependencies, the manager-selected `*` or `>=LATEST` form, lockfile refresh,
  and Cargo gates.
- Aligned the guide with the `rust-code-expert` reference workflow. Existing-project work now names
  the owning crate and module, callers, features, target triple, error contract, and value flow;
  greenfield work starts with domain types plus one success and error test. The completion baseline
  now includes `cargo fmt --check`, `cargo check`, `cargo test`, and Clippy, followed by the matching
  CLI, Tokio, unsafe/FFI, PyO3, or performance oracle.
- Completed a whole-document Rust review against the skill references and current official sources.
  Corrected modern module paths and the private-module `pub use` example; narrowed Python-style
  carryover to repo philosophies; made `Result`, panic, library/application errors, and CLI testing
  precise; added enum/trait/generic selection and explicit async task ownership; updated unsafe for
  2024 extern blocks and unsafe attributes; and added narrow FFI adapters with links to the focused
  Python and WebAssembly guides at their relevant boundaries.
- Split Python binding guidance into `templates/rust/docs/RUST_PYO3_STYLE.md` so
  `RUST_STYLE.md` stays focused on Rust. The new guide owns PyO3 boundary architecture, extension
  and embedding shapes, `cdylib`/`rlib`, current maturin linking, ABI selection, interpreter-bound
  values, domain-error to Python-exception translation, task ownership, and Python integration
  proof. The Rust guide retains the general FFI contract and links to the focused guide.
- Added `templates/rust/docs/RUST_WASM_STYLE.md` for the browser and WASI boundary. It covers
  target and tool selection, a Rust-core/thin-export architecture, `wasm-bindgen` API design,
  JavaScript ownership and error translation, browser and WASI validation, size and performance
  measurement, and current project-owned wasm-bindgen references. `RUST_STYLE.md` links exactly
  twice to each focused guide: at the general FFI boundary and at the foreign-caller proof point.
- Rotated `docs/CHANGELOG.md` after it crossed 1000 lines. Kept the two newest day blocks active
  and moved the 2026-08-07 through 2026-06-30 blocks into `docs/CHANGELOG-2026-08a.md`.

### Developer Tests and Notes

- Confirmed the documented compiler floor against
  `rustc 1.97.1 (8bab26f4f 2026-07-14)`.
- After the six-pass audit corrections, Markdown links, ASCII compliance, whitespace, and the
  source-file line limit pass: 501 targeted tests. The complete `pytest tests/` suite passes with
  1717 tests.

## 2026-08-10

### Additions and New Features

- Added the universal `tests/test_source_file_line_limit.py` hygiene gate. It scans Git-tracked
  authored source files through `file_utils.discover_files`, accepts 999 physical lines, fails at
  1000, and writes the standard complete violation report. Scope includes common programming,
  build, query, template, and authored-document formats (including `.md`) plus conventional names
  such as `Makefile` and `Dockerfile`; generic `.txt`, data, config, generated, notebook, and binary
  formats remain outside the gate.
- Added the optional manager-owned `tests/source_file_line_limit_overrides.txt` contract for exact
  paths to tracked sources outside local control, such as a downloaded normative specification.
  Blank lines and full-line comments are accepted; globs and paths escaping the repo are rejected.
  The propagation manifest marks the file as template-meta so one repo's approvals never ship to
  another repo.

### Behavior or Interface Changes

- `devel/bump_version.py patch` now prepares the next patch release. It treats repo versions such
  as `26.08` and Cargo versions such as `26.8.0` as the same release, previews the affected files,
  and uses plain `Current version` and `Next version` labels.
- Shortened source file line-limit report entries to `path: N lines`; the report header carries
  the shared policy context once.
- Promoted PyPI packaging from the file-presence-driven `templates/python/_pypi/` conditional
  overlay to the real `pypi` repo type under `templates/pypi/`. The inheritance declaration
  `pypi: python` gives packages the complete Python rule set plus publishing-specific files.
  Declaring `python` selects Python tooling; declaring `pypi` adds publishing files.
  Legacy reset configs using `project_type: python` with `pypi: true` normalize to the canonical
  `pypi` marker.

### Fixes and Maintenance

- Split repository classification from repository style: `meta/docs/REPO_TYPE.md` now owns
  marker format, names, inheritance, and multi-type behavior, while `docs/REPO_STYLE.md`
  contains no type-marker contract. Updated human-guidance and propagation references.
- Recorded plan-gate guidance: ground exactness and performance requirements in measured product
  contracts, separate one-time implementation probes from permanent tests, and apply the
  permanent-test checklist before adding suite coverage.
- `tests/test_shebangs.py` now treats exact `#!perl` lines in `.conf` files as WeBWorK
  configuration markers rather than executable shebangs, covered with inline `tmp_path` input.
- Added template-local pytest import paths so `pytest tests/` resolves the template's helper
  modules without adding `PYTHONPATH` or custom commands to the downstream `source_me.sh` seed.
- Removed the fragile reset self-propagation pytest; the whole reset workflow remains in the
  clone-based E2E runner.
- Removed the unused `repolib.files.safe_walk` helper and corrected release-routing documentation.
- Condensed the source-file-size rules to the boundary, scope owner, and override path.
- Reduced `reset_repo.py` to an executable CLI stub. Filesystem mutation and orchestration now
  live in `repolib/reset.py`, while interview and JSON-answer resolution live in
  `repolib/reset_answers.py`.
- Split propagation planning from file mutation: `repolib/files.py` retains file and merge
  operations, and `repolib/plan.py` owns plan construction, typed overlays, and source buckets.
- Split the version command into the small `devel/bump_version.py` CLI,
  `devel/version_lib.py` for shared version behavior, and `devel/version_files.py` for repository
  discovery and updates. `make_release.py` and the PyPI publisher now use the same version library.
- Split PyPI authentication/repository resolution and console/subprocess helpers into
  `pypi_auth.py` and `pypi_support.py`. All three files propagate together into a package repo's
  `devel/` directory and use normal sibling imports; template tests provide those source overlay
  paths through a test-only `PYTHONPATH`.
- Extracted shared overlay routing into `repolib/plan.py`.
- Extracted reset cleanup and completion phases into focused helpers.
- Clarified reset answer parsing and aligned the extracted helpers with repository style.

### Decisions and Failures

- Untracked `local-only/` reference books need no path exception because hygiene discovery already
  uses `git ls-files`. The source selector deliberately does not exclude that directory, preventing
  it from becoming a loophole for tracked oversized code.

### Developer Tests and Notes

- Added an explicit boundary case proving that 999 lines passes and 1000 lines fails.
- Added an inline `tmp_path` behavior case proving the optional override list loads an exact path
  while ignoring comments and blank lines.
- The boundary cases pass, and direct pyflakes validation is clean. The complete new gate reports
  four existing source debts instead of weakening the rule: `devel/bump_version.py` (1329),
  `repolib/files.py` (1332), `reset_repo.py` (1126), and
  `templates/python/_pypi/devel/submit_to_pypi.py` (1349).
- Resolved all four debts above without overrides. The largest replacement module is now
  `templates/pypi/devel/submit_to_pypi.py` at 988 lines. The complete pytest suite passes with
  1727 tests and 2 environment-dependent skips; the standalone real-Git release E2E also passes.
- Exported the staged index into an isolated temporary Git repository and completed a live `pypi`
  reset. The canonical marker, Python inheritance, PyPI support trio, shared version modules, and
  source-release helper were present afterward; template/repolib/reset infrastructure was removed.
