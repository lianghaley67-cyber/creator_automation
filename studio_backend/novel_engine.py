"""Book-scoped novel production engine for Novel OS.

The functions here are deterministic fallbacks. They make the SaaS workflow
usable even when no external LLM key is configured, while keeping every output
scoped by book_id so one novel never inherits another novel's memory.
"""
from __future__ import annotations

import re
from typing import Any, Callable

from .story_workflow import build_story_blueprint


SkillFn = Callable[[dict[str, Any]], dict[str, Any]]


DEFAULT_PIPELINE = [
    "market_analysis",
    "world_build",
    "character_design",
    "plot_design",
    "chapter_write",
    "style_optimize",
    "logic_check",
]


NOVEL_WORLD_SIMULATOR_CONTRACT = {
    "identity": "小说世界模拟器",
    "mission": "让当前世界在既定条件下真实发生，而不是解释剧情或输出写作建议。",
    "input_sections": ["World State", "Character State", "Chapter Mission", "Memory"],
    "output_rule": "只输出小说正文，不要JSON、标题说明、写作思路、结构提示或总结。",
    "must_do": [
        "从当前场景直接开始，第一段就出现异常、压力或必须回应的问题。",
        "所有信息通过动作、对话、物件、环境细节呈现。",
        "角色用选择和行动推动事件，每200-300字必须出现推进或变化。",
        "承接上一章的结果和代价，不复述上一章正文。",
        "每章按4-5个递进场景推进：后果出现、冲突升级、线索发现、主动选择、章末钩子。",
        "每一幕必须给出新信息，不能循环使用同一段动作、台词或线索。",
        "上一章回忆不得超过本章10%，只能用于揭示线索、动机或代价。",
        "每一段必须提供新信息、新变化或新冲突，避免无意义心理描写。",
        "玄学内容必须落到可观察物件、时间、方位、因果代价或风水逻辑上。",
        "结尾留下角色当下必须面对的具体悬念。",
        "语言保持番茄小说可读性：画面清楚、句子干净、对话推动剧情。",
    ],
    "never_do": [
        "不解释这一章的作用。",
        "不总结人物成长。",
        "不写创作技巧、提示词、AI过程或结构分析。",
        "不使用公众号风格、教学语气、复盘表格。",
        "不为了制造冲突降低人物智商。",
        "不复制、改写或大段复述上一章原文。",
        "不为了凑字数重复同一批线索、动作和台词。",
        "不写流水账，不用“他心中一震”“暗暗发誓”等模板化表达。",
        "不重置场景、关系和危机，不重新铺垫世界观。",
    ],
}


def normalize_real_event_strategy(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    enabled = data.get("enabled")
    if enabled is None:
        enabled = data.get("based_on_real_event", False)
    source_type = str(data.get("source_type") or data.get("event_source") or "个人").strip()
    custom_source = str(data.get("source_type_custom") or "").strip()
    if source_type == "__custom__" and custom_source:
        source_type = custom_source
    if not bool(enabled):
        return {
            "enabled": False,
            "source_type": source_type,
            "source_type_custom": custom_source,
            "adaptation_level": "",
            "risk_control": "",
        }
    return {
        "enabled": bool(enabled),
        "source_type": source_type,
        "source_type_custom": custom_source,
        "adaptation_level": str(data.get("adaptation_level") or "中"),
        "risk_control": str(
            data.get("risk_control")
            or data.get("risk_avoidance")
            or "人物、地点、时间线和关键事件均虚构化，只保留情绪真实，不影射具体个人。"
        ),
    }


def normalize_core_design(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    return {
        "爽点设计": str(data.get("爽点设计") or data.get("satisfaction_design") or "阶段性小胜、认知升级和关系确认交替出现。"),
        "情绪曲线": str(data.get("情绪曲线") or data.get("emotion_curve") or "压抑开局 -> 行动破局 -> 爽感释放 -> 新悬念牵引"),
        "读者画像": str(data.get("读者画像") or data.get("reader_profile") or "需要现实共鸣、成长代偿和强钩子的中文网文读者"),
        "平台标签": str(data.get("平台标签") or data.get("commercial_tags") or data.get("platform_tags") or "番茄,女频,成长,强钩子"),
    }


def _text(value: Any, fallback: str = "") -> str:
    return str(value or fallback).strip()


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def _safe_int(value: Any, fallback: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return fallback


def _parse_chapter_range(value: Any, default_start: int, default_end: int) -> tuple[int, int]:
    text = _text(value)
    if not text:
        return default_start, default_end
    for sep in ["-", "－", "—", "到", "~"]:
        if sep in text:
            left, right = text.split(sep, 1)
            start = _safe_int(left.strip(), default_start)
            end = _safe_int(right.strip(), default_end)
            return min(start, end), max(start, end)
    chapter = _safe_int(text, default_start)
    return chapter, chapter


def normalize_long_form_plan(raw: Any, *, chapter_count: int = 500, phase_count: int = 5) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    total = max(1, min(_safe_int(data.get("total_chapters"), chapter_count), 500))
    phases = max(1, min(_safe_int(data.get("phase_count"), phase_count), 50))
    volume_plans: list[dict[str, Any]] = []
    for index, item in enumerate(_list(data.get("volume_plans"))):
        if not isinstance(item, dict):
            continue
        default_start = (index * total) // phases + 1
        default_end = ((index + 1) * total) // phases
        start, end = _parse_chapter_range(item.get("chapter_range"), default_start, default_end)
        volume_plans.append({
            "volume_name": _text(item.get("volume_name"), f"第{index + 1}卷"),
            "chapter_range": f"{max(1, start)}-{min(total, max(start, end))}",
            "theme": _text(item.get("theme")),
            "stage_goal": _text(item.get("stage_goal")),
            "core_conflict": _text(item.get("core_conflict")),
            "protagonist_growth": _text(item.get("protagonist_growth")),
            "ending_result": _text(item.get("ending_result")),
            "ending_hook": _text(item.get("ending_hook")),
        })
    if not volume_plans:
        for index in range(phases):
            start = (index * total) // phases + 1
            end = ((index + 1) * total) // phases
            volume_plans.append({
                "volume_name": f"第{index + 1}卷",
                "chapter_range": f"{start}-{max(start, end)}",
                "theme": "",
                "stage_goal": "",
                "core_conflict": "",
                "protagonist_growth": "",
                "ending_result": "",
                "ending_hook": "",
            })
    story_units: list[dict[str, Any]] = []
    for item in _list(data.get("story_units")):
        if not isinstance(item, dict):
            continue
        start = _safe_int(item.get("start_chapter"), 0)
        end = _safe_int(item.get("end_chapter"), start)
        if not start and item.get("chapter_range"):
            start, end = _parse_chapter_range(item.get("chapter_range"), 1, min(total, 20))
        if not start:
            continue
        story_units.append({
            "start_chapter": max(1, min(start, total)),
            "end_chapter": max(1, min(max(start, end), total)),
            "unit_name": _text(item.get("unit_name"), "故事单元"),
            "main_event": _text(item.get("main_event")),
            "stage_conflict": _text(item.get("stage_conflict")),
            "payoff_emotion": _text(item.get("payoff_emotion")),
            "foreshadowing": _text(item.get("foreshadowing")),
            "payoff": _text(item.get("payoff")),
        })
    return {
        "total_chapters": total,
        "story_mainline": _text(data.get("story_mainline")),
        "phase_count": phases,
        "volume_plans": volume_plans,
        "story_units": story_units,
    }


def _story_safe_line(value: Any, fallback: str) -> str:
    """Convert planning language into a line that can safely appear in prose."""
    text = _text(value)
    meta_tokens = [
        "主角", "章末", "具体问题", "更高层威胁", "悬念", "读者", "本章", "剧情", "目标推进",
        "开局危机", "世界规则", "人物困境", "章节规划", "规则重写", "小说世界模拟器", "不合规范",
        "世界观", "关键同盟", "感情线", "阶段目标", "卷主题", "人物成长", "设定", "系统",
    ]
    if not text or any(token in text for token in meta_tokens):
        return fallback
    if re.search(r"^[^，。！？]{1,12}[：:]", text):
        return fallback
    if len(re.findall(r"[、，,]", text)) >= 5:
        return fallback
    return text


def _clean_title_fragment(value: Any, *, limit: int = 10) -> str:
    text = _text(value)
    if not text:
        return ""
    text = re.sub(r"^第\s*\d+\s*[章节回]?[：:、\s-]*", "", text)
    text = re.sub(r"^(开启|推进|收束|开篇|开局|本章)\s*", "", text)
    bracket = re.search(r"【([^】]{2,12})】", text)
    if bracket:
        text = bracket.group(1)
    else:
        text = re.split(r"[：:，,。；;！!？?\n\r]", text, 1)[0]
    text = re.sub(r"[《》“”\"'`*_#\[\]{}()（）]", "", text).strip()
    text = re.sub(r"^(用|让|把|将|以|通过|围绕)", "", text).strip()
    banned = [
        "主角", "读者", "剧情", "章节", "本章", "目标", "悬念", "人物困境", "世界规则",
        "开局危机", "推进危机", "阶段危机", "故事单元",
    ]
    if any(token in text for token in banned):
        return ""
    return text[:limit].strip("：:，,。；;、 ")


def _title_candidates_by_keywords(source: str) -> list[str]:
    title_rules = [
        (["残香", "槐井"], "残香复燃，槐井索命"),
        (["香火", "槐井"], "香火一亮，井鬼上门"),
        (["破庙", "孩子"], "破庙求救，孩子断魂"),
        (["残香", "孩子"], "残香救命，代价上门"),
        (["老井", "索命"], "井中索命"),
        (["外卖", "摆拍"], "善意被拍成罪证"),
        (["视频", "投诉"], "一段视频，把她推上风口"),
        (["陌生人", "机会"], "她帮一单，命运改写"),
        (["送餐", "质疑"], "雨中送餐，善意成疑"),
        (["房租", "岗位"], "快交不起房租时，机会来了"),
        (["献祭", "神殿"], "祭台逃生，神殿追来"),
        (["身份", "隐瞒"], "他藏的身份，终于露痕"),
        (["偷拍视频", "群"], "偷拍视频进群后"),
        (["求救", "门口"], "求救声到了门口"),
    ]
    candidates: list[str] = []
    for tokens, title in title_rules:
        if all(token in source for token in tokens):
            candidates.append(title)
    single_keyword_titles = [
        (["槐井"], "槐井里的东西来了"),
        (["残香"], "残香突然亮了"),
        (["破庙"], "破庙来了不速之客"),
        (["摆拍"], "善意成了摆拍"),
        (["投诉"], "她被投诉了"),
        (["偷拍视频"], "偷拍视频出现了"),
        (["房租"], "房租催到眼前"),
        (["陌生人"], "陌生人递来转机"),
    ]
    for tokens, title in single_keyword_titles:
        if any(token in source for token in tokens):
            candidates.append(title)
    return candidates


def _title_phrase_from_full_title(value: Any) -> str:
    text = _text(value)
    if "：" in text:
        return text.split("：", 1)[1].strip()
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return text.strip()


def _used_chapter_title_phrases(chapters: list[Any], *, exclude_chapter: int | None = None) -> set[str]:
    used: set[str] = set()
    for item in chapters:
        if not isinstance(item, dict):
            continue
        if exclude_chapter is not None and int(item.get("chapter_number") or 0) == int(exclude_chapter):
            continue
        phrase = _title_phrase_from_full_title(item.get("title"))
        if phrase:
            used.add(phrase)
    return used


def _chapter_title_candidates(chapter_number: int, plan: dict[str, Any]) -> list[str]:
    goal = _text(plan.get("goal") or plan.get("chapter_goal"))
    conflict = _text(plan.get("conflict") or plan.get("plot_conflict"))
    suspense = _text(plan.get("suspense") or plan.get("hook"))
    source = " ".join([goal, conflict, suspense])
    candidates = _title_candidates_by_keywords(source)

    explicit = _clean_title_fragment(
        plan.get("title") or plan.get("chapter_title") or plan.get("name"),
        limit=12,
    )
    if explicit:
        candidates.append(explicit)

    bracket = _clean_title_fragment(goal, limit=10)
    if bracket:
        candidates.append(bracket)

    candidates.extend([
        "危机已经上门" if chapter_number == 1 else "新的麻烦来了",
        f"第{chapter_number}个转机出现",
        f"这一次，不能后退",
    ])
    deduped: list[str] = []
    for title in candidates:
        title = title[:16].strip()
        if title and title not in deduped:
            deduped.append(title)
    return deduped


def _chapter_title_phrase(chapter_number: int, plan: dict[str, Any], used_phrases: set[str] | None = None) -> str:
    used = used_phrases or set()
    candidates = _chapter_title_candidates(chapter_number, plan)
    for candidate in candidates:
        if candidate not in used:
            return candidate
    return f"第{chapter_number}章新危机"


def _format_chapter_title(chapter_number: int, plan: dict[str, Any], used_phrases: set[str] | None = None) -> str:
    return f"第{chapter_number}章：{_chapter_title_phrase(chapter_number, plan, used_phrases)}"


def _is_generic_role_name(name: str) -> bool:
    return _text(name) in {"", "主角", "女主", "男主", "核心视角", "主人公", "视角人物"}


def _fallback_protagonist_name(data: dict[str, Any]) -> str:
    seed = _text(data.get("protagonist_seed"))
    if seed and not _is_generic_role_name(seed) and len(seed) <= 5:
        return seed
    return "林小满" if _is_modern_realist_book(data) else "云栖"


def skill_market_analysis(ctx: dict[str, Any]) -> dict[str, Any]:
    core = normalize_core_design(ctx.get("core_design"))
    return {
        **ctx,
        "market_analysis": {
            "target_reader": core["读者画像"],
            "core_selling_points": [core["爽点设计"], core["情绪曲线"]],
            "platform_tags": [item.strip() for item in core["平台标签"].split(",") if item.strip()],
            "market_opportunity": "用明确处境、强行动目标和可持续章节钩子提升追读。",
            "risk_analysis": "避免题材跑偏、关系高风险、犯罪细节堆叠和平台外信息。",
            "quality_score": 88,
        },
    }


def skill_world_build(ctx: dict[str, Any]) -> dict[str, Any]:
    blueprint = _dict(ctx.get("blueprint"))
    world = _dict(blueprint.get("world_bible"))
    return {
        **ctx,
        "world_setting": {
            "time_background": world.get("time_background") or _text(ctx.get("worldview_seed"), "现代社会或架空世界的第一卷开端"),
            "social_system": world.get("society_system") or world.get("social_system") or "身份、资源和规则共同构成压力。",
            "relationship_network": world.get("relationship_map") or "林小满、同盟、对手、权力中心四层关系网。",
            "rule_system": world.get("rule_system") or "所有能力和选择必须付出代价，不允许临时开挂。",
            "power_system": world.get("power_system") or "能力成长、信息差、关系协作和关键选择共同构成力量体系。",
        },
    }


def skill_character_design(ctx: dict[str, Any]) -> dict[str, Any]:
    blueprint = _dict(ctx.get("blueprint"))
    characters = _list(blueprint.get("character_life_system"))
    if not characters:
        characters = [
            {
                "name": _fallback_protagonist_name(ctx),
                "background": _text(ctx.get("protagonist_seed"), "普通人处在高压现实中，被迫做出改变。"),
                "personality": "清醒、韧性强，遇事先观察再行动。",
                "strengths": "学习力、观察力、共情力、关键时刻的行动力。",
                "flaws": "习惯独自承担，不轻易求助。",
                "psychological_conflict": "想要安全感，又害怕依赖别人后再次失去。",
                "growth_route": "从被动承受，到主动选择，再到能保护自己和他人。",
                "final_change": "成为有判断、有边界、有行动力的人。",
            }
        ]
    cleaned = [dict(item) for item in characters if isinstance(item, dict)]
    if cleaned and _is_generic_role_name(_text(cleaned[0].get("name"))):
        cleaned[0]["name"] = _fallback_protagonist_name(ctx)
    return {**ctx, "characters": cleaned}


def build_chapter_plans(raw_plan: list[Any], target_count: int = 100) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for item in raw_plan:
        if not isinstance(item, dict):
            continue
        chapter = int(item.get("chapter") or len(plans) + 1)
        goal = _story_safe_line(item.get("goal") or item.get("chapter_goal"), "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。")
        conflict = _story_safe_line(item.get("conflict") or item.get("plot_conflict"), "自己的麻烦还没解决，别人的求助已经压到眼前。")
        suspense = _story_safe_line(item.get("suspense") or item.get("hook"), "一段偷拍视频被发进群里，善意突然变成了质疑。")
        plans.append(
            {
                "chapter": chapter,
                "title": _chapter_title_phrase(chapter, item),
                "goal": goal,
                "conflict": conflict,
                "suspense": suspense,
                **_chapter_continuity_plan(chapter, item, goal=goal, conflict=conflict, suspense=suspense),
            }
        )
    while len(plans) < target_count:
        chapter = len(plans) + 1
        goal = "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。"
        conflict = "自己的麻烦还没解决，别人的求助已经压到眼前。"
        suspense = "一段偷拍视频被发进群里，善意突然变成了质疑。"
        plans.append(
            {
                "chapter": chapter,
                "title": "雨中援手",
                "goal": goal,
                "conflict": conflict,
                "suspense": suspense,
                **_chapter_continuity_plan(chapter, {}, goal=goal, conflict=conflict, suspense=suspense),
            }
        )
    return plans[:target_count]


def _chapter_continuity_plan(
    chapter: int,
    item: dict[str, Any],
    *,
    goal: str,
    conflict: str,
    suspense: str,
) -> dict[str, Any]:
    """Normalize each chapter into one clear event and a finite scene ladder."""
    raw_core = _text(item.get("core_event") or item.get("main_event") or item.get("unit_event"))
    if not raw_core:
        raw_core = goal
    core_event = _story_safe_line(raw_core, goal)
    raw_clues = _list(item.get("new_clues") or item.get("clues"))
    clues = [_story_safe_line(clue, "") for clue in raw_clues if _story_safe_line(clue, "")]
    if not clues:
        clues = [
            _clean_title_fragment(core_event, limit=14) or "现场异常",
            _clean_title_fragment(conflict, limit=14) or "阻力压近",
            _clean_title_fragment(suspense, limit=14) or "新悬念出现",
        ]
    clues = list(dict.fromkeys(clues))[:3]
    consequence = item.get("previous_consequence") or "上一章的选择立刻产生代价。"
    scene_beats = [
        f"后果出现：{_story_safe_line(consequence, '上一章的选择立刻产生代价。')}",
        f"外部冲突：{conflict}",
        f"调查线索：围绕{clues[0]}推进，不再横向堆新元素。",
        f"主动选择：角色必须采取一个会改变局面的行动，完成{core_event}",
        f"章末钩子：{suspense}",
    ]
    return {
        "core_event": core_event,
        "scene_beats": scene_beats,
        "new_clues": clues,
        "irreversible_change": _story_safe_line(
            item.get("irreversible_change") or item.get("payoff") or suspense,
            "角色做出选择，局面不可逆地升级。",
        ),
        "planning_rule": "一章只围绕一个核心事件；最多3个新线索；每幕必须完成具体动作并产生不可逆变化。",
    }


def expand_story_units_to_raw_plans(units: list[Any], target_count: int) -> list[dict[str, Any]]:
    raw: list[dict[str, Any]] = []
    for unit in units:
        if not isinstance(unit, dict):
            continue
        start = max(1, _safe_int(unit.get("start_chapter"), 0))
        end = max(start, _safe_int(unit.get("end_chapter"), start))
        end = min(end, target_count)
        if start > target_count:
            continue
        unit_name = _text(unit.get("unit_name"), "故事单元")
        main_event = _text(unit.get("main_event"), "推进这一组章节的主要事件")
        conflict = _text(unit.get("stage_conflict"), "外部阻碍与内心选择同时出现。")
        emotion = _text(unit.get("payoff_emotion"), "压抑后的确认、理解、反击或希望。")
        foreshadowing = _text(unit.get("foreshadowing"), "")
        payoff = _text(unit.get("payoff"), "")
        for chapter in range(start, end + 1):
            if chapter == start:
                goal = f"开启【{unit_name}】：{main_event}"
                suspense = foreshadowing or "一个暂时解释不了的细节压到眼前。"
            elif chapter == end:
                goal = f"收束【{unit_name}】：{payoff or main_event}"
                suspense = payoff or foreshadowing or "阶段性结果背后露出新的代价。"
            else:
                goal = f"推进【{unit_name}】：{main_event}，释放{emotion}"
                suspense = foreshadowing or "新的阻碍让选择更难。"
            raw.append({
                "chapter": chapter,
                "title": unit_name,
                "goal": goal,
                "conflict": conflict,
                "suspense": suspense,
            })
    return raw


def skill_plot_design(ctx: dict[str, Any]) -> dict[str, Any]:
    blueprint = _dict(ctx.get("blueprint"))
    chapter_count = _safe_int(ctx.get("chapter_count"), 500)
    target_count = max(1, min(chapter_count, 500))
    long_form = _dict(ctx.get("long_form_plan"))
    unit_plan = expand_story_units_to_raw_plans(_list(long_form.get("story_units") or ctx.get("story_units")), target_count)
    blueprint_plan = _list(blueprint.get("hundred_chapter_plan") or blueprint.get("chapter_outline"))
    plans_by_chapter = {int(item.get("chapter") or 0): item for item in blueprint_plan if isinstance(item, dict)}
    for item in unit_plan:
        plans_by_chapter[int(item.get("chapter") or 0)] = item
    raw_plan = [plans_by_chapter[key] for key in sorted(plans_by_chapter) if key > 0]
    return {**ctx, "plot_outline": build_chapter_plans(raw_plan, target_count)}


def skill_chapter_write(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        **ctx,
        "chapter_generation_rule": {
            "input_required": ["bookId", "chapterPlan"],
            "must_follow": ["当前场景直接开始", "动作和对话呈现信息", "目标推进", "冲突制造", "悬念收尾"],
            "rule": "章节正文只能基于当前 book_id 的 storyArchive 和 chapterPlan 生成，按小说世界模拟器契约输出正文。",
            "world_simulator_contract": NOVEL_WORLD_SIMULATOR_CONTRACT,
        },
    }


def skill_style_optimize(ctx: dict[str, Any]) -> dict[str, Any]:
    return {
        **ctx,
        "style_optimization": {
            "remove": ["空洞说明", "重复描述", "作者解释", "纯设定堆叠"],
            "enhance": ["场景行动", "人物选择", "情绪转折", "章末钩子"],
        },
    }


def skill_logic_check(ctx: dict[str, Any]) -> dict[str, Any]:
    issues: list[str] = []
    if not ctx.get("bookId"):
        issues.append("缺少 bookId，禁止进入生成。")
    if not _list(ctx.get("plot_outline")):
        issues.append("缺少章节规划，禁止生成正文。")
    return {
        **ctx,
        "logic_check": {
            "pass": not issues,
            "issues": issues,
            "quality_score": 90 if not issues else 55,
        },
    }


SKILL_FUNCTIONS: dict[str, SkillFn] = {
    "market_analysis": skill_market_analysis,
    "world_build": skill_world_build,
    "character_design": skill_character_design,
    "plot_design": skill_plot_design,
    "chapter_write": skill_chapter_write,
    "style_optimize": skill_style_optimize,
    "logic_check": skill_logic_check,
}


def run_skill_pipeline(input_data: dict[str, Any], *, pipeline: list[str] | None = None, enabled: dict[str, bool] | None = None) -> dict[str, Any]:
    order = [step for step in (pipeline or DEFAULT_PIPELINE) if step in SKILL_FUNCTIONS]
    enabled = enabled or {}
    ctx = dict(input_data)
    ctx["pipeline_trace"] = []
    for step in order:
        if enabled.get(step, True) is False:
            ctx["pipeline_trace"].append({"step": step, "status": "skipped"})
            continue
        ctx = SKILL_FUNCTIONS[step](ctx)
        ctx["pipeline_trace"].append({"step": step, "status": "done"})
    return ctx


def analyze_story(output: dict[str, Any]) -> dict[str, Any]:
    plot_outline = _list(output.get("plot_outline"))
    characters = _list(output.get("characters"))
    core = normalize_core_design(output.get("core_design"))
    risk = normalize_real_event_strategy(output.get("real_event_strategy"))
    satisfaction_score = 75 + min(20, len(core["爽点设计"]) // 6)
    pacing_score = 70 + min(25, len(plot_outline) // 5)
    commercial_potential = 70 + min(20, len(core["平台标签"].split(",")) * 4)
    risk_level = "低"
    if risk["enabled"] and risk["adaptation_level"] in {"低", "low"}:
        risk_level = "中"
    if not characters or not plot_outline:
        risk_level = "高"
    total = round((satisfaction_score + pacing_score + commercial_potential + (85 if risk_level == "低" else 65 if risk_level == "中" else 45)) / 4)
    return {
        "爽点评分": min(satisfaction_score, 100),
        "节奏评分": min(pacing_score, 100),
        "商业潜力": min(commercial_potential, 100),
        "风险等级": risk_level,
        "score": total,
        "auto_rewrite": total < 60,
    }


def optimize_low_score_output(output: dict[str, Any], analysis: dict[str, Any]) -> dict[str, Any]:
    if not analysis.get("auto_rewrite"):
        return output
    patched = dict(output)
    plans = _list(patched.get("plot_outline"))
    if plans:
        plans[0] = {
            **plans[0],
            "goal": "开篇直接制造主角必须行动的危机，并明确本书终局目标。",
            "conflict": "现实压力、人物欲望和外部阻碍同场出现。",
            "suspense": "章末抛出与主线终局相关的高价值问题。",
        }
    patched["plot_outline"] = plans
    patched["optimization_record"] = {
        "problem": "商业智能评分低于60，触发自动重写。",
        "solution": "强化开篇目标、冲突密度和主线悬念。",
        "result": "已更新第1章规划和商业风险提示。",
    }
    return patched


def build_book_blueprint(input_data: dict[str, Any]) -> dict[str, Any]:
    book_id = _text(input_data.get("bookId") or input_data.get("id"))
    if not book_id:
        raise ValueError("bookId is required")
    chapter_count = max(1, min(_safe_int(input_data.get("chapter_count"), 500), 500))
    phase_count = max(1, min(_safe_int(input_data.get("phase_count"), 5), 50))
    long_form_input = input_data.get("long_form_plan") if isinstance(input_data.get("long_form_plan"), dict) else {
        "total_chapters": chapter_count,
        "story_mainline": input_data.get("story_mainline"),
        "phase_count": phase_count,
        "volume_plans": input_data.get("volume_plans"),
        "story_units": input_data.get("story_units"),
    }
    long_form_plan = normalize_long_form_plan(long_form_input, chapter_count=chapter_count, phase_count=phase_count)
    normalized_input = {
        **input_data,
        "bookId": book_id,
        "id": book_id,
        "chapter_count": long_form_plan["total_chapters"],
        "phase_count": long_form_plan["phase_count"],
        "story_mainline": long_form_plan["story_mainline"],
        "volume_plans": long_form_plan["volume_plans"],
        "story_units": long_form_plan["story_units"],
        "long_form_plan": long_form_plan,
        "real_event_strategy": normalize_real_event_strategy(input_data.get("real_event_strategy")),
        "core_design": normalize_core_design(input_data.get("core_design")),
    }
    blueprint = build_story_blueprint(normalized_input)
    pipeline_output = run_skill_pipeline({**normalized_input, "blueprint": blueprint})
    analysis = analyze_story(pipeline_output)
    optimized = optimize_low_score_output(pipeline_output, analysis)
    return {
        **optimized,
        "bookId": book_id,
        "id": book_id,
        "title": _text(input_data.get("title"), "未命名小说"),
        "genre": _text(input_data.get("genre"), "romance_fantasy"),
        "hook": _text(input_data.get("hook") or input_data.get("idea"), ""),
        "core_design": normalized_input["core_design"],
        "real_event_strategy": normalized_input["real_event_strategy"],
        "long_form_plan": long_form_plan,
        "volume_plans": long_form_plan["volume_plans"],
        "story_units": long_form_plan["story_units"],
        "chapter_count": long_form_plan["total_chapters"],
        "commercial_analysis": analysis,
    }


def build_story_archive(book: dict[str, Any]) -> dict[str, Any]:
    book_id = _text(book.get("id") or book.get("bookId"))
    return {
        "book_id": book_id,
        "title": _text(book.get("title"), "未命名小说"),
        "world": _dict(book.get("world_setting")),
        "characters": _list(book.get("characters")),
        "timeline": [],
        "plot": {
            "chapterPlans": _list(book.get("plot_outline")),
            "current_chapter": 0,
            "open_threads": [],
        },
        "updated_at": book.get("updated_at") or book.get("created_at"),
    }


def build_chapter_brief_from_book(
    book: dict[str, Any],
    archive: dict[str, Any],
    *,
    user_note: str = "",
    chapter_number: int | None = None,
) -> dict[str, Any]:
    chapters = _list(archive.get("chapters"))
    max_number = max((int(item.get("chapter_number") or 0) for item in chapters), default=0)
    next_number = int(chapter_number or max_number + 1)
    plans = _list(book.get("plot_outline"))
    chapter_plan = next((item for item in plans if int(item.get("chapter") or 0) == next_number), None)
    if not chapter_plan:
        chapter_plan = {
            "chapter": next_number,
            "title": "雨中援手",
            "goal": "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。",
            "conflict": "自己的麻烦还没解决，别人的求助已经压到眼前。",
            "suspense": "一段偷拍视频被发进群里，善意突然变成了质疑。",
        }
    used_title_phrases = _used_chapter_title_phrases(chapters, exclude_chapter=next_number)
    title_phrase = _chapter_title_phrase(next_number, chapter_plan, used_title_phrases)
    chapter_plan = {**chapter_plan, "title": title_phrase}
    characters = _list(book.get("characters") or archive.get("characters"))
    protagonist = characters[0] if characters and isinstance(characters[0], dict) else {}
    recent_chapters = sorted(_list(archive.get("chapters")), key=lambda item: int(item.get("chapter_number") or 0))[-3:]
    return {
        "bookId": book.get("id"),
        "story_name": book.get("title"),
        "chapter_number": next_number,
        "chapterPlan": chapter_plan,
        "title_hint": _format_chapter_title(next_number, chapter_plan, used_title_phrases),
        "world_state": {
            "title": book.get("title"),
            "genre": book.get("genre"),
            "world_setting": book.get("world_setting") or archive.get("world") or {},
            "core_design": book.get("core_design") or {},
        },
        "character_state": {
            "characters": characters[:8],
            "current_viewpoint": _character_name(book),
        },
        "chapter_mission": {
            "core_event": chapter_plan.get("core_event"),
            "scene_beats": _list(chapter_plan.get("scene_beats")),
            "new_clues": _list(chapter_plan.get("new_clues"))[:3],
            "irreversible_change": chapter_plan.get("irreversible_change"),
            "goal": chapter_plan.get("goal"),
            "conflict": chapter_plan.get("conflict"),
            "hook": chapter_plan.get("suspense"),
        },
        "memory": {
            "previous_chapters_summary": [
                {
                    "chapter_number": item.get("chapter_number"),
                    "title": item.get("title"),
                    "summary": item.get("summary") or item.get("context_summary"),
                }
                for item in recent_chapters
            ],
            "timeline": _list(archive.get("timeline"))[-8:],
            "open_threads": _list(_dict(archive.get("plot")).get("open_threads"))[:8],
        },
        "world_simulator_contract": NOVEL_WORLD_SIMULATOR_CONTRACT,
        "must_do": [
            "开头直接进入当前场景，不写作者说明。",
            "只输出小说正文，不要标题说明、JSON、结构提示或写作思路。",
            "信息必须通过动作、对话和细节呈现，不允许总结式旁白。",
            "只承接上一章结果，不复述上一章原文。",
            "本章必须形成4-5个递进场景，每一幕推进一个新信息：后果、冲突、线索、选择、钩子。",
            "若是第2章及以后，先写上一章造成的代价，再写新的危机和主动行动。",
            "开头必须紧接上一章结尾，不重新铺垫世界观、不重置危机。",
            "回忆总量不得超过正文10%，且只能用于揭示线索、动机或代价。",
            "每一段必须有新信息、新变化或新冲突，用行动和对话推动，不堆心理描写。",
            "本章必须引入至少1个新信息、升级1个矛盾，或改变主角处境。",
            "玄学内容必须可观察、可推理：落到物件、方位、时辰、因果代价或风水逻辑。",
            f"本章核心事件：{chapter_plan.get('core_event')}",
            f"五幕推进：{' / '.join(_list(chapter_plan.get('scene_beats')))}",
            f"本章最多使用3个新线索：{'、'.join(_list(chapter_plan.get('new_clues'))[:3])}",
            f"不可逆变化：{chapter_plan.get('irreversible_change')}",
            f"本章目标：{chapter_plan.get('goal')}",
            f"本章冲突：{chapter_plan.get('conflict')}",
            f"章末悬念：{chapter_plan.get('suspense')}",
        ],
        "do_not_do": [
            "不要继承其他小说的人物、世界观或旧章节。",
            "不要写“本章”“这一章”“下面”“为了增强冲突”等说明。",
            "不要复制、改写或大段复述上一章原文。",
            "不要重复同一段动作、台词、物件和线索来凑字数。",
            "不要写流水账、纯心理描写堆砌或“他心中一震”“暗暗发誓”等模板句。",
            "不要换一种说法重复同一件事。",
            "不要大段总结前文。",
            "不要写平台外引流、联系方式、外部链接、账号口令。",
            "不要为了冲突降低人物智商。",
            "不要偏离当前 bookId 的 Story Archive。",
        ],
        "user_note": user_note.strip(),
    }


def _character_name(book: dict[str, Any]) -> str:
    characters = _list(book.get("characters"))
    if characters and isinstance(characters[0], dict):
        name = _text(characters[0].get("name"))
        if name and not _is_generic_role_name(name):
            return name
    return _fallback_protagonist_name(book)


def _previous_summary(archive: dict[str, Any]) -> str:
    chapters = _list(archive.get("chapters"))
    if not chapters:
        return "门外的风声压低下来，第一件麻烦已经逼到眼前。"
    latest = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-1]
    return _text(latest.get("summary") or latest.get("title") or latest.get("content"), "上一章留下的选择还没有完成。")[:220]


def _previous_consequence_prompt(archive: dict[str, Any], fallback: str = "上一章的选择已经带来新的代价。") -> str:
    chapters = _list(archive.get("chapters"))
    if not chapters:
        return fallback
    latest = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-1]
    title = _text(latest.get("title"), "上一章")
    summary = _text(latest.get("summary"), "")
    if summary:
        summary = re.sub(r"第\s*\d+\s*章[：:][^\n。！？]*", "", summary).strip()
        summary = re.split(r"[。！？]", summary)[-1].strip() or summary[:40]
        return f"{title}之后，{summary}带来的代价必须立刻落到眼前。"
    return f"{title}之后，上一章的选择必须带来新的阻力、代价或追问。"


def _chapter_sentences(text: str) -> list[str]:
    compact = re.sub(r"\s+", "", _text(text))
    parts = re.split(r"[。！？!?；;]", compact)
    return [part for part in parts if len(part) >= 18]


def _chapter_shingles(text: str, size: int = 18) -> set[str]:
    compact = re.sub(r"[\s，。！？!?；;、“”\"'：:（）()\[\]【】《》,.]+", "", _text(text))
    if len(compact) < size:
        return set()
    return {compact[index:index + size] for index in range(0, len(compact) - size + 1)}


def _chapter_repetition_review(content: str, archive: dict[str, Any], chapter_number: int) -> dict[str, Any]:
    if chapter_number <= 1:
        return {"pass": True, "issues": [], "score": 100, "shared_sentences": []}
    chapters = _list(archive.get("chapters"))
    if not chapters:
        return {"pass": True, "issues": [], "score": 100, "shared_sentences": []}
    previous = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-1]
    previous_content = _text(previous.get("content") or previous.get("summary"))
    prev_sentences = set(_chapter_sentences(previous_content))
    current_sentences = _chapter_sentences(content)
    shared = [sentence for sentence in current_sentences if sentence in prev_sentences]
    prev_shingles = _chapter_shingles(previous_content)
    cur_shingles = _chapter_shingles(content)
    overlap = len(prev_shingles & cur_shingles) / max(1, len(cur_shingles))
    issues: list[str] = []
    if len(shared) >= 2:
        issues.append("疑似复述上一章：出现多句完全相同的长句。")
    if overlap > 0.18 and len(content) > 1200:
        issues.append("与上一章文本重合度过高，需要改写为后果承接和新事件推进。")
    return {
        "pass": not issues,
        "issues": issues,
        "score": max(45, 100 - len(shared) * 15 - (20 if overlap > 0.18 else 0)),
        "shared_sentences": shared[:3],
        "shingle_overlap": round(overlap, 3),
    }


def _chapter_prose_quality_issues(content: str) -> list[str]:
    issues: list[str] = []
    template_phrases = [
        "心中一震", "暗暗发誓", "眼神坚定", "热血沸腾", "命运的齿轮",
        "他知道自己不能退", "她知道自己不能退", "这一切才刚刚开始",
    ]
    if any(phrase in content for phrase in template_phrases):
        issues.append("存在模板化网文表达。")
    recap_tokens = ["前文", "此前发生", "回想起之前", "大致经过", "简单来说"]
    if any(token in content for token in recap_tokens):
        issues.append("存在总结前文倾向。")
    paragraphs = [part.strip() for part in re.split(r"\n{2,}", content) if part.strip()]
    memory_paragraphs = [
        part for part in paragraphs
        if any(token in part for token in ["想起", "记起", "回忆", "当年", "上一章"])
    ]
    memory_chars = sum(len(part) for part in memory_paragraphs)
    if memory_chars > max(160, len(content) * 0.1):
        issues.append("回忆内容超过正文10%，需要压缩为线索或动机。")
    weak_paragraphs = 0
    action_tokens = [
        "问", "说", "看", "走", "推", "按", "拿", "放", "追", "拦", "查", "翻", "指",
        "听", "碰", "退", "停", "递", "跪", "敲", "裂", "响", "亮", "渗", "写",
    ]
    for part in paragraphs:
        if len(part) < 18:
            continue
        has_dialogue = "“" in part and "”" in part
        has_action = any(token in part for token in action_tokens)
        has_change = any(token in part for token in ["忽然", "终于", "却", "反而", "露出", "出现", "多了", "少了", "变"])
        if not (has_dialogue or has_action or has_change):
            weak_paragraphs += 1
    if weak_paragraphs >= max(8, int(len(paragraphs) * 0.35)):
        issues.append("过多段落缺少动作、对话或新变化。")
    return issues


def _director_step(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    total = max(1, len(_list(book.get("plot_outline"))) or 100)
    protagonist = _character_name(book)
    if chapter_number <= 3:
        pace = f"快开局，直接把{protagonist}推入异常事件，迅速建立读者问题。"
    elif chapter_number <= total * 0.25:
        pace = f"持续加压，每章必须让{protagonist}获得一个新线索或付出一个代价。"
    elif chapter_number <= total * 0.75:
        pace = "中段升级，冲突不能横向重复，必须扩大代价和关系变化。"
    else:
        pace = "后段收束，回收伏笔同时打开终局压力。"
    return {
        "role": "Director",
        "chapter_position": f"{chapter_number}/{total}",
        "pace": pace,
        "conflict_speed": "每200-300字发生一次行动、发现、关系变化或风险升级。",
    }


def _plot_designer_step(brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    return {
        "role": "Plot Designer",
        "core_event": _text(plan.get("core_event"), _text(plan.get("goal"), "推进一个具体事件。")),
        "scene_beats": _list(plan.get("scene_beats")),
        "new_clues": _list(plan.get("new_clues"))[:3],
        "irreversible_change": _text(plan.get("irreversible_change"), "角色做出选择，局面不可逆地升级。"),
        "opening_conflict": _text(plan.get("conflict"), "旧问题未解决，新压力突然压上来。"),
        "chapter_goal": _text(plan.get("goal"), "推进一个具体行动，让主角获得线索、资源或关系变化。"),
        "twist": _text(brief.get("twist") or plan.get("irreversible_change") or plan.get("suspense"), "当前线索让局面转向更具体的风险。"),
        "hook": _text(plan.get("suspense") or brief.get("hook"), "章末留下一个具体问题或更高层威胁。"),
    }


def _character_manager_step(book: dict[str, Any], archive: dict[str, Any]) -> dict[str, Any]:
    characters = _list(book.get("characters"))
    protagonist = characters[0] if characters and isinstance(characters[0], dict) else {}
    ally = next((item for item in characters[1:] if isinstance(item, dict)), {})
    protagonist_name = _character_name(book)
    return {
        "role": "Character Manager",
        "protagonist": protagonist_name,
        "motivation": _text(protagonist.get("inner_conflict") or protagonist.get("psychological_conflict"), "想获得安全感，又害怕再次失去主动权。"),
        "behavior_guard": f"{protagonist_name}必须通过观察、选择和行动破局，不能突然降智或被动等待拯救。",
        "relationship_shift": f"与{_text(ally.get('name'), '关键同盟')}的信任推进一小步，但保留新的疑点。",
        "previous_summary": _previous_summary(archive),
    }


def _is_modern_realist_book(book: dict[str, Any]) -> bool:
    haystack = " ".join([
        _text(book.get("title")),
        _text(book.get("genre")),
        _text(book.get("hook")),
        _text(_dict(book.get("core_design")).get("平台标签")),
        _text(_dict(book.get("world_setting")).get("time_background")),
        _text(_dict(book.get("world_setting")).get("social_system")),
    ])
    return any(token in haystack for token in ["都市", "现代", "现言", "职场", "现实", "治愈", "励志", "普通人", "生活", "urban", "modern_romance"])


def _supporting_name(book: dict[str, Any], fallback: str = "周望") -> str:
    characters = _list(book.get("characters"))
    for item in characters[1:]:
        if isinstance(item, dict) and _text(item.get("name")):
            return _text(item.get("name"))
    return fallback


def _realist_scene_place(book: dict[str, Any], chapter_number: int) -> str:
    world = _dict(book.get("world_setting"))
    seed = _text(world.get("time_background") or world.get("social_system"))
    if "社区" in seed:
        return "社区服务站门口"
    if "职场" in seed or "公司" in seed:
        return "写字楼一层的闸机前"
    places = ["早餐铺门口", "老小区楼下", "社区服务站门口", "便民超市外的雨棚下", "公交站旁边"]
    return places[(max(chapter_number, 1) - 1) % len(places)]


def _clean_chapter_text(text: str) -> str:
    banned_prefixes = ["总结", "本章", "这一章", "下面", "以下", "作为", "我们可以看到", "写作", "结构", "为了增强", "故事刚开始"]
    lines = []
    meta_fragments = [
        "章末留下", "具体问题", "更高层威胁", "目标推进", "本章目标", "本章冲突", "章节规划",
        "小说世界模拟器", "不合规范", "按小说", "规则重写", "开局危机", "人物困境", "世界规则", "主角",
        "世界观", "关键同盟", "感情线", "阶段目标", "卷主题", "人物成长", "章节标题", "系统默认",
        "读者", "第一个选择", "如何面对",
    ]
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if any(line.startswith(prefix) for prefix in banned_prefixes):
            continue
        if any(fragment in line for fragment in meta_fragments):
            continue
        if "公众号" in line or "提示词" in line or "JSON" in line:
            continue
        if re.search(r"^[^，。！？]{1,12}[：:]", line):
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _next_episode_preview(book: dict[str, Any], hook: str, protagonist: str) -> str:
    safe_hook = _story_safe_line(hook, "那段视频的发布者，很可能就在她即将赶去的社区服务站里。")
    if _is_modern_realist_book(book):
        return f"下期看点：{protagonist}赶到社区服务站后，会发现质疑她的人不只想看热闹，还握着另一段被剪掉的视频。"
    return f"下期看点：{safe_hook}"


def _replace_role_tokens(text: str, protagonist: str) -> str:
    if not protagonist or protagonist == "主角":
        return text
    return (text or "").replace("主角", protagonist).replace("主人公", protagonist)


def _writer_step(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any], director: dict[str, Any], plot: dict[str, Any], character: dict[str, Any]) -> str:
    chapter_number = int(brief.get("chapter_number") or _dict(brief.get("chapterPlan")).get("chapter") or 1)
    place = _realist_scene_place(book, chapter_number) if _is_modern_realist_book(book) else _text(_dict(book.get("world_setting")).get("time_background"), "风声压低的街口")
    protagonist = _character_name(book)
    ally = _supporting_name(book)
    hook = plot["hook"]
    user_note = _text(brief.get("user_note"))
    previous = character["previous_summary"]
    previous_memory = _previous_consequence_prompt(archive) if archive.get("chapters") else "她出门前还在想，今天只要不再出错，就已经算赢。"
    goal = plot["chapter_goal"]
    conflict = plot["opening_conflict"]
    twist = plot["twist"]
    safe_goal = _story_safe_line(goal, "她必须先把这件急事处理好，才有资格去争取自己的机会。")
    safe_conflict = _story_safe_line(conflict, "自己的麻烦还没解决，别人的求助已经压到眼前。")
    safe_twist = _story_safe_line(twist, "她忽然意识到，这件事从一开始就被人剪掉了最重要的一段。")
    note_line = "她把快到嘴边的解释咽了回去。"

    if _is_modern_realist_book(book):
        rewrite_mode = any(token in user_note for token in ["重写", "重新生成", "不合规范", "避开原文"])
        if chapter_number > 1:
            scene_openings = [
                f"雨停后的{place}有股潮味，公告栏前挤着三个人。",
                f"{protagonist}赶到{place}时，墙上的电子钟刚跳过八点四十。",
                f"服务站玻璃门被人从里面推开，冷气和争吵声一起扑到{protagonist}脸上。",
                f"{place}外的台阶还湿着，{protagonist}刚站稳，就听见有人叫她的名字。",
            ]
            opening = scene_openings[(chapter_number + (1 if rewrite_mode else 0)) % len(scene_openings)]
            trigger = "桌上的投诉表被人翻得哗啦响" if not rewrite_mode else "一只录音笔被推到桌边，红灯还亮着"
            paragraphs = [
                opening,
                f"{previous_memory}",
                f"{protagonist}把伞收紧，水珠顺着伞骨砸在地砖上。她原本以为上一章的麻烦已经暂时按住，至少能给自己换来一次解释机会。",
                f"可她刚走近，就看见{trigger}。",
                f"{ally}站在走廊尽头，脸色难看。他没有立刻开口，只用眼神示意她看会议室里的人。",
                "里面坐着两个人。一个穿着深色外套，手边放着手机；另一个低头翻资料，像是已经准备好把结论写下来。",
                f"“你就是{protagonist}？”深色外套的人抬眼。",
                f"{protagonist}点头，“是。”",
                "“昨天的视频，是你让人拍的？”",
                f"这句话落下来，{protagonist}心里那点侥幸彻底没了。{safe_conflict}",
                f"{ally}往前半步，“她不是那种人。”",
                "“你替她保证？”对方笑了一下，“那你也解释解释，为什么视频只拍到她帮人，没拍到前面发生了什么？”",
                f"{protagonist}没有急着辩。她看见桌角压着一张打印截图，截图下面有一行小字，正好是{safe_goal}",
                "她伸手拿起那张纸。",
                "“可以给我三分钟吗？”",
                "“你想说什么？”",
                f"“我想先确认一件事。”{protagonist}把截图转向众人，“这个账号发视频的时间，比我离开现场还早两分钟。”",
                "会议室里静了一下。",
                f"{ally}猛地抬头，“也就是说，有人提前等在那里？”",
                f"{protagonist}看着截图右下角的时间，声音很稳，“不是等我，是等任何一个会伸手的人。”",
                "深色外套的人皱起眉，“你有证据？”",
                "她把手机放到桌上，点开刚才在走廊里收到的一条消息。消息只有一张照片，照片里是雨棚下的监控探头。",
                f"{safe_twist}",
                "照片下面还有一句话。",
                "想查真相，就别从正门进。",
                f"{protagonist}抬起头，第一次觉得这件事不是一场误会，而是有人把她推到了一个早就搭好的局里。",
                _next_episode_preview(book, hook, protagonist),
            ]
        else:
            paragraphs = [
            f"雨水从雨棚边缘滴下来时，{protagonist}的手机第三次响起。",
            f"她站在{place}，一只手拎着还冒热气的早餐，另一只手按住帆布包里的缴费单。屏幕上跳着房东的名字，像一颗烫在掌心里的钉子。",
            "她没有立刻接。",
            "排队的人往前挪了一步，后面的大爷催了句：“姑娘，走不走？”",
            f"{protagonist}回过神，把手机扣在掌心里，“走。”",
            f"刚迈出半步，门口忽然传来一声闷响。一个外卖箱歪倒在水洼边，豆浆从袋口淌出来，混着雨水流到她鞋尖前。",
            f"{ally}蹲在地上，手肘擦破了一块皮，车轮旁边扎着一枚细钉。手机提示音还在响，一声比一声急。",
            "“您有一笔订单即将超时。”",
            f"{ally}低低骂了一句，伸手去扶车，手指却抖了一下。",
            f"{protagonist}把早餐袋放到台阶上，蹲下看了眼轮胎，“不能骑了。”",
            "“我知道。”他撑着车把站起来，脸色比雨后的水泥地还灰，“还有九单。”",
            "旁边有人看热闹，有人绕开水洼，也有人举起手机拍。早餐铺老板娘探出头：“小周，摔着没？”",
            f"{ally}摇头，“没事。”",
            "话刚说完，手机又跳出一条消息。客户催单，平台倒计时，红色数字挤在一块，看得人喘不过气。",
            f"{protagonist}看着那串数字，忽然想起早上压在心底的事：{previous_memory}",
            f"她知道自己也快被生活催到角落里了。房租、工作、家里的电话，每一样都在等她低头。可眼前这个人连低头的时间都没有。",
            "“最近的一单在哪？”她问。",
            f"{ally}抬头看她，“你要干什么？”",
            "“帮你送。”",
            "“别闹。”",
            f"“我没闹。”{protagonist}伸手，“地址。”",
            f"{ally}盯着她，像是没听懂。雨水从他额前滴下来，砸在外卖箱的塑料扣上。",
            "旁边拍视频的小姑娘小声说：“这也能帮啊？”",
            f"{protagonist}没看她，只看着{ally}，“你推车去补胎。近的给我，远的等车好。客户要骂，让他骂我。”",
            "“你还有自己的事。”",
            f"“所以我只帮你一单。”她顿了顿，“但这一单不能烂在这里。”",
            f"{ally}终于把手机递给她。屏幕上是春明巷七号楼，备注写着：孩子上学前必须送到。",
            f"{protagonist}拨通客户电话，往雨里跑。",
            "电话那头几乎是吼出来的：“怎么还没到？我孩子早饭都没吃！”",
            f"她喘着气穿过路口，“您好，骑手车胎扎了，我现在给您送过去。八分钟内到。豆浆洒了一点，我让他补您一份。”",
            "“你是谁？”",
            "“路过帮忙的。”",
            "对面安静了两秒。",
            "“路过？”",
            "“对。”她跨过一片积水，鞋里瞬间灌进凉水，“但早餐是真的在路上。”",
            "春明巷七号楼没有电梯。楼道里的灯坏了两盏，墙上贴着褪色的小广告，空气里有潮味和旧油烟味。",
            f"{protagonist}爬到四楼时，胸口像塞了团湿棉花。门开得很快，一个女人抱着孩子站在门口，眼底全是没睡醒的火气。",
            "“抱歉，晚了。”她把袋子递过去。",
            "女人接过早餐，看见她裤脚上的泥水，声音低了一点，“你不是骑手？”",
            "“不是。”",
            "孩子从女人怀里探出头，“妈妈，她跑来的。”",
            "女人打开袋子，发现豆浆少了一点，眉头刚皱起，又松开了。",
            "“算了。”她把门边一包纸巾递出来，“擦擦吧。”",
            f"{protagonist}愣了一下，“不用。”",
            "“拿着。”女人说，“我刚才语气也不好。”",
            f"{protagonist}接过纸巾，指尖碰到包装袋边缘，心里那根绷了一早上的线忽然松了一点。",
            f"{note_line}",
            "她下楼时，手机又响了。",
            f"这次不是房东，是一个陌生号码。",
            f"“你好，是{protagonist}吗？”电话那头的声音很急，“我是春和社区服务站。你是不是要来做临时登记？”",
            f"{protagonist}停在二楼转角，“是，我可能会晚几分钟。”",
            "“不用按临时工流程走了。”",
            "她心口一沉。",
            "对方紧接着说：“刚才有人把你帮外卖员送餐的视频发到业主群了。主任让你直接过来，他想跟你聊另一个岗位。”",
            f"{protagonist}握着手机，楼道窗外的雨又密了起来。",
            "她还没来得及问，电话那头压低声音。",
            "“不过你最好快点。有人说你们是在摆拍，还把视频发到平台投诉区了。”",
            f"{safe_twist}",
            f"{protagonist}抬头，看见楼道墙角贴着一张刚被雨水洇开的通知。通知最下面，有人用黑笔补了一行字。",
            "别让她进服务站。",
            _next_episode_preview(book, hook, protagonist),
            ]
    else:
        shrine_terms = any(token in " ".join([
            _text(book.get("title")),
            _text(book.get("hook")),
            _text(_dict(book.get("core_design")).get("平台标签")),
        ]) for token in ["香火", "庙", "祈愿", "神道", "玄学", "修仙"])
        if shrine_terms:
            shrine = _text(_dict(book.get("world_setting")).get("time_background"), "青石镇外的破庙")
            if chapter_number > 1:
                rewrite_seed = int(brief.get("regenerate_seed") or 0)
                variant = (chapter_number + rewrite_seed) % 3
                if variant == 0:
                    paragraphs = [
                        f"天还没亮，{protagonist}就被一阵湿冷的铃声惊醒。",
                        f"那声音不是从庙门外传来的，而是从他昨夜救下孩子时留下的那缕香火里传出来的。香火只剩半寸，却照得供桌下一片发青。",
                        f"{ally}靠在门边守了一夜，听见动静立刻睁眼，“又来了？”",
                        f"{protagonist}没有回答。他看见香灰在桌面上排成一行字。",
                        f"{safe_goal}",
                        f"上一章留下的余痛还没退，掌心被愿力烧出的红痕仍在跳。{previous_memory}",
                        "门开时，一个老更夫站在雨雾里，怀里抱着一只湿透的铜铃。",
                        f"“听愿的人在不在？”老更夫嗓子哑得厉害，“镇北槐井出事了。”",
                        f"{ally}脸色一变，“那里不能去。”",
                        f"“昨夜那孩子的命，是从那里被借走的。”{ally}压低声音，“你救回来一口气，就等于把欠账记到了自己名下。”",
                        "铜铃忽然自己响了一声，铃口渗出一缕黑水。",
                        f"{protagonist}伸手按住铜铃，掌心红痕被烫亮。他看见黑水、槐根、一个跪在井边写名字的人。",
                        "名字写到一半，那人回头。",
                        f"那张脸，竟和{protagonist}有七分相似。",
                        "老更夫跪了下去，“今晚子时前，若不把井里的名册取出来，镇上还会死三个人。”",
                        f"{ally}一把拦住{protagonist}，“这是引你过去。”",
                        f"“如果是引我过去，”{protagonist}说，“那就说明它怕我不去。”",
                        f"{safe_twist}",
                        "他跨出庙门时，身后的破神像裂开一道缝，掉出一枚旧木签。",
                        "木签上写着：槐井取名。",
                        _next_episode_preview(book, hook, protagonist),
                    ]
                elif variant == 1:
                    paragraphs = [
                        f"午后的青石镇忽然起了白雾，雾从义庄方向漫过来，贴着地面往{shrine}爬。",
                        f"{protagonist}刚把昨夜救下的孩子安顿好，就听见庙外有人喊：“死人回来了！”",
                        f"{ally}手里的水碗一晃，“别出去。”",
                        f"{protagonist}看向供桌。残香没有亮，香灰却在桌上慢慢凹出一个掌印。",
                        f"那掌印指向义庄，也指向本章必须完成的事：{safe_goal}",
                        f"他想起上一章留下的警告。{previous_memory}",
                        "义庄门口围满了人，却没有一个敢靠近门槛。",
                        "门槛内躺着一具盖了白布的尸体。白布下面伸出一只手，手心里攥着半截烧黑的香。",
                        f"{protagonist}刚走近，那只手忽然松开，香头滚到他脚边。",
                        "香灰落地成字：借命者，偿愿。",
                        f"{ally}低声道：“这是冲你来的。”",
                        f"{protagonist}蹲下，没有碰尸体，只看见尸体袖口缝着一个小小的槐叶纹。",
                        "槐叶纹旁边，还有新鲜的泥。",
                        f"{safe_conflict}",
                        "围观的人群里，有个瘦高男人悄悄后退。",
                        f"{protagonist}抬头，“站住。”",
                        "男人拔腿就跑，白雾像被他撞破，露出一条通往镇北的窄巷。",
                        f"{ally}追出去两步，又猛地停住，“别追，他不是活人。”",
                        f"{protagonist}看见男人脚下没有影子。",
                        f"{safe_twist}",
                        "义庄里的尸体突然坐了起来，白布滑落，露出一张没有五官的脸。",
                        "那张脸朝着他，缓缓张开不存在的嘴。",
                        "“第二个愿，换你来还。”",
                        _next_episode_preview(book, hook, protagonist),
                    ]
                else:
                    paragraphs = [
                        f"傍晚，镇口的功德碑突然裂了。",
                        f"{protagonist}赶到时，碑前已经跪了一地人。每个人手里都攥着一张红纸，红纸上写着同一个名字。",
                        f"他的名字。",
                        f"{ally}把其中一张抢过来，脸色当场沉下去，“有人在替你收愿。”",
                        f"{protagonist}摸到袖中的残香。香没有热，反而冷得像一截冰。",
                        f"上一章的痕迹还没有散去，{previous_memory}",
                        "碑裂开的缝里夹着一片薄薄的木牌。",
                        f"{protagonist}抽出来，木牌背面刻着：{safe_goal}",
                        "跪在最前面的老妇抬头，眼睛浑浊，“你既然收了我们的愿，就该替我们办事。”",
                        f"{ally}挡到{protagonist}身前，“他什么时候收过？”",
                        "老妇把红纸举高。红纸边缘沾着香灰，香灰的颜色和破庙供桌上的一模一样。",
                        f"{protagonist}忽然明白，有人偷了庙里的香灰，把所有人的愿都栽到他身上。",
                        f"{safe_conflict}",
                        "人群后方，有孩子哭了起来。",
                        "哭声一起，功德碑的裂缝里渗出黑水，水面映出一座他从没见过的神龛。",
                        "神龛上供着的不是神像。",
                        "是一本翻开的名册。",
                        f"{protagonist}盯着那本名册，发现第一页第一行，写的正是昨夜那个孩子的名字。",
                        f"{safe_twist}",
                        "他把红纸按在裂碑上，声音不高，却压住了满场哭求。",
                        "“愿可以接，但账要先算清楚。”",
                        "裂碑深处传来一声轻笑。",
                        "那笑声像从井底冒出来。",
                        _next_episode_preview(book, hook, protagonist),
                    ]
            else:
                paragraphs = [
                f"第一声哭喊传进破庙时，供桌上的残香忽然自己亮了。",
                f"{protagonist}正跪在裂开的神像前，指尖还沾着灰。庙外雨声很急，檐角的水线像刀一样劈在青石阶上。",
                "他抬头看了一眼。",
                "香火明明已经断了三年。",
                f"门外有人踉跄撞进来，怀里抱着一个脸色发青的孩子。女人膝盖一软，几乎是爬到供桌前的。",
                "“神仙，求你救救他。”",
                "她把额头磕在地上，声音哑得像被砂纸磨过，“我家只剩这一个孩子了。”",
                f"{protagonist}没有动。这里没有神仙，只有一座塌了半边墙的荒庙，还有一个连明日口粮都不知道去哪找的人。",
                "可那炷残香又亮了一寸。",
                "烟气没有往上散，反而像一根细线，慢慢缠上孩子的手腕。",
                f"{protagonist}看见了一行极淡的字。",
                "寿尽于今夜，魂归槐井。",
                "他后背一寒。",
                "女人还在磕头，血从额角渗出来，混着雨水落在地砖缝里。孩子胸口起伏越来越轻，像下一口气随时会断。",
                f"{ally}站在门边，脸色发白，“云临，别碰。这孩子不是病，是被东西扣了命。”",
                f"{protagonist}低声问：“什么东西？”",
                "“镇北那口老井。”",
                "话音刚落，庙外忽然传来一阵水声。",
                "不是雨声。",
                "像有人拖着湿透的衣摆，一步一步踩过泥地，往庙门口走来。",
                "女人猛地回头，脸上最后一点血色也没了。",
                "“它来了。”",
                f"{protagonist}握紧供桌边缘，木刺扎进掌心。他本该把人赶出去，关上门，当作自己什么都没看见。",
                f"{previous}",
                "可那孩子的手忽然动了一下，冰凉的小指勾住了他的袖口。",
                "很轻。",
                "轻得像一根快断的线。",
                f"{protagonist}闭了闭眼，再睁开时，供桌上的残香已经烧到第三寸。",
                "烟气在他眼前凝成一个字。",
                "愿。",
                "他伸手握住那缕香烟。",
                "一瞬间，庙里所有声音都远了。雨声、哭声、井水拖地的声音，全被压到耳膜之外。",
                "他听见一个稚嫩的声音在黑暗里发抖。",
                "我想回家。",
                f"{protagonist}胸口像被什么东西撞了一下。",
                "下一刻，剧痛从掌心钻进骨缝。那不是灵气，也不是寻常法力，而是一股带着千百人叹息的热流，蛮横地冲进他的经脉。",
                f"{ally}惊声道：“你疯了？凡人接香火，会被愿力烧死！”",
                f"{protagonist}没有松手。",
                "门槛外，一只湿漉漉的手搭了上来。那手指节细长，指甲里全是黑泥，水珠滴在地上，立刻腐出一圈白烟。",
                "女人尖叫着抱紧孩子。",
                f"{protagonist}抬手，把那炷残香插回香炉。",
                "“他还没答应跟你走。”",
                "门外的东西停住了。",
                "雨幕里慢慢抬起一张没有五官的脸。",
                "庙里的神像忽然震了一下，大片泥壳从脸上剥落。供桌下，一块被灰尘埋住的木牌翻了出来。",
                f"{protagonist}低头，看见木牌上刻着两个旧字。",
                "听愿。",
                f"{safe_twist}",
                "那无脸之物像是被这两个字激怒，猛地撞向庙门。",
                "破门板当场裂开。",
                f"{protagonist}把孩子推回女人怀里，掌心的香火烧得皮肉发红。",
                "他终于明白，自己不是捡到了一座庙。",
                "是这座庙，等到了一个愿意替人接下因果的人。",
                "门外黑水漫过门槛。",
                "香炉里，第二缕香火亮了。",
                _next_episode_preview(book, hook, protagonist),
                ]
        else:
            paragraphs = [
                f"风从街口卷过来时，{protagonist}听见身后有人喊她的名字。",
                f"她没有回头，先把手里的东西压进袖中。{safe_conflict}",
                f"{ally}追上来，声音压得很低：“你真要现在去？”",
                f"{protagonist}看着前方那扇半开的门，“现在不去，线索就没了。”",
                f"门内传来瓷器碎裂声，紧接着是短促的呼救。围在外面的人齐齐后退，只有她往前走了一步。",
                f"{previous}",
                f"她知道这不是逞强。{safe_goal}",
                "有人伸手拦她，“进去就是惹祸。”",
                f"{protagonist}避开那只手，“我已经在祸里了。”",
                f"{note_line}",
                f"{ally}咬了咬牙，跟在她身后，“那我陪你。”",
                f"门轴发出一声刺耳的响。屋里没有灯，只有地上的水迹一直延到屏风后面。",
                f"{protagonist}蹲下，用指腹碰了碰水迹。水还是温的。",
                f"屏风后忽然有人笑了一声。",
                f"{safe_twist}",
                f"{protagonist}抬起眼，手指慢慢收紧。",
                _next_episode_preview(book, hook, protagonist),
            ]
    return _replace_role_tokens(_clean_chapter_text("\n\n".join(paragraphs)), protagonist)


def _editor_step(content: str) -> dict[str, Any]:
    issues: list[str] = []
    if len(content) < 2000:
        issues.append("正文长度低于2000字，连载沉浸感不足。")
    if any(word in content for word in [
        "总结", "本章讲述", "本文", "公众号", "提示词", "JSON", "章末留下", "具体问题",
        "更高层威胁", "主角", "世界观", "关键同盟", "感情线", "章节规划", "系统默认",
        "故事刚开始", "读者", "第一个选择", "如何面对",
    ]):
        issues.append("存在说明/总结/平台化表达。")
    issues.extend(_chapter_prose_quality_issues(content))
    if content.count("？") + content.count("?") < 2:
        issues.append("对话和问题牵引不足。")
    if not content.rstrip().endswith(("？", "。", "！", "”")):
        issues.append("结尾不完整。")
    return {
        "role": "Editor",
        "pass": not issues,
        "issues": issues,
        "immersion_score": max(60, 95 - len(issues) * 15),
    }


def _expand_chapter_body(
    body: str,
    *,
    book: dict[str, Any],
    brief: dict[str, Any],
    plot: dict[str, Any],
    protagonist: str,
    target_length: int = 2100,
) -> str:
    """Expand deterministic chapter prose until it meets the long-form target."""
    text = _clean_chapter_text(body)
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    ally = _supporting_name(book)
    safe_goal = _story_safe_line(plot.get("chapter_goal"), "她必须在事情失控前抓住唯一的线索。")
    safe_conflict = _story_safe_line(plot.get("opening_conflict"), "眼前的阻力比她预想得更早压了过来。")
    safe_twist = _story_safe_line(plot.get("twist"), "真正的问题藏在众人都忽略的细节里。")
    hook = _story_safe_line(plot.get("hook"), "门外又传来一声不该出现的响动。")
    scene_beats = []
    for item in _list(plot.get("scene_beats")):
        beat = re.sub(r"^[^：:]{1,8}[：:]\s*", "", _text(item)).strip()
        if beat:
            scene_beats.append(beat)
    new_clues = [_story_safe_line(item, "") for item in _list(plot.get("new_clues"))]
    new_clues = [item for item in new_clues if item][:3]
    is_shrine = any(token in " ".join([
        _text(book.get("title")),
        _text(book.get("hook")),
        _text(_dict(book.get("core_design")).get("平台标签")),
    ]) for token in ["香火", "庙", "祈愿", "神道", "玄学", "修仙"])
    scene_actions = [
        ("先处理后果", "确认谁受了伤、谁改了口、谁因为上一章的选择失去退路"),
        ("正面应对阻力", "让反对的人当场说清理由，也逼出围观者真正害怕的事"),
        ("核验关键线索", "只围着这一条线索查来源、时间和经手的人"),
        ("做出主动选择", "把查到的证据换成一次行动，而不是停在猜测里"),
        ("留下章末钩子", "让新的危险以一个具体物件、一句话或一次异动落到眼前"),
    ]
    planned_blocks: list[list[str]] = []
    for idx, beat in enumerate(scene_beats[:5]):
        clue = new_clues[idx % len(new_clues)] if new_clues else "眼前线索"
        action_name, action_detail = scene_actions[idx] if idx < len(scene_actions) else scene_actions[-1]
        planned_blocks.append([
            f"{protagonist}把这一幕先压成一个必须完成的动作：{beat}",
            f"围绕{clue}，他这次要{action_name}，具体做法是{action_detail}。",
            f"{ally}指向{clue}，提醒他别被旁支牵走。",
            f"{protagonist}顺着{clue}往下核，得到的不是完整答案，而是一个能推动下一步的变化。",
            f"等这一幕结束，局面必须留下痕迹：{hook}",
        ])
    expansion_sets = [
        [
            f"{protagonist}没有立刻往前走。他先把四周重新看了一遍：门槛上的水痕、墙角被蹭掉的灰、还有地面那道断断续续的脚印，每一样都像被人刻意摆在明处。",
            f"{ally}压低声音，“你在看什么？”",
            f"“看谁希望我只盯着眼前这件事。”{protagonist}说。",
            f"{safe_conflict}",
            "这句话说出口后，周围反而安静下来。安静不是安全，而是所有人都在等他先犯错。",
            f"{protagonist}把掌心贴到袖口，那里还残留着上一场风波留下的痛感。他把刚才听见的三句话按顺序记下，决定先追最早变口供的那个人。",
        ],
        [
            "人群里忽然有人咳了一声。",
            "那人很快低下头，可声音已经暴露了位置。",
            f"{protagonist}转过去时，对方正把一样东西塞进怀里。动作很快，却没有快过他的眼睛。",
            f"“拿出来。”{protagonist}说。",
            "对方脸色一白，“什么？”",
            f"{ally}往前一步，挡住那人的退路。",
            "那东西终于掉了出来，是一片被水泡软的纸角。纸角上只剩半个字，却和刚才出现的线索完全对得上。",
            f"{safe_goal}",
        ],
        [
            f"{protagonist}蹲下身，把那片纸角按在干净的石面上。水迹慢慢散开，露出更多细碎的墨痕。",
            "墨不是普通的墨，颜色发暗，边缘带着一点灰白，像烧过的香灰混进去。",
            f"{ally}看见后，呼吸明显停了一下。",
            f"“这不是今天才写的。”{protagonist}说。",
            "“那是什么时候？”",
            f"“至少在上一件事发生之前。”",
            "这意味着他们不是被意外卷进来，而是从一开始就被人算进了局里。",
            f"{safe_twist}",
        ],
        [
            "外面的风忽然重了。",
            "门板被吹得轻轻一响，像有人用指节敲在背面。",
            f"{protagonist}站起来，示意众人后退。",
            f"{ally}低声问：“要不要先离开？”",
            f"“现在离开，就等于把线索交回去。”{protagonist}看着门缝，“我只差一步。”",
            "他走到门前，没有直接拉开，而是先听。",
            "门外没有脚步声，只有某种潮湿的摩擦声，一下一下，贴着地面靠近。",
            f"{hook}",
        ],
        [
            f"{protagonist}忽然明白，对方要的不是一场胜负，而是让他在众人面前做一个无法解释的选择。",
            "救人，就会被说成借机收买人心；不救，就会眼看着线索断掉。",
            f"他看向{ally}，“如果我做错，你就把看到的全部记下来。”",
            f"{ally}怔了一下，“你觉得我会让你一个人担？”",
            f"{protagonist}笑了笑，没有回答。",
            "下一刻，他伸手按住那道裂开的边缘。冰冷的触感钻进指缝，像有无数细小的针顺着骨头往上爬。",
            "他忍住没有松手。",
        ],
        [
            "所有声音都在这一瞬间退远。",
            f"{protagonist}看见了一个短促的画面：有人在夜里搬动木箱，箱角滴着水；有人把名字从册页上划掉，又用另一种颜色补上；还有一只手，把半截香塞进门缝。",
            "画面很乱，却足够说明一件事。",
            "真正动手的人，还在他们身边。",
            f"{protagonist}睁开眼时，第一眼看的不是门外，而是人群最后方那个始终没有说话的人。",
            "那人也在看他。",
            "四目相对的一刻，对方的袖口轻轻动了一下。",
        ],
        [
            f"{ally}顺着他的目光看过去，脸色瞬间变了。",
            "“是他？”",
            f"{protagonist}没有点头。他还差最后一个证据。",
            "于是他故意把那片纸角收进袖中，转身往外走。",
            "身后果然响起急促的脚步声。",
            "不是追赶，是拦截。",
            "对方终于急了。",
            f"{protagonist}在门槛前停住，轻声说：“现在，可以谈真正的条件了。”",
        ],
        [
            "风把最后一点雾吹开，露出远处灰白的天光。",
            f"{protagonist}知道，这一章的问题还没有彻底解决，但局面已经变了：他不再只是被推着走的人。",
            f"{safe_goal}",
            "他把找到的线索握紧，指腹被边缘硌得发疼。",
            f"{ally}问：“下一步去哪？”",
            f"{protagonist}看向那条被雾遮住的小路，“去找那个以为自己藏得很好的人。”",
            _next_episode_preview(book, hook, protagonist),
        ],
    ]
    if is_shrine:
        expansion_sets[0][0] = f"{protagonist}没有立刻往前走。他先看香灰落下的方向，看门槛上逆流的水，看供桌底下那道新裂开的缝。"
        expansion_sets[3][6] = "门外没有脚步声，只有水从井底翻上来的声音，一下又一下，像有人在黑暗里拖着湿透的衣摆。"
    index = max(0, chapter_number - 1)
    planned_index = 0
    while len(text) < target_length and planned_index < len(planned_blocks):
        text = _clean_chapter_text(f"{text}\n\n" + "\n\n".join(planned_blocks[planned_index]))
        planned_index += 1
    guard = 0
    while len(text) < target_length and guard < len(expansion_sets):
        block = expansion_sets[(index + guard) % len(expansion_sets)]
        text = _clean_chapter_text(f"{text}\n\n" + "\n\n".join(block))
        guard += 1
    extra_index = 0
    while len(text) < target_length and extra_index < 4:
        extra_blocks = [
            [
                f"{protagonist}没有马上回答。他把刚才每个人站过的位置在心里重新排了一遍，终于发现最不合理的不是那片纸角，而是纸角出现得太及时。",
                "如果它真是意外留下的，不会刚好落在所有人都能看见的地方。",
                f"{ally}顺着他的视线看过去，“有人故意把它送到你手里。”",
                f"{protagonist}点头，“所以我们现在不能只追线索，还要追送线索的人。”",
            ],
            [
                "这一次，他没有再让众人围着看。",
                f"{protagonist}把东西收好，转身走到人少的角落，低声问了三个问题：谁最先发现异常，谁最后离开现场，谁一直没有靠近却知道得最多。",
                "三个答案拼在一起，像三段断开的绳，绳头却指向同一个方向。",
                f"{safe_twist}",
            ],
            [
                f"{ally}看见他的神色，声音压得更低，“你已经知道是谁了？”",
                f"“还差一步。”{protagonist}说。",
                "他要的不是猜测，而是让对方自己露出破绽。于是他故意把最重要的那句话说错半句。",
                "果然，人群里有人下意识抬头，眼底闪过一瞬慌乱。",
            ],
            [
                f"{protagonist}捕捉到了那一眼。",
                "这一眼比任何证据都短，却足够让他决定下一步。",
                f"他对{ally}说：“别拦他，让他走。”",
                f"{ally}一怔，很快明白过来。线索不会自己往前跑，除非拿线索的人以为自己还没暴露。",
                f"{protagonist}跟了上去。新的危机没有结束，只是终于露出了能追的方向。",
            ],
        ]
        text = _clean_chapter_text(f"{text}\n\n" + "\n\n".join(extra_blocks[extra_index]))
        extra_index += 1
    return text


def _chapter_summary(content: str) -> str:
    compact = " ".join(part.strip() for part in content.splitlines() if part.strip())
    return compact[:180]


def generate_chapter_from_plan(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    used_title_phrases = _used_chapter_title_phrases(_list(archive.get("chapters")), exclude_chapter=chapter_number)
    title = _format_chapter_title(chapter_number, plan, used_title_phrases)
    attempt_brief = dict(brief)
    director: dict[str, Any] = {}
    plot: dict[str, Any] = {}
    character: dict[str, Any] = {}
    content = ""
    continuity = {"pass": True, "issues": [], "score": 100, "shared_sentences": []}
    for attempt in range(3):
        if attempt:
            attempt_brief = {**attempt_brief, "regenerate_seed": attempt}
        director = _director_step(book, archive, attempt_brief)
        plot = _plot_designer_step(attempt_brief)
        character = _character_manager_step(book, archive)
        body = _writer_step(book, archive, attempt_brief, director, plot, character)
        body = _expand_chapter_body(
            body,
            book=book,
            brief=attempt_brief,
            plot=plot,
            protagonist=_character_name(book),
        )
        content = f"{title}\n\n{body}".strip()
        continuity = _chapter_repetition_review(content, archive, chapter_number)
        if continuity["pass"]:
            break
    editor = _editor_step(content)
    if not continuity["pass"]:
        editor["issues"].extend(_list(continuity.get("issues")))
        editor["pass"] = False
        editor["immersion_score"] = min(int(editor["immersion_score"]), int(continuity.get("score") or 60))
    review = analyze_story({"plot_outline": [plan], "characters": book.get("characters"), "core_design": book.get("core_design"), "real_event_strategy": book.get("real_event_strategy")})
    review["continuity_pass"] = continuity["pass"]
    review["continuity_issues"] = continuity["issues"]
    review["continuity_score"] = continuity["score"]
    review["editor_immersion_score"] = editor["immersion_score"]
    review["score"] = round((float(review.get("score") or 0) + editor["immersion_score"]) / 2)
    return {
        "id": f"{book.get('id')}-{chapter_number}",
        "book_id": book.get("id"),
        "chapter_number": chapter_number,
        "title": title,
        "content": content,
        "summary": _chapter_summary(content),
        "chapterPlan": plan,
        "quality": review,
        "production_trace": [director, plot, character],
        "editorial_review": editor,
        "continuity_review": continuity,
        "created_at": book.get("updated_at"),
    }
