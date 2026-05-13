param(
    [string]$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    [switch]$WithOptionalMedia
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python not found: $PythonExe"
}

Set-Location $root
& $PythonExe -m pip install -r .\studio_backend\requirements.txt

if ($WithOptionalMedia) {
    & $PythonExe -m pip install -r .\studio_backend\requirements.optional.txt
}

Set-Location (Join-Path $root "studio_frontend")
npm install

Write-Host ""
Write-Host "Setup complete."
Write-Host "Backend:  powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1"
Write-Host "Frontend: powershell -ExecutionPolicy Bypass -File .\run_creator_studio_frontend.ps1"
