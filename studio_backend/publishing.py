from __future__ import annotations

import html
import json
import os
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Callable

from .channel_skills import build_channel_drafts, build_channel_drafts_with_ai, render_xiaohongshu_cards
from .storage import OUTPUTS_DIR, STUDIO_DIR, make_id, now_iso, to_media_url


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


def _clean_ai_trend_title(raw_title: str, trend: dict[str, Any]) -> str:
    query = str(trend.get("query") or "").strip()
    title = str(raw_title or query or trend.get("title") or "").strip()
    title = re.sub(r"\s*资讯检索\s*\d{4}-\d{2}-\d{2}\s*$", "", title).strip()
    title = re.sub(r"\s*AI 最新资讯日报\s*\d{4}-\d{2}-\d{2}\s*$", "AI 最新资讯日报", title).strip()
    title = re.sub(r"\s*\d{4}-\d{2}-\d{2}\s*$", "", title).strip()
    title = title or query or "今天值得关注的 AI 资讯"
    lower_title = title.lower()
    if len(title) <= 24 and any(word in lower_title for word in ("安装", "install", "教程", "说明")):
        return _compact(f"{title}：先看这3个坑", 32)
    if len(title) <= 18:
        return _compact(f"{title}：普通人怎么用", 32)
    return _compact(title, 48)


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


def _wechat_channel_html(markdown: str) -> str:
    blocks: list[str] = []
    for raw in str(markdown or "").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("# "):
            blocks.append(
                f'<h1 style="font-size:24px;line-height:1.45;color:#132431;">{html.escape(line[2:])}</h1>'
            )
        elif line.startswith("## "):
            blocks.append(
                f'<h2 style="font-size:19px;line-height:1.6;color:#0b6670;margin-top:28px;">{html.escape(line[3:])}</h2>'
            )
        else:
            blocks.append(
                f'<p style="font-size:16px;line-height:1.9;color:#243241;margin:0 0 16px;">{html.escape(line)}</p>'
            )
    return (
        '<section style="max-width:100%;font-family:-apple-system,BlinkMacSystemFont,'
        "'Segoe UI','Microsoft YaHei',sans-serif;\">"
        + "".join(blocks)
        + "</section>"
    )


def _source_media_files(artifacts: dict[str, Any]) -> list[Path]:
    candidates: list[str] = []

    def collect(value: Any) -> None:
        if isinstance(value, dict):
            for item in value.values():
                collect(item)
        elif isinstance(value, list):
            for item in value:
                collect(item)
        elif isinstance(value, str):
            candidates.append(value)

    collect(artifacts)
    files: list[Path] = []
    seen: set[Path] = set()
    for value in candidates:
        path: Path | None = None
        if value.startswith("/studio-files/"):
            path = STUDIO_DIR / value.removeprefix("/studio-files/")
        else:
            candidate = Path(value)
            if candidate.is_absolute():
                path = candidate
        if path and path.is_file():
            resolved = path.resolve()
            if resolved not in seen:
                seen.add(resolved)
                files.append(resolved)
    return files


def _write_xiaohongshu_package(
    package_dir: Path,
    record: dict[str, Any],
    source_artifacts: dict[str, Any],
) -> Path:
    xhs = record["xiaohongshu"]
    public_base = os.getenv("CREATOR_STUDIO_PUBLIC_BASE_URL", "").strip().rstrip("/")
    if public_base and not public_base.startswith("https://"):
        qr_url = os.getenv("WECHAT_QR_IMAGE_URL", "").strip()
        parsed_qr = urllib.parse.urlsplit(qr_url)
        if parsed_qr.scheme == "https" and parsed_qr.netloc:
            public_base = f"{parsed_qr.scheme}://{parsed_qr.netloc}"
    task_id = str(record.get("id") or "")
    platform_saved_url = (
        f"{public_base}/api/distribution/tasks/{task_id}/xiaohongshu/status"
        if public_base and task_id
        else ""
    )
    assistant = r'''import json
import urllib.request
from pathlib import Path

from playwright.sync_api import sync_playwright


ROOT = Path(__file__).resolve().parent
TITLE = (ROOT / "xiaohongshu_title.txt").read_text(encoding="utf-8").strip()
NOTE = (ROOT / "xiaohongshu_note.txt").read_text(encoding="utf-8").strip()
BODY = NOTE.removeprefix(TITLE).strip()
CARDS = sorted((ROOT / "xiaohongshu_cards").glob("*.png"))
MEDIA = sorted((ROOT / "media").glob("*")) if (ROOT / "media").exists() else []
UPLOADS = CARDS or [path for path in MEDIA if path.is_file()]
PLATFORM_SAVED_URL = __PLATFORM_SAVED_URL__


def first_visible(page, selectors):
    for selector in selectors:
        matches = page.locator(selector)
        for index in range(matches.count()):
            item = matches.nth(index)
            if item.is_visible():
                return item
    return None


def first_visible_button(page, labels):
    for label in labels:
        matches = page.get_by_text(label, exact=True)
        for index in range(matches.count()):
            item = matches.nth(index)
            if item.is_visible():
                return item
    return None


with sync_playwright() as playwright:
    context = playwright.chromium.launch_persistent_context(
        str(ROOT / ".xiaohongshu_browser"),
        headless=False,
        channel="chrome",
    )
    page = context.pages[0] if context.pages else context.new_page()
    page.goto("https://creator.xiaohongshu.com/publish/publish")
    input("请在打开的浏览器里完成登录并进入“发布图文”页面，然后回到这里按 Enter：")

    image_tab = first_visible_button(page, ["上传图文"])
    if image_tab:
        image_tab.click()
        page.wait_for_timeout(1200)

    upload = first_visible(page, ["input[type=file]"])
    if upload and UPLOADS:
        upload.set_input_files([str(path) for path in UPLOADS])
        page.wait_for_timeout(2500)

    title = first_visible(
        page,
        ["input[placeholder*='标题']", "textarea[placeholder*='标题']"],
    )
    if title:
        title.fill(TITLE)

    body = first_visible(
        page,
        [
            "textarea[placeholder*='正文']",
            "textarea[placeholder*='描述']",
            "[contenteditable=true]",
        ],
    )
    if body:
        body.fill(BODY)

    print("图片、标题和正文已尽量自动填好。请先在浏览器里审核。")
    action = input("输入 SAVE 后按 Enter，助手会尝试保存到小红书草稿箱；直接按 Enter 则只保留填写页面：").strip().upper()
    if action == "SAVE":
        save_button = first_visible_button(
            page,
            ["暂存离开", "保存草稿", "存草稿", "暂存"],
        )
        if save_button:
            save_button.click()
            page.wait_for_timeout(2000)
            print("已点击小红书的草稿保存按钮，请在页面确认草稿是否出现。")
            if PLATFORM_SAVED_URL:
                payload = json.dumps(
                    {
                        "status": "platform_draft_saved",
                        "notes": "本地自动填充助手已点击小红书平台草稿保存按钮。",
                    }
                ).encode("utf-8")
                request = urllib.request.Request(
                    PLATFORM_SAVED_URL,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                try:
                    urllib.request.urlopen(request, timeout=15).read()
                    print("系统状态已同步为“小红书平台草稿已保存”。")
                except Exception as exc:
                    print(f"平台草稿已点击保存，但系统状态回写失败：{exc}")
        else:
            print("没有识别到草稿按钮。小红书页面可能已改版，请手动点击“暂存离开”或“保存草稿”。")
    input("检查完成后按 Enter 关闭助手：")
    context.close()
'''.replace("__PLATFORM_SAVED_URL__", repr(platform_saved_url))
    checklist = "\n".join(
        [
            "小红书半自动发布清单",
            "",
            "1. 下载并解压这个素材包。",
            "2. 首次使用：pip install playwright，然后执行 playwright install chromium。",
            "3. 在解压目录执行：python xiaohongshu_fill_assistant.py。",
            "4. 按提示完成小红书登录，助手会上传图片并填写标题、正文。",
            "5. 检查封面、话题和错别字；输入 SAVE 可尝试保存到运行助手的浏览器本地草稿。",
            "6. 正式发布仍由你本人确认；发布后复制链接，回填系统并标记“已发布”。",
            "",
            "不想运行助手时，也可以点击系统里的“开始半自动发布”，手动上传并粘贴。",
        ]
    )
    (package_dir / "xiaohongshu_title.txt").write_text(
        str(xhs.get("title") or ""), encoding="utf-8"
    )
    (package_dir / "xiaohongshu_checklist.txt").write_text(checklist, encoding="utf-8")
    cover_text = str(xhs.get("cover_text") or "").strip()
    if cover_text:
        (package_dir / "xiaohongshu_cover_text.txt").write_text(
            cover_text, encoding="utf-8"
        )
    (package_dir / "xiaohongshu_fill_assistant.py").write_text(
        assistant, encoding="utf-8"
    )
    launcher = "\r\n".join(
        [
            "@echo off",
            "chcp 65001 >nul",
            "cd /d %~dp0",
            "python -m pip install playwright",
            "python -m playwright install chromium",
            "python xiaohongshu_fill_assistant.py",
            "pause",
        ]
    )
    (package_dir / "一键保存到小红书草稿箱.bat").write_text(
        launcher, encoding="utf-8-sig"
    )

    archive = package_dir / "xiaohongshu_publish_package.zip"
    used_names: set[str] = set()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
        for filename in (
            "xiaohongshu_title.txt",
            "xiaohongshu_note.txt",
            "xiaohongshu_checklist.txt",
            "xiaohongshu_cover_text.txt",
            "xiaohongshu_fill_assistant.py",
            "一键保存到小红书草稿箱.bat",
        ):
            file_path = package_dir / filename
            if file_path.exists():
                bundle.write(file_path, filename)
        for index, media_path in enumerate(_source_media_files(source_artifacts), start=1):
            name = media_path.name
            if name in used_names:
                name = f"{index}_{name}"
            used_names.add(name)
            bundle.write(media_path, f"media/{name}")
        cards_dir = package_dir / "xiaohongshu_cards"
        if cards_dir.exists():
            for card_path in sorted(cards_dir.glob("*.png")):
                bundle.write(card_path, f"xiaohongshu_cards/{card_path.name}")
    return archive


def refresh_distribution_manifest(record: dict[str, Any]) -> dict[str, Any]:
    package_dir = OUTPUTS_DIR / "distribution" / str(record.get("id") or "")
    package_dir.mkdir(parents=True, exist_ok=True)
    archive = _write_xiaohongshu_package(
        package_dir,
        record,
        record.get("source_artifacts")
        if isinstance(record.get("source_artifacts"), dict)
        else {},
    )
    record["xiaohongshu"]["package_url"] = to_media_url(archive)
    manifest_file = package_dir / "manifest.json"
    record["manifest_url"] = to_media_url(manifest_file)
    manifest_file.write_text(
        json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return record


def prepare_distribution_package(
    job: dict[str, Any],
    *,
    title: str = "",
    summary: str = "",
    author: str = "",
    hashtags: list[str] | None = None,
    wechat_skill_id: str = "",
    xiaohongshu_skill_id: str = "",
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
    source_type = str(job.get("source_type") or request_payload.get("source_type") or "generated_job")
    effective_wechat_skill_id = wechat_skill_id
    effective_xhs_skill_id = xiaohongshu_skill_id
    if source_type == "ai_trends":
        effective_wechat_skill_id = effective_wechat_skill_id or "wechat_operator_flywheel_v1"
        effective_xhs_skill_id = effective_xhs_skill_id or "xiaohongshu_operator_flywheel_v1"
    if effective_wechat_skill_id or effective_xhs_skill_id:
        channel_drafts = build_channel_drafts_with_ai(
            source_text=script,
            title=final_title,
            summary=final_summary,
            source_type=source_type,
            hashtags=final_tags,
            wechat_skill_id=effective_wechat_skill_id or "wechat_article_v1",
            xiaohongshu_skill_id=effective_xhs_skill_id or "xiaohongshu_note_v1",
        )
    else:
        channel_drafts = build_channel_drafts(
            source_text=script,
            title=final_title,
            summary=final_summary,
            source_type=source_type,
            hashtags=final_tags,
        )
    wechat_draft = channel_drafts["wechat"]
    xhs_draft = channel_drafts["xiaohongshu"]
    final_title = str(wechat_draft["title"])
    final_summary = str(wechat_draft["summary"])
    xhs_title = str(xhs_draft["title"])
    xhs_body = str(xhs_draft["body"])

    task_id = make_id("distribution")
    package_dir = OUTPUTS_DIR / "distribution" / task_id
    package_dir.mkdir(parents=True, exist_ok=True)
    wechat_file = package_dir / "wechat_article.html"
    xhs_file = package_dir / "xiaohongshu_note.txt"
    wechat_file.write_text(
        _wechat_channel_html(str(wechat_draft["markdown"])), encoding="utf-8"
    )
    xhs_file.write_text(f"{xhs_title}\n\n{xhs_body}", encoding="utf-8")
    card_files: list[Path] = []
    card_error = ""
    try:
        card_files = render_xiaohongshu_cards(
            package_dir, list(xhs_draft.get("card_pages") or [])
        )
    except Exception as exc:
        card_error = str(exc)[:300]

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
        "channel_skills": {
            "wechat": wechat_draft["skill_id"],
            "xiaohongshu": xhs_draft["skill_id"],
            "xiaohongshu_images": xhs_draft["image_skill_id"],
        },
        "wechat": {
            "status": "ready",
            "skill_id": wechat_draft["skill_id"],
            "markdown": wechat_draft["markdown"],
            "article_html_url": to_media_url(wechat_file),
            "draft_media_id": "",
            "publish_id": "",
        },
        "xiaohongshu": {
            "status": "ready_for_manual_confirm",
            "skill_id": xhs_draft["skill_id"],
            "image_skill_id": xhs_draft["image_skill_id"],
            "creator_url": XIAOHONGSHU_CREATOR_URL,
            "title": xhs_title,
            "body": xhs_body,
            "cover_text": xhs_draft["cover_text"],
            "card_urls": [to_media_url(path) for path in card_files],
            "card_generation_error": card_error,
            "note_url": to_media_url(xhs_file),
            "published_note_url": "",
            "started_at": "",
            "published_at": "",
            "notes": "",
            "manual_confirm_required": True,
        },
    }
    return refresh_distribution_manifest(record)


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
        "source_type": "wechat_material",
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
    return refresh_distribution_manifest(record)


def prepare_trend_distribution_package(
    trend: dict[str, Any],
    *,
    script: str = "",
    question: str = "",
    title: str = "",
    author: str = "",
    hashtags: list[str] | None = None,
    wechat_skill_id: str = "",
    xiaohongshu_skill_id: str = "",
) -> dict[str, Any]:
    items = list(trend.get("items") or [])
    angles = [str(item).strip() for item in trend.get("angles") or [] if str(item).strip()]
    content = str(script or "").strip()
    if not content:
        sections = [str(trend.get("summary") or "").strip()]
        for item in items[:6]:
            item_title = str(item.get("title") or "").strip()
            item_summary = str(item.get("summary") or "").strip()
            if item_title:
                sections.append(f"{item_title}：{item_summary}" if item_summary else item_title)
        if angles:
            sections.append("普通人可以关注：" + "；".join(angles[:4]))
        content = "\n\n".join(item for item in sections if item)
    if not content:
        raise ValueError("这份实时资讯没有可分发的内容。")

    source_title = _clean_ai_trend_title(
        str(title or question or trend.get("title") or trend.get("query") or "").strip(),
        trend,
    )
    synthetic_job = {
        "id": f"trend:{trend.get('id', '')}",
        "status": "completed",
        "script_text": content,
        "request": {
            "topic": source_title or "今天值得关注的 AI 实时资讯",
            "title": title,
            "content_mode": "ai_growth",
            "keywords": list(hashtags or ["AI工具", "效率提升", "职场成长"]),
        },
        "artifacts": {},
        "source_type": "ai_trends",
    }
    record = prepare_distribution_package(
        synthetic_job,
        title=source_title,
        summary=str(trend.get("summary") or content),
        author=author,
        hashtags=hashtags,
        wechat_skill_id=wechat_skill_id,
        xiaohongshu_skill_id=xiaohongshu_skill_id,
    )
    record["job_id"] = ""
    record["trend_id"] = str(trend.get("id") or "")
    record["source_type"] = "ai_trends"
    record["source_question"] = question
    xhs = dict(record.get("xiaohongshu") or {})
    recommendation_reason = (
        "这条内容有明确的新信息、普通人影响和可执行动作，适合做成小红书知识型笔记。"
        if script
        else "这份日报包含多条新资讯，建议先加入个人经历或明确观点，再发布成小红书笔记。"
    )
    xhs.update(
        {
            "recommended": True,
            "recommendation_reason": recommendation_reason,
            "cover_text": _compact(source_title or "AI 正在改变普通人的工作方式", 14),
            "publish_steps": [
                "先检查标题是否直接说清读者能得到什么。",
                "封面使用短句，不堆叠资讯标题。",
                "正文前两段加入你的真实判断或使用经历。",
                "上传配图或视频后，人工确认再发布。",
            ],
        }
    )
    record["xiaohongshu"] = xhs
    return refresh_distribution_manifest(record)


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
    if not media_id:
        raise RuntimeError(
            f"微信接口没有返回草稿 media_id，不能确认发送成功。原始返回：{draft_result}"
        )
    verify_result = _post_wechat_json("draft/get", token, {"media_id": media_id})
    news_items = verify_result.get("news_item")
    if not isinstance(news_items, list) or not news_items:
        raise RuntimeError(
            f"微信返回了草稿 ID，但随后读取不到草稿内容。草稿 ID：{media_id}"
        )
    verified_title = str(news_items[0].get("title") or "").strip()
    result = {
        "status": "draft_created",
        "draft_media_id": media_id,
        "submitted_at": now_iso(),
        "verified": True,
        "verified_title": verified_title,
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
