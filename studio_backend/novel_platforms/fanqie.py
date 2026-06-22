"""
番茄小说（FanQie Novel）自动化发布模块。

登录方式：微信扫码（WeChat QR）
发布流程：创作中心 → 选作品 → 新建章节 → 填内容 → 保存草稿
"""
from __future__ import annotations

import threading
import time
import json
import re
from pathlib import Path
from typing import Any

from ..storage import STUDIO_DIR, to_media_url

# ── 常量 ──────────────────────────────────────────────────────────────
AUTHOR_CENTER_URL = "https://fanqienovel.com/author"
PROFILE_DIR = STUDIO_DIR / "fanqie_browser_profile"
SCREENSHOT_DIR = STUDIO_DIR / "fanqie_session"
QR_SCREENSHOT = SCREENSHOT_DIR / "qr.png"
SESSION_SCREENSHOT = SCREENSHOT_DIR / "session.png"
RESULT_SCREENSHOT = SCREENSHOT_DIR / "result.png"

_BROWSER_LOCK = threading.Lock()
_STATE_LOCK = threading.Lock()
_SESSION_READY = threading.Event()
_LOGIN_THREAD: threading.Thread | None = None

_STATE: dict[str, Any] = {
    "status": "not_started",   # not_started | starting | qr_ready | logged_in | expired | failed
    "logged_in": False,
    "screenshot_url": "",
    "qr_url": "",
    "message": "尚未启动番茄小说登录。",
    "username": "",
}


# ── 状态工具 ──────────────────────────────────────────────────────────

def _set_state(**patch: Any) -> None:
    with _STATE_LOCK:
        _STATE.update(patch)


def get_session_state() -> dict[str, Any]:
    with _STATE_LOCK:
        return dict(_STATE)


def _versioned_url(path: Path) -> str:
    return f"{to_media_url(path)}?v={int(time.time() * 1000)}"


# ── Playwright 工具 ───────────────────────────────────────────────────

def _open_context(playwright: Any) -> Any:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 900},
        args=["--no-sandbox", "--disable-dev-shm-usage"],
        locale="zh-CN",
    )


def _first_visible(page: Any, selectors: list[str]) -> Any | None:
    for sel in selectors:
        try:
            matches = page.locator(sel)
            for i in range(min(matches.count(), 10)):
                el = matches.nth(i)
                if el.is_visible():
                    return el
        except Exception:
            continue
    return None


def _first_visible_text(page: Any, labels: list[str]) -> Any | None:
    for label in labels:
        try:
            matches = page.get_by_text(label, exact=True)
            for i in range(min(matches.count(), 10)):
                el = matches.nth(i)
                if el.is_visible():
                    return el
        except Exception:
            continue
    return None


def _screenshot(page: Any, path: Path) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(path))
    return _versioned_url(path)


def _is_logged_in(page: Any) -> bool:
    url = str(page.url or "")
    # 未登录时通常跳回 /login 或显示微信扫码
    if "/login" in url:
        return False
    if _first_visible_text(page, ["微信扫码登录", "扫码登录", "手机号登录"]):
        return False
    # 已登录标志：有"我的作品"等创作中心元素
    if _first_visible_text(page, ["我的作品", "作品管理", "创作中心", "新建作品"]):
        return True
    if _first_visible(page, ["[class*='work-list']", "[class*='author-center']", "[class*='my-work']"]):
        return True
    return False


def _get_username(page: Any) -> str:
    try:
        el = _first_visible(page, [
            "[class*='user-name']", "[class*='nickname']",
            "[class*='avatar-name']", "header [class*='name']",
        ])
        if el:
            return str(el.inner_text()).strip()[:30]
    except Exception:
        pass
    return ""


def _find_qr_element(page: Any) -> Any | None:
    selectors = [
        "[class*='qrcode'] canvas",
        "[class*='qr-code'] canvas",
        "[class*='qrcode'] img",
        "[class*='login-qr'] img",
        "img[alt*='二维码']",
        "canvas",
    ]
    for sel in selectors:
        try:
            matches = page.locator(sel)
            for i in range(matches.count()):
                el = matches.nth(i)
                if not el.is_visible():
                    continue
                box = el.bounding_box()
                if box and 80 <= box["width"] <= 500 and 80 <= box["height"] <= 500:
                    return el
        except Exception:
            continue
    return None


def _capture_qr(page: Any) -> str:
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
    qr = _find_qr_element(page)
    if qr:
        qr.screenshot(path=str(QR_SCREENSHOT))
        return _versioned_url(QR_SCREENSHOT)
    # 回退：截整页
    page.screenshot(path=str(QR_SCREENSHOT))
    return _versioned_url(QR_SCREENSHOT)


# ── 登录 session worker ───────────────────────────────────────────────

def _login_worker() -> None:
    from playwright.sync_api import sync_playwright

    try:
        with _BROWSER_LOCK:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            with sync_playwright() as pw:
                context = _open_context(pw)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(AUTHOR_CENTER_URL, wait_until="domcontentloaded", timeout=60_000)
                    page.wait_for_timeout(3000)

                    if _is_logged_in(page):
                        username = _get_username(page)
                        _set_state(
                            status="logged_in",
                            logged_in=True,
                            screenshot_url=_screenshot(page, SESSION_SCREENSHOT),
                            message=f"已登录番茄小说，账号：{username or '未知'}",
                            username=username,
                        )
                        _SESSION_READY.set()
                        return

                    # 未登录：展示微信扫码
                    qr_url = _capture_qr(page)
                    _set_state(
                        status="qr_ready",
                        logged_in=False,
                        qr_url=qr_url,
                        screenshot_url=qr_url,
                        message="请用微信扫描二维码登录番茄小说创作中心。",
                    )
                    _SESSION_READY.set()

                    # 轮询等待扫码
                    deadline = time.time() + 300  # 5 分钟超时
                    while time.time() < deadline:
                        page.wait_for_timeout(2000)
                        if _is_logged_in(page):
                            username = _get_username(page)
                            _set_state(
                                status="logged_in",
                                logged_in=True,
                                screenshot_url=_screenshot(page, SESSION_SCREENSHOT),
                                message=f"番茄小说登录成功，账号：{username or '未知'}",
                                username=username,
                            )
                            return
                        # 刷新 QR 截图（微信 QR 有时会自动刷新）
                        new_qr = _capture_qr(page)
                        _set_state(qr_url=new_qr, screenshot_url=new_qr)

                    _set_state(
                        status="expired",
                        logged_in=False,
                        message="扫码超时（5 分钟），请重新发起登录。",
                    )
                finally:
                    context.close()
    except Exception as exc:
        _set_state(
            status="failed",
            logged_in=False,
            message=f"番茄小说浏览器启动失败：{str(exc)[:300]}",
        )
        _SESSION_READY.set()


def capture_login_session() -> dict[str, Any]:
    """启动或复用登录 session，返回当前状态。"""
    global _LOGIN_THREAD
    with _STATE_LOCK:
        running = _LOGIN_THREAD is not None and _LOGIN_THREAD.is_alive()
    if not running:
        _SESSION_READY.clear()
        _set_state(
            status="starting",
            logged_in=False,
            message="正在启动番茄小说登录页面……",
        )
        _LOGIN_THREAD = threading.Thread(
            target=_login_worker,
            name="fanqie-login",
            daemon=True,
        )
        _LOGIN_THREAD.start()
        _SESSION_READY.wait(timeout=20)
    return get_session_state()


def refresh_login_qr() -> dict[str, Any]:
    """重新发起登录（上一次超时或失败后调用）。"""
    global _LOGIN_THREAD
    with _STATE_LOCK:
        running = _LOGIN_THREAD is not None and _LOGIN_THREAD.is_alive()
    if running:
        # 当前 session 仍在运行，只返回最新状态
        return get_session_state()
    return capture_login_session()


# ── 作品列表 ──────────────────────────────────────────────────────────

def list_works() -> list[dict[str, Any]]:
    """
    获取创作中心的作品列表。
    返回 [{"id": ..., "name": ..., "status": ...}, ...]
    """
    from playwright.sync_api import sync_playwright

    with _BROWSER_LOCK:
        with sync_playwright() as pw:
            context = _open_context(pw)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(AUTHOR_CENTER_URL, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(3000)

                if not _is_logged_in(page):
                    raise RuntimeError("番茄小说未登录，请先扫码登录。")

                works: list[dict[str, Any]] = []

                # 等待作品列表渲染
                page.wait_for_timeout(2000)

                # 尝试从作品卡片提取信息
                title_selectors = [
                    "[class*='work-title']",
                    "[class*='book-title']",
                    "[class*='novel-title']",
                    "[class*='work-name']",
                    "[class*='item-title']",
                ]
                for sel in title_selectors:
                    items = page.locator(sel)
                    count = items.count()
                    if count > 0:
                        for i in range(count):
                            el = items.nth(i)
                            name = str(el.inner_text()).strip()
                            if name:
                                works.append({
                                    "id": f"fanqie_work_{i}",
                                    "name": name,
                                    "index": i,
                                })
                        break

                if not works:
                    # 截图帮助调试
                    _screenshot(page, RESULT_SCREENSHOT)

                return works
            finally:
                context.close()


# ── 推章节草稿 ────────────────────────────────────────────────────────

def push_chapter_draft(
    *,
    work_name: str,
    chapter_number: int,
    chapter_title: str,
    content: str,
) -> dict[str, Any]:
    """
    将章节内容推送到番茄小说对应作品的草稿箱。

    Args:
        work_name:      番茄小说上的小说名称（用于匹配作品）
        chapter_number: 章节序号（仅用于日志/标题）
        chapter_title:  章节标题
        content:        章节正文（Markdown 纯文本）
    """
    from playwright.sync_api import sync_playwright

    # 把 Markdown 转成纯文本（去掉 # ## 等标记符）
    plain = _md_to_plain(content)

    with _BROWSER_LOCK:
        with sync_playwright() as pw:
            context = _open_context(pw)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(AUTHOR_CENTER_URL, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(3000)

                if not _is_logged_in(page):
                    raise RuntimeError("番茄小说未登录，请先扫码登录。")

                # 1. 找到目标作品并进入章节管理
                _navigate_to_work(page, work_name)

                # 2. 新建章节
                _click_new_chapter(page)

                # 3. 填写标题
                _fill_chapter_title(page, chapter_title)

                # 4. 填写正文
                _fill_chapter_content(page, plain)

                # 5. 保存草稿
                _save_draft(page)

                screenshot_url = _screenshot(page, RESULT_SCREENSHOT)
                return {
                    "ok": True,
                    "message": f"第 {chapter_number} 章「{chapter_title}」已保存到番茄小说草稿箱。",
                    "screenshot_url": screenshot_url,
                }
            except Exception as exc:
                try:
                    screenshot_url = _screenshot(page, RESULT_SCREENSHOT)
                except Exception:
                    screenshot_url = ""
                raise RuntimeError(f"番茄小说推稿失败：{str(exc)}") from exc
            finally:
                context.close()


# ── 内部导航步骤 ──────────────────────────────────────────────────────

def _navigate_to_work(page: Any, work_name: str) -> None:
    """在创作中心找到指定作品，点击进入章节管理。"""
    page.wait_for_timeout(2000)

    # 尝试按文本找到作品
    work_el = page.get_by_text(work_name, exact=False)
    if work_el.count() > 0:
        work_el.first.click()
        page.wait_for_timeout(2000)
        return

    # 尝试找"章节管理"按钮（某些布局下作品名旁边有直接按钮）
    chapter_mgr = _first_visible_text(page, ["章节管理", "管理章节"])
    if chapter_mgr:
        chapter_mgr.click()
        page.wait_for_timeout(2000)
        return

    _screenshot(page, RESULT_SCREENSHOT)
    raise RuntimeError(
        f"未找到作品「{work_name}」，请确认番茄小说创作中心中存在此作品，"
        f"或检查 screenshot_url 查看当前页面。"
    )


def _click_new_chapter(page: Any) -> None:
    """点击「新建章节」按钮。"""
    btn = _first_visible_text(page, ["新建章节", "添加章节", "+ 新建", "新建正文"])
    if not btn:
        btn = _first_visible(page, [
            "button[class*='add']",
            "button[class*='create']",
            "button[class*='new']",
            "[class*='add-chapter']",
        ])
    if not btn:
        _screenshot(page, RESULT_SCREENSHOT)
        raise RuntimeError("未找到「新建章节」按钮，页面结构可能已改版。")
    btn.click()
    page.wait_for_timeout(2500)


def _fill_chapter_title(page: Any, title: str) -> None:
    title_input = _first_visible(page, [
        "input[placeholder*='章节名']",
        "input[placeholder*='标题']",
        "input[placeholder*='章节标题']",
        "input[class*='chapter-title']",
        "input[class*='title']",
    ])
    if not title_input:
        _screenshot(page, RESULT_SCREENSHOT)
        raise RuntimeError("未找到章节标题输入框。")
    title_input.triple_click()
    title_input.fill(title)


def _fill_chapter_content(page: Any, text: str) -> None:
    """向富文本编辑器填入纯文本正文。"""
    editor = _first_visible(page, [
        "[contenteditable='true']",
        "textarea[placeholder*='正文']",
        "textarea[placeholder*='内容']",
        "[class*='editor'] [contenteditable]",
        "[class*='content-editor']",
        ".ql-editor",
        "[data-slate-editor]",
    ])
    if not editor:
        _screenshot(page, RESULT_SCREENSHOT)
        raise RuntimeError("未找到章节正文编辑器。")

    editor.click()
    page.wait_for_timeout(500)

    # contenteditable 用 JS 注入更可靠
    tag = editor.evaluate("el => el.tagName").lower()
    if tag != "textarea":
        page.evaluate(
            """([el, content]) => {
                el.focus();
                document.execCommand('selectAll');
                document.execCommand('insertText', false, content);
            }""",
            [editor.element_handle(), text],
        )
    else:
        editor.fill(text)

    page.wait_for_timeout(1000)


def _save_draft(page: Any) -> None:
    btn = _first_visible_text(page, [
        "保存草稿", "存草稿", "暂存", "保存", "存储",
    ])
    if not btn:
        btn = _first_visible(page, [
            "button[class*='save']",
            "button[class*='draft']",
        ])
    if not btn:
        _screenshot(page, RESULT_SCREENSHOT)
        raise RuntimeError("未找到「保存草稿」按钮。")
    btn.click()
    page.wait_for_timeout(2000)


# ── 工具函数 ──────────────────────────────────────────────────────────

def _md_to_plain(md: str) -> str:
    """把 Markdown 转成适合小说平台的纯文本（保留段落换行，去掉 # * ` 等）。"""
    lines = []
    for line in md.splitlines():
        # 去掉 ATX 标题符号
        line = re.sub(r"^#{1,6}\s*", "", line)
        # 去掉粗体/斜体
        line = re.sub(r"\*{1,3}(.*?)\*{1,3}", r"\1", line)
        line = re.sub(r"_{1,3}(.*?)_{1,3}", r"\1", line)
        # 去掉代码块标记
        line = re.sub(r"`{1,3}[^`]*`{1,3}", "", line)
        lines.append(line)
    return "\n".join(lines).strip()
