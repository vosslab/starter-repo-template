# TypeScript test suite

These tests ship to every `REPO_TYPE=typescript` consumer via `propagate_style_guides.py`. They enforce the canonical TS toolchain shape (tsconfig fields, ESLint config, package.json scripts/deps) and act as the consumer-side fast lane for type checking + lint.

## Skip behavior

Every `.py` test in this folder reads `REPO_TYPE` at the repo root:
- Marker missing OR token != `typescript` -> test skips silently.
- Marker == `typescript` AND `tsconfig.json` missing -> test FAILS (TS-typed repo without tsconfig is broken).
- Marker == `typescript` AND `npx` not installed -> test skips (local-dev-without-node case; CI must install Node).

## Files

| File | What it checks |
|---|---|
| `test_typescript_tsc.py` | Runs `npx tsc --noEmit -p tsconfig.json`. Asserts exit 0. Catches type errors. |
| `test_typescript_eslint.py` | Runs `npx eslint --max-warnings 0 'src/**/*.ts' 'tests/**/*.ts' '*.ts'`. Asserts exit 0. Zero-warning gate. |
| `test_tsconfig_canonical.py` | Loads `tsconfig.json`, asserts each canonical `compilerOptions` field is present with the canonical value (target=es2020, module=esnext, strict=true, noUncheckedIndexedAccess=true, etc.). Allows extra fields; rejects regressions in the strict set. |
| `test_package_json_schema.py` | Loads `package.json`, asserts required top-level keys (`name`, `type`, `scripts`, `devDependencies`); asserts `type == "module"`; asserts canonical scripts (`build`, `serve`, `check`, `clean`, `typecheck`, `lint`, `format:check`, `test:node`) present; asserts canonical devDeps (`eslint`, `@eslint/js`, `typescript-eslint`, `globals`, `typescript`, `esbuild`, `prettier`, `@playwright/test`) present. Superset OK. |
| `test_eslint_config_present.py` | Asserts `eslint.config.js` exists at repo root (canonical flat config); asserts `.eslintrc.cjs` does NOT exist (legacy form rejected); asserts ESLint devDeps present in `package.json`. |
| `test_smoke.mjs` | Minimal Node test (asserts `1 + 1 == 2`) so `node --test tests/test_*.mjs` has at least one passing test on a freshly-bootstrapped repo. Delete or replace once real Node tests exist. |

## `tsconfig.json` (sibling file at template root)

Canonical strict TypeScript config shipped to every TS consumer. Test `test_tsconfig_canonical.py` enforces its content (per-field). Edit the canonical at `templates/typescript/tsconfig.json` in this template repo; propagation overwrites at consumers.

## Run locally

From a TS-typed consumer repo:

```bash
source source_me.sh && pytest tests/test_typescript_*.py tests/test_tsconfig_canonical.py tests/test_package_json_schema.py tests/test_eslint_config_present.py
```

For the Node smoke + any real Node tests:

```bash
node --test 'tests/test_*.mjs'
```

Or the combined gate (preferred):

```bash
bash check_codebase.sh
```

## Adding a new TS test

Drop a `test_<name>.py` in `templates/typescript/tests/` here. It propagates to every TS consumer on next `propagate_style_guides.py` run. Follow the skip-behavior pattern at the top of the existing tests.

For a new Node test, drop `test_<name>.mjs` in the same folder.
