from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any
from urllib import error, request

try:
    import cv2  # type: ignore
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    cv2 = None
    np = None

OPENAI_CHAT_URL = "https://api.openai.com/v1/chat/completions"
OPENAI_TTS_URL = "https://api.openai.com/v1/audio/speech"
ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech"


@dataclass
class Artifacts:
    run_dir: Path
    script_file: Path
    audio_file: Path
    subtitle_file: Path
    video_file: Path
    metadata_file: Path


@dataclass
class StoryShot:
    start_s: float
    end_s: float
    shot_type: str
    action_hint: str
    speaker: str
    line: str
    emotion: str = "happy"
    scene_key: str = "park_lane"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate short video assets: script -> AI voice -> subtitles -> mp4."
    )
    parser.add_argument("--env-file", default=".env", help="Path to .env file.")

    parser.add_argument("--topic", default="", help="Topic for script generation.")
    parser.add_argument("--script-file", default="", help="Use existing script file instead of generation.")
    parser.add_argument("--style-file", default="", help="Optional style notes/transcripts (txt/md/json).")
    parser.add_argument("--seconds", type=int, default=60, help="Target duration for generated script.")

    parser.add_argument(
        "--provider",
        choices=["openai", "elevenlabs", "edge", "pyttsx3"],
        default="openai",
        help="TTS provider.",
    )
    parser.add_argument(
        "--voice-authorized",
        action="store_true",
        help="Required when using cloned voice with ElevenLabs.",
    )
    parser.add_argument("--audio-only", action="store_true", help="Skip final mp4 rendering.")

    parser.add_argument("--output-dir", default="outputs/ai_voice_video", help="Output root directory.")
    parser.add_argument("--background-image", default="", help="Optional background image for video.")
    parser.add_argument("--bg-color", default="#111827", help="Fallback background color.")
    parser.add_argument("--size", default="1080x1920", help="Output size, e.g. 1080x1920.")
    parser.add_argument("--fps", type=int, default=30, help="Output FPS.")

    parser.add_argument("--line-chars", type=int, default=18, help="Max subtitle chars per line.")
    parser.add_argument("--subtitle-font", default="Microsoft YaHei", help="Subtitle font name.")
    parser.add_argument("--subtitle-size", type=int, default=16, help="Subtitle font size.")
    parser.add_argument("--subtitle-margin-v", type=int, default=120, help="Subtitle margin from bottom.")

    parser.add_argument("--openai-api-key", default="", help="OpenAI API key.")
    parser.add_argument("--openai-text-model", default="", help="OpenAI model for script generation.")
    parser.add_argument("--openai-tts-model", default="", help="OpenAI model for TTS.")
    parser.add_argument("--openai-voice", default="", help="OpenAI voice name.")

    parser.add_argument("--elevenlabs-api-key", default="", help="ElevenLabs API key.")
    parser.add_argument("--elevenlabs-voice-id", default="", help="ElevenLabs voice id.")
    parser.add_argument("--elevenlabs-model", default="", help="ElevenLabs model id.")
    parser.add_argument("--edge-voice", default="", help="Edge TTS voice name.")
    parser.add_argument("--edge-rate", default="", help="Edge TTS rate, e.g. +5%.")
    parser.add_argument("--edge-volume", default="", help="Edge TTS volume, e.g. +0%.")
    parser.add_argument("--pyttsx3-voice-hint", default="", help="Substring to match a local pyttsx3 voice.")
    parser.add_argument("--pyttsx3-rate", type=int, default=0, help="Optional pyttsx3 speech rate override.")
    return parser.parse_args()


def load_env_file(path: Path) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def fill_default_args(args: argparse.Namespace) -> None:
    if not args.openai_api_key:
        args.openai_api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not args.elevenlabs_api_key:
        args.elevenlabs_api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
    if not args.elevenlabs_voice_id:
        args.elevenlabs_voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if not args.edge_voice:
        args.edge_voice = os.getenv("EDGE_TTS_VOICE", "zh-CN-XiaoxiaoNeural").strip()
    if not args.edge_rate:
        args.edge_rate = os.getenv("EDGE_TTS_RATE", "").strip()
    if not args.edge_volume:
        args.edge_volume = os.getenv("EDGE_TTS_VOLUME", "").strip()
    if not args.pyttsx3_voice_hint:
        args.pyttsx3_voice_hint = os.getenv("PYTTSX3_VOICE_HINT", "zh").strip()
    if not args.pyttsx3_rate:
        rate_text = os.getenv("PYTTSX3_RATE", "").strip()
        if rate_text.isdigit():
            args.pyttsx3_rate = int(rate_text)

    if not args.openai_text_model:
        args.openai_text_model = os.getenv("OPENAI_TEXT_MODEL", "gpt-4o-mini")
    if not args.openai_tts_model:
        args.openai_tts_model = os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts")
    if not args.openai_voice:
        args.openai_voice = os.getenv("OPENAI_TTS_VOICE", "alloy")
    if not args.elevenlabs_model:
        args.elevenlabs_model = os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2")


def read_text_file(path: Path) -> str:
    for encoding in ("utf-8", "utf-8-sig", "gbk"):
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Unable to decode file: {path}")


def slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    if cleaned:
        return cleaned[:36]
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:10]
    return f"topic-{digest}"


def ensure_output_paths(output_dir: str, topic: str) -> Artifacts:
    root = Path(output_dir).expanduser()
    if not root.is_absolute():
        root = Path.cwd() / root
    root.mkdir(parents=True, exist_ok=True)

    run_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{run_stamp}_{slugify(topic or 'script')}"
    run_dir = root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    return Artifacts(
        run_dir=run_dir,
        script_file=run_dir / "script.txt",
        audio_file=run_dir / "voice.mp3",
        subtitle_file=run_dir / "subtitles.srt",
        video_file=run_dir / "final_video.mp4",
        metadata_file=run_dir / "metadata.json",
    )


def decode_http_error(exc: error.HTTPError) -> str:
    try:
        payload = exc.read().decode("utf-8", errors="replace")
    except Exception:
        payload = "<no error body>"
    return f"HTTP {exc.code}: {payload}"


def post_json(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 120) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
        return json.loads(content)
    except error.HTTPError as exc:
        raise RuntimeError(f"API call failed for {url}: {decode_http_error(exc)}") from exc


def post_json_binary(url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int = 180) -> bytes:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = request.Request(
        url=url,
        data=body,
        method="POST",
        headers={"Content-Type": "application/json", **headers},
    )
    try:
        with request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except error.HTTPError as exc:
        raise RuntimeError(f"API call failed for {url}: {decode_http_error(exc)}") from exc


def extract_chat_text(response: dict[str, Any]) -> str:
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise RuntimeError(f"Unexpected OpenAI response: {response}")

    message = choices[0].get("message", {})
    content = message.get("content", "")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        chunks: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if isinstance(text, str) and text.strip():
                    chunks.append(text.strip())
        if chunks:
            return "\n".join(chunks).strip()
    raise RuntimeError(f"Unable to parse message content: {message}")


def normalize_script(text: str) -> str:
    cleaned = text.strip()
    cleaned = re.sub(r"^```[\w-]*\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def load_style_reference(style_file: str) -> str:
    if not style_file:
        return ""
    path = Path(style_file).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Style file not found: {path}")

    raw = read_text_file(path).strip()
    if not raw:
        return ""

    if path.suffix.lower() == ".json":
        try:
            obj = json.loads(raw)
            raw = json.dumps(obj, ensure_ascii=False, indent=2)
        except json.JSONDecodeError:
            pass
    return raw[:5000]


def generate_script(topic: str, seconds: int, style_reference: str, api_key: str, model: str) -> str:
    char_low = max(int(seconds * 3.5), 80)
    char_high = max(int(seconds * 4.5), char_low + 40)

    system_prompt = (
        "You are an expert script writer for short-form social videos. "
        "Return only the final Chinese voice-over script body."
    )
    user_prompt = f"""
Write a spoken Chinese script for WeChat Channels.
Requirements:
1) Topic: {topic}
2) Target length: around {seconds} seconds, roughly {char_low}-{char_high} Chinese chars.
3) Structure: 3-second hook -> core point -> one practical action -> CTA ending.
4) Conversational, short sentences, easy to speak in one take.
5) Do not include meta phrases like "as an AI" or "here is the script".
6) Output Chinese script content only.

Style reference (optional):
{style_reference or "None"}
""".strip()

    response = post_json(
        url=OPENAI_CHAT_URL,
        headers={"Authorization": f"Bearer {api_key}"},
        payload={
            "model": model,
            "temperature": 0.7,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        },
    )
    return normalize_script(extract_chat_text(response))


def synthesize_openai_tts(text: str, output_file: Path, api_key: str, model: str, voice: str) -> None:
    payload_candidates = [
        {"model": model, "voice": voice, "input": text, "response_format": "mp3"},
        {"model": model, "voice": voice, "input": text, "format": "mp3"},
    ]
    last_error: Exception | None = None
    for payload in payload_candidates:
        try:
            audio_bytes = post_json_binary(
                url=OPENAI_TTS_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Accept": "audio/mpeg",
                },
                payload=payload,
            )
            output_file.write_bytes(audio_bytes)
            return
        except Exception as exc:  # noqa: BLE001
            last_error = exc
    if last_error:
        raise RuntimeError(f"OpenAI TTS failed: {last_error}") from last_error
    raise RuntimeError("OpenAI TTS failed with unknown error.")


def synthesize_elevenlabs_tts(
    text: str,
    output_file: Path,
    api_key: str,
    voice_id: str,
    model_id: str,
) -> None:
    payload = {
        "text": text,
        "model_id": model_id,
        "voice_settings": {
            "stability": 0.35,
            "similarity_boost": 0.8,
            "style": 0.2,
            "use_speaker_boost": True,
        },
    }
    url = f"{ELEVENLABS_TTS_URL}/{voice_id}?output_format=mp3_44100_128"
    audio_bytes = post_json_binary(
        url=url,
        headers={
            "xi-api-key": api_key,
            "Accept": "audio/mpeg",
        },
        payload=payload,
    )
    output_file.write_bytes(audio_bytes)


async def _save_edge_tts(
    text: str,
    output_file: Path,
    voice: str,
    rate: str,
    volume: str,
) -> None:
    try:
        import edge_tts
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "edge-tts is not installed. Run: pip install edge-tts"
        ) from exc

    communicate = edge_tts.Communicate(
        text=text,
        voice=voice,
        rate=rate or "+0%",
        volume=volume or "+0%",
    )
    await communicate.save(str(output_file))


def synthesize_edge_tts(
    text: str,
    output_file: Path,
    voice: str,
    rate: str = "",
    volume: str = "",
) -> None:
    asyncio.run(
        _save_edge_tts(
            text=text,
            output_file=output_file,
            voice=voice,
            rate=rate,
            volume=volume,
    )
    )


def convert_audio_file(source_file: Path, output_file: Path) -> None:
    if source_file.resolve() == output_file.resolve():
        return

    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required to convert local TTS output into mp3.")

    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(source_file),
        "-vn",
        "-codec:a",
        "libmp3lame",
        "-q:a",
        "2",
        str(output_file),
    ]
    run_command(cmd)


def synthesize_pyttsx3_tts(
    text: str,
    output_file: Path,
    voice_hint: str = "",
    rate: int = 0,
) -> None:
    try:
        import pyttsx3
    except ImportError as exc:  # noqa: BLE001
        raise RuntimeError(
            "pyttsx3 is not installed. Run: pip install pyttsx3"
        ) from exc

    temp_wav = output_file.with_suffix(".wav")
    if temp_wav.exists():
        temp_wav.unlink()

    engine = pyttsx3.init()
    if rate > 0:
        engine.setProperty("rate", rate)
    if voice_hint:
        hint = voice_hint.lower()
        for voice in engine.getProperty("voices"):
            identity = " ".join(
                [
                    str(getattr(voice, "id", "")),
                    str(getattr(voice, "name", "")),
                    str(getattr(voice, "languages", "")),
                ]
            ).lower()
            if hint in identity:
                engine.setProperty("voice", voice.id)
                break

    engine.save_to_file(text, str(temp_wav))
    engine.runAndWait()
    engine.stop()
    if not temp_wav.exists():
        raise RuntimeError("pyttsx3 did not create an audio file.")
    convert_audio_file(temp_wav, output_file)
    temp_wav.unlink(missing_ok=True)


def probe_audio_duration(audio_file: Path) -> float | None:
    ffprobe_exe = resolve_binary("ffprobe")
    if not ffprobe_exe:
        return None

    cmd = [
        ffprobe_exe,
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(audio_file),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        return None
    try:
        return float(result.stdout.strip())
    except ValueError:
        return None


def estimate_duration_from_text(text: str) -> float:
    compact = re.sub(r"\s+", "", text)
    return max(len(compact) / 4.0, 4.0)


def contains_cjk(text: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", text))


def _clamp_float(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def _motion_profile(duration: float, rhythm_text: str, dynamic_style: str) -> tuple[float, float]:
    text = str(rhythm_text or "")
    compact = re.sub(r"\s+", "", text)
    punct_count = len(re.findall(r"[，,。.!！？?；;、]", text))
    excited_marks = len(re.findall(r"[!！?？]", text))
    density = punct_count / max(len(compact), 1)
    beat_hz = _clamp_float((punct_count + 2) / max(duration, 1.0), 0.55, 2.8)
    energy = _clamp_float(1.0 + excited_marks * 0.08 + density * 6.0, 0.9, 1.85)

    style = str(dynamic_style or "").strip().lower()
    if style == "comic":
        beat_hz = _clamp_float(beat_hz * 1.12, 0.55, 3.2)
        energy = _clamp_float(energy * 1.12, 0.95, 2.0)
    elif style == "gentle":
        beat_hz = _clamp_float(beat_hz * 0.85, 0.45, 2.2)
        energy = _clamp_float(energy * 0.88, 0.8, 1.5)
    return beat_hz, energy


def split_caption_units(script_text: str, max_line_chars: int) -> list[str]:
    normalized = script_text.replace("\r", " ").replace("\n", " ").strip()
    if not normalized:
        return []

    if contains_cjk(normalized):
        compact = re.sub(r"[ \t]+", "", normalized)
        pieces = [p.strip() for p in re.split(r"(?<=[.!?;\u3002\uff01\uff1f\uff1b])", compact) if p.strip()]
        if not pieces:
            pieces = [compact] if compact else []

        units: list[str] = []
        unit_limit = max(max_line_chars * 2, max_line_chars + 4)
        for piece in pieces:
            current = piece
            while len(current) > unit_limit:
                cut = current.rfind("\uFF0C", 0, unit_limit)
                if cut < max_line_chars:
                    cut = unit_limit
                chunk = current[:cut].strip("\uFF0C, ")
                if chunk:
                    units.append(chunk)
                current = current[cut:].lstrip("\uFF0C, ")
            if current:
                units.append(current)
        return units

    normalized = re.sub(r"\s+", " ", normalized)
    pieces = [p.strip() for p in re.split(r"(?<=[.!?;])\s+", normalized) if p.strip()]
    if not pieces:
        pieces = [normalized]

    units: list[str] = []
    unit_limit = max(max_line_chars * 2, max_line_chars + 8)
    for piece in pieces:
        if len(piece) <= unit_limit:
            units.append(piece)
            continue
        words = piece.split(" ")
        bucket: list[str] = []
        for word in words:
            trial = " ".join(bucket + [word]).strip()
            if bucket and len(trial) > unit_limit:
                units.append(" ".join(bucket))
                bucket = [word]
            else:
                bucket.append(word)
        if bucket:
            units.append(" ".join(bucket))
    return units


def wrap_caption_text(text: str, max_line_chars: int) -> str:
    if len(text) <= max_line_chars:
        return text
    if contains_cjk(text):
        cut = text.rfind("\uFF0C", 0, max_line_chars + 1)
        if cut < max_line_chars // 2:
            cut = max_line_chars
    else:
        cut = text.rfind(" ", 0, max_line_chars + 1)
        if cut < max_line_chars // 2:
            cut = max_line_chars
    first = text[:cut].strip("\uFF0C, ")
    second = text[cut:].lstrip("\uFF0C, ")
    return f"{first}\n{second}"


def format_srt_timestamp(seconds: float) -> str:
    total_ms = max(int(round(seconds * 1000)), 0)
    ms = total_ms % 1000
    total_s = total_ms // 1000
    sec = total_s % 60
    total_m = total_s // 60
    minute = total_m % 60
    hour = total_m // 60
    return f"{hour:02d}:{minute:02d}:{sec:02d},{ms:03d}"


def write_srt(units: list[str], total_duration: float, max_line_chars: int, output_file: Path) -> None:
    if not units:
        units = ["..."]

    weights = [max(len(re.sub(r"\s+", "", unit)), 1) for unit in units]
    total_weight = sum(weights)
    count = len(units)
    min_slot = 0.8

    if total_duration >= min_slot * count:
        remain = total_duration - min_slot * count
        durations = [min_slot + remain * (w / total_weight) for w in weights]
    else:
        durations = [total_duration * (w / total_weight) for w in weights]

    cursor = 0.0
    lines: list[str] = []
    for idx, (unit, slot) in enumerate(zip(units, durations), start=1):
        start = cursor
        end = total_duration if idx == count else min(total_duration, start + slot)
        if end <= start:
            end = min(total_duration, start + 0.1)
        text = wrap_caption_text(unit, max_line_chars)

        lines.append(str(idx))
        lines.append(f"{format_srt_timestamp(start)} --> {format_srt_timestamp(end)}")
        lines.append(text)
        lines.append("")
        cursor = end

    output_file.write_text("\n".join(lines), encoding="utf-8")


def parse_size(size: str) -> tuple[int, int]:
    token = size.lower().strip()
    if "x" not in token:
        raise ValueError("--size must be WIDTHxHEIGHT, for example 1080x1920")
    width_text, height_text = token.split("x", 1)
    width = int(width_text)
    height = int(height_text)
    if width <= 0 or height <= 0:
        raise ValueError("Width and height must be positive.")
    return width, height


def normalize_color(color: str) -> str:
    c = color.strip()
    if re.fullmatch(r"#[0-9a-fA-F]{6}", c):
        return f"0x{c[1:]}"
    return c


def escape_path_for_subtitles(path: Path) -> str:
    value = path.resolve().as_posix()
    value = value.replace(":", r"\:")
    value = value.replace("'", r"\'")
    value = value.replace(",", r"\,")
    return value


def run_command(cmd: list[str]) -> None:
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr_tail = "\n".join(result.stderr.splitlines()[-25:])
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{stderr_tail}")


def resolve_binary(name: str) -> str | None:
    direct = shutil.which(name)
    if direct:
        return direct

    script_dir = Path(__file__).resolve().parent
    ffmpeg_root = script_dir / "tools" / "ffmpeg"
    if not ffmpeg_root.exists():
        return None

    exe_name = f"{name}.exe" if os.name == "nt" else name
    for build_dir in sorted(ffmpeg_root.glob("*"), reverse=True):
        candidate = build_dir / "bin" / exe_name
        if candidate.exists():
            return str(candidate)
    return None


def render_video(
    audio_file: Path,
    subtitle_file: Path,
    output_file: Path,
    size: str,
    fps: int,
    background_image: str,
    bg_color: str,
    subtitle_font: str,
    subtitle_size: int,
    subtitle_margin_v: int,
    duration: float,
    dynamic_background: bool = False,
    dynamic_style: str = "gentle",
    dynamic_rhythm_text: str = "",
) -> None:
    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError(
            "ffmpeg not found. Install ffmpeg or place it under tools/ffmpeg/<build>/bin."
        )

    width, height = parse_size(size)
    subtitle_style = (
        f"FontName={subtitle_font},"
        f"FontSize={subtitle_size},"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BorderStyle=1,"
        "Outline=2,"
        "Shadow=0,"
        "Alignment=2,"
        f"MarginV={subtitle_margin_v}"
    )
    subtitle_filter = (
        f"subtitles='{escape_path_for_subtitles(subtitle_file)}':"
        f"force_style='{subtitle_style}'"
    )
    beat_hz, motion_energy = _motion_profile(duration, dynamic_rhythm_text, dynamic_style)

    if background_image:
        image_path = Path(background_image).expanduser().resolve()
        if not image_path.exists():
            raise FileNotFoundError(f"Background image not found: {image_path}")
        if dynamic_background:
            if str(dynamic_style).strip().lower() == "comic":
                speed_x = round(beat_hz * 1.55, 3)
                speed_y = round(beat_hz * 1.22, 3)
                offset_x = int(max(14, width * 0.022 * motion_energy))
                offset_y = int(max(10, height * 0.02 * motion_energy))
                scale_ratio = _clamp_float(1.12 + 0.06 * motion_energy, 1.10, 1.26)
            else:
                speed_x = round(beat_hz * 1.2, 3)
                speed_y = round(beat_hz * 1.05, 3)
                offset_x = int(max(10, width * 0.018 * motion_energy))
                offset_y = int(max(8, height * 0.016 * motion_energy))
                scale_ratio = _clamp_float(1.08 + 0.05 * motion_energy, 1.08, 1.2)
            scaled_w = int(width * scale_ratio)
            scaled_h = int(height * scale_ratio)
            vf = ",".join(
                [
                    f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase",
                    (
                        f"crop={width}:{height}:"
                        f"x='(in_w-out_w)/2+sin(t*{speed_x})*{offset_x}':"
                        f"y='(in_h-out_h)/2+cos(t*{speed_y})*{offset_y}'"
                    ),
                    subtitle_filter,
                ]
            )
        else:
            vf = ",".join(
                [
                    f"scale={width}:{height}:force_original_aspect_ratio=increase",
                    f"crop={width}:{height}",
                    subtitle_filter,
                ]
            )
        cmd = [
            ffmpeg_exe,
            "-y",
            "-loop",
            "1",
            "-framerate",
            str(fps),
            "-i",
            str(image_path),
            "-i",
            str(audio_file),
            "-vf",
            vf,
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
        run_command(cmd)
        return

    color_source = f"color=c={normalize_color(bg_color)}:s={width}x{height}:r={fps}:d={duration:.3f}"
    vf = subtitle_filter
    if dynamic_background:
        bar_width = int(max(120, width * (0.18 + 0.05 * (motion_energy - 1.0))))
        swing = int(max(18, width * 0.08 * motion_energy))
        bar_speed = round(beat_hz * 1.1, 3)
        vf = ",".join(
            [
                (
                    "drawbox="
                    f"x='(iw-w)/2+sin(t*{bar_speed})*{swing}':y=0:w={bar_width}:h=ih:"
                    "color=white@0.06:t=fill"
                ),
                subtitle_filter,
            ]
        )

    cmd = [
        ffmpeg_exe,
        "-y",
        "-f",
        "lavfi",
        "-i",
        color_source,
        "-i",
        str(audio_file),
        "-vf",
        vf,
        "-r",
        str(fps),
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_file),
    ]
    run_command(cmd)


def _require_native_animation_stack() -> None:
    if cv2 is None or np is None:
        raise RuntimeError(
            "Native animation renderer requires opencv-python and numpy."
        )


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _normalize_story_lines(script_text: str) -> list[str]:
    source = str(script_text or "").replace("\r", "\n")
    raw = [item.strip() for item in re.split(r"[\n]+", source) if item.strip()]
    lines: list[str] = []
    for item in raw:
        pieces = [part.strip() for part in re.split(r"(?<=[。！？!?；;])", item) if part.strip()]
        if pieces:
            lines.extend(pieces)
        else:
            lines.append(item)
    return lines or ["拟人化毛豆开始今天的温柔小冒险。"]


def _build_story_shots(
    *,
    script_text: str,
    duration: float,
    storyboard_payload: Any,
) -> list[StoryShot]:
    lines = _normalize_story_lines(script_text)
    fallback_shots = [
        "wide_duo_establishing",
        "medium_duo_dialog",
        "tracking_duo_motion",
        "medium_duo_reaction",
        "wide_duo_action",
        "tracking_duo_follow",
    ]
    fallback_actions = [
        "walk_and_wave",
        "point_and_explain",
        "gentle_step",
        "smile_and_nod",
        "gentle_step",
        "laughing_talk",
        "point_and_explain",
    ]

    parsed_payload: list[StoryShot] = []
    if isinstance(storyboard_payload, list):
        for item in storyboard_payload:
            if not isinstance(item, dict):
                continue
            start_s = _safe_float(item.get("start_s"), -1.0)
            end_s = _safe_float(item.get("end_s"), -1.0)
            if end_s <= start_s or start_s < 0:
                continue
            parsed_payload.append(
                StoryShot(
                    start_s=max(0.0, start_s),
                    end_s=min(duration, end_s),
                    shot_type=str(item.get("shot_type", "wide_duo_establishing")) or "wide_duo_establishing",
                    action_hint=str(item.get("action_hint", "point_and_explain")) or "point_and_explain",
                    speaker=str(item.get("speaker", "maodou")) or "maodou",
                    line=str(item.get("line", "")).strip(),
                    emotion=str(item.get("emotion", "happy")).strip() or "happy",
                    scene_key=str(item.get("scene_key", "park_lane")).strip() or "park_lane",
                )
            )

    if parsed_payload:
        parsed_payload = [shot for shot in parsed_payload if shot.end_s > shot.start_s]
        if parsed_payload:
            parsed_payload.sort(key=lambda item: item.start_s)
            parsed_payload[0].start_s = 0.0
            parsed_payload[-1].end_s = duration
            return parsed_payload

    segment_count = min(max(len(lines), 5), 8)
    segment_duration = max(duration / float(segment_count), 3.5)
    cursor = 0.0
    built: list[StoryShot] = []
    for index in range(segment_count):
        start_s = cursor
        end_s = min(duration, start_s + segment_duration)
        built.append(
            StoryShot(
                start_s=start_s,
                end_s=end_s,
                shot_type=fallback_shots[index % len(fallback_shots)],
                action_hint=fallback_actions[index % len(fallback_actions)],
                speaker="maodou" if index % 2 == 0 else "peanut",
                line=lines[index % len(lines)],
                scene_key=["park_lane", "flower_garden", "farm_patch", "mini_stage"][index % 4],
            )
        )
        cursor = end_s
        if cursor >= duration:
            break
    if built:
        built[-1].end_s = duration
    return built


def _find_shot_at_time(shots: list[StoryShot], t: float) -> tuple[int, StoryShot]:
    if not shots:
        default_shot = StoryShot(
            start_s=0.0,
            end_s=max(t + 1.0, 1.0),
            shot_type="wide_duo_establishing",
            action_hint="point_and_explain",
            speaker="maodou",
            line="",
        )
        return 0, default_shot
    for index, shot in enumerate(shots):
        if t < shot.end_s or index == len(shots) - 1:
            return index, shot
    return len(shots) - 1, shots[-1]


def _ease_in_out(x: float) -> float:
    clamped = _clamp_float(x, 0.0, 1.0)
    return clamped * clamped * (3.0 - 2.0 * clamped)


def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _is_3d_style(animation_style: str) -> bool:
    return "3d" in str(animation_style or "").strip().lower()


def _is_toddler_single_style(animation_style: str) -> bool:
    style = str(animation_style or "").strip().lower()
    return ("toddler" in style and "single" in style) or "single_toddler" in style


def _draw_base_scene(
    scene_w: int,
    scene_h: int,
    *,
    three_d: bool = False,
    toddler_mode: bool = False,
) -> Any:
    if three_d and not toddler_mode:
        y = np.linspace(0.0, 1.0, scene_h, dtype=np.float32)[:, None]
        x = np.linspace(0.0, 1.0, scene_w, dtype=np.float32)[None, :]
        cx = 0.5 + 0.04 * np.sin(x * math.pi)
        cy = 0.38
        radius = np.sqrt((x - cx) ** 2 + (y - cy) ** 2)
        spotlight = np.clip(1.0 - radius * 1.75, 0.0, 1.0)
        floor = np.clip((y - 0.63) * 2.6, 0.0, 1.0)
        b = 58 + 64 * spotlight + 16 * floor
        g = 112 + 118 * spotlight + 34 * floor
        r = 42 + 38 * spotlight + 18 * floor
        canvas = np.stack([b, g, r], axis=2).astype(np.uint8)
        overlay = canvas.copy()
        cv2.ellipse(
            overlay,
            (int(scene_w * 0.5), int(scene_h * 0.82)),
            (int(scene_w * 0.34), int(scene_h * 0.08)),
            0,
            0,
            360,
            (70, 132, 68),
            -1,
            cv2.LINE_AA,
        )
        cv2.addWeighted(overlay, 0.18, canvas, 0.82, 0.0, canvas)
        return canvas

    if toddler_mode:
        y = np.linspace(0.0, 1.0, scene_h, dtype=np.float32)[:, None]
        x = np.linspace(0.0, 1.0, scene_w, dtype=np.float32)[None, :]
        sky_b = (236.0 - 20.0 * y + 3.0 * np.sin(x * math.pi * 0.8)).astype(np.uint8)
        sky_g = (244.0 - 18.0 * y + 2.0 * np.cos(x * math.pi * 0.7)).astype(np.uint8)
        sky_r = (255.0 - 10.0 * y + 0.0 * x).astype(np.uint8)
        canvas = np.stack([sky_b, sky_g, sky_r], axis=2)
        ground_start = int(scene_h * 0.68)
        ground = canvas[ground_start:]
        gy = np.linspace(0.0, 1.0, ground.shape[0], dtype=np.float32)[:, None]
        ground[:, :, 0] = np.clip(150.0 + gy * 25.0, 0, 255).astype(np.uint8)
        ground[:, :, 1] = np.clip(212.0 + gy * 20.0, 0, 255).astype(np.uint8)
        ground[:, :, 2] = np.clip(142.0 + gy * 14.0, 0, 255).astype(np.uint8)
        cv2.circle(canvas, (int(scene_w * 0.18), int(scene_h * 0.2)), int(scene_h * 0.09), (255, 248, 210), -1, cv2.LINE_AA)
        cv2.circle(canvas, (int(scene_w * 0.18), int(scene_h * 0.2)), int(scene_h * 0.05), (255, 255, 232), -1, cv2.LINE_AA)
        return canvas

    y = np.linspace(0.0, 1.0, scene_h, dtype=np.float32)[:, None]
    x = np.linspace(0.0, 1.0, scene_w, dtype=np.float32)[None, :]
    sky_b = (230.0 - 42.0 * y + 6.0 * np.sin(x * math.pi)).astype(np.uint8)
    sky_g = (240.0 - 58.0 * y + 4.0 * np.cos(x * math.pi * 0.7)).astype(np.uint8)
    sky_r = (255.0 - 72.0 * y + 3.0 * np.sin((x + y) * math.pi)).astype(np.uint8)
    canvas = np.stack([sky_b, sky_g, sky_r], axis=2)

    ground_start = int(scene_h * 0.68)
    ground = canvas[ground_start:]
    gy = np.linspace(0.0, 1.0, ground.shape[0], dtype=np.float32)[:, None]
    ground[:, :, 0] = np.clip(120.0 + gy * 40.0, 0, 255).astype(np.uint8)
    ground[:, :, 1] = np.clip(180.0 + gy * 45.0, 0, 255).astype(np.uint8)
    ground[:, :, 2] = np.clip(110.0 + gy * 25.0, 0, 255).astype(np.uint8)
    if three_d:
        overlay = canvas.copy()
        sun_center = (int(scene_w * 0.18), int(scene_h * 0.22))
        cv2.circle(overlay, sun_center, int(scene_h * 0.14), (255, 244, 208), -1, lineType=cv2.LINE_AA)
        cv2.circle(overlay, sun_center, int(scene_h * 0.085), (255, 255, 238), -1, lineType=cv2.LINE_AA)

        horizon = int(scene_h * 0.66)
        for idx in range(4):
            ridge_y = int(horizon - scene_h * (0.04 + idx * 0.025))
            color = (128 + idx * 8, 170 + idx * 6, 140 + idx * 10)
            cv2.ellipse(
                overlay,
                (int(scene_w * (0.18 + idx * 0.23)), ridge_y),
                (int(scene_w * 0.24), int(scene_h * 0.08)),
                0,
                180,
                360,
                color,
                -1,
                lineType=cv2.LINE_AA,
            )
        cv2.addWeighted(overlay, 0.24, canvas, 0.76, 0.0, canvas)

        for row in range(9):
            ratio = row / 8.0
            y_line = int(horizon + (scene_h - horizon) * (ratio**1.55))
            alpha_color = (96 + int(30 * ratio), 158 + int(18 * ratio), 118 + int(20 * ratio))
            cv2.line(canvas, (0, y_line), (scene_w, y_line), alpha_color, 1, lineType=cv2.LINE_AA)
        vanishing_x = int(scene_w * 0.5)
        for col in range(-6, 7):
            base_x = int(vanishing_x + col * scene_w * 0.08)
            cv2.line(
                canvas,
                (vanishing_x, horizon),
                (base_x, scene_h),
                (92, 146, 106),
                1,
                lineType=cv2.LINE_AA,
            )
    return canvas


def _draw_environment(
    frame: Any,
    t: float,
    scene_w: int,
    scene_h: int,
    *,
    three_d: bool = False,
    toddler_mode: bool = False,
    scene_key: str = "park_lane",
) -> None:
    if toddler_mode:
        cloud_speed = 10.0
        for idx in range(3):
            phase = (t * cloud_speed + idx * 220.0) % (scene_w + 220.0)
            cx = int(phase - 110.0)
            cy = int(scene_h * (0.16 + idx * 0.08))
            cv2.ellipse(frame, (cx, cy), (92, 30), 0, 0, 360, (255, 255, 255), -1, lineType=cv2.LINE_AA)
            cv2.ellipse(frame, (cx + 44, cy + 5), (66, 24), 0, 0, 360, (248, 252, 255), -1, lineType=cv2.LINE_AA)
        hill_y = int(scene_h * 0.73)
        cv2.ellipse(frame, (int(scene_w * 0.28), hill_y), (int(scene_w * 0.28), int(scene_h * 0.1)), 0, 180, 360, (152, 224, 156), -1, cv2.LINE_AA)
        cv2.ellipse(frame, (int(scene_w * 0.74), hill_y + 8), (int(scene_w * 0.25), int(scene_h * 0.09)), 0, 180, 360, (142, 216, 146), -1, cv2.LINE_AA)
        return

    scene_key = str(scene_key or "park_lane").strip().lower()
    if three_d:
        lower_y = int(scene_h * 0.74)
        for idx in range(5):
            leaf_x = int(scene_w * (0.14 + idx * 0.18) + math.sin(t * 0.6 + idx) * 14.0)
            leaf_y = int(scene_h * (0.2 + (idx % 3) * 0.08))
            cv2.ellipse(frame, (leaf_x, leaf_y), (48, 18), -22, 0, 360, (74, 150, 69), -1, cv2.LINE_AA)
            cv2.ellipse(frame, (leaf_x + 22, leaf_y + 6), (32, 12), 18, 0, 360, (91, 171, 82), -1, cv2.LINE_AA)

        if scene_key == "flower_garden":
            for idx in range(16):
                flower_x = int(scene_w * (0.08 + idx * 0.055))
                flower_y = int(lower_y + scene_h * 0.08 + math.sin(t * 2.0 + idx) * 5)
                stem_color = (48, 132, 56)
                cv2.line(frame, (flower_x, flower_y + 26), (flower_x, flower_y), stem_color, 3, cv2.LINE_AA)
                petal_color = (87, 179, 255) if idx % 3 == 0 else (139, 118, 255) if idx % 3 == 1 else (86, 222, 246)
                for angle in range(0, 360, 90):
                    px = int(flower_x + math.cos(math.radians(angle)) * 7)
                    py = int(flower_y + math.sin(math.radians(angle)) * 7)
                    cv2.circle(frame, (px, py), 6, petal_color, -1, cv2.LINE_AA)
                cv2.circle(frame, (flower_x, flower_y), 5, (72, 214, 255), -1, cv2.LINE_AA)
        elif scene_key == "farm_patch":
            for row in range(3):
                y_row = int(lower_y + scene_h * (0.035 + row * 0.04))
                cv2.ellipse(frame, (int(scene_w * 0.5), y_row), (int(scene_w * 0.36), int(scene_h * 0.018)), 0, 0, 360, (65, 124, 92), 3, cv2.LINE_AA)
                for col in range(7):
                    sprout_x = int(scene_w * (0.2 + col * 0.1) + math.sin(t + row + col) * 3)
                    cv2.line(frame, (sprout_x, y_row), (sprout_x, y_row - 16), (46, 140, 62), 3, cv2.LINE_AA)
                    cv2.ellipse(frame, (sprout_x - 5, y_row - 15), (7, 4), -25, 0, 360, (82, 207, 86), -1, cv2.LINE_AA)
                    cv2.ellipse(frame, (sprout_x + 5, y_row - 15), (7, 4), 25, 0, 360, (110, 226, 94), -1, cv2.LINE_AA)
        elif scene_key == "mini_stage":
            for idx in range(8):
                x0 = int(scene_w * (0.22 + idx * 0.07))
                y0 = int(scene_h * 0.22 + math.sin(t * 1.8 + idx) * 4)
                color = (255, 210, 87) if idx % 2 == 0 else (116, 211, 255)
                pts = np.array([[x0, y0], [x0 + 18, y0 + 24], [x0 - 18, y0 + 24]], dtype=np.int32)
                cv2.fillConvexPoly(frame, pts, color, cv2.LINE_AA)
            cv2.ellipse(frame, (int(scene_w * 0.5), int(scene_h * 0.88)), (int(scene_w * 0.34), int(scene_h * 0.045)), 0, 0, 360, (71, 109, 168), -1, cv2.LINE_AA)
        else:
            for idx in range(7):
                bush_x = int(scene_w * (0.1 + idx * 0.14) + math.sin(t * 0.8 + idx) * 9.0)
                bush_y = int(lower_y + scene_h * 0.08)
                cv2.ellipse(frame, (bush_x, bush_y), (52, 22), 0, 0, 360, (77, 164, 82), -1, cv2.LINE_AA)
                cv2.ellipse(frame, (bush_x + 24, bush_y + 5), (36, 16), 0, 0, 360, (90, 184, 91), -1, cv2.LINE_AA)
        return

    cloud_speed = 24.0 if three_d else 26.0
    for idx in range(4):
        layer_speed = cloud_speed * (0.72 + idx * 0.1) if three_d else cloud_speed
        phase = (t * layer_speed + idx * 180.0) % (scene_w + 240.0)
        cx = int(phase - 120.0)
        cy = int(scene_h * (0.16 + idx * 0.07))
        cv2.ellipse(frame, (cx, cy), (96, 34), 0, 0, 360, (255, 255, 255), -1, lineType=cv2.LINE_AA)
        cv2.ellipse(frame, (cx + 52, cy + 6), (72, 28), 0, 0, 360, (250, 250, 255), -1, lineType=cv2.LINE_AA)
    flower_count = 22 if scene_key == "flower_garden" else 12
    for idx in range(flower_count):
        flower_x = int((idx + 0.5) * scene_w / float(flower_count))
        petal_shift = int(3.0 * math.sin(t * 3.2 + idx))
        stem_top = int(scene_h * 0.76 + petal_shift)
        stem_bottom = int(scene_h * 0.86)
        cv2.line(frame, (flower_x, stem_bottom), (flower_x, stem_top), (58, 120, 45), 3, lineType=cv2.LINE_AA)
        petal_color = (88, 171, 255) if idx % 3 == 0 else (120, 105, 255) if idx % 3 == 1 else (68, 208, 247)
        cv2.circle(frame, (flower_x - 5, stem_top), 6, petal_color, -1, lineType=cv2.LINE_AA)
        cv2.circle(frame, (flower_x + 5, stem_top), 6, petal_color, -1, lineType=cv2.LINE_AA)

    board_top = int(scene_h * 0.56)
    board_left = int(scene_w * 0.07)
    board_right = int(scene_w * 0.28)
    board_bottom = int(scene_h * 0.72)
    label = "MAODOU PARK"
    if scene_key == "farm_patch":
        label = "FARM PATCH"
        soil_top = int(scene_h * 0.69)
        for row in range(5):
            y = int(soil_top + row * scene_h * 0.055)
            cv2.ellipse(frame, (int(scene_w * 0.5), y), (int(scene_w * 0.44), int(scene_h * 0.018)), 0, 0, 360, (76, 132, 174), 3, cv2.LINE_AA)
            for col in range(7):
                sprout_x = int(scene_w * (0.2 + col * 0.1) + math.sin(t + row + col) * 4)
                cv2.line(frame, (sprout_x, y), (sprout_x, y - 18), (58, 136, 65), 3, cv2.LINE_AA)
                cv2.ellipse(frame, (sprout_x - 5, y - 17), (7, 4), -25, 0, 360, (78, 190, 85), -1, cv2.LINE_AA)
                cv2.ellipse(frame, (sprout_x + 5, y - 17), (7, 4), 25, 0, 360, (88, 205, 95), -1, cv2.LINE_AA)
    elif scene_key == "mini_stage":
        label = "HAPPY STAGE"
        stage_y = int(scene_h * 0.77)
        cv2.rectangle(frame, (int(scene_w * 0.18), stage_y), (int(scene_w * 0.82), int(scene_h * 0.9)), (92, 111, 214), -1)
        cv2.rectangle(frame, (int(scene_w * 0.18), stage_y), (int(scene_w * 0.82), int(scene_h * 0.9)), (62, 72, 155), 4)
        for idx in range(9):
            x = int(scene_w * (0.22 + idx * 0.07))
            y = int(scene_h * 0.5 + math.sin(t * 2.0 + idx) * 7)
            color = (255, 210, 87) if idx % 2 == 0 else (116, 211, 255)
            cv2.circle(frame, (x, y), 12, color, -1, cv2.LINE_AA)
    elif scene_key == "flower_garden":
        label = "FLOWER GARDEN"
        for idx in range(6):
            cx = int(scene_w * (0.14 + idx * 0.14))
            cy = int(scene_h * (0.69 + 0.02 * math.sin(t + idx)))
            cv2.ellipse(frame, (cx, cy), (80, 28), 0, 0, 360, (104, 190, 126), -1, cv2.LINE_AA)

    cv2.rectangle(frame, (board_left, board_top), (board_right, board_bottom), (173, 214, 255), -1)
    cv2.rectangle(frame, (board_left, board_top), (board_right, board_bottom), (121, 137, 162), 3)
    cv2.putText(
        frame,
        label,
        (board_left + 10, board_top + 36),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.58,
        (46, 81, 122),
        2,
        lineType=cv2.LINE_AA,
    )
    if three_d:
        horizon = int(scene_h * 0.66)
        for idx in range(5):
            bush_x = int((idx + 0.35) * scene_w / 5.0 + math.sin(t * 0.8 + idx) * 16.0)
            bush_y = int(scene_h * (0.72 + idx * 0.015))
            cv2.ellipse(frame, (bush_x, bush_y), (58, 24), 0, 0, 360, (96, 180, 114), -1, cv2.LINE_AA)
            cv2.ellipse(frame, (bush_x + 28, bush_y + 3), (44, 19), 0, 0, 360, (84, 162, 100), -1, cv2.LINE_AA)
        overlay = frame.copy()
        glow_center = (int(scene_w * 0.26 + math.sin(t * 0.65) * 22.0), int(scene_h * 0.18))
        cv2.circle(overlay, glow_center, int(scene_h * 0.16), (255, 241, 212), -1, lineType=cv2.LINE_AA)
        cv2.addWeighted(overlay, 0.09, frame, 0.91, 0.0, frame)
        for col in range(-5, 6):
            x1 = int(scene_w * 0.5 + col * scene_w * 0.1)
            x2 = int(x1 + col * 24 + math.sin(t * 0.9 + col) * 8.0)
            cv2.line(frame, (x1, horizon), (x2, scene_h), (105, 162, 118), 1, lineType=cv2.LINE_AA)


def _draw_contact_shadow(frame: Any, cx: float, cy: float, scale: float, strength: float = 0.32) -> None:
    overlay = frame.copy()
    cv2.ellipse(
        overlay,
        (int(cx), int(cy + 24.0 * scale)),
        (max(int(48 * scale), 12), max(int(13 * scale), 4)),
        0,
        0,
        360,
        (32, 42, 56),
        -1,
        lineType=cv2.LINE_AA,
    )
    cv2.addWeighted(overlay, _clamp_float(strength, 0.05, 0.7), frame, 1.0 - _clamp_float(strength, 0.05, 0.7), 0.0, frame)


def _shade_character_volume(
    frame: Any,
    *,
    center: tuple[int, int],
    body_w: int,
    body_h: int,
    highlight_color: tuple[int, int, int],
    shadow_color: tuple[int, int, int],
    strength: float,
) -> None:
    overlay = frame.copy()
    highlight_center = (int(center[0] - body_w * 0.18), int(center[1] - body_h * 0.2))
    shadow_center = (int(center[0] + body_w * 0.2), int(center[1] + body_h * 0.22))
    cv2.ellipse(
        overlay,
        highlight_center,
        (max(body_w // 5, 6), max(body_h // 6, 6)),
        -15,
        0,
        360,
        highlight_color,
        -1,
        lineType=cv2.LINE_AA,
    )
    cv2.ellipse(
        overlay,
        shadow_center,
        (max(body_w // 4, 8), max(body_h // 5, 8)),
        18,
        0,
        360,
        shadow_color,
        -1,
        lineType=cv2.LINE_AA,
    )
    alpha = _clamp_float(strength, 0.08, 0.45)
    cv2.addWeighted(overlay, alpha, frame, 1.0 - alpha, 0.0, frame)


def _pose_from_action(action_hint: str, t: float, speaking: bool, *, gentle_motion: bool = False) -> dict[str, float]:
    action = str(action_hint or "").strip().lower()
    fast = 0.7 if gentle_motion else 1.0
    stride = 0.0
    bounce = 0.0
    arm_wave = 0.0
    eye_scale = 1.0
    smile = 0.45
    brow = 0.0
    cheek = 0.42
    if "run" in action or "chase" in action:
        fast = 0.85 if gentle_motion else 1.8
        stride = math.sin(t * (3.6 if gentle_motion else 9.2)) * (0.35 if gentle_motion else 1.0)
        bounce = abs(math.sin(t * (3.8 if gentle_motion else 9.2))) * (0.08 if gentle_motion else 0.14)
    elif "jump" in action:
        fast = 0.8 if gentle_motion else 1.2
        stride = math.sin(t * (2.6 if gentle_motion else 5.4)) * (0.22 if gentle_motion else 0.35)
        bounce = abs(math.sin(t * (2.4 if gentle_motion else 4.8))) * (0.12 if gentle_motion else 0.26)
        arm_wave = math.sin(t * (2.8 if gentle_motion else 6.2)) * (0.45 if gentle_motion else 0.95)
    elif "wave" in action:
        stride = math.sin(t * (2.2 if gentle_motion else 5.2)) * (0.2 if gentle_motion else 0.45)
        arm_wave = math.sin(t * (2.8 if gentle_motion else 7.0)) * (0.55 if gentle_motion else 1.2)
    elif "surprise" in action:
        eye_scale = 1.2 if gentle_motion else 1.35
        smile = 0.18
        brow = 0.9
        cheek = 0.18
        stride = math.sin(t * (2.2 if gentle_motion else 5.6)) * (0.12 if gentle_motion else 0.22)
    elif "laugh" in action:
        stride = math.sin(t * (2.4 if gentle_motion else 6.0)) * (0.18 if gentle_motion else 0.34)
        arm_wave = math.sin(t * (3.0 if gentle_motion else 8.2)) * (0.35 if gentle_motion else 0.62)
        smile = 0.92
        brow = 0.2
        cheek = 0.85
    elif "hug" in action:
        stride = math.sin(t * (1.8 if gentle_motion else 3.8)) * (0.1 if gentle_motion else 0.2)
        smile = 0.86
        brow = 0.25
        cheek = 0.75
    elif "thinking" in action:
        eye_scale = 0.88
        smile = 0.22
        brow = -0.65
        cheek = 0.22
        stride = math.sin(t * (1.8 if gentle_motion else 3.6)) * (0.08 if gentle_motion else 0.16)
    elif "encourage" in action or "closeup" in action:
        eye_scale = 1.14
        smile = 0.82
        brow = 0.35
        cheek = 0.9
        arm_wave = math.sin(t * (2.2 if gentle_motion else 4.8)) * (0.25 if gentle_motion else 0.5)
    else:
        stride = math.sin(t * (2.0 if gentle_motion else 4.6)) * (0.14 if gentle_motion else 0.3)
        arm_wave = math.sin(t * (2.6 if gentle_motion else 5.2)) * (0.2 if gentle_motion else 0.45)
    mouth_open = 0.35 + 0.45 * (0.5 + 0.5 * math.sin(t * ((4.2 if gentle_motion else 7.0) * fast)))
    if not speaking:
        mouth_open *= 0.25
    return {
        "stride": stride,
        "bounce": bounce,
        "arm_wave": arm_wave,
        "eye_scale": eye_scale,
        "smile": smile,
        "brow": brow,
        "cheek": cheek,
        "mouth_open": mouth_open,
    }


def _draw_maodou(
    frame: Any,
    cx: float,
    cy: float,
    scale: float,
    pose: dict[str, float],
    *,
    three_d: bool = False,
) -> None:
    body_w = int(138 * scale)
    body_h = int(188 * scale)
    head_tilt = int(5 * math.sin(pose["stride"] * 2.2))
    body_center = (int(cx), int(cy - pose["bounce"] * 50 * scale))
    if three_d:
        _draw_contact_shadow(frame, cx, cy, scale, strength=0.34)
    pod_fill = (93, 215, 107)
    pod_edge = (32, 132, 55)
    cv2.ellipse(frame, body_center, (body_w // 2, body_h // 2), head_tilt, 0, 360, pod_fill, -1, cv2.LINE_AA)
    cv2.ellipse(frame, body_center, (body_w // 2, body_h // 2), head_tilt, 0, 360, pod_edge, 5, cv2.LINE_AA)
    if three_d:
        _shade_character_volume(
            frame,
            center=body_center,
            body_w=body_w,
            body_h=body_h,
            highlight_color=(190, 255, 174),
            shadow_color=(45, 96, 52),
            strength=0.24,
        )
    inner_center = (body_center[0] + int(body_w * 0.04), body_center[1] + int(body_h * 0.06))
    inner_axes = (int(body_w * 0.34), int(body_h * 0.38))
    cv2.ellipse(frame, inner_center, inner_axes, head_tilt + 4, 0, 360, (58, 171, 70), -1, cv2.LINE_AA)
    cv2.ellipse(frame, inner_center, inner_axes, head_tilt + 4, 0, 360, (188, 246, 132), 5, cv2.LINE_AA)
    cv2.ellipse(
        frame,
        (body_center[0] - int(body_w * 0.19), body_center[1] - int(body_h * 0.02)),
        (int(body_w * 0.19), int(body_h * 0.46)),
        head_tilt - 8,
        252,
        108,
        (185, 248, 150),
        5,
        cv2.LINE_AA,
    )
    bean_centers = [
        (inner_center[0] + int(body_w * 0.02), int(inner_center[1] - body_h * 0.22)),
        (inner_center[0] - int(body_w * 0.04), int(inner_center[1] + body_h * 0.02)),
        (inner_center[0] + int(body_w * 0.05), int(inner_center[1] + body_h * 0.25)),
    ]
    for idx, bean_center in enumerate(bean_centers):
        bean_r = int((26 + idx * 2) * scale)
        cv2.circle(frame, bean_center, bean_r, (126, 236, 119), -1, cv2.LINE_AA)
        cv2.circle(frame, bean_center, bean_r, (51, 155, 63), 2, cv2.LINE_AA)
        cv2.circle(
            frame,
            (bean_center[0] - int(bean_r * 0.28), bean_center[1] - int(bean_r * 0.34)),
            max(int(bean_r * 0.18), 3),
            (210, 255, 195),
            -1,
            cv2.LINE_AA,
        )

    eye_y = int(body_center[1] - body_h * 0.21)
    eye_offset = int(body_w * 0.17)
    eye_r = max(int(13 * scale * pose["eye_scale"]), 5)
    for delta in (-eye_offset, eye_offset):
        cv2.circle(frame, (body_center[0] + delta, eye_y), eye_r + 2, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, (body_center[0] + delta + int(1.5 * pose["stride"]), eye_y), eye_r, (48, 49, 62), -1, cv2.LINE_AA)
        cv2.circle(
            frame,
            (body_center[0] + delta - int(eye_r * 0.35), eye_y - int(eye_r * 0.35)),
            max(int(eye_r * 0.32), 2),
            (255, 255, 255),
            -1,
            cv2.LINE_AA,
        )
        brow_y = eye_y - int(eye_r * 2.2)
        brow_slope = int(8 * scale * pose.get("brow", 0.0))
        cv2.line(
            frame,
            (body_center[0] + delta - int(13 * scale), brow_y + brow_slope),
            (body_center[0] + delta + int(13 * scale), brow_y - brow_slope),
            (36, 101, 45),
            max(int(4 * scale), 2),
            cv2.LINE_AA,
        )

    mouth_w = max(int(46 * scale), 14)
    mouth_h = max(int((13 + 22 * pose["mouth_open"]) * scale), 7)
    mouth_y = int(body_center[1] - body_h * 0.03)
    cv2.ellipse(frame, (body_center[0], mouth_y), (mouth_w // 2, mouth_h // 2), 0, 0, 360, (37, 29, 48), -1, cv2.LINE_AA)
    cv2.ellipse(
        frame,
        (body_center[0], mouth_y + int(mouth_h * 0.16)),
        (max(mouth_w // 4, 4), max(mouth_h // 5, 3)),
        0,
        0,
        360,
        (116, 82, 242),
        -1,
        cv2.LINE_AA,
    )
    cv2.ellipse(frame, (body_center[0], mouth_y), (mouth_w // 2, mouth_h // 2), 0, 0, 360, (44, 56, 89), 3, cv2.LINE_AA)
    cv2.ellipse(
        frame,
        (body_center[0] - int(mouth_w * 0.12), mouth_y - int(mouth_h * 0.28)),
        (max(mouth_w // 5, 4), max(mouth_h // 8, 2)),
        0,
        0,
        180,
        (255, 255, 255),
        -1,
        cv2.LINE_AA,
    )
    cheek_alpha = _clamp_float(pose.get("cheek", 0.4), 0.0, 1.0)
    if cheek_alpha > 0.1:
        cheek_color = (100, 188, 142)
        cv2.ellipse(
            frame,
            (body_center[0] - int(body_w * 0.27), mouth_y - int(8 * scale)),
            (int(10 * scale), int(5 * scale)),
            0,
            0,
            360,
            cheek_color,
            -1,
            cv2.LINE_AA,
        )
        cv2.ellipse(
            frame,
            (body_center[0] + int(body_w * 0.27), mouth_y - int(8 * scale)),
            (int(10 * scale), int(5 * scale)),
            0,
            0,
            360,
            cheek_color,
            -1,
            cv2.LINE_AA,
        )
    if three_d:
        cv2.circle(
            frame,
            (body_center[0] - int(body_w * 0.18), body_center[1] + int(body_h * 0.04)),
            max(int(6 * scale), 3),
            (136, 224, 131),
            -1,
            lineType=cv2.LINE_AA,
        )
        for offset in (-0.2, 0.03, 0.23):
            cv2.ellipse(
                frame,
                (body_center[0] + int(math.sin(offset * 9.0) * 12 * scale), int(body_center[1] + body_h * offset)),
                (int(body_w * 0.2), int(body_h * 0.035)),
                head_tilt,
                0,
                360,
                (73, 164, 76),
                2,
                cv2.LINE_AA,
            )

    arm_y = int(body_center[1] - body_h * 0.02)
    arm_len = int(66 * scale)
    wave = pose["arm_wave"]
    left_hand = (
        body_center[0] - int(body_w * 0.42) - int(arm_len * 0.72),
        arm_y + int(arm_len * (0.2 + 0.3 * wave)),
    )
    right_hand = (
        body_center[0] + int(body_w * 0.42) + int(arm_len * 0.72),
        arm_y + int(arm_len * (0.2 - 0.3 * wave)),
    )
    cv2.line(
        frame,
        (body_center[0] - int(body_w * 0.42), arm_y),
        left_hand,
        (45, 126, 56),
        max(int(7 * scale), 2),
        cv2.LINE_AA,
    )
    cv2.line(
        frame,
        (body_center[0] + int(body_w * 0.42), arm_y),
        right_hand,
        (45, 126, 56),
        max(int(7 * scale), 2),
        cv2.LINE_AA,
    )
    for hand, color in ((left_hand, (255, 196, 88)), (right_hand, (255, 118, 114))):
        cv2.circle(frame, hand, max(int(13 * scale), 5), color, -1, cv2.LINE_AA)
        cv2.circle(frame, hand, max(int(13 * scale), 5), (74, 102, 94), 2, cv2.LINE_AA)

    foot_y = int(body_center[1] + body_h * 0.45)
    leg_len = int(56 * scale)
    stride = pose["stride"]
    left_foot = (body_center[0] - int(body_w * 0.2) - int(16 * stride * scale), foot_y)
    right_foot = (body_center[0] + int(body_w * 0.2) + int(16 * stride * scale), foot_y)
    cv2.line(
        frame,
        (body_center[0] - int(body_w * 0.14), foot_y - int(leg_len * 0.72)),
        left_foot,
        (44, 110, 48),
        max(int(8 * scale), 2),
        cv2.LINE_AA,
    )
    cv2.line(
        frame,
        (body_center[0] + int(body_w * 0.14), foot_y - int(leg_len * 0.72)),
        right_foot,
        (44, 110, 48),
        max(int(8 * scale), 2),
        cv2.LINE_AA,
    )
    for foot, color in ((left_foot, (78, 129, 238)), (right_foot, (110, 88, 229))):
        cv2.ellipse(frame, foot, (int(24 * scale), int(10 * scale)), 0, 0, 360, color, -1, cv2.LINE_AA)
        cv2.ellipse(frame, foot, (int(24 * scale), int(10 * scale)), 0, 0, 360, (53, 61, 111), 2, cv2.LINE_AA)


def _draw_peanut_mom(
    frame: Any,
    cx: float,
    cy: float,
    scale: float,
    pose: dict[str, float],
    *,
    three_d: bool = False,
) -> None:
    body_w = int(148 * scale)
    body_h = int(204 * scale)
    body_center = (int(cx), int(cy - pose["bounce"] * 44 * scale))
    if three_d:
        _draw_contact_shadow(frame, cx, cy, scale * 1.04, strength=0.3)
    top_center = (body_center[0], int(body_center[1] - body_h * 0.18))
    bottom_center = (body_center[0], int(body_center[1] + body_h * 0.18))
    peanut_fill = (82, 188, 245)
    peanut_edge = (43, 124, 190)
    peanut_shadow = (35, 102, 168)
    peanut_mark = (66, 148, 220)
    cv2.ellipse(frame, top_center, (body_w // 2, int(body_h * 0.34)), -7, 0, 360, peanut_fill, -1, cv2.LINE_AA)
    cv2.ellipse(frame, bottom_center, (body_w // 2, int(body_h * 0.36)), 7, 0, 360, peanut_fill, -1, cv2.LINE_AA)
    cv2.ellipse(frame, body_center, (int(body_w * 0.39), int(body_h * 0.19)), 0, 0, 360, peanut_fill, -1, cv2.LINE_AA)
    cv2.ellipse(frame, top_center, (body_w // 2, int(body_h * 0.34)), -7, 0, 360, peanut_edge, 4, cv2.LINE_AA)
    cv2.ellipse(frame, bottom_center, (body_w // 2, int(body_h * 0.36)), 7, 0, 360, peanut_edge, 4, cv2.LINE_AA)
    if three_d:
        _shade_character_volume(
            frame,
            center=body_center,
            body_w=body_w,
            body_h=body_h,
            highlight_color=(150, 218, 255),
            shadow_color=peanut_shadow,
            strength=0.25,
        )
    for offset in (-0.18, 0.02, 0.21):
        cv2.ellipse(
            frame,
            (body_center[0] + int(math.sin(offset * 7.0) * 8 * scale), int(body_center[1] + body_h * offset)),
            (int(body_w * 0.19), int(body_h * 0.035)),
            0,
            0,
            360,
            peanut_mark,
            2,
            cv2.LINE_AA,
        )
    for offset in (-0.28, -0.1, 0.08, 0.26):
        x_mid = body_center[0] + int(body_w * offset)
        cv2.ellipse(
            frame,
            (x_mid, body_center[1]),
            (int(body_w * 0.18), int(body_h * 0.44)),
            5,
            74,
            286,
            peanut_mark,
            2,
            cv2.LINE_AA,
        )
    rng_marks = [
        (-0.26, -0.28),
        (-0.08, -0.34),
        (0.16, -0.2),
        (0.25, 0.0),
        (-0.22, 0.18),
        (0.04, 0.28),
        (0.24, 0.31),
    ]
    for ox, oy in rng_marks:
        cv2.circle(
            frame,
            (body_center[0] + int(body_w * ox), body_center[1] + int(body_h * oy)),
            max(int(2.4 * scale), 1),
            (36, 101, 158),
            -1,
            cv2.LINE_AA,
        )
    if three_d:
        cv2.ellipse(
            frame,
            (body_center[0] - int(body_w * 0.16), body_center[1] - int(body_h * 0.1)),
            (int(body_w * 0.12), int(body_h * 0.045)),
            -18,
            0,
            360,
            (155, 224, 255),
            -1,
            cv2.LINE_AA,
        )

    eye_y = int(body_center[1] - body_h * 0.18)
    eye_offset = int(body_w * 0.18)
    eye_r = max(int(13 * scale * pose["eye_scale"]), 5)
    for delta in (-eye_offset, eye_offset):
        cv2.circle(frame, (body_center[0] + delta, eye_y), eye_r + 2, (255, 255, 255), -1, cv2.LINE_AA)
        cv2.circle(frame, (body_center[0] + delta + int(pose["stride"] * 1.2), eye_y), eye_r, (53, 58, 78), -1, cv2.LINE_AA)
        cv2.circle(
            frame,
            (body_center[0] + delta - int(eye_r * 0.35), eye_y - int(eye_r * 0.35)),
            max(int(eye_r * 0.32), 2),
            (255, 255, 255),
            -1,
            cv2.LINE_AA,
        )
        brow_y = eye_y - int(eye_r * 2.2)
        brow_slope = int(8 * scale * pose.get("brow", 0.0))
        cv2.line(
            frame,
            (body_center[0] + delta - int(13 * scale), brow_y + brow_slope),
            (body_center[0] + delta + int(13 * scale), brow_y - brow_slope),
            (76, 104, 145),
            max(int(4 * scale), 2),
            cv2.LINE_AA,
        )
    mouth_w = max(int(46 * scale), 12)
    mouth_h = max(int((12 + 22 * pose["mouth_open"]) * scale), 6)
    mouth_y = int(body_center[1] + body_h * 0.04)
    cv2.ellipse(frame, (body_center[0], mouth_y), (mouth_w // 2, mouth_h // 2), 0, 0, 360, (45, 28, 44), -1, cv2.LINE_AA)
    cv2.ellipse(
        frame,
        (body_center[0], mouth_y + int(mouth_h * 0.18)),
        (max(mouth_w // 4, 4), max(mouth_h // 5, 3)),
        0,
        0,
        360,
        (116, 82, 242),
        -1,
        cv2.LINE_AA,
    )
    cv2.ellipse(frame, (body_center[0], mouth_y), (mouth_w // 2, mouth_h // 2), 0, 0, 360, (60, 72, 98), 3, cv2.LINE_AA)
    cv2.ellipse(
        frame,
        (body_center[0] - int(mouth_w * 0.12), mouth_y - int(mouth_h * 0.28)),
        (max(mouth_w // 5, 4), max(mouth_h // 8, 2)),
        0,
        0,
        180,
        (255, 255, 255),
        -1,
        cv2.LINE_AA,
    )
    if pose.get("cheek", 0.4) > 0.1:
        cv2.ellipse(
            frame,
            (body_center[0] - int(body_w * 0.28), mouth_y - int(7 * scale)),
            (int(10 * scale), int(5 * scale)),
            0,
            0,
            360,
            (112, 171, 242),
            -1,
            cv2.LINE_AA,
        )
        cv2.ellipse(
            frame,
            (body_center[0] + int(body_w * 0.28), mouth_y - int(7 * scale)),
            (int(10 * scale), int(5 * scale)),
            0,
            0,
            360,
            (112, 171, 242),
            -1,
            cv2.LINE_AA,
        )

    arm_y = int(body_center[1] - body_h * 0.01)
    arm_len = int(72 * scale)
    wave = pose["arm_wave"]
    left_hand = (
        body_center[0] - int(body_w * 0.45) - int(arm_len * 0.62),
        arm_y + int(arm_len * (0.22 + 0.26 * wave)),
    )
    right_hand = (
        body_center[0] + int(body_w * 0.45) + int(arm_len * 0.62),
        arm_y + int(arm_len * (0.24 - 0.24 * wave)),
    )
    cv2.line(
        frame,
        (body_center[0] - int(body_w * 0.45), arm_y),
        left_hand,
        (64, 127, 184),
        max(int(8 * scale), 2),
        cv2.LINE_AA,
    )
    cv2.line(
        frame,
        (body_center[0] + int(body_w * 0.45), arm_y),
        right_hand,
        (64, 127, 184),
        max(int(8 * scale), 2),
        cv2.LINE_AA,
    )
    for hand, color in ((left_hand, (255, 116, 120)), (right_hand, (255, 205, 87))):
        cv2.circle(frame, hand, max(int(13 * scale), 5), color, -1, cv2.LINE_AA)
        cv2.circle(frame, hand, max(int(13 * scale), 5), (82, 91, 111), 2, cv2.LINE_AA)

    foot_y = int(body_center[1] + body_h * 0.48)
    leg_len = int(54 * scale)
    stride = pose["stride"]
    left_foot = (body_center[0] - int(body_w * 0.2) - int(12 * stride * scale), foot_y)
    right_foot = (body_center[0] + int(body_w * 0.2) + int(12 * stride * scale), foot_y)
    for hip, foot in (
        ((body_center[0] - int(body_w * 0.12), foot_y - int(leg_len * 0.76)), left_foot),
        ((body_center[0] + int(body_w * 0.12), foot_y - int(leg_len * 0.76)), right_foot),
    ):
        cv2.line(frame, hip, foot, (53, 112, 176), max(int(8 * scale), 2), cv2.LINE_AA)
    for foot, color in ((left_foot, (88, 117, 240)), (right_foot, (95, 205, 135))):
        cv2.ellipse(frame, foot, (int(25 * scale), int(10 * scale)), 0, 0, 360, color, -1, cv2.LINE_AA)
        cv2.ellipse(frame, foot, (int(25 * scale), int(10 * scale)), 0, 0, 360, (57, 65, 104), 2, cv2.LINE_AA)


def _character_positions(
    *,
    shot: StoryShot,
    scene_w: int,
    scene_h: int,
    local_ratio: float,
    single_protagonist: bool = False,
) -> tuple[tuple[float, float], tuple[float, float]]:
    ground_y = scene_h * 0.8
    if single_protagonist:
        maodou_x = scene_w * 0.5 + math.sin(local_ratio * math.pi * 1.2) * scene_w * 0.02
        mom_x = scene_w * 1.3
        return (maodou_x, ground_y), (mom_x, ground_y)

    maodou_x = scene_w * 0.34
    mom_x = scene_w * 0.66
    action = shot.action_hint.lower()
    if "run" in action or "chase" in action:
        swing = math.sin(local_ratio * math.pi * 2.0)
        maodou_x += swing * scene_w * 0.15
        mom_x -= swing * scene_w * 0.11
    elif "jump" in action:
        maodou_x += math.sin(local_ratio * math.pi) * scene_w * 0.08
    elif "hug" in action:
        maodou_x = _lerp(maodou_x, scene_w * 0.48, _ease_in_out(local_ratio))
        mom_x = _lerp(mom_x, scene_w * 0.52, _ease_in_out(local_ratio))
    return (maodou_x, ground_y), (mom_x, ground_y)


def _camera_target(
    *,
    shot: StoryShot,
    scene_w: int,
    scene_h: int,
    maodou_pos: tuple[float, float],
    mom_pos: tuple[float, float],
    t: float,
    three_d: bool = False,
    single_protagonist: bool = False,
    single_scene_locked: bool = False,
) -> tuple[float, float, float]:
    if single_scene_locked:
        cx = maodou_pos[0] + math.sin(t * 0.45) * scene_w * 0.005
        cy = scene_h * 0.59
        zoom = 1.22 if single_protagonist else 1.15
        if three_d:
            zoom *= 1.02
        return cx, cy, zoom

    cx = scene_w * 0.5
    cy = scene_h * 0.53
    zoom = 1.0
    shot_type = shot.shot_type.lower()
    speaker = shot.speaker.lower()
    if "wide" in shot_type:
        zoom = 1.0
    elif "medium" in shot_type:
        zoom = 1.32
        cx = (maodou_pos[0] + mom_pos[0]) * 0.5
        cy = scene_h * 0.56
    elif "tracking" in shot_type:
        zoom = 1.5
        cx = maodou_pos[0] + math.sin(t * 2.2) * scene_w * 0.04
        cy = scene_h * 0.57
    elif "face" in shot_type:
        zoom = 2.5
        if "peanut" in shot_type or "mom" in shot_type:
            target = mom_pos
        elif "maodou" in shot_type:
            target = maodou_pos
        else:
            target = maodou_pos if speaker == "maodou" else mom_pos
        cx, cy = target[0], target[1] - scene_h * 0.16
    elif "maodou" in shot_type:
        zoom = 2.0
        cx, cy = maodou_pos[0], maodou_pos[1] - scene_h * 0.14
    elif "mom" in shot_type or "peanut" in shot_type:
        zoom = 2.0
        cx, cy = mom_pos[0], mom_pos[1] - scene_h * 0.14
    else:
        zoom = 1.45
        cx = maodou_pos[0] if speaker == "maodou" else mom_pos[0]
        cy = scene_h * 0.57
    if three_d:
        zoom *= 1.06
        cx += math.sin(t * 0.9) * scene_w * 0.008
        cy -= scene_h * 0.016
    return cx, cy, zoom


def _apply_3d_cinematic_grade(frame: Any, t: float) -> Any:
    overlay = frame.copy()
    h, w = frame.shape[:2]
    glow_x = int(w * 0.24 + math.sin(t * 0.7) * 18.0)
    glow_y = int(h * 0.16)
    cv2.circle(overlay, (glow_x, glow_y), int(min(w, h) * 0.2), (255, 240, 214), -1, lineType=cv2.LINE_AA)
    graded = cv2.addWeighted(overlay, 0.11, frame, 0.89, 0.0)
    return cv2.convertScaleAbs(graded, alpha=1.02, beta=2)


def _temporal_optical_flow_align(prev_frame: Any, current_frame: Any) -> Any:
    if prev_frame is None or current_frame is None:
        return current_frame
    prev_gray = cv2.cvtColor(prev_frame, cv2.COLOR_BGR2GRAY)
    current_gray = cv2.cvtColor(current_frame, cv2.COLOR_BGR2GRAY)
    scale = 0.25
    prev_small = cv2.resize(prev_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    current_small = cv2.resize(current_gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
    flow = cv2.calcOpticalFlowFarneback(
        prev_small,
        current_small,
        None,
        0.35,
        3,
        11,
        3,
        5,
        1.1,
        0,
    )
    h, w = current_gray.shape[:2]
    flow = cv2.resize(flow, (w, h), interpolation=cv2.INTER_LINEAR) * (1.0 / scale)
    grid_x, grid_y = np.meshgrid(np.arange(w), np.arange(h))
    map_x = (grid_x + flow[:, :, 0]).astype(np.float32)
    map_y = (grid_y + flow[:, :, 1]).astype(np.float32)
    warped_prev = cv2.remap(prev_frame, map_x, map_y, cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)
    diff = cv2.absdiff(current_frame, warped_prev)
    diff_gray = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
    stable_mask = (diff_gray < 26).astype(np.float32)[:, :, None]
    mixed = cv2.addWeighted(current_frame, 0.72, warped_prev, 0.28, 0.0)
    aligned = mixed * stable_mask + current_frame * (1.0 - stable_mask)
    return np.clip(aligned, 0, 255).astype(np.uint8)


def _crop_camera(frame: Any, cx: float, cy: float, zoom: float, out_w: int, out_h: int) -> Any:
    zoom = _clamp_float(zoom, 1.0, 2.7)
    crop_w = int(max(out_w / zoom, 64))
    crop_h = int(max(out_h / zoom, 64))
    x1 = int(max(0, min(frame.shape[1] - crop_w, cx - crop_w / 2.0)))
    y1 = int(max(0, min(frame.shape[0] - crop_h, cy - crop_h / 2.0)))
    crop = frame[y1 : y1 + crop_h, x1 : x1 + crop_w]
    if crop.size == 0:
        return cv2.resize(frame, (out_w, out_h), interpolation=cv2.INTER_LINEAR)
    return cv2.resize(crop, (out_w, out_h), interpolation=cv2.INTER_LINEAR)


def _write_cheerful_bgm_wav(output_file: Path, duration: float) -> None:
    duration = max(duration, 1.0)
    sample_rate = 44100
    total_samples = int(duration * sample_rate)
    notes = [261.63, 329.63, 392.0, 440.0, 392.0, 329.63, 293.66, 349.23]
    beat_s = 0.4

    with wave.open(str(output_file), "wb") as wav_file:
        wav_file.setnchannels(2)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        chunk = bytearray()
        for index in range(total_samples):
            t = index / float(sample_rate)
            note_index = int(t / beat_s) % len(notes)
            local = (t % beat_s) / beat_s
            freq = notes[note_index]
            env = math.exp(-local * 2.4)
            lead = math.sin(2.0 * math.pi * freq * t) * env
            chord = math.sin(2.0 * math.pi * (freq * 0.5) * t) * 0.7
            sparkle = math.sin(2.0 * math.pi * (freq * 2.0) * t + 0.6) * 0.24 * (1.0 - local)
            kick = math.sin(2.0 * math.pi * 72.0 * t) * max(0.0, 1.0 - ((t % 0.8) / 0.18))
            value = (lead * 0.36 + chord * 0.22 + sparkle * 0.1 + kick * 0.14) * 0.72
            pcm = int(max(-1.0, min(1.0, value)) * 32767 * 0.55)
            chunk.extend(struct.pack("<hh", pcm, pcm))
            if len(chunk) >= 32768:
                wav_file.writeframes(chunk)
                chunk.clear()
        if chunk:
            wav_file.writeframes(chunk)


def _mix_voice_and_bgm(voice_file: Path, bgm_file: Path, output_file: Path) -> None:
    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg not found.")
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(voice_file),
        "-i",
        str(bgm_file),
        "-filter_complex",
        "[1:a]volume=0.2[a1];[0:a][a1]amix=inputs=2:duration=first:dropout_transition=2,alimiter=limit=0.95[aout]",
        "-map",
        "[aout]",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
        str(output_file),
    ]
    run_command(cmd)


def render_native_cartoon_video(
    *,
    audio_file: Path,
    subtitle_file: Path,
    output_file: Path,
    script_text: str,
    storyboard: Any,
    prompt_template: Any,  # noqa: ARG001 - kept for metadata/debug consistency.
    size: str,
    fps: int,
    duration: float,
    subtitle_font: str,
    subtitle_size: int,
    subtitle_margin_v: int,
    force_bgm: bool,
    background_image: str,
    animation_style: str = "",
    single_protagonist: bool = False,
    single_scene_locked: bool = False,
    optical_flow_temporal_align: bool = False,
    forbid_extra_characters: bool = False,
    layered_clean_rendering: bool = False,
) -> None:
    _require_native_animation_stack()
    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg not found. Install ffmpeg or place it under tools/ffmpeg/<build>/bin.")

    width, height = parse_size(size)
    duration = max(duration, 1.0)
    is_3d = _is_3d_style(animation_style)
    toddler_mode = _is_toddler_single_style(animation_style)
    explicit_single_style = "single" in str(animation_style or "").strip().lower() and "duo" not in str(
        animation_style or ""
    ).strip().lower()
    single_character_mode = bool(single_protagonist or toddler_mode or explicit_single_style)
    frame_count = max(int(math.ceil(duration * max(fps, 1))), 1)
    scene_w = int(width * (1.2 if toddler_mode else 1.35))
    scene_h = int(height * (1.18 if toddler_mode else 1.25))
    shots = _build_story_shots(script_text=script_text, duration=duration, storyboard_payload=storyboard)
    base_scene = _draw_base_scene(scene_w, scene_h, three_d=is_3d, toddler_mode=toddler_mode)

    with tempfile.TemporaryDirectory(prefix="native3d_" if is_3d else "native2d_") as temp_dir_str:
        temp_dir = Path(temp_dir_str)
        frame_dir = temp_dir / "frames"
        frame_dir.mkdir(parents=True, exist_ok=True)
        narration_mix_file = temp_dir / "voice_mix.m4a"
        bgm_file = temp_dir / "bgm.wav"

        current_cam = (scene_w * 0.5, scene_h * 0.56, 1.06 if toddler_mode else 1.0)
        prev_output_frame = None
        for index in range(frame_count):
            t = min(duration, index / float(max(fps, 1)))
            shot_index, shot = _find_shot_at_time(shots, t)
            shot_span = max(shot.end_s - shot.start_s, 0.001)
            local_ratio = _clamp_float((t - shot.start_s) / shot_span, 0.0, 1.0)

            frame = base_scene.copy()
            _draw_environment(
                frame,
                t,
                scene_w,
                scene_h,
                three_d=is_3d,
                toddler_mode=toddler_mode,
                scene_key=shot.scene_key,
            )

            maodou_pos, mom_pos = _character_positions(
                shot=shot,
                scene_w=scene_w,
                scene_h=scene_h,
                local_ratio=local_ratio,
                single_protagonist=single_character_mode,
            )
            speaking_maodou = True if single_character_mode else shot.speaker.lower() == "maodou"
            pose_maodou = _pose_from_action(
                shot.action_hint,
                t,
                speaking=speaking_maodou,
                gentle_motion=toddler_mode,
            )
            if layered_clean_rendering:
                char_layer = np.zeros_like(frame)
                _draw_maodou(char_layer, maodou_pos[0], maodou_pos[1], scale=1.0, pose=pose_maodou, three_d=is_3d)
                if not single_character_mode:
                    pose_mom = _pose_from_action(
                        shot.action_hint,
                        t + 0.35,
                        speaking=not speaking_maodou,
                        gentle_motion=toddler_mode,
                    )
                    _draw_peanut_mom(char_layer, mom_pos[0], mom_pos[1], scale=1.02, pose=pose_mom, three_d=is_3d)
                mask = np.any(char_layer > 0, axis=2)
                frame[mask] = char_layer[mask]
            else:
                _draw_maodou(frame, maodou_pos[0], maodou_pos[1], scale=1.0, pose=pose_maodou, three_d=is_3d)
                if not single_character_mode:
                    pose_mom = _pose_from_action(
                        shot.action_hint,
                        t + 0.35,
                        speaking=not speaking_maodou,
                        gentle_motion=toddler_mode,
                    )
                    _draw_peanut_mom(frame, mom_pos[0], mom_pos[1], scale=1.02, pose=pose_mom, three_d=is_3d)

            target_cam = _camera_target(
                shot=shot,
                scene_w=scene_w,
                scene_h=scene_h,
                maodou_pos=maodou_pos,
                mom_pos=mom_pos,
                t=t,
                three_d=is_3d,
                single_protagonist=single_character_mode,
                single_scene_locked=single_scene_locked or toddler_mode,
            )
            cam_smooth = 0.2 if toddler_mode else (0.16 if is_3d else 0.14)
            current_cam = (
                _lerp(current_cam[0], target_cam[0], cam_smooth),
                _lerp(current_cam[1], target_cam[1], cam_smooth),
                _lerp(current_cam[2], target_cam[2], cam_smooth),
            )
            output_frame = _crop_camera(frame, current_cam[0], current_cam[1], current_cam[2], width, height)
            if is_3d:
                output_frame = _apply_3d_cinematic_grade(output_frame, t)
            if optical_flow_temporal_align:
                if index % 2 == 0:
                    output_frame = _temporal_optical_flow_align(prev_output_frame, output_frame)
                prev_output_frame = output_frame.copy()

            if (not toddler_mode) and shot_index > 0 and (t - shot.start_s) < 0.18:
                blend = _clamp_float((0.18 - (t - shot.start_s)) / 0.18, 0.0, 0.45)
                flash = np.full_like(output_frame, 255)
                output_frame = cv2.addWeighted(output_frame, 1.0 - blend, flash, blend, 0.0)

            if (not toddler_mode) and ("!" in shot.line or "！" in shot.line):
                shake = int(2.0 * math.sin(t * 42.0))
                matrix = np.float32([[1, 0, shake], [0, 1, 0]])
                output_frame = cv2.warpAffine(
                    output_frame,
                    matrix,
                    (width, height),
                    flags=cv2.INTER_LINEAR,
                    borderMode=cv2.BORDER_REFLECT_101,
                )

            frame_file = frame_dir / f"frame_{index:06d}.png"
            if not cv2.imwrite(str(frame_file), output_frame, [cv2.IMWRITE_PNG_COMPRESSION, 1]):
                raise RuntimeError(f"Unable to write native animation frame: {frame_file}")

        if force_bgm:
            _write_cheerful_bgm_wav(bgm_file, duration)
            _mix_voice_and_bgm(audio_file, bgm_file, narration_mix_file)
            final_audio = narration_mix_file
        else:
            final_audio = audio_file

        subtitle_style = (
            f"FontName={subtitle_font},"
            f"FontSize={subtitle_size},"
            "PrimaryColour=&H00FFFFFF,"
            "OutlineColour=&H00000000,"
            "BorderStyle=1,"
            "Outline=2,"
            "Shadow=0,"
            "Alignment=2,"
            f"MarginV={subtitle_margin_v}"
        )
        subtitle_filter = (
            f"subtitles='{escape_path_for_subtitles(subtitle_file)}':"
            f"force_style='{subtitle_style}'"
        )

        cmd = [
            ffmpeg_exe,
            "-y",
            "-framerate",
            str(fps),
            "-i",
            str(frame_dir / "frame_%06d.png"),
            "-i",
            str(final_audio),
            "-vf",
            subtitle_filter,
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            "slow",
            "-crf",
            "15",
            "-profile:v",
            "high",
            "-level",
            "4.2",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            "-movflags",
            "+faststart",
            str(output_file),
        ]
        run_command(cmd)


def main() -> int:
    args = parse_args()
    load_env_file(Path(args.env_file).expanduser())
    fill_default_args(args)

    if not args.script_file and not args.topic.strip():
        raise ValueError("Provide --topic or --script-file.")

    style_reference = load_style_reference(args.style_file)
    topic = args.topic.strip()
    artifacts = ensure_output_paths(args.output_dir, topic or "script")

    if args.script_file:
        script_path = Path(args.script_file).expanduser()
        if not script_path.exists():
            raise FileNotFoundError(f"Script file not found: {script_path}")
        script_text = normalize_script(read_text_file(script_path))
        if not topic:
            topic = script_path.stem
    else:
        if not args.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for topic-based script generation.")
        script_text = generate_script(
            topic=topic,
            seconds=args.seconds,
            style_reference=style_reference,
            api_key=args.openai_api_key,
            model=args.openai_text_model,
        )

    if not script_text:
        raise RuntimeError("Script is empty.")
    artifacts.script_file.write_text(script_text, encoding="utf-8")

    if args.provider == "openai":
        if not args.openai_api_key:
            raise ValueError("OPENAI_API_KEY is required for OpenAI TTS.")
        synthesize_openai_tts(
            text=script_text,
            output_file=artifacts.audio_file,
            api_key=args.openai_api_key,
            model=args.openai_tts_model,
            voice=args.openai_voice,
        )
    elif args.provider == "elevenlabs":
        if not args.voice_authorized:
            raise ValueError("Pass --voice-authorized when using cloned voice.")
        if not args.elevenlabs_api_key:
            raise ValueError("ELEVENLABS_API_KEY is required for ElevenLabs TTS.")
        if not args.elevenlabs_voice_id:
            raise ValueError("Set ELEVENLABS_VOICE_ID or --elevenlabs-voice-id.")
        synthesize_elevenlabs_tts(
            text=script_text,
            output_file=artifacts.audio_file,
            api_key=args.elevenlabs_api_key,
            voice_id=args.elevenlabs_voice_id,
            model_id=args.elevenlabs_model,
        )
    else:
        if args.provider == "edge":
            synthesize_edge_tts(
                text=script_text,
                output_file=artifacts.audio_file,
                voice=args.edge_voice,
                rate=args.edge_rate,
                volume=args.edge_volume,
            )
        else:
            synthesize_pyttsx3_tts(
                text=script_text,
                output_file=artifacts.audio_file,
                voice_hint=args.pyttsx3_voice_hint,
                rate=args.pyttsx3_rate,
            )

    duration = probe_audio_duration(artifacts.audio_file) or estimate_duration_from_text(script_text)
    units = split_caption_units(script_text, args.line_chars)
    write_srt(
        units=units,
        total_duration=duration,
        max_line_chars=args.line_chars,
        output_file=artifacts.subtitle_file,
    )

    if not args.audio_only:
        render_video(
            audio_file=artifacts.audio_file,
            subtitle_file=artifacts.subtitle_file,
            output_file=artifacts.video_file,
            size=args.size,
            fps=args.fps,
            background_image=args.background_image,
            bg_color=args.bg_color,
            subtitle_font=args.subtitle_font,
            subtitle_size=args.subtitle_size,
            subtitle_margin_v=args.subtitle_margin_v,
            duration=duration,
        )

    metadata = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "topic": topic,
        "provider": args.provider,
        "duration_seconds": round(duration, 3),
        "script_chars": len(re.sub(r"\s+", "", script_text)),
        "openai_text_model": args.openai_text_model,
        "openai_tts_model": args.openai_tts_model,
        "openai_voice": args.openai_voice,
        "elevenlabs_model": args.elevenlabs_model,
        "elevenlabs_voice_id": args.elevenlabs_voice_id if args.provider == "elevenlabs" else "",
        "edge_voice": args.edge_voice if args.provider == "edge" else "",
        "edge_rate": args.edge_rate if args.provider == "edge" else "",
        "edge_volume": args.edge_volume if args.provider == "edge" else "",
        "pyttsx3_voice_hint": args.pyttsx3_voice_hint if args.provider == "pyttsx3" else "",
        "pyttsx3_rate": args.pyttsx3_rate if args.provider == "pyttsx3" else 0,
    }
    artifacts.metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"Script:   {artifacts.script_file}")
    print(f"Audio:    {artifacts.audio_file}")
    print(f"Subtitle: {artifacts.subtitle_file}")
    if args.audio_only:
        print("Video:    skipped (--audio-only)")
    else:
        print(f"Video:    {artifacts.video_file}")
    print(f"Meta:     {artifacts.metadata_file}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:  # noqa: BLE001
        print(f"ERROR: {exc}", file=sys.stderr)
        raise SystemExit(1)
