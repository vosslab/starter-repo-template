# License policy

This document is the canonical Vosslab policy for license filenames, legal-text sources,
GitHub detection, template reset behavior, and release verification. It records the policy
verified against GitHub and Licensee on 2026-08-26. GitHub may change its detector, so recheck
the linked implementation before changing the filename convention.

This policy is operational guidance, not legal advice. Consult qualified counsel when ownership,
third-party material, compatibility, dual licensing, or other legal questions are consequential.

## Required filenames

- Store each license as a real regular file at the repository root.
- Name each file `LICENSE.<SPDX>`, where `<SPDX>` visibly identifies its license.
- Do not add `.md`, `.txt`, `.rst`, `.html`, or another rendering extension.
- Do not create `LICENSE`, `LICENSE.md`, aliases, wrappers, hard links, or symbolic links.
- Keep one authoritative root file for each license that applies.
- Use hyphenated identifiers from the reset catalog, such as `GPL-3.0` and `CC-BY-SA-4.0`.

Examples:

```text
LICENSE.MIT
LICENSE.LGPL-3.0
LICENSE.GPL-3.0
LICENSE.CC-BY-4.0
LICENSE.CC-BY-SA-4.0
```

The visible suffix is more useful to the maintainer than Markdown rendering. GitHub displays an
extensionless `LICENSE.<SPDX>` body as plain source text, which is intentional.

## GitHub behavior

GitHub documents `LICENSE` and `LICENSE.md` as license-picker names and says that most projects
use a root `LICENSE.txt`, `LICENSE.md`, or `LICENSE.rst`. GitHub then uses Licensee to score
candidate filenames and compare their contents with known license bodies.

The current Licensee filename matcher gives these names different treatment:

| Root name | Current behavior | Vosslab policy |
| --- | --- | --- |
| `LICENSE.md` | Filename score 0.95 and rendered as Markdown | Do not use; the license type is hidden |
| `LICENSE.MIT` | Filename score 0.80 through the generic suffix rule | Required convention |
| `LICENSE.MIT.md` | Compound suffix misses the candidate rules; filename score 0.00 | Do not use |
| `LICENSE.md` symlink | Git stores the target pathname, not a second legal-text blob | Do not use |

The GitHub license tab is a useful discovery feature, not the legal source of truth. A tab may
lag after a push, and repositories with several license candidates may show several tabs or may
not receive one aggregate license classification. The committed legal-text files and the README
scope statement remain authoritative.

## Complete legal text

- Store the complete license body, not a summary, excerpt, deed, badge, or URL alone.
- Preserve the publisher's wording and section order.
- Keep the root license file free of project explanations or Markdown commentary.
- Put scope and multi-license explanations in `README.md`.
- Keep every catalog and installed license body ASCII for portable tooling and terminals.
- Replace `[year]` and `[fullname]` in `LICENSE.MIT` with the actual copyright year and holder
  after reset. Those fields are part of the upstream MIT application template.

Creative Commons publishes its 4.0 legal-code text as UTF-8 plain text. Each source currently
contains one typographic quote pair around `Licensor.` The template catalog changes only that
pair to ASCII straight quotes; the legal wording and section order are otherwise preserved.

## Multiple licenses

Use a separate real file for each distinct grant. For the usual code-plus-documentation split,
the repository root can contain:

```text
LICENSE.GPL-3.0
LICENSE.CC-BY-SA-4.0
```

The README must state which paths or classes of material each license covers. A filename list
alone does not express scope, exceptions, or whether several code licenses are alternatives or
simultaneous obligations. Keep this explanation outside the legal bodies so Licensee receives
unmodified license text.

The repository conventions remain:

- Use GPLv3 for most application source code unless the project states otherwise.
- Use LGPLv3 for libraries intended for proprietary or mixed-source use.
- Use CC BY-SA 4.0 for non-code creative work, including text and figures.
- Select MIT, Apache-2.0, AGPL-3.0, MPL-2.0, or CC BY 4.0 only when the repository's intended
  reuse and distribution model calls for that license.

## Reset and release

`reset_repo.py` copies selected catalog bodies from `LICENSES/LICENSE.<SPDX>` to identically
named root files, then removes the catalog. The license identifiers are selected from a positive
allow-list, so generated source and destination paths do not contain arbitrary user input. It
replaces the template README with a project heading and a scope statement linking the selected
code license and, when chosen, the documentation license.

`devel/make_release.py` requires at least one committed `LICENSE.<SPDX>` file. It rejects plain,
rendering-extension, executable, and symlink forms. For a multi-license repository, it verifies
every committed license byte-for-byte in both source archives.

Git records a hard-linked regular file as an ordinary blob, so release tooling cannot distinguish
one from an independently created file. Avoid hard links as a maintainer convention; the release
gate enforces supported filenames and Git object modes.

Before release:

1. Confirm every applicable license is a committed real root file named `LICENSE.<SPDX>`.
2. Replace the MIT application placeholders when MIT is selected.
3. Confirm the README maps each license to the material it covers.
4. Run `licensee detect .` locally when the Licensee gem is available.
5. Run the repository's release tool and verify the GitHub tabs after pushing.

## Observed repositories

The current Vosslab repositories reproduce the filename distinction:

- [attack-on-cancer](https://github.com/vosslab/attack-on-cancer) contains
  `LICENSE.MIT.md`, but GitHub shows no repository license tab.
- [biology-problems-website](https://github.com/vosslab/biology-problems-website) contains the
  extensionless legacy names `LICENSE.CC_BY_4_0` and `LICENSE.LGPL_v3`; GitHub shows separate
  CC-BY-4.0 and LGPL-3.0 license tabs.

The new reset convention keeps the useful extensionless behavior while replacing the legacy
underscore spellings with the catalog's consistent hyphenated identifiers.

## Body sources

Use the license publisher's plain-text legal code where it is available. The template catalog
was rebuilt from these sources:

| Catalog file | Body source |
| --- | --- |
| `LICENSE.AGPL-3.0` | [GNU AGPLv3 plain text](https://www.gnu.org/licenses/agpl-3.0.txt) |
| `LICENSE.Apache-2.0` | [Apache License 2.0 plain text](https://www.apache.org/licenses/LICENSE-2.0.txt) |
| `LICENSE.CC-BY-4.0` | [CC BY 4.0 legal code](https://creativecommons.org/licenses/by/4.0/legalcode.txt) |
| `LICENSE.CC-BY-SA-4.0` | [CC BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt) |
| `LICENSE.GPL-3.0` | [GNU GPLv3 plain text](https://www.gnu.org/licenses/gpl-3.0.txt) |
| `LICENSE.LGPL-3.0` | [GNU LGPLv3 plain text](https://www.gnu.org/licenses/lgpl-3.0.txt) |
| `LICENSE.MIT` | [GitHub Licenses API MIT body](https://api.github.com/licenses/mit) |
| `LICENSE.MPL-2.0` | [Mozilla MPL 2.0 plain text](https://www.mozilla.org/media/MPL/2.0/index.txt) |

## Detection sources

These are the primary sources for the GitHub-facing policy:

- [GitHub: Adding a license to a repository](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/adding-a-license-to-a-repository)
- [GitHub: Licensing a repository](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/licensing-a-repository)
- [GitHub REST API endpoints for licenses](https://docs.github.com/en/rest/licenses/licenses)
- [Licensee: What we look at](https://github.com/licensee/licensee/blob/main/docs/what-we-look-at.md)
- [Licensee license-file matcher](https://github.com/licensee/licensee/blob/main/lib/licensee/project_files/license_file.rb)
- [Choose a License catalog](https://github.com/github/choosealicense.com)

The following user-supplied sources are useful supporting evidence, but they are not normative
GitHub or license-publisher policy:

- [Automated License Compliance Checker](https://github.com/marketplace/actions/automated-license-compliance-checker)
  addresses dependency scanning and broader compliance, which Licensee does not perform.
- [GitHub Community discussion 81440](https://github.com/orgs/community/discussions/81440)
  records one cache-refresh experience, not a guaranteed refresh procedure.
- [GitHub License Detection NOASSERTION guide](https://gist.github.com/gwpl/63763c12270d35e98c293eb9850f1943)
  provides useful diagnostics and a local Licensee workflow, but remains an unofficial gist.
