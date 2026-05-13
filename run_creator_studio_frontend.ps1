param(
    [int]$Port = 5173,
    [switch]$InstallDeps,
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$root = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "studio_frontend"
Set-Location $root

if ($InstallDeps -or -not (Test-Path -LiteralPath ".\node_modules")) {
    npm install
}

if ($Dev) {
    npm run dev -- --host 127.0.0.1 --port $Port
    exit $LASTEXITCODE
}

npm run build
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

npm run preview -- --host 127.0.0.1 --port $Port
