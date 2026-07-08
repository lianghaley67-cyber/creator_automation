"""Toolized workflow helpers for serial fiction projects.

This module stays deterministic on purpose: it gives the UI and tests a stable
planning/diagnosis layer before any LLM writes prose.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any


FANQIE_HARD_RULES = [
    "不要写平台外引流、联系方式、外部链接、账号口令。",
    "不要把亲兄妹、继亲、师生强权等高风险关系写成暧昧或恋爱主线。",
    "不要连续堆叠死亡、追杀、洗钱、诈骗、监控、后门等强刺激元素。",
    "不要写成AI写作教程、提示词拆解、自媒体复盘或工具说明。",
    "每章只推进1个主目标，打开或回收1到2个悬念。",
]

SETUP_QUESTIONS = [
    "这本书一句话讲什么？主角最终想得到什么？",
    "核心爽点是什么：复仇、逆袭、救赎、权谋、破案、升级，还是爱情拉扯？",
    "男女主/双主角的关系边界是什么？有没有必须避开的伦理关系？",
    "世界观是现代、古代、架空玄幻、都市异能，还是混合？",
    "如果是修仙/玄幻，力量体系和代价是什么？如果是现代言情，现实压力是什么？",
    "第一卷要解决什么问题？结尾希望读者期待什么？",
    "你想要的文风更偏强剧情、强情绪、轻松甜宠，还是悬疑拉扯？",
]

GENRE_TEMPLATES = {
    "romance_fantasy": {
        "label": "言情玄幻连载",
        "promise": "用情感关系推动玄幻危机，用每章选择制造牵挂。",
        "avoid": ["亲属恋", "只谈设定不推进", "每章都靠误会拖延"],
    },
    "fantasy": {
        "label": "玄幻连载",
        "promise": "用清晰等级、代价和目标推进成长线。",
        "avoid": ["设定堆砌", "主角无代价开挂", "反派工具化"],
    },
    "fantasy_upgrade": {
        "label": "玄幻升级连载",
        "promise": "用等级压迫、资源争夺和世界秘密推进主角成长。",
        "avoid": ["纯打斗流水账", "系统无脑送经验", "设定多但人物没有情绪"],
    },
    "xianxia": {
        "label": "修仙升级连载",
        "promise": "用修炼体系、宗门规则、资源争夺和因果代价推动成长。",
        "avoid": ["境界说明压过剧情", "主角突然无敌", "奇遇替代选择"],
    },
    "romance": {
        "label": "言情连载",
        "promise": "用人物真实欲望和关系变化推动追读。",
        "avoid": ["无效拉扯", "只靠误会", "人设前后矛盾"],
    },
    "modern_romance": {
        "label": "现代言情连载",
        "promise": "用现实处境、关系拉扯、职业压力和自我成长推进故事。",
        "avoid": ["霸总模板台词", "全靠巧合重逢", "现实问题写成鸡汤"],
    },
}

SENSITIVE_PATTERNS = {
    "genre_drift": re.compile(r"代码|GitHub|变量|算法|服务器|Docker|API|U盘|数据库|后门", re.I),
    "family_romance_risk": re.compile(r"亲兄妹|亲妹妹|亲哥哥|同母异父|同父异母|继兄|继妹|哥哥.*妹妹|妹妹.*哥哥"),
    "crime_stack": re.compile(r"洗钱|赌债|诈骗|股权|伪造|监控|后门|合同陷阱|绑架"),
    "violence_stack": re.compile(r"追杀|尸体|死亡|杀人|血|跳楼|自杀|枪|刀"),
    "platform_leak": re.compile(r"微信|QQ|公众号|小红书|微博|关注我|私信|http|www\.", re.I),
    "tutorial_leak": re.compile(r"提示词|怎么写|AI原版|我的修改|教程|步骤|表格|工具"),
}


@dataclass(frozen=True)
class StoryMetric:
    key: str
    label: str
    count: int
    severity: str
    suggestion: str


def _text_from_chapter(chapter: dict[str, Any]) -> str:
    return "\n".join(
        str(chapter.get(key) or "")
        for key in ("title", "content_markdown", "content_xhs", "context_summary")
    )


def _count_chapter_hits(chapters: list[dict[str, Any]], pattern: re.Pattern[str]) -> int:
    return sum(1 for chapter in chapters if pattern.search(_text_from_chapter(chapter)))


def diagnose_story_archive(chapters: list[dict[str, Any]], bible: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return a practical diagnosis for a serial fiction archive."""
    bible = bible or {}
    total = len(chapters)
    open_threads = [
        item for item in (bible.get("ongoing_threads") or [])
        if isinstance(item, dict) and item.get("status") != "resolved"
    ]
    world_notes = str(bible.get("world_notes") or "")
    all_text = "\n".join(_text_from_chapter(chapter) for chapter in chapters) + "\n" + world_notes

    metrics = [
        StoryMetric(
            "genre_drift",
            "类型跑偏",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["genre_drift"]),
            "high",
            "如果目标是言情/玄幻，不要让代码、服务器、U盘、商业阴谋成为主线。",
        ),
        StoryMetric(
            "family_romance_risk",
            "关系高风险",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["family_romance_risk"]),
            "high",
            "把亲属/疑似亲属关系改为无血缘、误会、契约或阵营关系，恋爱线必须清白。",
        ),
        StoryMetric(
            "crime_stack",
            "犯罪元素过密",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["crime_stack"]),
            "medium",
            "商业犯罪可以保留为背景，但每卷只选一个核心阴谋，不要章章加码。",
        ),
        StoryMetric(
            "violence_stack",
            "强刺激过密",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["violence_stack"]),
            "medium",
            "减少死亡/追杀堆叠，用选择、代价、秘密和关系张力替代。",
        ),
        StoryMetric(
            "tutorial_leak",
            "不像小说正文",
            _count_chapter_hits(chapters, SENSITIVE_PATTERNS["tutorial_leak"]),
            "high",
            "小说模块只输出故事，不出现AI写作过程、提示词、复盘表格。",
        ),
    ]

    hard_issues: list[str] = []
    if any(metric.key == "family_romance_risk" and metric.count for metric in metrics):
        hard_issues.append("存在亲属/疑似亲属暧昧风险，推荐评估会非常吃亏。")
    if total and metrics[0].count / total >= 0.35:
        hard_issues.append("已有大量章节偏向现代技术/商业阴谋，不像言情玄幻连载。")
    if len(open_threads) > 12:
        hard_issues.append(f"未解悬念过多（{len(open_threads)}条），读者会累，系统也容易续写失控。")
    if SENSITIVE_PATTERNS["platform_leak"].search(all_text):
        hard_issues.append("正文/档案中可能出现平台外信息，需要发布前清理。")

    score = 100
    score -= min(metrics[0].count * 4, 30)
    score -= min(metrics[1].count * 8, 32)
    score -= min(metrics[2].count * 2, 16)
    score -= min(metrics[3].count * 2, 16)
    score -= min(len(open_threads), 20)
    score = max(score, 0)

    next_actions = [
        "先暂停直接生成下一章，别继续把偏掉的设定往后滚。",
        "重新确认一本书的定位：类型、主角目标、关系边界、第一卷终点。",
        "把高风险关系改成无血缘/契约/阵营关系，清掉平台外信息。",
        "把未解悬念收束到5条以内，再决定第1卷接下来3章怎么走。",
        "之后每章先生成章节Brief，确认后再写正文。",
    ]

    return {
        "score": score,
        "level": "需要重构" if score < 60 else ("需要收束" if score < 80 else "基本可用"),
        "chapter_count": total,
        "open_thread_count": len(open_threads),
        "world_notes_length": len(world_notes),
        "metrics": [metric.__dict__ for metric in metrics],
        "hard_issues": hard_issues,
        "next_actions": next_actions,
        "rules": FANQIE_HARD_RULES,
    }


def build_story_blueprint(seed: dict[str, Any]) -> dict[str, Any]:
    """Build a book-level blueprint draft that must be confirmed before chapters."""
    raw_genre = str(seed.get("genre") or "romance_fantasy").strip()
    template = GENRE_TEMPLATES.get(raw_genre, GENRE_TEMPLATES["romance_fantasy"])
    title = str(seed.get("title") or seed.get("name") or "未命名故事").strip()
    idea = str(seed.get("idea") or seed.get("premise") or "").strip()
    audience = str(seed.get("audience") or "喜欢强剧情、强情绪、又希望设定清楚的女性读者").strip()
    tone = str(seed.get("tone") or "有画面感、克制但有张力，章末留钩子").strip()

    chapter_count = int(seed.get("chapter_count") or 30)
    first_volume_count = min(max(int(seed.get("first_volume_count") or 10), 6), chapter_count)

    opening_question = idea or "主角在一个无法回头的选择前，必须在感情和命运之间做决定。"
    outline = []
    for index in range(1, first_volume_count + 1):
        if index == 1:
            goal = "用一个具体场景把主角困境、能力/秘密和关系张力立起来。"
        elif index == first_volume_count:
            goal = "回收第一卷核心矛盾，同时打开更大的代价。"
        else:
            goal = "推进一个选择，让主角获得线索或付出代价。"
        outline.append({
            "chapter": index,
            "goal": goal,
            "conflict": "外部阻碍 + 内心选择，不靠纯误会拖剧情。",
            "hook": "章末留下一个具体问题，让读者想看下一章。",
        })

    return {
        "status": "needs_confirmation",
        "next_step": "先回答或修改下方问题，确认后再生成第1章。",
        "questions": SETUP_QUESTIONS,
        "book_profile": {
            "title": title,
            "genre": template["label"],
            "one_sentence": opening_question,
            "target_reader": audience,
            "tone": tone,
            "promise": template["promise"],
        },
        "risk_rules": {
            "must_avoid": template["avoid"] + FANQIE_HARD_RULES,
            "chapter_rule": "每章只推进一个主要动作，最多保留两个悬念。",
        },
        "volume_plan": {
            "planned_chapters": chapter_count,
            "first_volume_chapters": first_volume_count,
            "first_volume_goal": "先完成读者能理解、能追下去的第一卷闭环。",
        },
        "chapter_outline": outline,
    }


def build_chapter_brief(
    story: dict[str, Any],
    bible: dict[str, Any],
    chapters: list[dict[str, Any]],
    *,
    chapter_number: int | None = None,
    user_note: str = "",
) -> dict[str, Any]:
    """Create the next chapter brief so generation is guided, not improvised."""
    last_number = max((int(c.get("chapter_number") or 0) for c in chapters), default=0)
    current = chapter_number or last_number + 1
    last_chapter = next((c for c in chapters if int(c.get("chapter_number") or 0) == last_number), None)
    open_threads = [
        str(item.get("thread") or "")
        for item in (bible.get("ongoing_threads") or [])
        if isinstance(item, dict) and item.get("status") != "resolved" and item.get("thread")
    ][:5]

    return {
        "story_id": story.get("id", ""),
        "story_name": story.get("name", "连载故事"),
        "chapter_number": current,
        "title_hint": f"第{current}章：先写一个明确的选择",
        "must_do": [
            "开头直接进入场景，不写作者说明。",
            "本章只解决一个目标：让主角做出一个会付出代价的选择。",
            "至少安排一个人物关系变化，避免只有设定或旁白。",
            "结尾留下一个具体悬念，但不要新增大堆设定。",
        ],
        "do_not_do": FANQIE_HARD_RULES,
        "previous_summary": (last_chapter or {}).get("context_summary", ""),
        "open_threads_to_use": open_threads,
        "user_note": user_note.strip(),
    }


def validate_chapter_text(text: str, brief: dict[str, Any] | None = None) -> dict[str, Any]:
    """Lightweight local review before platform publishing."""
    plain = re.sub(r"\s+", "", text or "")
    issues: list[str] = []
    for key in ("platform_leak", "tutorial_leak", "family_romance_risk"):
        if SENSITIVE_PATTERNS[key].search(text or ""):
            issues.append({
                "platform_leak": "正文含平台外信息/链接/引流痕迹。",
                "tutorial_leak": "正文像教程或AI写作拆解，不像小说。",
                "family_romance_risk": "存在亲属/疑似亲属暧昧风险。",
            }[key])
    if len(plain) < 1200:
        issues.append("章节正文偏短，番茄连载建议至少有完整场景、冲突和章末钩子。")
    if (text or "").count("？") + (text or "").count("?") > 16:
        issues.append("疑问句过多，像设定提纲，建议改成行动和对话。")
    if brief and str(brief.get("story_name") or "") and str(brief.get("story_name")) not in (text or "")[:200]:
        issues.append("开头没有明显章节归属，建议标题包含书名或章节名。")

    return {
        "pass": not issues,
        "issues": issues,
        "score": max(0, 100 - len(issues) * 18),
        "next_action": "可以进入人工审稿/发布" if not issues else "先按问题修改，再推送平台",
    }


def summarize_workflow() -> dict[str, Any]:
    return {
        "steps": [
            {"key": "plan", "label": "开书策划", "desc": "先确认题材、主角目标、关系边界和第一卷终点。"},
            {"key": "outline", "label": "章节脉络", "desc": "把第一卷拆成可确认的章节目标，不直接乱写。"},
            {"key": "brief", "label": "本章 Brief", "desc": "每章先定目标、冲突、转折和禁忌。"},
            {"key": "draft", "label": "生成正文", "desc": "只按本章 Brief 写小说正文。"},
            {"key": "review", "label": "合规复核", "desc": "检查类型跑偏、关系风险、平台外信息和章节完整度。"},
            {"key": "publish", "label": "推送番茄", "desc": "通过后再推送到番茄草稿箱。"},
        ],
        "principle": "小说不是文案的一种，它是一本书的长期工程。",
    }
