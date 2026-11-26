# GitHub Pages style

> This file is vendored. Local changes can and will be overwritten by propagation.

This guide owns the GitHub Pages deployment contract for repositories with
`REPO_TYPE=githubpages`. It complements `docs/TYPESCRIPT_STYLE.md`,
which owns local TypeScript maintenance.

## Build and upload with Pages

Run release verification locally before pushing. Pages installs the committed dependencies,
builds the site, uploads the artifact, and publishes it after the upload succeeds.

- Use `./update_dependencies.sh` for local dependency refresh and audit. Complete the project's
  local release checks for types, lint, relevant test suites, and the production build before
  pushing to GitHub.
- For the standard Pages seed, run `./check_codebase.sh` and `./build_github_pages.sh` locally.
  Run `./run_playwright_tests.sh` when the project has browser tests.
- Commit the reviewed `package.json` and `package-lock.json` together.
- The Pages workflow runs `npm ci --no-audit`, then
  `./build_github_pages.sh`, then uploads `dist/` and deploys it.
- `build_github_pages.sh` bundles the site and checks the required build inputs and outputs.
  Keep release checks in the local verifier so publishing depends on the build and artifact.

The workflow uses an explicit Node major validated by local maintenance. Update
that value only after validating the newer major locally.

## Activate workflow seeds

The repository receives `deploy-pages.yml` at its root so propagation never overwrites
an active workflow. To activate it, move it to:

```text
.github/workflows/deploy-pages.yml
```

Keep custom workflows when they need a different build or artifact path. Update
the equivalent install, build, upload, and deploy steps instead of replacing a
working custom workflow.

Leave GitHub's defaults and the repository's existing Dependabot setup unchanged;
this template does not provide or recommend a replacement configuration.

## Build contract

`build_github_pages.sh` writes the complete publishable site to `dist/`. It must
use installed local tools, verify its required source files, and leave
`dist/index.html`, `dist/main.js`, and `dist/.nojekyll` ready for the Pages
artifact action.
