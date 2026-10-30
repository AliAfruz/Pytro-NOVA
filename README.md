# Pytro-NOVA

<p align="center"><img src="docs/assets/pytro-nova-knight.png" alt="Original knight-and-NOVA-dragon artwork supplied by Ali Afruz" width="960"></p>

**Version 3.9.5 · Linux and Windows · Offline scientific software**

**Offline, native Qt electrochemistry viewer for Linux and Windows.**

Pytro-NOVA includes a C++17/Qt Widgets desktop interface and a Python analysis
backend. It reads recognized measurement arrays from legacy Metrohm Autolab
NOVA `.nox` files and supports CSV/TSV imports for specified techniques.
**This is an independent tool, not Metrohm software**; no instrument control,
NOVA installation or cloud service is required for the supported file layouts.

> Version 3.9.5 introduces the Pytro-NOVA name and decoder/packaging fixes,
> retaining automated Windows portable `.exe` and installer builds
> while retaining Linux support and the clean TXT converter. Source archives
> are not themselves precompiled Windows or Linux applications. GitHub Actions
> builds downloadable `.deb`, Windows ZIP and Windows installer artifacts.

## Quick downloads

Download the ready-to-run Windows installer, portable Windows ZIP, or Ubuntu 24.04 `.deb` from [GitHub Releases](https://github.com/AliAfruz/Pytro-NOVA/releases/latest). The Windows ZIP must be fully extracted before running `PytroNOVA.exe`.

## Supported data and limitations

- **CV:** measured potential/current signals and available CV columns.
- **EIS:** Nyquist, Bode magnitude and phase, subject to recognized NOVA fields.
- **GCD and OCP:** time/potential curves recovered from verified stored signal
  plots; GCD *cycle groups are inferred*, not instrument-recorded cycle IDs.
- **LSV, DPV, SWV, CA and CP:** CSV/TSV import; `.nox` support depends on
  whether the specific procedure's signals can be recognized.
- **Scientific analysis:** existing peak analysis, EIS models and plot overlays
  retained from the original v3.9.1 project.

**Do not assume universal `.nox` compatibility.** Unsupported procedure layouts,
missing channels or unknown serialized variants may produce no datasets. A plot
of GCD potential vs time alone does not establish the applied current; no
capacitance/capacity is calculated without appropriate verified inputs.

## Install on Ubuntu / Debian

From the extracted repository folder:

```bash
bash scripts/install_ubuntu.sh
```

The script installs Qt 6 development headers, a C++ toolchain, Python 3,
NumPy and SciPy with `apt`, compiles the native GUI, and installs it under
`/usr/local`. You may be asked for your administrator password.

Launch from the application menu as **Pytro-NOVA**, or:

```bash
PytroNOVA
```

Manual build (other Linux distributions; install Qt 6, CMake and Python 3):

```bash
cmake -S . -B build/linux -DCMAKE_BUILD_TYPE=Release -DCMAKE_INSTALL_PREFIX=/usr/local
cmake --build build/linux --parallel 2
sudo cmake --install build/linux
```

Create an Ubuntu/Debian `.deb` installer with:

```bash
bash scripts/build_deb.sh
sudo apt install ./build/deb/*.deb
```

The `.deb` is compiled for the machine and distribution on which you build it;
for a portable GitHub binary, build in CI for each supported target. Qt 5 is
also accepted by CMake, but Qt 6 is recommended.

**Uninstall (system install):** Remove the `PytroNOVA` and `pytro-nova-to-txt`
executables from `/usr/local/bin`, the `pytro-nova` directory from
`/usr/local/share`, and the desktop/icon entries installed by CMake. If you
installed the `.deb`, use your package manager instead.

## Windows `.exe` and installer (x64)

**Use the Windows build**, not the Linux `.deb`. In the GitHub repository, open
**Actions → Windows executable and installer → Run workflow**. When the run
finishes, download its two artifacts:

- `Pytro-NOVA-Windows-Portable`: a ZIP containing `PytroNOVA.exe`, Qt DLLs and a
  bundled Python 3.12 runtime with NumPy/SciPy. Extract the **entire** ZIP and
  double-click `PytroNOVA.exe` (no system Python or Qt installation required).
- `Pytro-NOVA-Windows-Installer`: an Inno Setup `Pytro-NOVA-Setup-…exe` installer,
  which installs the same components under your Windows user account and adds
  Start Menu shortcuts.

For locally produced Windows release packages, read
[`docs/WINDOWS_PACKAGING.md`](docs/WINDOWS_PACKAGING.md). The portable package
includes `Pytro-NOVA-to-TXT.cmd` to export measurement data from Command Prompt:

```bat
Pytro-NOVA-to-TXT.cmd "C:\data\measurement.nox" --output "C:\data\exports"
```

**These binaries are made by the GitHub Windows runner**, not by a Linux
compiler. The Windows build workflow checks the portable Python backend
against a synthetic GCD fixture and the numeric-analysis imports before
uploading release artifacts. Windows executables are **not code-signed**;
SmartScreen may display an unknown-publisher warning.

## Convert NOVA files to clean, separate text files

### Desktop interface

Open a supported `.nox` file, choose **Export clean TXT** (bottom toolbar or
main menu), and select an output parent folder. A fresh, non-overwriting
folder is created for each export.

### Terminal / batch processing

Installed command:

```bash
pytro-nova-to-txt "/path/to/measurement.nox" --output "$HOME/Documents"
```

No GUI or Qt installation is needed to run the standalone converter from a
source checkout:

```bash
python3 tools/nova_to_txt.py "/path/to/measurement.nox" --output "$HOME/Documents"
```

Limit export to a named dataset, or import a labeled GCD CSV:

```bash
pytro-nova-to-txt experiment.nox -o "$HOME/Documents" --dataset "CV 1"
python3 tools/nova_to_txt.py examples/new_techniques/SYNTHETIC_GCD.csv \
  --technique GCD --output "$HOME/Documents"
```

**Example output:**

```text
measurement_NOVA_TEXT/
├── README.txt
├── manifest.json
├── full_data/
│   ├── 01_CV_1_All_Columns.txt
│   └── 02_EIS_1_All_Columns.txt
└── plot_data/
    ├── 01_CV_1_Current_vs_Voltage.txt
    ├── 02_EIS_1_Nyquist.txt
    ├── 02_EIS_1_Bode_Magnitude.txt
    └── 02_EIS_1_Bode_Phase.txt
```

For files containing separately recorded GCD or OCP level traces, the export
also creates `recorded_segments/` with one TXT file per actual decoded
segment, preventing plotting software from connecting physically separate
trace intervals.

Each TXT uses **UTF-8, tab-separated columns, a unit-labeled header, dot
decimals and original measurement order**. Floating-point values are written
in the shortest lossless round-trip representation. The `full_data` folder retains *all*
columns available to the decoder; `plot_data` contains two-column XY tables.
`manifest.json` records decoded metadata, warnings and file-to-signal mapping.
No smoothing, fitting, interpolation or unit conversion is performed during
TXT export. The original `.nox` file remains unchanged.

The older `Export plot CSVs` button continues to work as before.

## Repository layout

```text
app/                       C++/Qt desktop and plotting UI
backend/                   Python .nox reader and scientific computations
backend/text_export.py     New text exporter
packaging/linux/            Desktop entry, SVG icon, CLI launcher
packaging/windows/          Windows installer and batch converter launcher
scripts/package_windows.ps1    Windows portable dependency bundling
scripts/                    Ubuntu installation and .deb build scripts
tools/                      Command-line converter and diagnostics
tests/                      Numerical and source-level regression tests
examples/new_techniques/    Synthetic technique input files
.github/workflows/          Linux and Windows build/test CI
```

## Tests

```bash
python3 -m unittest discover -s tests -v
```

The full tests for specific real `.nox` variants require original files supplied
separately and **must not be committed**. Relevant optional environment
variables: `METROHM_SAMPLE`, `METROHM_GCD_SAMPLE`, and
`METROHM_SELF_DISCHARGE_SAMPLE`. The included synthetic CSV fixtures are
not actual instrument measurements.

## Upload to GitHub

Use the contents of this folder as the repository root, so `.github/`, `app/`,
`backend/` and this README are at the top level. See [the upload guide](docs/GITHUB_UPLOAD.md).
The source ZIP is ready for GitHub; it is not a Windows executable. Native Linux
build and regression checks were run locally. Windows builds are provided through
GitHub Actions and must complete before publishing Windows binaries.

The EIS numerical components are unchanged from the verified MIT-licensed
[EIS-studio source](https://github.com/AliAfruz/EIS-studio), with its original
license included. See [component provenance](THIRD_PARTY_NOTICES.md). Real NOVA
measurements, environments, build trees, credentials and exported user data are
excluded from the source package.

## Existing documentation and license

- Earlier release details: [v3.9.1 README](docs/legacy-readme-v3.9.1.md).
- Changes and validation history: `CHANGES_v3_*.md`.
- License: `LICENSE` (original MIT copyright notice retained), with upstream EIS
  notices in `docs/licenses/`.

NOVA and Metrohm Autolab are trademarks of their respective owners. No
association or endorsement is claimed.
