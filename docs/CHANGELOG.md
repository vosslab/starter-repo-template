## 2026-07-03

### Behavior or Interface Changes

- Added `all` as a recognized `REPO_TYPE` token for repos that consume every template family. `all`
  now appears in the repo-type manifest, the reset/bootstrap prompt, and the style docs. Routing for
  `all` aggregates the propagation plan for the existing typed repos so it receives universal files
  plus every typed overlay.

## 2026-07-03

### Fixes and Maintenance

- `templates/typescript/docs/FUN_VIBES_DESIGN_STYLE.md`,
  `templates/typescript/docs/PLAYFUL_TRAINING_GAME_STYLE.md`: fixed broken markdown links flagged by
  `tests/test_markdown_links.py`. Removed the dead `docs/GAME_USAGE.md` link (non-universal file that
  ships nowhere). Converted the `docs/REPO_STYLE.md` and `docs/MARKDOWN_STYLE.md` references from
  markdown links to backticked plain paths: those universal docs land flat in a consumer `docs/`, so
  a bare-sibling link is correct in consumers but unresolvable in the template tree where these files
  sit under `templates/typescript/docs/`. Plain-path text reads correctly in both layouts. Co-located
  sibling links (FUN_VIBES <-> PLAYFUL, PLAYWRIGHT_USAGE) stay as markdown links since they resolve in
  both places. `tests/test_markdown_links.py` now passes (36 files).

### Behavior or Interface Changes

- `docs/COLOR_CONTRAST_ACCESSIBILITY.md`: reframed as the generic WCAG contrast method doc (the
  canonical propagation source shipped to consumer repos) -- target ratio, contrast-ratio formula,
  calculator usage, online checkers, and the applicable rules. App-specific audited palette tables
  no longer live here; each consumer repo carries its own palette audit in a separate
  `docs/PALETTE_CONTRAST_AUDIT.md`.

## 2026-07-02

### Additions and New Features

- `devel/clean_build.sh`: new light build cleaner. Wipes build output, tool caches, and test
  artifacts (dist, _site, `*.tsbuildinfo`, .eslintcache, test-results, playwright-report,
  coverage, Python bytecode) while KEEPING dependency installs (node_modules, Rust target/) so
  the next build starts ab initio with no reinstall. In TypeScript repos this is the target of
  `npm run clean`. Ships universally via `devel/`.

### Behavior or Interface Changes

- `devel/dist_clean.sh`: reframed as the deep "restore to shippable state" cleaner (fresh-clone
  equivalent for a source release). It still removes node_modules and Rust target/, but no longer
  deletes `package-lock.json` -- the lockfile is committed and drives reproducible `npm ci`, so it
  belongs in a distribution. Header now points everyday build cleaning at `devel/clean_build.sh`.

### Removals and Deprecations

- `meta/propagation/manifests.yaml`: removed `dist_clean.sh` from `root_propagate_allowlist`. Both
  cleaners now live in `devel/` (universal propagation); no cleaner ships to the repo root.

## 2026-07-01

### Additions and New Features

- `docs/PYTEST_STYLE.md`: added a canonical `## Fixture policy` section. Setup is inline first:
  tests keep setup inline and close to the test, and use real repo files when the real file is
  the point. Separate test data or shared setup is reserved for cases where file shape, loader
  behavior, or shared test infrastructure is the thing under test. The policy covers both
  on-disk `tests/fixtures/` files and custom `@pytest.fixture` functions. `tmp_path` and the
  vendored `collect_report` autouse harness (at the canonical hygiene module shape) are named
  as the durable examples of shared infrastructure.

- `meta/docs/HUMAN_GUIDANCE.md`: recorded the fixture policy as intentional durable human
  guidance, a four-bullet entry pointing to the canonical section in
  `docs/PYTEST_STYLE.md`. Reworded "synthetic fixtures" / "fixture repos" to
  "synthetic repo trees" for consistency with the new policy language.

### Behavior or Interface Changes

- `docs/PYTEST_STYLE.md`: removed pro-fixture guidance ("Prefer fixtures for setup and shared
  resources", "fine and preferred for setup"). Test-structure bullets now read "Keep setup
  inline and close to the test." and "Use `tmp_path` for temp files." The "Is this a good
  pytest?" checklist no longer carries a fixture item; fixture nuance lives only in the new
  policy section.

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: reduced the "Node test fixture policy" to a
  two-paragraph inline-setup-first form with a plain-text pointer to the canonical section in
  `docs/PYTEST_STYLE.md`. Removed the fixture-creation bullets and the transitional example.

- `templates/typescript/docs/PLAYWRIGHT_USAGE.md`: removed the mention of a
  `tests/playwright/fixtures/` directory. Added one sentence separating Playwright's own
  "fixtures" framework feature from repo test-data design decisions.

- `docs/REPO_STYLE.md`: updated the `PYTEST_STYLE.md` index line to say "fixture policy".

- `tests/TESTS_README.md`: updated the `fixtures/` tree line to read "optional test data for
  loader/file-shape checks".

### Fixes and Maintenance

- `docs/CHANGELOG.md`: rotated per the changelog-rotation policy in `docs/REPO_STYLE.md`
  (file had reached 1038 lines). Moved the `2026-06-29` through `2026-06-12` day blocks into
  a new `docs/CHANGELOG-2026-06b.md` archive (next letter since `docs/CHANGELOG-2026-06a.md`
  already existed); the active file now keeps only the `2026-07-01` and `2026-06-30` blocks.
  Ran with `devel/rotate_changelog.py --dry-run` first, then `--yes`.

### Decisions and Failures

- The fixture policy covers both on-disk fixture data files and custom `@pytest.fixture`
  functions. Root cause: coding agents tend to overproduce fixtures, so the docs steer agents
  toward inline setup by default.

- This was a docs-only pass; no enforcement guard test was added. The vendored `collect_report`
  autouse harness stays as the named shared-infrastructure instance -- migrating it would be a
  separate code change across vendored tests.

- Applied an omission principle on human direction: fixture nuance lives only in the canonical
  `docs/PYTEST_STYLE.md` section; satellite docs say "inline setup first", point there, or say
  nothing, since each extra mention makes fixtures more salient to agents. Dropped "framework
  behavior" from the durable-use list as too broad; the canonical list is now "file shape,
  loader behavior, or shared test infrastructure".

### Developer Tests and Notes

- Verified with a full `pytest tests/` run: "1335 passed in 4.55s". A repo-wide categorized
  fixture-mention audit came back clean: every hit is policy text, a pointer, a durable-use
  mention, an actual path, a framework product term, or changelog history.
- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: documented the `tests/**/*.{ts,mts}` ESLint
  relaxation (`@typescript-eslint/no-floating-promises` and `no-console` off for `node:test`
  files, `src/` and `tools/` stay strict) and noted `tsx` as a required canonical
  devDependency for `check_codebase.sh` step 5.

## 2026-06-30

### Additions and New Features

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: reconciled dependency-version guidance with
  evidence from ten ~/nsh/TYPESCRIPT/ repos. Replaced stale frozen numbers ("Require 5.x",
  ">=9") with an apps-not-libraries `>={latest}` policy: high floors, `>=` always, `<` only
  for a confirmed incompatibility such as the typescript-eslint TS ceiling.
  `tools/sync_typescript_package_pins.py` is the refresh helper; lockfile regenerated forward;
  post-refresh validation runs through the normal gates.

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: canonicalized the entry point. `src/main.ts`
  or `src/main.tsx` is canonical; `src/init.ts` is legacy with a migrate direction
  (`build_github_pages.sh` accepts it as a fallback and prints a rename warning).

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: documented the esbuild policy: CLI default
  for the standard build, JS API only when a plugin requires it; loaders, multi-entry, and
  pre-build codegen variants covered. Elevated a command-architecture principle: named scripts
  are the interface, npm aliases are thin 1:1 mirrors.

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: added a node-test fixture policy: inline
  durable inputs directly; use fixtures for initial scaffold or a loader under test.
  Reconciled the stale pdf "removed" note.

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: added "Live demo / GitHub Pages" section
  documenting the Actions-from-dist deploy shape (`build_github_pages.sh` -> `dist/`,
  `dist/.nojekyll`, `dist/` as site root, root-level `deploy-pages.yml` seed a human moves
  into the workflows directory). Convention framed from the science-choose-adventure precedent.
  Added a `### Pages deployment shape` subheading and the live-URL README convention
  (link as `https://<owner>.github.io/<repo>/` just below the first paragraph).

- `templates/typescript/noexist/run_playwright_tests.sh`: new consumer-owned seed giving
  Playwright its own named front door. Runs preflight, optional `--build`, builds `dist/`
  as needed, forwards args to `npx playwright test`, relies on `playwright.config.ts`
  `webServer`. Not part of `check_codebase.sh`. Includes a bash 3.2-safe empty-array guard
  on the run line.

- `templates/typescript/tests/TESTS_TYPESCRIPT_README.md`: fully rewritten as a
  consumer-facing onboarding quickstart aimed at a new repo manager. Covers front-door
  scripts (`check_codebase.sh`, `run_playwright_tests.sh`), repo layout under `tests/`,
  four test tiers and their run order (pyflakes -> node --test -> Playwright -> E2E),
  ship-to-Pages workflow with the live-URL README convention, and common first-run
  failures. Removes template-internal history and overlay framing (the 2026-05-24
  removed-mirrors narrative, `propagate_style_guides.py`/overlay language, "vendored
  Python tests in this overlay"). The corrected Playwright front-door instruction
  pointing to `./run_playwright_tests.sh` is part of this rewrite.

### Behavior or Interface Changes

- `templates/typescript/noexist/package.json`: re-pointed `test:playwright` to
  `./run_playwright_tests.sh` and documented it in the front-door tables.

- `templates/typescript/noexist/package.json`: dependency-floor refresh; bumped 7 stale
  pins: `eslint` >=10.5.0 -> >=10.6.0, `typescript-eslint` >=8.61.0 -> >=8.62.1,
  `prettier` >=3.8.4 -> >=3.9.4, `playwright` >=1.60.0 -> >=1.61.1,
  `@playwright/test` >=1.60.0 -> >=1.61.1, `@types/node` >=25.9.3 -> >=26.0.1,
  `globals` >=17.6.0 -> >=17.7.0. Remaining 4 pins unchanged (already latest).

- `templates/typescript/noexist/package.json`: added top-level `allowScripts` block
  (`esbuild@0.28.1`, `fsevents@2.3.2`, `fsevents@2.3.3`) so esbuild's postinstall binary
  installs on a fresh `npm install`. Keys are version-pinned and maintained manually:
  after a sync that bumps esbuild or fsevents, re-apply the matching key by hand.

### Fixes and Maintenance

- `templates/typescript/docs/TYPESCRIPT_STYLE.md`: renamed `### Deployment shape` to
  `### Pages deployment shape` (3-6 word sentence-case heading rule; no in-doc anchor
  references to update).

### Decisions and Failures

- Doc-follows-experience stance: TYPESCRIPT_STYLE.md reconciliation was driven by evidence
  from real repos, not theory. Rules are updated to match observed working patterns rather
  than aspirational prescriptions. This stance is the standing policy for future doc updates.

- `deploy-pages.yml` ships at repo root (not under `.github/`): agents edit only repo-root
  files; a human completes the move into the workflows directory. Root placement is the
  convention so the seed ships cleanly from the template.

- `run_playwright_tests.sh` is untracked; the human stages it before committing.

- Validation: `pytest tests/` 1332 passed; `pytest tests/test_markdown_links.py` 32 passed.
