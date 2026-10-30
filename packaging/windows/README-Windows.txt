PYTRO-NOVA 3.9.4 - WINDOWS x64
===================================

PORTABLE EDITION
1. Extract the whole ZIP. Do not move PytroNOVA.exe out of the extracted folder.
2. Double-click PytroNOVA.exe. The adjacent Qt DLLs and python/ directory are required.
3. Select an existing .nox file or a technique-tagged CSV/TSV file.
4. Click "Export clean TXT" for separate full_data, plot_data, and recorded_segments files.

The converter also runs from Command Prompt:
  Pytro-NOVA-to-TXT.cmd "C:\data\measurement.nox" --output "C:\data\exports"
  Pytro-NOVA-to-TXT.cmd "C:\data\GCD.csv" --technique GCD --output "C:\data\exports"

The output parent folder must exist. See manifest.json in the output for details.

INSTALLER EDITION
Run Pytro-NOVA-Setup-v3.9.4-Windows-x64.exe. The installer places the same
components under your user account and creates a Start Menu shortcut.

SYSTEM REQUIREMENTS
Windows 10/11 (64-bit), x64 CPU. No separate Qt or Python install is needed.
The built EXE and installer are not digitally signed.

DATA INTEGRITY
Exports retain decoded values, original point order and available units.
NOVA .nox decoding depends on the instrument's saved file layout; not every
NOVA procedure is supported. This is not software for instrument control.

THIRD-PARTY SOFTWARE
Qt 6, Python 3.12, NumPy and SciPy are bundled. Read THIRD_PARTY_NOTICES.txt
before redistributing and review their original license terms.
