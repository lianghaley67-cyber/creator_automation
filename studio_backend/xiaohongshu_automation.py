from __future__ import annotations

import threading
import time
from queue import Empty, Queue
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
_LOGIN_COMMANDS: Queue[dict[str, Any]] = Queue()
_SESSION_STATE: dict[str, Any] = {
    "status": "not_started",
    "logged_in": False,
    "screenshot_url": "",
    "viewport_width": 1440,
    "viewport_height": 1000,
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


def _normalize_phone(phone: str) -> str:
    normalized = "".join(character for character in str(phone or "") if character.isdigit())
    if normalized.startswith("86") and len(normalized) == 13:
        normalized = normalized[2:]
    if len(normalized) != 11:
        raise ValueError("请输入 11 位中国大陆手机号。")
    return normalized


def _login_page_screenshot(page: Any) -> str:
    page.screenshot(path=str(SESSION_SCREENSHOT))
    return _versioned_media_url(SESSION_SCREENSHOT)


def _challenge_visible(page: Any) -> bool:
    challenge_selectors = [
        "[class*='captcha']",
        "[class*='geetest']",
        "[class*='slide-verify']",
        "[class*='slider']",
        "iframe[src*='captcha']",
    ]
    if _first_visible(page, challenge_selectors):
        return True
    return bool(
        _first_visible_text(
            page,
            ["请完成验证", "拖动滑块", "向右拖动滑块填充拼图"],
        )
    )


def _login_failure_text(page: Any) -> str:
    keywords = [
        "验证码错误",
        "验证码不正确",
        "验证码已过期",
        "验证码失效",
        "验证码错误或已过期",
        "操作频繁",
        "请求频繁",
        "请稍后再试",
        "请完成验证",
        "手机号格式错误",
        "登录失败",
        "账号存在风险",
        "当前环境存在风险",
    ]
    candidates = page.locator(
        "[role='alert'], [class*='error'], [class*='toast'], "
        "[class*='message'], [class*='tip']"
    )
    for index in range(min(candidates.count(), 30)):
        item = candidates.nth(index)
        if not item.is_visible():
            continue
        text = " ".join(str(item.inner_text() or "").split())
        if text and any(keyword in text for keyword in keywords):
            return text[:160]

    body_text = str(page.locator("body").inner_text() or "")
    for line in body_text.splitlines():
        normalized = " ".join(line.split())
        if normalized and any(keyword in normalized for keyword in keywords):
            return normalized[:160]
    return ""


def _session_snapshot(page: Any) -> dict[str, Any]:
    viewport = page.viewport_size or {"width": 1440, "height": 1000}
    logged_in = _is_logged_in(page)
    challenge_visible = _challenge_visible(page)
    return {
        "status": "logged_in" if logged_in else "phone_required",
        "logged_in": logged_in,
        "challenge_visible": challenge_visible,
        "screenshot_url": _login_page_screenshot(page),
        "viewport_width": int(viewport["width"]),
        "viewport_height": int(viewport["height"]),
        "message": (
            "服务器上的小红书登录态有效，可以直接保存草稿。"
            if logged_in
            else (
                "检测到滑块验证，请在服务器画面中拖动滑块。"
                if challenge_visible
                else "当前没有检测到滑块。请直接发送新验证码并登录，不要在画面上拖动。"
            )
        ),
    }


def _ensure_phone_login(page: Any) -> Any:
    phone_input = _phone_login_input(page)
    if phone_input:
        return phone_input
    sms_login = _first_visible_text(page, ["短信登录", "手机号登录"])
    if sms_login:
        sms_login.click()
        page.wait_for_timeout(1000)
    phone_input = _phone_login_input(page)
    if not phone_input:
        raise RuntimeError("没有找到小红书手机号登录框，页面可能已改版。")
    return phone_input


def _send_sms_on_page(page: Any, phone: str) -> dict[str, Any]:
    phone_input = _ensure_phone_login(page)
    phone_input.fill(phone)
    send_button = _first_visible_text(page, ["发送验证码", "获取验证码"])
    if not send_button:
        raise RuntimeError("没有找到“发送验证码”按钮，页面可能已改版。")
    send_button.click()
    page.wait_for_timeout(800)

    consent_button = _first_visible_text(page, ["同意并继续", "同意并登录"])
    if consent_button:
        consent_button.click()
        page.wait_for_timeout(700)
        send_button = _first_visible_text(page, ["发送验证码", "获取验证码"])
        if not send_button:
            raise RuntimeError("同意用户协议后，没有重新找到“发送验证码”按钮。")
        send_button.click()
        page.wait_for_timeout(1800)
    else:
        page.wait_for_timeout(1000)

    screenshot_url = _login_page_screenshot(page)
    consent_still_visible = _first_visible_text(page, ["同意并继续", "同意并登录"])
    if consent_still_visible:
        raise RuntimeError("小红书用户协议确认弹窗仍未关闭，请查看服务器诊断截图。")
    active_send_button = _first_visible_text(page, ["发送验证码", "获取验证码"])
    if active_send_button and active_send_button.is_enabled():
        raise RuntimeError("小红书没有确认验证码已发送，可能触发了风控或滑块验证，请查看诊断截图。")
    return {
        "status": "sms_sent",
        "logged_in": False,
        "screenshot_url": screenshot_url,
        "phone_masked": f"{phone[:3]}****{phone[-4:]}",
        "message": "验证码请求已提交，请查看手机短信。若页面要求滑块验证，请查看截图提示。",
    }


def _verify_sms_on_page(page: Any, phone: str, code: str) -> dict[str, Any]:
    phone_input = _ensure_phone_login(page)
    phone_input.fill(phone)
    code_input = _first_visible(
        page,
        [
            "input[placeholder*='验证码']",
            "input[placeholder*='短信']",
        ],
    )
    if not code_input:
        raise RuntimeError("没有找到验证码输入框，页面可能已改版。")
    code_input.fill(code)

    checkbox = _first_visible(page, ["input[type='checkbox']"])
    if checkbox and not checkbox.is_checked():
        checkbox.check(force=True)

    login_button = _first_visible_text(page, ["登录"])
    if not login_button:
        raise RuntimeError("没有找到小红书登录按钮。")
    login_button.scroll_into_view_if_needed()
    login_button.click(no_wait_after=True, timeout=10000, force=True)

    logged_in = False
    failure_message = ""
    challenge_visible = False
    deadline = time.time() + 20
    while time.time() < deadline:
        page.wait_for_timeout(1000)
        if _is_logged_in(page):
            logged_in = True
            break
        failure_message = _login_failure_text(page)
        challenge_visible = _challenge_visible(page)
        if failure_message:
            break
        if challenge_visible:
            break

    screenshot_url = _login_page_screenshot(page)
    return {
        "status": "logged_in" if logged_in else "verification_failed",
        "logged_in": logged_in,
        "challenge_visible": challenge_visible,
        "screenshot_url": screenshot_url,
        "message": (
            "小红书服务器登录成功，后续可以直接保存官方草稿。"
            if logged_in
            else (
                f"小红书提示：{failure_message}。请重新获取验证码后再试。"
                if failure_message
                else (
                    "小红书要求先完成滑块验证。请在下方服务器画面中拖动滑块，然后重新获取验证码。"
                    if challenge_visible
                    else "小红书点击登录后仍停留在原页面，但没有显示滑块或错误文字。请重新发送一个新验证码，并在收到后 60 秒内只点击一次登录。"
                )
            )
        ),
    }


def _drag_on_page(
    page: Any,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> dict[str, Any]:
    if not _challenge_visible(page):
        raise RuntimeError("当前小红书页面没有检测到滑块，请不要拖动画面，直接使用新验证码登录。")
    viewport = page.viewport_size or {"width": 1440, "height": 1000}
    width = float(viewport["width"])
    height = float(viewport["height"])
    points = (start_x, start_y, end_x, end_y)
    if not all(value >= 0 for value in points):
        raise ValueError("拖动坐标不能小于 0。")
    if start_x > width or end_x > width or start_y > height or end_y > height:
        raise ValueError("拖动位置超出服务器浏览器画面，请刷新截图后重试。")
    if abs(end_x - start_x) < 20 and abs(end_y - start_y) < 10:
        raise ValueError("拖动距离太短，请从滑块中心按住并向右拖动。")

    page.mouse.move(start_x, start_y)
    page.mouse.down()
    page.mouse.move(end_x, end_y, steps=35)
    page.wait_for_timeout(350)
    page.mouse.up()
    page.wait_for_timeout(1800)

    logged_in = _is_logged_in(page)
    screenshot_url = _login_page_screenshot(page)
    return {
        "status": "logged_in" if logged_in else "drag_completed",
        "logged_in": logged_in,
        "challenge_visible": _challenge_visible(page),
        "screenshot_url": screenshot_url,
        "viewport_width": int(width),
        "viewport_height": int(height),
        "message": (
            "滑块验证后已登录成功。"
            if logged_in
            else "服务器已经执行拖动并刷新画面。请查看滑块是否通过；通过后继续发送验证码或登录。"
        ),
    }


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
                    initial_state = _session_snapshot(page)
                    logged_in = bool(initial_state["logged_in"])
                    if not logged_in:
                        initial_state["message"] = "请输入手机号，通过短信验证码登录服务器浏览器。"
                    _set_session_state(**initial_state)
                    _SESSION_READY.set()
                    if logged_in:
                        return
                    deadline = time.time() + 600
                    while time.time() < deadline:
                        try:
                            command = _LOGIN_COMMANDS.get(timeout=2)
                        except Empty:
                            continue
                        result_holder = command["result"]
                        try:
                            if command["action"] == "send_sms":
                                result = _send_sms_on_page(page, command["phone"])
                            elif command["action"] == "verify_sms":
                                result = _verify_sms_on_page(
                                    page,
                                    command["phone"],
                                    command["code"],
                                )
                            elif command["action"] == "drag":
                                result = _drag_on_page(
                                    page,
                                    command["start_x"],
                                    command["start_y"],
                                    command["end_x"],
                                    command["end_y"],
                                )
                            elif command["action"] == "refresh":
                                result = _session_snapshot(page)
                            else:
                                result = {"status": "failed", "message": "未知登录操作。"}
                            _set_session_state(**result)
                            result_holder["result"] = result
                            if result.get("logged_in"):
                                result_holder["event"].set()
                                return
                        except Exception as exc:
                            screenshot_url = _login_page_screenshot(page)
                            _set_session_state(
                                status="sms_failed",
                                logged_in=False,
                                screenshot_url=screenshot_url,
                                message=str(exc)[:300],
                            )
                            result_holder["error"] = str(exc)
                        finally:
                            result_holder["event"].set()
                    _set_session_state(
                        status="expired",
                        logged_in=False,
                        message="短信登录会话已过期，请重新检查登录状态。",
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


def _run_login_command(action: str, **payload: str) -> dict[str, Any]:
    session = capture_login_session()
    if session.get("logged_in"):
        return session
    holder: dict[str, Any] = {"event": threading.Event()}
    _LOGIN_COMMANDS.put(
        {
            "action": action,
            "result": holder,
            **payload,
        }
    )
    if not holder["event"].wait(timeout=75):
        raise RuntimeError("小红书登录操作超时，请稍后重试。")
    if holder.get("error"):
        raise RuntimeError(str(holder["error"]))
    return dict(holder.get("result") or {})


def send_sms_code(phone: str) -> dict[str, Any]:
    return _run_login_command("send_sms", phone=_normalize_phone(phone))


def verify_sms_code(phone: str, code: str) -> dict[str, Any]:
    normalized_code = "".join(character for character in str(code or "") if character.isdigit())
    if not 4 <= len(normalized_code) <= 10:
        raise ValueError("请输入短信中的验证码。")
    return _run_login_command(
        "verify_sms",
        phone=_normalize_phone(phone),
        code=normalized_code,
    )


def drag_login_slider(
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> dict[str, Any]:
    return _run_login_command(
        "drag",
        start_x=start_x,
        start_y=start_y,
        end_x=end_x,
        end_y=end_y,
    )


def refresh_login_frame() -> dict[str, Any]:
    return _run_login_command("refresh")


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
