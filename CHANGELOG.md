# Pytro-NOVA changes

## 3.9.4 — 30 October 2026

- Renamed the application, executable, Linux package, desktop entry, Windows
  installer, workflows and documentation to Pytro-NOVA.
- Preserved the original knight artwork for the README and website.
- Fixed NRBF nested primitive arrays, invalid stream headers, missing roots and
  invalid/overflowing null runs. Added regression cases for malformed inputs.
- Declared NumPy and SciPy dependencies for the Linux installer.
- Made the Linux TXT launcher relocatable and able to use a selected interpreter.
- Installed scientific dependencies before Windows regression tests and limited
  release-write permissions to the release publication job.
- Added verified upstream EIS license/provenance, citation metadata, line-ending
  rules and a GitHub upload guide. Numerical EIS source remains unchanged.

Earlier NOVA Lab history is retained in the original `CHANGES_v3*.md` files.
