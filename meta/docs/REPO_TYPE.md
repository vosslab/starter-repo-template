# REPO_TYPE.md

`REPO_TYPE` is the root marker that declares which shared template families a
repository consumes. It classifies a repository; it does not define repository
style. Repository conventions live in [docs/REPO_STYLE.md](../../docs/REPO_STYLE.md).

## Marker format

- Store `REPO_TYPE` at the repository root.
- Write one or more lowercase type names followed by a newline.
- Separate several names with commas and no spaces, for example `python,rust`.
- Preserve declaration order.
- Maintain the marker when the repository changes; it remains live after bootstrap.

## Available types

The available names, in canonical display order, are `markdown`, `python`, `pypi`,
`typescript`, `githubpages`, `rust`, `swift`, `podman`, `other`, `scripted`, `website`,
`compiled`, and `all`.

Inheritance adds the complete parent rule set:

- `pypi` -> `python` -> `scripted`
- `githubpages` -> `typescript` -> `website`
- `typescript` -> `website`
- `rust` -> `compiled`
- `swift` -> `compiled`

`markdown`, `podman`, `scripted`, `website`, `compiled`, and `other` are root types. Every listed type
is valid as a direct marker. `all` expands to every concrete type supported by
the template.

Use `githubpages` alone for a TypeScript repository deployed with the template's
GitHub Pages build. Inheritance already supplies the TypeScript and website
families; writing `githubpages,typescript` is redundant.

During `reset_repo.py`, selecting `typescript` prompts whether the repository
uses the template's GitHub Pages build. An affirmative answer writes the
canonical `githubpages` child marker, matching the Python-to-PyPI promotion flow.

Existing Pages consumers previously marked `typescript` must change their marker
to `githubpages` to keep receiving updates to the four Pages front doors. Existing
generic TypeScript consumers may remove old copies of those files when they do not
fit the repository; propagation does not infer whether a previously copied file is
still locally owned.

## Multiple types

`markdown` covers Markdown and Djot writing repositories. Used alone, it ships the two style
guides (`REPO_STYLE.md` has a content-focused overlay), agent guidance, the guidance/decision
ledgers, and three pytest checks: local links, ASCII/ISO-8859-1 compliance, and whitespace.
The checks include `.md` and `.djot` sources. Link checking covers inline links/images and
reference definitions/defined references; it is not a full document parser and does not validate
external URLs, anchor IDs, or undefined reference labels.

Only pytest is required in the managed development dependencies. `source_me.sh`, shared test
helpers, fixers, and the merged `tests/conftest.py` support validation. No development tools or
additional code checks ship, including through automatic discovery. Run
`source source_me.sh && python3 -m pytest tests/` in the consumer.

The reset interview displays one type per line, like the license menu; `[m]` selects `markdown`.
Reset removes unselected template files from a new clone. Changing an existing repository's marker
does not delete its old files or remove local agent imports; review those explicitly when migrating.
README, changelog, licensing, and content remain repository-owned.

When combined with another type, such as `markdown,python`, the normal development baseline wins:
lean Markdown overlays are omitted regardless of marker order. `all` also keeps the full baseline.

Declare several types only when a repository genuinely ships several families,
such as a Python CLI with a Rust extension. The repository receives the union of
the declared types and their inherited rule sets. Declaration order determines
which typed overlay wins if several overlays provide the same path.

## Podman opt-in and migration

Declare `podman` alone or alongside a language, for example `python,podman`, to receive the
mandatory Podman disk-budget guard. It has no parent type; `all` includes it. There is no
container-runtime fallback and no automatic detection for fresh repositories.

During propagation, an existing guard without this marker triggers a filename search for
Dockerfile/Containerfile (including prefix and dotted-suffix variants), compose/docker-compose
YAML, Podman-prefixed YAML, and shell scripts containing `podman` or `docker` in their filenames,
including nested deployment folders. Documentation and skill references alone do not opt in.
Hidden folders, `OTHER_REPOS`, dependency/build trees, and
symlinked directories are excluded. No runtime is started and file contents are not interpreted.
Container evidence appends `podman` to the marker and refreshes the guard. Without evidence,
recognized unchanged vendored copies are removed; locally modified copies remain with a warning.
Dry runs preview these actions without writing the marker or deleting the guard. Repositories
without an existing guard must opt in explicitly. Docker evidence selects the Podman check,
which still requires Podman; Docker alone does not satisfy it.
