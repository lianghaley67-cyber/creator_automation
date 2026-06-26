"""
Supabase-backed story archive for AI serial fiction.
Tables: stories, chapters, story_bible
"""
from __future__ import annotations

import json
import os
import re
import urllib.request
import urllib.error
from datetime import datetime, timezone
from typing import Any

def _url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def _key() -> str:
    return os.getenv("SUPABASE_ANON_KEY", "")


def _enabled() -> bool:
    return bool(_url() and _key())


def _headers() -> dict[str, str]:
    k = _key()
    return {
        "apikey": k,
        "Authorization": f"Bearer {k}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _rest(method: str, table: str, body: Any = None, params: str = "") -> list[dict]:
    if not _enabled():
        return []
    url = f"{_url()}/rest/v1/{table}"
    if params:
        url = f"{url}?{params}"
    data = json.dumps(body, ensure_ascii=False).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, headers=_headers(), method=method)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            raw = resp.read().decode("utf-8")
            result = json.loads(raw) if raw.strip() else []
            return result if isinstance(result, list) else [result]
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Supabase {method} {table} error {exc.code}: {err[:300]}") from exc
    except urllib.error.URLError as exc:
        import logging
        logging.getLogger(__name__).warning("Supabase %s %s network error: %s", method, table, exc.reason)
        return []


# ── Stories ────────────────────────────────────────────────────────────────

def list_stories() -> list[dict]:
    return _rest("GET", "stories", params="order=created_at.desc")


def get_story(story_id: str) -> dict:
    rows = _rest("GET", "stories", params=f"id=eq.{story_id}")
    return rows[0] if rows else {}


def create_story(name: str, genre: str = "fantasy", style_notes: str = "") -> dict:
    rows = _rest("POST", "stories", {
        "name": name,
        "genre": genre,
        "style_notes": style_notes,
    })
    story = rows[0] if rows else {}
    if story.get("id"):
        _rest("POST", "story_bible", {
            "story_id": story["id"],
            "characters": [],
            "world_notes": "",
            "ongoing_threads": [],
            "last_chapter_number": 0,
        })
    return story


def update_story(story_id: str, *, name: str | None = None, style_notes: str | None = None) -> dict:
    body: dict = {"updated_at": _now()}
    if name is not None:
        body["name"] = name
    if style_notes is not None:
        body["style_notes"] = style_notes
    rows = _rest("PATCH", "stories", body, f"id=eq.{story_id}")
    return rows[0] if rows else {}


def delete_story(story_id: str) -> None:
    """删除故事及其所有章节（CASCADE）"""
    _rest("DELETE", "stories", params=f"id=eq.{story_id}")


# ── Chapters ───────────────────────────────────────────────────────────────

def list_chapters(story_id: str) -> list[dict]:
    return _rest("GET", "chapters", params=f"story_id=eq.{story_id}&order=chapter_number.asc")


def get_chapter(story_id: str, chapter_number: int) -> dict:
    rows = _rest("GET", "chapters", params=f"story_id=eq.{story_id}&chapter_number=eq.{chapter_number}")
    return rows[0] if rows else {}


def save_chapter(
    *,
    story_id: str,
    chapter_number: int,
    title: str,
    content_markdown: str,
    content_xhs: str = "",
    context_summary: str = "",
) -> dict:
    body = {
        "story_id": story_id,
        "chapter_number": chapter_number,
        "title": title,
        "content_markdown": content_markdown,
        "content_xhs": content_xhs,
        "context_summary": context_summary or _auto_summary(content_markdown),
    }
    rows = _rest("POST", "chapters", body)
    _rest("PATCH", "story_bible",
          {"last_chapter_number": chapter_number, "updated_at": _now()},
          f"story_id=eq.{story_id}")
    return rows[0] if rows else {}


def delete_chapter(story_id: str, chapter_number: int) -> None:
    """删除单章，story_bible 中的 last_chapter_number 自动回退"""
    _rest("DELETE", "chapters",
          params=f"story_id=eq.{story_id}&chapter_number=eq.{chapter_number}")
    # 回退 last_chapter_number
    remaining = list_chapters(story_id)
    last_num = max((c["chapter_number"] for c in remaining), default=0)
    _rest("PATCH", "story_bible",
          {"last_chapter_number": last_num, "updated_at": _now()},
          f"story_id=eq.{story_id}")


# ── Story Bible ────────────────────────────────────────────────────────────

def get_story_bible(story_id: str) -> dict:
    rows = _rest("GET", "story_bible", params=f"story_id=eq.{story_id}")
    return rows[0] if rows else {}


def update_story_bible(
    story_id: str,
    *,
    characters: list | None = None,
    world_notes: str | None = None,
    ongoing_threads: list | None = None,
) -> None:
    body: dict = {"updated_at": _now()}
    if characters is not None:
        body["characters"] = characters
    if world_notes is not None:
        body["world_notes"] = world_notes
    if ongoing_threads is not None:
        body["ongoing_threads"] = ongoing_threads
    _rest("PATCH", "story_bible", body, f"story_id=eq.{story_id}")


# ── Context Builder ────────────────────────────────────────────────────────

def build_story_context(story_id: str) -> str:
    """为下一章生成注入 prompt 的上下文字符串。"""
    if not story_id or not _enabled():
        return ""
    bible = get_story_bible(story_id)
    if not bible:
        return ""

    last_num = bible.get("last_chapter_number", 0)
    parts: list[str] = ["【故事档案 · 续写上下文】"]

    # 人物表
    chars = bible.get("characters") or []
    if chars:
        char_lines = [
            f"- {c.get('name','')}（{c.get('role','')}）：{c.get('status','')}"
            for c in chars if c.get("name")
        ]
        if char_lines:
            parts.append("人物：\n" + "\n".join(char_lines))

    # 世界观
    world = (bible.get("world_notes") or "").strip()
    if world:
        parts.append(f"世界观：{world}")

    # 未解悬念
    threads = bible.get("ongoing_threads") or []
    open_threads = [t for t in threads if t.get("status") != "resolved"]
    if open_threads:
        thread_lines = [f"- {t.get('thread','')}" for t in open_threads if t.get("thread")]
        if thread_lines:
            parts.append("未解悬念：\n" + "\n".join(thread_lines))

    # 历史章节摘要（除最后一章）
    if last_num > 1:
        chapters = list_chapters(story_id)
        old = [c for c in chapters if c["chapter_number"] < last_num]
        if old:
            summaries = [
                f"第{c['chapter_number']}章《{c['title']}》：{c['context_summary']}"
                for c in old
            ]
            parts.append("前情摘要：\n" + "\n".join(summaries))

    # 上一章完整内容
    if last_num >= 1:
        chapters = list_chapters(story_id)
        last = next((c for c in chapters if c["chapter_number"] == last_num), None)
        if last:
            md = (last.get("content_markdown") or "")[:3000]
            parts.append(
                f"【上一章完整内容 · 第{last_num}章《{last['title']}》】\n{md}"
            )

    parts.append(f"当前任务：续写第 {last_num + 1} 章")
    return "\n\n".join(parts)


def next_chapter_number(story_id: str) -> int:
    bible = get_story_bible(story_id)
    return (bible.get("last_chapter_number") or 0) + 1


def build_story_context_for_chapter(story_id: str, target_chapter: int) -> str:
    """为重新生成指定章节构建上下文，只使用 target_chapter 之前的章节作为背景。"""
    if not story_id or not _enabled():
        return ""
    bible = get_story_bible(story_id)
    if not bible:
        return ""

    parts: list[str] = ["【故事档案 · 重写上下文】"]

    chars = bible.get("characters") or []
    if chars:
        char_lines = [
            f"- {c.get('name','')}（{c.get('role','')}）：{c.get('status','')}"
            for c in chars if c.get("name")
        ]
        if char_lines:
            parts.append("人物：\n" + "\n".join(char_lines))

    world = (bible.get("world_notes") or "").strip()
    if world:
        parts.append(f"世界观：{world}")

    threads = bible.get("ongoing_threads") or []
    open_threads = [t for t in threads if t.get("status") != "resolved"]
    if open_threads:
        thread_lines = [f"- {t.get('thread','')}" for t in open_threads if t.get("thread")]
        if thread_lines:
            parts.append("未解悬念：\n" + "\n".join(thread_lines))

    chapters = list_chapters(story_id)
    prev_chapters = [c for c in chapters if c["chapter_number"] < target_chapter]

    if len(prev_chapters) > 1:
        old = prev_chapters[:-1]
        summaries = [
            f"第{c['chapter_number']}章《{c['title']}》：{c['context_summary']}"
            for c in old
        ]
        parts.append("前情摘要：\n" + "\n".join(summaries))

    if prev_chapters:
        last = prev_chapters[-1]
        md = (last.get("content_markdown") or "")[:3000]
        parts.append(
            f"【上一章完整内容 · 第{last['chapter_number']}章《{last['title']}》】\n{md}"
        )

    parts.append(
        f"当前任务：重新创作第 {target_chapter} 章（原版审核不通过，需完整重写；"
        f"剧情必须与第 {target_chapter - 1} 章无缝衔接，不能出现剧情断裂）"
    )
    return "\n\n".join(parts)


# ── AI Context Extraction ──────────────────────────────────────────────────

def extract_and_update_bible(
    story_id: str,
    chapter_markdown: str,
    *,
    api_key: str,
    base_url: str,
    model: str,
) -> None:
    """用 AI 从章节内容提取人物/世界观/悬念，并合并更新 story_bible。"""
    if not story_id or not api_key:
        return

    bible = get_story_bible(story_id)
    existing_chars = bible.get("characters") or []
    existing_world = bible.get("world_notes") or ""
    existing_threads = bible.get("ongoing_threads") or []

    prompt = f"""从以下小说章节内容中提取结构化信息，输出合法 JSON，不加任何说明：

{{
  "characters": [
    {{"name": "人物名", "role": "身份/关系", "status": "本章结束时的状态或动态"}}
  ],
  "world_notes": "世界观关键信息一句话（补充或更新，不重复）",
  "ongoing_threads": [
    {{"thread": "悬念描述", "status": "open 或 resolved"}}
  ]
}}

已有人物：{json.dumps(existing_chars, ensure_ascii=False)}
已有世界观：{existing_world}
已有悬念：{json.dumps(existing_threads, ensure_ascii=False)}

章节内容（前2000字）：
{chapter_markdown[:2000]}"""

    endpoint = base_url.rstrip("/") + "/v1/chat/completions"
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.3,
        "max_tokens": 800,
    }
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        endpoint, data=data,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {api_key}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            raw = str(result["choices"][0]["message"]["content"]).strip()
        json_match = re.search(r"\{[\s\S]*\}", raw)
        if not json_match:
            return
        extracted = json.loads(json_match.group())
        # 合并人物（按名字去重，更新状态）
        merged_chars = {c["name"]: c for c in existing_chars}
        for c in (extracted.get("characters") or []):
            if c.get("name"):
                merged_chars[c["name"]] = {**merged_chars.get(c["name"], {}), **c}
        # 合并世界观
        new_world = (extracted.get("world_notes") or "").strip()
        merged_world = f"{existing_world}；{new_world}".strip("；") if new_world and new_world not in existing_world else existing_world
        # 合并悬念（按内容去重，允许状态更新）
        merged_threads_map = {t["thread"]: t for t in existing_threads if t.get("thread")}
        for t in (extracted.get("ongoing_threads") or []):
            if t.get("thread"):
                merged_threads_map[t["thread"]] = t
        update_story_bible(
            story_id,
            characters=list(merged_chars.values()),
            world_notes=merged_world,
            ongoing_threads=list(merged_threads_map.values()),
        )
    except Exception:  # noqa: BLE001
        pass  # 提取失败不影响主流程


def _auto_summary(markdown: str, max_chars: int = 300) -> str:
    """快速摘要：取正文前 max_chars 字符，去掉标题行。"""
    lines = [ln.strip() for ln in markdown.splitlines() if ln.strip() and not ln.startswith("#")]
    return " ".join(lines)[:max_chars]
