# NOVA Lab v3.9.3 — Windows executable distribution

- Added Windows x64 GitHub Actions native Qt/MSVC build with automated ZIP and
  optional-style per-user Inno Setup `.exe` installer outputs.
- Bundled official isolated CPython 3.12, NumPy and SciPy with the native Qt
  GUI so a clean Windows machine does not require a separate Python install.
- Updated Windows GUI backend lookup to prefer a `python/python.exe` runtime
  next to `NovaLab.exe`; `NOVA_PYTHON` continues to override this choice.
- Included `NOVA-to-TXT.cmd` to access the existing scientifically conservative
  clean TXT export without installing Qt or Python globally.
- Added portable package integrity smoke tests for Qt plugin presence, NumPy
  and SciPy imports, synthetic GCD TXT export and JSON manifest creation.
- Retained the Ubuntu/Linux build flow and original analysis functionality.

**Verification status:** Source-level tests execute in this environment, but
Windows Qt/MSVC and Inno Setup builds require a Windows build host. The GitHub
workflow builds and validates the actual Windows binaries when run.
