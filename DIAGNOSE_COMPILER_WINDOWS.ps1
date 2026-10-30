# Self-contained smoke checks, useful when g++ exits with no diagnostics.
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$gxx = 'C:\Qt\Tools\mingw1310_64\bin\g++.exe'
$env:Path = 'C:\Qt\Tools\mingw1310_64\bin;C:\Qt\6.12.0\mingw_64\bin;' + $env:Path
if (-not (Test-Path $gxx)) { throw "g++ not found: $gxx" }
$src = Join-Path $env:TEMP 'pytro-nova_compiler_test.cpp'
$obj = Join-Path $env:TEMP 'pytro-nova_compiler_test.o'
Set-Content -Path $src -Value 'int main() { return 0; }' -Encoding Ascii
Remove-Item $obj -ErrorAction SilentlyContinue
Write-Host 'Testing standalone C++ compiler...' -ForegroundColor Cyan
& $gxx -O0 -c $src -o $obj
$exit = $LASTEXITCODE
Write-Host "Compiler exit code: $exit"
Write-Host "Object file created: $(Test-Path $obj)"
if ($exit -ne 0 -or -not (Test-Path $obj)) {
    Write-Host 'Compiler failed on a tiny source file. Check toolchain/antivirus/Windows Event Viewer.' -ForegroundColor Yellow
    exit 1
}
Write-Host 'Standalone compiler works. Building project with one job:' -ForegroundColor Cyan
& cmake --build (Join-Path $PSScriptRoot 'build-mingw') --parallel 1 --verbose
Write-Host "Build exit code: $LASTEXITCODE"
