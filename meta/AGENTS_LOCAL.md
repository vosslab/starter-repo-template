# Template-local agent instructions

Use these instructions only while maintaining the starter template source checkout.

- Record human guidance in `meta/docs/HUMAN_GUIDANCE.md`.
- Record design decisions in `meta/docs/DESIGN_DECISIONS.md`.
- Prefer Homebrew Python 3.12 on the maintainer's macOS checkout and system Python 3.13 on
  Debian 13. Use a virtual environment only when the configured system interpreter cannot
  support the work.
- On the maintainer's macOS machine, Python 3.12 packages are installed in
  `/opt/homebrew/lib/python3.12/site-packages/`.
- The reset workflow removes the tracked `meta/` directory from consumer repositories.
