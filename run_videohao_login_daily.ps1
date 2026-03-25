param(
    [string]$PythonExe = "python",
    [string]$InputCsv = ".\data\videohao_posts.csv",
    [int]$Days = 3,
    [int]$TimeoutSec = 900,
    [string]$WatchDir = "",
    [string]$SourceCsv = "",
    [string]$LibraryOutput = "",
    [switch]$AllowDemoData,
    [switch]$Mock,
    [switch]$MockOnQuota
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

$ArgsList = @(
    ".\videohao_login_fetch.py",
    "--output-csv", $InputCsv,
    "--days", $Days,
    "--timeout-sec", $TimeoutSec
)

if ($WatchDir) {
    $ArgsList += @("--watch-dir", $WatchDir)
}
if ($SourceCsv) {
    $ArgsList += @("--source-csv", $SourceCsv, "--skip-open")
}
if ($LibraryOutput) {
    $ArgsList += @("--library-output", $LibraryOutput)
}
if ($AllowDemoData) {
    $ArgsList += "--allow-demo-data"
}
if ($Mock) {
    $ArgsList += "--mock"
}
if ($MockOnQuota) {
    $ArgsList += "--mock-on-quota"
}

& $PythonExe $ArgsList
exit $LASTEXITCODE
