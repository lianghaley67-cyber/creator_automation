# Personal Video Factory (Distill + Daily Auto Generate)

This workflow has two steps:
1. Distill your speaking style from historical scripts.
2. Generate one talking-head video daily automatically.

## 1) Prepare your data

Put your historical scripts here:
- `data/style_samples/*.txt`
- `data/style_samples/*.md`

Create your daily topics file:
- copy `data/daily_topics.example.txt` to `data/daily_topics.txt`
- one topic per line

## 2) Distill your style

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python .\personal_video_factory.py distill `
  --samples-dir .\data\style_samples `
  --output-profile .\data\style_profile.auto.json
```

This generates:
- `data/style_profile.auto.json`

## 3) Generate one daily video

```powershell
python .\personal_video_factory.py generate `
  --profile .\data\style_profile.auto.json `
  --topics-file .\data\daily_topics.txt `
  --provider elevenlabs `
  --voice-authorized
```

Notes:
- It rotates topics daily using `data/daily_video_state.json`.
- It writes generated scripts into `data/generated_scripts/`.
- It calls `ai_voice_video_generator.py` to produce audio/subtitles/video.

## 4) Schedule daily run on Windows

```powershell
schtasks /Create /SC DAILY /TN "PersonalDailyVideo" /TR "powershell -ExecutionPolicy Bypass -Command cd C:\Users\HP\Documents\Playground\creator_automation; python .\personal_video_factory.py generate --profile .\data\style_profile.auto.json --topics-file .\data\daily_topics.txt --provider elevenlabs --voice-authorized" /ST 08:30 /F
```

Change `08:30` to your preferred daily publishing time.
