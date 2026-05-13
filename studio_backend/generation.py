from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import ai_voice_video_generator as avvg  # noqa: E402

from .analysis import clean_script
from .avatar import run_sadtalker
from .kling_provider import (
    create_kling_official_task,
    create_kling_task,
    wait_for_kling_official_video,
    wait_for_kling_video,
)
from .storage import OUTPUTS_DIR, now_iso, to_media_url
from .voice_clone import convert_with_local_voice_clone
from .zhipu_provider import create_zhipu_video_task, wait_for_zhipu_video
from .kids_mode import normalize_kids_script_text


ProgressCallback = Callable[[int, str, str], None]


def _report_progress(
    progress_callback: ProgressCallback | None,
    percent: int,
    stage: str,
    message: str,
) -> None:
    if not progress_callback:
        return
    progress_callback(percent, stage, message)


def _compact_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return cleaned[:36] or "manual"


def _pick(items: list[str], seed: str, fallback: str) -> str:
    if not items:
        return fallback
    total = sum(ord(char) for char in seed)
    return items[total % len(items)]


def _normalize_keywords(raw: Any) -> list[str]:
    if isinstance(raw, list):
        tokens = [str(item).strip() for item in raw]
    else:
        tokens = re.split(r"[\n,，、|]+", str(raw or ""))
    return [item for item in tokens if item]


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _bool_value(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on"}:
        return True
    if text in {"0", "false", "no", "off", ""}:
        return False
    return default


def _int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _float_value(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _should_apply_distilled_default(request_payload: dict[str, Any], field: str, expected: Any) -> bool:
    if field not in request_payload:
        return True
    current = request_payload.get(field)
    if current is None:
        return True
    if isinstance(expected, bool):
        return _bool_value(current, expected) == expected
    if isinstance(expected, int) and not isinstance(expected, bool):
        return _int_value(current, expected) == expected
    if isinstance(expected, float):
        return abs(_float_value(current, expected) - expected) < 1e-6
    return _string(current) == _string(expected)


def _distilled_sadtalker_defaults(
    request_payload: dict[str, Any],
    persona: dict[str, Any],
    avatar_settings: dict[str, Any],
    reference_assets: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    enriched_request = dict(request_payload)
    enriched_avatar_settings = dict(avatar_settings)
    applied: dict[str, Any] = {}

    if _string(enriched_request.get("render_mode")) != "sadtalker":
        return enriched_request, enriched_avatar_settings, applied

    visual_profile = dict(persona.get("visual_profile") or {})
    emotion_profile = dict(persona.get("emotion_profile") or {})
    # Do not auto-wire the full uploaded video into ref_pose/ref_eyeblink.
    # SadTalker loads reference clips into memory, and typical phone uploads
    # are large enough to trigger OOM or multi-minute stalls on a local PC.
    # Users can still provide an explicit short reference clip when needed.

    camera_distance = _string(visual_profile.get("camera_distance")) or "medium_close"
    camera_movement_style = _string(visual_profile.get("camera_movement_style")) or "stable"
    face_center_bias = _string(visual_profile.get("face_center_bias")) or "centered"
    expression_energy = _string(emotion_profile.get("expression_energy")) or "balanced"
    motion_score = _float_value(visual_profile.get("motion_score"), 0.0)
    face_center_drift = _float_value(visual_profile.get("face_center_drift"), 0.0)
    use_cpu = _bool_value(
        enriched_request.get("avatar_use_cpu"),
        _bool_value(enriched_avatar_settings.get("use_cpu"), False),
    )

    preprocess_default = "crop" if camera_distance in {"close_up", "medium_close"} else "full"
    dynamic_motion = (
        camera_movement_style == "dynamic"
        or face_center_bias == "loose"
        or motion_score >= 12
        or face_center_drift >= 0.08
    )
    still_mode_default = not dynamic_motion
    pose_style_default = 0 if still_mode_default else 14 if motion_score >= 25 else 9
    expression_scale_default = {
        "intense": 1.35,
        "balanced": 1.1,
        "calm": 0.9,
    }.get(expression_energy, 1.0)
    # Prefer clearer portrait output on GPU by default.
    # CPU mode keeps a lower resolution to avoid severe stalls on consumer PCs.
    size_default = 256 if use_cpu else 512

    if _should_apply_distilled_default(enriched_request, "avatar_preprocess", "full"):
        enriched_request["avatar_preprocess"] = preprocess_default
        applied["avatar_preprocess"] = preprocess_default
    if _should_apply_distilled_default(enriched_request, "avatar_still_mode", True):
        enriched_request["avatar_still_mode"] = still_mode_default
        applied["avatar_still_mode"] = still_mode_default
    if _should_apply_distilled_default(enriched_request, "avatar_pose_style", 0):
        enriched_request["avatar_pose_style"] = pose_style_default
        applied["avatar_pose_style"] = pose_style_default
    if _should_apply_distilled_default(enriched_request, "avatar_expression_scale", 1.0):
        enriched_request["avatar_expression_scale"] = expression_scale_default
        applied["avatar_expression_scale"] = expression_scale_default
    if _should_apply_distilled_default(enriched_request, "avatar_size", 512):
        enriched_request["avatar_size"] = size_default
        applied["avatar_size"] = size_default

    applied["distilled_visual_profile"] = {
        "camera_distance": camera_distance,
        "camera_movement_style": camera_movement_style,
        "face_center_bias": face_center_bias,
        "motion_score": motion_score,
        "face_center_drift": face_center_drift,
        "expression_energy": expression_energy,
    }
    return enriched_request, enriched_avatar_settings, applied


def _apply_reference_defaults(
    request_payload: dict[str, Any],
    persona: dict[str, Any],
    avatar_settings: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    enriched_request = dict(request_payload)
    enriched_avatar_settings = dict(avatar_settings)
    reference_assets = dict(persona.get("reference_assets") or {})
    applied_defaults: dict[str, Any] = {}
    requested_style_tag = _string(enriched_request.get("reference_style_tag"))
    style_profiles = list(reference_assets.get("style_profiles") or [])
    selected_style_profile: dict[str, Any] = {}
    if requested_style_tag:
        normalized_style_tag = requested_style_tag.lower()
        for profile in style_profiles:
            if _string(profile.get("style_tag")).lower() == normalized_style_tag:
                selected_style_profile = dict(profile)
                applied_defaults["reference_style_tag"] = requested_style_tag
                break
        if not selected_style_profile:
            applied_defaults["reference_style_tag"] = f"{requested_style_tag} (fallback_latest)"

    portrait_path = _string(enriched_request.get("portrait_path"))
    if not portrait_path:
        portrait_path = _string(selected_style_profile.get("portrait_path")) or _string(reference_assets.get("portrait_path"))
        if portrait_path:
            enriched_request["portrait_path"] = portrait_path
            applied_defaults["portrait_path"] = (
                "style_profile_portrait" if selected_style_profile else "latest_upload_portrait"
            )

    voice_reference_path = _string(enriched_request.get("voice_clone_reference_path"))
    if not voice_reference_path:
        voice_reference_path = _string(selected_style_profile.get("voice_reference_path")) or _string(reference_assets.get("voice_reference_path"))
        if voice_reference_path:
            enriched_request["voice_clone_reference_path"] = voice_reference_path
            applied_defaults["voice_clone_reference_path"] = (
                "style_profile_voice_reference" if selected_style_profile else "latest_upload_voice_reference"
            )

    if not _string(enriched_avatar_settings.get("source_image")) and portrait_path:
        enriched_avatar_settings["source_image"] = portrait_path
        applied_defaults["avatar_source_image"] = (
            "style_profile_portrait" if selected_style_profile else "latest_upload_portrait"
        )

    enriched_request, enriched_avatar_settings, distilled_defaults = _distilled_sadtalker_defaults(
        enriched_request,
        persona,
        enriched_avatar_settings,
        reference_assets,
    )
    applied_defaults.update(distilled_defaults)
    return enriched_request, enriched_avatar_settings, applied_defaults


def _unique_nonempty(items: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        cleaned = _string(item)
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        result.append(cleaned)
    return result


def _has_any_trait(values: list[str], *targets: str) -> bool:
    pool = {_string(item) for item in values if _string(item)}
    return any(target in pool for target in targets)


def _persona_applied_summary(persona: dict[str, Any]) -> dict[str, Any]:
    human = dict(persona.get("human_profile") or {})
    speech = dict(persona.get("speech_profile") or {})
    visual = dict(persona.get("visual_profile") or {})
    emotion = dict(persona.get("emotion_profile") or {})
    generation = dict(persona.get("generation_profile") or {})
    return {
        "name": _string(persona.get("name")),
        "sample_count": _int_value(persona.get("sample_count"), 0),
        "personality_traits": _unique_nonempty(list(human.get("personality_traits") or []))[:4],
        "behavior_traits": _unique_nonempty(list(human.get("behavior_traits") or []))[:4],
        "communication_traits": _unique_nonempty(list(human.get("communication_traits") or []))[:4],
        "emotion_traits": _unique_nonempty(list(human.get("emotion_traits") or []))[:4],
        "expression_traits": _unique_nonempty(list(human.get("expression_traits") or []))[:4],
        "voice_traits": _unique_nonempty(list(human.get("voice_traits") or []))[:4],
        "script_flow": _unique_nonempty(list(generation.get("script_flow") or []))[:4],
        "recommended_chars_60s": _int_value(
            generation.get("recommended_chars_60s"),
            _int_value(speech.get("recommended_chars_60s"), 220),
        ),
        "camera_distance": _string(visual.get("camera_distance")),
        "lighting_style": _string(visual.get("lighting_style")),
        "expression_energy": _string(emotion.get("expression_energy")),
        "pause_style": _string(emotion.get("pause_style")),
        "prompt_block_excerpt": _string(persona.get("prompt_block"))[:220],
    }


_FORM_HELPER_TEXT_MARKERS = (
    "只填主题、标题、关键词或树洞内容时，系统会结合你的蒸馏画像自动写文案",
    "本地声音克隆会默认使用最近一次上传视频里提取的参考音频",
)


def _looks_like_form_helper_text(text: str) -> bool:
    cleaned = clean_script(_string(text))
    if not cleaned:
        return False
    if len(cleaned) > 240:
        return False
    return any(marker in cleaned for marker in _FORM_HELPER_TEXT_MARKERS)


def _sanitize_prompt_field(value: Any) -> str:
    cleaned = clean_script(_string(value))
    if _looks_like_form_helper_text(cleaned):
        return ""
    return cleaned


def _synthesize_base_audio_for_clone(
    script_text: str,
    base_audio_file: Path,
    request_payload: dict[str, Any],
) -> str:
    try:
        avvg.synthesize_edge_tts(
            text=script_text,
            output_file=base_audio_file,
            voice=str(request_payload.get("edge_voice", "zh-CN-XiaoxiaoNeural")),
            rate=str(request_payload.get("edge_rate", "")),
            volume=str(request_payload.get("edge_volume", "")),
        )
        return "edge"
    except Exception:
        avvg.synthesize_pyttsx3_tts(
            text=script_text,
            output_file=base_audio_file,
            voice_hint=os.getenv("PYTTSX3_VOICE_HINT", "zh"),
            rate=int(os.getenv("PYTTSX3_RATE", "0") or "0"),
        )
        return "pyttsx3"


def _ps_single_quoted(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def _synthesize_windows_sapi_child_tts(
    script_text: str,
    audio_file: Path,
    request_payload: dict[str, Any],
) -> str:
    if os.name != "nt":
        raise RuntimeError("Windows SAPI TTS is only available on Windows.")
    try:
        import win32com.client  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("pywin32 is required for Windows SAPI TTS.") from exc
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required for Windows SAPI child voice processing.")
    wav_file = audio_file.with_suffix(".sapi.wav").resolve()
    audio_file = audio_file.resolve()
    wav_file.unlink(missing_ok=True)
    audio_file.unlink(missing_ok=True)
    voice_name = _string(request_payload.get("sapi_voice")) or "Microsoft Huihui Desktop"
    rate = max(-10, min(10, _int_value(request_payload.get("sapi_rate"), 0)))
    volume = max(0, min(100, _int_value(request_payload.get("sapi_volume"), 96)))
    try:
        voice = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        for token in voice.GetVoices():
            description = str(token.GetDescription())
            if voice_name.lower() in description.lower() or "huihui" in description.lower():
                voice.Voice = token
                break
        voice.Rate = rate
        voice.Volume = volume
        stream.Open(str(wav_file), 3, False)
        voice.AudioOutputStream = stream
        voice.Speak(script_text)
        stream.Close()
        if not wav_file.exists() or wav_file.stat().st_size < 1024:
            raise RuntimeError("Windows SAPI TTS did not create a valid wav file.")
        avvg.run_command(
            [
                ffmpeg_exe,
                "-y",
                "-i",
                str(wav_file),
                "-af",
                "aresample=44100,loudnorm=I=-18:TP=-2:LRA=9,volume=1.02",
                "-codec:a",
                "libmp3lame",
                "-q:a",
                "2",
                str(audio_file),
            ]
        )
    finally:
        wav_file.unlink(missing_ok=True)
    if not _audio_is_valid(audio_file):
        raise RuntimeError("Windows SAPI child voice fallback produced invalid audio.")
    return "windows_sapi_child_fallback"


def _audio_is_valid(audio_file: Path) -> bool:
    duration = avvg.probe_audio_duration(audio_file)
    if not (duration and duration > 0.2 and audio_file.exists() and audio_file.stat().st_size > 1024):
        return False
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        return True
    try:
        result = subprocess.run(
            [
                ffmpeg_exe,
                "-hide_banner",
                "-i",
                str(audio_file),
                "-af",
                "volumedetect",
                "-f",
                "null",
                "NUL" if os.name == "nt" else "/dev/null",
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
            check=False,
        )
        match = re.search(r"max_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", result.stderr)
        if match:
            return float(match.group(1)) > -55.0
    except Exception:
        return True
    return True


def _write_silent_fallback_audio(audio_file: Path, script_text: str) -> None:
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required for fallback audio rendering.")
    duration = max(avvg.estimate_duration_from_text(script_text), 3.0)
    avvg.run_command(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=44100:cl=stereo",
            "-t",
            f"{duration:.3f}",
            str(audio_file),
        ]
    )


def build_distilled_script(persona: dict[str, Any], request_payload: dict[str, Any]) -> str:
    custom_script = _sanitize_prompt_field(request_payload.get("custom_script"))
    if custom_script:
        return custom_script

    title = clean_script(_string(request_payload.get("title"))).replace("\n", " ").strip()
    keywords = _normalize_keywords(request_payload.get("keywords", []))
    story_memo = _sanitize_prompt_field(request_payload.get("story_memo")).replace("\n", " ").strip()
    topic = _string(request_payload.get("topic")) or title or "今天这条内容"
    content_type = _string(request_payload.get("content_type")) or "insight"
    emotion_tone = _string(request_payload.get("emotion_tone")) or "steady"
    seconds = _int_value(request_payload.get("seconds"), 60) or 60

    hooks = list(persona.get("hook_candidates") or [])
    ctas = list(persona.get("cta_candidates") or [])
    terms = _unique_nonempty(list(persona.get("signature_terms") or []))
    speech = dict(persona.get("speech_profile") or {})
    human = dict(persona.get("human_profile") or {})

    personality_traits = _unique_nonempty(list(human.get("personality_traits") or []))
    behavior_traits = _unique_nonempty(list(human.get("behavior_traits") or []))
    communication_traits = _unique_nonempty(list(human.get("communication_traits") or []))
    emotion_traits = _unique_nonempty(list(human.get("emotion_traits") or []))
    expression_traits = _unique_nonempty(list(human.get("expression_traits") or []))
    voice_traits = _unique_nonempty(list(human.get("voice_traits") or []))
    script_flow = _unique_nonempty(list((persona.get("generation_profile") or {}).get("script_flow") or []))
    prompt_block = _string(persona.get("prompt_block"))

    focus_topic = title or topic
    keyword_phrase = "、".join(keywords[:4])
    term_line = "、".join(terms[:4]) if terms else "结构、节奏、表达、行动"
    memo_excerpt = story_memo[:42] + ("…" if len(story_memo) > 42 else "") if story_memo else ""
    prompt_anchor_line = (
        f"这条内容会继续沿着“{prompt_block}”这条蒸馏主线来讲，把你的判断、经历和表达方式保留下来。"
        if prompt_block
        else ""
    )

    direct = _has_any_trait(personality_traits, "direct", "practical")
    reflective = _has_any_trait(personality_traits, "reflective")
    interactive = _has_any_trait(personality_traits, "interactive") or _has_any_trait(
        communication_traits, "dialogue_style"
    )
    motivating = _has_any_trait(personality_traits, "motivating") or emotion_tone == "intense"
    step_driven = _has_any_trait(behavior_traits, "step_driven")
    action_oriented = _has_any_trait(behavior_traits, "action_oriented", "clear_decision")
    empathetic = _has_any_trait(emotion_traits, "empathetic") or emotion_tone == "warm"
    assertive = _has_any_trait(emotion_traits, "assertive", "intense") or emotion_tone == "intense"
    question_led = _has_any_trait(emotion_traits, "question_led") or interactive
    short_sentences = _has_any_trait(communication_traits, "short_sentences") or _has_any_trait(
        voice_traits, "short_bursts"
    )
    punchy = _string(speech.get("rhythm_style")) == "punchy"
    soft_cta = _string(speech.get("cta_style")) == "soft"
    point_then_method = _has_any_trait(script_flow, "point_then_method")

    seed_parts = [topic, title, " ".join(keywords[:6]), memo_excerpt, content_type, emotion_tone, "|".join(script_flow)]
    seed = "|".join(part for part in seed_parts if part) + f"|{datetime.now():%Y%m%d}"

    if direct and assertive:
        hook_default = f"先说结论，{focus_topic}这件事，别再靠临场发挥了。"
    elif question_led:
        hook_default = f"你是不是也在{focus_topic}这件事上，明明很认真，却总觉得讲出来不像自己？"
    elif empathetic:
        hook_default = f"如果你最近在{focus_topic}上有点卡住，先别急着否定自己。"
    else:
        hook_default = f"很多人做{focus_topic}时，不是没内容，而是还没找到自己的表达骨架。"

    cta_default = (
        "如果你愿意，我下一条继续把这套表达顺序拆得更细。"
        if soft_cta
        else "你今天就照这个顺序录一条，先发出去，再根据反馈继续调。"
        if motivating or action_oriented
        else "先照着这个顺序试一条，你会更容易找到自己的表达状态。"
    )

    hook = _pick(hooks, seed, hook_default)
    cta = _pick(ctas, seed[::-1], cta_default)
    if soft_cta:
        cta = cta.replace("评论区", "留言区").replace("立刻", "先")

    if direct:
        point_line = f"先说我的判断，{focus_topic}真正要稳住的，不是热闹感，而是{term_line}这套属于你的顺序。"
    elif reflective:
        point_line = f"我后来反复验证才发现，{focus_topic}最容易出问题的地方，不在努力，而在{term_line}没有固定下来。"
    else:
        point_line = f"你会发现，{focus_topic}一旦把{term_line}这些稳定元素钉住，整条内容就更像你自己。"

    method_line = (
        "我更建议你直接拆三步：先抛问题，再给判断，最后留一个观众今天就能执行的动作。"
        if step_driven
        else "别一下子追求完美，先把最重要的一层讲清，再补例子和动作，内容反而更稳。"
        if action_oriented
        else "先把核心观点说干净，再补一个真实场景，最后给动作，表达会比堆信息更有效。"
    )
    structure_lines = [point_line, method_line] if point_then_method else [method_line, point_line]

    keyword_line = (
        f"这条内容我会围着{keyword_phrase}展开，但重点还是回到你一贯的表达方式。"
        if keyword_phrase
        else f"这次不追求讲很多，只围着{focus_topic}把一个核心点说透。"
    )

    memo_line = (
        f"你刚刚提到“{memo_excerpt}”，这正好能拿来做成更有真人感的一条口播。"
        if memo_excerpt
        else f"真正让观众记住你的，往往不是信息量，而是你讲{focus_topic}时那种稳定又自然的节奏。"
    )

    emotion_line = (
        "所以你不用逼自己一下子变得特别会说，先保留你本来的温度，再把结构理顺就够了。"
        if empathetic
        else "别再一边讲一边怀疑自己，镜头一开就先把结论抛出来，你的状态会立刻稳很多。"
        if assertive
        else "你先把自己的节奏稳住，情绪自然会更顺，表达也会更像你本人。"
    )

    audience_line = (
        "你可以直接把观众拉进来，问他是不是也有同样的问题，这样开头更容易有真人交流感。"
        if interactive
        else "你不用刻意演，像平时认真和人解释一件事那样说，镜头里的你会更自然。"
    )

    visual_line = (
        "画面上保留一点表情和停顿，不要一口气念完，真人感会更强。"
        if _has_any_trait(expression_traits, "dynamic", "medium_close", "close_up")
        else "镜头上保持稳定和克制，让重点落在你的判断和语气上。"
    )

    voice_line = (
        "语气别飘，重音落在判断和动作词上。"
        if _has_any_trait(voice_traits, "assertive_tone")
        else "语气像聊天一样推进，不要太播音腔。"
        if _has_any_trait(voice_traits, "conversational_tone")
        else "语气保持稳定，停顿留给重点，不要抢词。"
    )

    lines: list[str] = [hook]
    if title and title != topic:
        lines.append(f"今天我就借“{title}”这件事，把你最该稳住的一层说清楚。")

    if content_type == "tutorial":
        lines.extend(
            [
                memo_line,
                prompt_anchor_line,
                *structure_lines,
                "你今天就按这个顺序试一条：先说问题，再给判断，最后只留一个马上能执行的动作。",
                voice_line,
                cta,
            ]
        )
    elif content_type == "emotional":
        lines.extend(
            [
                memo_line,
                prompt_anchor_line,
                *structure_lines,
                "很多时候你不是做不到，而是在镜头里太着急证明自己，反而把原本像你的那层表达弄丢了。",
                emotion_line,
                visual_line,
                cta,
            ]
        )
    elif content_type == "qa":
        lines.extend(
            [
                f"很多人问我，{focus_topic}到底应该怎么讲，短答案就是先别贪多。",
                prompt_anchor_line,
                *structure_lines,
                audience_line,
                "你先录一条二十秒版本，把顺序录顺，再慢慢加内容。",
                cta,
            ]
        )
    else:
        lines.extend(
            [
                memo_line,
                keyword_line,
                prompt_anchor_line,
                *structure_lines,
                emotion_line,
                audience_line,
                visual_line,
                cta,
            ]
        )

    script = "\n".join(_unique_nonempty(lines))
    target_chars = max(int(seconds * 3.6), 180)
    if _compact_len(script) < int(target_chars * 0.88):
        script = script + "\n" + f"记住，关于{focus_topic}这件事，你真正要复制的不是别人的腔调，而是你自己的{term_line}和节奏。"

    if short_sentences or punchy:
        script = script.replace("，", "。\n")
        script = re.sub(r"\n{3,}", "\n\n", script).strip()
    return script


def build_script(persona: dict[str, Any], request_payload: dict[str, Any]) -> str:
    custom_script = clean_script(str(request_payload.get("custom_script", "")).strip())
    if custom_script:
        return custom_script

    title = clean_script(str(request_payload.get("title", "")).strip()).replace("\n", " ").strip()
    keywords = _normalize_keywords(request_payload.get("keywords", []))
    story_memo = clean_script(str(request_payload.get("story_memo", "")).strip()).replace("\n", " ").strip()
    topic = str(request_payload.get("topic", "")).strip() or title or "今天这条内容"
    content_type = str(request_payload.get("content_type", "insight"))
    emotion_tone = str(request_payload.get("emotion_tone", "steady"))
    seconds = int(request_payload.get("seconds", 60) or 60)
    hooks = list(persona.get("hook_candidates") or [])
    ctas = list(persona.get("cta_candidates") or [])
    terms = list(persona.get("signature_terms") or [])
    speech_profile = dict(persona.get("speech_profile") or {})
    emotion_profile = dict(persona.get("emotion_profile") or {})
    seed_parts = [topic, title, " ".join(keywords[:6]), story_memo[:80], content_type, emotion_tone]
    seed = "|".join(part for part in seed_parts if part) + f"|{datetime.now():%Y%m%d}"

    hook = _pick(hooks, seed, "很多人以为自己缺的是能力，其实缺的是一套稳定表达方式。")
    cta = _pick(ctas, seed[::-1], "如果你要我把这套模版发给你，评论区打模版。")
    if speech_profile.get("cta_style") == "soft":
        cta = cta.replace("评论区打模版", "你愿意的话可以留言，我再继续展开")
    term_line = "、".join(terms[:4]) if terms else "结构、节奏、表达、执行"
    rhythm_style = str(speech_profile.get("rhythm_style", "balanced"))
    pause_style = str(emotion_profile.get("pause_style", "short_bursts"))
    warm_line = {
        "steady": "你不用一下子做很大，先把表达顺序固定住，效果会更稳。",
        "warm": "如果你最近有点累，也别急着否定自己，先把节奏找回来。",
        "intense": "现在最拖住你的不是能力，而是每次都从零开始组织表达。",
    }.get(emotion_tone, "先把表达顺序固定住，效果会更稳。")

    if content_type == "tutorial":
        lines = [
            hook,
            f"如果你想把{topic}说得更清楚，先别追求高级感，先把步骤拆出来。",
            f"我的做法一直很简单，就抓住{term_line}这几个固定点，一条一条往外说。",
            "今天你直接照着做三步：先说问题，再说判断，最后给一个立刻能执行的动作。",
            warm_line,
            cta,
        ]
    elif content_type == "emotional":
        lines = [
            hook,
            f"如果你最近因为{topic}反复怀疑自己，我想先告诉你，这不代表你不行。",
            "很多时候不是你做不到，而是你没有把自己的感受和观点用更稳定的方式表达出来。",
            f"当我开始固定{term_line}这些表达骨架之后，内容会更像我，人也更松弛。",
            warm_line,
            cta,
        ]
    elif content_type == "qa":
        lines = [
            f"很多人问我，{topic}到底怎么做，今天我直接给你一个短答案。",
            f"先别把事情想复杂，先抓住{term_line}这几个固定锚点。",
            "你每次开口，只要按结论、原因、动作这三个顺序说，内容就不会散。",
            warm_line,
            "你今天就先录一条二十秒版本，发出去，再根据反馈继续调。",
            cta,
        ]
    else:
        lines = [
            hook,
            f"很多人在做{topic}的时候，不是没有内容，而是表达没有形成固定结构。",
            f"我更建议你先把{term_line}这些稳定元素钉住，这样内容会越来越像你自己。",
            "每次开口时，就按钩子、判断、例子、动作、收尾这个顺序来，说话会更顺，镜头感也会更稳。",
            warm_line,
            cta,
        ]

    insert_at = 1 if len(lines) > 1 else 0
    if title and title != topic:
        lines.insert(insert_at, title)
        insert_at += 1
    if keywords:
        lines.insert(insert_at, " / ".join(keywords[:6]))
        insert_at += 1
    if story_memo:
        lines.insert(insert_at, story_memo[:120])

    script = "\n".join(lines)
    target_chars = max(int(seconds * 3.6), 180)
    if _compact_len(script) < int(target_chars * 0.88):
        script = script + "\n" + f"记住，关于{topic}这件事，你先稳定输出，再慢慢升级表达精度。"
    if rhythm_style == "punchy" and pause_style == "short_bursts":
        script = script.replace("，", "，").replace("。", "。\n")
        script = re.sub(r"\n{3,}", "\n\n", script).strip()
    return script


def _synthesize_audio(script_text: str, audio_file: Path, request_payload: dict[str, Any]) -> str:
    avvg.load_env_file(ROOT_DIR / ".env")
    provider = str(request_payload.get("tts_provider", "edge"))
    if provider == "local_clone":
        reference_audio_text = str(request_payload.get("voice_clone_reference_path", "")).strip()
        if not reference_audio_text:
            raise RuntimeError("Local voice clone needs an extracted or configured reference audio.")
        base_audio_file = audio_file.with_name(f"{audio_file.stem}.base.mp3")
        base_audio_file.unlink(missing_ok=True)
        _synthesize_base_audio_for_clone(script_text, base_audio_file, request_payload)
        try:
            convert_with_local_voice_clone(
                source_audio=base_audio_file,
                reference_audio=Path(reference_audio_text).expanduser(),
                output_file=audio_file,
            )
        finally:
            base_audio_file.unlink(missing_ok=True)
        if not _audio_is_valid(audio_file):
            raise RuntimeError("Local voice clone produced invalid audio.")
        return "local_clone"

    if provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            raise RuntimeError("OPENAI_API_KEY is required for OpenAI TTS.")
        avvg.synthesize_openai_tts(
            text=script_text,
            output_file=audio_file,
            api_key=api_key,
            model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
            voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
        )
        if not _audio_is_valid(audio_file):
            raise RuntimeError("OpenAI TTS produced invalid audio.")
        return provider

    if provider == "elevenlabs":
        api_key = os.getenv("ELEVENLABS_API_KEY", "").strip()
        voice_id = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
        if not api_key or not voice_id:
            raise RuntimeError("ELEVENLABS_API_KEY and ELEVENLABS_VOICE_ID are required for ElevenLabs.")
        avvg.synthesize_elevenlabs_tts(
            text=script_text,
            output_file=audio_file,
            api_key=api_key,
            voice_id=voice_id,
            model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
        )
        if not _audio_is_valid(audio_file):
            raise RuntimeError("ElevenLabs TTS produced invalid audio.")
        return provider

    if provider == "pyttsx3":
        avvg.synthesize_pyttsx3_tts(
            text=script_text,
            output_file=audio_file,
            voice_hint=_fallback_voice_hint(request_payload),
            rate=int(os.getenv("PYTTSX3_RATE", "0") or "0"),
        )
        if _audio_is_valid(audio_file):
            return "pyttsx3"
        _write_silent_fallback_audio(audio_file, script_text)
        return "silent_fallback"

    edge_error: Exception | None = None
    try:
        avvg.synthesize_edge_tts(
            text=script_text,
            output_file=audio_file,
            voice=str(request_payload.get("edge_voice", "zh-CN-XiaoxiaoNeural")),
            rate=str(request_payload.get("edge_rate", "")),
            volume=str(request_payload.get("edge_volume", "")),
        )
        if _audio_is_valid(audio_file):
            return "edge"
    except Exception as exc:
        edge_error = exc

    eleven_api = os.getenv("ELEVENLABS_API_KEY", "").strip()
    eleven_voice = os.getenv("ELEVENLABS_VOICE_ID", "").strip()
    if eleven_api and eleven_voice:
        try:
            avvg.synthesize_elevenlabs_tts(
                text=script_text,
                output_file=audio_file,
                api_key=eleven_api,
                voice_id=eleven_voice,
                model_id=os.getenv("ELEVENLABS_MODEL_ID", "eleven_multilingual_v2"),
            )
            if _audio_is_valid(audio_file):
                return "elevenlabs_fallback"
        except Exception:
            pass

    openai_api = os.getenv("OPENAI_API_KEY", "").strip()
    if openai_api:
        try:
            avvg.synthesize_openai_tts(
                text=script_text,
                output_file=audio_file,
                api_key=openai_api,
                model=os.getenv("OPENAI_TTS_MODEL", "gpt-4o-mini-tts"),
                voice=os.getenv("OPENAI_TTS_VOICE", "alloy"),
            )
            if _audio_is_valid(audio_file):
                return "openai_fallback"
        except Exception:
            pass

    if os.name == "nt":
        try:
            return _synthesize_windows_sapi_child_tts(script_text, audio_file, request_payload)
        except Exception:
            pass

    try:
        avvg.synthesize_pyttsx3_tts(
            text=script_text,
            output_file=audio_file,
            voice_hint=_fallback_voice_hint(request_payload),
            rate=int(os.getenv("PYTTSX3_RATE", "0") or "0"),
        )
        if _audio_is_valid(audio_file):
            return "pyttsx3_fallback"
    except Exception:
        pass

    if edge_error:
        raise RuntimeError(f"TTS failed and no voiced fallback was available: {edge_error}") from edge_error
    raise RuntimeError("TTS failed and no voiced fallback was available.")


def _run_avatar_command(
    command_template: str,
    *,
    audio_file: Path,
    script_file: Path,
    video_file: Path,
    request_payload: dict[str, Any],
) -> None:
    command = command_template.format(
        audio=str(audio_file),
        script=str(script_file),
        output=str(video_file),
        video=str(video_file),
        portrait=str(request_payload.get("portrait_path", "")),
        emotion=str(request_payload.get("emotion_tone", "steady")),
        topic=str(request_payload.get("topic", "")),
    )
    result = subprocess.run(
        command,
        cwd=str(ROOT_DIR),
        capture_output=True,
        text=True,
        check=False,
        shell=True,
    )
    if result.returncode != 0:
        stderr = "\n".join(result.stderr.splitlines()[-20:])
        raise RuntimeError(stderr or "Avatar command execution failed.")


def _fallback_voice_hint(request_payload: dict[str, Any]) -> str:
    edge_voice = str(request_payload.get("edge_voice", "")).strip().lower()
    if edge_voice.startswith("en-"):
        return "en"
    if edge_voice.startswith("zh-"):
        return "zh"
    return os.getenv("PYTTSX3_VOICE_HINT", "zh")


def _concat_audio_clips(clips: list[Path], output_file: Path) -> None:
    if not clips:
        raise RuntimeError("No audio clips to concatenate.")
    if len(clips) == 1:
        output_file.write_bytes(clips[0].read_bytes())
        return
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required to concatenate character voice clips.")
    concat_file = output_file.with_suffix(".audio_concat.txt")
    concat_file.write_text(
        "\n".join(f"file '{str(path.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in clips),
        encoding="utf-8",
    )
    avvg.run_command(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_file),
        ]
    )


def _write_srt_from_timed_units(
    *,
    segments: list[dict[str, Any]],
    output_file: Path,
    max_line_chars: int,
) -> None:
    lines: list[str] = []
    index = 1
    for segment in segments:
        text = _string(segment.get("text"))
        start = _float_value(segment.get("start"), 0.0)
        end = _float_value(segment.get("end"), start)
        if not text or end <= start:
            continue
        lines.extend(
            [
                str(index),
                f"{avvg.format_srt_timestamp(start)} --> {avvg.format_srt_timestamp(end)}",
                avvg.wrap_caption_text(text, max_line_chars),
                "",
            ]
        )
        index += 1
    output_file.write_text("\n".join(lines), encoding="utf-8")


def _storyboard_speakers_for_lines(script_text: str, request_payload: dict[str, Any]) -> list[str]:
    lines = [line.strip() for line in re.split(r"[\r\n]+", script_text) if line.strip()]
    storyboard = request_payload.get("animation_storyboard")
    speakers: list[str] = []
    if isinstance(storyboard, list):
        for item in storyboard:
            if isinstance(item, dict):
                speaker = _string(item.get("speaker"))
                if speaker in {"maodou", "peanut"}:
                    speakers.append(speaker)
    while len(speakers) < len(lines):
        speakers.append("maodou" if len(speakers) % 2 == 0 else "peanut")
    return speakers[: len(lines)]


def _synthesize_kids_character_audio(script_text: str, audio_file: Path, request_payload: dict[str, Any]) -> str:
    maodou_ref = Path(_string(request_payload.get("maodou_voice_reference_path"))).expanduser()
    peanut_ref = Path(_string(request_payload.get("peanut_voice_reference_path"))).expanduser()
    refs = {
        "maodou": maodou_ref if maodou_ref.exists() else None,
        "peanut": peanut_ref if peanut_ref.exists() else None,
    }
    if not refs["maodou"] and not refs["peanut"]:
        return _synthesize_audio(script_text, audio_file, request_payload)

    lines = [line.strip() for line in re.split(r"[\r\n]+", script_text) if line.strip()]
    if not lines:
        return _synthesize_audio(script_text, audio_file, request_payload)
    speakers = _storyboard_speakers_for_lines(script_text, request_payload)
    clip_dir = audio_file.with_suffix("")
    clip_dir.mkdir(parents=True, exist_ok=True)
    clips: list[Path] = []
    timed_segments: list[dict[str, Any]] = []
    cursor = 0.0
    cloned_count = 0
    try:
        for index, line in enumerate(lines, start=1):
            speaker = speakers[index - 1] if index - 1 < len(speakers) else ("maodou" if index % 2 else "peanut")
            ref_audio = refs.get(speaker) or refs.get("maodou") or refs.get("peanut")
            base_clip = clip_dir / f"voice_base_{index:02d}.mp3"
            out_clip = clip_dir / f"voice_{index:02d}.mp3"
            _synthesize_windows_sapi_child_tts(
                line,
                base_clip,
                {
                    **request_payload,
                    "sapi_rate": request_payload.get("sapi_rate", 0),
                    "sapi_volume": request_payload.get("sapi_volume", 96),
                },
            )
            if ref_audio:
                try:
                    convert_with_local_voice_clone(
                        source_audio=base_clip,
                        reference_audio=ref_audio,
                        output_file=out_clip,
                    )
                    cloned_count += 1
                except Exception as exc:
                    request_payload["character_voice_clone_warning"] = str(exc)[:500]
                    out_clip.write_bytes(base_clip.read_bytes())
            else:
                out_clip.write_bytes(base_clip.read_bytes())
            clip_duration = avvg.probe_audio_duration(out_clip) or avvg.estimate_duration_from_text(line)
            timed_segments.append(
                {
                    "index": index,
                    "speaker": speaker,
                    "text": line,
                    "start": round(cursor, 3),
                    "end": round(cursor + clip_duration, 3),
                    "duration": round(clip_duration, 3),
                }
            )
            cursor += clip_duration
            clips.append(out_clip)
        _concat_audio_clips(clips, audio_file)
    finally:
        for clip in clip_dir.glob("voice_*.mp3"):
            if clip.resolve() != audio_file.resolve():
                clip.unlink(missing_ok=True)
        for clip in clip_dir.glob("voice_base_*.mp3"):
            clip.unlink(missing_ok=True)
        try:
            clip_dir.rmdir()
        except OSError:
            pass
    if not _audio_is_valid(audio_file):
        raise RuntimeError("Character voice audio was generated but is invalid.")
    request_payload["character_voice_clone_segments"] = cloned_count
    request_payload["timed_caption_units"] = timed_segments
    return "kids_character_voice_clone" if cloned_count else "kids_character_voice_reference_fallback"


def _resolution_to_size(output_resolution: str) -> str:
    token = _string(output_resolution).lower()
    if token == "720p":
        return "720x1280"
    if token == "1440p":
        return "1440x2560"
    return "1080x1920"


def _mux_generated_video_with_audio_and_subtitles(
    *,
    source_video: Path,
    audio_file: Path,
    subtitle_file: Path,
    output_file: Path,
    fps: int,
    subtitle_font: str,
    subtitle_size: int,
    subtitle_margin_v: int,
) -> None:
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required to mux Kling video output.")
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
        f"subtitles='{avvg.escape_path_for_subtitles(subtitle_file)}':"
        f"force_style='{subtitle_style}'"
    )
    avvg.run_command(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(source_video),
            "-i",
            str(audio_file),
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
    )


def _split_script_for_video_scenes(script_text: str, *, target_count: int) -> list[str]:
    lines = [line.strip() for line in re.split(r"[\r\n]+", script_text) if line.strip()]
    if not lines:
        compact = re.sub(r"\s+", "", script_text).strip()
        lines = [item for item in re.split(r"(?<=[。！？!?])", compact) if item.strip()]
    if not lines:
        return [script_text.strip() or "可爱的毛豆和花生一起学习。"]
    count = max(1, min(target_count, len(lines)))
    groups: list[list[str]] = [[] for _ in range(count)]
    for index, line in enumerate(lines):
        groups[min(count - 1, index * count // len(lines))].append(line)
    return ["\n".join(group).strip() for group in groups if group]


def _split_items_for_video_scenes(items: list[Any], *, target_count: int) -> list[list[Any]]:
    cleaned = [item for item in items if item]
    if not cleaned:
        return []
    count = max(1, min(target_count, len(cleaned)))
    groups: list[list[Any]] = [[] for _ in range(count)]
    for index, item in enumerate(cleaned):
        groups[min(count - 1, index * count // len(cleaned))].append(item)
    return [group for group in groups if group]


def _zhipu_scene_plan(
    script_text: str,
    request_payload: dict[str, Any],
    *,
    target_count: int,
) -> list[dict[str, Any]]:
    storyboard = request_payload.get("animation_storyboard")
    if isinstance(storyboard, list) and storyboard:
        groups = _split_items_for_video_scenes(storyboard, target_count=target_count)
        plan: list[dict[str, Any]] = []
        for group in groups:
            lines = [
                _string(item.get("line")) if isinstance(item, dict) else ""
                for item in group
            ]
            scene_script = "\n".join(line for line in lines if line).strip()
            if not scene_script:
                scene_script = script_text.strip()
            plan.append({"script": scene_script, "storyboard": group})
        if plan:
            return plan
    return [
        {"script": scene_script, "storyboard": []}
        for scene_script in _split_script_for_video_scenes(script_text, target_count=target_count)
    ]


def _scene_audio_durations(scene_plan: list[dict[str, Any]], request_payload: dict[str, Any], total_duration: float) -> list[float]:
    timed_units = request_payload.get("timed_caption_units")
    if isinstance(timed_units, list) and timed_units:
        durations: list[float] = []
        cursor = 0
        for scene in scene_plan:
            line_count = len([line for line in re.split(r"[\r\n]+", _string(scene.get("script"))) if line.strip()])
            line_count = max(1, line_count)
            scene_units = timed_units[cursor : cursor + line_count]
            cursor += line_count
            duration = sum(_float_value(unit.get("duration"), 0.0) for unit in scene_units if isinstance(unit, dict))
            durations.append(max(0.5, duration))
        if len(durations) == len(scene_plan) and sum(durations) > 0:
            return durations

    weights = [max(_compact_len(_string(scene.get("script"))), 1) for scene in scene_plan]
    total_weight = float(sum(weights) or 1)
    return [max(0.5, float(total_duration) * weight / total_weight) for weight in weights]


def _trim_video_clip_to_duration(source_file: Path, output_file: Path, *, duration: float, fps: int) -> None:
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required to trim generated scene videos.")
    avvg.run_command(
        [
            ffmpeg_exe,
            "-y",
            "-i",
            str(source_file),
            "-t",
            f"{max(duration, 0.5):.3f}",
            "-r",
            str(fps),
            "-an",
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "16",
            "-pix_fmt",
            "yuv420p",
            str(output_file),
        ]
    )


def _concat_video_clips(clips: list[Path], output_file: Path) -> None:
    if not clips:
        raise RuntimeError("No video clips to concatenate.")
    if len(clips) == 1:
        output_file.write_bytes(clips[0].read_bytes())
        return
    ffmpeg_exe = avvg.resolve_binary("ffmpeg")
    if not ffmpeg_exe:
        raise RuntimeError("ffmpeg is required to concatenate generated video clips.")
    concat_file = output_file.with_suffix(".concat.txt")
    concat_file.write_text(
        "\n".join(f"file '{str(path.resolve()).replace(chr(39), chr(39) + chr(92) + chr(39) + chr(39))}'" for path in clips),
        encoding="utf-8",
    )
    avvg.run_command(
        [
            ffmpeg_exe,
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_file),
            "-c",
            "copy",
            str(output_file),
        ]
    )


def render_job(
    job: dict[str, Any],
    persona: dict[str, Any],
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    request_payload = dict(job.get("request", {}))
    avatar_settings = dict(job.get("avatar_settings") or {})
    request_payload, avatar_settings, applied_defaults = _apply_reference_defaults(
        request_payload,
        persona,
        avatar_settings,
    )
    request_payload["story_memo"] = _sanitize_prompt_field(request_payload.get("story_memo"))
    request_payload["custom_script"] = _sanitize_prompt_field(request_payload.get("custom_script"))
    script_source = "custom_script" if _string(request_payload.get("custom_script")) else "distilled_persona"
    persona_applied = _persona_applied_summary(persona)
    output_root = OUTPUTS_DIR / job["id"]
    _report_progress(progress_callback, 10, "preparing", "Preparing output folder")
    output_root.mkdir(parents=True, exist_ok=True)

    topic = str(request_payload.get("topic", "")).strip()
    _report_progress(progress_callback, 18, "writing_script", "Generating script")
    script_text = build_distilled_script(persona, request_payload)
    if _string(request_payload.get("project_mode")) == "kids_cartoon":
        script_text = normalize_kids_script_text(script_text)
        request_payload["custom_script"] = script_text
    artifacts = avvg.ensure_output_paths(str(output_root), topic or _slugify(job["id"]))
    artifacts.script_file.write_text(script_text, encoding="utf-8")

    render_mode = str(request_payload.get("render_mode", "subtitle_card"))
    artifact_urls = {
        "script_url": to_media_url(artifacts.script_file),
        "metadata_url": to_media_url(artifacts.metadata_file),
    }
    provider = ""
    duration = 0.0
    if render_mode != "script_only":
        _report_progress(progress_callback, 42, "synthesizing_audio", "Generating audio")
        if _string(request_payload.get("project_mode")) == "kids_cartoon":
            provider = _synthesize_kids_character_audio(script_text, artifacts.audio_file, request_payload)
        else:
            provider = _synthesize_audio(script_text, artifacts.audio_file, request_payload)
        duration = avvg.probe_audio_duration(artifacts.audio_file) or avvg.estimate_duration_from_text(script_text)
        max_line_chars = 18
        _report_progress(progress_callback, 58, "writing_subtitles", "Generating subtitles")
        timed_caption_units = request_payload.get("timed_caption_units")
        if isinstance(timed_caption_units, list) and timed_caption_units:
            _write_srt_from_timed_units(
                segments=timed_caption_units,
                output_file=artifacts.subtitle_file,
                max_line_chars=max_line_chars,
            )
        else:
            avvg.write_srt(
                units=avvg.split_caption_units(script_text, max_line_chars),
                total_duration=duration,
                max_line_chars=max_line_chars,
                output_file=artifacts.subtitle_file,
            )
        artifact_urls["audio_url"] = to_media_url(artifacts.audio_file)
        artifact_urls["subtitle_url"] = to_media_url(artifacts.subtitle_file)

        if render_mode == "avatar_command":
            _report_progress(progress_callback, 78, "rendering_avatar", "Running avatar renderer")
            command_template = str(request_payload.get("avatar_command_template", "")).strip()
            if not command_template:
                raise RuntimeError("Avatar render mode requires avatar_command_template.")
            _run_avatar_command(
                command_template,
                audio_file=artifacts.audio_file,
                script_file=artifacts.script_file,
                video_file=artifacts.video_file,
                request_payload=request_payload,
            )
        elif render_mode == "sadtalker":
            _report_progress(progress_callback, 78, "rendering_sadtalker", "Rendering with SadTalker")
            avatar_result = run_sadtalker(
                avatar_settings,
                audio_file=artifacts.audio_file,
                output_file=artifacts.video_file,
                request_payload=request_payload,
                progress_callback=lambda percent, message: _report_progress(
                    progress_callback,
                    percent,
                    "rendering_sadtalker",
                    message,
                ),
            )
            artifact_urls["avatar_raw_video_url"] = to_media_url(avatar_result["raw_video_path"])
        elif render_mode in {"cartoon_native_2d", "cartoon_native_3d"}:
            animation_style = _string(request_payload.get("animation_style"))
            is_3d = render_mode == "cartoon_native_3d" or "3d" in animation_style.lower()
            target_fps = 24 if _bool_value(request_payload.get("single_scene_locked"), False) else 30
            fps = max(12, min(60, int(request_payload.get("target_fps") or target_fps)))
            video_provider = _string(request_payload.get("video_provider")).lower()
            if video_provider in {"zhipu_qingying", "zhipu", "qingying", "bigmodel", "cogvideox"}:
                requested_seconds = _int_value(request_payload.get("seconds"), int(duration or 0)) or int(duration or 0)
                target_video_seconds = max(duration, min(60, float(requested_seconds or 30)))
                scene_count = max(1, min(6, int((target_video_seconds + 9.9) // 10)))
                if _string(request_payload.get("project_mode")) == "kids_cartoon":
                    scene_count = max(2, scene_count)
                scene_plan = _zhipu_scene_plan(script_text, request_payload, target_count=scene_count)
                zhipu_clips: list[Path] = []
                zhipu_tasks: list[dict[str, Any]] = []
                scene_audio_durations = _scene_audio_durations(scene_plan, request_payload, duration)
                for scene_index, scene in enumerate(scene_plan, start=1):
                    scene_script = _string(scene.get("script")) or script_text
                    scene_storyboard = scene.get("storyboard")
                    percent = 70 + min(16, int(scene_index * 16 / max(1, len(scene_plan))))
                    _report_progress(
                        progress_callback,
                        percent,
                        "creating_zhipu_scene",
                        f"Submitting Zhipu Qingying scene {scene_index}/{len(scene_plan)}",
                    )
                    scene_payload = dict(request_payload)
                    scene_payload["custom_script"] = scene_script
                    scene_payload["seconds"] = 10 if duration >= 8 else 5
                    scene_payload["scene_index"] = scene_index
                    scene_payload["scene_count"] = len(scene_plan)
                    if isinstance(scene_storyboard, list) and scene_storyboard:
                        scene_payload["animation_storyboard"] = scene_storyboard
                    scene_source = artifacts.video_file.with_name(f"zhipu_scene_{scene_index:02d}.mp4")
                    task = create_zhipu_video_task(
                        request_payload=scene_payload,
                        script_text=scene_script,
                        duration=10.0,
                    )
                    zhipu_tasks.append({
                        "scene": scene_index,
                        "task_id": task["task_id"],
                        "model": (task.get("request") or {}).get("model", ""),
                        "script": scene_script,
                        "storyboard": scene_storyboard if isinstance(scene_storyboard, list) else [],
                    })
                    request_payload["zhipu_task_id"] = task["task_id"]
                    request_payload["zhipu_model"] = (task.get("request") or {}).get("model", "")
                    _report_progress(
                        progress_callback,
                        percent,
                        "waiting_zhipu_scene",
                        f"Waiting for Zhipu Qingying scene {scene_index}/{len(scene_plan)} task {task['task_id']}",
                    )
                    zhipu_result = wait_for_zhipu_video(
                        task_id=task["task_id"],
                        output_file=scene_source,
                        timeout_sec=int(os.getenv("ZHIPU_VIDEO_TIMEOUT_SEC", "3600") or "3600"),
                    )
                    zhipu_tasks[-1]["task_status"] = zhipu_result.get("task_status", "")
                    scene_duration = scene_audio_durations[min(scene_index - 1, len(scene_audio_durations) - 1)]
                    timed_scene_source = artifacts.video_file.with_name(f"zhipu_scene_{scene_index:02d}_timed.mp4")
                    _trim_video_clip_to_duration(
                        scene_source,
                        timed_scene_source,
                        duration=scene_duration,
                        fps=fps,
                    )
                    zhipu_tasks[-1]["audio_duration"] = round(scene_duration, 3)
                    zhipu_clips.append(timed_scene_source)
                    artifact_urls[f"zhipu_scene_{scene_index:02d}_url"] = to_media_url(timed_scene_source)

                zhipu_source = artifacts.video_file.with_name("zhipu_qingying_raw.mp4")
                _report_progress(progress_callback, 87, "concatenating_zhipu_scenes", "Joining Zhipu Qingying scene videos")
                _concat_video_clips(zhipu_clips, zhipu_source)
                artifact_urls["zhipu_raw_video_url"] = to_media_url(zhipu_source)
                request_payload["zhipu_result"] = {
                    "task_status": "SUCCESS",
                    "provider": "zhipu_qingying",
                    "model": request_payload.get("zhipu_model", ""),
                    "scene_count": len(zhipu_clips),
                    "tasks": zhipu_tasks,
                }
                _report_progress(progress_callback, 88, "muxing_zhipu_video", "Adding narration and subtitles")
                _mux_generated_video_with_audio_and_subtitles(
                    source_video=zhipu_source,
                    audio_file=artifacts.audio_file,
                    subtitle_file=artifacts.subtitle_file,
                    output_file=artifacts.video_file,
                    fps=fps,
                    subtitle_font=str(request_payload.get("subtitle_font", "Microsoft YaHei")),
                    subtitle_size=int(request_payload.get("subtitle_size", 24)),
                    subtitle_margin_v=int(request_payload.get("subtitle_margin_v", 360)),
                )
            elif video_provider in {"kling", "official_kling", "kling_official", "dashscope_kling", "aliyun_kling"}:
                official_kling_ready = bool(
                    os.getenv("KLING_ACCESS_KEY", "").strip()
                    and os.getenv("KLING_SECRET_KEY", "").strip()
                )
                dashscope_kling_ready = bool(os.getenv("DASHSCOPE_API_KEY", "").strip())
                use_official_kling = (
                    video_provider in {"kling", "official_kling", "kling_official"} and official_kling_ready
                )
                use_dashscope_kling = (
                    video_provider in {"kling", "dashscope_kling", "aliyun_kling"} and dashscope_kling_ready
                )
                if not use_official_kling and not use_dashscope_kling:
                    raise RuntimeError(
                        "Kling API is selected, but no usable credentials were found. "
                        "Set KLING_ACCESS_KEY and KLING_SECRET_KEY for official Kling, "
                        "or set DASHSCOPE_API_KEY for DashScope Kling."
                    )
                provider_name = "official" if use_official_kling else "dashscope"
                request_payload["kling_provider"] = provider_name
                _report_progress(progress_callback, 72, "creating_kling_task", "Submitting 可灵 video task")
                kling_source = artifacts.video_file.with_name("kling_raw.mp4")
                if use_official_kling:
                    task = create_kling_official_task(
                        request_payload=request_payload,
                        script_text=script_text,
                        duration=duration,
                    )
                else:
                    task = create_kling_task(
                        request_payload=request_payload,
                        script_text=script_text,
                        duration=duration,
                    )
                request_payload["kling_task_id"] = task["task_id"]
                _report_progress(progress_callback, 78, "waiting_kling_task", f"Waiting for 可灵 task {task['task_id']}")
                if use_official_kling:
                    kling_result = wait_for_kling_official_video(task_id=task["task_id"], output_file=kling_source)
                else:
                    kling_result = wait_for_kling_video(task_id=task["task_id"], output_file=kling_source)
                artifact_urls["kling_raw_video_url"] = to_media_url(kling_source)
                request_payload["kling_result"] = {
                    "task_id": kling_result.get("task_id", ""),
                    "task_status": kling_result.get("task_status", ""),
                    "provider": provider_name,
                }
                _report_progress(progress_callback, 88, "muxing_kling_video", "Adding narration and subtitles")
                _mux_generated_video_with_audio_and_subtitles(
                    source_video=kling_source,
                    audio_file=artifacts.audio_file,
                    subtitle_file=artifacts.subtitle_file,
                    output_file=artifacts.video_file,
                    fps=fps,
                    subtitle_font=str(request_payload.get("subtitle_font", "Microsoft YaHei")),
                    subtitle_size=int(request_payload.get("subtitle_size", 24)),
                    subtitle_margin_v=int(request_payload.get("subtitle_margin_v", 360)),
                )
            else:
                stage = "rendering_native_3d" if is_3d else "rendering_native_2d"
                mode_name = "3D" if is_3d else "2D"
                _report_progress(
                    progress_callback,
                    78,
                    stage,
                    f"Rendering native frame-by-frame {mode_name} animation ({fps}fps)",
                )
                output_size = _resolution_to_size(request_payload.get("output_resolution", "1080p"))
                avvg.render_native_cartoon_video(
                    audio_file=artifacts.audio_file,
                    subtitle_file=artifacts.subtitle_file,
                    output_file=artifacts.video_file,
                    script_text=script_text,
                    storyboard=request_payload.get("animation_storyboard"),
                    prompt_template=None,
                    size=output_size,
                    fps=fps,
                    duration=duration,
                    subtitle_font=str(request_payload.get("subtitle_font", "Microsoft YaHei")),
                    subtitle_size=int(request_payload.get("subtitle_size", 24)),
                    subtitle_margin_v=int(request_payload.get("subtitle_margin_v", 360)),
                    force_bgm=_bool_value(request_payload.get("force_bgm"), True),
                    background_image=str(request_payload.get("background_image", "")),
                    animation_style=animation_style or ("cartoon_3d" if is_3d else "cartoon_2d"),
                    single_protagonist=_bool_value(request_payload.get("single_protagonist"), False),
                    single_scene_locked=_bool_value(request_payload.get("single_scene_locked"), False),
                    optical_flow_temporal_align=_bool_value(request_payload.get("optical_flow_temporal_align"), False),
                    forbid_extra_characters=_bool_value(request_payload.get("forbid_extra_characters"), False),
                    layered_clean_rendering=_bool_value(request_payload.get("layered_clean_rendering"), False),
                )
        elif render_mode == "subtitle_card":
            if _bool_value(request_payload.get("forbid_static_micro_motion"), False):
                raise RuntimeError(
                    "Static-image micro-motion rendering is disabled by policy. "
                    "Please use render_mode=cartoon_native_3d or cartoon_native_2d."
                )
            _report_progress(progress_callback, 78, "rendering_video", "Rendering subtitle video")
            project_mode = _string(request_payload.get("project_mode"))
            dynamic_default = project_mode == "kids_cartoon"
            dynamic_background = _bool_value(request_payload.get("dynamic_background"), dynamic_default)
            dynamic_style = _string(request_payload.get("dynamic_style")) or ("comic" if dynamic_default else "gentle")
            avvg.render_video(
                audio_file=artifacts.audio_file,
                subtitle_file=artifacts.subtitle_file,
                output_file=artifacts.video_file,
                size="1080x1920",
                fps=30,
                background_image=str(request_payload.get("background_image", "")),
                bg_color=str(request_payload.get("background_color", "#10212c")),
                subtitle_font=str(request_payload.get("subtitle_font", "Microsoft YaHei")),
                subtitle_size=int(request_payload.get("subtitle_size", 18)),
                subtitle_margin_v=int(request_payload.get("subtitle_margin_v", 360 if project_mode == "kids_cartoon" else 120)),
                duration=duration,
                dynamic_background=dynamic_background,
                dynamic_style=dynamic_style,
                dynamic_rhythm_text=script_text,
            )
        if artifacts.video_file.exists():
            artifact_urls["video_url"] = to_media_url(artifacts.video_file)

    _report_progress(progress_callback, 92, "writing_metadata", "Writing metadata")
    metadata = {
        "created_at": now_iso(),
        "job_id": job["id"],
        "topic": topic,
        "provider": provider,
        "render_mode": render_mode,
        "duration_seconds": round(duration, 3),
        "script_chars": _compact_len(script_text),
        "persona_name": persona.get("name", ""),
        "request": request_payload,
        "applied_defaults": applied_defaults,
        "persona_applied": persona_applied,
        "script_source": script_source,
        "persona_script_used": script_source == "distilled_persona",
        "persona_visual_used": "distilled_visual_profile" in applied_defaults,
    }
    artifacts.metadata_file.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    _report_progress(progress_callback, 100, "completed", "Task completed")

    return {
        "status": "completed",
        "completed_at": now_iso(),
        "request": request_payload,
        "script_text": script_text,
        "progress_percent": 100,
        "progress_stage": "completed",
        "progress_message": "Task completed",
        "artifacts": artifact_urls,
        "output_dir": str(artifacts.run_dir),
        "summary": {
            "duration_seconds": round(duration, 3),
            "script_chars": _compact_len(script_text),
            "tts_provider": provider,
            "render_mode": render_mode,
            "applied_defaults": applied_defaults,
            "persona_name": persona.get("name", ""),
            "persona_applied": persona_applied,
            "script_source": script_source,
            "persona_script_used": script_source == "distilled_persona",
            "persona_visual_used": "distilled_visual_profile" in applied_defaults,
        },
    }
