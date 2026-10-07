# Temporary Graphify Cargo normalization workaround

## Status and ownership

Added and verified on 2026-10-07 against official Graphify 0.9.80. The workaround
is maintained in starter-repo-template; consumer scripts are vendored copies.
This document stays under `meta/docs/` and does not propagate to consumers.

The workaround consists of:

- `normalize_cargo_twins` in
  [devel/graphify_prune_tests.py](../../devel/graphify_prune_tests.py).
- The marked four-line call and reconciliation log in
  [devel/graphify_map_repo.py](../../devel/graphify_map_repo.py), immediately before
  `graphify cluster-only . --no-label`.
- [tests/meta/test_graphify_cargo_normalize_temp.py](../../tests/meta/test_graphify_cargo_normalize_temp.py).
  These tests stay in the template.

There are no installed Graphify patches, package-version pins, new CLI flags, or
forced Graphify writes. The earlier experimental upstream fix is separate from
this workaround and is not installed.

## Failure being addressed

A completely fresh mapping run in qti-package-maker-rs reproduced this sequence:

| Stage | Nodes | JSON edge records |
| --- | ---: | ---: |
| Fresh extraction | 2,142 | 5,008 |
| After Rust-test pruning | 1,891 | 4,383 |
| After Cargo reconciliation | 1,885 | 4,383 |

Graphify's Cargo workspace introspector emits `crate:*` nodes while its Cargo
manifest extractor emits AST package nodes describing the same packages.
`build_from_json` merges these exact twins by `(source_file, label)`. This is
exact reconciliation, not duplicate-ID handling or fuzzy matching.

| Removed alias | Retained AST package |
| --- | --- |
| `crate:qti-cli` | `pkg_qti_cli` |
| `crate:qti-core` | `pkg_qti_core` |
| `crate:qti-engines` | `pkg_qti_engines` |
| `crate:qti-integrity` | `pkg_qti_integrity` |
| `crate:qti-molecule` | `pkg_qti_molecule` |
| `crate:xtask` | `pkg_xtask` |

Without the workaround, `cluster-only` loads 1,885 nodes but compares them with
the 1,891 raw JSON records. Its shrinkage guard refuses overwrite and the wrapper
raises `CalledProcessError`. Simply bypassing that guard would also risk losing
the ten Cargo dependency links: the original JSON endpoints still reference the
removed aliases, and Graphify's original-link export filters absent endpoints.

## How the workaround behaves

After Rust-test pruning, the helper finds each `crate:*` node with exactly one
AST Cargo package sharing its source file and label. The retained node must have
`_origin: ast`, `type: package`, and `ecosystem: cargo`.

Before saving, it independently loads a deep copy through Graphify's normalizer.
The proposed retained IDs and record count must exactly match that loaded graph.
Ambiguous twins or unexplained node differences raise an error before writing.

It then removes only the matched aliases and redirects their endpoints in both
`links` and `edges`, preserving every original link record and its attributes.
Hyperedge members in the top-level and graph-metadata slots are redirected too.
The helper saves through a temporary sibling file and atomic replacement.

With no matching aliases, the helper returns without rewriting the file. With
aliases, the wrapper logs each reconciliation. Graphify's normal shrinkage guard
remains enabled for both clustering and labeling; the helper does not fabricate
nodes, pad counts, or use `force=True`.

## Verified behavior

Using official Graphify 0.9.80 and the vendored copies of the two updated scripts,
the exact clean `./devel/graphify_map_repo.py -F` run completed in qti-package-maker-rs.
Clustering, labeling, benchmarking, graph diagnostics, and manager-context generation
all completed.

The resulting graph contains 1,885 nodes and all 4,383 serialized links. The only
missing original IDs are the six aliases listed above. After applying their endpoint
remaps, the before/after edge multisets match, all ten `crate_depends_on` links
survive, and there are zero dangling endpoints. Graphify reports 4,339 in-memory
edges because its simple graph collapses parallel relations for clustering.

The focused test and repository-check run passed 677 cases. Dedicated tests cover
production-node and parallel-link preservation, a second-call no-op, rejection of
unexplained normalization without changing the original file, and Graphify's
continued refusal to overwrite after unexpected production-node loss.

## Removal conditions

Verify a released upstream version with the workaround disabled. A release note
or a successful run against an already normalized graph is insufficient. Start
with no `graphify-out/` so the raw Cargo aliases are exercised if still emitted.

Removal is ready when fresh extraction either emits canonical package nodes
directly, or reclustering handles its own normalization while preserving all
original links. The full mapping command must finish, retain production symbols
and Cargo dependencies, and still refuse genuinely unexpected node loss.
The counts above are evidence from this checkout, not permanent inventory requirements.

## Removal steps

Make these edits in starter-repo-template:

1. Delete the marked temporary `normalize_cargo_twins` function at the end of
   `devel/graphify_prune_tests.py`.
2. Remove its `import copy` if no remaining code uses it. Keep the existing
   JSON/path imports and all Rust-test pruning functions.
3. Delete the marked four-line block in `devel/graphify_map_repo.py`: the temporary
   comment, helper call, loop, and reconciliation print. Keep the existing pruning
   step and `cluster-only . --no-label` subprocess call.
4. Delete `tests/meta/test_graphify_cargo_normalize_temp.py`. Keep the existing
   Graphify lifecycle and Rust-test pruning tests.
5. Record removal and acceptance evidence in `docs/CHANGELOG.md` and update the
   temporary decision in `docs/DESIGN_DECISIONS.md`. Mark this document retired or
   move it to `meta/docs/archive/` using the repository's `git mv` convention.
6. Propagate the updated canonical scripts to consumers using the template's
   normal propagation workflow. Do not remove the workaround only in a consumer;
   a later propagation would restore it.
7. Run focused tests and repeat the clean mapping acceptance check in the affected
   Rust repo. Verify the installed Graphify release, link preservation, and guard
   behavior before considering removal complete.

Focused checks after deleting the dedicated temporary test:

```bash
source source_me.sh && python3 -m pytest \
  tests/meta/test_graphify_map_repo.py \
  tests/meta/test_graphify_prune_tests.py \
  tests/test_pyflakes_code_lint.py \
  tests/test_function_typing.py \
  tests/test_import_requirements.py -q
```

If acceptance fails, retain the workaround in the template and propagate that
version. Do not disable the shrinkage guard to make the removal check pass.
