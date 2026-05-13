param(
    [string]$ApiBase = "http://127.0.0.1:8000",
    [string]$PackPath = ".\studio_data\presets\digital_human_pack_20260423.json",
    [int]$DelaySec = 1
)

$ErrorActionPreference = "Stop"

if (-not (Test-Path -LiteralPath $PackPath)) {
    throw "Pack file not found: $PackPath"
}

$apiBaseTrimmed = $ApiBase.TrimEnd("/")
$healthUrl = "$apiBaseTrimmed/api/health"
$generateUrl = "$apiBaseTrimmed/api/generate"

Write-Host "Checking backend health: $healthUrl"
$health = Invoke-RestMethod -Uri $healthUrl -Method Get -TimeoutSec 8
if ($health.status -ne "ok") {
    throw "Backend health check failed."
}

$raw = Get-Content -LiteralPath $PackPath -Raw -Encoding UTF8
$items = $raw | ConvertFrom-Json
if (-not $items) {
    throw "No items found in pack: $PackPath"
}

$jobRows = @()
$index = 0
foreach ($item in $items) {
    $index++
    $payload = @{
        topic = "$($item.topic)"
        title = "$($item.title)"
        keywords = @($item.keywords)
        story_memo = ""
        custom_script = "$($item.custom_script)"
        content_type = "$($item.content_type)"
        emotion_tone = "$($item.emotion_tone)"
        seconds = [int]$item.seconds
        render_mode = "$($item.render_mode)"
        tts_provider = "$($item.tts_provider)"
        avatar_preprocess = "$($item.avatar_preprocess)"
        avatar_still_mode = [bool]$item.avatar_still_mode
        avatar_size = [int]$item.avatar_size
        output_resolution = "$($item.output_resolution)"
        notes = "$($item.notes)"
    }

    Write-Host ""
    Write-Host "[$index/$($items.Count)] Submit: $($payload.title)"
    $body = $payload | ConvertTo-Json -Depth 8
    $bodyBytes = [System.Text.Encoding]::UTF8.GetBytes($body)
    $resp = Invoke-RestMethod -Uri $generateUrl -Method Post -ContentType "application/json; charset=utf-8" -Body $bodyBytes -TimeoutSec 20
    $jobRows += [PSCustomObject]@{
        index = $index
        title = $payload.title
        topic = $payload.topic
        job_id = $resp.id
        status = $resp.status
        created_at = $resp.created_at
    }
    Write-Host "Job created: $($resp.id) | status=$($resp.status)"

    if ($DelaySec -gt 0 -and $index -lt $items.Count) {
        Start-Sleep -Seconds $DelaySec
    }
}

Write-Host ""
Write-Host "All jobs submitted."
$jobRows | Format-Table index, title, job_id, status, created_at
