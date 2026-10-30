# Install NumPy/SciPy into the Python 3 runtime used by Pytro-NOVA.
$ErrorActionPreference = 'Stop'
if ($env:NOVA_PYTHON -and (Test-Path $env:NOVA_PYTHON)) {
    $python = $env:NOVA_PYTHON
} else {
    $python = & py -3 -c 'import sys; print(sys.executable)'
}
if (-not $python) { throw 'Python 3 was not found. Install Python 3 and retry.' }
Write-Host "Installing advanced analysis packages into $python" -ForegroundColor Cyan
& $python -m pip install -r (Join-Path $PSScriptRoot 'backend\requirements-advanced.txt')
if ($LASTEXITCODE -ne 0) { throw 'Python advanced dependency installation failed.' }
& $python -c 'import numpy, scipy; print("Advanced backend ready: numpy", numpy.__version__, "scipy", scipy.__version__)'
if ($LASTEXITCODE -ne 0) { throw 'Advanced dependencies could not be imported.' }
Write-Host 'Advanced analysis backend is ready.' -ForegroundColor Green
