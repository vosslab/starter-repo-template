# TypeScript modernization plan

## Context

TypeScript repositories need one reliable local maintenance command: update to current
dependencies, resolve security findings, validate code and builds, and prove the resulting
lockfile installs. GitHub Pages publishes the locally tested result. This plan is approved
for implementation in starter-repo-template; consumer repositories are not modified.

## Objectives

- Use TypeScript 7 with typed Oxlint, retaining Prettier and existing build tools.
- Keep and improve `sync_typescript_package_pins.py` with repository-scoped selection.
- Maintain current registry dependencies and overrides with open-ended `>=` minimums.
- Provide `update_dependencies.sh` as the agent's complete local maintenance entry point.
- Synchronize package release versions through the existing version command.
- Keep Pages deployment simple and establish canonical GitHub Pages guidance.

## Design philosophy

Use existing commands once each. Shell orchestrates; Python handles substantive branching.
Keep offline policy checks separate from live registry freshness, audit, and compatibility.
Failures retain updates and provide actionable diagnostics for forward repairs. Do not
add dependency caps, downgrade fallbacks, forced peer resolution, automatic rollback,
automatic override deletion, or additional maintenance infrastructure.

## Scope and ownership

The TypeScript template owns compiler/lint defaults, package-policy pytest, updater, and
maintenance entry points. Shared configuration propagates; local configuration is seeded
through `noexist` and remains consumer-owned. Version helpers own root package metadata.
The GitHub Pages template owns deployment/build seeds and its canonical style document.
The manager owns integration, propagation verification, documentation, and final review.

No bulk consumer migration, hosted deployment, commits, or automatic merging is included.
Generated provenance manifests remain historical snapshots. Existing custom consumer
workflows and lint settings must be reviewed during later individual migrations.

## Implementation contracts

### Compiler and linting

Replace ESLint defaults with TypeScript 7, Oxlint, and its typed backend. Preserve relevant
correctness checks, generated-file exclusions, browser/Node contexts, Prettier, and tests.
Use installed executables so checks do not implicitly download tools. Keep the regular
`check_codebase.sh` free of dependency updates and avoid repeating its checks in maintenance.
Use a shared Oxlint base and a consumer-owned local configuration. Update reset sentinels
and propagation expectations together.

### Dependency selection and updates

Discover eligible git-tracked manifests within the current repository, including standalone
WASM/related subdirectories. Exclude generated outputs, provenance, reference copies, and
template/fixture manifests. Select a single candidate automatically. Multiple candidates
require a CLI choice; noninteractive agents pass `--package-json PATH`, otherwise receive
the candidate list and a failure. `--select-only` prints the selected absolute path to stdout;
prompts and diagnostics go to stderr. Default operation previews; `--apply` writes changes.

Query registry latest releases for dependency requirements and override leaves. Preserve
aliases while querying their target package, local/file/git/workspace specifications, and
override `$dependency` references. Traverse nested overrides and `.` values, preserving
selector keys. Direct overrides must match direct specifications exactly or use references.
Report registry failures rather than silently skipping packages. Refresh requirements to
`>=latest`, then repair compatibility forward or replace blocking dependencies.

Offline pytest enforces stable manifest conventions, including override values and direct
override consistency. Selector keys and lifecycle-script approval identities are not pins.
Do not make offline tests query a registry or assert current release numbers.

### Local maintenance

`./update_dependencies.sh [--package-json PATH]` selects the package and npm project context,
applies current requirements, installs with strict peer checking, verifies freshness and
the resolved tree, audits security, runs established code checks, validates the production
build, and proves the resulting lockfile with `npm ci --no-audit`.

Use the repository check/build commands once each. A standalone nested package uses its
own check command or declared typecheck/test scripts, and its declared build. Missing
required checks or unsupported npm contexts fail explicitly rather than passing silently.
Success means current requirements, no unresolved audit findings, successful validation,
and a clean lockfile installation. Print stage results and actionable failure details;
distinguish audit service failure from confirmed vulnerabilities. Preserve edited manifests
and lockfiles on failure so agents can repair and rerun.

Review whether overrides remain needed through fresh resolution in a disposable copy,
followed by audit and project checks. Do not mistake a retained forced lock resolution for
proof of safe removal. Document only overrides needing ongoing compatibility explanation;
routine security overrides do not require a separate ledger or expiry mechanism.

### Release versions

Discover the root package manifest in the existing version helper. Synchronize its version
and lockfile root metadata (`version` and `packages[""].version`), leaving dependency versions
untouched. Normalize calendar versions as valid SemVer using the existing Cargo convention.
Explicit version setting repairs divergent metadata; preserve ordinary conflict handling.
Use standard-library JSON handling with existing key order and indentation; do not run npm.

### GitHub Pages

Deploy with `npm ci --no-audit`, the existing production build, artifact upload, and deployment.
Use an explicitly locally validated Node major and current Actions; scope permissions to
the jobs that need them. The build retains compiler validation. Dependency maintenance and
full test suites run locally. Leave GitHub defaults and existing Dependabot configuration unchanged; do not ship
or recommend a replacement Dependabot configuration.

Canonical guidance lives in `templates/githubpages/docs/GITHUB_PAGES_STYLE.md`, propagated
to `docs/GITHUB_PAGES_STYLE.md` only for Pages repositories. TypeScript guidance refers to
Pages ownership instead of duplicating deployment policy. Template tests verify useful
install/build/artifact contracts, not negative restrictions or fixed release versions.

## Milestones

Each milestone is agent-executable, with no human-dependent acceptance gate.
Parallel-plan ready: yes; updater, versioning, linting, and Pages have independent ownership.

| Milestone | Deliverable and exit evidence | Dependencies |
| --- | --- | --- |
| M1 | Record baseline, template boundaries, current tool metadata | None |
| M2 | Prove TypeScript 7 and typed Oxlint diagnose representative failures | M1 |
| M3 | Replace lint defaults and preserve consumer-local ownership | M2 |
| M4 | Update check/setup entry points; validate local executable use | M3 |
| M5 | Implement bounded updater, selection, aliases, and overrides; focused tests pass | M1 |
| M6 | Synchronize root package and lock versions; regression tests pass | M1 |
| M7 | Add offline package-policy checks with override coverage | M1 |
| M8 | Integrate maintenance command and actionable success/failure reporting | M4-M7 |
| M9 | Exercise vulnerable transitives, retained overrides, and safe removal experiments | M8 |
| M10 | Update Pages workflow/build, Actions maintenance, and canonical guidance | M1, M4 |
| M11 | Verify reset/propagation in disposable repositories and preserve custom files | M3-M10 |
| M12 | Run generated repository maintenance, production build, and clean installation | M11 |
| M13 | Independent review, documentation, relevant suite, and cleanup | M12 |

## Validation and failure response

Retain focused regressions for repository selection, aliases, override traversal, policy,
version metadata, and meaningful maintenance failures. Use disposable repositories for live
registry experiments; do not permanently encode advisory-dependent expectations. Validate
fresh scaffolds and legacy/custom ownership, nested package selection, failed latest updates
followed by forward repair, clean lockfile installation, and Pages production artifacts.

The manager resolves integration failures and checks diagnostics are sufficient for an agent
to repair without repeating discovery. Security findings stay failures until addressed;
network outages stay incomplete checks. Record actual evidence without claiming a hosted
deployment or consumer migration. Do not repeat successful checks without a relevant change.

## Documentation and rollout

Refresh TypeScript/test/setup guidance and canonical Pages policy. Record direct human
preferences in HUMAN_GUIDANCE and settled implementation choices in DESIGN_DECISIONS;
update CHANGELOG with behavior, tests, and material limitations. Propagation is tested only
in disposable repositories. The user later propagates templates and agents migrate each
consumer, preserving custom workflow/build behavior and removing obsolete lint packages
after the new checks pass.

## Progress and evidence

- Planning baseline: 60 focused version, repolib folder, and reset tests passed.
- M1-M13 implementation and review complete in this repository; no consumer migration or hosted
  deployment was performed. The human's final correction removes the Dependabot seed and its
  recommendation: freshness, audit, and compatibility work remain local.
- Live generated Pages repository: `./update_dependencies.sh` passed registry refresh, offline
  policy, strict installation, resolved freshness, zero-finding audit, TypeScript, typed Oxlint,
  Prettier, Node tests, production build, and clean lockfile installation. The final rerun used
  the updated esbuild lifecycle approval and a sandbox-writable npm cache.
- Live typed-lint proof: an unhandled promise fails; diagnostic-only console warnings do not.
- Live vulnerable tree: old glob with a minimatch override had three high findings. Updating
  glob and the override to current releases and resolving fresh produced zero audit findings.
  A separate fresh-resolution experiment proved an obsolete minimatch override could be removed.
- Nested manifest discovery reports ambiguity noninteractively and accepts explicit selection.
  Disposable noexist propagation preserved a custom Pages workflow byte-for-byte.
- Regression tests cover aliases (including override aliases), nested override requirements,
  missing references, audit findings versus outages, retained failure evidence, release metadata,
  and propagation contracts. Shell syntax and diff whitespace checks passed.
- Implementation baseline: `source source_me.sh && python3 -m pytest tests/ -q`: 2,762 passed,
  five failures in unchanged files: HUMAN_GUIDANCE header fixed-point behavior, COLOR_PALETTE
  vendored header, Graphify temporary-test indentation, and Rust/Swift style links. These are
  outside this implementation. New and changed behavior tests pass.
- Registry versions validated: TypeScript 7.0.2, Oxlint 1.94.0, oxlint-tsgolint 7.0.2007,
  esbuild 0.28.2, Playwright 1.65.1, Prettier 3.10.1, tsx 4.23.15, and Node types 26.6.6.
  This is dated implementation evidence, not a permanent version constraint.
- npm workspace members require their workspace-root commands; the maintenance selector supports
  root and standalone nested projects. Agents review retained overrides and repair failures;
  the script does not claim to automatically decide whether an override is still necessary.

## Pruning and independent audit

All six fresh independent passes completed on 2026-11-16: Plan, Test, Style, Docs, Legacy,
and Comment. Each returned findings; no reviewer reported a finding-free pass. The audit
covered the modernization changes; pruning inventoried all repository-owned meta tests and
E2E runners, excluding shared propagated hygiene tests and support.

### Findings and disposition

| Severity | Finding and impact | Resolution |
| --- | --- | --- |
| High | The npm clean alias named a missing root script; the quickstart also understated deep-clean effects | Pointed the alias and quickstart to the existing light cleaner under `devel/`, which retains dependencies |
| Medium | Formatting documentation used `npx`, which can fetch an unvalidated tool | Documented the installed Prettier executable |
| Medium | The policy helper claimed all modes were offline despite a live freshness mode | Clarified module and CLI descriptions; positional manifest validation remains offline |
| Medium | Pages guidance still prescribed recurring Actions maintenance | Removed the directive; dependency maintenance remains local and existing GitHub settings remain alone |
| Low | An unused updater compatibility alias and stale ESLint configuration references remained | Removed the alias/cache ignore and updated propagation/design guidance |
| Low | A runnable helper used a module-level assert and the wrapper forwarded unsupported flags | Replaced the assert with an explicit error and limited wrapper arguments to its documented selection interface |

The Plan pass recommended an exact Node patch pin. The coordinator retained the existing
validated major setting and clarified the plan: selecting Node 26 is intentional; a permanent
patch pin is outside the adopted dependency policy. Reviewers disagreed about which clean
command existed; inspection resolved this in favor of the Docs pass: both cleaners are under
`devel/`, and the root command was absent.

The generated Graphify snapshot still describes the earlier tooling. Its refresh is deferred;
this audit did not regenerate the graph or its counts. Hosted Pages execution remains unverified.

### Test burden and protection

- Meta suite inventory fell from 51 modules / 521 functions / 10,114 lines to
  46 modules / 491 functions / 9,495 lines: 30 tests and 619 lines removed.
- Removed five modules covering report naming/formatting, stale-report plumbing, cache call
  counts, and environment-dependent shell setup. Removed three generic fixer-wrapper cases and
  duplicate npm-command, help-text, and reset-sentinel assertions from mixed modules.
- Removed two custom fixtures and their mutable global cleanup machinery. No dependency or
  shared production/test support became unused; vendored checks were preserved.
- Retained selection/alias/override policy, audit classification and freshness, package/lockfile
  version integrity, failed-update evidence, and the real auto-fixer exit-code regression.
- Retained all four E2E runners. License migration remains an explicit human requirement;
  the other runners protect real reset, propagation, and release seams.
- Known protection loss: exact report presentation, cache spawn counts, shell-seed environment,
  and generic fixer error wrappers are no longer checked separately. No replacement tests added.

### Verification

- Meta collection: 667 before, 637 after pruning; collection succeeds.
- Full suite after pruning: 2,672 passed, the same five baseline failures listed above.
  The wider count also falls because hygiene parametrization no longer includes deleted files.
- Two temporary smoke checks passed: the actual npm light-clean alias removes build output
  while preserving dependencies; unsupported updater-only flags fail before maintenance.
  Deleted the temporary checks after running them.
- Shell syntax and diff whitespace checks passed. No live registry update, hosted deployment,
  or consumer migration was repeated for these audit corrections.
