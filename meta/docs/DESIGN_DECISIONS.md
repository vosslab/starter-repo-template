# Design decisions

Durable decisions for the starter repository template. Consumer-facing conventions remain in
[docs/REPO_STYLE.md](../../docs/REPO_STYLE.md); this ledger records how this repository implements
and propagates them.

## Testing and hygiene

### Planning and archive Markdown has no source-code line budget

**Decision.** Exclude `.md` files beneath any `docs/active_plans/` or `docs/archive/` tree from the
source-file line-limit gate. Keep other source types in those trees covered.

**Why.** Plans and archives preserve working context and history; their useful size follows the work
they document rather than the maintainability budget for executable or current reference source.
An exact local override list gives every exceptional source file an individual approval record.

**Consequence.** The universal test applies the directory-category rule automatically wherever the
named `docs/` tree is nested. Exact-path overrides remain reserved for exceptional external sources,
while other hygiene checks continue to inspect these Markdown files. Universal noexist propagation
seeds a commented override file for new consumers and preserves each established consumer's file.

**Owner.** [tests/test_source_file_line_limit.py](../../tests/test_source_file_line_limit.py) and
[docs/REPO_STYLE.md](../../docs/REPO_STYLE.md).

## Repository structure

### Support directories follow their audience

**Decision.** Place optional domain-facing utilities for regular users in `tools/`, and place
repository-engineering commands for highly technical maintainers in `devel/`. Put primary product
workflows in the application CLI and shared behavior in an importable package.

**Why.** Audience plus input and output gives each command a durable home. User data producing a
domain result indicates `tools/`; source, Git state, manifests, tests, or internal fixtures
producing repository state or engineering evidence indicates `devel/`.

**Consequence.** Graphify and dependency refresh ship from `devel/`. Direct domain conversions such
as HTML-to-PDF belong in `tools/`. Future placement decisions apply the same boundary before adding
or moving a command.

**Owner.** [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md),
[tools/TOOLS_README.md](../../tools/TOOLS_README.md), and
[devel/DEVEL_README.md](../../devel/DEVEL_README.md).

### One native package stays at root

**Decision.** Place a repository's only native application, library, or tool-helper package in a
named folder at the repository root. Use `packages/` to group multiple native products or packages.

**Why.** A root-level package makes one code owner immediately visible. The additional `packages/`
layer earns its place when it separates multiple independently named code owners.

**Consequence.** A large `tools/` or `devel/` command can move reusable behavior into one clear
root-level helper package while retaining a thin command entry point. Repositories with multiple
native packages give each one a distinct home under `packages/`.

**Owner.** [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md) and the repository's package manifests.

## Propagation

### Development requirements have split ownership

**Decision.** Propagate `pip_requirements-dev.txt` through a dedicated bucket that owns a marked
universal package block and preserves the repository-specific local block.

**Why.** NOEXIST freezes shared dependencies at repository creation, while OVERWRITE would erase
packages each repository needs. Requirement-aware merging can refresh shared tools without
confusing comments, directives, extras, or version constraints with package identity.

**Consequence.** Marker-free consumers migrate automatically. Canonical package names identify
universal duplicates, the template specification wins during migration, and ambiguous ownership
markers stop the write.

**Owner.** [repolib/requirements_sync.py](../../repolib/requirements_sync.py) and
[REQUIREMENTS_BUCKET_SPEC.md](REQUIREMENTS_BUCKET_SPEC.md).

### Gitignore migration preserves local content

**Decision.** Recognize every shipped LOCAL-section banner and relocate its consumer-owned body
after the canonical managed blocks without changing the body's line order.

**Why.** Earlier propagation placed the LOCAL section before or between managed blocks. A canonical
rebuild can distinguish those rules from obsolete managed content only by recognizing the banner
that assigned their ownership.

**Consequence.** The parser retains compatibility with the previous full LOCAL heading, the legacy
short heading, and the older divided banner. Repositories converge to the current trailing LOCAL
layout on their next propagation.

**Owner.** [repolib/gitignore.py](../../repolib/gitignore.py) and
[GITIGNORE_SYSTEM.md](GITIGNORE_SYSTEM.md).

### Propagation records consumer maintenance

**Decision.** A successful, non-dry-run single-repository propagation that changes files adds one
canonical maintenance entry to the consumer's active changelog. No-op, dry-run, and failed runs
leave the changelog unchanged.

**Why.** Propagated maintenance belongs in the repository history, while unchanged or unsuccessful
runs have no maintenance event to record.

**Consequence.** The propagation writer preserves canonical changelog structure and remains
idempotent. Its entry stays compatible with the consumer's changelog query, rotation, and commit
tools even if implementation ownership changes later.

**Owner.** [propagate_style_guides.py](../../propagate_style_guides.py) and
[repolib/propagation_changelog.py](../../repolib/propagation_changelog.py).
