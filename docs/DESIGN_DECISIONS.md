# Design decisions

<!-- VENDORED HEADER: START -->
Record each durable decision about how this code and repository are shaped, once it is settled, with
the reasoning a later reader needs. Guidance Neil Voss states belongs in
[HUMAN_GUIDANCE.md](HUMAN_GUIDANCE.md), dated history in `docs/CHANGELOG.md`, open discussion in
`docs/active_plans/decisions/`. [PROPAGATED HEADER - ENTRIES BELOW ARE YOURS]
<!-- VENDORED HEADER: END -->

Write each decision as a level-three heading with these four fields. `Owner` names the
authoritative code or contract document, rather than a person.

```markdown
### <decision title>

**Decision.** <the durable direction>

**Why.** <the reason it was chosen>

**Consequence.** <the constraint a future change preserves>

**Owner.** <the authoritative code or contract doc>
```

## Software design

### Support directories follow their audience

**Decision.** Place optional domain-facing utilities for regular users in `tools/`, and place
repository-engineering commands for highly technical maintainers in `devel/`. Put primary product
workflows in the application CLI and shared behavior in an importable package.

**Why.** Audience plus input and output gives each command a durable home. User data producing a
domain result indicates `tools/`; source, Git state, manifests, tests, or internal fixtures
producing repository state or engineering evidence indicates `devel/`.

**Consequence.** Graphify and dependency refresh ship from `devel/`, while direct conversions such
as HTML-to-PDF ship from `tools/`. Future placement decisions apply the same boundary before adding
or moving a command.

**Owner.** `docs/REPO_STYLE.md`, `tools/TOOLS_README.md`, and `devel/DEVEL_README.md`.

### One native package stays at root

**Decision.** Place a repository's only native application, library, or tool-helper package in a
named folder at the repository root. Use `packages/` to group multiple native products or packages.

**Why.** A root-level package makes one code owner immediately visible. The additional `packages/`
layer earns its place when it separates multiple independently named code owners.

**Consequence.** A large `tools/` or `devel/` command can move reusable behavior into one clear
root-level helper package while retaining a thin command entry point. Repositories with multiple
native packages give each one a distinct home under `packages/`.

**Owner.** `docs/REPO_STYLE.md` and the repository's package manifests.

### Propagation records consumer maintenance

**Decision.** A successful, non-dry-run single-repository propagation that changes files adds one
canonical maintenance entry to the consumer's active changelog through `devel/changelog_lib.py`.

**Why.** Propagated maintenance belongs in the repository history, while no-op runs and failed runs
must not manufacture history. Using the shared parser and serializer keeps the entry compatible with
the changelog query, rotation, and commit tools.

**Consequence.** Propagation change accounting and `.gitignore` normalization remain idempotent, and
future changelog writes use the shared changelog library rather than assembling Markdown separately.

**Owner.** `devel/changelog_lib.py` and the single-repository propagation contract.

## Dependencies

## Generated artifacts
