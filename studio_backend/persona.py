from __future__ import annotations

from collections import Counter
from typing import Any

from .storage import now_iso


# 默认内容模式定义
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
    """
    构建人设的提示词块，用于指导AI生成符合人设的内容
    
    Args:
        persona: 完整的人设字典
    
    Returns:
        格式化的提示词字符串，包含说话风格、视觉风格、表情能量等参数
    """
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
    """
    根据人脸占比判断相机距离
    
    Args:
        face_ratio: 人脸区域占画面总面积的比例
    
    Returns:
        相机距离类型: "close_up" / "medium_close" / "medium"
    """
    if face_ratio >= 0.18:
        return "close_up"
    if face_ratio >= 0.08:
        return "medium_close"
    return "medium"


def _lighting_style(brightness: float) -> str:
    """
    根据画面亮度判断光照风格
    
    Args:
        brightness: 画面平均亮度值 (0-255)
    
    Returns:
        光照风格: "bright_clean" / "balanced_soft" / "low_key"
    """
    if brightness >= 160:
        return "bright_clean"
    if brightness >= 105:
        return "balanced_soft"
    return "low_key"


def _expression_energy(motion: float, speaking_pace: float) -> str:
    """
    根据动作幅度和语速判断表情能量
    
    Args:
        motion: 动作分数
        speaking_pace: 语速 (字符/秒)
    
    Returns:
        表情能量等级: "intense" / "balanced" / "calm"
    """
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
    """
    根据语言特征提取人格特质
    
    Args:
        speaking_pace: 语速 (字符/秒)
        question_ratio: 问句比例
        exclamation_ratio: 感叹句比例
        short_sentence_ratio: 短句比例
    
    Returns:
        人格特质列表
    """
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
    """
    根据行为特征提取行为特质
    
    Args:
        motion: 动作分数
        face_center_drift: 人脸中心漂移度
        short_sentence_ratio: 短句比例
        pause_density: 停顿密度
    
    Returns:
        行为特质列表
    """
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
    """
    根据沟通特征提取沟通特质
    
    Args:
        rhythm_style: 节奏风格
        cta_style: 行动号召风格
        question_ratio: 问句比例
        short_sentence_ratio: 短句比例
    
    Returns:
        沟通特质列表
    """
    traits = ["hook_first", rhythm_style]
    traits.append("cta_close" if cta_style == "direct" else "soft_close")
    if question_ratio >= 0.18:
        traits.append("dialogue_style")
    if short_sentence_ratio >= 0.45:
        traits.append("short_sentences")
    return traits


def _emotion_traits(expression_energy: str, delivery_temperature: str, emphasis_style: str) -> list[str]:
    """
    提取情感特质
    
    Args:
        expression_energy: 表情能量
        delivery_temperature: 传递温度
        emphasis_style: 强调风格
    
    Returns:
        情感特质列表
    """
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
    """
    提取表达特质
    
    Args:
        camera_distance: 相机距离
        camera_movement_style: 相机运动风格
        face_center_bias: 人脸中心偏差
        lighting_style: 光照风格
    
    Returns:
        表达特质列表
    """
    return [camera_distance, camera_movement_style, face_center_bias, lighting_style]


def _voice_traits(
    speaking_pace: float,
    pause_style: str,
    question_ratio: float,
    exclamation_ratio: float,
) -> list[str]:
    """
    提取声音特质
    
    Args:
        speaking_pace: 语速 (字符/秒)
        pause_style: 停顿风格
        question_ratio: 问句比例
        exclamation_ratio: 感叹句比例
    
    Returns:
        声音特质列表
    """
    pace_code = "fast_voice" if speaking_pace >= 4.6 else "balanced_voice" if speaking_pace >= 3.6 else "calm_voice"
    tone_code = "assertive_tone" if exclamation_ratio >= 0.18 else "conversational_tone" if question_ratio >= 0.18 else "steady_tone"
    return [pace_code, pause_style, tone_code]


def _generation_profile(speech_profile: dict[str, Any], human_profile: dict[str, Any]) -> dict[str, Any]:
    """
    构建生成配置文件，指导内容生成
    
    Args:
        speech_profile: 语音配置
        human_profile: 人物配置
    
    Returns:
        生成配置字典，包含支持的输入类型、脚本流程、声音锚点等
    """
    return {
        "supported_inputs": ["topic", "title", "keywords", "story_memo", "custom_script"],
        "script_flow": ["hook_first", "point_then_method", "cta_close"],
        "voice_anchor": human_profile.get("voice_traits", []),
        "expression_anchor": human_profile.get("expression_traits", []),
        "recommended_chars_60s": speech_profile.get("recommended_chars_60s", 220),
    }


def default_persona(name: str = "我的数字分身") -> dict[str, Any]:
    """
    创建默认人设
    
    Args:
        name: 人设名称，默认"我的数字分身"
    
    Returns:
        完整的默认人设字典，包含语音、视觉、情感、人物配置等
    
    该函数生成一个平衡风格的默认人设，适合大多数内容创作场景。
    """
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
    # 扁平化字段，便于外部访问
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
    """
    从分析记录中蒸馏人设（核心函数）
    
    Args:
        analyses: 媒体分析记录列表，包含语音指标和视觉指标
        existing: 现有的人设数据（可选），用于保留用户自定义的部分配置
        preferred_name: 首选的人设名称（可选）
    
    Returns:
        蒸馏后的完整人设字典
    
    该函数是人设系统的核心，通过分析上传的参考视频/图片，自动提取：
    - 语音特征（语速、句式、停顿风格等）
    - 视觉特征（人脸比例、亮度、运动幅度等）
    - 情感特征（表情能量、传递温度等）
    - 人物特质（人格、行为、沟通风格等）
    
    如果没有分析数据，返回默认人设。
    """
    if not analyses:
        return default_persona(preferred_name or (existing or {}).get("name", "我的数字分身"))

    # 初始化计数器和统计列表
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

    # 遍历所有分析记录，收集数据
    for analysis in analyses:
        analysis_ids.append(str(analysis.get("id", "")))
        speech = analysis.get("speech_metrics", {})
        visual = analysis.get("visual_metrics", {})

        has_speech_sample = float(speech.get("char_count", 0) or 0.0) > 0
        if has_speech_sample:
            # 收集钩子和CTA候选
            hook = str(speech.get("hook_candidate", "")).strip()
            cta = str(speech.get("cta_candidate", "")).strip()
            if hook:
                hook_counter[hook] += 1
            if cta:
                cta_counter[cta] += 1

            # 收集关键词
            for term in speech.get("keywords", []) or []:
                cleaned = str(term).strip()
                if cleaned:
                    term_counter[cleaned] += 1

            # 收集语音指标
            chars_60s_values.append(int(speech.get("recommended_chars_60s", 220) or 220))
            sentence_lengths.append(float(speech.get("avg_sentence_len", 22.0) or 22.0))
            speaking_paces.append(float(speech.get("speaking_pace_cps", 3.8) or 3.8))
            question_ratios.append(float(speech.get("question_ratio", 0.1) or 0.1))
            exclamation_ratios.append(float(speech.get("exclamation_ratio", 0.1) or 0.1))
            pause_densities.append(float(speech.get("comma_pause_density", 5.0) or 5.0))
            short_sentence_ratios.append(float(speech.get("short_sentence_ratio", 0.5) or 0.5))
        
        # 收集视觉指标（无论是否有语音样本）
        face_ratios.append(float(visual.get("face_ratio", 0.12) or 0.12))
        brightness_scores.append(float(visual.get("brightness_score", 120.0) or 120.0))
        motion_scores.append(float(visual.get("motion_score", 8.0) or 8.0))
        face_center_drifts.append(float(visual.get("face_center_drift", 0.04) or 0.04))

    # 计算平均值和构建人设
    base_persona = default_persona()
    fallback_speech = dict((existing or {}).get("speech_profile") or base_persona["speech_profile"])
    
    # 获取最常见的钩子、CTA和关键词
    hooks = [value for value, _ in hook_counter.most_common(6)] or base_persona["hook_candidates"]
    ctas = [value for value, _ in cta_counter.most_common(6)] or base_persona["cta_candidates"]
    terms = [value for value, _ in term_counter.most_common(12)] or base_persona["signature_terms"]

    # 计算平均语音指标
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
    
    # 计算平均视觉指标
    face_ratio = round(sum(face_ratios) / max(len(face_ratios), 1), 3)
    brightness = round(sum(brightness_scores) / max(len(brightness_scores), 1), 2)
    motion = round(sum(motion_scores) / max(len(motion_scores), 1), 2)
    face_center_drift = round(sum(face_center_drifts) / max(len(face_center_drifts), 1), 3)

    # 构建完整人设
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
    
    # 添加扁平化字段和生成配置
    persona["hook_candidates"] = hooks
    persona["cta_candidates"] = ctas
    persona["signature_terms"] = terms
    persona["recommended_chars_60s"] = persona["speech_profile"]["recommended_chars_60s"]
    persona["generation_profile"] = _generation_profile(persona["speech_profile"], persona["human_profile"])
    persona["prompt_block"] = _build_prompt_block(persona)
    return persona
