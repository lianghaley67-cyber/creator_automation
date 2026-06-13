from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from .storage import OUTPUTS_DIR, make_id, now_iso, to_media_url


WECHAT_API_ROOT = "https://api.weixin.qq.com/cgi-bin"
XIAOHONGSHU_CREATOR_URL = os.getenv(
    "XIAOHONGSHU_CREATOR_URL", "https://creator.xiaohongshu.com/publish/publish"
).strip()


def _compact(value: Any, limit: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text[:limit].strip()


def _plain_script(job: dict[str, Any]) -> str:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    return str(
        job.get("script_text")
        or request_payload.get("custom_script")
        or request_payload.get("story_memo")
        or request_payload.get("topic")
        or ""
    ).strip()


def _default_hashtags(job: dict[str, Any]) -> list[str]:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    tags = list(request_payload.get("keywords") or [])
    mode = str(request_payload.get("content_mode") or "").strip()
    if mode == "working_mom":
        tags.extend(["职场妈妈", "一人公司", "AI提效"])
    tags.extend(["内容创作", "成长复盘"])
    output: list[str] = []
    for item in tags:
        normalized = re.sub(r"[#\s]+", "", str(item or "")).strip()
        if normalized and normalized not in output:
            output.append(normalized[:18])
    return output[:8]


def _wechat_html(title: str, summary: str, script: str) -> str:
    paragraphs = [
        html.escape(item.strip())
        for item in re.split(r"\n+|(?<=[。！？!?])", script)
        if item.strip()
    ]
    body = "".join(
        f'<p style="font-size:16px;line-height:1.9;color:#243241;margin:0 0 16px;">{item}</p>'
        for item in paragraphs
    )
    intro = (
        f'<blockquote style="margin:0 0 22px;padding:12px 16px;border-left:4px solid #00a8b5;'
        f'background:#f3fafb;color:#526273;">{html.escape(summary)}</blockquote>'
        if summary
        else ""
    )
    return (
        '<section style="max-width:100%;font-family:-apple-system,BlinkMacSystemFont,'
        "'Segoe UI','Microsoft YaHei',sans-serif;\">"
        f"<h1 style=\"font-size:24px;line-height:1.45;color:#132431;\">{html.escape(title)}</h1>"
        f"{intro}{body}</section>"
    )


def prepare_distribution_package(
    job: dict[str, Any],
    *,
    title: str = "",
    summary: str = "",
    author: str = "",
    hashtags: list[str] | None = None,
) -> dict[str, Any]:
    if str(job.get("status") or "").lower() != "completed":
        raise ValueError("任务完成后才能准备分发。")
    script = _plain_script(job)
    if not script:
        raise ValueError("当前任务没有可分发的文案。")
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    final_title = _compact(title or request_payload.get("title") or request_payload.get("topic"), 64)
    if not final_title:
        final_title = "今天这件事，我终于想明白了"
    final_summary = _compact(summary or script, 120)
    final_tags = hashtags or _default_hashtags(job)
    xhs_title = _compact(final_title, 20)
    xhs_body = f"{script}\n\n" + " ".join(f"#{tag}" for tag in final_tags)

    task_id = make_id("distribution")
    package_dir = OUTPUTS_DIR / "distribution" / task_id
    package_dir.mkdir(parents=True, exist_ok=True)
    wechat_file = package_dir / "wechat_article.html"
    xhs_file = package_dir / "xiaohongshu_note.txt"
    manifest_file = package_dir / "manifest.json"
    wechat_file.write_text(_wechat_html(final_title, final_summary, script), encoding="utf-8")
    xhs_file.write_text(f"{xhs_title}\n\n{xhs_body}", encoding="utf-8")

    artifacts = job.get("artifacts") if isinstance(job.get("artifacts"), dict) else {}
    record = {
        "id": task_id,
        "job_id": str(job.get("id") or ""),
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "status": "prepared",
        "title": final_title,
        "summary": final_summary,
        "author": _compact(author, 32),
        "hashtags": final_tags,
        "script": script,
        "source_artifacts": artifacts,
        "wechat": {
            "status": "ready",
            "article_html_url": to_media_url(wechat_file),
            "draft_media_id": "",
            "publish_id": "",
        },
        "xiaohongshu": {
            "status": "ready_for_manual_confirm",
            "creator_url": XIAOHONGSHU_CREATOR_URL,
            "title": xhs_title,
            "body": xhs_body,
            "note_url": to_media_url(xhs_file),
            "manual_confirm_required": True,
        },
    }
    manifest_file.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    record["manifest_url"] = to_media_url(manifest_file)
    return record


def prepare_material_distribution_package(
    material: dict[str, Any],
    *,
    title: str = "",
    summary: str = "",
    author: str = "",
    hashtags: list[str] | None = None,
) -> dict[str, Any]:
    script = str(material.get("script") or "").strip()
    if not script:
        raise ValueError("这条微信素材还没有生成文案。")
    source_text = str(material.get("text") or "").strip()
    synthetic_job = {
        "id": f"material:{material.get('id', '')}",
        "status": "completed",
        "script_text": script,
        "request": {
            "topic": title or source_text[:64] or "微信素材文章",
            "title": title,
            "content_mode": material.get("content_mode", ""),
            "keywords": list(material.get("keywords") or []),
        },
        "artifacts": {},
    }
    record = prepare_distribution_package(
        synthetic_job,
        title=title,
        summary=summary,
        author=author,
        hashtags=hashtags,
    )
    record["job_id"] = ""
    record["material_id"] = str(material.get("id") or "")
    record["source_type"] = "wechat_material"
    return record


def _post_wechat_json(path: str, token: str, payload: dict[str, Any]) -> dict[str, Any]:
    url = f"{WECHAT_API_ROOT}/{path}?{urllib.parse.urlencode({'access_token': token})}"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json; charset=utf-8"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    if int(result.get("errcode") or 0):
        raise RuntimeError(
            f"微信接口失败：{result.get('errcode')} {result.get('errmsg') or '未知错误'}"
        )
    return result


def submit_wechat_draft(
    task: dict[str, Any],
    *,
    get_access_token: Callable[[], str],
    publish_now: bool = False,
    thumb_media_id: str = "",
) -> dict[str, Any]:
    token = get_access_token()
    if not token:
        raise RuntimeError("未配置 WECHAT_APP_ID / WECHAT_APP_SECRET。")
    thumb_media_id = str(
        thumb_media_id or os.getenv("WECHAT_THUMB_MEDIA_ID", "")
    ).strip()
    if not thumb_media_id:
        raise RuntimeError("未配置 WECHAT_THUMB_MEDIA_ID，请先上传一张公众号永久封面图。")
    article_path = OUTPUTS_DIR / "distribution" / str(task.get("id")) / "wechat_article.html"
    if not article_path.exists():
        raise RuntimeError("公众号文章文件不存在，请重新准备分发包。")
    article = {
        "title": str(task.get("title") or ""),
        "author": str(task.get("author") or ""),
        "digest": str(task.get("summary") or ""),
        "content": article_path.read_text(encoding="utf-8"),
        "thumb_media_id": thumb_media_id,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }
    draft_result = _post_wechat_json("draft/add", token, {"articles": [article]})
    media_id = str(draft_result.get("media_id") or "")
    result = {
        "status": "draft_created",
        "draft_media_id": media_id,
        "submitted_at": now_iso(),
        "publish_id": "",
    }
    if publish_now:
        publish_result = _post_wechat_json(
            "freepublish/submit", token, {"media_id": media_id}
        )
        result.update(
            {
                "status": "publishing",
                "publish_id": str(publish_result.get("publish_id") or ""),
            }
        )
    return result


def upload_wechat_cover(
    *,
    filename: str,
    content_type: str,
    body: bytes,
    get_access_token: Callable[[], str],
) -> dict[str, Any]:
    token = get_access_token()
    if not token:
        raise RuntimeError("未配置 WECHAT_APP_ID / WECHAT_APP_SECRET。")
    if not body:
        raise RuntimeError("封面图片为空。")
    boundary = f"----CreatorStudio{make_id('cover').replace('_', '')}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", filename or "cover.jpg")
    multipart = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_type or 'image/jpeg'}\r\n\r\n"
    ).encode("utf-8") + body + f"\r\n--{boundary}--\r\n".encode("utf-8")
    query = urllib.parse.urlencode({"access_token": token, "type": "image"})
    request = urllib.request.Request(
        f"{WECHAT_API_ROOT}/material/add_material?{query}",
        data=multipart,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    if int(result.get("errcode") or 0):
        raise RuntimeError(
            f"微信封面上传失败：{result.get('errcode')} {result.get('errmsg') or '未知错误'}"
        )
    media_id = str(result.get("media_id") or "").strip()
    if not media_id:
        raise RuntimeError(f"微信封面上传未返回 media_id：{result}")
    return {"media_id": media_id, "url": str(result.get("url") or "")}
