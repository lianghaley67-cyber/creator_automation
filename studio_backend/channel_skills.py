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
        "file": "06_wechat_article.md",
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
        "file": "07_xiaohongshu_note.md",
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
        "file": "08_xiaohongshu_images.md",
        "description": "1080×1440 封面与内容卡片自动分页。适合知识卡片和步骤拆解。",
        "persona_tags": ["通用"],
        "example": {
            "title": "AI省时间攻略",
            "cover": "5个让普通人每天少做1小时的AI方法",
            "pages": ["封面：5个让普通人每天少做1小时的AI方法", "01 整理笔记：把乱七八糟的记录扔给AI", "02 写回复：让AI起草，你来润色"],
        },
    },
    "wechat_ai_popularizer_v1": {
        "name": "公众号·大白话AI科普",
        "channel": "wechat",
        "file": "09_ai_popularizer.md",
        "description": "用生活场景解释AI，零基础也能看懂。禁用技术词汇，配生活化类比。",
        "persona_tags": ["AI科普", "零基础"],
        "example": {
            "title": "用AI每天省2小时，我的具体方法（不需要懂代码）",
            "summary": "AI不是程序员专属的工具。我是一个完全不懂代码的普通人，但我现在每天都在用AI省时间——整理笔记、写回复、做计划……",
            "excerpt": "## 事情是怎么发生的\n\n我以前每天花将近一个小时在微信上整理各种消息和待办……\n\n## 我后来想明白的事\n\nAI就像一个很快的助手，你说得越清楚，它帮你帮得越好……",
        },
    },
    "xiaohongshu_ai_popularizer_v1": {
        "name": "小红书·大白话AI科普",
        "channel": "xiaohongshu",
        "file": "09_ai_popularizer.md",
        "description": "用大白话讲AI，标题用「原来AI能...」句式，配生活场景举例，3步教上手。",
        "persona_tags": ["AI科普", "零基础"],
        "example": {
            "title": "原来AI能帮我5分钟整理一周工作！",
            "body": "不是技术人，但我现在天天用AI省时间。\n\n每周一早上要交工作总结，以前要想半小时，现在扔给AI，5分钟搞定。\n\n上手3步：\n1. 打开任意AI工具（手机微信小程序就有）\n2. 把你要整理的内容复制进去\n3. 说清楚你要什么格式和字数\n\n你最想让AI帮你省掉哪个最烦的工作？\n\n#AI工具推荐 #AI新手入门 #普通人学AI",
        },
    },
    "wechat_growth_female_v1": {
        "name": "公众号·知识成长女性",
        "channel": "wechat",
        "file": "10_growth_female.md",
        "description": "展现真实学习历程，有失败有进步。共情感>教导感，让读者觉得“她跟我一样”。",
        "persona_tags": ["成长记录", "真实感"],
        "example": {
            "title": "学AI第3个月，这件事让我突然开窍",
            "summary": "我不是技术背景，学AI这件事，前两个月走了很多弯路。但这些弯路让我搞清楚了一件事：AI不是在考验你聪不聪明。",
            "excerpt": "## 我以前错误的认知\n\n我以前以为，学AI就是学用哪个工具……\n\n## 转折发生的关键时刻\n\n有一天我换了一种方式跟AI说话……",
        },
    },
    "xiaohongshu_growth_female_v1": {
        "name": "小红书·知识成长女性",
        "channel": "xiaohongshu",
        "file": "10_growth_female.md",
        "description": "突出成长过程，标题用“学AI第N月”或“我花了xxx踩的坑”，包含一个真实困惑或失败。",
        "persona_tags": ["成长记录", "真实感"],
        "example": {
            "title": "学AI第2个月，我一度觉得自己是最笨的那个",
            "body": "说实话，刚开始学AI工具的时候，我真的很挫败。\n\n我看着别人三五分钟做出来的东西，自己搞了一下午还是乱的。后来才发现——不是我笨，是我一直在用错误的方式提问。\n\n我以前跟AI说“帮我写一篇文章”，它给我的东西每次都很空洞。直到我开始说得更具体——对话一下子就顺了。\n\n提示词说得越具体，AI越听话。这是我花了两个月才真正明白的事。\n\n你学AI的时候，哪个地方卡了最久？\n\n#女性成长 #学AI路上 #职场进阶",
        },
    },
    "xiaohongshu_tool_guide_v1": {
        "name": "小红书·AI工具实操手册",
        "channel": "xiaohongshu",
        "file": "11_ai_tool_guide.md",
        "description": "手把手操作指南，含可直接复制的提示词模板，截图级别的步骤说明。",
        "persona_tags": ["工具教程", "实操"],
        "example": {
            "title": "用NotebookLM做播客内容，我的完整操作步骤",
            "body": "NotebookLM可以把你上传的文章，自动生成像真人聊天一样的播客音频。\n\n适合：想做知识类内容但不想露脸的创作者。\n\n操作步骤：\n1. 打开 notebooklm.google.com（需要谷歌账号）\n2. 点击“新建笔记本”\n3. 上传你的文章或粘贴内容\n4. 点击右下角“音频概览”\n5. 等1-2分钟，自动生成双人播客\n6. 点击下载保存MP3\n\n可直接使用的提示词：\n“请用普通人也能听懂的方式总结这篇内容，并列出3个最值得关注的点”\n\n注意：目前中文内容效果一般，更适合英文内容。\n\n你想用它处理什么类型的内容？\n\n#AI工具测评 #工具推荐 #效率工具",
        },
    },
    "wechat_tool_guide_v1": {
        "name": "公众号·AI工具实操手册",
        "channel": "wechat",
        "file": "11_ai_tool_guide.md",
        "description": "包含工具名称和具体使用场景，含完整操作步骤和提示词公式，诚实评估局限性。",
        "persona_tags": ["工具教程", "实操"],
        "example": {
            "title": "我用NotebookLM做AI播客的完整操作流程（附提示词模板）",
            "summary": "NotebookLM是谷歌出的一个AI工具，我用它把我收藏的文章自动转成播客，效果出乎意料地好。",
            "excerpt": "## 这个工具是什么，我为什么开始用它\n\n我每周都会收藏大量文章，但根本没时间读……\n\n## 详细操作步骤\n\n第一步：……",
        },
    },
    "xiaohongshu_monetization_v1": {
        "name": "小红书·AI变现路径探索",
        "channel": "xiaohongshu",
        "file": "12_monetization_bridge.md",
        "description": "诚实分享AI变现探索，体现“普通人可做”，不画大饼，说真实门槛和风险。",
        "persona_tags": ["变现探索", "副业"],
        "example": {
            "title": "学AI内容创作3个月后，我是怎么开始接商单的",
            "body": "不骗你，我不是什么AI大佬，就是普通人。\n\n3个月前我开始把自己学AI的过程发出来——踩了什么坑，用了什么方法，效果怎么样。\n\n慢慢积累了一些关注者，上个月有AI工具品牌问我能不能合作。\n\n这条路的门槛：你要真的在学、真的在用，然后把过程记录出来。\n\n最大的风险：流量不稳，收入不固定，不适合当成主要收入来源。\n\n我现在还在探索阶段，不敢说“成功”，但这条路是真实可走的。\n\n你在探索哪种AI变现的方式？\n\n#AI变现 #副业探索 #内容创作变现",
        },
    },
    "wechat_operator_flywheel_v1": {
        "name": "公众号·运营增长飞轮",
        "channel": "wechat",
        "file": "13_operator_flywheel.md",
        "description": "参考姜胡说的行动飞轮、极简动作和圈层套利思路，把资讯改造成可复利的操作系统。",
        "persona_tags": ["运营判断", "复利", "变现前置"],
        "example": {
            "title": "别再收藏AI工具了，先把一个动作跑通",
            "summary": "真正有价值的不是你知道多少工具，而是你能不能把一个重复动作变成流程，并持续复盘。",
            "excerpt": "## 先说结论\n\nAI内容不是拼新闻速度，而是拼你能不能把信息翻译成普通人今天能做的动作……",
        },
    },
    "xiaohongshu_operator_flywheel_v1": {
        "name": "小红书·运营增长飞轮",
        "channel": "xiaohongshu",
        "file": "13_operator_flywheel.md",
        "description": "把资讯变成可收藏、可执行、可复盘的小红书实操笔记，适合建立长期信任。",
        "persona_tags": ["运营判断", "复利", "实操"],
        "example": {
            "title": "别再只收藏AI资讯",
            "body": "真正有用的不是知道一个新工具，而是把它变成你今天能省下10分钟的动作。\n\n1. 先问它解决谁的问题\n2. 再选一个小场景测试\n3. 记录哪里省时间\n4. 写出你的真实判断\n\n#AI工具 #普通人学AI",
        },
    },
    "wechat_tool_research_v1": {
        "name": "公众号·工具研究说明书",
        "channel": "wechat",
        "file": "14_tool_research_playbook.md",
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
        "file": "14_tool_research_playbook.md",
        "description": "适合工具种草和教程：先讲清楚工具本身，再给安装、上手、进阶和避坑清单。",
        "persona_tags": ["工具研究", "教程", "实操"],
        "example": {
            "title": "Trae新手先看这篇",
            "body": "Trae 不是一个普通文档工具，它更像 AI 编程助手。\n\n适合：想用 AI 辅助写代码、改代码、理解项目的新手。\n\n安装前先确认：系统版本、官网来源、账号登录、模型权限。\n\n#AI工具 #Trae教程",
        },
    },
}

# 预设主题组，前端展示为可点击的 Chip
PRESET_TOPICS = [
    {"id": "ai_tools_tips", "label": "自媒体AI使用技巧", "query": "AI tools for content creators latest tips 2025 自媒体AI工具使用技巧"},
    {"id": "vibe_coding", "label": "Vibe Coding技巧", "query": "vibe coding AI programming no-code tools cursor windsurf latest 2025"},
    {"id": "skill_generation", "label": "Skill生成技巧", "query": "AI skill generation prompt engineering Claude skills automation 2025"},
    {"id": "ai_news", "label": "最新AI动态", "query": "AI latest news models tools 2025 最新AI新闻"},
    {"id": "ai_workflow", "label": "AI提效工作流", "query": "AI productivity workflow automation tools 2025 AI工作流提效"},
    {"id": "ai_for_creators", "label": "创作者AI工具", "query": "AI tools for content creators video image text generation 2025"},
    {"id": "ai_monetization", "label": "AI变现机会", "query": "AI side hustle monetization opportunities content creator 2025 AI变现"},
    {"id": "notebooklm_podcast", "label": "NotebookLM播客", "query": "NotebookLM podcast audio overview latest features tips 2025"},
]


def list_channel_skills() -> list[dict[str, Any]]:
    output = []
    for skill_id, metadata in CHANNEL_SKILLS.items():
        skill_path = SKILLS_DIR / metadata["file"]
        output.append(
            {
                "id": skill_id,
                "name": metadata["name"],
                "channel": metadata["channel"],
                "file": metadata["file"],
                "description": metadata["description"],
                "persona_tags": metadata.get("persona_tags", []),
                "example": metadata.get("example", {}),
                "configured": skill_path.exists(),
            }
        )
    return output


def load_skill_content(skill_id: str) -> str:
    metadata = CHANNEL_SKILLS.get(skill_id)
    if not metadata:
        return ""
    skill_path = SKILLS_DIR / metadata["file"]
    if not skill_path.exists():
        return ""
    return skill_path.read_text(encoding="utf-8", errors="replace").strip()


def _load_jianghushuo_lens() -> str:
    skill_path = SKILLS_DIR / "jianghushuo-perspective.md"
    if not skill_path.exists():
        return (
            "姜胡说式内容判断：先给结论，不堆资料；把问题拆成极简单动作；"
            "用“不是X而是Y”提出观点；最后给一个今天就能做的动作。"
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
    "claude",
    "claude code",
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
        "Claude",
        "Claude Code",
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


def _evidence_lines(source_text: str, limit: int = 6) -> list[str]:
    lines: list[str] = []
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
    for raw in str(source_text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip(" -")
        if len(line) < 4:
            continue
        if line in {"【检索资料】", "检索资料"}:
            continue
        if any(line.startswith(prefix) for prefix in skip_prefixes):
            continue
        if line.startswith("http"):
            line = f"来源链接：{line}"
        if line not in lines:
            lines.append(_compact(line, 240))
        if len(lines) >= limit:
            break
    return lines


def _build_tool_research_fallback(
    *,
    source_text: str,
    title: str,
    summary: str,
    hashtags: list[str],
) -> dict[str, Any]:
    tool_name = _infer_tool_name(title, source_text)
    evidence_items = _evidence_lines(source_text)
    evidence = "\n".join(f"- {item}" for item in evidence_items) or "- 当前资料不足，需要继续核验官方说明。"
    final_title = _compact(f"{tool_name} 是什么？怎么安装和上手", 64)
    wechat_summary = _compact(
        f"这是一份给完全不了解 {tool_name} 的新手看的工具说明：先讲它能做什么，再讲适合谁、怎么安装、怎么上手，以及哪些信息必须自己核验。",
        150,
    )
    wechat_markdown = f"""# {final_title}

{wechat_summary}

## 先说清楚：{tool_name} 到底是干什么的

从目前资料看，{tool_name} 是一个需要先理解使用场景再决定是否安装的 AI 工具。你不要先被工具名带着跑，先看它能不能帮你解决一个具体问题：写代码、整理资料、理解项目、生成内容，或者减少某个重复动作。

下面这些是当前资料里能看到的信息：

{evidence}

## 它能解决什么问题

1. 帮新手降低上手门槛：把复杂任务拆成步骤。
2. 帮内容创作者整理资料：把零散信息变成选题、脚本或教程。
3. 帮学习者快速理解一个陌生项目：先看结构，再做小实验。
4. 帮已经有工作流的人提效：把重复整理、总结、改写交给 AI 先跑一遍。

## 适合谁，不适合谁

适合三类人：第一，想用 AI 辅助学习或创作，但不知道从哪里开始的人；第二，经常需要整理资料、写教程、拆步骤的人；第三，愿意自己验证工具效果，而不是只看别人推荐的人。

不适合两类人：第一，期待安装完立刻自动解决所有问题的人；第二，不愿意看权限、账号、数据上传风险的人。

## 安装或访问方式：先做核验

当前资料不足以保证所有安装细节都准确，所以建议按这个顺序核验：

1. 先找官网或官方文档，不要随便点第三方安装包。
2. 确认电脑系统是否支持。
3. 确认是否需要账号、手机号、邮箱或海外网络环境。
4. 确认免费额度、付费规则和可用模型。
5. 如果要打开本地文件或项目，先备份重要资料。

## 完全新手第一次怎么用

第一步：不要一上来就处理大项目，先拿一段普通文字或一个小文件测试。

第二步：问它三个问题：这个内容是什么？我应该先看哪里？下一步最小动作是什么？

第三步：只让它做一件事，比如整理步骤、解释概念、生成一个检查清单。

第四步：你自己核对结果，不要直接复制发布。

第五步：把好用的提问保存下来，变成你自己的固定模板。

## 怎么把它用得更好

可以复制这段提示词：

“我是完全新手，请先用大白话解释这个工具/项目是干什么的，再告诉我它适合解决什么问题。请按‘适合谁、安装前检查、新手第一步、常见坑、进阶用法’输出。没有证据的信息请标注需要核验，不要编造。”

## 常见坑

坑一：只看别人说好用，自己没有测试场景。

坑二：安装来源不明，忽略账号、权限和数据上传风险。

坑三：把 AI 输出当最终答案。它可以帮你整理，但最后判断要你自己做。

## 还可以继续讨论什么

你可以继续追问：{tool_name} 和同类工具有什么区别？它适不适合我的工作流？有没有适合小白的第一个练习任务？如果要做成课程或小红书系列，应该拆成哪几篇？
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
            f"先别急着安装。对完全不了解它的人来说，第一步不是下载，而是判断：它能不能解决你的具体问题。",
            "适合谁：想用AI辅助学习、整理资料、写教程、理解项目的人。",
            "安装前先检查：\n1. 官网或官方文档\n2. 系统是否支持\n3. 是否需要账号/网络环境\n4. 免费额度和付费规则\n5. 是否会读取本地文件或上传资料",
            "新手第一次这样用：\n1. 拿一个小任务测试\n2. 让它先解释，不要直接生成\n3. 让它给步骤清单\n4. 你自己核对结果\n5. 保存好用的提示词",
            "可复制提示词：\n“我是完全新手，请用大白话告诉我这个工具是干什么的、适合谁、怎么开始用、有哪些坑。没有证据的信息请标注需要核验。”",
            "你想让我下一篇继续拆：安装流程、使用案例，还是和同类工具对比？",
            " ".join(f"#{tag}" for tag in tags[:6]),
        ]
    )
    card_pages = [
        {"title": xhs_title, "body": f"先判断 {tool_name} 能不能解决你的问题，再决定要不要安装。", "kind": "cover"},
        {"title": "01 它是什么", "body": f"{tool_name} 是一个需要结合具体场景判断的 AI 工具，先看用途，再看安装。", "kind": "content"},
        {"title": "02 适合谁", "body": "适合想用 AI 学习、整理资料、写教程、理解项目的人。", "kind": "content"},
        {"title": "03 先检查", "body": "官网来源、系统支持、账号规则、付费额度、数据权限都要先核验。", "kind": "content"},
        {"title": "04 第一步", "body": "拿一个小任务测试，让它先解释、再列步骤，最后自己核对结果。", "kind": "content"},
    ]
    return {
        "wechat": {
            "skill_id": "wechat_tool_research_v1",
            "title": final_title,
            "summary": wechat_summary,
            "markdown": wechat_markdown,
        },
        "xiaohongshu": {
            "skill_id": "xiaohongshu_tool_research_v1",
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
) -> dict[str, Any]:
    """生成渠道内容草稿，优先用 OpenAI 按 Skill 规则生成，无 API Key 时降级到规则模板。"""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip()
    model = os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"

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
            )
        except Exception:  # noqa: BLE001
            pass

    fallback = build_channel_drafts(
        source_text=source_text,
        title=title,
        summary=summary,
        source_type=source_type,
        hashtags=hashtags,
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
) -> dict[str, Any]:
    wechat_meta = CHANNEL_SKILLS.get(wechat_skill_id, CHANNEL_SKILLS["wechat_article_v1"])
    xhs_meta = CHANNEL_SKILLS.get(xiaohongshu_skill_id, CHANNEL_SKILLS["xiaohongshu_note_v1"])
    wechat_skill_content = load_skill_content(wechat_skill_id) or load_skill_content("wechat_article_v1")
    xhs_skill_content = load_skill_content(xiaohongshu_skill_id) or load_skill_content("xiaohongshu_note_v1")

    tags_str = " ".join(f"#{t}" for t in (hashtags or ["AI工具", "普通人学AI"])[:6])
    persona_block = (
        "账号定位：吸引对AI感兴趣的普通人，人设是知识成长女性，"
        "用大白话科普AI知识，后续考虑内容变现。目标是让人人都能听懂AI。"
    )
    jianghushuo_lens = _load_jianghushuo_lens()

    system_prompt = f"""你是一位中文自媒体内容创作专家。
{persona_block}

语言硬规则：
- 文案主体必须使用中文，表达要像真人说话，不要翻译腔。
- AI 工具名、模型名、产品名、公司名、英文缩写和专有名词可以保留英文原名，例如 Claude、ChatGPT、NotebookLM、API、Vibe Coding。
- 不要把公认英文名称硬翻译成奇怪中文；但第一次出现英文缩写时，用一句中文解释它是干什么的。

运营质量硬规则：
- 不要复述资讯，不要写“以下内容来自接口返回结果”这种废话。你要替读者完成判断、翻译和补课。
- 每篇都必须回答 5 个问题：这件事到底是什么；它解决谁的什么痛点；普通人今天怎么用；容易踩什么坑；下一步最小动作是什么。
- 如果主题是某个具体工具、安装教程、使用说明或“怎么用”，必须优先写成工具说明书，而不是运营观点文。必须包含：工具是什么、核心功能、解决的问题、适合人群、安装/访问方式、新手第一步、进阶用法、常见坑、待核验信息。
- 如果原始资料信息不足，要基于常识补齐“需要核验的清单”，但不要编造下载链接、价格、官方承诺、收益数字。
- 公众号要像一篇能建立信任的付费前置内容：观点明确、步骤具体、有边界、有复盘感。
- 小红书要像一篇能收藏的实操笔记：开头说人话，中间给步骤，最后给一个可复制动作。
- 必须至少给出一个可直接复制的提示词、检查清单或操作步骤；否则判定为不合格。
- 标题禁止空泛，不能只写“资讯检索”“安装说明”。标题要让读者知道看完能解决什么问题。

姜胡说式思考参考（只吸收方法，不要模仿成男性口吻，不要自称姜胡说）：
{jianghushuo_lens}

请严格按照以下两个 Skill 规则分别生成公众号文章和小红书笔记。

【公众号文章 Skill 规则】
{wechat_skill_content}

【小红书笔记 Skill 规则】
{xhs_skill_content}

输出格式：只输出合法 JSON，不加任何说明文字，格式如下：
{{
  "wechat": {{
    "title": "公众号文章标题",
    "summary": "文章摘要（60-100字）",
    "markdown": "完整公众号文章（Markdown格式，1000-1800字，用##分节，必须包含：我的判断、适合谁、具体步骤、坑点提醒、今天就能做的动作）"
  }},
  "xiaohongshu": {{
    "title": "小红书标题（不超过20字）",
    "cover_text": "封面短句（不超过12字）",
    "body": "小红书正文（350-650字，必须包含：适合谁、3-5步操作、避坑提醒、可复制动作）\\n\\n{tags_str}",
    "card_pages": [
      {{"title": "封面标题", "body": "封面一句话说明", "kind": "cover"}},
      {{"title": "01 要点标题（10字内）", "body": "要点详细说明（50-80字）", "kind": "content"}},
      {{"title": "02 要点标题（10字内）", "body": "要点详细说明（50-80字）", "kind": "content"}},
      {{"title": "03 要点标题（10字内）", "body": "要点详细说明（50-80字）", "kind": "content"}}
    ]
  }}
}}"""

    user_prompt = f"""请根据以下内容，按照 Skill 规则分别生成公众号文章和小红书笔记：

标题：{title or "AI最新资讯"}
摘要：{summary[:200] if summary else ""}

原始内容：
{source_text[:3000]}

生成前请先在内部完成这一步，不要输出：
1. 判断这个主题是“工具说明书”还是“资讯观点文”。只要出现具体工具名、安装、教程、怎么用，就按工具说明书写。
2. 从原始内容中提取确实信息：工具名称、用途、平台、安装入口、操作步骤、限制条件、来源链接。没有证据的地方标注“资料不足，建议核验”，不要用空话替代。
3. 把零散资讯补成一个可执行流程。
4. 对不确定信息标注“需要自行核验”，不要编造。
5. 让内容像一个愿意长期付费的读者读完会说：这篇真的帮我少走了一步弯路。"""

    raw = _openai_chat(
        api_key=api_key,
        base_url=base_url,
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.72,
        max_tokens=2400,
    )

    # 提取 JSON（兼容被 ``` 包裹的情况）
    json_match = re.search(r"\{[\s\S]*\}", raw)
    if not json_match:
        raise ValueError(f"AI 返回内容不包含合法 JSON: {raw[:200]}")
    data = json.loads(json_match.group())

    wechat_data = data.get("wechat") or {}
    xhs_data = data.get("xiaohongshu") or {}

    final_title = _compact(str(wechat_data.get("title") or title or "今天的AI资讯"), 64)
    xhs_title = _compact(str(xhs_data.get("title") or final_title), 20)
    xhs_body = str(xhs_data.get("body") or "")
    if not xhs_body:
        xhs_body = str(xhs_data.get("cover_text") or xhs_title)

    card_pages = xhs_data.get("card_pages") or []
    if not card_pages:
        card_pages = [{"title": xhs_title, "body": _compact(xhs_body, 100), "kind": "cover"}]

    return {
        "wechat": {
            "skill_id": wechat_skill_id,
            "title": final_title,
            "summary": _compact(str(wechat_data.get("summary") or summary), 150),
            "markdown": str(wechat_data.get("markdown") or ""),
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


def build_channel_drafts(
    *,
    source_text: str,
    title: str,
    summary: str,
    source_type: str,
    hashtags: list[str],
) -> dict[str, Any]:
    paragraphs = _paragraphs(source_text)
    if not paragraphs:
        paragraphs = [_compact(source_text, 500)]
    is_trend = source_type == "ai_trends"
    final_title = _compact(title, 64) or ("今天值得关注的 3 个变化" if is_trend else "这件事，我终于想明白了")
    if is_trend and _is_tool_research_request(final_title, source_text, source_type):
        return _build_tool_research_fallback(
            source_text=source_text,
            title=final_title,
            summary=summary,
            hashtags=hashtags,
        )

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
                "坑三：只写“很厉害”。真正有价值的内容要说清楚：谁能用、怎么用、哪里不能用。",
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
    xhs_lines.append("可复制动作：把一条资讯丢给AI，问它“这件事能帮我省掉哪个重复动作？给我一个今天就能测试的步骤”。")
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
