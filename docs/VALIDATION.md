# Pytro-NOVA 3.9.4 validation

Checked on 30 October 2026 on Ubuntu 26.10 with GCC 15.3 and Qt 6.11.2.

- Original verification: **68 regression tests passed, zero skips** with Python 3.11 and Python 3.14.
- Before GitHub publication, all **69 tests passed, zero skips** on Python 3.11, including a new Windows packaging source-path regression.
- Existing CV/EIS, GCD and self-discharge `.nox` samples were supplied privately
  through the documented environment variables. They are absent from this repo.
- Synthetic fixtures cover all supported CSV techniques and known circuit cases.
- Five new decoder tests expose failures in the original 3.9.3 archive and pass
  with the corrected reader: nested primitive arrays, array-overflowing null runs,
  zero/negative null runs, non-header records and missing stream roots.
- The three bundled EIS numerical files match their pinned upstream source hashes.
- The native Qt application builds; its headless startup check succeeds. A staged
  installation starts outside the source tree. The installed TXT launcher also
  converts synthetic data outside the source tree using a selected interpreter.
- A native Linux `.deb` was built, including NumPy/SciPy runtime dependencies.
  This local package targets Ubuntu 26.10 / Qt 6.11; build in the included Ubuntu
  24.04 workflow for that older distribution rather than assuming binary portability.
- Shell scripts passed `bash -n`; both workflow files parse as YAML.

The complete unit-test logs are in `docs/validation/`. Passing software tests does
not certify universal NOVA file compatibility or unique electrochemical mechanisms.

## Windows limitation

Windows packaging names, interpreter wiring, workflow structure and version
consistency have source-level regression coverage. The Windows EXE and installer
were **not built or executed on this Linux machine**. Run the included Windows
GitHub Actions workflow and inspect its artifacts before distributing binaries.
