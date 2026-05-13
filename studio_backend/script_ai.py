from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

from .kids_mode import normalize_kids_script_text


ZHIPU_CHAT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"


def _string(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _api_key() -> str:
    return (
        os.getenv("SCRIPT_AI_API_KEY", "").strip()
        or os.getenv("ZHIPUAI_API_KEY", "").strip()
        or os.getenv("BIGMODEL_API_KEY", "").strip()
        or os.getenv("GLM_API_KEY", "").strip()
    )


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
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Third-party script AI failed: HTTP {exc.code} {body}") from exc


def _extract_chat_content(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                return _string(message.get("content"))
            return _string(first.get("text"))
    return ""


def _topic_terms(topic: str, learning_goal: str) -> list[str]:
    text = f"{topic} {learning_goal}"
    candidates = [
        "种子",
        "发芽",
        "小芽",
        "水",
        "阳光",
        "叶子",
        "颜色",
        "形状",
        "数字",
        "分类",
        "观察",
    ]
    terms = [term for term in candidates if term in text]
    compact = "".join(ch for ch in text if "\u4e00" <= ch <= "\u9fff")
    for size in (4, 3, 2):
        for index in range(0, max(0, len(compact) - size + 1)):
            term = compact[index : index + size]
            if term and term not in terms:
                terms.append(term)
        if len(terms) >= 3:
            break
    return terms[:8]


def _script_matches_topic(script: str, terms: list[str]) -> bool:
    if not terms:
        return True
    compact = "".join(ch for ch in script if "\u4e00" <= ch <= "\u9fff")
    hits = sum(1 for term in terms if term and term in compact)
    return hits >= max(1, min(2, len(terms)))


def _request_zhipu_script(
    *,
    api_key: str,
    endpoint: str,
    model: str,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
    correction: str = "",
) -> tuple[str, dict[str, Any]]:
    mode_label = "科普动画" if content_mode == "science" else "益智早教动画"
    target_lines = 6 if seconds <= 35 else 9 if seconds <= 45 else 12
    system_prompt = (
        "你是3-6岁儿童科普动画和益智早教动画编剧。"
        "只输出最终中文旁白文案，不要标题，不要解释，不要分镜，不要括号场景说明。"
        "文案必须第一人称，用“我/我们”自然带小朋友观察、数数、寻找和复习。"
        "不要写“毛豆：”“花生：”“合：”“旁白：”等说话标签。"
        "每句短、清楚、有节奏，适合轻快儿童配音。"
        "必须严格围绕用户给定主题，不得改写成其他主题。"
    )
    user_prompt = (
        f"内容类型：{mode_label}\n"
        f"唯一主题：{topic}\n"
        f"学习目标：{learning_goal}\n"
        f"互动提示：{prompt_hint}\n"
        f"目标时长：{seconds}秒以内\n"
        f"请写{target_lines}句左右，每句单独换行。"
        "要求：每一句都要服务这个唯一主题；只讲一个知识点；每10秒左右有一次互动；最后一句复习并鼓励；"
        "不得出现角色标签、镜头说明、场景说明、字幕说明。"
    )
    if correction:
        user_prompt += f"\n上一次问题：{correction}\n请重写，必须包含主题关键词。"
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(os.getenv("SCRIPT_AI_TEMPERATURE", "0.55") or "0.55"),
        "top_p": float(os.getenv("SCRIPT_AI_TOP_P", "0.85") or "0.85"),
        "max_tokens": int(os.getenv("SCRIPT_AI_MAX_TOKENS", "700") or "700"),
    }
    response = _post_json(endpoint, request_payload, api_key=api_key)
    return normalize_kids_script_text(_extract_chat_content(response)), response


def generate_kids_script_with_zhipu(
    *,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
) -> dict[str, Any]:
    api_key = _api_key()
    if not api_key:
        raise RuntimeError("SCRIPT_AI_API_KEY or ZHIPUAI_API_KEY is required for third-party AI script generation.")

    model = os.getenv("SCRIPT_AI_MODEL", "glm-4-flash").strip() or "glm-4-flash"
    endpoint = os.getenv("SCRIPT_AI_ENDPOINT", ZHIPU_CHAT_ENDPOINT).strip() or ZHIPU_CHAT_ENDPOINT
    terms = _topic_terms(topic, learning_goal)
    script, response = _request_zhipu_script(
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        topic=topic,
        seconds=seconds,
        prompt_hint=prompt_hint,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    if script and not _script_matches_topic(script, terms):
        script, response = _request_zhipu_script(
            api_key=api_key,
            endpoint=endpoint,
            model=model,
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
            correction=f"文案跑题，没有围绕“{topic} / {learning_goal}”。",
        )
    if not script:
        raise RuntimeError(f"Third-party script AI returned empty content: {json.dumps(response, ensure_ascii=False)[:500]}")
    if not _script_matches_topic(script, terms):
        raise RuntimeError(f"Third-party script AI returned off-topic content for topic: {topic}")
    return {
        "script": script,
        "provider": "zhipu",
        "model": model,
        "endpoint": endpoint,
    }


def generate_kids_script_with_ai(
    *,
    provider: str,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
) -> dict[str, Any]:
    normalized_provider = _string(provider).lower() or os.getenv("SCRIPT_AI_PROVIDER", "zhipu").strip().lower()
    if normalized_provider in {"zhipu", "bigmodel", "glm", "zhipu_ai", "third_party"}:
        return generate_kids_script_with_zhipu(
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
        )
    raise RuntimeError(f"Unsupported script AI provider: {provider}")
