# AI Voice Video Generator (Python)

This tool creates a complete short-video package:
- script
- AI voice audio (`mp3`)
- subtitles (`srt`)
- final vertical video (`mp4`)

Output folder pattern:
`outputs/ai_voice_video/<timestamp_topic>/`

## 1) Prepare

1. Install `ffmpeg` and ensure `ffmpeg` + `ffprobe` are in `PATH`.
2. Copy `voice_pipeline.env.example` to `.env`.
3. Fill API keys in `.env`.

## 2) Run with OpenAI voice

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python .\ai_voice_video_generator.py `
  --topic "why creators freeze on camera" `
  --style-file .\style_profile.template.json `
  --provider openai
```

## 3) Run with ElevenLabs cloned voice

```powershell
cd C:\Users\HP\Documents\Playground\creator_automation
python .\ai_voice_video_generator.py `
  --topic "how to publish short videos consistently" `
  --style-file .\style_profile.template.json `
  --provider elevenlabs `
  --voice-authorized
```

## 4) Use your own script directly

```powershell
python .\ai_voice_video_generator.py `
  --script-file .\my_script.txt `
  --provider elevenlabs `
  --voice-authorized
```

## 5) Useful options

- `--background-image .\cover.jpg` use your own background image
- `--audio-only` skip MP4 rendering and export script/audio/srt only
- `--size 1080x1920` set output size
- `--line-chars 18` control subtitle width
