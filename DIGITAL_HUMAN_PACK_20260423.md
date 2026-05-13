# Digital Human Copy Pack (2026-04-23)

This pack is ready for your local Creator Studio backend (`POST /api/generate`).

## Files

- Pack JSON:
  `C:\Users\HP\Documents\Playground\creator_automation\studio_data\presets\digital_human_pack_20260423.json`
- Batch submit script:
  `C:\Users\HP\Documents\Playground\creator_automation\run_digital_human_pack.ps1`

## Quick Run

1. Start backend:

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_creator_studio_backend.ps1
```

2. Submit all scripts as generation jobs:

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
powershell -ExecutionPolicy Bypass -File .\run_digital_human_pack.ps1
```

3. Optional: custom backend URL or another pack file:

```powershell
powershell -ExecutionPolicy Bypass -File .\run_digital_human_pack.ps1 `
  -ApiBase "http://127.0.0.1:8000" `
  -PackPath ".\studio_data\presets\digital_human_pack_20260423.json" `
  -DelaySec 2
```

## Notes

- Default render mode in this pack: `sadtalker`
- Default TTS in this pack: `local_clone`
- If your local clone is not ready, switch `tts_provider` to `edge` inside the JSON.
