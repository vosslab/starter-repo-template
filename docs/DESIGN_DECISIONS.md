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

## Dependencies

## Generated artifacts

### Graphify agent guidance lives in the propagated devel README

**Decision.** Document Graphify usage for downstream repositories in
[../devel/DEVEL_README.md](../devel/DEVEL_README.md), and do not run
`graphify claude install` or `graphify codex install`.

**Why.** A repository README is never shared between repositories, `AGENTS.md` arrives only when a
repository lacks one, and `docs/` files are replaced wholesale on sync, so a shared `docs/USAGE.md`
would overwrite each repository's own usage document. Files under `devel/` are shared by location.
The Graphify installers additionally write into `CLAUDE.md` and `AGENTS.md` and add a PreToolUse
hook, contending with how those two files are already maintained.

**Consequence.** Guidance that must reach every repository goes in `devel/DEVEL_README.md`.
Third-party tools do not write to `CLAUDE.md` or `AGENTS.md`.

**Owner.** [../devel/DEVEL_README.md](../devel/DEVEL_README.md)

### Rust test symbols leave the graph before clustering

**Decision.** In a Cargo repository, a fresh build extracts with `--no-cluster`, removes
`#[cfg(test)]` symbols from `graph.json`, then runs `cluster-only`. Graphify's own source is never
modified.

**Why.** Filtering at print time leaves the symbols in the graph, where they still distort
community detection, hub degree ranking, and connector spread. `cluster-only` re-clusters an
existing graph, which makes removing them before clustering possible without forking Graphify.
Spans are found with tree-sitter because a brace scan would have to reason about strings,
comments, and nested modules to be correct.

**Consequence.** The gate is `Cargo.toml`, so repositories without Rust run the original pipeline
unchanged. Pruning is limited to fresh builds: re-clustering renumbers communities, and a fresh
build is the only path that always relabels afterward, so stored labels cannot go stale.

**Owner.** [../devel/graphify_prune_tests.py](../devel/graphify_prune_tests.py)

### The repository-map page is generated, never shared

**Decision.** `docs/GRAPHIFY.md` and `docs/GRAPHIFY_map.svg` are written by
`devel/graphify_map_repo.py --page` in each repository, and never copied between repositories.

**Why.** A code map describes the repository it was built from. Files under `docs/` are replaced
wholesale on sync, so sharing this template's copy would overwrite a repository's own page with a
map of the wrong codebase.

**Consequence.** Both are recorded as files that never transfer. Exact entries are required rather
than a filename pattern, because link-bucket classification reads only the exact list, and the page
must classify as non-shared so it may link to the `devel/` tooling that generates it.

**Owner.** [../devel/graphify_docs_lib.py](../devel/graphify_docs_lib.py)

### The map page draws its own diagram rather than reusing Graphify's

**Decision.** Generate the Mermaid community diagram from `graph.json`, with no theme directive
and plain-text labels. Do not extract Graphify's call-flow HTML.

**Why.** Graphify's Mermaid pins a dark theme and uses HTML labels, which renders wrong in GitHub
light mode and risks sanitization; its per-section diagrams are large dependency dumps. Scraping
generated HTML would also couple this repository to markup that changes release to release.

**Consequence.** Theme neutrality, label sanitization, and diagram size stay under local control,
and the generator depends on the graph data rather than on Graphify's presentation layer.

**Owner.** [../devel/graphify_docs_lib.py](../devel/graphify_docs_lib.py)

### The committed graph figure is decorative

**Decision.** Strip per-symbol labels from the exported SVG, keep the community legend, and treat
the whole figure step as optional.

**Why.** The export is matplotlib output: text is emitted as per-glyph references, so a 452-symbol
map costs 1.9 MB, and 452 overlapping filename labels are unreadable anyway. The legend carries
the names a reader needs. Matplotlib is not a required Graphify dependency, so the export can be
unavailable.

**Consequence.** The figure conveys cluster shape and scale, not detail, so coordinate rounding is
acceptable. A failed export or an unparsable SVG omits the figure instead of failing the page.

**Owner.** [../devel/graphify_clean_svg.py](../devel/graphify_clean_svg.py)

### Graphify orientation filters test symbols instead of trusting the graph

**Decision.** `devel/graphify_context_lib.py` drops test scaffolding, repository-wide utility types,
and uninformative call targets before printing orientation.

**Why.** Graphify's Rust extractor indexes `#[cfg(test)] mod tests` contents as production symbols.
Those modules live inside `src/*.rs`, so no `.graphifyignore` rule can exclude them without also
dropping the production code in the same file. Separately, a symbol spanning most communities is a
utility type carrying no navigational information.

**Consequence.** This filter is presentational and remains the fallback, not the primary fix. A
Cargo repository now removes those symbols from the graph itself before clustering, so the filter
covers what pruning does not reach: incremental updates, and other languages whose inline test
conventions have no prune step.

**Owner.** [../devel/graphify_context_lib.py](../devel/graphify_context_lib.py)

### Graphify diagnostics and staleness checks stay advisory

**Decision.** Edge-fidelity diagnostics and the stale-map warning report findings and never fail a
build or suppress orientation.

**Why.** Graphify documents no reliable threshold for same-endpoint edge collapse, and repeated
endpoint pairs are legitimate in some codebases. Context mode exists to orient a reader, so a stale
map must still print in full.

**Consequence.** These checks print and continue. Context mode also reads the `needs_update` flag
file directly rather than shelling out, preserving its documented promise to print orientation
without running Graphify.

**Owner.** [../devel/graphify_map_repo.py](../devel/graphify_map_repo.py)
