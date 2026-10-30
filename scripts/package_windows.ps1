# Build a complete portable Windows distribution from an existing MSVC/Qt build.
# Run with PowerShell 7, or on the Windows GitHub Actions runner.
param(
    [string]$BuildDir = 'build/windows',
    [string]$QtDir = $env:QT_ROOT_DIR,
    [string]$PythonVersion = '3.12.10',
    [string]$HostPython = 'python'
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if (-not $QtDir) { throw 'QtDir is required (Qt 6 MSVC x64 directory). Pass -QtDir or set QT_ROOT_DIR.' }
$qtBin = Join-Path $QtDir 'bin'
$deployTool = Join-Path $qtBin 'windeployqt.exe'
if (-not (Test-Path $deployTool)) { throw "Qt deployment tool missing: $deployTool" }

if (-not [System.IO.Path]::IsPathRooted($BuildDir)) { $BuildDir = Join-Path $root $BuildDir }
$builtExe = Join-Path $BuildDir 'Release/PytroNOVA.exe'
if (-not (Test-Path $builtExe)) {
    $builtExe = Join-Path $BuildDir 'PytroNOVA.exe'
}
if (-not (Test-Path $builtExe)) { throw "Build PytroNOVA.exe first: $BuildDir" }

$version = '3.9.5'
$dist = Join-Path $root 'dist'
$portable = Join-Path $dist "Pytro-NOVA-v$version-Windows-x64"
New-Item -ItemType Directory -Force -Path $dist | Out-Null
if (Test-Path $portable) { Remove-Item $portable -Recurse -Force }
New-Item -ItemType Directory -Force -Path $portable | Out-Null
Copy-Item $builtExe (Join-Path $portable 'PytroNOVA.exe')

Write-Host '[1/5] Deploying Qt DLLs and platform plugins...' -ForegroundColor Cyan
# Deploy the dynamic Qt libraries; keep plugin directories next to the EXE.
& $deployTool --release --no-translations --compiler-runtime --dir $portable (Join-Path $portable 'PytroNOVA.exe')
if ($LASTEXITCODE -ne 0) { throw "windeployqt failed (exit $LASTEXITCODE)" }
if (-not (Test-Path (Join-Path $portable 'platforms/qwindows.dll'))) {
    throw 'The Qt Windows platform plugin was not deployed.'
}

Write-Host '[2/5] Copying read-only NOVA decoder and TXT converter...' -ForegroundColor Cyan
Copy-Item (Join-Path $root 'backend') (Join-Path $portable 'backend') -Recurse
Get-ChildItem -Path (Join-Path $portable 'backend') -Directory -Recurse -Filter '__pycache__' |
    Remove-Item -Recurse -Force
New-Item -ItemType Directory -Force -Path (Join-Path $portable 'tools') | Out-Null
Copy-Item (Join-Path $root 'tools/nova_to_txt.py') (Join-Path $portable 'tools/nova_to_txt.py')
Copy-Item (Join-Path $root 'LICENSE') (Join-Path $portable 'LICENSE')
Copy-Item (Join-Path $root 'THIRD_PARTY_NOTICES.md') (Join-Path $portable 'THIRD_PARTY_NOTICES.md')
Copy-Item (Join-Path $root 'docs/licenses') (Join-Path $portable 'licenses') -Recurse
Copy-Item (Join-Path $root 'packaging/windows/Pytro-NOVA-to-TXT.cmd') (Join-Path $portable 'Pytro-NOVA-to-TXT.cmd')
Copy-Item (Join-Path $root 'packaging/windows/README-Windows.txt') (Join-Path $portable 'README-Windows.txt')
Copy-Item (Join-Path $root 'packaging/windows/THIRD_PARTY_NOTICES.txt') (Join-Path $portable 'THIRD_PARTY_NOTICES.txt')

Write-Host '[3/5] Fetching the official Windows embeddable Python distribution...' -ForegroundColor Cyan
$pyRoot = Join-Path $portable 'python'
New-Item -ItemType Directory -Force -Path $pyRoot | Out-Null
$embeddedZip = Join-Path $dist "python-$PythonVersion-embed-amd64.zip"
$url = "https://www.python.org/ftp/python/$PythonVersion/python-$PythonVersion-embed-amd64.zip"
Invoke-WebRequest -Uri $url -OutFile $embeddedZip
Expand-Archive -Path $embeddedZip -DestinationPath $pyRoot -Force
Remove-Item $embeddedZip -Force
# The official embeddable interpreter uses an isolated ._pth file; these
# entries permit wheel imports and our adjacent scientific backend.
$pth = Get-ChildItem -Path $pyRoot -Filter 'python*._pth' | Select-Object -First 1
if (-not $pth) { throw 'Python embedded runtime missing ._pth file.' }
@(
    "python$($PythonVersion.Split('.')[0])$($PythonVersion.Split('.')[1]).zip"
    '.'
    'Lib\site-packages'
    '..\backend'
    '..\tools'
    'import site'
) | Set-Content -Path $pth.FullName -Encoding ascii

Write-Host '[4/5] Including NumPy and SciPy for Advanced Lab...' -ForegroundColor Cyan
$site = Join-Path $pyRoot 'Lib/site-packages'
New-Item -ItemType Directory -Force -Path $site | Out-Null
# The runner's Python MUST match the embedded interpreter minor version.
$hostVersion = & $HostPython -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
if ($LASTEXITCODE -ne 0 -or $hostVersion -ne '3.12') {
    throw "Packaging requires host Python 3.12, found '$hostVersion'."
}
& $HostPython -m pip install --disable-pip-version-check --no-compile --only-binary=:all: `
    --target $site -r (Join-Path $root 'backend/requirements-advanced.txt')
if ($LASTEXITCODE -ne 0) { throw 'Wheel installation into the portable runtime failed.' }

Write-Host '[5/5] Validating the embedded backend and clean TXT export...' -ForegroundColor Cyan
$embedded = Join-Path $pyRoot 'python.exe'
& $embedded -c 'import sys, numpy, scipy; print("Portable Python:", sys.version, "NumPy:", numpy.__version__, "SciPy:", scipy.__version__)'
if ($LASTEXITCODE -ne 0) { throw 'The bundled scientific interpreter is not functional.' }
$syntheticFile = Join-Path $root 'examples/new_techniques/SYNTHETIC_GCD.csv'
$smokeDir = Join-Path $env:TEMP "Pytro-NOVA-Windows-Smoke-$PID"
New-Item -ItemType Directory -Force -Path $smokeDir | Out-Null
try {
    $response = & $embedded (Join-Path $portable 'tools/nova_to_txt.py') `
        $syntheticFile --technique GCD --output $smokeDir
    if ($LASTEXITCODE -ne 0) { throw 'Embedded NOVA-to-TXT conversion failed.' }
    $outcome = ($response | Out-String | ConvertFrom-Json)
    if (-not $outcome.folder -or $outcome.text_files -lt 1) { throw 'TXT converter returned no files.' }
    if (-not (Test-Path (Join-Path $outcome.folder 'manifest.json'))) { throw 'Missing TXT export manifest.' }
    Write-Host "Validated: $($outcome.text_files) TXT files from synthetic GCD fixture." -ForegroundColor Green
} finally {
    Remove-Item $smokeDir -Recurse -Force -ErrorAction SilentlyContinue
}

# A genuine Qt startup test: QApplication loads the Windows platform plugin;
# the dedicated flag exits before any main window is shown.
$gui = Start-Process -FilePath (Join-Path $portable 'PytroNOVA.exe') `
    -ArgumentList '--verify-runtime' -Wait -PassThru
if ($gui.ExitCode -ne 0) { throw "Portable Qt GUI startup failed ($($gui.ExitCode))." }

$portableZip = Join-Path $dist "Pytro-NOVA-v$version-Windows-x64.zip"
if (Test-Path $portableZip) { Remove-Item $portableZip -Force }
Compress-Archive -Path $portable -DestinationPath $portableZip -CompressionLevel Optimal
Write-Host "Portable Windows ZIP: $portableZip" -ForegroundColor Green
