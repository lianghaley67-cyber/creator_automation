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


def _compact(value: Any, limit: int = 120) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()[:limit].strip()


def _paragraphs(content: str) -> list[str]:
    parts = [
        re.sub(r"\s+", " ", item).strip(" -")
        for item in re.split(r"\n+|(?<=[。！？!?])", content)
    ]
    return [item for item in parts if len(item) >= 4]


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

    return build_channel_drafts(
        source_text=source_text,
        title=title,
        summary=summary,
        source_type=source_type,
        hashtags=hashtags,
    )


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

    system_prompt = f"""你是一位中文自媒体内容创作专家。
{persona_block}

语言硬规则：
- 文案主体必须使用中文，表达要像真人说话，不要翻译腔。
- AI 工具名、模型名、产品名、公司名、英文缩写和专有名词可以保留英文原名，例如 Claude、ChatGPT、NotebookLM、API、Vibe Coding。
- 不要把公认英文名称硬翻译成奇怪中文；但第一次出现英文缩写时，用一句中文解释它是干什么的。

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
    "markdown": "完整公众号文章（Markdown格式，800-1500字，用##分节）"
  }},
  "xiaohongshu": {{
    "title": "小红书标题（不超过20字）",
    "cover_text": "封面短句（不超过12字）",
    "body": "小红书正文（300-500字）\\n\\n{tags_str}",
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
{source_text[:3000]}"""

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

    if is_trend:
        wechat_intro = _compact(summary or paragraphs[0], 180)
        wechat_sections = [
            ("今天发生了什么", "\n".join(paragraphs[:4])),
            ("这对普通人意味着什么", "\n".join(paragraphs[4:7] or paragraphs[:2])),
            ("我准备怎么用", "先确认信息来源，再选一个和自己工作最相关的变化做小范围尝试，把判断留给自己。"),
        ]
        xhs_hook = "今天的变化很多，但真正值得普通人关注的，不是模型名字，而是哪些工作正在变得更省时间。"
        xhs_points = paragraphs[:4]
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
    wechat_markdown += "\n\n## 写在最后\n\n你遇到过类似的问题吗？可以先写下一个最想减少的重复动作。"

    xhs_title = _compact(final_title.replace("今天", ""), 20)
    xhs_lines = [xhs_hook]
    for index, point in enumerate(xhs_points[:5], start=1):
        xhs_lines.append(f"{index}. {_compact(point, 120)}")
    xhs_lines.append("我更愿意把 AI 当成助手：它负责整理，我负责判断。你最想先改掉哪个重复流程？")
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
