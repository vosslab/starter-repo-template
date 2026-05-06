# starter_repo_template
`starter_repo_template` is canonical bootstrap infrastructure for Python repositories that need consistent repository policy, Python style conventions, licensing boundaries, and test/lint scaffolding before project-specific code is added.

Only `README.md` and `docs/CHANGELOG.md` are intentionally repository-specific; every other file is designed to remain generic for downstream template users.

## Documentation

- [docs/REPO_STYLE.md](docs/REPO_STYLE.md): Repository structure, naming, versioning, dependency manifest, and licensing conventions.
- [docs/PYTHON_STYLE.md](docs/PYTHON_STYLE.md): Python implementation rules for formatting, structure, imports, argparse, and testing.
- [docs/PYTEST_STYLE.md](docs/PYTEST_STYLE.md): Pytest test-writing rules, commands, and failure triage.
- [docs/E2E_TESTS.md](docs/E2E_TESTS.md): End-to-end test conventions; slow tests live in `tests_e2e/` outside pytest.
- [docs/MARKDOWN_STYLE.md](docs/MARKDOWN_STYLE.md): Markdown writing and formatting conventions for repository documentation.
- [docs/AUTHORS.md](docs/AUTHORS.md): Canonical authorship and attribution metadata for template maintenance.
- [docs/CHANGELOG.md](docs/CHANGELOG.md): Repository-specific history of updates to this template.

## Quick start

Run the fast test suite:

```bash
pytest tests/
```

Run end-to-end tests separately (see [docs/E2E_TESTS.md](docs/E2E_TESTS.md)):

```bash
bash tests_e2e/run_all.sh
```
