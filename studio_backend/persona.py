from __future__ import annotations

from collections import Counter
from typing import Any

from .storage import now_iso


DEFAULT_CONTENT_MODES = [
    {
        "key": "insight",
        "label": "观点拆解",
        "description": "适合认知升级、判断表达、讲一个你自己的清晰观点。",
    },
    {
        "key": "tutorial",
        "label": "步骤教学",
        "description": "适合做干货教程、步骤演示、方法拆解。",
    },
    {
        "key": "emotional",
        "label": "情感共鸣",
        "description": "适合做情绪承接、关系话题、鼓励型表达。",
    },
    {
        "key": "qa",
        "label": "高频问答",
        "description": "适合把评论区问题变成口播内容。",
    },
]


def _build_prompt_block(persona: dict[str, Any]) -> str:
    speech = persona["speech_profile"]
    visual = persona["visual_profile"]
    emotion = persona["emotion_profile"]
    human = persona.get("human_profile") or {}
    hooks = " | ".join(speech["hook_candidates"][:4])
    ctas = " | ".join(speech["cta_candidates"][:4])
    terms = ", ".join(speech["signature_terms"][:8])
    personality = ", ".join(human.get("personality_traits", [])[:4])
    communication = ", ".join(human.get("communication_traits", [])[:4])
    return "\n".join(
        [
            "Use spoken Chinese with short, clear sentences.",
            f"Target around {speech['recommended_chars_60s']} chars for a 60-second clip.",
            f"Preferred framing: {visual['camera_distance']}; lighting: {visual['lighting_style']}.",
            f"Expression energy: {emotion['expression_energy']}; delivery warmth: {emotion['delivery_temperature']}.",
            f"Pause style: {emotion['pause_style']}; emphasis style: {emotion['emphasis_style']}.",
            f"Shot behavior: {visual['camera_movement_style']}; center bias: {visual['face_center_bias']}.",
            f"Rhythm style: {speech['rhythm_style']}; CTA style: {speech['cta_style']}.",
            f"Personality cues: {personality}" if personality else "Keep the host persona grounded and authentic.",
            f"Communication cues: {communication}" if communication else "Keep the communication style clear and hook-led.",
            f"Hook examples: {hooks}" if hooks else "Open fast with a practical hook.",
            f"CTA examples: {ctas}" if ctas else "Close with a direct CTA.",
            f"Signature terms: {terms}" if terms else "Keep repeated wording consistent.",
        ]
    )


def _camera_distance(face_ratio: float) -> str:
    if face_ratio >= 0.18:
        return "close_up"
    if face_ratio >= 0.08:
        return "medium_close"
    return "medium"


def _lighting_style(brightness: float) -> str:
    if brightness >= 160:
        return "bright_clean"
    if brightness >= 105:
        return "balanced_soft"
    return "low_key"


def _expression_energy(motion: float, speaking_pace: float) -> str:
    if motion >= 16 or speaking_pace >= 4.7:
        return "intense"
    if motion >= 8 or speaking_pace >= 3.8:
        return "balanced"
    return "calm"


def _personality_traits(
    speaking_pace: float,
    question_ratio: float,
    exclamation_ratio: float,
    short_sentence_ratio: float,
) -> list[str]:
    traits: list[str] = []
    traits.append("practical" if speaking_pace >= 3.6 else "gentle")
    traits.append("direct" if short_sentence_ratio >= 0.5 else "reflective")
    if question_ratio >= 0.18:
        traits.append("interactive")
    if exclamation_ratio >= 0.18 or speaking_pace >= 4.6:
        traits.append("motivating")
    return traits


def _behavior_traits(
    motion: float,
    face_center_drift: float,
    short_sentence_ratio: float,
    pause_density: float,
) -> list[str]:
    traits: list[str] = ["action_oriented" if motion >= 10 else "steady_execution"]
    if short_sentence_ratio >= 0.45:
        traits.append("step_driven")
    if pause_density <= 5.0:
        traits.append("clear_decision")
    if face_center_drift <= 0.06:
        traits.append("stable_presence")
    return traits


def _communication_traits(
    rhythm_style: str,
    cta_style: str,
    question_ratio: float,
    short_sentence_ratio: float,
) -> list[str]:
    traits = ["hook_first", rhythm_style]
    traits.append("cta_close" if cta_style == "direct" else "soft_close")
    if question_ratio >= 0.18:
        traits.append("dialogue_style")
    if short_sentence_ratio >= 0.45:
        traits.append("short_sentences")
    return traits


def _emotion_traits(expression_energy: str, delivery_temperature: str, emphasis_style: str) -> list[str]:
    traits = [expression_energy, delivery_temperature]
    if emphasis_style:
        traits.append(emphasis_style)
    return traits


def _expression_traits(
    camera_distance: str,
    camera_movement_style: str,
    face_center_bias: str,
    lighting_style: str,
) -> list[str]:
    return [camera_distance, camera_movement_style, face_center_bias, lighting_style]


def _voice_traits(
    speaking_pace: float,
    pause_style: str,
    question_ratio: float,
    exclamation_ratio: float,
) -> list[str]:
    pace_code = "fast_voice" if speaking_pace >= 4.6 else "balanced_voice" if speaking_pace >= 3.6 else "calm_voice"
    tone_code = "assertive_tone" if exclamation_ratio >= 0.18 else "conversational_tone" if question_ratio >= 0.18 else "steady_tone"
    return [pace_code, pause_style, tone_code]


def _generation_profile(speech_profile: dict[str, Any], human_profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "supported_inputs": ["topic", "title", "keywords", "story_memo", "custom_script"],
        "script_flow": ["hook_first", "point_then_method", "cta_close"],
        "voice_anchor": human_profile.get("voice_traits", []),
        "expression_anchor": human_profile.get("expression_traits", []),
        "recommended_chars_60s": speech_profile.get("recommended_chars_60s", 220),
    }


def default_persona(name: str = "我的数字分身") -> dict[str, Any]:
    timestamp = now_iso()
    hooks = [
        "你是不是也在这件事上反复卡住？",
        "很多人以为这是能力问题，其实是表达结构没搭好。",
    ]
    ctas = [
        "如果你要我把模板发给你，评论区打模板。",
        "关注我，下一条我把具体步骤拆给你。",
    ]
    terms = ["结构", "节奏", "表达", "执行", "稳定输出"]
    persona = {
        "id": "persona_default",
        "name": name,
        "created_at": timestamp,
        "updated_at": timestamp,
        "sample_count": 0,
        "source_analysis_ids": [],
        "speech_profile": {
            "recommended_chars_60s": 220,
            "avg_sentence_len": 22.0,
            "speaking_pace_cps": 3.8,
            "question_ratio": 0.1,
            "exclamation_ratio": 0.1,
            "comma_pause_density": 5.0,
            "short_sentence_ratio": 0.5,
            "rhythm_style": "balanced",
            "cta_style": "direct",
            "hook_candidates": hooks,
            "cta_candidates": ctas,
            "signature_terms": terms,
        },
        "visual_profile": {
            "camera_distance": "medium_close",
            "lighting_style": "balanced_soft",
            "camera_movement_style": "stable",
            "face_center_bias": "centered",
            "motion_score": 8.0,
            "brightness_score": 120.0,
            "face_ratio": 0.12,
            "face_center_drift": 0.04,
        },
        "emotion_profile": {
            "expression_energy": "balanced",
            "delivery_temperature": "clear_practical",
            "pause_style": "short_sentences",
            "emphasis_style": "measured",
        },
        "human_profile": {
            "personality_traits": ["practical", "direct", "interactive"],
            "behavior_traits": ["steady_execution", "step_driven", "stable_presence"],
            "communication_traits": ["hook_first", "balanced", "cta_close", "short_sentences"],
            "emotion_traits": ["balanced", "clear_practical", "measured"],
            "expression_traits": ["medium_close", "stable", "centered", "balanced_soft"],
            "voice_traits": ["balanced_voice", "short_sentences", "steady_tone"],
        },
        "content_modes": DEFAULT_CONTENT_MODES,
    }
    persona["hook_candidates"] = hooks
    persona["cta_candidates"] = ctas
    persona["signature_terms"] = terms
    persona["recommended_chars_60s"] = persona["speech_profile"]["recommended_chars_60s"]
    persona["generation_profile"] = _generation_profile(persona["speech_profile"], persona["human_profile"])
    persona["prompt_block"] = _build_prompt_block(persona)
    return persona


def distill_persona(
    analyses: list[dict[str, Any]],
    *,
    existing: dict[str, Any] | None = None,
    preferred_name: str | None = None,
) -> dict[str, Any]:
    if not analyses:
        return default_persona(preferred_name or (existing or {}).get("name", "我的数字分身"))

    hook_counter: Counter[str] = Counter()
    cta_counter: Counter[str] = Counter()
    term_counter: Counter[str] = Counter()
    chars_60s_values: list[int] = []
    sentence_lengths: list[float] = []
    speaking_paces: list[float] = []
    question_ratios: list[float] = []
    exclamation_ratios: list[float] = []
    pause_densities: list[float] = []
    short_sentence_ratios: list[float] = []
    face_ratios: list[float] = []
    brightness_scores: list[float] = []
    motion_scores: list[float] = []
    face_center_drifts: list[float] = []
    analysis_ids: list[str] = []

    for analysis in analyses:
        analysis_ids.append(str(analysis.get("id", "")))
        speech = analysis.get("speech_metrics", {})
        visual = analysis.get("visual_metrics", {})

        has_speech_sample = float(speech.get("char_count", 0) or 0.0) > 0
        if has_speech_sample:
            hook = str(speech.get("hook_candidate", "")).strip()
            cta = str(speech.get("cta_candidate", "")).strip()
            if hook:
                hook_counter[hook] += 1
            if cta:
                cta_counter[cta] += 1

            for term in speech.get("keywords", []) or []:
                cleaned = str(term).strip()
                if cleaned:
                    term_counter[cleaned] += 1

            chars_60s_values.append(int(speech.get("recommended_chars_60s", 220) or 220))
            sentence_lengths.append(float(speech.get("avg_sentence_len", 22.0) or 22.0))
            speaking_paces.append(float(speech.get("speaking_pace_cps", 3.8) or 3.8))
            question_ratios.append(float(speech.get("question_ratio", 0.1) or 0.1))
            exclamation_ratios.append(float(speech.get("exclamation_ratio", 0.1) or 0.1))
            pause_densities.append(float(speech.get("comma_pause_density", 5.0) or 5.0))
            short_sentence_ratios.append(float(speech.get("short_sentence_ratio", 0.5) or 0.5))
        face_ratios.append(float(visual.get("face_ratio", 0.12) or 0.12))
        brightness_scores.append(float(visual.get("brightness_score", 120.0) or 120.0))
        motion_scores.append(float(visual.get("motion_score", 8.0) or 8.0))
        face_center_drifts.append(float(visual.get("face_center_drift", 0.04) or 0.04))

    base_persona = default_persona()
    fallback_speech = dict((existing or {}).get("speech_profile") or base_persona["speech_profile"])
    hooks = [value for value, _ in hook_counter.most_common(6)] or base_persona["hook_candidates"]
    ctas = [value for value, _ in cta_counter.most_common(6)] or base_persona["cta_candidates"]
    terms = [value for value, _ in term_counter.most_common(12)] or base_persona["signature_terms"]

    speaking_pace = round(
        (sum(speaking_paces) / len(speaking_paces)) if speaking_paces else float(fallback_speech.get("speaking_pace_cps", 3.8)),
        2,
    )
    question_ratio = round(
        (sum(question_ratios) / len(question_ratios)) if question_ratios else float(fallback_speech.get("question_ratio", 0.1)),
        2,
    )
    exclamation_ratio = round(
        (sum(exclamation_ratios) / len(exclamation_ratios)) if exclamation_ratios else float(fallback_speech.get("exclamation_ratio", 0.1)),
        2,
    )
    pause_density = round(
        (sum(pause_densities) / len(pause_densities)) if pause_densities else float(fallback_speech.get("comma_pause_density", 5.0)),
        2,
    )
    short_sentence_ratio = round(
        (sum(short_sentence_ratios) / len(short_sentence_ratios)) if short_sentence_ratios else float(fallback_speech.get("short_sentence_ratio", 0.5)),
        2,
    )
    face_ratio = round(sum(face_ratios) / max(len(face_ratios), 1), 3)
    brightness = round(sum(brightness_scores) / max(len(brightness_scores), 1), 2)
    motion = round(sum(motion_scores) / max(len(motion_scores), 1), 2)
    face_center_drift = round(sum(face_center_drifts) / max(len(face_center_drifts), 1), 3)

    persona = {
        "id": (existing or {}).get("id", "persona_default"),
        "name": preferred_name or (existing or {}).get("name", "我的数字分身"),
        "created_at": (existing or {}).get("created_at", now_iso()),
        "updated_at": now_iso(),
        "sample_count": len(analyses),
        "source_analysis_ids": [item for item in analysis_ids if item],
        "speech_profile": {
            "recommended_chars_60s": int(
                round(
                    (sum(chars_60s_values) / len(chars_60s_values))
                    if chars_60s_values
                    else float(fallback_speech.get("recommended_chars_60s", 220))
                )
            ),
            "avg_sentence_len": round(
                (sum(sentence_lengths) / len(sentence_lengths))
                if sentence_lengths
                else float(fallback_speech.get("avg_sentence_len", 22.0)),
                2,
            ),
            "speaking_pace_cps": speaking_pace,
            "question_ratio": question_ratio,
            "exclamation_ratio": exclamation_ratio,
            "comma_pause_density": pause_density,
            "short_sentence_ratio": short_sentence_ratio,
            "rhythm_style": "punchy" if short_sentence_ratio >= 0.55 else "balanced" if short_sentence_ratio >= 0.3 else "narrative",
            "cta_style": "direct" if len(ctas) > 0 else "soft",
            "hook_candidates": hooks,
            "cta_candidates": ctas,
            "signature_terms": terms,
        },
        "visual_profile": {
            "camera_distance": _camera_distance(face_ratio),
            "lighting_style": _lighting_style(brightness),
            "camera_movement_style": "stable" if motion <= 10 and face_center_drift <= 0.06 else "dynamic",
            "face_center_bias": "centered" if face_center_drift <= 0.05 else "loose",
            "motion_score": motion,
            "brightness_score": brightness,
            "face_ratio": face_ratio,
            "face_center_drift": face_center_drift,
        },
        "emotion_profile": {
            "expression_energy": _expression_energy(motion, speaking_pace),
            "delivery_temperature": "empathetic" if speaking_pace < 3.5 else "clear_practical",
            "pause_style": "short_bursts" if pause_density <= 5.0 and short_sentence_ratio >= 0.5 else "layered",
            "emphasis_style": "question_led" if question_ratio >= 0.25 else "assertive" if exclamation_ratio >= 0.25 else "measured",
        },
        "human_profile": {
            "personality_traits": _personality_traits(
                speaking_pace,
                question_ratio,
                exclamation_ratio,
                short_sentence_ratio,
            ),
            "behavior_traits": _behavior_traits(
                motion,
                face_center_drift,
                short_sentence_ratio,
                pause_density,
            ),
            "communication_traits": _communication_traits(
                "punchy" if short_sentence_ratio >= 0.55 else "balanced" if short_sentence_ratio >= 0.3 else "narrative",
                "direct" if len(ctas) > 0 else "soft",
                question_ratio,
                short_sentence_ratio,
            ),
            "emotion_traits": _emotion_traits(
                _expression_energy(motion, speaking_pace),
                "empathetic" if speaking_pace < 3.5 else "clear_practical",
                "question_led" if question_ratio >= 0.25 else "assertive" if exclamation_ratio >= 0.25 else "measured",
            ),
            "expression_traits": _expression_traits(
                _camera_distance(face_ratio),
                "stable" if motion <= 10 and face_center_drift <= 0.06 else "dynamic",
                "centered" if face_center_drift <= 0.05 else "loose",
                _lighting_style(brightness),
            ),
            "voice_traits": _voice_traits(
                speaking_pace,
                "short_bursts" if pause_density <= 5.0 and short_sentence_ratio >= 0.5 else "layered",
                question_ratio,
                exclamation_ratio,
            ),
        },
        "content_modes": (existing or {}).get("content_modes", DEFAULT_CONTENT_MODES),
    }
    persona["hook_candidates"] = hooks
    persona["cta_candidates"] = ctas
    persona["signature_terms"] = terms
    persona["recommended_chars_60s"] = persona["speech_profile"]["recommended_chars_60s"]
    persona["generation_profile"] = _generation_profile(persona["speech_profile"], persona["human_profile"])
    persona["prompt_block"] = _build_prompt_block(persona)
    return persona
