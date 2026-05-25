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


def _fetch_tavily() -> list[dict[str, Any]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    items: list[dict[str, Any]] = []
    for query in TREND_QUERIES:
        try:
            payload = {
                "api_key": api_key,
                "query": query,
                "search_depth": "basic",
                "max_results": 5,
                "include_answer": True,
            }
            data = _get_json("https://api.tavily.com/search", payload=payload)
            for result in data.get("results") or []:
                items.append(
                    {
                        "source": "tavily",
                        "query": query,
                        "title": _compact(result.get("title", ""), 120),
                        "summary": _compact(result.get("content", "")),
                        "url": result.get("url", ""),
                    }
                )
        except Exception as exc:  # noqa: BLE001
            items.append({"source": "tavily", "query": query, "title": "Tavily 抓取失败", "summary": str(exc), "url": ""})
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


def collect_ai_trends() -> dict[str, Any]:
    items = _fetch_tavily() + _fetch_rss()
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
        "title": f"AI 最新资讯日报 {now[:10]}",
        "summary": "聚焦 AI 视频生成、创作者工具、效率工作流和职场妈妈可转化选题。",
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
