# Contributing to Pytro-NOVA

Issues and pull requests are welcome for documented, reproducible improvements.

## Develop and test

1. Use Python 3.9+ and Qt 6 development headers on Linux.
2. Run `python3 -m unittest discover -s tests -v`.
3. Run `cmake -S . -B build/linux -DCMAKE_BUILD_TYPE=Release` and `cmake --build build/linux --parallel 2`.
4. Describe the experimental technique, NOVA version, and decoded columns before changing the decoder.
5. Include tests with **synthetic**, openly licensed or explicitly permissioned fixtures.

Never upload laboratory `.nox` source files, participant details, unpublished
measurement datasets, access tokens, or proprietary software with an issue or PR.
Confirm both raw row alignment and original unit semantics; do not create or
silently interpolate missing physical measurements. Decoder heuristics must be
identified as inferred, especially GCD cycle labels.

## Pull requests

Keep changes focused, explain whether they affect data values or only display,
and report your tests. Binary artifacts are created by the build/release pipeline,
not committed to Git.
