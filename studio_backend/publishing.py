from __future__ import annotations

import html
import ipaddress
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
        tool_name = re.sub(r"(安装|install|教程|说明|使用|怎么用|指南)+", "", title, flags=re.IGNORECASE).strip(" ：:-")
        tool_name = tool_name or title
        return _compact(f"{tool_name} 是什么？怎么安装和上手", 36)
    if len(title) <= 18:
        return _compact(f"{title}：普通人怎么用", 32)
    return _compact(title, 48)


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


def _is_tool_research_topic(title: str, job: dict[str, Any]) -> bool:
    request_payload = job.get("request") if isinstance(job.get("request"), dict) else {}
    corpus = " ".join(
        [
            str(title or ""),
            str(request_payload.get("topic") or ""),
            str(request_payload.get("title") or ""),
            str(request_payload.get("content_mode") or ""),
            " ".join(str(item) for item in request_payload.get("keywords") or []),
        ]
    ).lower()
    has_strong_marker = any(marker in corpus for marker in _TOOL_RESEARCH_STRONG_MARKERS)
    has_specific_tool = any(marker in corpus for marker in _TOOL_RESEARCH_SPECIFIC_TOOLS)
    has_soft_marker = any(marker in corpus for marker in _TOOL_RESEARCH_SOFT_MARKERS)
    return has_strong_marker or (has_specific_tool and has_soft_marker)


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
    lines = [raw.strip() for raw in str(markdown or "").splitlines()]
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            blocks.append(
                f'<h1 style="font-size:24px;line-height:1.45;color:#132431;">{html.escape(line[2:])}</h1>'
            )
            index += 1
        elif line.startswith("## "):
            blocks.append(
                f'<h2 style="font-size:19px;line-height:1.6;color:#0b6670;margin-top:28px;">{html.escape(line[3:])}</h2>'
            )
            index += 1
        elif _is_markdown_table_row(line):
            separator_index = index + 1
            while separator_index < len(lines) and not lines[separator_index]:
                separator_index += 1
            if separator_index < len(lines) and _is_markdown_table_separator(lines[separator_index]):
                table_rows = [line]
                row_index = separator_index + 1
                while row_index < len(lines):
                    if not lines[row_index]:
                        lookahead = row_index + 1
                        while lookahead < len(lines) and not lines[lookahead]:
                            lookahead += 1
                        if lookahead < len(lines) and _is_markdown_table_row(lines[lookahead]):
                            row_index = lookahead
                            continue
                        break
                    if not _is_markdown_table_row(lines[row_index]):
                        break
                    table_rows.append(lines[row_index])
                    row_index += 1
                blocks.append(_wechat_table_html(table_rows))
                index = row_index
            else:
                blocks.append(
                    f'<p style="font-size:16px;line-height:1.9;color:#243241;margin:0 0 16px;">{html.escape(line)}</p>'
                )
                index += 1
        else:
            blocks.append(
                f'<p style="font-size:16px;line-height:1.9;color:#243241;margin:0 0 16px;">{html.escape(line)}</p>'
            )
            index += 1
    section = (
        '<section style="max-width:100%;font-family:-apple-system,BlinkMacSystemFont,'
        "'Segoe UI','Microsoft YaHei',sans-serif;\">"
        + "".join(blocks)
        + "</section>"
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "</head><body>"
        + section
        + "</body></html>"
    )


def _split_markdown_table_row(line: str) -> list[str]:
    text = str(line or "").strip()
    if text.startswith("|"):
        text = text[1:]
    if text.endswith("|"):
        text = text[:-1]
    return [cell.strip() for cell in text.split("|")]


def _is_markdown_table_row(line: str) -> bool:
    return "|" in str(line or "") and len(_split_markdown_table_row(line)) >= 2


def _is_markdown_table_separator(line: str) -> bool:
    cells = _split_markdown_table_row(line)
    if len(cells) < 2:
        return False
    for cell in cells:
        compact = re.sub(r"\s+", "", cell)
        if not re.fullmatch(r":?-{3,}:?", compact or ""):
            return False
    return True


def _wechat_table_html(rows: list[str]) -> str:
    if not rows:
        return ""
    headers = _split_markdown_table_row(rows[0])
    body_rows = [_split_markdown_table_row(row) for row in rows[1:]]
    column_count = max([len(headers), *[len(row) for row in body_rows]] or [0])

    def pad(cells: list[str]) -> list[str]:
        return cells + [""] * max(0, column_count - len(cells))

    th_style = (
        "border:1px solid #d0d5dd;background:#f3fafb;padding:10px 12px;"
        "text-align:left;font-weight:700;color:#0b6670;"
    )
    td_style = "border:1px solid #d0d5dd;padding:10px 12px;color:#243241;vertical-align:top;"
    thead = "".join(f'<th style="{th_style}">{html.escape(cell)}</th>' for cell in pad(headers))
    tbody = "".join(
        "<tr>" + "".join(f'<td style="{td_style}">{html.escape(cell)}</td>' for cell in pad(row)) + "</tr>"
        for row in body_rows
    )
    return (
        '<table style="width:100%;border-collapse:collapse;margin:18px 0;'
        'font-size:15px;line-height:1.7;">'
        f"<thead><tr>{thead}</tr></thead><tbody>{tbody}</tbody></table>"
    )


def _tutorial_font(size: int, *, bold: bool = False) -> Any:
    try:
        from PIL import ImageFont

        candidates = [
            "C:/Windows/Fonts/msyhbd.ttc" if bold else "C:/Windows/Fonts/msyh.ttc",
            "C:/Windows/Fonts/simhei.ttf" if bold else "C:/Windows/Fonts/simsun.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.otf" if bold else "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.otf",
            "/usr/share/fonts/truetype/noto/NotoSansCJK-Bold.ttc" if bold else "/usr/share/fonts/truetype/noto/NotoSansCJK-Regular.ttc",
            "/usr/share/fonts/truetype/wqy/wqy-microhei.ttc",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
        for path in candidates:
            if path and Path(path).exists():
                return ImageFont.truetype(path, size)
    except Exception:  # noqa: BLE001
        from PIL import ImageFont

        return ImageFont.load_default()
    from PIL import ImageFont

    return ImageFont.load_default()


def _draw_wrapped(draw: Any, text: str, xy: tuple[int, int], font: Any, fill: str, max_width: int, line_height: int) -> int:
    x, y = xy
    line = ""
    for char in str(text or ""):
        if draw.textlength(line + char, font=font) <= max_width:
            line += char
            continue
        if line:
            draw.text((x, y), line, font=font, fill=fill)
            y += line_height
        line = char
    if line:
        draw.text((x, y), line, font=font, fill=fill)
        y += line_height
    return y


def _tutorial_screenshot_card(
    output_path: Path,
    *,
    title: str,
    subtitle: str,
    rows: list[tuple[str, str, str]],
    footer: str,
) -> None:
    from PIL import Image, ImageDraw

    width, height = 1800, 1080
    image = Image.new("RGB", (width, height), "#f3f7fb")
    draw = ImageDraw.Draw(image)
    title_font = _tutorial_font(54, bold=True)
    sub_font = _tutorial_font(32)
    label_font = _tutorial_font(28, bold=True)
    body_font = _tutorial_font(34)
    footer_font = _tutorial_font(28)
    draw.rounded_rectangle((56, 56, width - 56, height - 56), radius=30, fill="#ffffff", outline="#d0d5dd", width=3)
    draw.text((110, 104), title, font=title_font, fill="#101828")
    draw.text((112, 184), subtitle, font=sub_font, fill="#475467")
    y = 292
    for label, body, color in rows:
        draw.rounded_rectangle((112, y, width - 112, y + 164), radius=24, fill="#f9fafb", outline="#d0d5dd", width=2)
        draw.rounded_rectangle((148, y + 48, 320, y + 116), radius=16, fill=color)
        draw.text((184, y + 64), label, font=label_font, fill="#ffffff")
        _draw_wrapped(draw, body, (360, y + 38), body_font, "#101828", width - 500, 44)
        y += 192
    draw.text((112, height - 122), footer, font=footer_font, fill="#475467")
    image.save(output_path, quality=96)


def _official_url_from_markdown(markdown: str) -> str:
    match = re.search(r"官方入口[：:]\s*(https?://[^\s<]+)", markdown)
    if match:
        return match.group(1).rstrip("。,.，")
    match = re.search(r"官方链接[：:]\s*(https?://[^\s<]+)", markdown)
    if match:
        return match.group(1).rstrip("。,.，")
    match = re.search(r"https?://[^\s<]+", markdown)
    return match.group(0).rstrip("。,.，") if match else ""


def _tool_name_from_title(title: str) -> str:
    text = re.split(r"[\s：:，,、-]", str(title or "").strip(), maxsplit=1)[0]
    return _compact(text or "这个工具", 24)


def _is_public_https_url(url: str) -> bool:
    try:
        parsed = urllib.parse.urlsplit(str(url or "").strip())
    except Exception:  # noqa: BLE001
        return False
    if parsed.scheme != "https" or not parsed.hostname:
        return False
    host = parsed.hostname.lower()
    if host in {"localhost", "127.0.0.1", "::1"} or host.endswith(".local"):
        return False
    try:
        address = ipaddress.ip_address(host)
    except ValueError:
        return True
    return not (
        address.is_private
        or address.is_loopback
        or address.is_link_local
        or address.is_reserved
        or address.is_multicast
    )


def _capture_public_webpage_screenshot(url: str, output_path: Path) -> bool:
    if os.getenv("CREATOR_STUDIO_REAL_SCREENSHOTS", "1").strip().lower() in {"0", "false", "no"}:
        return False
    if not _is_public_https_url(url):
        return False
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            page = browser.new_page(
                viewport={"width": 1440, "height": 1100},
                device_scale_factor=1,
            )
            page.goto(url, wait_until="domcontentloaded", timeout=12000)
            page.wait_for_timeout(1800)
            page.screenshot(path=str(output_path), full_page=False)
            browser.close()
        return output_path.exists() and output_path.stat().st_size > 0
    except Exception:  # noqa: BLE001
        return False


def _tavily_search_images(query: str, *, max_results: int = 3) -> list[str]:
    """通过 Tavily 搜索图片，返回图片 URL 列表。"""
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        return []
    try:
        payload = {
            "api_key": api_key,
            "query": query,
            "search_depth": "basic",
            "max_results": max_results,
            "include_images": True,
        }
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(
            "https://api.tavily.com/search",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8", errors="replace"))
        images: list[str] = []
        for url in result.get("images") or []:
            url = str(url).strip()
            if url.startswith("https://") and _is_public_https_url(url):
                images.append(url)
        return images[:max_results]
    except Exception:  # noqa: BLE001
        return []


def _download_remote_image(url: str, output_path: Path) -> bool:
    """下载远程图片到本地，返回是否成功。"""
    if not url or not _is_public_https_url(url):
        return False
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "CreatorStudio/1.0"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            content_type = resp.headers.get("Content-Type", "")
            if "image" not in content_type and not url.lower().endswith((".jpg", ".jpeg", ".png", ".webp", ".gif")):
                return False
            body = resp.read()
        if len(body) < 1024:
            return False
        output_path.write_bytes(body)
        return True
    except Exception:  # noqa: BLE001
        return False


def _generate_tool_tutorial_screenshots(
    package_dir: Path,
    *,
    tool_name: str,
    official_url: str,
) -> list[dict[str, str]]:
    try:
        import PIL  # noqa: F401
    except Exception:  # noqa: BLE001
        return []

    image_dir = package_dir / "tutorial_screenshots"
    image_dir.mkdir(parents=True, exist_ok=True)
    tool_name = _compact(tool_name or "这个工具", 24)
    official_url = official_url or "先核验官方入口，不要用陌生下载站。"
    output: list[dict[str, str]] = []
    if _is_public_https_url(official_url):
        real_path = image_dir / "01.png"
        if _capture_public_webpage_screenshot(official_url, real_path):
            output.append(
                {
                    "src": "tutorial_screenshots/01.png",
                    "alt": f"{tool_name} 官方入口真实截图",
                    "caption": f"真实截图：先确认地址栏是官方入口 {official_url}，再找 Download / Get Started / Sign in。",
                    "kind": "real",
                }
            )
    # Tavily 图片搜索：为 slot 2-4 尝试获取真实截图
    _tavily_slot_queries = [
        f"{tool_name} official website download page screenshot",
        f"{tool_name} interface getting started tutorial screenshot",
        f"{tool_name} first prompt AI assistant screenshot",
        f"{tool_name} output result review screenshot",
    ]
    tavily_images: list[str | None] = [None, None, None, None]
    for slot_index, query in enumerate(_tavily_slot_queries):
        results = _tavily_search_images(query, max_results=3)
        for img_url in results:
            slot_path = image_dir / f"tavily_{slot_index + 1:02d}.png"
            if _download_remote_image(img_url, slot_path):
                tavily_images[slot_index] = str(slot_path)
                break

    specs = [
        (
            "示意图 1：确认官方入口",
            "给读者看：域名、下载入口、登录入口是不是官方页面。",
            [
                ("确认", f"地址栏应看到官方链接：{official_url}", "#177ddc"),
                ("按钮", "画面里要能看到 Download / Get Started / Sign in 这类入口。", "#10b8d8"),
                ("避坑", "如果打不开，先换浏览器或网络，不要马上搜索陌生安装包。", "#ff7a45"),
            ],
            "小白看这张图，要能确认：我从哪里进、下一步点哪里。",
        ),
        (
            "示意图 2：新建安全测试文件夹",
            "给读者看：第一次不要拿真实项目和私人资料测试。",
            [
                ("文件夹", f"桌面新建 {tool_name}-test，只放测试 README。", "#10b981"),
                ("内容", "README 写：我想解决什么、我卡在哪里、我希望输出什么。", "#10b8d8"),
                ("边界", "不要放客户资料、账号、合同、私人聊天记录。", "#ff7a45"),
            ],
            "小白看这张图，要能确认：测试范围很小，风险可控。",
        ),
        (
            "示意图 3：输入第一条提示词",
            "给读者看：先解释和列计划，不要上来就让工具乱改。",
            [
                ("提示", "我是新手，请先不要修改文件，请解释这里有什么。", "#177ddc"),
                ("要求", "列出下一步最小动作和风险，不确定的地方标注需要核验。", "#10b8d8"),
                ("成功", "输出里应有：看到的信息、建议步骤、风险提醒。", "#10b981"),
            ],
            "小白看这张图，要能确认：第一条提示词没有让工具直接动手。",
        ),
        (
            "示意图 4：检查结果和复盘",
            "给读者看：AI 输出以后，仍然要人工判断。",
            [
                ("检查", "有没有说明依据？有没有胡编官网、价格、功能边界？", "#ff7a45"),
                ("限制", "第一次只允许它改一个小文件，或生成一个小清单。", "#10b8d8"),
                ("复盘", "记下：省了哪一步、哪里不准、下次提示词怎么改。", "#10b981"),
            ],
            "小白看这张图，要能确认：这次测试能沉淀成下一次流程。",
        ),
    ]
    for index, (title, subtitle, rows, footer) in enumerate(specs, start=1):
        if output and index == 1:
            continue
        # 优先用 Tavily 搜到的真实截图
        tavily_path = tavily_images[index - 1]
        if tavily_path and Path(tavily_path).exists():
            output.append(
                {
                    "src": f"tutorial_screenshots/tavily_{index:02d}.png",
                    "alt": f"{tool_name} 真实截图 - {title}",
                    "caption": f"来自网络的真实截图参考：{footer}",
                    "kind": "real",
                }
            )
            continue
        # 降级到 PIL 示意图
        path = image_dir / f"{index:02d}.png"
        _tutorial_screenshot_card(path, title=title, subtitle=subtitle, rows=rows, footer=footer)
        output.append(
            {
                "src": f"tutorial_screenshots/{index:02d}.png",
                "alt": title,
                "caption": footer,
                "kind": "illustration",
            }
        )
    return output


def _inject_tool_tutorial_screenshots(article_html: str, images: list[dict[str, str]]) -> str:
    if not images or "tutorial_screenshots/" in article_html:
        return article_html
    has_real = any(item.get("kind") == "real" for item in images)
    intro = (
        "第一张是服务器自动截取的公开官网真实截图；后面的图是系统按步骤生成的操作示意图，用来提示你正式发布前还需要替换哪些真实操作画面。"
        if has_real
        else "下面这 4 张图是系统按步骤生成的操作示意图，不是真实网页截图。它们用于帮读者理解该截哪里；正式发布前，建议替换成你实际操作时截到的官网、下载页、工作台和首次输出页面。"
    )
    heading = "配图实操版：真实截图 + 操作示意图" if has_real else "配图实操版：操作示意图"
    figures = [
        f'<h2 style="font-size:19px;line-height:1.6;color:#0b6670;margin-top:28px;">{heading}</h2>',
        f'<p style="font-size:16px;line-height:1.9;color:#243241;margin:0 0 16px;">{html.escape(intro)}</p>',
    ]
    for item in images:
        figures.append(
            '<figure style="margin:22px 0;">'
            f'<img src="{html.escape(item["src"])}" alt="{html.escape(item["alt"])}" '
            'style="max-width:100%;border-radius:12px;border:1px solid #d0d5dd;">'
            f'<figcaption style="font-size:14px;color:#667085;line-height:1.7;margin-top:8px;">{html.escape(item["caption"])}</figcaption>'
            "</figure>"
        )
    insert = "".join(figures)
    existing_heading = re.search(
        r'(<h2[^>]*>\s*配图实操版[^<]*</h2>)',
        article_html,
        flags=re.IGNORECASE,
    )
    if existing_heading:
        return (
            article_html[: existing_heading.end()]
            + "".join(figures[1:])
            + article_html[existing_heading.end() :]
        )
    marker = '<h2 style="font-size:19px;line-height:1.6;color:#0b6670;margin-top:28px;">安装：小白照着这几步走</h2>'
    if marker in article_html:
        return article_html.replace(marker, insert + marker, 1)
    return article_html.replace("</body></html>", insert + "</body></html>")


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
        if _is_tool_research_topic(final_title, job):
            effective_wechat_skill_id = effective_wechat_skill_id or "wechat_tool_deep_review_v1"
            effective_xhs_skill_id = effective_xhs_skill_id or "xiaohongshu_tool_deep_review_v1"
        else:
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
    wechat_html = _wechat_channel_html(str(wechat_draft["markdown"]))
    if str(wechat_draft.get("skill_id") or "").endswith("tool_deep_review_v1"):
        tutorial_images = _generate_tool_tutorial_screenshots(
            package_dir,
            tool_name=_tool_name_from_title(str(wechat_draft.get("title") or final_title)),
            official_url=_official_url_from_markdown(str(wechat_draft.get("markdown") or "")),
        )
        wechat_html = _inject_tool_tutorial_screenshots(wechat_html, tutorial_images)
    wechat_file.write_text(wechat_html, encoding="utf-8")
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
    sections = [str(trend.get("summary") or "").strip()]
    for item in items[:6]:
        item_title = str(item.get("title") or "").strip()
        item_summary = str(item.get("summary") or "").strip()
        item_url = str(item.get("url") or "").strip()
        if item_title:
            detail = f"{item_title}：{item_summary}" if item_summary else item_title
            if item_url:
                detail += f"\n来源链接：{item_url}"
            sections.append(detail)
    if angles:
        sections.append("普通人可以关注：" + "；".join(angles[:4]))
    research_context = "\n\n".join(item for item in sections if item)
    if content and research_context:
        content = f"{content}\n\n【检索资料】\n{research_context}"
    elif not content:
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


def _guess_image_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if suffix == ".gif":
        return "image/gif"
    if suffix == ".webp":
        return "image/webp"
    return "image/png"


def _upload_wechat_article_image(
    *,
    token: str,
    image_path: Path,
) -> str:
    if not image_path.exists() or not image_path.is_file():
        raise RuntimeError(f"公众号正文图片不存在：{image_path.name}")
    body = image_path.read_bytes()
    if not body:
        raise RuntimeError(f"公众号正文图片为空：{image_path.name}")
    boundary = f"----CreatorStudio{make_id('articleimg').replace('_', '')}"
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "_", image_path.name or "article.png")
    content_type = _guess_image_content_type(image_path)
    multipart = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{safe_name}"\r\n'
        f"Content-Type: {content_type}\r\n\r\n"
    ).encode("utf-8") + body + f"\r\n--{boundary}--\r\n".encode("utf-8")
    query = urllib.parse.urlencode({"access_token": token})
    request = urllib.request.Request(
        f"{WECHAT_API_ROOT}/media/uploadimg?{query}",
        data=multipart,
        method="POST",
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(request, timeout=60) as response:
        result = json.loads(response.read().decode("utf-8", errors="replace"))
    if int(result.get("errcode") or 0):
        raise RuntimeError(
            f"微信正文图片上传失败：{result.get('errcode')} {result.get('errmsg') or '未知错误'}"
        )
    url = str(result.get("url") or "").strip()
    if not url:
        raise RuntimeError(f"微信正文图片上传未返回 url：{result}")
    return url


def _prepare_wechat_article_content(content: str, article_dir: Path, token: str) -> str:
    """Upload local article images to WeChat and replace src with hosted URLs."""
    uploaded: dict[str, str] = {}

    def replace_src(match: re.Match[str]) -> str:
        prefix, src, suffix = match.group(1), html.unescape(match.group(2)).strip(), match.group(3)
        if not src or re.match(r"^(https?:|data:|//)", src, flags=re.IGNORECASE):
            return match.group(0)
        if src.startswith("/"):
            local_path = (OUTPUTS_DIR / src.lstrip("/")).resolve()
        else:
            local_path = (article_dir / src).resolve()
        try:
            local_path.relative_to(article_dir.resolve())
        except ValueError:
            return match.group(0)
        cache_key = str(local_path)
        if cache_key not in uploaded:
            uploaded[cache_key] = _upload_wechat_article_image(
                token=token,
                image_path=local_path,
            )
        return f'{prefix}{html.escape(uploaded[cache_key], quote=True)}{suffix}'

    return re.sub(
        r'(<img\b[^>]*?\bsrc=["\'])([^"\']+)(["\'])',
        replace_src,
        content,
        flags=re.IGNORECASE,
    )


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
    article_content = _prepare_wechat_article_content(
        article_path.read_text(encoding="utf-8"),
        article_path.parent,
        token,
    )
    article = {
        "title": str(task.get("title") or ""),
        "author": str(task.get("author") or ""),
        "digest": str(task.get("summary") or ""),
        "content": article_content,
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
