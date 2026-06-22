"""
番茄小说（FanQie Novel）自动化发布模块。

登录方式：Cookie 导入（从浏览器导出后粘贴）
发布流程：HTTP API 直接调用（不使用 Playwright 浏览器，绕开 headless 检测）
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
AUTHOR_CENTER_URL = "https://fanqienovel.com/main/writer"
LOGIN_URL = "https://fanqienovel.com/login"
PROFILE_DIR = STUDIO_DIR / "fanqie_browser_profile"
SCREENSHOT_DIR = STUDIO_DIR / "fanqie_session"
COOKIE_FILE = STUDIO_DIR / "fanqie_cookies.json"
QR_SCREENSHOT = SCREENSHOT_DIR / "qr.png"
SESSION_SCREENSHOT = SCREENSHOT_DIR / "session.png"
RESULT_SCREENSHOT = SCREENSHOT_DIR / "result.png"

API_BASE = "https://fanqienovel.com/api/author"
APP_NAME = "muye_novel"

_HTTP_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://fanqienovel.com/",
    "Origin": "https://fanqienovel.com",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
    "sec-fetch-site": "same-origin",
    "sec-fetch-mode": "cors",
    "sec-fetch-dest": "empty",
}

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
        locale="zh-CN",
        user_agent=(
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        args=[
            "--no-sandbox",
            "--disable-dev-shm-usage",
            "--disable-blink-features=AutomationControlled",
        ],
        ignore_default_args=["--enable-automation"],
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
    # 未登录时跳回 /login（下载 APP 页）
    if url.rstrip("/").endswith("/login"):
        return False
    if _first_visible_text(page, ["微信扫码登录", "扫码登录", "手机号登录", "下载番茄小说APP"]):
        # 只有"下载 APP"按钮说明被踢到了读者登录页，没有作者面板
        if not _first_visible_text(page, ["工作台", "作品管理", "数据中心", "当前作品"]):
            return False
    # 已登录标志：番茄作家中心特有元素
    if _first_visible_text(page, ["工作台", "作品管理", "数据中心", "当前作品", "开书灵感", "作品运营"]):
        return True
    if "/main/writer" in url and "/login" not in url:
        return True
    return False


def _get_username(page: Any) -> str:
    try:
        el = _first_visible(page, [
            "[class*='user-name']", "[class*='nickname']",
            "[class*='avatar-name']", "header [class*='name']",
            "[class*='author-name']", "[class*='pen-name']",
        ])
        if el:
            return str(el.inner_text()).strip()[:30]
        # 从页面 title 提取（番茄作家中心 title 通常含笔名）
        title = str(page.title() or "")
        if "-" in title:
            return title.split("-")[0].strip()[:20]
    except Exception:
        pass
    return ""


def _page_debug_info(page: Any) -> dict:
    """收集页面调试信息（URL、所有可见文本按钮、输入框）。"""
    try:
        info = page.evaluate("""() => {
            const btns = Array.from(document.querySelectorAll('button, [role=button], a, span[class*=tab], div[class*=tab], li[class*=tab]'))
                .filter(el => el.offsetParent !== null)
                .map(el => ({ tag: el.tagName, cls: el.className?.substring(0,80), text: el.innerText?.trim()?.substring(0,40) }))
                .filter(x => x.text);
            const imgs = Array.from(document.querySelectorAll('img, canvas'))
                .filter(el => el.offsetParent !== null)
                .map(el => ({ tag: el.tagName, src: (el.src||'').substring(0,80), w: el.offsetWidth, h: el.offsetHeight, cls: el.className?.substring(0,60) }))
                .filter(x => x.w > 50 && x.h > 50);
            return { url: location.href, title: document.title, btns, imgs };
        }""")
        return info or {}
    except Exception as exc:
        return {"error": str(exc)}


def _click_wechat_login_tab(page: Any) -> bool:
    """尝试切换到微信扫码登录标签，返回是否成功。"""
    # 先用 JS 找所有包含"微信"/"wechat"/"扫码"文字的可点击元素
    try:
        result = page.evaluate("""() => {
            const keywords = ['微信', 'wechat', 'WeChat', '扫码', '二维码', 'scan', 'qr'];
            const els = Array.from(document.querySelectorAll('*'))
                .filter(el => {
                    if (!el.offsetParent) return false;
                    const t = (el.innerText || el.textContent || '').trim();
                    const cls = (el.className || '').toLowerCase();
                    const id = (el.id || '').toLowerCase();
                    return keywords.some(k => t.includes(k) || cls.includes(k.toLowerCase()) || id.includes(k.toLowerCase()));
                });
            if (els.length > 0) {
                els[0].click();
                return { clicked: true, text: els[0].innerText?.trim()?.substring(0,40), cls: els[0].className?.substring(0,60) };
            }
            return { clicked: false };
        }""")
        if result and result.get("clicked"):
            page.wait_for_timeout(2000)
            return True
    except Exception:
        pass

    # 备用：Playwright 文本选择器
    for label in ["微信登录", "微信扫码登录", "扫码登录", "微信扫码", "二维码登录"]:
        try:
            els = page.get_by_text(label, exact=False)
            for i in range(els.count()):
                el = els.nth(i)
                if el.is_visible():
                    el.click()
                    page.wait_for_timeout(2000)
                    return True
        except Exception:
            continue

    for sel in ["[class*='wechat']", "[class*='wx-login']", "[class*='scan']", "[class*='qr']"]:
        try:
            el = page.locator(sel).first
            if el.is_visible():
                el.click()
                page.wait_for_timeout(2000)
                return True
        except Exception:
            continue
    return False


def _find_qr_element(page: Any) -> Any | None:
    selectors = [
        "img[src*='qrcode']",
        "img[src*='qr_code']",
        "[class*='qrcode'] img",
        "[class*='qr-code'] img",
        "[class*='qrcode'] canvas",
        "[class*='scan-code'] img",
        "[class*='login-qr'] img",
        "img[alt*='二维码']",
        "img[alt*='扫码']",
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
                if box and 80 <= box["width"] <= 400 and 80 <= box["height"] <= 400:
                    return el
        except Exception:
            continue
    return None


def _capture_qr(page: Any) -> str:
    """截取登录页面，优先截 QR 元素或登录卡片，最终回退全页截图。"""
    SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 检查微信 QR iframe（wx.qq.com / open.weixin.qq.com）
    try:
        for frame in page.frames:
            if any(k in (frame.url or "") for k in ["weixin", "wx.qq", "open.weixin"]):
                frame_el = page.frame_locator(f"iframe[src*='weixin'], iframe[src*='wx.qq']").locator("img, canvas").first
                if frame_el.is_visible():
                    frame_el.screenshot(path=str(QR_SCREENSHOT))
                    return _versioned_url(QR_SCREENSHOT)
    except Exception:
        pass

    # 2. 找 QR 元素
    qr = _find_qr_element(page)
    if qr:
        try:
            qr.screenshot(path=str(QR_SCREENSHOT))
            return _versioned_url(QR_SCREENSHOT)
        except Exception:
            pass

    # 3. 截登录卡片区域
    for card_sel in [
        "[class*='login-box']", "[class*='login-card']",
        "[class*='login-container']", "[class*='login-modal']",
        "[class*='login-wrap']", "[class*='login-panel']",
        "form",
    ]:
        try:
            card = page.locator(card_sel).first
            if card.is_visible():
                box = card.bounding_box()
                if box and box["width"] > 80:
                    card.screenshot(path=str(QR_SCREENSHOT))
                    return _versioned_url(QR_SCREENSHOT)
        except Exception:
            continue

    # 4. 全页截图（让用户看到完整页面，自行找 QR）
    page.screenshot(path=str(QR_SCREENSHOT), full_page=True)
    return _versioned_url(QR_SCREENSHOT)


# ── HTTP 会话工具 ─────────────────────────────────────────────────────

def _build_http_session() -> Any:
    """从保存的 cookie 文件构建 requests.Session。"""
    import requests

    if not COOKIE_FILE.exists():
        raise RuntimeError("未找到已保存的 Cookie，请先导入 Cookie。")

    cookies_data: list[dict] = json.loads(COOKIE_FILE.read_text(encoding="utf-8"))
    session = requests.Session()
    session.headers.update(_HTTP_HEADERS)
    # 直接按名/值设置，不指定 domain，确保所有请求都带上 cookie
    for c in cookies_data:
        session.cookies.set(c["name"], c["value"])
    return session


def _verify_login_http(session: Any) -> tuple[bool, str]:
    """
    用 HTTP GET 验证登录状态，返回 (is_logged_in, username)。
    不使用 Playwright，无 headless 检测风险。
    """
    try:
        resp = session.get(
            f"{API_BASE}/user/author_info/v0/",
            params={"app_name": APP_NAME},
            timeout=15,
        )
        data = resp.json()
        if data.get("code") == 0:
            info = data.get("data") or {}
            name = (
                info.get("pen_name")
                or info.get("nick_name")
                or info.get("user_name")
                or ""
            )
            return True, str(name)
    except Exception:
        pass

    # 备用：检查章节列表接口是否能访问
    try:
        resp = session.get(
            f"{API_BASE}/book/list/v0/",
            params={"app_name": APP_NAME, "page_count": 1},
            timeout=15,
        )
        if resp.status_code == 200 and resp.json().get("code") == 0:
            return True, ""
    except Exception:
        pass

    return False, ""


def _save_cookies_to_file(ctx_cookies: list[dict]) -> None:
    """将 Playwright 上下文中的 cookie 列表保存到 JSON 文件。"""
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    COOKIE_FILE.write_text(
        json.dumps(ctx_cookies, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ── Cookie 导入 ───────────────────────────────────────────────────────

def import_cookies(cookies_json: list[dict]) -> dict[str, Any]:
    """
    把从浏览器导出的 Cookie JSON 写入持久化 Profile，
    下次打开浏览器即为已登录状态。
    """
    from playwright.sync_api import sync_playwright

    # 规范化 Cookie 格式（Cookie-Editor 导出 → Playwright 格式）
    clean: list[dict] = []
    for c in cookies_json:
        name = str(c.get("name") or "").strip()
        value = str(c.get("value") or "")
        if not name:
            continue
        entry: dict[str, Any] = {
            "name": name,
            "value": value,
            "domain": str(c.get("domain") or ".fanqienovel.com"),
            "path": str(c.get("path") or "/"),
        }
        # Cookie-Editor 用 expirationDate，标准格式用 expires
        exp = c.get("expirationDate") or c.get("expires")
        if isinstance(exp, (int, float)) and exp > 0:
            entry["expires"] = float(exp)
        # sameSite: Cookie-Editor 输出 null / "no_restriction" / "lax" / "strict"
        same_raw = c.get("sameSite")
        same = str(same_raw).lower() if same_raw is not None else ""
        mapping = {
            "no_restriction": "None",
            "lax": "Lax",
            "strict": "Strict",
            "none": "None",
        }
        entry["sameSite"] = mapping.get(same, "Lax")
        if c.get("httpOnly"):
            entry["httpOnly"] = True
        if c.get("secure"):
            entry["secure"] = True
        clean.append(entry)

    if not clean:
        raise ValueError("Cookie 列表为空或格式不正确，请重新导出。")

    # ── 阶段 1：把 cookie 写入 Playwright profile（供浏览器自动化备用） ──
    with _BROWSER_LOCK:
        PROFILE_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as pw:
            ctx = _open_context(pw)
            try:
                failed = []
                for ck in clean:
                    try:
                        ctx.add_cookies([ck])
                    except Exception as e:
                        failed.append(f"{ck.get('name')}: {e}")
                if failed:
                    import logging
                    logging.getLogger(__name__).warning("跳过的 Cookie: %s", failed)

                # 把 Playwright 中的 cookie 存成 JSON，供 HTTP 直接调用
                all_cookies = ctx.cookies()
                _save_cookies_to_file(all_cookies)
            finally:
                ctx.close()

    # ── 阶段 2：用 requests 直接 HTTP 验证（不启动浏览器，无 headless 检测） ──
    session = _build_http_session()
    logged_in, username = _verify_login_http(session)

    if logged_in:
        _set_state(
            status="logged_in",
            logged_in=True,
            screenshot_url="",
            message=f"Cookie 导入成功，已登录番茄小说：{username or '创作者'}",
            username=username,
        )

    return {
        "ok": logged_in,
        "cookie_count": len(clean),
        "logged_in": logged_in,
        "username": username,
        "screenshot_url": "",
        "message": (
            f"导入 {len(clean)} 个 Cookie，HTTP 验证成功，账号：{username or '创作者'}"
            if logged_in
            else (
                f"导入 {len(clean)} 个 Cookie 并已保存，但 HTTP 验证暂未通过。"
                " Cookie 已存储，可以尝试直接推送章节。"
            )
        ),
    }


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

                    # 直接进作者中心，让它自然跳到作者登录页
                    page.goto(AUTHOR_CENTER_URL, wait_until="domcontentloaded", timeout=30_000)
                    page.wait_for_timeout(4000)

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

                    # 收集调试信息写入状态
                    dbg = _page_debug_info(page)
                    _set_state(debug_info=dbg)

                    # 尝试切换到微信扫码登录
                    _click_wechat_login_tab(page)
                    page.wait_for_timeout(2000)

                    qr_url = _capture_qr(page)
                    _set_state(
                        status="qr_ready",
                        logged_in=False,
                        qr_url=qr_url,
                        screenshot_url=qr_url,
                        message="请用微信扫描二维码登录番茄小说创作中心。",
                    )
                    _SESSION_READY.set()

                    # 轮询等待扫码（5 分钟）
                    deadline = time.time() + 300
                    while time.time() < deadline:
                        page.wait_for_timeout(2500)
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
                        # 每次刷新 QR 截图（QR 会自动过期刷新）
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


# ── HTTP 直接推章节（主要路径） ───────────────────────────────────────

def _fanqie_api(session: Any, method: str, path: str, **kwargs: Any) -> dict:
    """封装 FanQie API 调用，统一加 app_name 参数并检查返回码。"""
    url = f"{API_BASE}/{path.lstrip('/')}"
    # 在 params 里始终带 app_name
    params = kwargs.pop("params", {})
    params.setdefault("app_name", APP_NAME)
    resp = session.request(method, url, params=params, timeout=30, **kwargs)
    resp.raise_for_status()
    body = resp.json()
    return body


def _list_books_http(session: Any) -> list[dict]:
    """获取创作者名下的书籍列表。"""
    for path in [
        "book/list/v0/",
        "book/list/v1/",
        "book/get_author_book_list/v0/",
    ]:
        try:
            body = _fanqie_api(session, "GET", path, params={"page_count": 50})
            if body.get("code") == 0:
                items = (
                    body.get("data", {}).get("book_list")
                    or body.get("data", {}).get("items")
                    or body.get("data", [])
                )
                if isinstance(items, list):
                    return items
        except Exception:
            continue
    return []


def _find_book_id_http(session: Any, work_name: str) -> str | None:
    """按书名在书籍列表里查找 book_id。"""
    books = _list_books_http(session)
    for book in books:
        name = book.get("book_name") or book.get("title") or book.get("name") or ""
        if work_name in name or name in work_name:
            return str(book.get("book_id") or book.get("id") or "")
    return None


def _create_chapter_http(session: Any, book_id: str, title: str) -> str:
    """新建章节，返回 item_id。"""
    for path in [
        "article/new_item/v0/",
        "article/new_article/v0/",
        "article/create_item/v0/",
    ]:
        try:
            body = _fanqie_api(
                session, "POST", path,
                data={
                    "book_id": book_id,
                    "item_type": 1,          # 1 = 正文章节
                    "title": title,
                    "app_name": APP_NAME,
                },
            )
            if body.get("code") == 0:
                item_id = (
                    (body.get("data") or {}).get("item_id")
                    or (body.get("data") or {}).get("id")
                )
                if item_id:
                    return str(item_id)
        except Exception:
            continue
    raise RuntimeError("无法创建新章节，请检查 API 或联系开发者。")


def _save_chapter_content_http(
    session: Any,
    book_id: str,
    item_id: str,
    title: str,
    content: str,
) -> bool:
    """保存章节内容（草稿）。"""
    payload = {
        "book_id": book_id,
        "item_id": item_id,
        "title": title,
        "content": content,
        "app_name": APP_NAME,
    }
    for path in [
        "article/save_article/v0/",
        "article/save_draft/v0/",
        "article/update_item/v0/",
        "article/save_doc/v0/",
    ]:
        try:
            body = _fanqie_api(session, "POST", path, data=payload)
            if body.get("code") == 0:
                return True
        except Exception:
            continue
    return False


def push_chapter_via_http(
    *,
    book_id: str,
    chapter_title: str,
    content: str,
) -> dict[str, Any]:
    """
    用 HTTP 直接调用 FanQie API 推送章节，不经过 Playwright 浏览器。
    返回详细信息供调试。
    """
    import requests

    session = _build_http_session()

    # ── 步骤 1：验证登录 ──
    logged_in, username = _verify_login_http(session)

    # ── 步骤 2：创建新章节（获取 item_id） ──
    item_id = _create_chapter_http(session, book_id, chapter_title)

    # ── 步骤 3：写入内容 ──
    saved = _save_chapter_content_http(session, book_id, item_id, chapter_title, content)

    return {
        "ok": saved,
        "item_id": item_id,
        "book_id": book_id,
        "logged_in": logged_in,
        "username": username,
        "message": (
            f"章节「{chapter_title}」已创建（item_id={item_id}）并保存到草稿箱。"
            if saved
            else f"章节已创建（item_id={item_id}），但内容写入未确认，请检查番茄后台。"
        ),
    }


# ── 推章节草稿 ────────────────────────────────────────────────────────

def push_chapter_draft(
    *,
    work_name: str,
    book_id: str = "",
    chapter_number: int,
    chapter_title: str,
    content: str,
) -> dict[str, Any]:
    """
    将章节内容推送到番茄小说对应作品的草稿箱。
    优先使用 HTTP 直接调用，无 Playwright 浏览器检测问题。

    Args:
        work_name:      番茄小说上的小说名称（用于匹配作品）
        book_id:        直接指定 book_id（填了就跳过名称查找）
        chapter_number: 章节序号（仅用于日志/标题）
        chapter_title:  章节标题
        content:        章节正文（Markdown 或纯文本）
    """
    plain = _md_to_plain(content)

    # ── 路径 1：HTTP 直接 API ──
    if COOKIE_FILE.exists():
        try:
            session = _build_http_session()

            # 如果没有传 book_id，按名称查找
            bid = book_id
            if not bid:
                bid = _find_book_id_http(session, work_name) or ""

            if not bid:
                raise RuntimeError(
                    f"未能在番茄小说找到作品「{work_name}」，"
                    "请在前端填写 book_id（从章节管理 URL 获取）。"
                )

            result = push_chapter_via_http(
                book_id=bid,
                chapter_title=chapter_title,
                content=plain,
            )
            result["chapter_number"] = chapter_number
            if result.get("ok"):
                result["message"] = (
                    f"第 {chapter_number} 章「{chapter_title}」" + result.get("message", "")
                )
            return result

        except RuntimeError:
            raise
        except Exception as exc:
            raise RuntimeError(f"番茄小说 HTTP 推稿失败：{str(exc)}") from exc

    # ── 路径 2：Playwright 浏览器（备用，仅在 cookie 文件不存在时走） ──
    from playwright.sync_api import sync_playwright

    with _BROWSER_LOCK:
        with sync_playwright() as pw:
            context = _open_context(pw)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(AUTHOR_CENTER_URL, wait_until="domcontentloaded", timeout=60_000)
                page.wait_for_timeout(3000)

                if not _is_logged_in(page):
                    raise RuntimeError("番茄小说未登录，请先导入 Cookie。")

                _navigate_to_work(page, work_name)
                _click_new_chapter(page)
                _fill_chapter_title(page, chapter_title)
                _fill_chapter_content(page, plain)
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
