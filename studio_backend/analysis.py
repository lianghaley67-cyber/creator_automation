from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from ai_voice_video_generator import resolve_binary  # noqa: E402

from .storage import PORTRAITS_DIR, STUDIO_DIR, VOICE_REFERENCES_DIR, to_media_url


CTA_PATTERN = re.compile(r"关注|评论|收藏|私信|转发|点赞|点个赞|留言|评论区")
_WHISPER_MODELS: dict[str, Any] = {}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".mpeg", ".mpg", ".wmv"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}


def clean_script(raw: str) -> str:
    text = raw.replace("\r", "")
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"`{3}[\s\S]*?`{3}", "", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?;\u3002\uff01\uff1f\uff1b])\s*", normalized)
    return [item.strip() for item in parts if item.strip()]


def extract_terms(text: str) -> list[str]:
    words = re.findall(r"[\u4e00-\u9fffA-Za-z0-9]{2,10}", text)
    stop_tokens = {"this", "that", "with", "from", "your", "have", "will", "just", "then"}
    result: list[str] = []
    for word in words:
        if word.lower() in stop_tokens:
            continue
        result.append(word)
    return result


def _parse_rational(value: str) -> float:
    if not value or value == "0/0":
        return 0.0
    if "/" not in value:
        try:
            return float(value)
        except ValueError:
            return 0.0
    numerator, denominator = value.split("/", 1)
    try:
        return float(numerator) / float(denominator)
    except (ValueError, ZeroDivisionError):
        return 0.0


def detect_media_kind(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    return "video"


def probe_video_file(video_path: Path) -> dict[str, Any]:
    info = {
        "duration_seconds": 0.0,
        "width": 0,
        "height": 0,
        "fps": 0.0,
        "size_bytes": video_path.stat().st_size,
    }
    ffprobe_exe = resolve_binary("ffprobe")
    if ffprobe_exe:
        cmd = [
            ffprobe_exe,
            "-v",
            "error",
            "-print_format",
            "json",
            "-show_streams",
            "-show_format",
            str(video_path),
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if result.returncode == 0 and result.stdout.strip():
            payload = json.loads(result.stdout)
            for stream in payload.get("streams", []):
                if stream.get("codec_type") != "video":
                    continue
                info["width"] = int(stream.get("width") or 0)
                info["height"] = int(stream.get("height") or 0)
                info["fps"] = _parse_rational(str(stream.get("avg_frame_rate") or "0"))
                break
            info["duration_seconds"] = float(payload.get("format", {}).get("duration") or 0.0)
    if info["width"] and info["height"]:
        return info
    try:
        import cv2
    except ImportError:
        return info
    capture = cv2.VideoCapture(str(video_path))
    if capture.isOpened():
        info["width"] = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        info["height"] = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        info["fps"] = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = float(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        if info["fps"] > 0 and frame_count > 0:
            info["duration_seconds"] = round(frame_count / info["fps"], 3)
    capture.release()
    return info


def sample_visual_metrics(video_path: Path) -> dict[str, Any]:
    try:
        import cv2
    except ImportError:
        return {"frame_samples": 0, "brightness_score": 0.0, "motion_score": 0.0, "face_ratio": 0.0}

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return {"frame_samples": 0, "brightness_score": 0.0, "motion_score": 0.0, "face_ratio": 0.0}

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    step = max(int(fps * 2.5), 1)
    frame_index = 0
    prev_gray = None
    brightness_scores: list[float] = []
    motion_scores: list[float] = []
    face_ratios: list[float] = []
    face_center_x: list[float] = []
    face_center_y: list[float] = []
    frame_samples = 0
    face_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )

    while frame_index < total_frames and frame_samples < 18:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            break
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness_scores.append(float(gray.mean()))
        if prev_gray is not None:
            motion_scores.append(float(cv2.absdiff(prev_gray, gray).mean()))
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(80, 80))
        if len(faces) > 0:
            selected = max(faces, key=lambda item: float(item[2] * item[3]))
            x, y, w, h = selected
            largest = float(w * h)
            face_ratios.append(largest / float(frame.shape[0] * frame.shape[1]))
            face_center_x.append((x + w / 2) / float(frame.shape[1]))
            face_center_y.append((y + h / 2) / float(frame.shape[0]))
        prev_gray = gray
        frame_index += step
        frame_samples += 1

    center_drift = 0.0
    if face_center_x and face_center_y:
        mean_x = sum(face_center_x) / len(face_center_x)
        mean_y = sum(face_center_y) / len(face_center_y)
        drift_x = sum(abs(value - mean_x) for value in face_center_x) / len(face_center_x)
        drift_y = sum(abs(value - mean_y) for value in face_center_y) / len(face_center_y)
        center_drift = round((drift_x + drift_y) / 2.0, 3)

    capture.release()
    return {
        "frame_samples": frame_samples,
        "brightness_score": round(sum(brightness_scores) / max(len(brightness_scores), 1), 2),
        "motion_score": round(sum(motion_scores) / max(len(motion_scores), 1), 2),
        "face_ratio": round(sum(face_ratios) / max(len(face_ratios), 1), 3),
        "face_center_x": round(sum(face_center_x) / max(len(face_center_x), 1), 3),
        "face_center_y": round(sum(face_center_y) / max(len(face_center_y), 1), 3),
        "face_center_drift": center_drift,
    }


def _fit_long_edge(frame: Any, *, max_long_edge: int = 1280) -> Any:
    height, width = frame.shape[:2]
    current_long_edge = max(height, width)
    if current_long_edge <= max_long_edge:
        return frame
    scale = max_long_edge / float(current_long_edge)
    target_width = max(int(width * scale), 1)
    target_height = max(int(height * scale), 1)
    import cv2

    return cv2.resize(frame, (target_width, target_height), interpolation=cv2.INTER_AREA)


def extract_portrait_image(video_path: Path, output_image: Path) -> dict[str, Any]:
    try:
        import cv2
    except ImportError:
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "opencv-python-headless not installed.",
        }

    capture = cv2.VideoCapture(str(video_path))
    if not capture.isOpened():
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "Unable to open video.",
        }

    fps = float(capture.get(cv2.CAP_PROP_FPS) or 25.0)
    total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
    frame_step = max(int(fps * 1.2), 1)
    face_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )

    best_frame = None
    best_face = None
    best_score = float("-inf")
    sampled = 0
    frame_index = 0

    while frame_index < max(total_frames, 1) and sampled < 48:
        capture.set(cv2.CAP_PROP_POS_FRAMES, frame_index)
        ok, frame = capture.read()
        if not ok or frame is None:
            break

        if best_frame is None:
            best_frame = frame.copy()

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(96, 96))
        if len(faces) > 0:
            x, y, w, h = max(faces, key=lambda item: float(item[2] * item[3]))
            frame_area = float(frame.shape[0] * frame.shape[1]) or 1.0
            face_ratio = float(w * h) / frame_area
            center_x = (x + w / 2.0) / float(frame.shape[1])
            center_y = (y + h / 2.0) / float(frame.shape[0])
            center_distance = abs(center_x - 0.5) + abs(center_y - 0.42)
            brightness = float(gray.mean()) / 255.0
            score = face_ratio * 5.0 - center_distance + brightness * 0.12
            if score > best_score:
                best_score = score
                best_frame = frame.copy()
                best_face = (int(x), int(y), int(w), int(h))

        frame_index += frame_step
        sampled += 1

    if best_frame is None:
        capture.release()
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "No readable frame found.",
        }

    capture.release()

    portrait_frame = best_frame
    portrait_source = "full_frame"
    if best_face is not None:
        x, y, w, h = best_face
        frame_height, frame_width = best_frame.shape[:2]
        margin_x = int(w * 0.9)
        margin_top = int(h * 1.0)
        margin_bottom = int(h * 1.8)
        left = max(x - margin_x, 0)
        top = max(y - margin_top, 0)
        right = min(x + w + margin_x, frame_width)
        bottom = min(y + h + margin_bottom, frame_height)
        candidate = best_frame[top:bottom, left:right]
        if candidate.size:
            portrait_frame = candidate
            portrait_source = "face_crop"

    portrait_frame = _fit_long_edge(portrait_frame)
    output_image.parent.mkdir(parents=True, exist_ok=True)
    output_image.unlink(missing_ok=True)
    if not cv2.imwrite(str(output_image), portrait_frame):
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "Failed to write portrait image.",
        }

    return {
        "portrait_path": str(output_image),
        "portrait_url": to_media_url(output_image),
        "portrait_source": portrait_source,
        "portrait_note": "",
    }


def extract_voice_reference(
    video_path: Path,
    output_audio: Path,
    *,
    max_seconds: int = 20,
    sample_rate: int = 24000,
) -> dict[str, Any]:
    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        return {
            "voice_reference_path": "",
            "voice_reference_source": "unavailable",
            "voice_reference_note": "ffmpeg unavailable.",
        }

    output_audio.parent.mkdir(parents=True, exist_ok=True)
    output_audio.unlink(missing_ok=True)
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        str(sample_rate),
        "-ac",
        "1",
        "-t",
        str(max_seconds),
        str(output_audio),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0 or not output_audio.exists():
        stderr = "\n".join(result.stderr.splitlines()[-20:])
        return {
            "voice_reference_path": "",
            "voice_reference_source": "unavailable",
            "voice_reference_note": stderr or "Failed to extract voice reference.",
        }

    return {
        "voice_reference_path": str(output_audio),
        "voice_reference_url": to_media_url(output_audio),
        "voice_reference_source": "video_audio",
        "voice_reference_seconds": max_seconds,
        "voice_reference_note": "",
    }


def extract_audio_track(video_path: Path, output_audio: Path) -> tuple[bool, str]:
    ffmpeg_exe = resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        return False, "ffmpeg unavailable, skipped transcription."
    cmd = [
        ffmpeg_exe,
        "-y",
        "-i",
        str(video_path),
        "-vn",
        "-acodec",
        "pcm_s16le",
        "-ar",
        "16000",
        "-ac",
        "1",
        str(output_audio),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        stderr = "\n".join(result.stderr.splitlines()[-20:])
        return False, stderr or "Audio extraction failed."
    return True, "Audio extracted."


def transcribe_audio(audio_path: Path, *, model_name: str = "small") -> tuple[str, str]:
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        return "", "faster-whisper not installed, skipped auto transcription."

    try:
        model = _WHISPER_MODELS.get(model_name)
        if model is None:
            model = WhisperModel(model_name, device="cpu", compute_type="int8")
            _WHISPER_MODELS[model_name] = model
        segments, _ = model.transcribe(str(audio_path), language="zh", vad_filter=True)
        transcript = "".join(segment.text.strip() for segment in segments if segment.text.strip())
        return transcript.strip(), f"Whisper model: {model_name}"
    except Exception as exc:  # noqa: BLE001
        return "", f"Auto transcription failed: {exc}"


def analyze_video_file(
    video_path: Path,
    *,
    transcript_text: str = "",
    notes: str = "",
    whisper_model: str = "small",
) -> dict[str, Any]:
    probe = probe_video_file(video_path)
    visual = sample_visual_metrics(video_path)
    portrait_info = extract_portrait_image(video_path, PORTRAITS_DIR / f"{video_path.stem}.jpg")
    voice_reference_info = extract_voice_reference(video_path, VOICE_REFERENCES_DIR / f"{video_path.stem}.wav")

    transcript = clean_script(transcript_text)
    transcript_source = "manual"
    transcription_note = "Used uploaded transcript."

    if not transcript:
        temp_audio = STUDIO_DIR / f"temp_{video_path.stem}.wav"
        ok, message = extract_audio_track(video_path, temp_audio)
        if ok:
            transcript, transcription_note = transcribe_audio(temp_audio, model_name=whisper_model)
            transcript_source = "auto" if transcript else "none"
            temp_audio.unlink(missing_ok=True)
        else:
            transcript_source = "none"
            transcription_note = message

    transcript = transcript or clean_script(notes)
    sentences = split_sentences(transcript)
    compact = re.sub(r"\s+", "", transcript)
    char_count = len(compact)
    duration_seconds = float(probe.get("duration_seconds") or 0.0)
    speaking_pace = round(char_count / duration_seconds, 2) if duration_seconds > 0 and char_count > 0 else 0.0
    keyword_counts = Counter(extract_terms(transcript))
    keywords = [value for value, _ in keyword_counts.most_common(12)]
    question_ratio = round(
        len(re.findall(r"[?\uFF1F]", transcript)) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0
    exclamation_ratio = round(
        len(re.findall(r"[!\uFF01]", transcript)) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0
    comma_pause_density = round(
        len(re.findall(r"[\uFF0C\u3001,]", transcript)) / max(char_count, 1) * 100,
        2,
    ) if char_count else 0.0
    short_sentence_ratio = round(
        sum(1 for sentence in sentences if len(re.sub(r"\s+", "", sentence)) <= 18) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0

    hook_candidate = sentences[0] if sentences else ""
    cta_candidate = ""
    for sentence in reversed(sentences):
        if CTA_PATTERN.search(sentence):
            cta_candidate = sentence
            break
    if not cta_candidate and sentences:
        cta_candidate = sentences[-1]

    punctuation_count = len(re.findall(r"[!\uFF01?\uFF1F]", transcript))
    emotional_punch = round(punctuation_count / max(len(sentences), 1), 2) if sentences else 0.0
    cta_density = round(1.0 if CTA_PATTERN.search(cta_candidate) else 0.0, 2)
    rhythm_style = "punchy" if short_sentence_ratio >= 0.55 else "balanced" if short_sentence_ratio >= 0.3 else "narrative"
    framing_style = "center_locked" if visual["face_center_drift"] <= 0.05 else "dynamic_follow"

    return {
        "video_probe": {
            "duration_seconds": round(duration_seconds, 3),
            "width": int(probe.get("width") or 0),
            "height": int(probe.get("height") or 0),
            "fps": round(float(probe.get("fps") or 0.0), 2),
            "size_bytes": int(probe.get("size_bytes") or 0),
        },
        "transcript_text": transcript,
        "speech_metrics": {
            "char_count": char_count,
            "sentence_count": len(sentences),
            "avg_sentence_len": round(char_count / max(len(sentences), 1), 2) if sentences else 0.0,
            "speaking_pace_cps": speaking_pace,
            "recommended_chars_60s": int(round(speaking_pace * 60)) if speaking_pace else 220,
            "hook_candidate": hook_candidate,
            "cta_candidate": cta_candidate,
            "keywords": keywords,
            "emotional_punch": emotional_punch,
            "question_ratio": question_ratio,
            "exclamation_ratio": exclamation_ratio,
            "comma_pause_density": comma_pause_density,
            "short_sentence_ratio": short_sentence_ratio,
            "cta_density": cta_density,
            "rhythm_style": rhythm_style,
        },
        "visual_metrics": visual,
        "summary": {
            "transcript_source": transcript_source,
            "transcription_note": transcription_note,
            "delivery_hint": "high_energy" if speaking_pace >= 4.7 or visual["motion_score"] >= 16 else "steady",
            "framing_hint": "close_face" if visual["face_ratio"] >= 0.18 else "balanced_face",
            "framing_style": framing_style,
            "pause_style": "short_bursts" if comma_pause_density <= 5.0 and short_sentence_ratio >= 0.5 else "layered",
            "cta_style": "direct" if cta_density >= 1 else "soft",
        },
        "reference_assets": {
            **portrait_info,
            **voice_reference_info,
        },
    }


def _build_speech_metrics(transcript: str, duration_seconds: float) -> dict[str, Any]:
    sentences = split_sentences(transcript)
    compact = re.sub(r"\s+", "", transcript)
    char_count = len(compact)
    speaking_pace = round(char_count / duration_seconds, 2) if duration_seconds > 0 and char_count > 0 else 0.0
    keyword_counts = Counter(extract_terms(transcript))
    keywords = [value for value, _ in keyword_counts.most_common(12)]
    question_ratio = round(
        len(re.findall(r"[?\uFF1F]", transcript)) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0
    exclamation_ratio = round(
        len(re.findall(r"[!\uFF01]", transcript)) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0
    comma_pause_density = round(
        len(re.findall(r"[\uFF0C\u3002\uFF1B]", transcript)) / max(char_count, 1) * 100,
        2,
    ) if char_count else 0.0
    short_sentence_ratio = round(
        sum(1 for sentence in sentences if len(re.sub(r"\s+", "", sentence)) <= 18) / max(len(sentences), 1),
        2,
    ) if sentences else 0.0
    hook_candidate = sentences[0] if sentences else ""
    cta_candidate = ""
    for sentence in reversed(sentences):
        if CTA_PATTERN.search(sentence):
            cta_candidate = sentence
            break
    if not cta_candidate and sentences:
        cta_candidate = sentences[-1]
    punctuation_count = len(re.findall(r"[!\uFF01?\uFF1F]", transcript))
    emotional_punch = round(punctuation_count / max(len(sentences), 1), 2) if sentences else 0.0
    cta_density = round(1.0 if CTA_PATTERN.search(cta_candidate) else 0.0, 2)
    rhythm_style = "punchy" if short_sentence_ratio >= 0.55 else "balanced" if short_sentence_ratio >= 0.3 else "narrative"
    return {
        "char_count": char_count,
        "sentence_count": len(sentences),
        "avg_sentence_len": round(char_count / max(len(sentences), 1), 2) if sentences else 0.0,
        "speaking_pace_cps": speaking_pace,
        "recommended_chars_60s": int(round(speaking_pace * 60)) if speaking_pace else 220,
        "hook_candidate": hook_candidate,
        "cta_candidate": cta_candidate,
        "keywords": keywords,
        "emotional_punch": emotional_punch,
        "question_ratio": question_ratio,
        "exclamation_ratio": exclamation_ratio,
        "comma_pause_density": comma_pause_density,
        "short_sentence_ratio": short_sentence_ratio,
        "cta_density": cta_density,
        "rhythm_style": rhythm_style,
    }


def sample_image_visual_metrics(image_path: Path) -> tuple[dict[str, Any], int, int]:
    try:
        import cv2
    except ImportError:
        return {
            "frame_samples": 1,
            "brightness_score": 0.0,
            "motion_score": 0.0,
            "face_ratio": 0.0,
            "face_center_x": 0.0,
            "face_center_y": 0.0,
            "face_center_drift": 0.0,
        }, 0, 0

    frame = cv2.imread(str(image_path))
    if frame is None:
        return {
            "frame_samples": 1,
            "brightness_score": 0.0,
            "motion_score": 0.0,
            "face_ratio": 0.0,
            "face_center_x": 0.0,
            "face_center_y": 0.0,
            "face_center_drift": 0.0,
        }, 0, 0

    height, width = frame.shape[:2]
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = float(gray.mean())
    face_ratio = 0.0
    center_x = 0.0
    center_y = 0.0

    face_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(80, 80))
    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda item: float(item[2] * item[3]))
        frame_area = float(max(height * width, 1))
        face_ratio = float(w * h) / frame_area
        center_x = (x + w / 2.0) / float(max(width, 1))
        center_y = (y + h / 2.0) / float(max(height, 1))

    return {
        "frame_samples": 1,
        "brightness_score": round(brightness, 2),
        "motion_score": 0.0,
        "face_ratio": round(face_ratio, 3),
        "face_center_x": round(center_x, 3),
        "face_center_y": round(center_y, 3),
        "face_center_drift": 0.0,
    }, int(width), int(height)


def extract_portrait_from_image(image_path: Path, output_image: Path) -> dict[str, Any]:
    output_image.parent.mkdir(parents=True, exist_ok=True)
    try:
        import cv2
    except ImportError:
        output_image.unlink(missing_ok=True)
        shutil.copy2(image_path, output_image)
        return {
            "portrait_path": str(output_image),
            "portrait_url": to_media_url(output_image),
            "portrait_source": "image_copy",
            "portrait_note": "opencv unavailable, copied original image.",
        }

    frame = cv2.imread(str(image_path))
    if frame is None:
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "Unable to read image file.",
        }

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    face_cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )
    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(96, 96))

    portrait_frame = frame
    portrait_source = "full_frame"
    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda item: float(item[2] * item[3]))
        frame_height, frame_width = frame.shape[:2]
        margin_x = int(w * 0.9)
        margin_top = int(h * 1.0)
        margin_bottom = int(h * 1.8)
        left = max(x - margin_x, 0)
        top = max(y - margin_top, 0)
        right = min(x + w + margin_x, frame_width)
        bottom = min(y + h + margin_bottom, frame_height)
        candidate = frame[top:bottom, left:right]
        if candidate.size:
            portrait_frame = candidate
            portrait_source = "face_crop"

    portrait_frame = _fit_long_edge(portrait_frame)
    output_image.unlink(missing_ok=True)
    if not cv2.imwrite(str(output_image), portrait_frame):
        return {
            "portrait_path": "",
            "portrait_source": "unavailable",
            "portrait_note": "Failed to write portrait image.",
        }
    return {
        "portrait_path": str(output_image),
        "portrait_url": to_media_url(output_image),
        "portrait_source": portrait_source,
        "portrait_note": "",
    }


def analyze_image_file(
    image_path: Path,
    *,
    transcript_text: str = "",
    notes: str = "",
) -> dict[str, Any]:
    visual, width, height = sample_image_visual_metrics(image_path)
    portrait_suffix = image_path.suffix.lower() if image_path.suffix.lower() in IMAGE_EXTENSIONS else ".jpg"
    portrait_info = extract_portrait_from_image(image_path, PORTRAITS_DIR / f"{image_path.stem}{portrait_suffix}")
    voice_reference_info = {
        "voice_reference_path": "",
        "voice_reference_url": "",
        "voice_reference_source": "image_only",
        "voice_reference_note": "Image assets do not contain voice. Upload at least one video for voice cloning.",
    }

    transcript = clean_script(transcript_text) or clean_script(notes)
    speech_metrics = _build_speech_metrics(transcript, duration_seconds=0.0)
    framing_style = "center_locked" if visual["face_center_drift"] <= 0.05 else "dynamic_follow"

    return {
        "video_probe": {
            "duration_seconds": 0.0,
            "width": int(width),
            "height": int(height),
            "fps": 0.0,
            "size_bytes": int(image_path.stat().st_size),
        },
        "transcript_text": transcript,
        "speech_metrics": speech_metrics,
        "visual_metrics": visual,
        "summary": {
            "transcript_source": "manual" if transcript else "none",
            "transcription_note": "Image-only analysis (no speech track)." if transcript else "Image-only analysis.",
            "delivery_hint": "steady",
            "framing_hint": "close_face" if visual["face_ratio"] >= 0.18 else "balanced_face",
            "framing_style": framing_style,
            "pause_style": "short_bursts" if speech_metrics["comma_pause_density"] <= 5.0 and speech_metrics["short_sentence_ratio"] >= 0.5 else "layered",
            "cta_style": "direct" if speech_metrics["cta_density"] >= 1 else "soft",
        },
        "reference_assets": {
            **portrait_info,
            **voice_reference_info,
        },
    }


def analyze_media_file(
    media_path: Path,
    *,
    transcript_text: str = "",
    notes: str = "",
    whisper_model: str = "small",
    media_kind_hint: str = "",
) -> dict[str, Any]:
    media_kind = (media_kind_hint or detect_media_kind(media_path)).strip().lower()
    if media_kind == "image":
        return analyze_image_file(
            media_path,
            transcript_text=transcript_text,
            notes=notes,
        )
    return analyze_video_file(
        media_path,
        transcript_text=transcript_text,
        notes=notes,
        whisper_model=whisper_model,
    )
