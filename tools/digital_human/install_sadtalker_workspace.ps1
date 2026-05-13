param(
    [string]$RepoDir = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "SadTalker"),
    [string]$EnvDir = (Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "envs\\sadtalker"),
    [string]$PythonExe = "",
    [switch]$DownloadSource = $true,
    [switch]$CreateVenv,
    [switch]$InstallRequirements,
    [switch]$DownloadReleaseAssets,
    [switch]$CpuOnly,
    [string]$TorchIndexUrl = "https://download.pytorch.org/whl/cu121"
)

$ErrorActionPreference = "Stop"
$toolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$zipPath = Join-Path $toolsDir "SadTalker-main.zip"
$tempExtract = Join-Path $toolsDir "SadTalker-main"

function Test-ZipArchive {
    param([string]$Path)
    & tar -tf $Path | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if ($DownloadSource) {
    New-Item -ItemType Directory -Force -Path $toolsDir | Out-Null
    if (Test-Path $zipPath) { Remove-Item -LiteralPath $zipPath -Force }
    Write-Host "Downloading SadTalker source zip..."
    & curl.exe -L --retry 5 --retry-delay 3 "https://codeload.github.com/OpenTalker/SadTalker/zip/refs/heads/main" -o $zipPath
    if (-not (Test-ZipArchive -Path $zipPath)) {
        throw "Downloaded SadTalker zip is incomplete. Please rerun this script and check network stability."
    }

    if (Test-Path $tempExtract) { Remove-Item -LiteralPath $tempExtract -Recurse -Force }
    & tar -xf $zipPath -C $toolsDir
    if (Test-Path $RepoDir) { Remove-Item -LiteralPath $RepoDir -Recurse -Force }
    Move-Item -LiteralPath $tempExtract -Destination $RepoDir
    Write-Host "SadTalker source ready at $RepoDir"
}

$venvPython = Join-Path $EnvDir "Scripts\\python.exe"
if ($CreateVenv) {
    if (-not $PythonExe) {
        throw "Provide -PythonExe with a compatible Python, ideally Python 3.10 or 3.8."
    }
    Write-Host "Creating local virtual environment..."
    & $PythonExe -m venv $EnvDir
}

if ($InstallRequirements) {
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment not found: $venvPython"
    }
    if (-not (Test-Path (Join-Path $RepoDir "requirements.txt"))) {
        throw "SadTalker requirements.txt not found under $RepoDir"
    }

    Write-Host "Installing Python dependencies..."
    & $venvPython -m pip install --upgrade pip
    if ($CpuOnly) {
        & $venvPython -m pip install torch torchvision torchaudio
    } else {
        & $venvPython -m pip install torch torchvision torchaudio --index-url $TorchIndexUrl
    }
    & $venvPython -m pip install -r (Join-Path $RepoDir "requirements.txt")
}

if ($DownloadReleaseAssets) {
    $checkpointDir = Join-Path $RepoDir "checkpoints"
    New-Item -ItemType Directory -Force -Path $checkpointDir | Out-Null
    Write-Host "Querying latest SadTalker release assets..."
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/OpenTalker/SadTalker/releases/latest" -Headers @{ "User-Agent" = "creator-studio" }
    $assets = @($release.assets | Where-Object { $_.name -match "safetensors|mapping_|gfpgan|GFPGAN|checkpoint|zip|tar" })
    if (-not $assets.Count) {
        Write-Warning "No downloadable checkpoint assets were returned by the GitHub release API."
    }
    foreach ($asset in $assets) {
        $target = Join-Path $checkpointDir $asset.name
        Write-Host "Downloading $($asset.name)..."
        & curl.exe -L --retry 5 --retry-delay 3 $asset.browser_download_url -o $target
    }
}

Write-Host ""
Write-Host "SadTalker bootstrap finished."
Write-Host "RepoDir   : $RepoDir"
Write-Host "EnvPython : $venvPython"
Write-Host "Then open the studio UI and paste these paths into the SadTalker settings panel."
