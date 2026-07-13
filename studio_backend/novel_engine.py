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


def normalize_real_event_strategy(raw: Any) -> dict[str, Any]:
    data = raw if isinstance(raw, dict) else {}
    enabled = data.get("enabled")
    if enabled is None:
        enabled = data.get("based_on_real_event", False)
    return {
        "enabled": bool(enabled),
        "source_type": str(data.get("source_type") or data.get("event_source") or "个人"),
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
            "relationship_network": world.get("relationship_map") or "主角、同盟、对手、权力中心四层关系网。",
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
                "name": "主角",
                "background": _text(ctx.get("protagonist_seed"), "普通人处在高压现实中，被迫做出改变。"),
                "personality": "清醒、韧性强，遇事先观察再行动。",
                "strengths": "学习力、观察力、共情力、关键时刻的行动力。",
                "flaws": "习惯独自承担，不轻易求助。",
                "psychological_conflict": "想要安全感，又害怕依赖别人后再次失去。",
                "growth_route": "从被动承受，到主动选择，再到能保护自己和他人。",
                "final_change": "成为有判断、有边界、有行动力的人。",
            }
        ]
    return {**ctx, "characters": [item for item in characters if isinstance(item, dict)]}


def build_chapter_plans(raw_plan: list[Any], target_count: int = 100) -> list[dict[str, Any]]:
    plans: list[dict[str, Any]] = []
    for item in raw_plan:
        if not isinstance(item, dict):
            continue
        chapter = int(item.get("chapter") or len(plans) + 1)
        plans.append(
            {
                "chapter": chapter,
                "goal": _text(item.get("goal") or item.get("chapter_goal"), "推进一个具体行动，让主角获得线索、资源或关系变化。"),
                "conflict": _text(item.get("conflict") or item.get("plot_conflict"), "外部阻碍与内心选择同时出现。"),
                "suspense": _text(item.get("suspense") or item.get("hook"), "章末留下一个具体问题或更高层威胁。"),
            }
        )
    while len(plans) < target_count:
        chapter = len(plans) + 1
        plans.append(
            {
                "chapter": chapter,
                "goal": "推进一个具体行动，让主角获得线索、资源或关系变化。",
                "conflict": "外部阻碍与内心选择同时出现。",
                "suspense": "章末留下一个具体问题或更高层威胁。",
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
            "must_follow": ["目标推进", "冲突制造", "悬念收尾"],
            "rule": "章节正文只能基于当前 book_id 的 storyArchive 和 chapterPlan 生成。",
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


def build_chapter_brief_from_book(book: dict[str, Any], archive: dict[str, Any], *, user_note: str = "") -> dict[str, Any]:
    chapters = _list(archive.get("chapters"))
    next_number = len(chapters) + 1
    plans = _list(book.get("plot_outline"))
    chapter_plan = next((item for item in plans if int(item.get("chapter") or 0) == next_number), None)
    if not chapter_plan:
        chapter_plan = {
            "chapter": next_number,
            "goal": "推进一个具体行动，让主角获得线索、资源或关系变化。",
            "conflict": "外部阻碍与内心选择同时出现。",
            "suspense": "章末留下一个具体问题或更高层威胁。",
        }
    return {
        "bookId": book.get("id"),
        "story_name": book.get("title"),
        "chapter_number": next_number,
        "chapterPlan": chapter_plan,
        "title_hint": f"第{next_number}章：{chapter_plan.get('goal')}",
        "must_do": [
            "开头直接进入冲突场景，不写作者说明。",
            f"本章目标：{chapter_plan.get('goal')}",
            f"本章冲突：{chapter_plan.get('conflict')}",
            f"章末悬念：{chapter_plan.get('suspense')}",
        ],
        "do_not_do": [
            "不要继承其他小说的人物、世界观或旧章节。",
            "不要写平台外引流、联系方式、外部链接、账号口令。",
            "不要为了冲突降低人物智商。",
            "不要偏离当前 bookId 的 Story Archive。",
        ],
        "user_note": user_note.strip(),
    }


def generate_chapter_from_plan(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    title = f"第{chapter_number}章：{_text(plan.get('goal'), '新的选择')[:24]}"
    protagonist = (_list(book.get("characters")) or [{"name": "主角"}])[0]
    protagonist_name = _text(protagonist.get("name"), "主角") if isinstance(protagonist, dict) else "主角"
    content = (
        f"{title}\n\n"
        f"{protagonist_name}没有再等别人给答案。\n\n"
        f"眼前的问题很具体：{plan.get('goal')} 可真正挡在面前的，是{plan.get('conflict')}\n\n"
        "她先确认手里还能调动的资源，再把最危险的选择拆成三步。第一步，是让对手以为她还在原地；"
        "第二步，是把关键线索交到可信的人手里；第三步，则是亲自去验证那个最不愿面对的答案。\n\n"
        "这一次，她没有靠侥幸，也没有靠别人替她承担。她做出的每个决定都带着代价，却也让局面第一次向她倾斜。\n\n"
        f"就在她以为终于抓住主动权时，新的消息送到了面前：{plan.get('suspense')}"
    )
    review = analyze_story({"plot_outline": [plan], "characters": book.get("characters"), "core_design": book.get("core_design"), "real_event_strategy": book.get("real_event_strategy")})
    return {
        "id": f"{book.get('id')}-{chapter_number}",
        "book_id": book.get("id"),
        "chapter_number": chapter_number,
        "title": title,
        "content": content,
        "chapterPlan": plan,
        "quality": review,
        "created_at": book.get("updated_at"),
    }
