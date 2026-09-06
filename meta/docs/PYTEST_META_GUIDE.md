# Pytest meta guide

This template-only guide covers tests that validate the starter template. Use
[docs/PYTEST_STYLE.md](../../docs/PYTEST_STYLE.md) to decide whether a test belongs in the suite,
then use [docs/PYTEST_AUTHORING_GUIDE.md](../../docs/PYTEST_AUTHORING_GUIDE.md) to construct it.

## Meta test coverage

`tests/meta/test_*.py` covers the starter template itself: propagation plans, reset behavior,
manifests, and shared test infrastructure. `tests/meta/e2e/` holds real template workflows for the
explicit E2E lane. The `tests/meta/` tree stays with the starter template.

## Related vendored tests

The root `tests/` tree supplies universal test files to consumer repositories. A test under
`templates/<type>/tests/` ships with that repository type. The propagation plan routes each source
by its folder.

`tests/conftest.py` preserves consumer-owned pytest configuration through the propagation merge.
Use its `REPO_HYGIENE_FILTERS` registry for consumer-specific hygiene patterns; keep template tests
focused on universal behavior.

## Vendored footer

End every shipped template pytest module with this exact final line:

```python
# Vendored pytest file. Local changes can and will be overwritten.
```

The footer marks tests that propagation maintains and may refresh. Template-meta and consumer-local
tests retain their own ownership conventions.
