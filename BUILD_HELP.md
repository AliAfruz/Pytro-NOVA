# Pytro-NOVA v2.0 — Split-Compilation Build Fix

This variant addresses the Windows MinGW report where G++ 13.1 terminates compiling `app/main.cpp` with no compiler diagnostic, even after reducing optimization to `-O0`.

## What changed

- Moved the Advanced Lab GUI implementation out of the dashboard source. `app/main.cpp` and `app/advanced_dialog.cpp` are now **separate C++ compilation units**.
- New small factory interface `app/advanced_dialog_api.h` connects the two modules.
- The Windows build script now compiles with **one job** and conservative GCC `-O0` options.
- Added `DIAGNOSE_COMPILER_WINDOWS.ps1`, which tests the compiler against a tiny C++ file and prints its exit code.
- Kept the Python analysis backend intact: AsLS baseline, Gaussian/Lorentzian fits, multi-CV comparison, EIS RC/CPE/Warburg fitting.

## Install and run

Unzip to `C:\path\to\NOVA\NOVA_Lab_v2_SplitBuild_Fix` and open PowerShell:

```powershell
cd "C:\path\to\NOVA\NOVA_Lab_v2_SplitBuild_Fix"
powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
```

This folder is a **separate project**. Do not accidentally build `NOVA_Lab_Advanced_v2` again.

If the split build still fails without diagnostics, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\DIAGNOSE_COMPILER_WINDOWS.ps1
```

Send the output, including the compiler exit code. Common silent-exit causes include memory exhaustion, a crashing GCC process, or endpoint security terminating the compiler. This change has been checked for source consistency and Python regression tests; a Windows C++ build is still required to verify it.
