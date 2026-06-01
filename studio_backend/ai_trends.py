from __future__ import annotations

import base64
import json
import os
import re
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
    "AI productivity for working mothers time management",
    "China AI video generation tools latest news",
]

RSS_FEEDS = [
    "https://openai.com/news/rss.xml",
    "https://blog.google/technology/ai/rss/",
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
