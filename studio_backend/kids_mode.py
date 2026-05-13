from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .storage import STUDIO_DIR, make_id


CARTOON_ROOT = STUDIO_DIR / "cartoon_mode"
CARTOON_UPLOADS_DIR = CARTOON_ROOT / "uploads"

KIDS_ANIMATION_HARD_RULES = [
    "固定双角色：拟人化毛豆与拟人化花生共同出镜，允许短暂表情特写，但必须快速回到双人互动。",
    "保持同一明亮 3D 卡通世界观：允许在公园、花园、菜园、小舞台等区块自然转场，禁止突兀跳变。",
    "镜头语言必须连续叙事：远景、中景、跟拍、表情特写、双人反应镜头自然切换。",
    "全程逐帧原生动画，不允许静态图片平移、漂浮或慢推拉替代动作。",
    "人物表情细腻多变：开心、惊讶、思考、委屈、鼓励、搞笑反应持续更新。",
    "肢体动作连贯：走、跑、挥手、互动、停顿、回头、靠近镜头，节奏自然。",
    "剧情完整起承转合，段落之间必须有因果与互动，不重复台词结构。",
    "光影、材质和色彩必须鲜明，角色呈现圆润立体、柔和高光和卡通 PBR 质感。",
    "角色风格参考可爱 3D 角色海报质感：大眼睛高光、张嘴微笑、腮红、运动鞋、柔和棚拍绿色背景。",
    "毛豆必须呈现打开的绿色豆荚和饱满豆豆；花生必须呈现暖黄色花生壳格纹与颗粒凹凸。",
    "画面稳定清晰：禁止闪烁、重复叠图、角色消失、乱码问号和模糊抖动。",
    "风格参考经典夸张喜剧卡通节奏（如追逐喜剧感），但不复刻任何现有IP角色。",
    "限制额外角色和杂乱道具，主叙事始终围绕毛豆与花生展开。",
    "文案使用第一人称自然表达，不写“毛豆说”“花生说”等说话标签；镜头聚焦谁，谁自然开口。",
    "可以适度使用第二人称互动，让孩子感觉角色正在带着“你”一起看、数、找、想。",
]

KIDS_CHARACTER_DESIGN = {
    "maodou": (
        "match the provided reference character as closely as possible: cute anthropomorphic open edamame pod, "
        "glossy bright green shell, visible fuzzy pod edge, two large plump beans inside the pod, "
        "oversized sparkling brown eyes with multiple white highlights, curved eyebrows, rosy cheeks, "
        "wide happy open smile with tongue and teeth, human-like arms, peace-sign hand, green sneakers, "
        "soft premium 3D toy-poster lighting"
    ),
    "peanut": (
        "match the provided reference character as closely as possible: cute anthropomorphic peanut, "
        "warm golden peanut-shell body with clear waffle-like shell grid, tiny freckles and rounded bumps, "
        "oversized sparkling brown eyes with multiple white highlights, curved eyebrows, rosy cheeks, "
        "wide happy open smile with tongue and teeth, human-like arms, thumbs-up hand, orange sneakers, "
        "soft premium 3D toy-poster lighting"
    ),
}

REFERENCE_STYLE_CONTRACT = {
    "fidelity_target": "reference_locked",
    "local_renderer_limit": (
        "OpenCV native renderer is a low-fidelity preview/fallback. "
        "One-to-one template-level character matching requires a reference-image-capable image/video generation model."
    ),
    "image_prompt": (
        "Use the provided reference image as the locked character sheet. Recreate the same two cute 3D characters: "
        "an open green edamame pod with two large glossy beans, big sparkling brown eyes, blush cheeks, open happy mouth, "
        "peace-sign hand and green sneakers; and a golden peanut with waffle shell texture, freckles, big sparkling brown eyes, "
        "blush cheeks, open happy mouth, thumbs-up hand and orange sneakers. Keep proportions, expressions, materials, "
        "shoe style, face placement, and soft green studio background as close to the reference as possible. "
        "Premium 3D toy-poster quality, saturated colors, soft rim light, glossy PBR material, child-friendly, no extra characters."
    ),
    "video_prompt": (
        "Use the provided reference image as the locked character identity for every frame. Maintain the same edamame and peanut "
        "proportions, faces, shoes, hand shapes, shell textures, glossy materials, big eyes, blush, and soft green studio lighting. "
        "Animate them with gentle preschool-friendly body motion, expressive close-ups, natural mouth movement, and stable camera moves. "
        "Do not redesign the characters between shots; preserve identity consistency across the whole video."
    ),
}

SHOT_ROTATION = [
    "wide_duo_establishing",
    "medium_duo_dialog",
    "face_closeup_maodou",
    "tracking_duo_motion",
    "face_closeup_peanut",
    "medium_duo_reaction",
    "wide_duo_action",
    "tracking_duo_follow",
]

SCENE_ROTATION = [
    ("park_lane", "soft green studio garden backdrop with warm spotlight and gentle floor shadow"),
    ("flower_garden", "soft green studio garden backdrop with colorful low flowers and blurred leaves"),
    ("farm_patch", "soft green studio farm backdrop with small sprouts and warm child-friendly props"),
    ("mini_stage", "soft green studio stage backdrop with tiny bunting and warm toy-poster lighting"),
]

ACTION_ROTATION = [
    "walk_and_wave",
    "point_and_explain",
    "thinking_closeup",
    "run_and_laugh",
    "surprise_react",
    "encourage_closeup",
    "hug",
    "jump_playful",
]

CONTENT_PROFILES = {
    "science": {
        "label": "科普动画",
        "goal": "认识一个自然现象或生活小知识",
        "steps": ["看一看", "想一想", "试一试", "说一说"],
        "visuals": ["放大观察", "简单对比", "动作演示", "结果回顾"],
    },
    "early_learning": {
        "label": "益智早教",
        "goal": "练习观察、分类、数数、颜色、形状或生活习惯",
        "steps": ["找一找", "数一数", "比一比", "做一做"],
        "visuals": ["颜色提示", "形状提示", "节奏重复", "鼓励反馈"],
    },
}

SCENE_DIRECTIVE_PREFIXES = (
    "场景",
    "画面",
    "镜头",
    "动作",
    "表情",
    "情绪",
    "音乐",
    "音效",
    "旁白",
    "字幕",
    "转场",
    "分镜",
)

SPEAKER_LABEL_PATTERN = re.compile(
    r"^\s*(?:"
    r"毛豆|花生|合|二人|两人|大家|旁白|镜头|画面|场景|动作|表情|字幕|音效"
    r")\s*(?:说|问|喊|答|唱|念|带你|提示|旁白)?\s*[:：，,、\\-—]*\s*",
    re.IGNORECASE,
)

INLINE_SPEAKER_LABEL_PATTERN = re.compile(
    r"(^|[。！？!?；;，,\s])(?:毛豆|花生|合|二人|两人|大家|旁白)\s*(?:说|问|喊|答|唱|念|带你|提示|旁白)?\s*[:：]\s*",
    re.IGNORECASE,
)

AGE_RULES_3_TO_6 = [
    "每句尽量 8-18 个汉字，避免长从句。",
    "只讲 1 个核心知识点，最多 3 个小步骤。",
    "用具体可见的东西解释，避免抽象说教。",
    "每 10-15 秒设计一次提问、寻找、数数或模仿动作。",
    "结尾必须复述关键知识，并给孩子正向鼓励。",
]

KIDS_VOICE_PRESETS = {
    "soft_child_cn": {
        "label": "自然软萌中文童声",
        "edge_voice": "zh-CN-XiaoyiNeural",
        "edge_rate": "+3%",
        "edge_volume": "+2%",
    },
    "bright_child_cn": {
        "label": "自然活泼男孩声",
        "edge_voice": "zh-CN-YunxiNeural",
        "edge_rate": "+4%",
        "edge_volume": "+2%",
    },
    "warm_sister_cn": {
        "label": "自然温柔姐姐声",
        "edge_voice": "zh-CN-XiaoxiaoNeural",
        "edge_rate": "+2%",
        "edge_volume": "+1%",
    },
}

UNSAFE_OR_OFF_TARGET_TERMS = [
    "恐怖",
    "吓人",
    "血",
    "暴力",
    "惩罚",
    "焦虑",
    "赚钱",
    "投资",
    "成人",
]


def ensure_cartoon_dirs() -> None:
    CARTOON_ROOT.mkdir(parents=True, exist_ok=True)
    CARTOON_UPLOADS_DIR.mkdir(parents=True, exist_ok=True)


def clamp_kids_seconds(seconds: int) -> int:
    return max(30, min(60, int(seconds or 45)))


def sanitize_hint(text: str, *, limit: int = 160) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    return value[:limit]


def normalize_content_mode(value: str) -> str:
    mode = str(value or "").strip().lower()
    if mode in {"early", "early_learning", "education", "益智早教", "早教"}:
        return "early_learning"
    return "science"


def normalize_video_provider(value: str) -> str:
    provider = str(value or "").strip().lower()
    if provider in {"kling", "dashscope_kling", "aliyun_kling", "可灵"}:
        return "kling"
    if provider in {"zhipu", "zhipu_qingying", "qingying", "bigmodel", "cogvideox", "智谱", "清影", "智谱清影"}:
        return "zhipu_qingying"
    return "local_preview"


def _clean_child_topic(topic: str) -> str:
    text = sanitize_hint(topic, limit=18) or "有趣的小知识"
    for term in UNSAFE_OR_OFF_TARGET_TERMS:
        text = text.replace(term, "")
    return text.strip(" ，。！？") or "有趣的小知识"


def _short_child_phrase(text: str, fallback: str, *, limit: int = 12) -> str:
    phrase = sanitize_hint(text, limit=limit).strip(" ，。！？")
    for term in UNSAFE_OR_OFF_TARGET_TERMS:
        phrase = phrase.replace(term, "")
    return phrase.strip(" ，。！？") or fallback


def _profile_for(content_mode: str) -> dict[str, Any]:
    return CONTENT_PROFILES.get(normalize_content_mode(content_mode), CONTENT_PROFILES["science"])


def _arc_lines(
    topic: str,
    hint: str,
    *,
    content_mode: str = "science",
    learning_goal: str = "",
) -> list[str]:
    safe_topic = sanitize_hint(topic, limit=18) or "开心的一天"
    safe_topic = _clean_child_topic(safe_topic)
    profile = _profile_for(content_mode)
    goal = _short_child_phrase(learning_goal, profile["goal"], limit=22)
    hint_text = _short_child_phrase(hint, "", limit=22)
    step_a, step_b, step_c, step_d = profile["steps"]

    if normalize_content_mode(content_mode) == "early_learning":
        hint_line = f"我先{step_a}，你也试一试。"
        if hint_text:
            hint_line = f"我的小提示：{hint_text}。"
        return [
            f"我们一起玩《{safe_topic}》。",
            f"我看到小线索啦。",
            f"我们来练习{goal}。",
            hint_line,
            f"我来{step_b}：一、二、三。",
            f"我们再{step_c}，找不同。",
            f"最后复习：我学会了，你真棒！",
        ]

    hint_line = f"我的小提示：{hint_text}。" if hint_text else f"我先{step_a}，再{step_b}。"
    return [
        f"我们今天认识《{safe_topic}》。",
        f"我想知道：为什么会这样？",
        f"我们只学一个小知识。",
        f"我的重点：{goal}。",
        hint_line,
        f"我们一起{step_a}颜色和形状。",
        f"我再{step_b}，答案更清楚。",
        f"最后复习：我先观察，再思考，真棒！",
    ]


def _trim_preserving_review(lines: list[str], keep_count: int) -> list[str]:
    if keep_count >= len(lines):
        return lines
    if keep_count <= 1:
        return lines[-1:]
    return lines[: keep_count - 1] + [lines[-1]]


def normalize_kids_script_text(script_text: str) -> str:
    lines: list[str] = []
    for raw_line in str(script_text or "").splitlines():
        line = raw_line.strip()
        if not line:
            continue
        previous = None
        while previous != line:
            previous = line
            line = SPEAKER_LABEL_PATTERN.sub("", line)
        line = INLINE_SPEAKER_LABEL_PATTERN.sub(lambda match: match.group(1), line)
        line = _strip_visual_directives(line)
        line = re.sub(r"^(?:我i|我I)", "我", line)
        line = re.sub(r"[，,、]{2,}", "，", line)
        line = re.sub(r"[。！？!?]{2,}", lambda match: match.group(0)[0], line)
        line = re.sub(r"\s+", " ", line).strip().strip(" ，,、")
        if line:
            lines.append(line)
    return "\n".join(lines)


def _is_visual_directive(text: str) -> bool:
    cleaned = str(text or "").strip()
    if not cleaned:
        return False
    return cleaned.startswith(SCENE_DIRECTIVE_PREFIXES) or bool(
        re.match(r"^(?:春日|夏日|秋日|冬日|清晨|傍晚|夜晚|室内|室外|特写|远景|中景|近景|全景|慢慢|快速|静坐|走来|微风|阳光|草地|花园)", cleaned)
    )


def _strip_visual_directives(line: str) -> str:
    cleaned = str(line or "").strip()
    if _is_visual_directive(cleaned):
        return ""
    # Remove bracketed stage directions such as "（场景：春日草地...）" from narration.
    cleaned = re.sub(
        r"[（(【\[]\s*(?:场景|画面|镜头|动作|表情|情绪|音乐|音效|字幕|转场|分镜)\s*[:：][^）)】\]]*[）)】\]]",
        "",
        cleaned,
    )
    # If a line starts with a visual directive followed by narration, keep only the narration side.
    cleaned = re.sub(
        r"^\s*(?:场景|画面|镜头|动作|表情|情绪|音乐|音效|字幕|转场|分镜)\s*[:：][^。！？!?]*[。！？!?]?\s*",
        "",
        cleaned,
    )
    return cleaned.strip()


def _scene_from_line(line: str, *, fallback_index: int) -> tuple[str, str, str]:
    text = str(line or "")
    if any(token in text for token in ("复习", "学会", "真棒", "记住", "最后")):
        return (
            "celebration_stage",
            "a tiny 3D celebration stage in a green studio garden, warm spotlights, simple confetti shapes, happy preschool ending",
            "结果回顾",
        )
    if any(token in text for token in ("水", "喝水", "浇水", "雨", "水滴", "湿")) and any(
        token in text for token in ("太阳", "阳光", "光", "暖", "晒")
    ):
        return (
            "sprout_needs_demo",
            "a bright 3D preschool garden patch where a tiny sprout is shown with sparkling water drops and warm sunbeams, clean and magical but realistic for children",
            "简单对比",
        )
    if any(token in text for token in ("种子", "发芽", "小芽", "泥土", "土里", "叶子", "根")):
        return (
            "sprout_garden",
            "a bright 3D preschool garden patch with soft soil, tiny sprouts, dew drops, colorful labels without readable text, warm toy-poster lighting",
            "放大观察",
        )
    if any(token in text for token in ("水", "喝水", "浇水", "雨", "水滴", "湿")):
        return (
            "water_drop_demo",
            "a clean 3D science table in a green garden studio, sparkling water drops, a tiny watering can, safe rounded props, no readable text",
            "动作演示",
        )
    if any(token in text for token in ("太阳", "阳光", "光", "暖", "晒")):
        return (
            "sunlight_corner",
            "a warm sunny corner of a colorful 3D garden studio, golden sunbeams, soft shadows, bright cheerful preschool atmosphere",
            "简单对比",
        )
    if any(token in text for token in ("数", "一、二、三", "几个", "多少")):
        return (
            "counting_play_mat",
            "a colorful 3D early-learning play mat with three large rounded objects for counting, clean background, no readable text",
            "节奏重复",
        )
    if any(token in text for token in ("颜色", "红", "黄", "蓝", "绿", "形状", "圆", "方")):
        return (
            "color_shape_corner",
            "a bright 3D preschool color-and-shape corner with rounded blocks, vivid colors, simple uncluttered props, no readable text",
            "颜色提示",
        )
    if any(token in text for token in ("找", "哪里", "看一看", "观察", "发现", "线索")):
        return (
            "discovery_garden",
            "a playful 3D discovery garden scene with magnifying-glass-like framing, tiny child-friendly clues, saturated colors, soft green background",
            "放大观察",
        )
    key, prompt = SCENE_ROTATION[fallback_index % len(SCENE_ROTATION)]
    return key, prompt, "动作演示"


def _kids_voice_settings(edge_voice: str) -> dict[str, str]:
    requested = str(edge_voice or "").strip()
    if requested:
        for preset in KIDS_VOICE_PRESETS.values():
            if requested == preset["edge_voice"]:
                return dict(preset)
        custom = dict(KIDS_VOICE_PRESETS["soft_child_cn"])
        custom["label"] = "自定义中文童声"
        custom["edge_voice"] = requested
        return custom
    return dict(KIDS_VOICE_PRESETS["soft_child_cn"])


def _expand_lines_for_duration(lines: list[str], target_seconds: int, *, content_mode: str, learning_goal: str) -> list[str]:
    profile = _profile_for(content_mode)
    goal = _short_child_phrase(learning_goal, profile["goal"], limit=22)
    extras = [
        "我把眼睛睁大，仔细看一看。",
        "你也来找一找，线索藏在哪里？",
        "我数一数：一、二、三。",
        f"这个小知识，和{goal}有关。",
        "我靠近一点，给你看清楚。",
        "我做一个小动作，你跟我学一学。",
        "我发现啦，原来答案很简单。",
        "我们慢慢来，不着急。",
        "我再试一次，看看会不会一样。",
        "你做得很好，我们继续往下看。",
    ]
    target_line_count = 6 if target_seconds <= 35 else 9 if target_seconds <= 45 else 12
    result = list(lines)
    insert_at = max(1, len(result) - 1)
    for extra in extras:
        if len(result) >= target_line_count:
            break
        result.insert(insert_at, extra)
        insert_at += 1
    return result


def build_kids_english_script(
    topic: str,
    seconds: int,
    prompt_hint: str = "",
    content_mode: str = "science",
    learning_goal: str = "",
) -> str:
    # Backward-compatible function name kept to avoid changing existing API callers.
    target_seconds = clamp_kids_seconds(seconds)
    hint = sanitize_hint(prompt_hint, limit=48)
    lines = _arc_lines(topic, hint, content_mode=content_mode, learning_goal=learning_goal)
    lines = _expand_lines_for_duration(
        lines,
        target_seconds,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    if target_seconds <= 35:
        lines = _trim_preserving_review(lines, 6)
    elif target_seconds <= 45:
        lines = _trim_preserving_review(lines, 9)
    elif target_seconds <= 55:
        lines = _trim_preserving_review(lines, 11)
    return "\n".join(lines)


def analyze_kids_script_quality(
    script_text: str,
    *,
    content_mode: str = "science",
    learning_goal: str = "",
) -> dict[str, Any]:
    normalized_script = normalize_kids_script_text(script_text)
    lines = [line.strip() for line in normalized_script.splitlines() if line.strip()]
    compact = re.sub(r"\s+", "", normalized_script)
    profile = _profile_for(content_mode)
    interactions = sum(1 for line in lines if any(token in line for token in ("你", "找", "数", "看", "想", "试", "说")))
    long_lines = [line for line in lines if len(re.sub(r"\s+", "", line)) > 28]
    off_target = [term for term in UNSAFE_OR_OFF_TARGET_TERMS if term in compact]
    has_review = any(token in compact for token in ("复习", "学会", "记住", "真棒", "小知识"))
    has_goal = bool(sanitize_hint(learning_goal, limit=40)) or any(token in compact for token in ("认识", "练习", "观察", "数", "颜色", "形状"))
    has_first_person = any(token in compact for token in ("我", "我们"))
    has_speaker_label = bool(re.search(r"(毛豆|花生)\s*(说|问|喊|带你|举牌|靠近)", compact))
    issues: list[str] = []
    if len(lines) < 5:
        issues.append("文案段落偏少，建议至少 5 段形成开场、提问、演示、互动、复习。")
    if long_lines:
        issues.append("存在偏长句，3-6 岁内容建议拆短。")
    if interactions < 2:
        issues.append("互动点不足，建议加入找一找、数一数、想一想或跟着做。")
    if not has_review:
        issues.append("缺少结尾复习和正向鼓励。")
    if not has_goal:
        issues.append(f"学习目标不够明确，当前模式应聚焦：{profile['goal']}。")
    if not has_first_person:
        issues.append("文案应使用第一人称，让角色自然带孩子一起学习。")
    if has_speaker_label:
        issues.append("文案不需要“毛豆说/花生说”等说话标签，镜头聚焦时自然开口即可。")
    if off_target:
        issues.append(f"包含不适合 3-6 岁的词：{', '.join(off_target)}。")
    return {
        "age_band": "3-6",
        "content_mode": normalize_content_mode(content_mode),
        "profile_label": profile["label"],
        "line_count": len(lines),
        "char_count": len(compact),
        "interaction_count": interactions,
        "long_line_count": len(long_lines),
        "age_rules": list(AGE_RULES_3_TO_6),
        "issues": issues,
        "passed": not issues,
    }


def _line_action_hint(line: str) -> str:
    text = line.lower()
    if any(token in text for token in ("特写", "靠近镜头", "看向镜头", "大眼睛")):
        return "encourage_closeup"
    if any(token in text for token in ("跑", "追", "run", "chase")):
        return "run_and_laugh"
    if any(token in text for token in ("想", "不知道", "思考", "remember")):
        return "thinking_closeup"
    if any(token in text for token in ("跳", "jump")):
        return "jump_playful"
    if any(token in text for token in ("抱", "hug")):
        return "hug"
    if any(token in text for token in ("笑", "laugh", "哈哈")):
        return "laughing_talk"
    if any(token in text for token in ("惊", "哇", "surprise")):
        return "surprise_react"
    if any(token in text for token in ("挥手", "wave")):
        return "walk_and_wave"
    return "point_and_explain"


def build_kids_storyboard(
    script_text: str,
    seconds: int,
    *,
    content_mode: str = "science",
    learning_goal: str = "",
) -> list[dict[str, Any]]:
    target_seconds = clamp_kids_seconds(seconds)
    normalized_script = normalize_kids_script_text(script_text)
    lines = [item.strip() for item in normalized_script.splitlines() if item.strip()]
    if not lines:
        lines = _arc_lines("有趣的小知识", "", content_mode=content_mode, learning_goal=learning_goal)
    segment_count = min(max(len(lines), 1), 10)
    slot = max(target_seconds / float(segment_count), 3.2)

    storyboard: list[dict[str, Any]] = []
    cursor = 0.0
    for index in range(segment_count):
        sentence = lines[index % len(lines)]
        action = _line_action_hint(sentence) or ACTION_ROTATION[index % len(ACTION_ROTATION)]
        shot = SHOT_ROTATION[index % len(SHOT_ROTATION)]
        if "closeup" in action:
            shot = "face_closeup_maodou" if index % 2 == 0 else "face_closeup_peanut"
        speaker = "maodou" if index % 2 == 0 else "peanut"
        arc = "setup" if index <= 1 else "build" if index <= 4 else "twist" if index <= 6 else "resolve"
        scene_key, scene_prompt, interpreted_visual = _scene_from_line(sentence, fallback_index=index)
        profile = _profile_for(content_mode)
        learning_step = profile["steps"][index % len(profile["steps"])]
        visual_cue = interpreted_visual or profile["visuals"][index % len(profile["visuals"])]
        emotion = "curious"
        if "surprise" in action:
            emotion = "surprised"
        elif "laugh" in action:
            emotion = "happy"
        elif "thinking" in action:
            emotion = "thinking"
        elif "encourage" in action or "hug" in action:
            emotion = "encouraging"
        start = round(cursor, 3)
        end = round(min(target_seconds, start + slot), 3)
        storyboard.append(
            {
                "index": index + 1,
                "arc": arc,
                "start_s": start,
                "end_s": end,
                "duration_s": round(end - start, 3),
                "speaker": speaker,
                "scene_key": scene_key,
                "scene_prompt": scene_prompt,
                "learning_step": learning_step,
                "visual_cue": visual_cue,
                "shot_type": shot,
                "action_hint": action,
                "emotion": emotion,
                "line": sentence,
            }
        )
        cursor = end
        if cursor >= target_seconds:
            break

    if storyboard:
        storyboard[-1]["end_s"] = float(target_seconds)
        storyboard[-1]["duration_s"] = round(float(target_seconds) - float(storyboard[-1]["start_s"]), 3)
    return storyboard


def make_uploaded_image_path(suffix: str) -> Path:
    ensure_cartoon_dirs()
    ext = suffix.lower() if suffix else ".png"
    if ext not in {".png", ".jpg", ".jpeg", ".webp"}:
        ext = ".png"
    return CARTOON_UPLOADS_DIR / f"{make_id('cartoon_img')}{ext}"


def build_kids_generate_payload(
    *,
    topic: str,
    seconds: int,
    script_text: str,
    background_image_path: str,
    edge_voice: str,
    dynamic_background: bool,  # kept for backward compatibility; ignored by strict mode.
    content_mode: str = "science",
    learning_goal: str = "",
    reference_image_path: str = "",
    reference_image_url: str = "",
    video_provider: str = "zhipu_qingying",
) -> dict[str, Any]:
    safe_seconds = clamp_kids_seconds(seconds)
    normalized_script = normalize_kids_script_text(script_text)
    voice_preset = _kids_voice_settings(edge_voice)
    voice = voice_preset["edge_voice"]
    normalized_mode = normalize_content_mode(content_mode)
    quality = analyze_kids_script_quality(normalized_script, content_mode=normalized_mode, learning_goal=learning_goal)
    storyboard = build_kids_storyboard(
        normalized_script,
        safe_seconds,
        content_mode=normalized_mode,
        learning_goal=learning_goal,
    )
    return {
        "project_mode": "kids_cartoon",
        "topic": topic,
        "title": f"毛豆和花生：{topic}",
        "keywords": ["3-6岁", "少儿", "中文", "毛豆", "花生", "双角色", "3D动画", CONTENT_PROFILES[normalized_mode]["label"]],
        "character_design": dict(KIDS_CHARACTER_DESIGN),
        "reference_style_contract": dict(REFERENCE_STYLE_CONTRACT),
        "visual_fidelity_mode": "reference_locked_high_quality",
        "local_renderer_role": "preview_fallback_only",
        "story_memo": "",
        "custom_script": normalized_script,
        "content_type": "tutorial",
        "emotion_tone": "warm",
        "age_band": "3-6",
        "kids_content_mode": normalized_mode,
        "learning_goal": sanitize_hint(learning_goal, limit=48) or CONTENT_PROFILES[normalized_mode]["goal"],
        "script_quality": quality,
        "seconds": safe_seconds,
        "render_mode": "cartoon_native_3d",
        "tts_provider": "edge",
        "voice_clone_reference_path": "",
        "voice_clone_language": "zh-cn",
        "edge_voice": voice,
        "edge_rate": voice_preset["edge_rate"],
        "edge_volume": voice_preset["edge_volume"],
        "voice_preset": voice_preset["label"],
        "background_image": "",
        "reference_image": str(reference_image_path or background_image_path or "").strip(),
        "reference_image_url": str(reference_image_url or "").strip(),
        "character_reference_image": str(reference_image_path or background_image_path or "").strip(),
        "background_color": "#fde7b3",
        "subtitle_font": "Microsoft YaHei",
        "subtitle_size": 24,
        "subtitle_margin_v": 360,
        "avatar_command_template": "",
        "portrait_path": "",
        "ref_eyeblink": "",
        "ref_pose": "",
        "avatar_preprocess": "full",
        "avatar_enhancer": "",
        "avatar_background_enhancer": "",
        "avatar_still_mode": False,
        "avatar_pose_style": 14,
        "avatar_expression_scale": 1.35,
        "avatar_size": 256,
        "output_resolution": "1080p",
        "reference_style_tag": "",
        "reference_image_required": True,
        "avatar_use_cpu": False,
        "dynamic_background": False,
        "dynamic_style": "native_duo_cinematic_3d",
        "video_provider": normalize_video_provider(video_provider),
        "animation_style": "cartoon_3d_duo_cinematic",
        "single_protagonist": False,
        "single_scene_locked": False,
        "forbid_extra_characters": True,
        "forbid_clutter_props": True,
        "target_fps": 30,
        "optical_flow_temporal_align": True,
        "layered_clean_rendering": True,
        "native_frame_animation": True,
        "forbid_static_micro_motion": True,
        "force_bgm": True,
        "voice_character": "cute_child_cn",
        "animation_hard_rules": list(KIDS_ANIMATION_HARD_RULES),
        "animation_storyboard": storyboard,
        "notes": "kids_native_3d_duo_cinematic_no_default_background",
    }
