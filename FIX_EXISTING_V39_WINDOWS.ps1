$ErrorActionPreference = 'Stop'
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
$source = Join-Path $project 'app\main.cpp'
if (-not (Test-Path $source)) { throw "Cannot find $source" }
$content = [System.IO.File]::ReadAllText($source)
$old = 'curve.segments.append({});'
$new = 'curve.segments.append(QVector<QPointF>{});'
if ($content.Contains($old)) {
    $content = $content.Replace($old, $new)
    [System.IO.File]::WriteAllText($source, $content, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host 'Patched Qt 6 append overload.'
} elseif ($content.Contains($new)) {
    Write-Host 'The source is already patched.'
} else {
    throw 'Expected code not found. Please verify the project version.'
}
Set-Location $project
cmake --build build-mingw --parallel 1
if ($LASTEXITCODE -ne 0) { throw 'C++ build failed. See compiler output above.' }
Write-Host 'Build completed; executable at build-mingw\PytroNOVA.exe'
