# NOVA Lab 3.9.2 — Linux distribution, GitHub preparation, clean TXT export

## New features

- Linux CMake install target for native Qt desktop executable.
- Ubuntu/Debian installation script, .deb build script, desktop launcher and icon.
- CMake/CPack packaging and GitHub Actions Python+Qt+Debian pipeline.
- New desktop action **Export clean TXT** and Ctrl+Shift+T shortcut.
- `backend/text_export.py` and `tools/nova_to_txt.py` standalone offline converter.
- For each recognized decoded dataset: complete numeric table in tab-separated
  `.txt`, plus individual two-column XY plot tables. Where stored GCD/OCP
  segments exist, separate per-segment tables preserve measurement gaps.
- `manifest.json` preserves metadata, original column keys/labels, warnings,
  and annotations identifying inferred cycle groups.
- Collision-safe new folder and staging cleanup if conversion fails.
- Publication-safe `.gitignore` excludes original `.nox` and real-measurement-
  derived A110.001 examples. Historical documentation and source remain.

## Scientific behavior

Existing v3.9.1 decoding, plots and scientific algorithms are not intentionally
changed. Clean TXT export transcribes decoded numeric arrays without new
measurements, smoothing, interpolation, normalization or unit conversion.
Partial `.nox` format coverage and inferred GCD cycle IDs remain limitations.

## Verification

59 Python tests were executed, including 5 new text-export tests:
47 passed, 12 skipped because optional original files were unavailable.
Python source compilation, Bash syntax and synthetic CSV-to-TXT CLI execution
also succeeded. **Qt GUI compilation was not verified in the preparation
container**: Qt headers/libraries were absent and package network DNS failed.
GitHub CI is configured to compile Qt 6 and build a .deb on Ubuntu 24.04.
