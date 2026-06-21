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
    "wechat_tool_deep_review_v1": {
        "name": "公众号·AI工具深度实测",
        "channel": "wechat",
        "file": "15_tool_deep_review.md",
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
        "file": "15_tool_deep_review.md",
        "description": "把工具实测长文压缩成可收藏笔记：适合谁、安装检查、上手步骤、提示词和避坑。",
        "persona_tags": ["工具实测", "教程", "可收藏"],
        "example": {
            "title": "Trae新手安装前先看",
            "body": "Trae 适合想用 AI 辅助写代码、理解项目的人。\n\n安装前先查：官网来源、系统支持、账号登录、模型权限、数据权限。\n\n新手第一步：别打开重要项目，先拿测试文件夹练习。\n\n#AI工具 #Trae教程",
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
) -> dict[str, Any]:
    """生成渠道内容草稿，优先用 OpenAI 按 Skill 规则生成，无 API Key 时降级到规则模板。"""
    uses_tool_deep_review = (
        wechat_skill_id == "wechat_tool_deep_review_v1"
        or xiaohongshu_skill_id == "xiaohongshu_tool_deep_review_v1"
    )
    if uses_tool_deep_review and _is_tool_research_request(title, source_text, source_type):
        fallback = _build_tool_research_fallback(
            source_text=source_text,
            title=title,
            summary=summary,
            hashtags=hashtags,
        )
        fallback["wechat"]["skill_id"] = (
            "wechat_tool_deep_review_v1"
            if wechat_skill_id == "wechat_tool_deep_review_v1"
            else (wechat_skill_id or fallback["wechat"]["skill_id"])
        )
        fallback["xiaohongshu"]["skill_id"] = (
            "xiaohongshu_tool_deep_review_v1"
            if xiaohongshu_skill_id == "xiaohongshu_tool_deep_review_v1"
            else (xiaohongshu_skill_id or fallback["xiaohongshu"]["skill_id"])
        )
        return fallback

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
- 不要复述资讯，不要写'以下内容来自接口返回结果'这种废话。你要替读者完成判断、翻译和补课。
- 每篇都必须回答 5 个问题：这件事到底是什么；它解决谁的什么痛点；普通人今天怎么用；容易踩什么坑；下一步最小动作是什么。
- 如果主题是某个具体工具、安装教程、使用说明或'怎么用'，必须优先写成工具说明书，而不是运营观点文。必须包含：工具是什么、核心功能、解决的问题、适合人群、安装/访问方式、新手第一步、进阶用法、常见坑、待核验信息。
- 如果使用'AI工具深度实测'类 Skill，公众号必须写成高密度教程文章：开头直接给判断、工具是什么、安装前检查、官方链接、逐步安装、10分钟实操、配置检查、截图清单、卡点排查、进阶使用、同类工具对比、最后结论。不要单独写信息汇总小节，把官方入口、账号、费用、权限并入安装前检查表格，不要单独成节。
- 工具教程开头不要长篇铺垫，不要连续制造焦虑钩子。开头 3 段内必须讲清：是否值得试、先检查什么、今天最小动作是什么。
- 工具教程开头三层禁止规则（最高优先级）：摘要字段、正文开头第一段、第一个##小节，三者不能说同一件事。具体执行：①摘要只写'今天最小动作是什么'（1句，不超过40字）；②正文第一段只写'我为什么测它'（1-2句，连接一个具体麻烦）；③'工具是什么'的说明必须合并进安装前检查表格的第一行，不能单独成为正文的第一个##小节。违反此规则等于开头冗余，必须重写。
- 工具教程开头不要重复标题摘要。标题下方摘要最多 1 句；不要写 `## 先给结论` 或 `## 先说结论` 这种独立标题，标题和摘要后直接进入正文判断。开头判断必须用表格或清单给出标准，例如官方入口、系统支持、账号额度、文件权限，不能用 2 段散文重复'不要急着安装'。
- 工具教程必须保留真实使用入口，但只能短写：正文第一段只放 1-2 句第一人称，讲清'我为什么测它'，必须连接一个具体麻烦，例如整理资料太慢、看不懂项目、安装入口混乱、怕误授权本地文件。不能写成励志开场或连续钩子。第一段结束后立刻进入安装前检查表格，不允许插入过渡段落。
- 工具教程开头硬规则：正文第一段禁止从'工具是什么、官方介绍、功能很强'开始；必须从'我'的具体场景开始，具体到一个动作，例如看懂项目、整理资料、写教程、排查报错、担心文件权限。
- 功能说明硬规则：禁止把参数、版本号、模型名、能力清单当正文重点；每个功能必须翻译成'对普通人意味着什么、能省哪一步、不能替你做什么'。必要参数只能放在核验卡或括号里。
- 工具教程中段必须插入 1 句真实踩坑/失败经验，放在操作步骤之间，例如'我第一次让它一次改太多，后来改成只让它解释和做一个小动作'。这句必须服务操作建议，不能写成情绪故事。
- 工具教程必须给官方链接；只有原始资料或常识能确认时才写具体链接。没有官方链接时，必须写'没有抓到官方链接，先不要按第三方链接安装'。
- 操作步骤必须适合小白：每一步都写'操作 / 你会看到什么 / 卡住怎么办'。不能只写'去官网下载''按提示安装'。
- 操作颗粒度硬规则：每个关键步骤必须写清点哪里、输入什么、看到什么算成功、失败时先查哪里。网页工具要写官方入口、登录入口、下载/开始使用按钮、第一次进入工作台后先点哪里；命令行工具要写安装命令在哪看、在哪个终端执行、执行前检查什么、执行后怎么判断成功、报错先复制哪一行。
- 必须给一个读者今天能照着完成的实操任务，包含：新建测试文件夹或测试文档、放入测试素材、打开工具导入、输入第一条提示词、检查输出、只执行一个小动作、记录结果。每一步写清'你要做什么 / 为什么这样做 / 成功标志 / 失败处理'。
- 实操任务必须具体到对象名称，例如测试文件夹名、测试文件名、第一条提示词、按钮/菜单名、成功标志。不要写成'准备材料''开始使用'这种泛步骤。
- 必须给配置检查表：账号额度、模型选择、文件权限、自动修改、语言偏好、终端/执行权限。没有证据就写需要核验，并指出去 Settings / Account / Model / Preferences 等位置看。
- 不确定信息不要在文章里到处重复'资料不足'；官方入口、价格/额度、系统支持、本地文件权限、账号/地区/网络限制，统一并入安装前检查表格的'需要核验'列，不要单独再写一个'发布前核验'章节。
- 必须给常见卡点排查：官网打不开、下载按钮找不到、登录失败、模型不可用、文件权限弹窗、输出胡编、改动太大。
- 截图清单必须保留，但只写真正辅助操作判断的截图：官网入口、下载按钮、登录/工作台、第一个测试任务、结果复盘。每张图必须说明'读者看这张图要确认什么'，不要写装饰图。
- 正文不要主动写'配图实操版'标题，系统会自动把真实截图或清晰操作图插入文章。正文只保留'截图清单'，不要把占位图、示意图说成真实截图。
- 最后结论必须短，控制在 2 段以内，每段 1-2 句。第一段说清是否值得试和今天最小动作；第二段只留 1 个具体互动问题。不要连续抛多个问题，不要写'欢迎评论'，要像真人问朋友，例如：你现在最想让 AI 帮你省哪一步？A 看懂项目，B 整理资料，C 写教程，D 排查报错。
- 结尾互动硬规则：互动问题必须具体、可回答，优先 A/B/C/D 选项；禁止'你怎么看''你有什么想法''欢迎留言'。
- 上面这些是幕后写作检查清单，不能原样写进正文。正文里禁止出现'我会按什么顺序拆''本文将包含''资料里没明确写出的部分我会标注''以下回答几个问题'这类模板说明。
- 信息密度要求：每个小节都要有新信息或操作动作。不要把'为什么这样做''普通人会卡住'反复写多遍；同一意思出现第二次就删除或合并。
- 个人经验要求：最多出现 2 处第一人称经验；每处最多 2 句；必须具体到一个动作或一个坑。不要写'我觉得很重要''我建议大家'这类空话。
- 篇幅要求：工具深度实测公众号控制在 1200-1800 字，宁可短一点，也不要用情绪句凑长度。
- 如果原始资料信息不足，要基于常识补齐'需要核验的清单'，但不要编造下载链接、价格、官方承诺、收益数字。
- 公众号要像一篇能建立信任的付费前置内容：观点明确、步骤具体、有边界、有复盘感。
- 小红书要像一篇能收藏的实操笔记：开头说人话，中间给步骤，最后给一个可复制动作。
- 必须至少给出一个可直接复制的提示词、检查清单或操作步骤；否则判定为不合格。
- 标题禁止空泛，不能只写'资讯检索''安装说明'。标题要让读者知道看完能解决什么问题。

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
    "markdown": "完整公众号文章（Markdown格式，1200-1800字，用##分节；工具教程必须包含：开头直接给判断、工具是什么、安装前检查、官方链接、逐步安装、10分钟实操、配置检查、发布前核验框、截图清单、卡点排查、进阶使用、同类工具对比、最后结论。禁止写##先给结论或##先说结论，标题和摘要后直接进入正文判断。禁止单独写信息汇总小节，把官方入口、账号、费用、权限并入安装前检查和发布前核验。正文第一段必须从我的具体场景开始，功能说明必须翻译成对普通人意味着什么。必须有1个短个人入口和1句中途踩坑经验。安装和实操步骤必须具体到点哪里、输入什么、看到什么算成功、失败先查哪里；必须给测试文件夹/测试文件/第一条提示词/成功标志。截图清单只保留操作判断需要的截图，不要写配图实操版，不要重复钩子。最后结论必须短，2段以内，只留1个具体可回答的选项式互动问题）"
  }},
  "xiaohongshu": {{
    "title": "小红书标题（不超过20字）",
    "cover_text": "封面短句（不超过12字）",
    "body": "小红书正文（450-800字，必须包含：我为什么测它、适合谁、安装前检查、10分钟实操任务、截图建议、卡住排查、避坑提醒、可复制提示词、具体互动问题。开头从我的具体场景开始，功能必须说成人话，结尾必须是可回答的选项题）\\n\\n{tags_str}",
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
1. 判断这个主题是'工具深度实测教程''工具说明书'还是'资讯观点文'。只要出现具体工具名、安装、教程、配置、怎么用，就优先按工具深度实测教程写。
2. 从原始内容中提取确实信息：工具名称、用途、平台、官方链接、安装入口、操作步骤、限制条件、来源链接。没有证据的地方标注'资料不足，建议核验'，不要用空话替代。
3. 把零散资讯补成一个可执行流程，必须让读者知道今天打开电脑后第一步点哪里、第二步准备什么测试素材、第三步输入什么提示词、第四步怎么判断成功。
4. 对不确定信息标注'需要自行核验'，不要编造。
5. 让内容像一个愿意长期付费的读者读完会说：这篇真的帮我少走了一步弯路。
6. 先设计一个真实人设入口：我为什么测这个工具；它对应普通人的哪个麻烦；读者为什么要继续看。"""

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
