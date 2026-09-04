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

### Graphify exposes recurring maintainer actions

**Decision.** The wrapper exposes automatic update, explicit fresh, context, and cleaned SVG
actions. `--ollama` remains the one fresh-build fallback when the Claude allowance is exhausted.

**Why.** These are the maintainer's recurring tasks. Semantic extraction, global registration,
reflection, map-page generation, deep extraction, and forced shrinking add configuration without
serving the normal workflow.

**Consequence.** `--svg` exports through Graphify but writes only cleaned
`docs/GRAPHIFY_map.svg`; Graphify's full export stays in generated `graphify-out/`. The cleaned SVG
is recorded as non-shared because it describes the repository where it was generated.

**Owner.** [../devel/graphify_map_repo.py](../devel/graphify_map_repo.py)

### The committed graph figure is decorative

**Decision.** Strip per-symbol labels from the exported SVG, keep the community legend, and treat
the whole figure step as optional.

**Why.** The export is matplotlib output: text is emitted as per-glyph references, so a 452-symbol
map costs 1.9 MB, and 452 overlapping filename labels are unreadable anyway. The legend carries
the names a reader needs. Matplotlib is not a required Graphify dependency, so the export can be
unavailable.

**Consequence.** The figure conveys cluster shape and scale, not detail, so coordinate rounding is
acceptable. `--svg` reports an unavailable or unparsable export without placing a full-size SVG in
`docs/`.

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
