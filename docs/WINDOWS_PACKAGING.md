# Building Windows Pytro-NOVA: native `.exe`, portable ZIP and installer

The Windows app is a **native C++17/Qt Widgets executable**, not a conversion of
Python to an `.exe`. The Python backend is launched as a separate process for
read-only NOVA decoding, scientific analysis and TXT export. Packaging only
`PytroNOVA.exe` would omit critical dependencies. This workflow bundles them.

## Recommended: GitHub Actions (no Windows development setup necessary)

1. Push this repository to GitHub, including `.github/workflows/windows.yml`.
2. Open the **Actions** tab, select **Windows executable and installer**, then
   choose **Run workflow** on `main`.
3. After it succeeds, open the workflow run and download **both artifacts**:
   `Pytro-NOVA-Windows-Portable` and `Pytro-NOVA-Windows-Installer`.
4. The portable artifact contains a ZIP. Extract it completely on a 64-bit
   Windows 10/11 computer and run `PytroNOVA.exe`.
5. The installer artifact contains `Pytro-NOVA-Setup-v3.9.5-Windows-x64.exe`.
   Run it to install under the current user's AppData/Programs folder.

On a published GitHub Release, the workflow also attempts to attach both
files to the release. Builds on GitHub-hosted Windows machines require network
access to Qt, the CPython embedded distribution, PyPI and Inno Setup.

## Building locally on Windows

Prerequisites: Windows x64, Visual Studio 2022 C++ toolchain, CMake,
Qt **6.8.3 MSVC2022 x64** (dynamically linked), and Python **3.12 x64** with
`pip`. Inno Setup 6 is optional for the installer. Use PowerShell:

```powershell
.\scripts\build_windows.ps1 -QtDir 'C:\Qt\6.8.3\msvc2022_64'
```

To additionally build the installer, install Inno Setup 6 and pass
`-CreateInstaller`. Existing `BUILD_AND_RUN_WINDOWS.ps1` is the older MinGW
build-and-launch script; it does **not** produce portable distributions.

## Contents and numerical verification

The ZIP contains:

```text
Pytro-NOVA-v3.9.5-Windows-x64/
├── PytroNOVA.exe                 C++/Qt user interface
├── Qt6*.dll, platforms/        Bundled Qt runtime and required plugins
├── python/                    Official isolated CPython 3.12 executable,
│   └── Lib/site-packages/     NumPy and SciPy wheels
├── backend/                   NOVA decoder, electrochemical analysis and export
├── tools/nova_to_txt.py       Console converter entry point
├── Pytro-NOVA-to-TXT.cmd            Console converter shortcut
├── README-Windows.txt
├── THIRD_PARTY_NOTICES.txt
└── LICENSE
```

Before packaging, the Windows workflow executes the entire Python regression
suite. During packaging it checks that bundled Python imports NumPy/SciPy
and successfully exports clean TXT files from an included **synthetic GCD**
fixture; a missing `manifest.json` fails the build. It verifies the Qt
`qwindows.dll` plugin was bundled and runs a noninteractive `PytroNOVA.exe
--verify-runtime` check that initializes QApplication and verifies the adjacent
interpreter and decoder are present. This smoke test does **not** prove that
all NOVA `.nox` file variants load correctly, or that the GUI displays properly
on every Windows configuration. Test a real supported input file on Windows
before a public release.

## Security, licensing and signing

- The build does not need to access Windows Registry to decode `.nox` files.
- The original input file is not modified by conversion.
- Windows artifacts are **unsigned**; Microsoft Defender SmartScreen may show
  an unknown-publisher notice. Do not bypass such notices for files from an
  untrusted source. For broader distribution, use a suitable code-signing
  certificate and trusted release process.
- The C++ application ships Qt **dynamic** DLLs to permit relinking/replacement
  under applicable licenses. Before public distribution, review the licenses
  of all Qt modules/plugins, CPython, NumPy/SciPy and the original project;
  preserve any mandatory license notices and source-offer obligations.
- This product is independent of Metrohm and does not control instruments.
