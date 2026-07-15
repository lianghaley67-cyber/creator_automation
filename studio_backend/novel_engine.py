"""Book-scoped novel production engine for Novel OS.

The functions here are deterministic fallbacks. They make the SaaS workflow
usable even when no external LLM key is configured, while keeping every output
scoped by book_id so one novel never inherits another novel's memory.
"""
from __future__ import annotations

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
        "结尾留下角色当下必须面对的具体悬念。",
        "语言保持番茄小说可读性：画面清楚、句子干净、对话推动剧情。",
    ],
    "never_do": [
        "不解释这一章的作用。",
        "不总结人物成长。",
        "不写创作技巧、提示词、AI过程或结构分析。",
        "不使用公众号风格、教学语气、复盘表格。",
        "不为了制造冲突降低人物智商。",
    ],
}


def normalize_real_event_strategy(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    enabled = data.get("enabled")
    if enabled is None:
        enabled = data.get("based_on_real_event", False)
    if not bool(enabled):
        return {
            "enabled": False,
            "source_type": "",
            "source_type_custom": "",
            "adaptation_level": "",
            "risk_control": "",
        }
    source_type = str(data.get("source_type") or data.get("event_source") or "个人").strip()
    custom_source = str(data.get("source_type_custom") or "").strip()
    if source_type == "__custom__" and custom_source:
        source_type = custom_source
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


def _story_safe_line(value: Any, fallback: str) -> str:
    """Convert planning language into a line that can safely appear in prose."""
    text = _text(value)
    meta_tokens = ["主角", "章末", "具体问题", "更高层威胁", "悬念", "读者", "本章", "剧情", "目标推进"]
    if not text or any(token in text for token in meta_tokens):
        return fallback
    return text


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
        plans.append(
            {
                "chapter": chapter,
                "goal": _story_safe_line(item.get("goal") or item.get("chapter_goal"), "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。"),
                "conflict": _story_safe_line(item.get("conflict") or item.get("plot_conflict"), "自己的麻烦还没解决，别人的求助已经压到眼前。"),
                "suspense": _story_safe_line(item.get("suspense") or item.get("hook"), "一段偷拍视频被发进群里，善意突然变成了质疑。"),
            }
        )
    while len(plans) < target_count:
        chapter = len(plans) + 1
        plans.append(
            {
                "chapter": chapter,
                "goal": "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。",
                "conflict": "自己的麻烦还没解决，别人的求助已经压到眼前。",
                "suspense": "一段偷拍视频被发进群里，善意突然变成了质疑。",
            }
        )
    return plans[:target_count]


def skill_plot_design(ctx: dict[str, Any]) -> dict[str, Any]:
    blueprint = _dict(ctx.get("blueprint"))
    chapter_count = int(ctx.get("chapter_count") or 100)
    raw_plan = _list(blueprint.get("hundred_chapter_plan") or blueprint.get("chapter_outline"))
    return {**ctx, "plot_outline": build_chapter_plans(raw_plan, max(1, min(chapter_count, 100)))}


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
    normalized_input = {
        **input_data,
        "bookId": book_id,
        "id": book_id,
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
            "goal": "她必须先帮眼前的人解决一件急事，才可能抓住自己的机会。",
            "conflict": "自己的麻烦还没解决，别人的求助已经压到眼前。",
            "suspense": "一段偷拍视频被发进群里，善意突然变成了质疑。",
        }
    characters = _list(book.get("characters") or archive.get("characters"))
    protagonist = characters[0] if characters and isinstance(characters[0], dict) else {}
    recent_chapters = sorted(_list(archive.get("chapters")), key=lambda item: int(item.get("chapter_number") or 0))[-3:]
    return {
        "bookId": book.get("id"),
        "story_name": book.get("title"),
        "chapter_number": next_number,
        "chapterPlan": chapter_plan,
        "title_hint": f"第{next_number}章：{chapter_plan.get('goal')}",
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
            f"本章目标：{chapter_plan.get('goal')}",
            f"本章冲突：{chapter_plan.get('conflict')}",
            f"章末悬念：{chapter_plan.get('suspense')}",
        ],
        "do_not_do": [
            "不要继承其他小说的人物、世界观或旧章节。",
            "不要写“本章”“这一章”“下面”“为了增强冲突”等说明。",
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
        return "故事刚开始，读者还不知道她会如何面对第一个选择。"
    latest = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-1]
    return _text(latest.get("summary") or latest.get("title") or latest.get("content"), "上一章留下的选择还没有完成。")[:220]


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
        "opening_conflict": _text(plan.get("conflict"), "旧问题未解决，新压力突然压上来。"),
        "chapter_goal": _text(plan.get("goal"), "推进一个具体行动，让主角获得线索、资源或关系变化。"),
        "twist": _text(brief.get("twist"), "看似能解决问题的线索，反而暴露出更大的风险。"),
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
    banned_prefixes = ["总结", "本章", "这一章", "下面", "以下", "作为", "我们可以看到", "写作", "结构", "为了增强"]
    lines = []
    meta_fragments = ["章末留下", "具体问题", "更高层威胁", "目标推进", "本章目标", "本章冲突", "章节规划"]
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
    previous_memory = previous if archive.get("chapters") else "她出门前还在想，今天只要不再出错，就已经算赢。"
    goal = plot["chapter_goal"]
    conflict = plot["opening_conflict"]
    twist = plot["twist"]
    safe_goal = _story_safe_line(goal, "她必须先把这件急事处理好，才有资格去争取自己的机会。")
    safe_conflict = _story_safe_line(conflict, "自己的麻烦还没解决，别人的求助已经压到眼前。")
    safe_twist = _story_safe_line(twist, "她忽然意识到，这件事从一开始就被人剪掉了最重要的一段。")
    note_line = f"她把{user_note}这几个字在心里压了一遍，没让它变成解释。" if user_note else "她把快到嘴边的解释咽了回去。"

    if _is_modern_realist_book(book):
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
    if len(content) < 900:
        issues.append("正文长度偏短，连载沉浸感不足。")
    if any(word in content for word in ["总结", "本章讲述", "本文", "公众号", "提示词", "JSON", "章末留下", "具体问题", "更高层威胁", "主角"]):
        issues.append("存在说明/总结/平台化表达。")
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


def _chapter_summary(content: str) -> str:
    compact = " ".join(part.strip() for part in content.splitlines() if part.strip())
    return compact[:180]


def generate_chapter_from_plan(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    title = f"第{chapter_number}章：{_text(plan.get('goal'), '新的选择')[:24]}"
    director = _director_step(book, archive, brief)
    plot = _plot_designer_step(brief)
    character = _character_manager_step(book, archive)
    content = _writer_step(book, archive, brief, director, plot, character)
    editor = _editor_step(content)
    review = analyze_story({"plot_outline": [plan], "characters": book.get("characters"), "core_design": book.get("core_design"), "real_event_strategy": book.get("real_event_strategy")})
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
        "created_at": book.get("updated_at"),
    }
