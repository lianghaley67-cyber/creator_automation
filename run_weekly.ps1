param(
    [string]$PythonExe = "python",
    [string]$ProxyUrl = "",
    [int]$Days = 7
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Resolve-Python {
    param([string]$Preferred)
    $candidate = $Preferred
    if ($candidate) {
        & $candidate --version *> $null
        if ($LASTEXITCODE -eq 0) {
            return $candidate
        }
    }
    $fallback = Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    if (Test-Path $fallback) {
        return $fallback
    }
    throw "No usable Python found. Please install Python 3.12+."
}

$PythonExe = Resolve-Python -Preferred $PythonExe
$env:PYTHONUTF8 = "1"
if ($ProxyUrl) {
    $env:HTTP_PROXY = $ProxyUrl
    $env:HTTPS_PROXY = $ProxyUrl
    Write-Host "[INFO] Using proxy: $ProxyUrl"
}

Write-Host "Generating weekly report for last $Days day(s)..."
& $PythonExe .\weekly_report.py --days $Days

exit $LASTEXITCODE
