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


def _character_name(book: dict[str, Any]) -> str:
    protagonist = (_list(book.get("characters")) or [{"name": "主角"}])[0]
    if isinstance(protagonist, dict):
        name = _text(protagonist.get("name"), "主角")
        return "主角" if name in {"", "核心视角"} else name
    return "主角"


def _previous_summary(archive: dict[str, Any]) -> str:
    chapters = _list(archive.get("chapters"))
    if not chapters:
        return "故事刚开始，读者还不知道主角会如何面对第一个选择。"
    latest = sorted(chapters, key=lambda item: int(item.get("chapter_number") or 0))[-1]
    return _text(latest.get("summary") or latest.get("title") or latest.get("content"), "上一章留下的选择还没有完成。")[:220]


def _director_step(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any]) -> dict[str, Any]:
    plan = _dict(brief.get("chapterPlan"))
    chapter_number = int(brief.get("chapter_number") or plan.get("chapter") or 1)
    total = max(1, len(_list(book.get("plot_outline"))) or 100)
    if chapter_number <= 3:
        pace = "快开局，直接把主角推入异常事件，迅速建立读者问题。"
    elif chapter_number <= total * 0.25:
        pace = "持续加压，每章必须让主角获得一个新线索或付出一个代价。"
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
    return {
        "role": "Character Manager",
        "protagonist": _text(protagonist.get("name"), "主角"),
        "motivation": _text(protagonist.get("inner_conflict") or protagonist.get("psychological_conflict"), "想获得安全感，又害怕再次失去主动权。"),
        "behavior_guard": "主角必须通过观察、选择和行动破局，不能突然降智或被动等待拯救。",
        "relationship_shift": f"与{_text(ally.get('name'), '关键同盟')}的信任推进一小步，但保留新的疑点。",
        "previous_summary": _previous_summary(archive),
    }


def _clean_chapter_text(text: str) -> str:
    banned_prefixes = ["总结", "本章", "这一章", "下面", "以下", "作为", "我们可以看到"]
    lines = []
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line:
            if lines and lines[-1] != "":
                lines.append("")
            continue
        if any(line.startswith(prefix) for prefix in banned_prefixes):
            continue
        if "公众号" in line or "提示词" in line or "JSON" in line:
            continue
        lines.append(line)
    return "\n".join(lines).strip()


def _writer_step(book: dict[str, Any], archive: dict[str, Any], brief: dict[str, Any], director: dict[str, Any], plot: dict[str, Any], character: dict[str, Any]) -> str:
    title = _text(book.get("title"), "这本书")
    world = _dict(book.get("world_setting"))
    place = _text(world.get("time_background"), "夜色压低的城市")
    protagonist = _character_name(book)
    hook = plot["hook"]
    user_note = _text(brief.get("user_note"))
    previous = character["previous_summary"]
    relation = character["relationship_shift"]
    goal = plot["chapter_goal"]
    conflict = plot["opening_conflict"]
    twist = plot["twist"]
    note_line = f"她想起自己写在便签上的那句话：{user_note}" if user_note else "她把那句快要冲出口的解释咽了回去。"

    paragraphs = [
        f"警报响起的时候，{protagonist}正站在{place}的玻璃门前。",
        f"门内的屏幕一排排熄灭，只剩最中间那行红字还亮着：{conflict}",
        "人群先是安静了一秒，随即炸开。有人拍门，有人打电话，有人骂系统又在抽风。可她没有动。因为那行红字下面，还有一串只有她见过的编号。",
        f"那编号，和《{title}》开端里压在她身上的秘密一模一样。",
        f"{previous}",
        f"{protagonist}攥紧手机，掌心全是汗。她知道自己不能退。{goal}",
        "一个穿灰色外套的男人从人群后方挤过来，低声问：“你也看见了？”",
        "她抬眼看他。男人的袖口沾着雨水，右手却一直按在内袋上，像那里藏着什么比命还要紧的东西。",
        "“看见什么？”她反问。",
        "男人没有立刻回答，只把一张折成四方的纸塞进她手里。纸角很旧，边缘被磨得发白，上面只有一句话：不要相信第一次重启。",
        f"{note_line}",
        "大厅的灯忽然全灭。",
        "黑暗里，有人尖叫。紧接着，玻璃门外传来沉闷的撞击声，一下，又一下，像有什么东西正在从另一侧试图进来。",
        f"{protagonist}后退半步，肩膀撞上冰冷的墙。她能感觉到所有人的恐慌正在往她身上涌，可真正让她心口发紧的，是手机屏幕自动亮起。",
        "上面多了一条倒计时。",
        "十分钟。",
        "九分五十九秒。",
        "灰衣男人压低声音：“你手里那张纸，是上一轮留下来的。只有你能打开安全门。”",
        "“凭什么是我？”",
        "“因为上一轮，是你亲手关上的。”",
        "这句话像一根细针，猛地扎进她脑子里。许多破碎的画面一闪而过：奔跑的脚步、刺眼的白光、有人在她耳边喊不要回头。",
        "她疼得弯下腰，却在下一秒听见门外的撞击停了。",
        "安静比混乱更可怕。",
        "所有人都看向玻璃门。",
        "门外站着一个和她长得一模一样的人。",
        f"{relation}",
        f"{protagonist}的呼吸一点点沉下去。她没有冲过去，也没有尖叫。她把纸条翻到背面，看见背面还有一行更小的字。",
        f"{twist}",
        "倒计时跳到七分钟。",
        "灰衣男人催她：“开门，还是不开？”",
        f"{protagonist}抬起头，看着门外那个“自己”缓缓抬手，指尖贴上玻璃，一笔一画写下四个字。",
        f"{hook}",
    ]
    return _clean_chapter_text("\n\n".join(paragraphs))


def _editor_step(content: str) -> dict[str, Any]:
    issues: list[str] = []
    if len(content) < 900:
        issues.append("正文长度偏短，连载沉浸感不足。")
    if any(word in content for word in ["总结", "本章讲述", "本文", "公众号", "提示词", "JSON"]):
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
