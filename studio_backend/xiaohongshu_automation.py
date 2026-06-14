from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Any

from .storage import STUDIO_DIR, to_media_url


CREATOR_URL = "https://creator.xiaohongshu.com/publish/publish"
PROFILE_DIR = STUDIO_DIR / "xiaohongshu_browser_profile"
SCREENSHOT_DIR = STUDIO_DIR / "xiaohongshu_session"
SESSION_SCREENSHOT = SCREENSHOT_DIR / "login.png"
QR_SCREENSHOT = SCREENSHOT_DIR / "login_qr.png"
RESULT_SCREENSHOT = SCREENSHOT_DIR / "latest.png"
_BROWSER_LOCK = threading.Lock()
_SESSION_STATE_LOCK = threading.Lock()
_SESSION_READY = threading.Event()
_LOGIN_THREAD: threading.Thread | None = None
_SESSION_STATE: dict[str, Any] = {
    "status": "not_started",
    "logged_in": False,
    "screenshot_url": "",
    "message": "尚未启动小红书服务器登录。",
}


class XiaohongshuLoginRequired(RuntimeError):
    pass


def _first_visible(page: Any, selectors: list[str]) -> Any | None:
    for selector in selectors:
        matches = page.locator(selector)
        for index in range(matches.count()):
            item = matches.nth(index)
            if item.is_visible():
                return item
    return None


def _first_visible_text(page: Any, labels: list[str]) -> Any | None:
    for label in labels:
        matches = page.get_by_text(label, exact=True)
        for index in range(matches.count()):
            item = matches.nth(index)
            if item.is_visible():
                return item
    return None


def _open_context(playwright: Any) -> Any:
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    return playwright.chromium.launch_persistent_context(
        str(PROFILE_DIR),
        headless=True,
        viewport={"width": 1440, "height": 1000},
        args=["--no-sandbox", "--disable-dev-shm-usage"],
    )


def _is_logged_in(page: Any) -> bool:
    if "login" in str(page.url or "").lower():
        return False
    if _first_visible_text(page, ["扫码登录", "手机号登录", "登录后发布"]):
        return False
    return bool(
        _first_visible_text(page, ["上传图文", "上传视频", "写长文", "草稿箱"])
        or _first_visible(page, ["input[type=file]"])
    )


def _phone_login_input(page: Any) -> Any | None:
    return _first_visible(
        page,
        [
            "input[placeholder*='手机号']",
            "input[placeholder*='手机']",
            "input[type='tel']",
        ],
    )


def _login_card_box(page: Any) -> dict[str, float] | None:
    phone_input = _phone_login_input(page)
    if not phone_input:
        return None
    candidate: dict[str, float] | None = None
    parent = phone_input
    for _ in range(8):
        parent = parent.locator("xpath=..")
        if parent.count() != 1:
            break
        box = parent.bounding_box()
        if not box:
            continue
        if 180 <= box["width"] <= 460 and 180 <= box["height"] <= 560:
            candidate = box
        if box["width"] > 500 or box["height"] > 650:
            break
    return candidate


def _switch_to_qr_login(page: Any) -> bool:
    qr_text = _first_visible_text(page, ["扫码登录", "二维码登录"])
    if qr_text:
        qr_text.click()
        page.wait_for_timeout(1200)
        return True

    selectors = [
        "[class*='qrcode-switch']",
        "[class*='qr-code-switch']",
        "[class*='login-switch']",
        "[class*='switch-login']",
        "[class*='qrcode'] button",
        "img[alt*='二维码']",
        "[aria-label*='二维码']",
        "[title*='二维码']",
    ]
    candidate = _first_visible(page, selectors)
    if candidate:
        candidate.click()
        page.wait_for_timeout(1200)
        return True

    card_box = _login_card_box(page)
    if card_box:
        # 登录方式切换按钮固定在登录卡片右上角。以手机号输入框是否消失判断切换成功。
        for inset_x, inset_y in ((16, 16), (24, 16), (16, 24), (30, 24)):
            page.mouse.click(
                card_box["x"] + card_box["width"] - inset_x,
                card_box["y"] + inset_y,
            )
            page.wait_for_timeout(900)
            if not _phone_login_input(page):
                return True

    sms_title = _first_visible_text(page, ["短信登录", "手机号登录"])
    if sms_title:
        box = sms_title.bounding_box()
        if box:
            for offset_x, offset_y in ((170, -14), (185, -14), (170, -4)):
                page.mouse.click(box["x"] + offset_x, max(8, box["y"] + offset_y))
                page.wait_for_timeout(900)
                if not _phone_login_input(page):
                    return True
    return False


def _find_qr_element(page: Any) -> Any | None:
    qr_selectors = [
        "[class*='qrcode'] canvas",
        "[class*='qr-code'] canvas",
        "[class*='qrcode'] img",
        "[class*='qr-code'] img",
        "img[alt*='二维码']",
        "canvas",
    ]
    for selector in qr_selectors:
        matches = page.locator(selector)
        for index in range(matches.count()):
            qr = matches.nth(index)
            if not qr.is_visible():
                continue
            box = qr.bounding_box()
            if (
                box
                and 100 <= box["width"] <= 500
                and 100 <= box["height"] <= 500
            ):
                return qr
    return None


def _versioned_media_url(path: Path) -> str:
    return f"{to_media_url(path)}?v={int(time.time() * 1000)}"


def _capture_qr_image(
    page: Any,
    fallback_box: dict[str, float] | None = None,
) -> str:
    qr = _find_qr_element(page)
    if qr:
        qr.screenshot(path=str(QR_SCREENSHOT))
        return _versioned_media_url(QR_SCREENSHOT)
    # 二维码可能由背景图或 Shadow DOM 绘制。只要手机号输入框已消失，
    # 就裁剪登录卡片区域，保留一个可扫码的小图。
    if not _phone_login_input(page):
        card_candidates = [
            "[class*='login-container']",
            "[class*='login-box']",
            "[class*='login-panel']",
            "[class*='login-card']",
        ]
        card = _first_visible(page, card_candidates)
        if card:
            box = card.bounding_box()
            if box and 180 <= box["width"] <= 600 and 180 <= box["height"] <= 700:
                card.screenshot(path=str(QR_SCREENSHOT))
                return _versioned_media_url(QR_SCREENSHOT)
        if fallback_box:
            page.screenshot(
                path=str(QR_SCREENSHOT),
                clip={
                    "x": max(0, fallback_box["x"]),
                    "y": max(0, fallback_box["y"]),
                    "width": fallback_box["width"],
                    "height": fallback_box["height"],
                },
            )
            return _versioned_media_url(QR_SCREENSHOT)
    page.screenshot(path=str(SESSION_SCREENSHOT), full_page=True)
    return _versioned_media_url(SESSION_SCREENSHOT)


def _set_session_state(**patch: Any) -> None:
    with _SESSION_STATE_LOCK:
        _SESSION_STATE.update(patch)


def _login_session_worker() -> None:
    from playwright.sync_api import sync_playwright

    try:
        with _BROWSER_LOCK:
            SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
            with sync_playwright() as playwright:
                context = _open_context(playwright)
                try:
                    page = context.pages[0] if context.pages else context.new_page()
                    page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(2500)
                    logged_in = _is_logged_in(page)
                    screenshot_url = ""
                    if logged_in:
                        page.screenshot(path=str(SESSION_SCREENSHOT), full_page=True)
                        screenshot_url = _versioned_media_url(SESSION_SCREENSHOT)
                    else:
                        login_card_box = _login_card_box(page)
                        _switch_to_qr_login(page)
                        screenshot_url = _capture_qr_image(page, login_card_box)
                    _set_session_state(
                        status="logged_in" if logged_in else "waiting_for_scan",
                        logged_in=logged_in,
                        screenshot_url=screenshot_url,
                        message=(
                            "服务器上的小红书登录态有效，可以直接保存草稿。"
                            if logged_in
                            else "请直接用小红书 App 扫描下方二维码。图片不能点击，也不需要在这里输入手机号。服务器会等待 3 分钟。"
                        ),
                    )
                    _SESSION_READY.set()
                    if logged_in:
                        return
                    deadline = time.time() + 180
                    while time.time() < deadline:
                        page.wait_for_timeout(2000)
                        if _is_logged_in(page):
                            page.screenshot(path=str(SESSION_SCREENSHOT), full_page=True)
                            _set_session_state(
                                status="logged_in",
                                logged_in=True,
                                screenshot_url=_versioned_media_url(SESSION_SCREENSHOT),
                                message="扫码成功，服务器已保存小红书登录状态。",
                            )
                            return
                    _set_session_state(
                        status="expired",
                        logged_in=False,
                        message="登录二维码已过期，请点击按钮重新生成。",
                    )
                finally:
                    context.close()
    except Exception as exc:
        _set_session_state(
            status="failed",
            logged_in=False,
            message=f"服务器浏览器启动失败：{str(exc)[:300]}",
        )
        _SESSION_READY.set()


def capture_login_session() -> dict[str, Any]:
    global _LOGIN_THREAD
    with _SESSION_STATE_LOCK:
        running = _LOGIN_THREAD is not None and _LOGIN_THREAD.is_alive()
    if not running:
        _SESSION_READY.clear()
        _set_session_state(
            status="starting",
            logged_in=False,
            message="正在启动服务器小红书登录页面……",
        )
        _LOGIN_THREAD = threading.Thread(
            target=_login_session_worker,
            name="xiaohongshu-login-session",
            daemon=True,
        )
        _LOGIN_THREAD.start()
        _SESSION_READY.wait(timeout=15)
    with _SESSION_STATE_LOCK:
        return dict(_SESSION_STATE)


def _resolve_media_paths(task: dict[str, Any]) -> list[Path]:
    xiaohongshu = task.get("xiaohongshu") if isinstance(task.get("xiaohongshu"), dict) else {}
    paths: list[Path] = []
    for raw_url in xiaohongshu.get("card_urls") or []:
        url = str(raw_url or "").strip()
        marker = "/studio-files/"
        if marker not in url:
            continue
        relative = url.split(marker, 1)[1].split("?", 1)[0]
        candidate = (STUDIO_DIR / relative).resolve()
        try:
            candidate.relative_to(STUDIO_DIR.resolve())
        except ValueError:
            continue
        if candidate.exists() and candidate.is_file():
            paths.append(candidate)
    return paths


def save_platform_draft(task: dict[str, Any]) -> dict[str, Any]:
    from playwright.sync_api import sync_playwright

    xiaohongshu = task.get("xiaohongshu") if isinstance(task.get("xiaohongshu"), dict) else {}
    title = str(xiaohongshu.get("title") or task.get("title") or "").strip()[:20]
    body = str(xiaohongshu.get("body") or "").strip()
    uploads = _resolve_media_paths(task)
    if not uploads:
        raise RuntimeError("没有找到可上传的小红书图卡，请先重新生成公众号 + 小红书发布包。")
    if not title or not body:
        raise RuntimeError("小红书标题或正文为空，请先生成发布包。")

    with _BROWSER_LOCK:
        SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        with sync_playwright() as playwright:
            context = _open_context(playwright)
            try:
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(CREATOR_URL, wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(2500)
                if not _is_logged_in(page):
                    page.screenshot(path=str(SESSION_SCREENSHOT), full_page=True)
                    _set_session_state(
                        status="login_required",
                        logged_in=False,
                        screenshot_url=_versioned_media_url(SESSION_SCREENSHOT),
                        message="服务器的小红书登录已失效，请刷新二维码并重新扫码。",
                    )
                    raise XiaohongshuLoginRequired("服务器的小红书登录已失效，请先扫码登录。")

                image_tab = _first_visible_text(page, ["上传图文"])
                if image_tab:
                    image_tab.click()
                    page.wait_for_timeout(1500)

                upload = _first_visible(page, ["input[type=file]"])
                if not upload:
                    raise RuntimeError("没有找到小红书图片上传入口，页面可能已改版。")
                upload.set_input_files([str(path) for path in uploads])
                page.wait_for_timeout(4000)

                title_input = _first_visible(
                    page,
                    ["input[placeholder*='标题']", "textarea[placeholder*='标题']"],
                )
                if not title_input:
                    raise RuntimeError("没有找到小红书标题输入框，页面可能已改版。")
                title_input.fill(title)

                body_input = _first_visible(
                    page,
                    [
                        "textarea[placeholder*='正文']",
                        "textarea[placeholder*='描述']",
                        "[contenteditable=true]",
                    ],
                )
                if not body_input:
                    raise RuntimeError("没有找到小红书正文输入框，页面可能已改版。")
                body_input.fill(body)

                save_button = _first_visible_text(
                    page,
                    ["暂存离开", "保存草稿", "存草稿", "暂存"],
                )
                if not save_button:
                    page.screenshot(path=str(RESULT_SCREENSHOT), full_page=True)
                    raise RuntimeError("内容已经填好，但没有识别到“暂存离开”按钮，请查看服务器截图。")
                save_button.click()
                page.wait_for_timeout(3000)
                page.screenshot(path=str(RESULT_SCREENSHOT), full_page=True)
                return {
                    "status": "platform_draft_saved",
                    "screenshot_url": to_media_url(RESULT_SCREENSHOT),
                    "uploaded_images": len(uploads),
                    "message": "服务器已上传图卡、填写文案并点击保存草稿。",
                }
            finally:
                context.close()
