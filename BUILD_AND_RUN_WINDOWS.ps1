# Pytro-NOVA 3.9 — Qt 6.12.0 + MinGW 13.1.0 on Windows.
# Usage: powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1
#        powershell -ExecutionPolicy Bypass -File .\BUILD_AND_RUN_WINDOWS.ps1 "C:\my files\data.nox"
param([string] $NoxFile = "")
$ErrorActionPreference = 'Stop'

$qt = 'C:\Qt\6.12.0\mingw_64'
$mingw = 'C:\Qt\Tools\mingw1310_64'
$ninja = 'C:\Qt\Tools\Ninja\ninja.exe'
$gxx = Join-Path $mingw 'bin\g++.exe'
$build = Join-Path $PSScriptRoot 'build-mingw'
$exe = Join-Path $build 'PytroNOVA.exe'

foreach ($p in @((Join-Path $qt 'bin'), $gxx, $ninja, (Join-Path $PSScriptRoot 'CMakeLists.txt'))) {
    if (-not (Test-Path $p)) { throw "Missing prerequisite: $p" }
}

$env:Path = "$(Join-Path $qt 'bin');$(Join-Path $mingw 'bin');$env:Path"
$env:QT_QPA_PLATFORM_PLUGIN_PATH = Join-Path $qt 'plugins\platforms'

$cmake = (Get-Command cmake -ErrorAction SilentlyContinue | Select-Object -First 1).Source
if (-not $cmake) {
    $cmake = 'C:\Program Files\CMake\bin\cmake.exe'
    if (-not (Test-Path $cmake)) { throw 'CMake not found. Please install CMake and open a fresh PowerShell.' }
}

Set-Location $PSScriptRoot
Write-Host 'Configuring Pytro-NOVA...' -ForegroundColor Cyan
& $cmake -S $PSScriptRoot -B $build -G Ninja `
    '-DCMAKE_BUILD_TYPE=Release' `
    "-DCMAKE_PREFIX_PATH=$qt" `
    "-DCMAKE_CXX_COMPILER=$gxx" `
    "-DCMAKE_MAKE_PROGRAM=$ninja"
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed; see errors above.' }

Write-Host 'Building C++ Qt application...' -ForegroundColor Cyan
# Compile serially to reduce peak RAM usage. See BUILD_HELP.md for troubleshooting.
& $cmake --build $build --parallel 1
if ($LASTEXITCODE -ne 0) { throw "C++ build failed with exit code $LASTEXITCODE. Use DIAGNOSE_COMPILER_WINDOWS.ps1 for more details." }
if (-not (Test-Path $exe)) { throw "Expected executable not found: $exe" }

# The Qt frontend launches the Python decoder through QProcess.
# Resolve py.exe to the underlying python.exe if it exists.
if (-not $env:NOVA_PYTHON) {
    $pycmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pycmd) {
        $detected = & py -3 -c 'import sys; print(sys.executable)' 2>$null
        if ($LASTEXITCODE -eq 0 -and $detected -and (Test-Path $detected)) {
            $env:NOVA_PYTHON = $detected
        }
    }
}

# Install the optional scientific backend only if it is missing.
# The standard decoder and v1.1 analysis continue to work independently.
if ($env:NOVA_PYTHON -and (Test-Path $env:NOVA_PYTHON)) {
    Write-Host 'Checking NumPy / SciPy for Advanced Lab...' -ForegroundColor Cyan
    & $env:NOVA_PYTHON -c 'import numpy, scipy' 2>$null
    if ($LASTEXITCODE -ne 0) {
        Write-Host 'Installing Python analysis requirements (NumPy, SciPy)...' -ForegroundColor Yellow
        & $env:NOVA_PYTHON -m pip install -r (Join-Path $PSScriptRoot 'backend\requirements-advanced.txt')
        if ($LASTEXITCODE -ne 0) {
            Write-Host 'WARNING: NumPy/SciPy installation failed. The normal viewer works; Advanced Lab needs these packages.' -ForegroundColor Yellow
            Write-Host 'Try: py -3 -m pip install numpy scipy' -ForegroundColor Yellow
        }
    }
}
Write-Host 'Launching Pytro-NOVA...' -ForegroundColor Green
if ($NoxFile) {
    & $exe $NoxFile
} else {
    & $exe
}
