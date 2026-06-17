from __future__ import annotations

import base64
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from typing import Any

from .storage import STUDIO_DIR


TREND_QUERIES = [
    "AI tools for creators latest news",
    "AI video generation latest model updates",
    "AI coding tools software development latest news",
    "developer productivity AI agents GitHub latest updates",
    "AI productivity for working mothers time management",
    "China AI video generation tools latest news",
]

RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
    "https://github.blog/changelog/feed/",
    "https://huggingface.co/blog/feed.xml",
]


def _get_json(url: str, payload: dict[str, Any] | None = None, headers: dict[str, str] | None = None) -> dict[str, Any]:
    data = json.dumps(payload or {}, ensure_ascii=False).encode("utf-8") if payload is not None else None
    request = urllib.request.Request(
        url,
        data=data,
        headers={"Content-Type": "application/json", **(headers or {})},
        method="POST" if payload is not None else "GET",
    )
    with urllib.request.urlopen(request, timeout=25) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def _get_text(url: str) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": "CreatorStudio/1.0"})
    with urllib.request.urlopen(request, timeout=20) as response:
        return response.read().decode("utf-8", errors="replace")


def _compact(value: str, limit: int = 220) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def _question_subject(text: str, *, fallback: str = "今天这条 AI 资讯", limit: int = 28) -> str:
    subject = re.sub(r"https?://\S+", "", str(text or ""))
    subject = re.sub(r"[\[\]【】#*_`|<>]+", "", subject)
    subject = re.sub(r"\s+", " ", subject).strip(" -_—:：。，,")
    if not subject:
        subject = fallback
    return subject if len(subject) <= limit else subject[: limit - 1] + "…"


def _infer_life_work_focus(items: list[dict[str, Any]], query: str) -> str:
    corpus = " ".join(
        [
            query,
            *[str(item.get("title") or "") for item in items[:8]],
            *[str(item.get("summary") or "") for item in items[:8]],
        ]
    ).lower()
    if any(token in corpus for token in ("coding", "developer", "github", "software", "programming", "code", "ide", "开发", "编程", "代码", "工程", "程序员")):
        return "软件开发、工程效率和职业竞争力"
    if any(token in corpus for token in ("video", "creator", "短视频", "剪辑", "content", "filmmaking", "生成视频")):
        return "短视频创作和内容生产"
    if any(token in corpus for token in ("work", "productivity", "workflow", "效率", "办公", "职场", "time management")):
        return "普通人的工作效率和时间管理"
    if any(token in corpus for token in ("mom", "mother", "family", "妈妈", "育儿", "家庭", "带娃")):
        return "职场妈妈的生活安排和精力分配"
    if any(token in corpus for token in ("model", "gpt", "gemini", "claude", "accuracy", "模型", "准确", "幻觉")):
        return "AI 模型能力、误差和人的判断"
    return "普通人的生活、工作和学习方式"


def build_trend_questions(report: dict[str, Any]) -> list[str]:
    items = list(report.get("items") or [])
    query = str(report.get("query") or "").strip()
    title = _question_subject(report.get("title") or query, fallback="今天的 AI 最新趋势")
    first = _question_subject(items[0].get("title") if items else "", fallback=title)
    second = _question_subject(items[1].get("title") if len(items) > 1 else "", fallback=title)
    third = _question_subject(items[2].get("title") if len(items) > 2 else "", fallback=title)
    focus = _infer_life_work_focus(items, query)
    return [
        f"从「{first}」看，AI 正在解决普通人生活工作里的哪个具体问题？",
        f"如果把今天的资讯落到{focus}，最值得普通人立刻尝试的一个动作是什么？",
        f"「{second}」可能带来哪些机会和风险，哪些地方必须保留人的判断？",
        f"这些 AI 工具是不是完全准确？普通人怎么判断接口数据、模型输出和真实经验的边界？",
        f"如果用访谈方式深挖：这条资讯最触动我的一个焦虑、期待或真实经历是什么？",
        f"怎么把「{third}」转成一条有钩子、有观点、有行动建议的视频号口播文案？",
    ]


def build_trend_interview_followups(
    report: dict[str, Any],
    *,
    question: str,
    answer: str = "",
    depth: int = 1,
) -> list[str]:
    items = list(report.get("items") or [])
    query = str(report.get("query") or "").strip()
    first = _question_subject(items[0].get("title") if items else "", fallback=str(report.get("title") or "今天的 AI 资讯"))
    focus = _infer_life_work_focus(items, query)
    answer_text = _question_subject(answer, fallback="你刚才的回答", limit=42)
    depth = max(1, min(5, int(depth or 1)))
    if answer.strip():
        return [
            f"你提到「{answer_text}」，它背后真正担心的是时间、能力、收入，还是被技术替代？",
            f"如果围绕{focus}继续拆，你现在最想先解决的一个小场景是什么？",
            f"从「{first}」这条资讯看，你的判断有没有可能被接口数据或平台宣传带偏？",
            f"如果把你的回答写成视频号开头，哪一句最能让普通人立刻共鸣？",
        ]
    if depth <= 1:
        return [
            f"这个问题和你自己的工作/生活最贴近的场景是什么？",
            f"你看到「{first}」时，第一反应是兴奋、焦虑，还是怀疑？为什么？",
            f"如果只允许今天做一个小实验，你会把 AI 用在哪个动作上？",
            f"这件事里哪些判断必须由人来做，不能完全交给 AI？",
        ]
    return [
        f"继续往深处问：这件事会怎样改变普通人的{focus}？",
        "有没有一个你亲身经历过的瞬间，可以证明这个变化已经发生了？",
        "如果这个趋势判断错了，最可能错在哪里？",
        "最终写成文案时，你希望观众看完采取什么行动？",
    ]


def _normalize_query(query: str | None) -> str:
    return re.sub(r"\s+", " ", str(query or "")).strip()


def _fetch_tavily(query: str | None = None) -> list[dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    items: list[dict[str, Any]] = []
    search_queries = [_normalize_query(query)] if _normalize_query(query) else TREND_QUERIES
    for search_query in search_queries:
        try:
            payload = {
                "api_key": api_key,
                "query": search_query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            }
            data = _get_json("https://api.tavily.com/search", payload=payload)
            for result in data.get("results") or []:
                items.append(
                    {
                        "source": "tavily",
                        "query": search_query,
                        "title": _compact(result.get("title", ""), 120),
                        "summary": _compact(result.get("content", "")),
                        "url": result.get("url", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            items.append({"source": "tavily", "query": search_query, "title": "Tavily 抓取失败", "summary": str(exc), "url": ""})
    return items


def _fetch_rss() -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for feed in RSS_FEEDS:
        try:
            root = ET.fromstring(_get_text(feed))
            for item in root.findall(".//item")[:5]:
                title = item.findtext("title") or ""
                link = item.findtext("link") or ""
                description = item.findtext("description") or ""
                items.append(
                    {
                        "source": "rss",
                        "query": feed,
                        "title": _compact(title, 120),
                        "summary": _compact(re.sub(r"<[^>]+>", "", description)),
                        "url": link,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            items.append({"source": "rss", "query": feed, "title": "RSS 抓取失败", "summary": str(exc), "url": feed})
    return items


def collect_ai_trends(query: str | None = None) -> dict[str, Any]:
    normalized_query = _normalize_query(query)
    items = _fetch_tavily(normalized_query) + ([] if normalized_query else _fetch_rss())
    seen: set[str] = set()
    deduped: list[dict[str, Any]] = []
    for item in items:
        key = item.get("url") or item.get("title")
        if not key or key in seen:
            continue
        seen.add(key)
        deduped.append(item)
    selected = deduped[:20]
    now = datetime.now().isoformat(timespec="seconds")
    report = {
        "created_at": now,
        "query": normalized_query,
        "title": f"{normalized_query} 资讯检索 {now[:10]}" if normalized_query else f"AI 最新资讯日报 {now[:10]}",
        "summary": (
            f"按你的要求检索：{normalized_query}。以下内容来自 Tavily 接口返回结果，适合继续转成学习问答、选题和口播文案。"
            if normalized_query
            else "聚焦 AI 视频生成、创作者工具、效率工作流和职场妈妈可转化选题。"
        ),
        "items": selected,
        "angles": [
            "把 AI 新工具转译成职场妈妈能立刻用的省时方法。",
            "从 AI 视频生成更新中提炼短视频创作提效选题。",
            "用普通人的学习感悟解释技术变化，降低新技术焦虑。",
        ],
    }
    report["suggested_questions"] = build_trend_questions(report)
    archive_dir = STUDIO_DIR / "ai_trends"
    archive_dir.mkdir(parents=True, exist_ok=True)
    (archive_dir / f"{now[:10]}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def build_notebooklm_import_package(report: dict[str, Any] | None = None) -> dict[str, Any]:
    data = report or {}
    if not data:
        archive_dir = STUDIO_DIR / "ai_trends"
        latest = sorted(archive_dir.glob("*.json"), reverse=True)[:1] if archive_dir.exists() else []
        if latest:
            try:
                data = json.loads(latest[0].read_text(encoding="utf-8", errors="replace"))
            except Exception:  # noqa: BLE001
                data = {}
    if not data:
        data = collect_ai_trends()

    created_at = str(data.get("created_at") or datetime.now().isoformat(timespec="seconds"))
    title = str(data.get("title") or f"AI 最新资讯日报 {created_at[:10]}")
    items = list(data.get("items") or [])
    angles = list(data.get("angles") or [])
    lines = [
        f"# {title} - NotebookLM 导入包",
        "",
        "## 使用方式",
        "",
        "1. 打开 NotebookLM，新建一个 notebook。",
        "2. 把这份 Markdown 作为资料源上传或复制进去。",
        "3. 让 NotebookLM 先总结趋势，再生成 Audio Overview / 播客音频。",
        "",
        "## 播客分析指令",
        "",
        "请以“职场精英妈妈/AI 科技女性”的频道定位分析下面的 AI 资讯：",
        "- 先提炼 3 个普通人能听懂的技术变化。",
        "- 再判断哪些适合转化成视频号口播、嘉宾访谈或图文。",
        "- 最后生成一段 6-8 分钟播客大纲，语气要高认知、强共情、有温度。",
        "",
        "## 今日摘要",
        "",
        str(data.get("summary") or "").strip(),
        "",
        "## 可转化选题角度",
        "",
    ]
    lines.extend(f"- {angle}" for angle in angles)
    lines.extend(["", "## 资讯来源", ""])
    source_urls: list[str] = []
    for index, item in enumerate(items, 1):
        title_text = str(item.get("title") or "未命名资讯").strip()
        summary = str(item.get("summary") or "").strip()
        url = str(item.get("url") or "").strip()
        source = str(item.get("source") or "").strip()
        if url and url not in source_urls:
            source_urls.append(url)
        lines.append(f"### {index}. {title_text}")
        lines.append("")
        if source:
            lines.append(f"- 来源：{source}")
        if url:
            lines.append(f"- 链接：{url}")
        if summary:
            lines.append(f"- 摘要：{summary}")
        lines.append("")
    lines.extend(
        [
            "## 给 NotebookLM 的输出要求",
            "",
            "请生成：",
            "- 一份适合微信视频号的选题清单。",
            "- 一份双人访谈播客脚本，角色为理性 AI 专家和真实职场妈妈。",
            "- 一份真人出镜口播稿，保留 3 秒钩子、3 个方法、评论区互动。",
        ]
    )

    package_dir = STUDIO_DIR / "notebooklm"
    package_dir.mkdir(parents=True, exist_ok=True)
    safe_date = created_at[:10] or datetime.now().strftime("%Y-%m-%d")
    file_path = package_dir / f"{safe_date}-ai-trends-notebooklm.md"
    body = "\n".join(lines).strip() + "\n"
    file_path.write_text(body, encoding="utf-8")
    links_path = package_dir / f"{safe_date}-ai-trends-source-links.txt"
    links_path.write_text("\n".join(source_urls).strip() + "\n", encoding="utf-8")
    return {
        "status": "ok",
        "title": title,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "path": str(file_path),
        "url": f"/studio-files/notebooklm/{file_path.name}",
        "source_urls": source_urls,
        "source_links_path": str(links_path),
        "source_links_url": f"/studio-files/notebooklm/{links_path.name}",
        "body": body,
    }


def _openai_chat_call(
    *,
    messages: list[dict[str, str]],
    model: str | None = None,
    temperature: float = 0.7,
    max_tokens: int = 1500,
) -> str:
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY 未配置，无法调用 AI 摘要或讨论功能。")
    base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com").strip()
    model_name = model or os.getenv("OPENAI_MODEL", os.getenv("LLM_MODEL", "gpt-4o-mini")).strip() or "gpt-4o-mini"
    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model_name,
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
        raise RuntimeError(f"OpenAI API 调用失败 {exc.code}: {body[:300]}") from exc


def summarize_trends_with_ai(report: dict[str, Any]) -> dict[str, Any]:
    """调用 OpenAI 对抓取到的资讯进行结构化摘要，返回关键点、内容角度和建议 Skill。"""
    items = list(report.get("items") or [])
    query = str(report.get("query") or "").strip()

    items_text = "\n".join(
        f"{i+1}. 【{item.get('title', '')}】{item.get('summary', '')}"
        for i, item in enumerate(items[:12])
    )

    system_prompt = (
        "你是一位专注于 AI 领域的内容顾问，帮助「知识成长女性」类账号创作自媒体内容。"
        "账号目标：用大白话普及 AI 知识，吸引对 AI 感兴趣的普通人，人设是知识成长女性，后续考虑变现。"
        "语言要求：内容主体必须使用中文；AI 工具名、模型名、产品名、公司名、英文缩写和专有名词可以保留英文原名，例如 Claude、ChatGPT、NotebookLM、API。"
        "运营要求：不要复述新闻，要替读者判断价值、补齐背景、给出最小可执行动作和风险提醒。"
        "参考姜胡说式思路：不是追热点，而是把信息变成行动飞轮；不是知道更多，而是找到一个简单动作大量重复。"
        "请对提供的 AI 资讯进行结构化分析，输出纯 JSON，不加任何额外说明。"
    )
    user_prompt = f"""以下是今天抓取到的 AI 资讯（检索主题：{query or "AI最新资讯"}）：

{items_text}

请输出 JSON，格式如下：
{{
  "one_sentence": "一句话说清今天最重要的AI变化（不超过30字）",
  "key_points": [
    "关键点1：用大白话说清楚，不用技术词汇（30字内）",
    "关键点2：同上",
    "关键点3：同上"
  ],
  "plain_explanation": "用普通人能听懂的语言解释这些资讯的意义（100-150字，不用技术名词）",
  "content_angles": [
    "适合转成内容的角度1（20字内）",
    "适合转成内容的角度2（20字内）",
    "适合转成内容的角度3（20字内）"
  ],
  "reader_value": "读者看完能解决的一个具体问题（30字内）",
  "action_plan": ["今天能做的第1步", "第2步", "第3步"],
  "risk_notes": ["需要核验或容易踩坑的地方1", "地方2"],
  "suggested_wechat_skill": "从以下选一个最合适的：wechat_article_v1 / wechat_ai_popularizer_v1 / wechat_growth_female_v1 / wechat_tool_guide_v1 / wechat_operator_flywheel_v1",
  "suggested_xhs_skill": "从以下选一个最合适的：xiaohongshu_note_v1 / xiaohongshu_ai_popularizer_v1 / xiaohongshu_growth_female_v1 / xiaohongshu_tool_guide_v1 / xiaohongshu_monetization_v1 / xiaohongshu_operator_flywheel_v1",
  "skill_reason": "为什么推荐这两个 Skill（20字内）",
  "suggested_hashtags": ["话题标签1", "话题标签2", "话题标签3", "话题标签4"]
}}"""

    try:
        raw = _openai_chat_call(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.6,
            max_tokens=1200,
        )
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if json_match:
            return json.loads(json_match.group())
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:300]}
    return {"error": "AI 返回内容无法解析"}


def chat_about_trend(
    *,
    messages: list[dict[str, str]],
    trend_context: str = "",
    query: str = "",
) -> dict[str, Any]:
    """多轮讨论：基于资讯背景与用户展开对话，引导提炼内容选题。"""
    context_block = ""
    if trend_context:
        context_block = f"\n\n【今日资讯背景】\n{trend_context[:1000]}"

    system_prompt = (
        "你是一位熟悉 AI 领域的内容创作顾问，正在帮助一位「知识成长女性」自媒体博主将 AI 资讯转化为优质内容。"
        "对话风格：像聊天一样自然，用普通话，不用技术词汇。"
        "语言要求：主体回答用中文；遇到 AI 工具名、模型名、产品名、公司名、英文缩写和专有名词时保留英文原名，例如 Claude、ChatGPT、NotebookLM、API。"
        "你的目标：帮助博主：1）理解这条资讯的本质；2）找到与自己受众相关的角度；3）提炼可拍的内容选题。"
        "每次回复结构：先回答问题（2-3句话），再给出1-2个追问方向引导深入思考。"
        f"{context_block}"
    )

    ai_messages = [{"role": "system", "content": system_prompt}] + list(messages)

    try:
        response_text = _openai_chat_call(
            messages=ai_messages,
            temperature=0.75,
            max_tokens=600,
        )
    except Exception as exc:  # noqa: BLE001
        return {"status": "error", "error": str(exc)[:300], "response": "", "followup_questions": []}

    # 从回复里提取追问问题（简单规则）
    followup_questions: list[str] = []
    lines = response_text.split("\n")
    for line in lines:
        stripped = line.strip(" -•·1234567890.）)")
        if stripped and len(stripped) > 10 and stripped.endswith("？"):
            followup_questions.append(stripped)

    return {
        "status": "ok",
        "response": response_text,
        "followup_questions": followup_questions[:3],
    }


def archive_markdown_to_obsidian(*, title: str, body: str, source: str = "creator_studio") -> dict[str, Any]:
    safe_title = re.sub(r"[\\/:*?\"<>|#\[\]]+", "-", title).strip("- ") or "creator-studio-copy"
    date_text = datetime.now().strftime("%Y-%m-%d")
    archive_dir = os.getenv("OBSIDIAN_ARCHIVE_DIR", "01_Inbox/CreatorStudio").strip().strip("/")
    path = f"{archive_dir}/{date_text}-{safe_title[:48]}.md"
    markdown = f"---\nsource: {source}\ncreated: {datetime.now().isoformat(timespec='seconds')}\n---\n\n# {title}\n\n{body.strip()}\n"

    local_dir = STUDIO_DIR / "obsidian_archive"
    local_dir.mkdir(parents=True, exist_ok=True)
    local_path = local_dir / Path(path).name
    local_path.write_text(markdown, encoding="utf-8")

    token = os.getenv("GITEE_ACCESS_TOKEN", "").strip()
    owner = os.getenv("OBSIDIAN_REPO_OWNER", "lianghuanhuan").strip()
    repo = os.getenv("OBSIDIAN_REPO_NAME", "obsidian").strip()
    if not token:
        return {"status": "local_only", "path": str(local_path), "gitee_path": path, "message": "未配置 GITEE_ACCESS_TOKEN，已先保存到服务器本地。"}

    encoded_path = urllib.parse.quote(path, safe="")
    url = f"https://gitee.com/api/v5/repos/{owner}/{repo}/contents/{encoded_path}"
    payload = {
        "access_token": token,
        "content": base64.b64encode(markdown.encode("utf-8")).decode("ascii"),
        "message": f"Archive Creator Studio copy: {safe_title[:40]}",
        "branch": "master",
    }
    try:
        response = _get_json(url, payload=payload)
        return {"status": "archived", "path": str(local_path), "gitee_path": path, "response": response}
    except Exception as exc:  # noqa: BLE001
        return {"status": "local_only", "path": str(local_path), "gitee_path": path, "error": str(exc)}
