param(
    [string]$PythonExe = "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe",
    [int]$Port = 8000,
    [switch]$Reload
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$env:CREATOR_STUDIO_DATA_DIR = Join-Path $root "studio_runtime"

if (-not (Test-Path -LiteralPath $PythonExe)) {
    throw "Python not found: $PythonExe"
}

Set-Location $root
$args = @(
    "-m", "uvicorn", "studio_backend.app:app",
    "--host", "127.0.0.1",
    "--port", $Port
)
if ($Reload) {
    $args += "--reload"
}
& $PythonExe @args
