from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any


ROOT_DIR = Path(__file__).resolve().parents[1]
SKILLS_DIR = ROOT_DIR / "creator_skills"

CHANNEL_SKILLS: dict[str, dict[str, Any]] = {
    "wechat_article_v1": {
        "name": "公众号深度文章",
        "channel": "wechat",
        "content_kind": "wechat_article",
        "file": "wechat/06_wechat_article.md",
        "description": "长文结构、背景解释、个人判断和行动建议。适合深度科普和经验分享。",
        "persona_tags": ["通用"],
        "example": {
            "title": "用AI帮我省掉了每天1小时的重复工作",
            "summary": "我不是技术人，但我找到了一个普通人也能用的AI方法，每天少做1小时的重复事情。",
            "excerpt": "## 发生了什么\n\n每天早上，我要花差不多一小时整理前一天的工作记录……\n\n## 这意味着什么\n\nAI不是要替代你的判断，而是帮你减少重复劳动……",
        },
    },
    "xiaohongshu_note_v1": {
        "name": "小红书知识笔记",
        "channel": "xiaohongshu",
        "content_kind": "xiaohongshu_note",
        "file": "xiaohongshu/07_xiaohongshu_note.md",
        "description": "短标题、钩子、要点、互动问题和话题。适合知识传播类内容。",
        "persona_tags": ["通用"],
        "example": {
            "title": "普通人学AI，这3件事我一开始没想到",
            "body": "以为学AI要会代码——不用！\n\n1. 提示词说得越具体，效果越好\n2. 不同工具擅长不同事，选对比学多更重要\n3. 先用，再研究原理\n\n你学AI最大的困惑是什么？\n\n#AI工具推荐 #普通人学AI",
        },
    },
    "xiaohongshu_images_v1": {
        "name": "小红书图文卡片",
        "channel": "xiaohongshu",
        "content_kind": "xiaohongshu_image_cards",
        "file": "xiaohongshu/08_xiaohongshu_images.md",
        "description": "1080×1440 封面与内容卡片自动分页。适合知识卡片和步骤拆解。",
        "persona_tags": ["通用"],
        "example": {
            "title": "AI省时间攻略",
            "cover": "5个让普通人每天少做1小时的AI方法",
            "pages": ["封面：5个让普通人每天少做1小时的AI方法", "01 整理笔记：把乱七八糟的记录扔给AI", "02 写回复：让AI起草，你来润色"],
        },
    },
    "wechat_ai_growth_diary_v1": {
        "name": "公众号·AI成长实录",
        "channel": "wechat",
        "content_kind": "growth_diary",
        "file": "shared/13_ai_growth_diary.md",
        "description": "职场宝妈/独立女性/AI学习者视角，记录真实使用AI工具的过程、踩坑和变化，有温度、有共鸣、有可操作性。",
        "persona_tags": ["职场宝妈", "独立女性", "AI学习", "真实成长"],
        "example": {
            "title": "带娃间隙，我用30分钟学会了这件事，现在每周能省两小时",
            "summary": "我不是技术专家，只是一个职场宝妈，找到了一个用碎片时间也能学AI的方法，分享给有类似处境的你。",
            "excerpt": "## 我实际操作了什么\n\n孩子午睡那段时间，我打开了Claude，把上周的会议记录粘贴进去……\n\n## 卡在哪里了\n\n第一次它给我的格式完全不是我想要的，我重新描述了一遍需求……",
        },
    },
    "xiaohongshu_ai_growth_diary_v1": {
        "name": "小红书·AI成长实录",
        "channel": "xiaohongshu",
        "content_kind": "growth_diary",
        "file": "shared/13_ai_growth_diary.md",
        "description": "以职场宝妈/独立女性视角分享AI学习真实经历，有具体操作、有踩坑、有可复制提示词，适合有类似处境的女性读者。",
        "persona_tags": ["职场宝妈", "独立女性", "AI学习", "真实经历"],
        "example": {
            "title": "带娃的碎片时间，我找到了一个还不错的用法",
            "body": "孩子睡着了，我只有30分钟。\n\n我试了一件事：让AI帮我整理本周的工作记录。\n\n1. 打开Claude，粘贴会议笔记\n2. 输入提示词：帮我整理成周报格式，包含完成事项、遇到的问题、下周计划\n3. 修改了两处它不了解背景的地方\n\n卡在哪里：格式第一次不对，重新说了一遍需求才对。\n\n对我最值的：以前写周报要一小时，现在20分钟搞定。\n\n你现在最想让AI帮你省哪一步？A 写周报，B 做选题，C 整理资料，D 学新东西\n\n#AI工具 #职场宝妈 #AI学习",
        },
    },
    "wechat_ai_writing_workshop_v1": {
        "name": "公众号·言情玄幻连载",
        "channel": "wechat",
        "content_kind": "fiction_serial",
        "file": "shared/16_ai_writing_workshop.md",
        "description": "直接生成言情/玄幻连载小说章节：有故事名、章节名、人物欲望、冲突推进、情绪张力和结尾悬念。不输出AI写作教程、提示词拆解或创作手记。",
        "persona_tags": ["连载小说", "言情", "玄幻", "悬念", "故事结构"],
        "example": {
            "title": "烬月灯 · 第一章 她听见神骨在说话",
            "summary": "一个被逐出师门的少女，在满城灯会那夜听见了禁地神骨的声音。她以为那是救命，后来才知道那是债。",
            "excerpt": "## 第一章 她听见神骨在说话\n\n子时的灯一盏接一盏灭下去，唯独禁地深处那盏青灯亮了。\n\n沈照雪站在雨里，掌心的伤口还在渗血……",
        },
    },
    "xiaohongshu_ai_writing_workshop_v1": {
        "name": "小红书·言情玄幻连载",
        "channel": "xiaohongshu",
        "content_kind": "fiction_serial",
        "file": "shared/16_ai_writing_workshop.md",
        "description": "把公众号连载压缩成小红书短篇钩子：第一行抓人、250-350字故事片段、下期悬念或读者投票。不写AI写作方法。",
        "persona_tags": ["连载小说", "言情", "玄幻", "短篇钩子"],
        "example": {
            "title": "她听见神骨说话",
            "body": (
                "“别回头。”\n\n"
                "禁地里的声音第二次响起时，沈照雪已经走到了青灯前。\n\n"
                "雨水顺着她的袖口往下滴，掌心那道伤口却没有合上。她看见灯芯里有一截白骨，骨上刻着她的名字。\n\n"
                "师父说她天生命薄，不该修道。\n\n"
                "可那截神骨说：你不是命薄，你是命太重。\n\n"
                "下一章：她要不要把青灯带走？A 带走，B 留下\n\n"
                "#连载小说 #玄幻言情 #故事"
            ),
        },
    },
    "wechat_tool_research_v1": {
        "name": "公众号·工具研究说明书",
        "channel": "wechat",
        "content_kind": "tool_research",
        "file": "shared/14_tool_research_playbook.md",
        "description": "把一个具体工具讲清楚：它是什么、解决什么问题、适合谁、怎么安装、怎么上手、怎么进阶。",
        "persona_tags": ["工具研究", "教程", "实操"],
        "example": {
            "title": "Trae 是什么？新手安装和上手指南",
            "summary": "这不是工具新闻，而是一份给完全不了解 Trae 的新手看的说明书：先判断适不适合你，再决定要不要安装。",
            "excerpt": "## 先说清楚：Trae 到底是干什么的\n\n## 它解决什么问题\n\n## 新手安装前先检查这几件事",
        },
    },
    "xiaohongshu_tool_research_v1": {
        "name": "小红书·工具研究说明书",
        "channel": "xiaohongshu",
        "content_kind": "tool_research",
        "file": "shared/14_tool_research_playbook.md",
        "description": "适合工具种草和教程：先讲清楚工具本身，再给安装、上手、进阶和避坑清单。",
        "persona_tags": ["工具研究", "教程", "实操"],
        "example": {
            "title": "Trae新手先看这篇",
            "body": "Trae 不是一个普通文档工具，它更像 AI 编程助手。\n\n适合：想用 AI 辅助写代码、改代码、理解项目的新手。\n\n安装前先确认：系统版本、官网来源、账号登录、模型权限。\n\n#AI工具 #Trae教程",
        },
    },
    "wechat_tool_deep_review_v1": {
        "name": "公众号·AI工具深度实测",
        "channel": "wechat",
        "content_kind": "tool_deep_review",
        "file": "shared/15_tool_deep_review.md",
        "description": "按工具实测长文写法输出：是什么、安装、基础使用、进阶玩法、避坑、对比和结论。",
        "persona_tags": ["工具实测", "安装教程", "深度教程"],
        "example": {
            "title": "Trae 零基础上手：安装、配置和第一个项目怎么跑",
            "summary": "这篇不是简单介绍 Trae，而是给零基础读者看的实测教程：先判断适不适合，再照着完成安装和第一个练习。",
            "excerpt": "## 先说结论\n\n## Trae 是什么\n\n## 安装前先检查\n\n## 新手第一次这样用\n\n## 和同类工具怎么选",
        },
    },
    "xiaohongshu_tool_deep_review_v1": {
        "name": "小红书·AI工具深度实测",
        "channel": "xiaohongshu",
        "content_kind": "tool_deep_review",
        "file": "shared/15_tool_deep_review.md",
        "description": "把工具实测长文压缩成可收藏笔记：适合谁、安装检查、上手步骤、提示词和避坑。",
        "persona_tags": ["工具实测", "教程", "可收藏"],
        "example": {
            "title": "Trae新手安装前先看",
            "body": "Trae 适合想用 AI 辅助写代码、理解项目的人。\n\n安装前先查：官网来源、系统支持、账号登录、模型权限、数据权限。\n\n新手第一步：别打开重要项目，先拿测试文件夹练习。\n\n#AI工具 #Trae教程",
        },
    },
}

# 预设主题组，前端展示为可点击的 Chip
# 围绕 IP 定位：独立女性/职场宝妈/AI学习开发者/自媒体博主
# 4 大内容支柱：工具教程 / AI学习心得 / AI提效 / AI辅助创作
PRESET_TOPICS = [
    {
        "id": "cursor_beginner",
        "label": "Cursor新手避坑",
        "query": "Cursor AI IDE beginner mistakes tips workflow 2026 cursor新手使用技巧踩坑",
    },
    {
        "id": "claude_skill_prompt",
        "label": "Claude Skill提示词",
        "query": "Claude skill system prompt writing best practices 2026 如何写高质量Claude skill提示词",
    },
    {
        "id": "ai_novel_serial",
        "label": "AI写连载小说",
        "query": "AI fiction writing serial novel chapter generation Claude 2026 AI辅助写玄幻情感连载小说",
    },
    {
        "id": "working_mom_ai",
        "label": "职场宝妈AI效率",
        "query": "AI productivity tools working mom fragmented time management 2026 职场妈妈用AI利用碎片时间提效",
    },
    {
        "id": "vibe_coding_zero",
        "label": "零基础Vibe Coding",
        "query": "vibe coding no programming experience beginner cursor windsurf 2026 零基础用AI写代码实战",
    },
    {
        "id": "ai_learning_journal",
        "label": "学AI真实踩坑",
        "query": "AI learning journey beginner real mistakes pitfalls growth 2026 普通人学AI的真实经历踩坑记录",
    },
    {
        "id": "xiaohongshu_ai_workflow",
        "label": "小红书AI发布流程",
        "query": "xiaohongshu content creation AI workflow automation tools 2026 小红书AI辅助内容创作全流程",
    },
    {
        "id": "ai_tools_2026",
        "label": "2026最新AI工具",
        "query": "AI tools new releases 2026 latest models features 最新AI工具发布动态",
    },
]


USER_SKILLS_FILE = SKILLS_DIR / "user_skills.json"


def _load_user_skills() -> dict[str, Any]:
    if USER_SKILLS_FILE.exists():
        try:
            return json.loads(USER_SKILLS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"skills": {}, "deleted": []}


def _save_user_skills(data: dict[str, Any]) -> None:
    USER_SKILLS_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def list_channel_skills() -> list[dict[str, Any]]:
    user_data = _load_user_skills()
    deleted = set(user_data.get("deleted", []))
    output = []
    for skill_id, metadata in CHANNEL_SKILLS.items():
        if skill_id in deleted:
            continue
        skill_path = SKILLS_DIR / metadata["file"]
        output.append(
            {
                "id": skill_id,
                "name": metadata["name"],
                "channel": metadata["channel"],
                "file": metadata["file"],
                "description": metadata["description"],
                "persona_tags": metadata.get("persona_tags", []),
                "content_kind": _skill_content_kind(skill_id),
                "example": metadata.get("example", {}),
                "configured": skill_path.exists(),
                "builtin": True,
            }
        )
    for skill_id, metadata in user_data.get("skills", {}).items():
        if skill_id in deleted:
            continue
        skill_path = SKILLS_DIR / metadata["file"]
        output.append(
            {
                "id": skill_id,
                "name": metadata["name"],
                "channel": metadata["channel"],
                "file": metadata["file"],
                "description": metadata.get("description", ""),
                "persona_tags": metadata.get("persona_tags", []),
                "content_kind": _skill_content_kind(skill_id),
                "example": metadata.get("example", {}),
                "configured": skill_path.exists(),
                "builtin": False,
            }
        )
    return output


def add_user_skill(
    skill_id: str,
    name: str,
    channel: str,
    file_rel: str,
    description: str = "",
    persona_tags: list[str] | None = None,
    content_kind: str = "",
) -> None:
    normalized_kind = str(content_kind or "").strip()
    if not normalized_kind:
        normalized_kind = "xiaohongshu_note" if channel == "xiaohongshu" else "wechat_article"
    data = _load_user_skills()
    data.setdefault("skills", {})[skill_id] = {
        "name": name,
        "channel": channel,
        "file": file_rel,
        "description": description,
        "persona_tags": persona_tags or [],
        "content_kind": normalized_kind,
        "example": {},
    }
    data.setdefault("deleted", [])
    if skill_id in data["deleted"]:
        data["deleted"].remove(skill_id)
    _save_user_skills(data)


def delete_user_skill(skill_id: str) -> bool:
    data = _load_user_skills()
    data.setdefault("deleted", [])
    if skill_id not in data["deleted"]:
        data["deleted"].append(skill_id)
    _save_user_skills(data)
    return True


def load_skill_content(skill_id: str) -> str:
    user_data = _load_user_skills()
    metadata = CHANNEL_SKILLS.get(skill_id) or user_data.get("skills", {}).get(skill_id)
    if not metadata:
        return ""
    skill_path = SKILLS_DIR / metadata["file"]
    if not skill_path.exists():
        return ""
    return skill_path.read_text(encoding="utf-8", errors="replace").strip()


def _skill_content_kind(skill_id: str) -> str:
    """Return the content family a channel skill is allowed to generate."""
    normalized = str(skill_id or "").strip()
    metadata = CHANNEL_SKILLS.get(normalized) or _load_user_skills().get("skills", {}).get(normalized) or {}
    explicit = str(metadata.get("content_kind") or "").strip()
    if explicit:
        return explicit
    if "ai_writing_workshop" in normalized:
        return "fiction_serial"
    if "tool_deep_review" in normalized:
        return "tool_deep_review"
    if "tool_research" in normalized:
        return "tool_research"
    if "ai_growth_diary" in normalized:
        return "growth_diary"
    if "operator_flywheel" in normalized or "flywheel" in normalized:
        return "operator_flywheel"
    if "xiaohongshu_images" in normalized:
        return "xiaohongshu_image_cards"
    if normalized.startswith("xiaohongshu_"):
        return "xiaohongshu_note"
    if normalized.startswith("wechat_"):
        return "wechat_article"
    return "custom"


def _skill_family(kind: str) -> str:
    if kind in {"tool_deep_review", "tool_research"}:
        return "tool_tutorial"
    if kind == "fiction_serial":
        return "fiction_serial"
    if kind == "growth_diary":
        return "growth_diary"
    if kind == "operator_flywheel":
        return "operator_flywheel"
    return "general"


def _skill_type_contract(skill_id: str, channel: str) -> str:
    kind = _skill_content_kind(skill_id)
    if kind == "fiction_serial":
        return (
            f"【{channel} 当前 Skill 类型：连载小说】\n"
            "- 只能写小说正文或连载预告，禁止写AI创作教程、提示词拆解、工具测评、表格清单。\n"
            "- 必须有具体人物、目标、阻碍、关系张力和结尾悬念。\n"
            "- 如果原始素材是工具/资讯，只把它当灵感，不要照着写成工具文章。"
        )
    if kind in {"tool_deep_review", "tool_research"}:
        return (
            f"【{channel} 当前 Skill 类型：工具教程/实测】\n"
            "- 只能写工具说明、安装、实操、避坑、对比和结论，禁止写小说、情绪散文或成长日记。\n"
            "- 必须解释：它是什么、解决什么问题、适合谁、怎么安装/上手、哪里需要核验。\n"
            "- 操作步骤要具体到点哪里、输入什么、看到什么算成功。"
        )
    if kind == "growth_diary":
        return (
            f"【{channel} 当前 Skill 类型：AI成长实录】\n"
            "- 只能写真实使用经历：具体场景、做了什么、卡在哪里、怎么绕过、带来什么变化。\n"
            "- 禁止写成工具百科、新闻搬运、小说或纯观点鸡汤。"
        )
    if kind == "operator_flywheel":
        return (
            f"【{channel} 当前 Skill 类型：运营飞轮/实用价值】\n"
            "- 只能写普通人如何把一个信息变成可重复动作，强调省时、省力、复盘和长期积累。\n"
            "- 禁止写成安装教程、小说、纯资讯摘要。"
        )
    if kind == "xiaohongshu_note":
        return (
            f"【{channel} 当前 Skill 类型：小红书知识笔记】\n"
            "- 只能写短标题、强钩子、要点、互动和话题标签，禁止长篇公众号结构。"
        )
    return (
        f"【{channel} 当前 Skill 类型：通用内容】\n"
        "- 严格按当前 Skill 文件里的结构写，不借用其他 Skill 的栏目、语气和禁词。"
    )


def _build_output_format(tags_str: str, only_wechat: bool, only_xhs: bool) -> str:
    wechat_part = """{
  "wechat": {
    "title": "公众号文章标题",
    "summary": "文章摘要（1句话，40-80字）",
    "markdown": "完整公众号文章（Markdown格式，严格按照公众号 Skill 规则定义的结构和风格写作，用##分节）"
  }
}"""
    xhs_part = """{
  "xiaohongshu": {
    "title": "小红书标题（不超过20字）",
    "cover_text": "封面短句（不超过12字）",
    "body": "小红书正文（严格按照小红书 Skill 规则写作，结尾附话题标签）\\n\\n""" + tags_str + """",
    "card_pages": [
      {"title": "封面标题", "body": "封面一句话说明", "kind": "cover"},
      {"title": "01 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"},
      {"title": "02 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"},
      {"title": "03 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"}
    ]
  }
}"""
    both_part = """{
  "wechat": {
    "title": "公众号文章标题",
    "summary": "文章摘要（1句话，40-80字）",
    "markdown": "完整公众号文章（Markdown格式，严格按照公众号 Skill 规则定义的结构和风格写作，用##分节）"
  },
  "xiaohongshu": {
    "title": "小红书标题（不超过20字）",
    "cover_text": "封面短句（不超过12字）",
    "body": "小红书正文（严格按照小红书 Skill 规则写作，结尾附话题标签）\\n\\n""" + tags_str + """",
    "card_pages": [
      {"title": "封面标题", "body": "封面一句话说明", "kind": "cover"},
      {"title": "01 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"},
      {"title": "02 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"},
      {"title": "03 要点标题（10字内）", "body": "要点说明（50-80字）", "kind": "content"}
    ]
  }
}"""
    if only_wechat:
        return wechat_part
    if only_xhs:
        return xhs_part
    return both_part


def _validate_skill_output(skill_id: str, channel: str, content: str) -> None:
    kind = _skill_content_kind(skill_id)
    text = str(content or "")
    if not text.strip():
        raise ValueError(f"{channel} 输出为空。")
    if kind == "fiction_serial":
        forbidden_patterns = [
            r"我让\s*AI\s*写",
            r"AI原版",
            r"我的修改",
            r"提示词",
            r"这段是怎么写出来",
            r"小说片段",
            r"创作手记",
            r"方法论",
            r"安装前",
            r"官网入口",
            r"适合谁",
            r"\|.+\|.+\|",
        ]
        if any(re.search(pattern, text, flags=re.I) for pattern in forbidden_patterns):
            raise ValueError(f"{channel} 选择的是连载小说 Skill，但输出跑偏为教程/拆解结构。")
        if channel == "wechat":
            plain_story = re.sub(r"#+\s*", "", text)
            plain_story = re.sub(r"\s+", "", plain_story)
            if len(plain_story) < 800:
                raise ValueError("公众号连载小说正文过短。")
    if kind in {"tool_deep_review", "tool_research"}:
        if re.search(r"第[一二三四五六七八九十]+章|师门|神骨|禁地|他低声说|她没有", text):
            raise ValueError(f"{channel} 选择的是工具 Skill，但输出跑偏为小说。")
    if kind == "growth_diary" and re.search(r"第[一二三四五六七八九十]+章|神骨|禁地", text):
        raise ValueError(f"{channel} 选择的是成长实录 Skill，但输出跑偏为小说。")


def _load_jianghushuo_lens() -> str:
    skill_path = SKILLS_DIR / "jianghushuo-perspective.md"
    if not skill_path.exists():
        return (
            "姜胡说式内容判断：先给结论，不堆资料；把问题拆成极简单动作；"
            "用'不是X而是Y'提出观点；最后给一个今天就能做的动作。"
        )
    content = skill_path.read_text(encoding="utf-8", errors="replace")
    wanted = [
        "赚钱 = 极简单的动作 × 大量重复。",
        "行动飞轮：写→拍→盘，构成自我增长闭环。",
        "极简行动公式：赚钱 = 极简单的动作 × 大量重复。",
        "幸运表面积：被更多人看到 = 更多好运。",
        "圈层套利：你觉得简单的事，对别人可能很难。换个圈子，价值就变了。",
        "系统碾压纪律：不是你的意志力有问题，是你的系统有问题。",
        "不是X而是Y",
        "免费内容质量 > 市面收费课 → 自然建立信任",
        "开场钩子→痛点→方案（通常3步）→金句收尾",
    ]
    found = [line.strip("- **`> \t") for line in content.splitlines() if any(token in line for token in wanted)]
    if not found:
        return content[:1200]
    return "\n".join(found[:18])


def _compact(value: Any, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].strip()


def _paragraphs(content: str) -> list[str]:
    parts = [
        re.sub(r"\s+", " ", item).strip(" -")
        for item in re.split(r"\n+|(?<=[。！？!?])", content)
    ]
    return [item for item in parts if len(item) >= 4]


_TOOL_RESEARCH_STRONG_MARKERS = (
    "安装",
    "教程",
    "使用说明",
    "配置",
    "下载",
    "官网",
    "install",
    "setup",
    "guide",
    "tutorial",
)

_TOOL_RESEARCH_SOFT_MARKERS = ("怎么用", "上手", "使用", "入门")

_TOOL_RESEARCH_SPECIFIC_TOOLS = (
    "cursor",
    "trae",
    "claude code",
    "claude",
    "notebooklm",
    "windsurf",
    "gemini",
    "chatgpt",
    "copilot",
    "perplexity",
    "midjourney",
    "manus",
    "lovable",
    "replit",
    "bolt",
    "kimi",
    "豆包",
    "通义",
    "通义千问",
    "抬耳",
)

_KNOWN_OFFICIAL_URLS = {
    "trae": "https://www.trae.ai/",
    "cursor": "https://www.cursor.com/",
    "claude code": "https://docs.anthropic.com/en/docs/claude-code/overview",
    "claude": "https://claude.ai/",
    "chatgpt": "https://chatgpt.com/",
    "notebooklm": "https://notebooklm.google.com/",
    "windsurf": "https://windsurf.com/",
    "gemini": "https://gemini.google.com/",
    "copilot": "https://github.com/features/copilot",
    "perplexity": "https://www.perplexity.ai/",
}


def _is_tool_research_request(title: str, source_text: str, source_type: str) -> bool:
    corpus = f"{title} {source_text} {source_type}".lower()
    has_strong_marker = any(marker in corpus for marker in _TOOL_RESEARCH_STRONG_MARKERS)
    has_specific_tool = any(marker in corpus for marker in _TOOL_RESEARCH_SPECIFIC_TOOLS)
    has_soft_marker = any(marker in corpus for marker in _TOOL_RESEARCH_SOFT_MARKERS)
    return has_strong_marker or (has_specific_tool and has_soft_marker)


def _infer_tool_name(title: str, source_text: str) -> str:
    combined = f"{title}\n{source_text}"
    known = [
        "Trae",
        "Cursor",
        "Claude Code",
        "Claude",
        "ChatGPT",
        "NotebookLM",
        "Windsurf",
        "Gemini",
        "Kimi",
        "豆包",
        "通义千问",
    ]
    lower_combined = combined.lower()
    for name in known:
        if name.lower() in lower_combined:
            return name
    cleaned = re.sub(r"(安装|install|教程|说明|使用|怎么用|指南|资讯检索|AI最新资讯日报|\d{4}-\d{2}-\d{2})+", "", title, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ：:-")
    return _compact(cleaned or "这个工具", 24)


def _evidence_lines(source_text: str, tool_name: str = "", limit: int = 6) -> list[str]:
    lines: list[str] = []
    tool_lines: list[str] = []
    skip_prefixes = (
        "按你的要求检索",
        "以下内容来自",
        "适合继续转成",
        "今天发生了什么",
        "这对普通人意味着什么",
        "我准备怎么用",
        "写在最后",
        "请",
        "帮我",
        "我想",
    )
    skip_contains = (
        "请生成",
        "帮我把",
        "帮我生成",
        "小白能照着做",
        "零基础上手",
        "安装、配置和第一个任务教程",
    )
    tool_token = str(tool_name or "").lower().strip()
    for raw in str(source_text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" -")
        if len(line) < 4:
            continue
        if line in {"【检索资料】", "检索资料"}:
            continue
        if any(line.startswith(prefix) for prefix in skip_prefixes):
            continue
        if any(marker in line for marker in skip_contains):
            continue
        if any(marker in line for marker in ("无关的", "不应该混进", "不应混进")):
            continue
        if line.startswith("http"):
            line = f"来源链接：{line}"
        compacted = _compact(line, 240)
        if tool_token and tool_token in line.lower() and compacted not in tool_lines:
            tool_lines.append(compacted)
        elif compacted not in lines:
            lines.append(compacted)
        if len(tool_lines) >= limit:
            break
    if tool_lines:
        return tool_lines[:limit]
    return lines[:limit]


def _extract_urls(source_text: str) -> list[str]:
    urls: list[str] = []
    for raw_url in re.findall(r"https?://[^\s)）】\]。；;，,]+", str(source_text or "")):
        url = raw_url.rstrip(".")
        if url not in urls:
            urls.append(url)
    return urls


def _official_url_for_tool(tool_name: str, source_text: str) -> str:
    lower_name = str(tool_name or "").lower()
    for key, url in _KNOWN_OFFICIAL_URLS.items():
        if key in lower_name:
            return url
    urls = _extract_urls(source_text)
    if urls:
        return urls[0]
    return ""


def _build_tool_research_fallback(
    *,
    source_text: str,
    title: str,
    summary: str,
    hashtags: list[str],
) -> dict[str, Any]:
    tool_name = _infer_tool_name(title, source_text)
    evidence_items = _evidence_lines(source_text, tool_name=tool_name)
    evidence = "\n".join(f"- {item}" for item in evidence_items) or "- 当前资料不足，需要继续核验官方说明。"
    official_url = _official_url_for_tool(tool_name, source_text)
    official_line = official_url or "没有抓到官方链接，先不要按第三方链接安装。"
    final_title = _compact(f"{tool_name} 零基础上手：安装、配置和第一个任务", 64)
    wechat_summary = _compact(
        f"{tool_name} 上手前先做 4 项核验：官方入口、系统支持、账号额度、文件权限；再用测试文件夹跑一个最小任务。",
        150,
    )
    wechat_markdown = f"""# {final_title}

我会先测 {tool_name}，是因为做看懂项目、整理资料、写教程这类重复工作时，最怕两件事：入口找错、权限给大。还没跑通就把真实资料丢进去，是新手最常踩的坑。

下载之前先做这张检查表，通过后再进行下一步：

| 先查什么 | 怎么判断 |
| --- | --- |
| 官方入口 | 只从官网或官方文档进，不用网盘包、论坛包、陌生下载站 |
| 系统支持 | 看清支持 Windows、macOS、Linux、Web 还是插件形式 |
| 账号额度 | 找 Account / Billing / Usage，确认免费额度和付费规则 |
| 文件权限 | 要打开本地文件夹时，只授权测试文件夹，不给桌面或私人目录 |

## {tool_name} 是什么，适合谁

{tool_name} 可以先理解成一个 AI 工作助手：把陌生内容翻译成人话、拆出下一步、生成说明草稿，让你知道先做什么、哪里要自己判断。

适合：想用 AI 辅助写代码、整理资料、写教程、理解项目的人。

不适合：期待装完就自动解决所有问题的人；不愿意检查权限、账号和数据风险的人。

## 安装和上手步骤

### 第一步：确认官方入口

操作：在浏览器里打开 {official_line}，地址栏核对域名和官网一致。

你会看到什么：官网首页或产品介绍页，带有 Download、Get Started、Sign in 等入口按钮。

卡住怎么办：打不开先换网络或浏览器，不要从搜索广告位或陌生下载站进入。

### 第二步：下载安装

操作：点官网的 Download、Get Started 或对应系统版本链接，按提示完成安装或登录。

你会看到什么：`.exe` / `.dmg` 安装包，或直接进入 Web 工作台 / 插件商店页面。

卡住怎么办：系统不匹配先不要硬装；登录失败先看是否需要验证码、邮箱或地区要求。

### 第三步：配置账号和 API Key

操作：安装后打开 Settings / Account / API Keys 页面，填入 API Key 或完成账号登录。

你会看到什么：账号详情、额度余量或 API Key 输入框。

长期使用前还要确认：
- 模型选择：到 Model 或 Settings 页面看默认模型是什么
- 自动修改开关：Auto Apply / Agent Mode 新手建议先关闭
- 终端权限：第一次不要让它自动执行安装、删除、发布类命令

卡住怎么办：Key 是私密凭证，不要截图或放进代码仓库；额度不足先查官网 Billing 页面。

### 第四步：新建安全测试文件夹

操作：桌面新建 `{tool_name}-test` 文件夹，里面只放一个 `README.md`，写三行：我想解决什么问题、我卡在哪里、我希望输出什么。

你会看到什么：{tool_name} 里能看到测试文件和输入框。

卡住怎么办：不要打开重要项目或客户资料，只授权这个测试文件夹。

### 第五步：输入第一条提示词

操作：打开 {tool_name} 导入测试文件夹，复制下面这句话发给它：

> 我是新手，请先不要修改文件。请用大白话解释这个文件夹里有什么、下一步应该先做哪个最小动作。请列出风险，不确定的地方标注需要核验。

成功标志：输出里有它看到的信息、建议步骤、风险提醒。如果它直接开始写代码，补一句：先暂停，不要执行，只做解释和计划。

## 卡住了怎么排查

| 现象 | 怎么处理 |
| --- | --- |
| 官网打不开 | 确认链接来自官方，换网络或浏览器，不要下载陌生安装包 |
| 下载按钮找不到 | 找 Download / Get Started / Try / Sign in，有些工具先让你登录才能下载 |
| 登录失败 | 检查验证码、邮箱、地区限制、浏览器插件拦截 |
| 模型不可用 | 去 Settings / Account / Usage 看是否需要选模型或开通额度 |
| 文件权限弹窗 | 只授权测试文件夹，不要一次授权整个桌面 |
| 输出胡编 | 要求它列证据来源，涉及价格和官方承诺时回官网核验 |
| 改动太大 | 让它先给计划再逐步执行，每次只允许改一个文件 |

## 最后

{tool_name} 可以试，但不要直接拿真实项目试。今天只做一件事：用测试文件夹跑完解释、列计划、做一个小改动、复盘这个最小流程。

你现在最想让 AI 帮你省哪一步？A 看懂项目，B 整理资料，C 写教程，D 排查报错。
"""
    tags = []
    for tag in hashtags or ["AI工具", "工具教程", "普通人学AI"]:
        value = re.sub(r"[#\s]+", "", str(tag or "")).strip()
        if value and value not in tags:
            tags.append(value[:18])
    xhs_title = _compact(f"{tool_name}新手先看", 20)
    xhs_body = "\n\n".join(
        [
            f"{tool_name} 到底能干什么？",
            f"我会研究 {tool_name}，是因为我经常卡在一个很具体的动作：资料看不懂、项目不敢动、教程写不细，不知道能不能让 AI 先帮我拆第一步。",
            f"{tool_name} 对普通人的意义，不是参数多不多，而是能不能先帮你把陌生内容讲明白，再拆成一个可测试的小动作。",
            "适合谁：想用AI辅助学习、整理资料、写教程、理解项目的人。",
            f"官方入口：{official_line}",
            "安装前先检查：\n1. 域名是不是官方\n2. 系统是否支持（Windows/macOS/Linux/Web）\n3. 是否需要账号/网络环境\n4. 免费额度和付费规则（以官网当前页面为准）\n5. 是否会读取本地文件或上传资料",
            "小白操作步骤：\n1. 打开官方链接\n2. 找 Download / Get Started\n3. 选择自己的系统版本\n4. 安装后登录账号\n5. 先拿测试文件夹或一小段文字试用",
            "10分钟实操：\n1. 桌面新建一个测试文件夹\n2. 放一个README，写下你想解决的问题\n3. 打开工具导入测试文件夹\n4. 先问它【不要修改，只解释和列计划】\n5. 再让它只改一处或生成一个清单\n6. 记录哪里省时间、哪里还要人工判断",
            "卡住排查：\n官网打不开就先核验域名；登录失败看验证码和账号限制；模型不可用看额度；弹出文件权限时只授权测试文件夹；输出胡编就要求它列证据。",
            "截图建议：\n1. 官网入口：确认域名和下载入口\n2. 下载按钮：确认该点 Download 还是 Get Started\n3. 登录/工作台：首页是否进入可操作界面\n4. 第一个测试任务：确认它先解释和列计划",
            "可复制提示词：\n【我是完全新手，请用大白话告诉我这个工具是干什么的、适合谁、怎么开始用、有哪些坑。没有证据的信息请标注需要核验。】",
            "你现在最想让 AI 帮你省哪一步？A 看懂项目，B 整理资料，C 写教程，D 排查报错。",
            " ".join(f"#{tag}" for tag in tags[:6]),
        ]
    )
    card_pages = [
        {"title": xhs_title, "body": f"先拿一个真实小任务试 {tool_name}：看懂项目、整理资料、写教程或排查报错。", "kind": "cover"},
        {"title": "01 它是什么", "body": f"别先背功能名。先看 {tool_name} 能不能把陌生内容讲明白，并拆出下一步。", "kind": "content"},
        {"title": "02 适合谁", "body": "适合想用 AI 学习、整理资料、写教程、理解项目的人。", "kind": "content"},
        {"title": "03 官方入口", "body": f"优先从官方链接进入：{official_line}。不要从网盘、陌生论坛或不明安装包下载。", "kind": "content"},
        {"title": "04 小白步骤", "body": "打开官方链接，找 Download 或 Get Started，选择系统版本，登录后先跑一个测试任务。", "kind": "content"},
        {"title": "05 实操任务", "body": "桌面建测试文件夹，放 README，先让工具解释和列计划，再让它只改一处。", "kind": "content"},
        {"title": "06 卡住排查", "body": "打不开看官网域名，登录失败看验证码，模型不可用看额度，文件权限只给测试文件夹。", "kind": "content"},
    ]
    return {
        "wechat": {
            "skill_id": "wechat_tool_deep_review_v1",
            "title": final_title,
            "summary": wechat_summary,
            "markdown": wechat_markdown,
        },
        "xiaohongshu": {
            "skill_id": "xiaohongshu_tool_deep_review_v1",
            "image_skill_id": "xiaohongshu_images_v1",
            "title": xhs_title,
            "body": xhs_body,
            "cover_text": _compact(f"{tool_name}新手指南", 20),
            "card_pages": card_pages,
        },
    }


def _openai_chat(
    *,
    api_key: str,
    base_url: str,
    model: str,
    messages: list[dict[str, str]],
    temperature: float = 0.7,
    max_tokens: int = 2000,
) -> str:
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            return str(result["choices"][0]["message"]["content"]).strip()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"OpenAI API error {exc.code}: {body[:300]}") from exc


def build_channel_drafts_with_ai(
    *,
    source_text: str,
    title: str,
    summary: str,
    source_type: str,
    hashtags: list[str],
    wechat_skill_id: str = "wechat_article_v1",
    xiaohongshu_skill_id: str = "xiaohongshu_note_v1",
    story_id: str = "",
    target_channel: str = "",
) -> dict[str, Any]:
    """生成渠道内容草稿，优先用 OpenAI 按 Skill 规则生成，无 API Key 时降级到规则模板。"""
    uses_tool_deep_review = any(
        _skill_content_kind(skill_id) == "tool_deep_review"
        for skill_id in (wechat_skill_id, xiaohongshu_skill_id)
    )
    if uses_tool_deep_review and _is_tool_research_request(title, source_text, source_type):
        fallback = _build_tool_research_fallback(
            source_text=source_text,
            title=title,
            summary=summary,
            hashtags=hashtags,
        )
        fallback["wechat"]["skill_id"] = wechat_skill_id or fallback["wechat"]["skill_id"]
        fallback["xiaohongshu"]["skill_id"] = xiaohongshu_skill_id or fallback["xiaohongshu"]["skill_id"]
        return fallback

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip()
    model = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"

    # 自动检测可用的 OpenAI 兼容提供商（优先级：OpenAI → DeepSeek → Zhipu）
    if not api_key:
        deepseek_key = os.getenv("DEEPSEEK_API_KEY", "").strip()
        if deepseek_key:
            api_key = deepseek_key
            _ds_ep = os.getenv("DEEPSEEK_CHAT_ENDPOINT", "https://api.deepseek.com").strip()
            # 兼容完整 URL（含 /chat/completions 或 /v1/chat/completions）和 base URL 两种写法
            for _suffix in ("/chat/completions", "/v1/chat/completions", "/v1", "/"):
                if _ds_ep.endswith(_suffix):
                    _ds_ep = _ds_ep[: -len(_suffix)]
            base_url = _ds_ep
            model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    if not api_key:
        zhipu_key = os.getenv("ZHIPUAI_API_KEY", "").strip()
        if zhipu_key:
            api_key = zhipu_key
            base_url = "https://open.bigmodel.cn/api/paas"
            model = "glm-4-flash"

    if api_key:
        try:
            return _ai_generate_channel_drafts(
                source_text=source_text,
                title=title,
                summary=summary,
                hashtags=hashtags,
                wechat_skill_id=wechat_skill_id,
                xiaohongshu_skill_id=xiaohongshu_skill_id,
                api_key=api_key,
                base_url=base_url,
                model=model,
                story_id=story_id,
                target_channel=target_channel,
            )
        except Exception as _exc:  # noqa: BLE001
            import logging
            import traceback
            logging.getLogger(__name__).warning(
                "_ai_generate_channel_drafts failed (skill=%s): %s\n%s",
                wechat_skill_id, _exc, traceback.format_exc()
            )

    fallback = build_channel_drafts(
        source_text=source_text,
        title=title,
        summary=summary,
        source_type=source_type,
        hashtags=hashtags,
        wechat_skill_id=wechat_skill_id,
        xiaohongshu_skill_id=xiaohongshu_skill_id,
    )
    fallback["wechat"]["skill_id"] = wechat_skill_id or fallback["wechat"]["skill_id"]
    fallback["xiaohongshu"]["skill_id"] = xiaohongshu_skill_id or fallback["xiaohongshu"]["skill_id"]
    return fallback


def _ai_generate_channel_drafts(
    *,
    source_text: str,
    title: str,
    summary: str,
    hashtags: list[str],
    wechat_skill_id: str,
    xiaohongshu_skill_id: str,
    api_key: str,
    base_url: str,
    model: str,
    story_id: str = "",
    target_channel: str = "",
) -> dict[str, Any]:
    def _sanitize_skill(raw: str, max_chars: int = 2500) -> str:
        # 去掉 ``` 代码块（避免嵌入 prompt 后 AI 在 JSON 里生成反引号导致解析失败）
        cleaned = re.sub(r"```[\s\S]*?```", "[可复制提示词见下方]", raw)
        # 去掉重复换行
        cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
        return cleaned[:max_chars]

    wechat_skill_content = _sanitize_skill(
        load_skill_content(wechat_skill_id) or load_skill_content("wechat_article_v1")
    )
    xhs_skill_content = _sanitize_skill(
        load_skill_content(xiaohongshu_skill_id) or load_skill_content("xiaohongshu_note_v1")
    )

    tags_str = " ".join(f"#{t}" for t in (hashtags or ["AI工具", "普通人学AI"])[:6])

    wechat_kind = _skill_content_kind(wechat_skill_id)
    xhs_kind = _skill_content_kind(xiaohongshu_skill_id)
    wechat_family = _skill_family(wechat_kind)
    xhs_family = _skill_family(xhs_kind)
    families = {wechat_family, xhs_family}
    is_tool_tutorial = "tool_tutorial" in families
    is_growth_diary = "growth_diary" in families
    is_writing_workshop = "fiction_serial" in families
    is_flywheel = "operator_flywheel" in families
    jianghushuo_lens = _load_jianghushuo_lens() if (is_flywheel or is_growth_diary) else ""

    # ── 通用基础规则（所有 skill 都适用）──────────────────────
    base_rules = """语言规则：
- 文案主体必须使用中文，表达要像真人说话，不要翻译腔。
- AI工具名、产品名、英文缩写保留英文原名（Claude、ChatGPT、NotebookLM、API）；第一次出现英文缩写时用一句中文解释它是干什么的。
- 不复述资讯，不写"以下内容来自接口返回结果"这种废话。
- 标题禁止空泛，要让读者知道看完能解决什么问题。
- 不编造下载链接、价格、官方承诺、收益数字；信息不确定时写"建议自行核验"。
- 结尾互动问题必须具体可回答，优先用 A/B/C/D 选项；禁止"你怎么看""欢迎留言"。
- 正文里禁止出现"本文将包含""资料里没明确写出的部分我会标注"这类模板说明。"""

    # ── 工具教程专属规则 ──────────────────────────────────────
    tool_tutorial_rules = """工具教程专项规则：
- 写成高密度教程：开头直接给判断 → 安装前检查表格 → 官方链接 → 逐步安装 → 10分钟实操 → 配置检查 → 卡点排查 → 最后结论。
- 开头第一段只写"我为什么测它"（1-2句，连接一个具体麻烦），第一段后立刻进入安装前检查表格，不允许插入过渡段落。
- 操作步骤每一步写清：点哪里 / 输入什么 / 看到什么算成功 / 失败先查哪里。
- 中段必须插入1句真实踩坑经验，服务操作建议，不写成情绪故事。
- 官方入口、账号、费用、权限统一并入安装前检查表格，不单独成节。
- 最后结论控制在2段以内，第一段说是否值得试和今天最小动作，第二段只留1个具体互动问题。
- 公众号字数控制在1200-1800字。"""

    # ── AI成长实录专属规则 ────────────────────────────────────
    growth_diary_rules = (
        """AI成长实录规则类型：

【写作身份】：我是Haley，职场宝妈/软件开发者/AI学习者，把我真实用过的东西分享给有类似处境的女性。

【开头的关键检验】：
好的开头 = 一个具体场景/处境，读者能立刻对号入座
坏的开头 = "先说我的判断：" / "今天分享" / 工具介绍 / 讲道理

好开头示例：「那天孩子发烧，我请了半天假在家。他睡着后，我想起还有份周报没写，打开Claude抱着试试的心态——」
坏开头示例：「先说我的判断：这条资讯真正的价值，不是让你多记一个工具名，而是...」

【公众号8段结构（严格按此输出）】：
① 标题：写"我做了什么之后，发生了什么变化"——先写5个候选再选最好的
② 开头：一个具体场景（孩子睡着了/地铁上/下班后），不从工具介绍或讲道理开始
③ ## 我是怎么开始接触这个的
④ ## 我实际操作了什么（含完整可复制提示词）
⑤ ## 卡在哪里了，怎么解决的（必须有真实卡点，这让内容有可信度）
⑥ ## 现在它帮我省了什么 / 带来了什么变化（有时间感，比如"20分钟"而非"大大提升"）
⑦ ## 你今天可以试的一步（最小行动 + 完整可复制提示词）
⑧ ## 写给同样在路上的你（一句真实感受 + 选项式互动问题）

【小红书第一行】：让读者觉得"这是在说我"的具体处境，不从工具名或"今天分享"开始

【卡点段必须有的要素】：具体说明卡在哪里（不是"遇到了一些问题"）+ 怎么解决的（或绕过去的方法）"""
        if is_growth_diary
        else ""
    )

    # ── AI连载创作专属规则 ──────────────────────────────────
    writing_workshop_rules = (
        """连载小说规则类型：

【核心定位】：只输出故事。不说怎么写的，不讲提示词，不做教程，不写创作手记。

【公众号必须按此结构输出】：
① 标题：「[故事名] · 第X章 [副标题]」
② 故事正文（1200-1800字，这是全文唯一主体）
③ 结尾：下期暗示一句话 OR 读者投票「A [选项] 还是 B [选项]？」

【连载结构硬规则】：
- 第一段必须直接进入戏：异动、危险、重逢、误会、禁忌、追杀、婚约、神谕、旧物、伤口，至少出现一种。
- 本章必须有主角的具体目标，不能只是站着回忆或抒情。
- 本章必须出现阻碍：一个人、一条规矩、一个秘密、一种力量反噬或一次误会。
- 本章中段必须有一次关系碰撞：试探、拒绝、救人、误认、威胁、交易、靠近又退开。
- 结尾前必须出现新信息或反转，让主角失去一点安全感。
- 最后一句必须是悬念句，不能总结道理。

【故事质量要求（最高优先级）】：
- 情感类：用细节动作传递情绪，禁止写"她很难过/心痛"等情绪词；有具体场景；对话留白；有情节推进；结尾让人想看下一期
- 玄幻类：开场一句进入世界；世界观通过细节透出来不在正文解释；有节奏和停顿；结尾留悬念
- 质量底线：读完能说"写得好"或"想看下一期"，否则重写
- 正文字数不少于1200字

【禁止】：
× 教程结构、步骤说明、"提示词是这样的"
× "创作手记"、"AI方法论"、"我是怎么写的"、"我让AI写"、"AI原版"、"我的修改"
× 工具测评口吻、说教式结尾
× 故事正文少于800字
× 没有具体场景和人物
× 表格、清单、教程拆解、标题如"小说片段/这段是怎么写出来的"

【小红书】：第一行截取故事里最有张力的一句话，正文放250-350字精华片段 + 下期预告/投票"""
        if is_writing_workshop
        else ""
    )

    # ── 飞轮/运营观点专属规则（兼容旧 skill id）────────────
    flywheel_rules = (
        f"""运营飞轮规则类型：

【核心视角】：从普通职场人/自媒体人的真实使用视角出发，挖掘工具或资讯对普通人的深层实用价值。
不是发布通报，不是功能清单。核心问题只有一个：这件事能帮普通人在哪几件具体的事上省力、省时、做得更好？

【写作主轴（每篇选一个写深）】：
- 自媒体效率轴：这个工具如何改变"选题→写作→发布→复盘"流程，能省掉哪一步重复劳动？
- 职场提效轴：普通上班族怎么用它处理报告、会议记录、复杂文档、日常沟通？
- 学习效率轴：怎么用它更快看懂新领域、长文件、复杂系统？

【公众号必须按此7段结构输出，不能替换】：
① 标题：写"普通人用了之后什么变了"，不写工具名+功能介绍
② 开头：[我遇到的一个具体场景] + [今天我想分享的一个发现]（不从官方介绍或发布通报开始）
③ ## 它到底能帮普通人做什么：3-5个具体维度，每个维度写"场景→动作→结果"，不堆功能名称
④ ## 我是怎么开始用的：3步以内的最小启动路径（去哪里→第一步做什么→用什么测试）
⑤ ## 我踩过的坑 / 它的边界：诚实说明能做什么、不能替你做什么、什么时候会让你失望
⑥ ## 今天就做这一个动作：含可直接复制的提示词 + 期待结果
⑦ ## 写在最后：一句话长期视角 + 一个选项式互动问题

【格式禁令（最高优先级，违反即重写）】：
- 严禁出现：`### 第一步：` `### 第二步：` 等格式
- 严禁出现：安装前检查表格、"卡住了怎么排查"章节、下载安装步骤展开
- 严禁从工具的官方功能介绍角度开始写
- 工具内容不能写成安装教程，要写成"这个工具和普通人/自媒体人的关系"

【小红书结构】：
反常识钩子（第一行）→ 我的判断 → 适合谁（具体场景描述）→ 我怎么用（3步，具体）→ 避坑1条 → 可复制提示词 → 选项式互动问题

【接地气要求】：
- 像普通人给朋友分享一个发现，不像机构发布评测报告
- 每篇至少出现一处"我"的真实感受或踩坑（不是"我们"，是"我"）
- 结尾互动问题必须是具体选项，如"A 写开头，B 整理会议记录，C 看懂文档，D 做选题"

姜胡说式思考框架（只吸收方法，不模仿男性口吻，不自称姜胡说）：
{jianghushuo_lens}"""
        if is_flywheel
        else ""
    )

    general_article_rules = """通用深度文章规则类型：
- 公众号结构：开头钩子（我的具体困境/反直觉发现/和读者共同疑问） → 主体（工具类：是什么→我怎么用→对你的价值→我踩过的坑；资讯类：发生了什么→对普通人意味着什么→我的判断→你可以做的一件事） → 结尾CTA（互动/关注/行动引导之一）。
- 每完成2-3步后插入一句个人感受或踩坑。
- 总字数800-1500字。
- 不使用"### 第X步："格式，步骤用"1. 2. 3."或"**第一件事：**"等自然格式。"""

    def _family_rules(family: str) -> str:
        if family == "tool_tutorial":
            return tool_tutorial_rules
        if family == "growth_diary":
            return growth_diary_rules
        if family == "fiction_serial":
            return writing_workshop_rules
        if family == "operator_flywheel":
            return flywheel_rules
        return general_article_rules

    # ── 拼装 system prompt ────────────────────────────────────
    _only_wechat = target_channel == "wechat"
    _only_xhs = target_channel == "xiaohongshu"

    if _only_wechat:
        skill_type_block = f"""【公众号 Skill 绑定规则类型】
{_skill_type_contract(wechat_skill_id, "公众号")}
{_family_rules(wechat_family)}"""
    elif _only_xhs:
        skill_type_block = f"""【小红书 Skill 绑定规则类型】
{_skill_type_contract(xiaohongshu_skill_id, "小红书")}
{_family_rules(xhs_family)}"""
    else:
        skill_type_block = f"""【公众号 Skill 绑定规则类型】
{_skill_type_contract(wechat_skill_id, "公众号")}
{_family_rules(wechat_family)}

【小红书 Skill 绑定规则类型】
{_skill_type_contract(xiaohongshu_skill_id, "小红书")}
{_family_rules(xhs_family)}

关键要求：公众号输出只能服从公众号 Skill 的规则类型；小红书输出只能服从小红书 Skill 的规则类型。两边不要互相借用结构。"""

    account_context = (
        """【创作身份】
你是一位中文言情/玄幻连载小说作者和故事编辑。
目标读者：喜欢强情绪、强设定、强悬念的女性读者，读完这一章会想看下一章。
写作声音：小说正文，不是教程，不是自媒体经验分享，不解释AI怎么写。"""
        if wechat_family == "fiction_serial" and xhs_family == "fiction_serial"
        else """【账号人设】
我叫Haley，职场宝妈·软件开发者·AI学习者·自媒体博主。
目标读者：和我有类似处境的女性——上班、带娃、想学AI、想做自媒体，时间碎片化，不确定自己能不能做到。
写作声音：真实使用者，不是测评机构。用"我"，不用"我们"；有具体场景，不写空泛鸡汤。"""
    )

    thinking_context = (
        """【每次写作前，先完成内部故事设计（不输出）】
1. 本章类型：言情 / 玄幻 / 言情玄幻混合。
2. 本书核心钩子：一句话讲清主角、世界、禁忌和选择。
3. 本章主角目标：她/他这一章具体想要什么。
4. 本章阻碍：谁挡住她/他，阻碍带来什么代价。
5. 关系张力：两个人为什么互相吸引，又为什么不能轻易靠近。
6. 结尾悬念：最后一句停在答案揭开前一秒。"""
        if wechat_family == "fiction_serial" and xhs_family == "fiction_serial"
        else """【每次写作前，先完成内部思考（不输出）】
1. 读者今天在哪里？她是在孩子午睡时刷手机，还是下班后一个人刷到这篇？
2. 这篇文章触发的核心情绪是什么？（共鸣/解脱/好奇/归属，选一个主导情绪）
3. 金句是什么？有没有一句让人想截图的话？先想好它，再写全文。
4. 情绪弧线：开头被理解→中间真实起伏→结尾有"我也要试"的冲动。不能是平的。
5. 真实感来自哪里？有没有一个具体细节让人觉得"这是真实发生的"？"""
    )

    system_role = (
        "你是一位中文言情/玄幻连载小说作者。"
        if wechat_family == "fiction_serial" and xhs_family == "fiction_serial"
        else "你是一位中文内容创作专家，必须按每个渠道所选 Skill 的规则类型创作。"
    )

    system_prompt = f"""{system_role}

{account_context}

{thinking_context}

【去AI味（最高优先级）——违反此规则的内容必须重写】
禁用词：赋能、范式、颠覆、革命性、全面提升、深刻认识、受益匪浅、不言而喻
禁用句式：
× "通过这次经历，我深刻认识到..."
× "先说结论：[结论]，再说原因..."
× "这件事适合三类人：第一...第二...第三..."（汇报体，不是朋友说话）
× "让我们一起..."（只有"我"，没有"我们"）
× 结尾只问"你怎么看？欢迎留言"（必须给具体A/B/C/D选项）

{base_rules}

{skill_type_block}

请严格按照以下 Skill 规则的格式、结构和风格生成内容，Skill 规则优先于以上通用规则：

{"【公众号文章 Skill 规则】" + chr(10) + wechat_skill_content if not _only_xhs else ""}
{"【小红书笔记 Skill 规则】" + chr(10) + xhs_skill_content if not _only_wechat else ""}

输出格式：只输出合法 JSON，不加任何说明文字：
{_build_output_format(tags_str, _only_wechat, _only_xhs)}"""

    if wechat_family == "fiction_serial":
        # 注入故事档案上下文（连载续写）
        story_context_block = ""
        if story_id:
            try:
                from .story_db import build_story_context, next_chapter_number
                story_context_block = build_story_context(story_id)
                chapter_num_hint = next_chapter_number(story_id)
            except Exception:
                chapter_num_hint = 1
        else:
            chapter_num_hint = 1

        user_prompt = f"""请把以下内容当作连载小说的灵感种子，按照所选 Skill 分别生成公众号连载章节和小红书连载预告。

用户输入/标题：{title or "言情玄幻连载"}
补充摘要：{summary[:200] if summary else ""}

{story_context_block}

灵感素材：
{source_text[:2000]}

生成前内部自检（不要输出这些判断）：
1. 当前必须生成小说正文，不是AI写作教程，不是创作手记，不是提示词拆解。
2. 本章编号：第 {chapter_num_hint} 章。标题格式「[故事名] · 第{chapter_num_hint}章 [副标题]」。
3. 如果有故事档案，必须延续已有人物、世界观和悬念，不能推翻之前的设定。
4. 先确定故事名、章节名、类型、主角目标、阻碍、关系张力和章末悬念。
5. 公众号 markdown 只允许出现章节标题、故事正文、下期暗示/投票；禁止表格、教程小标题、"小说片段"、"这段是怎么写出来的"。
6. 小红书 body 第一行必须是故事里最有张力的一句话。"""
    else:
        user_prompt = f"""请根据以下内容，按照所选 Skill 的格式和风格分别生成公众号文章和小红书笔记：

标题：{title or "AI最新资讯"}
摘要：{summary[:200] if summary else ""}

原始内容：
{source_text[:3000]}

生成前内部自检（不要输出这些判断）：
1. 公众号当前规则类型：{wechat_kind}；小红书当前规则类型：{xhs_kind}。分别按自己的规则写，不要互相串格式。
2. 从原始内容提取确实信息；没有证据的地方写"建议核验"，不编造。
3. 确保公众号文章和小红书笔记有各自不同的结构和侧重点，不要互相复制。"""

    raw = _openai_chat(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.72,
        max_tokens=4000,
    )

    # 提取 JSON（兼容被 ``` 包裹的情况）
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"AI 返回内容不包含合法 JSON: {raw[:200]}")
    data = json.loads(json_match.group())

    wechat_data = data.get("wechat") or {}
    xhs_data = data.get("xiaohongshu") or {}

    final_title = _compact(str(wechat_data.get("title") or title or "今天的AI资讯"), 64)
    wechat_markdown = str(wechat_data.get("markdown") or "")
    if not _only_xhs:
        _validate_skill_output(wechat_skill_id, "wechat", wechat_markdown)
    xhs_title = _compact(str(xhs_data.get("title") or final_title), 20)
    xhs_body = str(xhs_data.get("body") or "")
    if not xhs_body:
        xhs_body = str(xhs_data.get("cover_text") or xhs_title)
    if not _only_wechat:
        _validate_skill_output(xiaohongshu_skill_id, "xiaohongshu", xhs_body)

    card_pages = xhs_data.get("card_pages") or []
    if not card_pages:
        card_pages = [{"title": xhs_title, "body": _compact(xhs_body, 100), "kind": "cover"}]

    result = {
        "wechat": {
            "skill_id": wechat_skill_id,
            "title": final_title,
            "summary": _compact(str(wechat_data.get("summary") or summary), 150),
            "markdown": wechat_markdown,
        },
        "xiaohongshu": {
            "skill_id": xiaohongshu_skill_id,
            "image_skill_id": "xiaohongshu_images_v1",
            "title": xhs_title,
            "body": xhs_body,
            "cover_text": _compact(str(xhs_data.get("cover_text") or xhs_title), 20),
            "card_pages": card_pages,
        },
    }

    # 连载故事：保存章节到 Supabase 并更新 story_bible
    import logging as _logging
    _log = _logging.getLogger(__name__)
    _log.info("story_id=%r wechat_family=%r", story_id, wechat_family)
    if story_id and wechat_family == "fiction_serial" and not _only_xhs:
        try:
            from .story_db import save_chapter, extract_and_update_bible, next_chapter_number
            _ch_hint = locals().get("chapter_num_hint")
            ch_num = _ch_hint if _ch_hint is not None else next_chapter_number(story_id)
            _log.info("saving chapter %s for story %s", ch_num, story_id)
            save_chapter(
                story_id=story_id,
                chapter_number=ch_num,
                title=final_title,
                content_markdown=wechat_markdown,
                content_xhs=xhs_body,
            )
            import threading
            t = threading.Thread(
                target=extract_and_update_bible,
                args=(story_id, wechat_markdown),
                kwargs={"api_key": api_key, "base_url": base_url, "model": model},
                daemon=True,
            )
            t.start()
            result["story_chapter_saved"] = ch_num
        except Exception as _save_exc:
            _log.warning("story chapter save failed: %s", _save_exc, exc_info=True)
            result["story_chapter_error"] = str(_save_exc)

    return result


def build_channel_drafts(
    *,
    source_text: str,
    title: str,
    summary: str,
    source_type: str,
    hashtags: list[str],
    wechat_skill_id: str = "wechat_tool_deep_review_v1",
    xiaohongshu_skill_id: str = "xiaohongshu_tool_deep_review_v1",
) -> dict[str, Any]:
    paragraphs = _paragraphs(source_text)
    if not paragraphs:
        paragraphs = [_compact(source_text, 500)]
    is_trend = source_type == "ai_trends"
    final_title = _compact(title, 64) or ("今天值得关注的 3 个变化" if is_trend else "这件事，我终于想明白了")
    wechat_kind = _skill_content_kind(wechat_skill_id)
    is_tool_skill = _skill_family(wechat_kind) == "tool_tutorial"
    is_growth_diary_skill = wechat_kind == "growth_diary"
    is_writing_workshop_skill = wechat_kind == "fiction_serial"

    if is_trend and is_tool_skill and _is_tool_research_request(final_title, source_text, source_type):
        return _build_tool_research_fallback(
            source_text=source_text,
            title=final_title,
            summary=summary,
            hashtags=hashtags,
        )

    # Growth diary fallback — persona-aware content instead of generic flywheel
    if is_growth_diary_skill:
        paragraphs = _paragraphs(source_text)
        core_info = _compact(paragraphs[0] if paragraphs else (summary or final_title), 200)
        tool_hint = _infer_tool_name(final_title, source_text)
        diary_title = _compact(f"我试了一下{tool_hint}，花了一个午休，发现了这件事", 48)
        diary_md = f"""# {diary_title}

孩子睡着的那段时间，我打开了电脑，想试试最近看到的这个东西：{tool_hint}。

## 我是怎么开始接触这个的

{core_info}

我当时将信将疑——不确定这对我有没有用。但我只有30分钟，就先试试。

## 我实际操作了什么

我把手头一个一直拖着没做的任务交给了它。提示词大概是这样：

【帮我把以下内容整理成一个可以直接用的格式，要简洁、具体，不要废话：[粘贴内容]】

## 卡在哪里了，怎么解决的

第一次给出的结果格式不是我想要的，重新描述了一遍需求才对。这让我意识到：给AI的指令越具体，结果越接近你要的。

## 现在它帮我省了什么

这件事以前要花我半小时，那次20分钟搞定了，还有10分钟陪孩子玩。

## 你今天可以试的一步

打开Claude或其他AI工具，把你最近最烦的一个重复任务粘贴进去，加上这句话：
【帮我把这个整理成可以直接用的格式，要简洁，不超过200字】

## 写给同样在路上的你

不是每次都完美，但每次试一下，就少踩一个坑。

你现在最想让AI帮你省哪一件事？A 写周报，B 做选题，C 整理资料，D 学新东西"""

        tags_norm = []
        for tag in hashtags or ["AI工具", "职场宝妈", "AI学习"]:
            v = re.sub(r"[#\s]+", "", str(tag)).strip()
            if v and v not in tags_norm:
                tags_norm.append(v[:18])
        xhs_body = (
            f"孩子睡着的30分钟，我试了一下{tool_hint}。\n\n"
            f"一句话评价：{core_info[:80]}\n\n"
            "我怎么用的：\n1. 打开工具，把任务描述清楚\n2. 加上「要简洁、具体、不废话」\n3. 第一次不对就重新描述\n\n"
            f"卡在哪里：格式第一次不对，重新说了才好。\n\n"
            "对我最值的：省了20分钟，还有时间陪孩子。\n\n"
            "你最想让AI帮你省哪件事？A 写周报，B 做选题，C 整理资料，D 学新东西\n\n"
            + " ".join(f"#{t}" for t in tags_norm[:5])
        )
        return {
            "wechat": {
                "skill_id": wechat_skill_id,
                "title": diary_title,
                "summary": f"一个职场宝妈用{tool_hint}做了一件事，花了一个午休，分享给同样在路上的你。",
                "markdown": diary_md,
            },
            "xiaohongshu": {
                "skill_id": xiaohongshu_skill_id,
                "image_skill_id": "xiaohongshu_images_v1",
                "title": _compact(f"我试了{tool_hint}这件事", 20),
                "body": xhs_body,
                "cover_text": _compact(f"试了{tool_hint}", 12),
                "card_pages": [
                    {"title": _compact(f"试了{tool_hint}", 12), "body": f"一个午休试了{tool_hint}，结果省了20分钟", "kind": "cover"},
                    {"title": "我怎么用的", "body": "描述清楚任务，加上「要简洁具体」，第一次不对就重新说", "kind": "content"},
                    {"title": "卡在哪里", "body": "格式第一次不对是正常的，重新描述需求就好", "kind": "content"},
                    {"title": "今天可以试", "body": "把你最烦的重复任务粘贴进去，让AI帮你整理成可用格式", "kind": "content"},
                ],
            },
        }

    # Writing workshop fallback — pure story, no tutorial
    if is_writing_workshop_skill:
        story_md = """# 烬月灯 · 第一章 她听见神骨在说话

满城灯火在子时同时熄灭。

只有禁地深处那一盏青灯还亮着，像一只没有闭上的眼。

沈照雪站在雨里，右手藏在袖中。掌心那道伤口是刚刚被戒尺打出来的，血顺着指缝往下滴，滴到石阶上，又很快被雨水冲散。

她没有喊疼。

师父说，沈照雪天生命薄，不该修道。师兄说，她这样的人留在玄清山，只会拖累别人。就连守门的小童递给她包袱时，也不敢看她的眼睛，只把那块写着“逐”字的木牌塞进她怀里。

她抱着包袱往山门外走，走到第九十九级石阶时，听见身后有人笑了一声。

“沈师妹，别回头。”那声音很轻，却像贴着耳骨落下，“你若回头，就真走不了了。”

沈照雪还是回了头。

山门上方，谢无咎撑着一把黑伞，站在雨幕里看她。他一身白衣没有沾半点水，腰间那枚玉牌晃了一下，上面刻着玄清山首徒的纹印。

三日前，也是这只手，把她从问心台上拽下来。

三日后，也是这张脸，亲眼看着她被逐出师门。

沈照雪把木牌攥紧，指节一点点发白。

“谢师兄放心。”她说，“我不回去。”

谢无咎没有接话。他只是看着她袖口渗出的血，眉心像是动了一下，又很快平下去。

雨声太密，沈照雪几乎以为自己看错了。

她转身继续下山。

可就在她踏出山门的那一刻，整座玄清山忽然震了一下。

青灯亮了。

那盏被封在禁地三百年的青灯，从来只在一个时候亮——神骨认主。

山上钟声大作。原本已经关上的山门轰然打开，数十道剑光从云中落下，长老们的声音压着雨声传来：“封山！所有弟子不得离开！”

沈照雪停在山门外。

她听见一个声音从很远的地方传来，像从骨头里醒过来。

“回来。”

那声音不是命令，却让她掌心的伤口忽然烧了起来。血没有再往下滴，而是在她手心里慢慢汇成一个细小的符纹。

谢无咎的伞落在地上。

他第一次失了分寸，几乎是瞬间掠到她面前，扣住她的手腕。

“你听见了什么？”他问。

沈照雪被他抓得发疼，却没有挣开。她看见他的眼底有一瞬间的慌乱，那慌乱不像担心，更像害怕某个秘密终于被她撞破。

她忽然明白，自己被逐出师门，也许不是因为命薄。

“我听见有人叫我回去。”她说。

谢无咎的手指收紧。

山门内，长老们已经赶到。所有人的目光都落在她手心那道符纹上，有震惊，有贪婪，也有说不清的恐惧。

掌门站在最前面，脸色比雨夜还沉。

“沈照雪，”他缓缓开口，“把手伸出来。”

沈照雪没有动。

她看向谢无咎。

三日前，她在问心台上被逼着认罪，所有人都说她偷了禁地钥匙。只有谢无咎走上来，替她挡下第一道雷刑。

他说：“她没有偷。”

可下一刻，他又亲手把那枚钥匙放进她的袖中。

那一瞬间，她才知道，有些救命不是救命，是把刀递得更近。

现在，那把刀又回到了她面前。

谢无咎低声说：“跟我走。”

“去哪？”

“禁地。”

沈照雪笑了一下。雨水从她睫毛上落下来，她看不清他的脸，只看见他握着她手腕的那只手，指骨紧得发白。

“谢师兄，”她问，“这一次，你是要救我，还是要把我送回去？”

谢无咎没有回答。

他身后的剑光已经逼近。

青灯的光从山腹深处透出来，照得整片雨夜泛起冷冷的蓝。沈照雪掌心的符纹越来越烫，像有什么东西要从皮肉里破出来。

那道声音第三次响起。

这一次，不止她听见了。

“把我的骨，还给我。”

下一章：沈照雪该跟谢无咎进禁地，还是当着所有人的面撕开掌门的谎言？A 进禁地，B 当场反击。"""

        tags_norm = []
        for tag in hashtags or ["连载小说", "情感故事", "AI写作"]:
            v = re.sub(r"[#\s]+", "", str(tag)).strip()
            if v and v not in tags_norm:
                tags_norm.append(v[:18])
        xhs_first = "「把我的骨，还给我。」"
        xhs_body = (
            f"{xhs_first}\n\n"
            "——《烬月灯》连载第一章\n\n"
            "沈照雪被逐出师门那夜，禁地青灯亮了。\n\n"
            "所有人都说她命薄，不配修道。可那截被封了三百年的神骨偏偏认了她。\n\n"
            "谢无咎曾救过她，也亲手把罪名塞进她袖中。现在他扣住她的手腕，说：跟我走。\n\n"
            "下期：她该进禁地，还是当场反击？\n\n"
            "你更想看 A 情感连载 还是 B 玄幻连载？\n\n"
            + " ".join(f"#{t}" for t in tags_norm[:5])
        )
        return {
            "wechat": {
                "skill_id": wechat_skill_id,
                "title": "烬月灯 · 第一章 她听见神骨在说话",
                "summary": "沈照雪被逐出师门那夜，禁地青灯亮起，被封三百年的神骨认了她。谢无咎伸手拦住她，却藏着另一个秘密。",
                "markdown": story_md,
            },
            "xiaohongshu": {
                "skill_id": xiaohongshu_skill_id,
                "image_skill_id": "xiaohongshu_images_v1",
                "title": "神骨认主那夜",
                "body": xhs_body,
                "cover_text": "神骨认主",
                "card_pages": [
                    {"title": "神骨认主", "body": "「把我的骨，还给我。」", "kind": "cover"},
                    {"title": "被逐那夜", "body": "沈照雪刚被赶下玄清山，禁地那盏三百年未亮的青灯忽然亮了。", "kind": "content"},
                    {"title": "旧债重来", "body": "谢无咎曾救她，也亲手把罪名塞进她袖中。现在他又要带她进禁地。", "kind": "content"},
                    {"title": "下章选择", "body": "她该跟他进禁地，还是当场撕开掌门的谎言？", "kind": "content"},
                ],
            },
        }

    if is_trend:
        wechat_intro = (
            "先说我的判断：这条资讯真正的价值，不是让你多记一个工具名，"
            "而是帮你判断它能不能变成一个省时间、可复盘、能长期积累的动作。"
        )
        usable_points = paragraphs[:6]
        pain_point = _compact(usable_points[0] if usable_points else final_title, 140)
        wechat_sections = [
            ("先说结论：别追热点，先找能省时间的动作", f"这条信息真正值得看的地方，不是它又出现了一个新名词，而是它可能帮普通人减少一个重复动作。\n\n我的判断是：如果它不能帮你更快完成写作、整理、检索、复盘或发布，那它暂时就不是你的重点。先别收藏一堆工具，先问一句：它能不能替我省下今天 10 分钟？"),
            ("这件事适合谁", f"适合三类人：第一，正在做内容但每天卡在选题和整理资料的人；第二，想学习 AI 但不知道从哪里开始的人；第三，希望把学习过程沉淀成个人资产的人。\n\n如果你只是想追最新工具名字，这篇不适合你。工具会变，但流程会留下。"),
            ("普通人今天可以怎么用", "\n".join([
                "第一步：把今天看到的资讯复制到一个文档里，只保留标题、链接和一句摘要。",
                "第二步：让 AI 帮你拆成三列：它是什么、能帮谁、省掉什么动作。",
                "第三步：只挑一个和你当前工作最相关的点，做 15 分钟小测试。",
                "第四步：把测试结果写成一段复盘：哪里有用、哪里夸大、哪里还要人工判断。",
                "第五步：把这段复盘改成小红书笔记或公众号文章，而不是直接搬运资讯。",
            ])),
            ("可直接复制的提示词", "请帮我分析下面这条 AI 资讯：1）它到底解决什么问题；2）适合哪类普通人；3）我今天可以用它做哪一个最小动作；4）有哪些风险或夸大宣传；5）帮我生成一条适合小红书/公众号的大白话选题。"),
            ("容易踩的坑", "\n".join([
                "坑一：把工具名字当内容。读者不关心你知道多少新工具，读者关心自己能不能少加班、少踩坑、少焦虑。",
                "坑二：没有验证就推荐。凡是安装、付费、授权、数据上传相关内容，都要提醒读者自己核验来源。",
                "坑三：只写'很厉害'。真正有价值的内容要说清楚：谁能用、怎么用、哪里不能用。",
            ])),
            ("今天就做一个最小动作", "不要再收藏 10 条资讯。今天只做一件事：选一个你最常重复的动作，比如整理资料、写开头、做选题，让 AI 跑一遍，然后记录节省了多少时间、结果哪里还要你修改。这个记录，就是你下一篇内容的素材。"),
        ]
        xhs_hook = "别再只收藏AI资讯了，真正有用的是把它变成你今天能省下10分钟的动作。"
        xhs_points = [
            "先问：它到底帮谁解决什么问题？",
            "再问：我今天能不能用它完成一个小任务？",
            "只测一个场景：写开头、整理资料、提炼观点或复盘流程。",
            "把结果写下来：哪里省时间，哪里还得人工判断。",
            "最后再决定要不要推荐给别人。",
        ]
    else:
        wechat_intro = _compact(summary or paragraphs[0], 180)
        middle = max(1, len(paragraphs) // 2)
        wechat_sections = [
            ("事情是怎么发生的", "\n".join(paragraphs[:middle])),
            ("我后来想明白的事", "\n".join(paragraphs[middle:] or paragraphs[:2])),
            ("下一步怎么做", "把重复动作交给工具，把事实核验、取舍和最后决定留给自己。"),
        ]
        xhs_hook = _compact(paragraphs[0], 90)
        xhs_points = paragraphs[1:5] or paragraphs[:3]

    wechat_markdown = f"# {final_title}\n\n{wechat_intro}\n\n" + "\n\n".join(
        f"## {heading}\n\n{body}" for heading, body in wechat_sections if body
    )
    wechat_markdown += "\n\n## 写在最后\n\n真正有复利的不是知道更多工具，而是把一个动作反复优化。今天先别求大而全，先选一个最烦、最重复、最容易验证的小动作，让 AI 帮你跑一遍，再把结果复盘下来。"

    xhs_title = _compact(
        final_title
        .replace("资讯检索", "")
        .replace("AI 最新资讯日报", "AI资讯")
        .replace("今天", "")
        .strip(" ：:-"),
        20,
    )
    xhs_lines = [xhs_hook, "", "我的判断：不要把AI资讯当新闻看，要当成工作流改造线索。"]
    for index, point in enumerate(xhs_points[:5], start=1):
        xhs_lines.append(f"{index}. {_compact(point, 120)}")
    xhs_lines.append("可复制动作：把一条资讯丢给AI，问它'这件事能帮我省掉哪个重复动作？给我一个今天就能测试的步骤'。")
    xhs_lines.append("提醒：安装、付费、授权、上传资料前，一定自己核验官方来源。")
    xhs_lines.append("你最想先改掉哪个重复流程？")
    normalized_tags = []
    for tag in hashtags:
        value = re.sub(r"[#\s]+", "", str(tag or "")).strip()
        if value and value not in normalized_tags:
            normalized_tags.append(value[:18])
    xhs_body = "\n\n".join(xhs_lines) + "\n\n" + " ".join(f"#{tag}" for tag in normalized_tags[:6])

    card_pages = [
        {
            "title": xhs_title,
            "body": _compact(xhs_hook, 120),
            "kind": "cover",
        }
    ]
    for index, point in enumerate(xhs_points[:5], start=1):
        card_pages.append(
            {
                "title": f"0{index}  {_compact(point, 18)}",
                "body": _compact(point, 170),
                "kind": "content",
            }
        )
    return {
        "wechat": {
            "skill_id": "wechat_article_v1",
            "title": final_title,
            "summary": wechat_intro,
            "markdown": wechat_markdown,
        },
        "xiaohongshu": {
            "skill_id": "xiaohongshu_note_v1",
            "image_skill_id": "xiaohongshu_images_v1",
            "title": xhs_title,
            "body": xhs_body,
            "cover_text": xhs_title,
            "card_pages": card_pages,
        },
    }


def render_xiaohongshu_cards(
    package_dir: Path,
    pages: list[dict[str, Any]],
) -> list[Path]:
    from PIL import Image, ImageDraw, ImageFont

    font_candidates = [
        Path("C:/Windows/Fonts/msyh.ttc"),
        Path("C:/Windows/Fonts/simhei.ttf"),
        Path("/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    font_path = next((path for path in font_candidates if path.exists()), None)
    if not font_path:
        raise RuntimeError("服务器缺少可用字体，无法生成小红书图文卡片。")

    output_dir = package_dir / "xiaohongshu_cards"
    output_dir.mkdir(parents=True, exist_ok=True)
    palette = [
        ("#F7F4EC", "#102A43", "#00A6A6"),
        ("#E9F5F2", "#17324D", "#E85D3F"),
        ("#FFF1E8", "#243B53", "#087E8B"),
        ("#EDF2FF", "#172B4D", "#F26B38"),
    ]

    def font(size: int) -> ImageFont.FreeTypeFont:
        return ImageFont.truetype(str(font_path), size=size)

    def wrap(draw: ImageDraw.ImageDraw, text: str, text_font: ImageFont.FreeTypeFont, width: int) -> list[str]:
        lines: list[str] = []
        current = ""
        for char in text:
            candidate = current + char
            if draw.textbbox((0, 0), candidate, font=text_font)[2] <= width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = char
        if current:
            lines.append(current)
        return lines

    files: list[Path] = []
    total = max(1, len(pages))
    for index, page in enumerate(pages, start=1):
        bg, ink, accent = palette[(index - 1) % len(palette)]
        image = Image.new("RGB", (1080, 1440), bg)
        draw = ImageDraw.Draw(image)
        draw.rounded_rectangle((72, 72, 1008, 1368), radius=32, outline=accent, width=5)
        draw.rectangle((72, 72, 92, 1368), fill=accent)
        title_font = font(74 if page.get("kind") == "cover" else 54)
        body_font = font(44)
        meta_font = font(28)
        y = 170
        for line in wrap(draw, str(page.get("title") or ""), title_font, 820)[:3]:
            draw.text((145, y), line, font=title_font, fill=ink)
            y += title_font.size + 24
        y += 36
        for line in wrap(draw, str(page.get("body") or ""), body_font, 800)[:10]:
            draw.text((145, y), line, font=body_font, fill=ink)
            y += body_font.size + 24
        draw.text((145, 1280), f"灵感工坊 · {index}/{total}", font=meta_font, fill=accent)
        output = output_dir / f"{index:02d}.png"
        image.save(output, format="PNG", optimize=True)
        files.append(output)
    return files
