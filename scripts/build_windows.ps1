# Windows x64 source build plus portable package (requires MSVC 2022, Qt 6,
# CMake and Python 3.12 on the build machine). GitHub Actions automates this.
param(
    [string]$QtDir = $env:QT_ROOT_DIR,
    [switch]$CreateInstaller
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $QtDir) { throw 'Pass -QtDir "C:\\Qt\\6.8.3\\msvc2022_64" or define QT_ROOT_DIR.' }
$buildDir = Join-Path $root 'build/windows'
& cmake -S $root -B $buildDir -G 'Visual Studio 17 2022' -A x64 "-DCMAKE_PREFIX_PATH=$QtDir"
if ($LASTEXITCODE -ne 0) { throw 'CMake configure failed.' }
& cmake --build $buildDir --config Release --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'C++/Qt build failed.' }
& (Join-Path $PSScriptRoot 'package_windows.ps1') -BuildDir $buildDir -QtDir $QtDir
if ($LASTEXITCODE -ne 0) { throw 'Windows packaging failed.' }
if ($CreateInstaller) {
    $iscc = Join-Path ${env:ProgramFiles(x86)} 'Inno Setup 6/ISCC.exe'
    if (-not (Test-Path $iscc)) { throw "Install Inno Setup 6 first: $iscc" }
    & $iscc (Join-Path $root 'packaging/windows/PytroNOVA.iss')
    if ($LASTEXITCODE -ne 0) { throw 'Windows setup compilation failed.' }
}
