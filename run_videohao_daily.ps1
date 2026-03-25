param(
    [string]$PythonExe = "python",
    [string]$InputCsv = ".\data\videohao_posts.csv",
    [int]$Days = 3,
    [string]$ReadyOutput = "",
    [string]$LibraryOutput = "",
    [string]$WatchDir = "",
    [switch]$UseLatestDownload,
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
    ".\videohao_daily_monitor.py",
    "--input", $InputCsv,
    "--days", $Days
)

if ($Mock) {
    $ArgsList += "--mock"
}
if ($MockOnQuota) {
    $ArgsList += "--mock-on-quota"
}
if ($ReadyOutput) {
    $ArgsList += @("--ready-output", $ReadyOutput)
}
if ($LibraryOutput) {
    $ArgsList += @("--library-output", $LibraryOutput)
}
if ($WatchDir) {
    $ArgsList += @("--watch-dir", $WatchDir)
}
if ($UseLatestDownload) {
    $ArgsList += "--use-latest-download"
}
if ($AllowDemoData) {
    $ArgsList += "--allow-demo-data"
}

& $PythonExe $ArgsList
exit $LASTEXITCODE
