# MERGE bucket specification

How the propagator's `merge_files` bucket works. Read alongside [PROPAGATION_RULES.md](PROPAGATION_RULES.md).

## Why MERGE exists

The propagator has historically offered two file-copy policies:

- **OVERWRITE** -- unconditional copy on every sync. Template owns the file.
- **NOEXIST** -- copy only when missing. Consumer owns the file after first seed.

Some files do not fit either: the template owns a specific region, the consumer owns the rest. Two ad-hoc precedents motivated this bucket:

- `CLAUDE.md` previously used an `@`-line preserve hack: template content was rewritten, but lines beginning with `@` from the consumer were merged back in. Now migrated to MERGE.
- `.gitignore` uses a managed-block merge: `# === UNIVERSAL ===` / `# === END UNIVERSAL ===` markers carry template-owned ignore rules; consumer content outside the block is preserved.

Both solve the same problem with different mechanisms. MERGE generalizes the fence-marker pattern into a fifth file-copy bucket alongside `overwrite_files`, `noexist_files`, `devel_files`, `test_files`.

## Fence convention

Two markers per file, chosen by file syntax. All comment-safe.

| Language / extension | Start fence | End fence |
| --- | --- | --- |
| Shell (`.sh`), Python (`.py`), YAML (`.yml`, `.yaml`), gitignore | `# === TEMPLATE-MANAGED START ===` | `# === TEMPLATE-MANAGED END ===` |
| JavaScript (`.js`, `.mjs`, `.cjs`), TypeScript (`.ts`, `.tsx`) | `// === TEMPLATE-MANAGED START ===` | `// === TEMPLATE-MANAGED END ===` |
| Markdown (`.md`) | `<!-- === TEMPLATE-MANAGED START === -->` | `<!-- === TEMPLATE-MANAGED END === -->` |

Pure JSON has no comment syntax. JSON is **not** a MERGE candidate; use NOEXIST + a documented extends pattern instead.

Both fences must appear exactly once per file, in start-then-end order. Any other shape is an error (see below).

## Semantics

For each file in `MERGE_FILES`, the propagator inspects both the template source and the consumer destination, then chooses an outcome:

| Consumer state | Template state | Outcome | Counter |
| --- | --- | --- | --- |
| Missing | Has both fences | Write template verbatim (template carries fences + managed content) | `created` |
| Both fences present, correct order | Has both fences | Replace consumer's between-fence region with template's between-fence content; preserve everything outside consumer's fences verbatim | `merged` if changed, `unchanged` if identical |
| Missing both fences (file exists, plain content) | Has both fences | Error: refuse to modify. Consumer is at pre-MERGE shape and must transition deliberately (see Migration). | `error` |
| One fence only, mismatched fence styles, or wrong order (end before start) | -- | Error: refuse to modify. Surface in `errors`. | `error` |
| Any | Missing one or both fences | Template-side validation error. Refuse to add the file to the MERGE bucket at plan-build time. | n/a |

Outcome rules in prose:

- "Outside consumer fences" includes every byte before the start fence line and every byte after the end fence line. The fence lines themselves come from the template on every merge.
- A merge that yields a byte-identical result to the existing consumer file is reported as `unchanged`, not `merged`. This keeps `--dry-run` output stable across no-op syncs.
- The propagator never mutates the consumer file if the consumer state is in an error class. Counters increment; the file on disk is untouched.
- `--bootstrap` does **not** override MERGE error semantics. A consumer with one fence is still an error under `--bootstrap`; only NOEXIST has bootstrap override behavior.

## Error cases

Listed for unambiguous test coverage. Each must surface to the user as an actionable message and **must not** modify the consumer file.

1. **Single fence (start only)** -- consumer has `# === TEMPLATE-MANAGED START ===` but no end marker. Error: "missing end fence".
2. **Single fence (end only)** -- consumer has end without start. Error: "missing start fence".
3. **Reversed order** -- end marker appears at an earlier line than start marker. Error: "fence markers out of order".
4. **Mismatched fence styles** -- consumer mixes shell `#` start with markdown `<!-- -->` end (e.g. file extension changed). Error: "fence style mismatch".
5. **Duplicate fence** -- start marker appears twice (or end twice). Error: "duplicate fence marker".
6. **Template missing fences** -- detected by `merge_file_safe` at sync time when reading the template source: if `_find_fences` returns None, surface "merge template missing fences" and refuse to modify the consumer. Covered by `tests/meta/test_merge_bucket_error_cases.py::test_error_template_missing_fences`.
7. **Plain consumer, fenced template** -- consumer file exists but has neither fence. Error: "consumer not at fenced shape; run migration". The user must hand-add fences once (see Migration), then re-sync.

## Migration: pre-MERGE consumer to fenced shape

A consumer at a non-fenced shape (e.g. a CLAUDE.md from before M-MERGE landed) must transition deliberately rather than have the propagator guess where the managed region starts.

One-shot transition for each new MERGE file:

1. Locate the region of the consumer file that should become template-managed. For CLAUDE.md, this is the leading block above the consumer's local `@`-imports.
2. Wrap that region in the two fence markers from the table above.
3. Re-run `propagate_style_guides.py --dry-run --sync-self`. The file should now report `merged` or `unchanged`; the consumer additions outside the fences are preserved.

The propagator does not perform this transition automatically. The risk of mis-placed fences (silently losing consumer content) outweighs the convenience of an auto-migrator.

## Precedent

- `CLAUDE.md` (ad-hoc `@`-line preserve): the first attempt at the same problem. M-MERGE/M-D migrates CLAUDE.md to the formal fence shape and deletes the ad-hoc logic.
- `.gitignore` managed-block (`# === UNIVERSAL ===` ... `# === END UNIVERSAL ===`): same fence-marker mechanism, applied via a separate code path (`gitignore_block` plan key, not `merge_files`). Kept separate because it composes multiple template sources (universal + typed overlay) into one consumer file. Future consolidation possible; not in M-MERGE scope.

## Bucket dispatch summary

`compute_propagation_plan` emits `merge_files` as a list of repo-relative paths, parallel to `overwrite_files` / `noexist_files` / `devel_files` / `test_files`. The dispatcher in `propagate_style_guides.py:apply_file_bucket` calls `merge_file_safe(source, dest, dry_run, counters)` per entry. The helper returns one of `created | merged | unchanged | error` and updates counters accordingly. Counter accounting: `merged_count` and `created_count` (shared with the prior CLAUDE.md overwrite-branch merge) - no separate `merged_managed` counter.

META rules still win: `assert_not_meta()` runs at plan-append time and at dispatcher entry. A MERGE-tagged META file fails loud.
