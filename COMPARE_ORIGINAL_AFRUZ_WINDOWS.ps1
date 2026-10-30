param(
    [Parameter(Mandatory=$true)][string]$AfruzZip,
    [Parameter(Mandatory=$true)][string]$EisInput,
    [string]$Dataset = 'EIS 2',
    [string]$Circuit = 'R-(R||C)'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$script = Join-Path $PSScriptRoot 'tools\compare_original_afruz.py'
if (-not (Test-Path $script)) { throw "Missing tool: $script" }
py -3 $script $AfruzZip $EisInput --dataset $Dataset --circuit $Circuit
if ($LASTEXITCODE -ne 0) { throw "Numerical parity check failed (exit code $LASTEXITCODE)." }
