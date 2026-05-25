from __future__ import annotations

import json
import base64
import hashlib
import hmac
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CREATE_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/services/aigc/video-generation/video-synthesis"
TASK_ENDPOINT = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"
OFFICIAL_BASE_URL = "https://api-singapore.klingai.com"
OFFICIAL_CREATE_PATH = "/v1/videos/image2video"
OFFICIAL_TASK_PATH = "/v1/videos/image2video/{task_id}"


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _post_json(url: str, payload: dict[str, Any], *, api_key: str, async_request: bool = False) -> dict[str, Any]:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    if async_request:
        headers["X-DashScope-Async"] = "enable"
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope Kling create task failed: HTTP {exc.code} {body}") from exc


def _post_json_with_token(url: str, payload: dict[str, Any], *, token: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kling official create task failed: HTTP {exc.code} {body}") from exc


def _get_json(url: str, *, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"DashScope Kling query task failed: HTTP {exc.code} {body}") from exc


def _get_json_with_token(url: str, *, token: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Kling official query task failed: HTTP {exc.code} {body}") from exc


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _make_official_jwt(access_key: str, secret_key: str, *, ttl_sec: int = 1800) -> str:
    now = int(time.time())
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": access_key,
        "exp": now + max(ttl_sec, 60),
        "nbf": now - 5,
    }
    signing_input = ".".join(
        [
            _b64url(json.dumps(header, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
            _b64url(json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")),
        ]
    )
    signature = hmac.new(secret_key.encode("utf-8"), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64url(signature)}"


def _official_base_url() -> str:
    return os.getenv("KLING_API_BASE", OFFICIAL_BASE_URL).strip().rstrip("/") or OFFICIAL_BASE_URL


def _official_create_url() -> str:
    override = os.getenv("KLING_OFFICIAL_CREATE_ENDPOINT", "").strip()
    if override:
        return override
    return f"{_official_base_url()}{os.getenv('KLING_OFFICIAL_CREATE_PATH', OFFICIAL_CREATE_PATH).strip() or OFFICIAL_CREATE_PATH}"


def _official_task_url(task_id: str) -> str:
    override = os.getenv("KLING_OFFICIAL_TASK_ENDPOINT", "").strip()
    if override:
        return override.format(task_id=task_id)
    path = os.getenv("KLING_OFFICIAL_TASK_PATH", OFFICIAL_TASK_PATH).strip() or OFFICIAL_TASK_PATH
    return f"{_official_base_url()}{path.format(task_id=task_id)}"


def _download_file(url: str, output_file: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "creator-automation/0.1"})
    with urllib.request.urlopen(request, timeout=300) as response:
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with output_file.open("wb") as handle:
            while True:
                chunk = response.read(1024 * 1024)
                if not chunk:
                    break
                handle.write(chunk)
    if not output_file.exists() or output_file.stat().st_size < 1024:
        raise RuntimeError("Downloaded Kling video is empty.")


def _build_prompt(request_payload: dict[str, Any], script_text: str) -> str:
    contract = dict(request_payload.get("reference_style_contract") or {})
    video_prompt = _string(contract.get("video_prompt"))
    topic = _string(request_payload.get("topic"))
    learning_goal = _string(request_payload.get("learning_goal"))
    storyboard = request_payload.get("animation_storyboard")
    scene_lines: list[str] = []
    if isinstance(storyboard, list):
        for item in storyboard[:6]:
            if isinstance(item, dict):
                line = _string(item.get("line"))
                shot = _string(item.get("shot_type"))
                scene = _string(item.get("scene_prompt"))
                if line:
                    scene_lines.append(f"{shot}: {line}；场景：{scene}")
    storyboard_text = "\n".join(scene_lines)
    return (
        f"{video_prompt}\n"
        f"主题：{topic}\n"
        f"学习目标：{learning_goal}\n"
        "风格：职场妈妈 AI 提效 IP 短视频，明亮高级、强共情、节奏紧凑，角色始终与参考图一致。\n"
        "动作：两个角色挥手、点头、眨眼、张嘴说话、轻微跳跃，镜头有中景和表情特写。\n"
        f"分镜：\n{storyboard_text}\n"
        f"旁白文案：\n{script_text}"
    )[:2400]


def _pick_task_id(response: dict[str, Any]) -> str:
    candidates = [
        response.get("task_id"),
        response.get("id"),
        (response.get("data") or {}).get("task_id") if isinstance(response.get("data"), dict) else "",
        (response.get("data") or {}).get("id") if isinstance(response.get("data"), dict) else "",
        (response.get("output") or {}).get("task_id") if isinstance(response.get("output"), dict) else "",
    ]
    for item in candidates:
        value = _string(item)
        if value:
            return value
    return ""


def _pick_task_status(payload: dict[str, Any]) -> str:
    pools = [payload]
    for key in ("data", "output"):
        if isinstance(payload.get(key), dict):
            pools.append(payload[key])
    for pool in pools:
        for key in ("task_status", "status", "state"):
            value = _string(pool.get(key)).upper()
            if value:
                return value
    return ""


def _pick_video_url(payload: dict[str, Any]) -> str:
    pools = [payload]
    for key in ("data", "output", "task_result"):
        value = payload.get(key)
        if isinstance(value, dict):
            pools.append(value)
    for pool in list(pools):
        result = pool.get("task_result")
        if isinstance(result, dict):
            pools.append(result)
        videos = pool.get("videos")
        if isinstance(videos, list):
            for item in videos:
                if isinstance(item, dict):
                    url = _string(item.get("url") or item.get("video_url"))
                    if url:
                        return url
        for key in ("video_url", "url", "result_url"):
            url = _string(pool.get(key))
            if url.startswith(("http://", "https://")):
                return url
    return ""


def _local_reference_image_value(request_payload: dict[str, Any]) -> str:
    image_path = Path(_string(request_payload.get("reference_image")))
    if not image_path.exists() or not image_path.is_file():
        image_path = Path(_string(request_payload.get("character_reference_image")))
    if not image_path.exists() or not image_path.is_file():
        return ""
    if image_path.stat().st_size > 10 * 1024 * 1024:
        raise RuntimeError("Kling official API reference image must be smaller than 10 MB when sent as base64.")
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def create_kling_official_task(
    *,
    request_payload: dict[str, Any],
    script_text: str,
    duration: float,
) -> dict[str, Any]:
    access_key = os.getenv("KLING_ACCESS_KEY", "").strip()
    secret_key = os.getenv("KLING_SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("KLING_ACCESS_KEY and KLING_SECRET_KEY are required for Kling official API.")

    reference_url = _string(request_payload.get("reference_image_url"))
    reference_image = reference_url if reference_url.startswith(("http://", "https://")) else ""
    if not reference_image:
        reference_image = _local_reference_image_value(request_payload)
    if not reference_image:
        raise RuntimeError(
            "Kling official API requires a character reference image. Upload a template image, "
            "or provide an HTTP/HTTPS reference_image_url."
        )

    requested_duration = int(round(duration or request_payload.get("seconds") or 5))
    clip_duration = 10 if requested_duration >= 8 else 5
    model = os.getenv("KLING_OFFICIAL_MODEL", "kling-v2-1").strip() or "kling-v2-1"
    mode = os.getenv("KLING_OFFICIAL_MODE", "pro").strip() or "pro"
    cfg_scale = float(os.getenv("KLING_CFG_SCALE", "0.6") or "0.6")
    payload = {
        "model_name": model,
        "prompt": _build_prompt(request_payload, script_text),
        "negative_prompt": "blurry, low resolution, distorted face, inconsistent character, extra characters, text artifacts",
        "image": reference_image,
        "mode": mode,
        "aspect_ratio": "9:16",
        "duration": str(clip_duration),
        "cfg_scale": cfg_scale,
    }
    token = _make_official_jwt(access_key, secret_key)
    response = _post_json_with_token(_official_create_url(), payload, token=token)
    task_id = _pick_task_id(response)
    if not task_id:
        raise RuntimeError(f"Kling official API did not return task id: {json.dumps(response, ensure_ascii=False)}")
    request_for_log = dict(payload)
    if len(str(request_for_log.get("image", ""))) > 200:
        request_for_log["image"] = "<base64_or_url_reference_image>"
    return {
        "task_id": task_id,
        "request": request_for_log,
        "response": response,
    }


def create_kling_task(
    *,
    request_payload: dict[str, Any],
    script_text: str,
    duration: float,
) -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required for 可灵 API via 阿里云百炼.")

    reference_url = _string(request_payload.get("reference_image_url"))
    if not reference_url.startswith(("http://", "https://")):
        raise RuntimeError(
            "可灵 API 需要可公网访问的参考图 URL。请配置 CREATOR_STUDIO_PUBLIC_BASE_URL，"
            "或在 reference_image_url 中传入 HTTP/HTTPS 图片地址。"
        )

    requested_duration = int(round(duration or request_payload.get("seconds") or 5))
    clip_duration = max(3, min(15, requested_duration))
    model = os.getenv("KLING_DASHSCOPE_MODEL", "kling/kling-v3-omni-video-generation").strip()
    mode = os.getenv("KLING_DASHSCOPE_MODE", "pro").strip() or "pro"
    watermark = os.getenv("KLING_WATERMARK", "false").strip().lower() in {"1", "true", "yes", "on"}
    endpoint = os.getenv("KLING_DASHSCOPE_ENDPOINT", CREATE_ENDPOINT).strip() or CREATE_ENDPOINT

    payload = {
        "model": model,
        "input": {
            "prompt": _build_prompt(request_payload, script_text),
            "media": [
                {
                    "type": "refer",
                    "url": reference_url,
                }
            ],
            "multi_shot": False,
            "shot_type": "intelligence",
            "multi_prompt": [],
            "element_list": [],
        },
        "parameters": {
            "mode": mode,
            "duration": clip_duration,
            "audio": False,
            "aspect_ratio": "9:16",
            "watermark": watermark,
        },
    }
    response = _post_json(endpoint, payload, api_key=api_key, async_request=True)
    output = dict(response.get("output") or {})
    task_id = _string(output.get("task_id"))
    if not task_id:
        raise RuntimeError(f"DashScope Kling did not return task_id: {json.dumps(response, ensure_ascii=False)}")
    return {
        "task_id": task_id,
        "request": payload,
        "response": response,
    }


def wait_for_kling_video(
    *,
    task_id: str,
    output_file: Path,
    poll_interval_sec: int = 15,
    timeout_sec: int = 900,
) -> dict[str, Any]:
    api_key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("DASHSCOPE_API_KEY is required for 可灵 API via 阿里云百炼.")
    endpoint_template = os.getenv("KLING_DASHSCOPE_TASK_ENDPOINT", TASK_ENDPOINT).strip() or TASK_ENDPOINT
    deadline = time.time() + max(timeout_sec, 60)
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        payload = _get_json(endpoint_template.format(task_id=task_id), api_key=api_key)
        last_payload = payload
        output = dict(payload.get("output") or {})
        status = _string(output.get("task_status")).upper()
        if status == "SUCCEEDED":
            video_url = _string(output.get("video_url"))
            if not video_url:
                raise RuntimeError(f"Kling task succeeded but no video_url returned: {json.dumps(payload, ensure_ascii=False)}")
            _download_file(video_url, output_file)
            return {
                "task_id": task_id,
                "task_status": status,
                "video_url": video_url,
                "response": payload,
            }
        if status in {"FAILED", "CANCELED", "UNKNOWN"}:
            raise RuntimeError(f"Kling task {status}: {json.dumps(payload, ensure_ascii=False)}")
        time.sleep(max(5, poll_interval_sec))
    raise RuntimeError(f"Kling task timed out: {json.dumps(last_payload, ensure_ascii=False)}")


def wait_for_kling_official_video(
    *,
    task_id: str,
    output_file: Path,
    poll_interval_sec: int = 15,
    timeout_sec: int = 900,
) -> dict[str, Any]:
    access_key = os.getenv("KLING_ACCESS_KEY", "").strip()
    secret_key = os.getenv("KLING_SECRET_KEY", "").strip()
    if not access_key or not secret_key:
        raise RuntimeError("KLING_ACCESS_KEY and KLING_SECRET_KEY are required for 可灵官方 API.")
    deadline = time.time() + max(timeout_sec, 60)
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        token = _make_official_jwt(access_key, secret_key)
        payload = _get_json_with_token(_official_task_url(task_id), token=token)
        last_payload = payload
        status = _pick_task_status(payload)
        if status in {"SUCCEEDED", "SUCCESS", "FINISHED", "COMPLETED"}:
            video_url = _pick_video_url(payload)
            if not video_url:
                raise RuntimeError(f"Kling official task succeeded but no video URL returned: {json.dumps(payload, ensure_ascii=False)}")
            _download_file(video_url, output_file)
            return {
                "task_id": task_id,
                "task_status": status,
                "video_url": video_url,
                "response": payload,
            }
        if status in {"FAILED", "FAIL", "CANCELED", "CANCELLED", "UNKNOWN"}:
            raise RuntimeError(f"Kling official task {status}: {json.dumps(payload, ensure_ascii=False)}")
        time.sleep(max(5, poll_interval_sec))
    raise RuntimeError(f"Kling official task timed out: {json.dumps(last_payload, ensure_ascii=False)}")
