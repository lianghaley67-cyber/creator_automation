param(
    [string]$PythonExe = "python",
    [string]$ProxyUrl = "",
    [ValidateSet("auto", "anti_anxiety", "self_rescue", "self_media")]
    [string]$Series = "auto",
    [switch]$MockOnQuota,
    [switch]$Mock
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

Write-Host "[1/2] Collecting topics..."
& $PythonExe .\topic_collector.py
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

Write-Host "[2/2] Generating content..."
if ($Mock) {
    & $PythonExe .\content_generator.py --mock --series $Series
} elseif ($MockOnQuota) {
    & $PythonExe .\content_generator.py --mock-on-quota --series $Series
} else {
    & $PythonExe .\content_generator.py --series $Series
}

exit $LASTEXITCODE
