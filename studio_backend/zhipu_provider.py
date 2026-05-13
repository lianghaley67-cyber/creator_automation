from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


CREATE_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/videos/generations"
TASK_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/async-result/{task_id}"


TRANSIENT_NETWORK_MARKERS = (
    "unexpected_eof_while_reading",
    "eof occurred in violation of protocol",
    "remote end closed connection",
    "connection reset",
    "connection aborted",
    "temporarily unavailable",
    "timed out",
    "timeout",
    "ssl",
)


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _api_key() -> str:
    return (
        os.getenv("ZHIPUAI_API_KEY", "").strip()
        or os.getenv("BIGMODEL_API_KEY", "").strip()
        or os.getenv("GLM_API_KEY", "").strip()
    )


def _is_transient_network_error(exc: BaseException) -> bool:
    if isinstance(exc, urllib.error.HTTPError):
        return exc.code in {429, 500, 502, 503, 504}
    if isinstance(exc, urllib.error.URLError):
        return True
    message = str(exc).lower()
    return any(marker in message for marker in TRANSIENT_NETWORK_MARKERS)


def _retry_delay(attempt: int, *, base_sec: float = 5.0, max_sec: float = 60.0) -> float:
    return min(max_sec, base_sec * (2**attempt))


def _is_zhipu_overload_error(exc: BaseException) -> bool:
    message = str(exc)
    return "HTTP 429" in message and ("1305" in message or "overload" in message.lower())


def _post_json(url: str, payload: dict[str, Any], *, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Zhipu video create task failed: HTTP {exc.code} {body}") from exc


def _post_json_with_retry(
    url: str,
    payload: dict[str, Any],
    *,
    api_key: str,
    attempts: int = 4,
) -> dict[str, Any]:
    last_error: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            return _post_json(url, payload, api_key=api_key)
        except Exception as exc:
            if not (_is_zhipu_overload_error(exc) or _is_transient_network_error(exc)):
                raise
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt, base_sec=10.0, max_sec=90.0))
    raise RuntimeError(
        "Zhipu Qingying request failed after retries. "
        "This is usually a temporary network/TLS interruption or service overload; please retry later."
    ) from last_error


def _get_json(url: str, *, api_key: str) -> dict[str, Any]:
    request = urllib.request.Request(url, headers={"Authorization": f"Bearer {api_key}"}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Zhipu video query task failed: HTTP {exc.code} {body}") from exc


def _get_json_with_retry(
    url: str,
    *,
    api_key: str,
    attempts: int = 4,
) -> dict[str, Any]:
    last_error: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            return _get_json(url, api_key=api_key)
        except Exception as exc:
            if not (_is_zhipu_overload_error(exc) or _is_transient_network_error(exc)):
                raise
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt))
    raise RuntimeError("Zhipu Qingying task query failed after network retries.") from last_error


def _download_file(url: str, output_file: Path, *, attempts: int = 4) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "creator-automation/0.1"})
    output_file.parent.mkdir(parents=True, exist_ok=True)
    temp_file = output_file.with_name(f"{output_file.name}.part")
    last_error: BaseException | None = None
    for attempt in range(max(1, attempts)):
        try:
            temp_file.unlink(missing_ok=True)
            with urllib.request.urlopen(request, timeout=300) as response:
                with temp_file.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        handle.write(chunk)
            if not temp_file.exists() or temp_file.stat().st_size < 1024:
                raise RuntimeError("Downloaded Zhipu video is empty.")
            temp_file.replace(output_file)
            break
        except Exception as exc:
            temp_file.unlink(missing_ok=True)
            if not _is_transient_network_error(exc):
                raise
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(_retry_delay(attempt))
            else:
                raise RuntimeError("Zhipu Qingying video download failed after network retries.") from last_error
    if not output_file.exists() or output_file.stat().st_size < 1024:
        raise RuntimeError("Downloaded Zhipu video is empty.")


def _reference_image_value(request_payload: dict[str, Any]) -> str:
    reference_url = _string(request_payload.get("reference_image_url"))
    if reference_url.startswith(("http://", "https://")):
        return reference_url

    image_path = Path(_string(request_payload.get("reference_image")))
    if not image_path.exists() or not image_path.is_file():
        image_path = Path(_string(request_payload.get("character_reference_image")))
    if not image_path.exists() or not image_path.is_file():
        return ""
    if image_path.stat().st_size > 5 * 1024 * 1024:
        raise RuntimeError("Zhipu video reference image must be smaller than 5 MB.")
    return base64.b64encode(image_path.read_bytes()).decode("ascii")


def _build_prompt(request_payload: dict[str, Any], script_text: str) -> str:
    contract = dict(request_payload.get("reference_style_contract") or {})
    video_prompt = _string(contract.get("video_prompt"))
    image_prompt = _string(contract.get("image_prompt"))
    topic = _string(request_payload.get("topic"))
    learning_goal = _string(request_payload.get("learning_goal"))
    scene_index = _string(request_payload.get("scene_index"))
    scene_count = _string(request_payload.get("scene_count"))
    has_reference = bool(_string(request_payload.get("reference_image_url")) or _string(request_payload.get("reference_image")))
    storyboard = request_payload.get("animation_storyboard")
    shots: list[str] = []
    if isinstance(storyboard, list):
        for item in storyboard[:4]:
            if isinstance(item, dict):
                shot = _string(item.get("shot_type"))
                emotion = _string(item.get("emotion"))
                line = _string(item.get("line"))
                scene_prompt = _string(item.get("scene_prompt"))
                visual_cue = _string(item.get("visual_cue"))
                if line:
                    shots.append(f"{shot} {emotion}, visual cue: {visual_cue}, scene: {scene_prompt}, narration: {line}")
    identity_prompt = (
        f"Reference identity: {video_prompt}. "
        if has_reference
        else (
            "Create original characters from text, do not use any default image or base video. "
            "Original character design: a cute anthropomorphic glossy green edamame pod with visible plump beans, "
            "big sparkling eyes, rosy cheeks, tiny sneakers, flexible arms, warm smile; and a cute anthropomorphic "
            "golden peanut with shell grid texture, freckles, big sparkling eyes, rosy cheeks, tiny sneakers and expressive hands. "
        )
    )
    prompt = (
        "Generate a complete 3D animated short video for 3-year-old preschool children, vertical 9:16, bright colorful toy-poster style. "
        "Use only two main characters: anthropomorphic edamame and anthropomorphic peanut. "
        "No real humans, no extra characters, no scary scenes, no complex text on screen. "
        "Do not put any speaker labels, captions, watermarked labels, or text such as '花生:', '毛豆:', '合:', 'peanut:', or 'edamame:' inside the video image. "
        f"This is scene {scene_index or '1'} of {scene_count or '1'} in a multi-scene short; make it visually distinct but keep character identity consistent. "
        "The video must follow the narration content closely with clear actions, facial expressions, close-up emotion shots, "
        "gentle camera movement, happy warm preschool tone, vivid colors, and simple science learning. "
        "Use the storyboard scene descriptions as visual guidance only; never render them as subtitles or spoken labels. "
        "The edamame and peanut should act out the narration in first person; do not show or say speaker labels like 'edamame says' or 'peanut says'. "
        "Use the focused character's mouth movement and close-up framing to imply who is speaking. "
        f"{identity_prompt}"
        f"Detailed style guide: {image_prompt}. "
        f"Topic: {topic}. Learning goal: {learning_goal}. "
        f"Storyboard: {' | '.join(shots)}. "
        f"Narration to follow exactly: {script_text}"
    )
    return prompt[:1400]


def _pick_task_status(payload: dict[str, Any]) -> str:
    for key in ("task_status", "status", "state"):
        value = _string(payload.get(key)).upper()
        if value:
            return value
    return ""


def _pick_video_url(payload: dict[str, Any]) -> str:
    video_result = payload.get("video_result")
    if isinstance(video_result, list):
        for item in video_result:
            if isinstance(item, dict):
                url = _string(item.get("url"))
                if url.startswith(("http://", "https://")):
                    return url
    for key in ("video_url", "url", "result_url"):
        url = _string(payload.get(key))
        if url.startswith(("http://", "https://")):
            return url
    return ""


def create_zhipu_video_task(
    *,
    request_payload: dict[str, Any],
    script_text: str,
    duration: float,
) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("ZHIPUAI_API_KEY is required for Zhipu Qingying/CogVideoX video generation.")

    reference_image = _reference_image_value(request_payload)
    requested_duration = int(round(duration or request_payload.get("seconds") or 5))
    clip_duration = 10 if requested_duration >= 8 else 5
    size = str(request_payload.get("zhipu_video_size") or "1080x1920").strip() or "1080x1920"
    fps = int(request_payload.get("target_fps") or 30)
    fps = 60 if fps >= 60 else 30
    payload: dict[str, Any] = {
        "model": os.getenv("ZHIPU_VIDEO_MODEL", "cogvideox-3").strip() or "cogvideox-3",
        "prompt": _build_prompt(request_payload, script_text),
        "quality": os.getenv("ZHIPU_VIDEO_QUALITY", "speed").strip() or "speed",
        "with_audio": False,
        "watermark_enabled": os.getenv("ZHIPU_VIDEO_WATERMARK", "true").strip().lower()
        not in {"0", "false", "no", "off"},
        "size": size,
        "fps": fps,
        "duration": clip_duration,
    }
    if reference_image:
        payload["image_url"] = reference_image

    endpoint = os.getenv("ZHIPU_VIDEO_ENDPOINT", CREATE_ENDPOINT).strip() or CREATE_ENDPOINT
    response = _post_json_with_retry(endpoint, payload, api_key=api_key)
    task_id = _string(response.get("id"))
    if not task_id:
        raise RuntimeError(f"Zhipu video API did not return task id: {json.dumps(response, ensure_ascii=False)}")
    request_for_log = dict(payload)
    if len(str(request_for_log.get("image_url", ""))) > 200:
        request_for_log["image_url"] = "<base64_or_url_reference_image>"
    return {
        "task_id": task_id,
        "request": request_for_log,
        "response": response,
    }


def wait_for_zhipu_video(
    *,
    task_id: str,
    output_file: Path,
    poll_interval_sec: int = 15,
    timeout_sec: int = 900,
) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("ZHIPUAI_API_KEY is required for Zhipu Qingying/CogVideoX video generation.")
    endpoint_template = os.getenv("ZHIPU_VIDEO_TASK_ENDPOINT", TASK_ENDPOINT).strip() or TASK_ENDPOINT
    deadline = time.time() + max(timeout_sec, 60)
    last_payload: dict[str, Any] = {}
    while time.time() < deadline:
        payload = _get_json_with_retry(endpoint_template.format(task_id=task_id), api_key=api_key)
        last_payload = payload
        status = _pick_task_status(payload)
        if status == "SUCCESS":
            video_url = _pick_video_url(payload)
            if not video_url:
                raise RuntimeError(f"Zhipu video task succeeded but no video URL returned: {json.dumps(payload, ensure_ascii=False)}")
            _download_file(video_url, output_file)
            return {
                "task_id": task_id,
                "task_status": status,
                "video_url": video_url,
                "response": payload,
            }
        if status in {"FAIL", "FAILED"}:
            raise RuntimeError(f"Zhipu video task {status}: {json.dumps(payload, ensure_ascii=False)}")
        time.sleep(max(5, poll_interval_sec))
    raise RuntimeError(f"Zhipu video task timed out: {json.dumps(last_payload, ensure_ascii=False)}")
