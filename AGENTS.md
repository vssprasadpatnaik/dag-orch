# AGENTS.md

## Cursor Cloud specific instructions

This repository is **documentation-only** (see `README.md`). It contains Markdown files
(`README.md`, `docs/*.md`) describing the Batch Intelligence & Control Plane (BICP) /
Managed Flow SLA initiative. There is **no application code, no dependency manifest, and no
build/lint/test tooling** in the repo.

Practical implications for working here:

- There is nothing to install, build, or run. The update script is intentionally a no-op.
- The "dev loop" is editing Markdown and previewing it. To preview locally, render the
  Markdown to HTML (e.g. `pip install markdown` then a small render script) and serve with
  `python3 -m http.server`, or use any Markdown previewer. Both Python 3.12 and Node 22 are
  available on the VM.
- To validate docs, check that internal cross-document links resolve (the docs link to each
  other with relative paths like `docs/batch-orchestration-architecture.md`).
- If/when application code is added, update this section with the real install/build/test/run
  commands and replace the no-op update script.
