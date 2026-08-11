# Human guidance

Durable preferences and stable decisions for agents working in this repo.
Keep entries current. Move outdated entries to `docs/CHANGELOG.md`.

See [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md) for repo-wide conventions.

## Documentation ownership

- [REPO_TYPE.md](REPO_TYPE.md) owns marker format, names, inheritance, and
  multi-type behavior.
- [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md) owns repository conventions.
  Keep type-marker rules out of it; the shared `REPO_` prefix does not make the
  two documents interchangeable.

## Hygiene discovery ownership

- Top-level hygiene tests select tracked files through
  [tests/file_utils.py](../../tests/file_utils.py) `discover_files`; they do not
  maintain local discovery or exclusion-prefix copies.
- Universal skip directories belong in [tests/file_utils.py](../../tests/file_utils.py).
  Repo-specific exclusions belong in [tests/conftest.py](../../tests/conftest.py)
  `REPO_HYGIENE_FILTERS`.
- The line-limit gate keeps only its exact-path manager approval list because
  that policy is specific to the gate.

## Plan and test gates

- Review implementation plans against [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md),
  [docs/PYTEST_STYLE.md](../../docs/PYTEST_STYLE.md),
  [tests/TESTS_README.md](../../tests/TESTS_README.md),
  [devel/DEVEL_README.md](../../devel/DEVEL_README.md), and relevant language guides.
- Ground acceptance gates in product behavior, repository policy, or measured evidence.
  Use byte equality, pixel equality, and timing thresholds only when exactness or
  performance is an explicit contract supported by a realistic baseline.
- Classify implementation probes separately from permanent tests. Keep useful
  one-time checks during the rebuild, then remove them before handoff.
- Apply the permanent-test checklist in
  [docs/PYTEST_STYLE.md](../../docs/PYTEST_STYLE.md). Permanent pytest stays
  deterministic, offline, fixture-light, fast, and behavior-focused. When in
  doubt, remove the test.

## Shebang semantics

- WeBWorK `.conf` files use an exact first-line `#!perl` configuration marker.
  Shebang hygiene treats that marker as data, not an OS interpreter directive.

## Propagation routing model

- File location is the primary routing determinant. Agents use location first;
  per-file overrides only when location cannot express the rule.
- Every file under `docs/`, `tests/`, and `devel/` ships universally to all
  consumer repos (overwrite bucket by default).
- Every file under `templates/<type>/` ships to consumer repos of that type,
  at its consumer-relative path (e.g. `templates/python/foo.py` ships as `foo.py`).
- `docs/PYTHON_STYLE.md` ships to all repo types. It is a universal doc.
- `pip_requirements-dev.txt` ships universally (root `root_propagate_allowlist`
  + `universal_noexist`). `pip_requirements.txt` is python-only noexist
  (`templates/python/noexist/pip_requirements.txt`).

## ROUTING_OVERRIDES holds only exclude_repos

- `ROUTING_OVERRIDES` in `meta/propagation/manifests.yaml` holds only one
  exception: `exclude_repos` for `docs/CLAUDE_HOOK_USAGE_GUIDE.md` (blocks
  the mirror from shipping back to its source repo `claude-code-permissions-hook`).
- Do not add `language`, `bucket`, or `requires_repo_file` fields. Those were
  removed when location-based routing replaced per-file gates.
- When a new language-specific file is needed, put it under the correct
  `templates/<type>/` folder rather than adding a `ROUTING_OVERRIDES` entry.

## Conditional overlays (_folder convention)

- An underscore folder under `templates/<type>/` (e.g. `templates/python/_ci/`)
  is a conditional overlay. The base walk skips it; a `conditional_overlays`
  manifest rule enables it per consumer.
- Conditional overlay rules live in `meta/propagation/manifests.yaml` under
  `conditional_overlays: <type>: <overlay_name>: {when, path, description}`.
- The only supported `when` verb is `has_file`: the overlay ships when the named
  file exists at the consumer repo root.
- The mechanism currently has no live overlays; `conditional_overlays` is empty.
- Prefer conditional overlays over `requires_repo_file` in `ROUTING_OVERRIDES`.

## PyPI child type

- `pypi` is a real child repo type of `python`, declared by `pypi: python` in
  `repo_type_inherits`.
- PyPI-only files live under `templates/pypi/` and ship through the `pypi` type.
- The legacy reset answer `project_type: python` plus `pypi: true` is normalized
  to the canonical `pypi` marker.

## Manifests single source of truth

- All propagation manifests live in `meta/propagation/manifests.yaml`.
- `repolib/manifests.py:load_manifests()` reads the YAML at import time with
  `yaml.safe_load` and returns the correct Python types.
- `repolib/model.py` assigns loaded values to its module-level public names.
- Edit `meta/propagation/manifests.yaml` to change any manifest. Do not add
  inline literals back to `repolib/model.py`.

## reset_repo.py design

- `reset_repo.py` is the bootstrap entry point for new consumer repos.
- Interactive interview is the human default: the script asks project type, license,
  PyPI intent, stage, and commit choices at the terminal.
- CLI surface is minimal: `-h`, `--dry-run`, and `--config <file>`. The `--force` and
  `--yes` flags were removed; `--force` had no use case and `--yes` is replaced by
  `--config` for non-interactive runs.
- `--config <file>` is the testing/reproducibility interface: a JSON answer file
  drives a non-interactive reset for e2e and subagent testing. It is not required for
  normal human use. Required JSON keys: `project_type` and `code_license`. Optional
  keys with defaults: `docs_license` (CC-BY-4.0), `pypi` (false; legacy Python-to-PyPI promotion),
  `stage` (true), `commit` (false). Short aliases are accepted for both required keys.
- Folder-name guard: reset refuses to run when the repo root basename is exactly
  `starter-repo-template`. This protects the template development checkout. Guard is
  folder name only; no remote or origin inspection (remote-slug detection is fragile
  for freshly cloned consumer repos that have not yet renamed their remote).
- Running outside a git repository exits with a clear message instead of a raw
  subprocess traceback.
- Do not add automation flags for decisions the user makes once at repo creation.

## E2E harness design

- `tests/meta/e2e/e2e_reset_routing.py` clones the template into consumer-named `/tmp` dirs
  (e.g. `/tmp/my_project_python/`) so each test case is isolated and ephemeral.
  Template-meta: lives under `tests/meta/e2e/`; never propagates to consumers; removed by reset.
- LOCAL mode (default): offline, clones committed local history only. Uncommitted
  working-tree changes are not exercised; commit before running LOCAL if you need the
  harness to see them.
- REMOTE mode (opt-in via `remote` argument): GitHub HTTPS clone (read-only); exercises
  what a consumer receives from origin/main. New code must be pushed to origin/main by the
  human first; REMOTE clones whatever is already there.
- Each case uses an ephemeral per-case JSON config; verified against the live
  propagation engine (oracle) plus reset-specific anchor checks.
- `tests/meta/e2e/run_all.sh` iterates all `e2e_*` scripts under `tests/meta/e2e/`
  and reports pass/fail; offline only (LOCAL mode). Also template-meta.

## Tests follow live config

- Tests assert on propagation engine behavior using synthetic repo trees; they
  do not duplicate manifest constants inline.
- Preferred pattern: call `repolib.manifests.load_manifests()` or inspect
  `repolib.model.*` constants rather than hardcoding expected sets.
- Routing assertions use `compute_propagation_plan` on synthetic repo trees so
  they reflect the live config automatically when manifests change.

## Test fixture policy

- Use inline setup first. For fixture cases, see the Fixture policy in [docs/PYTEST_STYLE.md](../../docs/PYTEST_STYLE.md).

## Prefer rule-based routing over per-file customization

- The goal is zero per-file routing entries in `ROUTING_OVERRIDES`.
- When a file needs special handling, exhaust location-based options first:
  move it to the correct folder or create a `_folder` conditional overlay.
- Only fall back to `ROUTING_OVERRIDES` for exceptions that cannot be expressed
  by directory placement (currently: `exclude_repos` only).
