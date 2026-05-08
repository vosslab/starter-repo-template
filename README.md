# starter_repo_template
`starter_repo_template` is canonical bootstrap infrastructure for Python repositories that need consistent repository policy, Python style conventions, licensing boundaries, and test/lint scaffolding before project-specific code is added.

Only `README.md` and `docs/CHANGELOG.md` are intentionally repository-specific; every other file is designed to remain generic for downstream template users.

## Documentation

- [docs/REPO_STYLE.md](docs/REPO_STYLE.md): Repository structure, naming, versioning, dependency manifest, and licensing conventions.
- [docs/PYTHON_STYLE.md](docs/PYTHON_STYLE.md): Python implementation rules for formatting, structure, imports, argparse, and testing.
- [docs/PYTEST_STYLE.md](docs/PYTEST_STYLE.md): Pytest test-writing rules, commands, and failure triage.
- [docs/PLAYWRIGHT_USAGE.md](docs/PLAYWRIGHT_USAGE.md): Browser-driven tests using Playwright in `tests/playwright/`.
- [docs/E2E_TESTS.md](docs/E2E_TESTS.md): End-to-end test conventions; shell/Python E2E lives in `tests/e2e/`, browser E2E in `tests/playwright/`.
- [docs/MARKDOWN_STYLE.md](docs/MARKDOWN_STYLE.md): Markdown writing and formatting conventions for repository documentation.
- [docs/AUTHORS.md](docs/AUTHORS.md): Canonical authorship and attribution metadata for template maintenance.
- [docs/CHANGELOG.md](docs/CHANGELOG.md): Repository-specific history of updates to this template.

## Quick start

Run the fast test suite:

```bash
pytest tests/
```

Run non-browser end-to-end tests separately (see [docs/E2E_TESTS.md](docs/E2E_TESTS.md)):

```bash
bash tests/e2e/run_all.sh
```

Run browser-driven Playwright tests (see [docs/PLAYWRIGHT_USAGE.md](docs/PLAYWRIGHT_USAGE.md)):

```bash
node tests/playwright/test_example.mjs
```
