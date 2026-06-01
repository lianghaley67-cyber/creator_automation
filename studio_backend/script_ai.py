from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from .kids_mode import normalize_kids_script_text


ZHIPU_CHAT_ENDPOINT = "https://open.bigmodel.cn/api/paas/v4/chat/completions"
MINIMAX_CHAT_ENDPOINT = "https://api.minimax.io/v1/chat/completions"
DEEPSEEK_CHAT_ENDPOINT = "https://api.deepseek.com/chat/completions"
GEMINI_GENERATE_ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
ROOT_DIR = Path(__file__).resolve().parents[1]


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


def _env_key(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _post_json(url: str, payload: dict[str, Any], *, api_key: str, auth_scheme: str = "Bearer") -> dict[str, Any]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"{auth_scheme} {api_key}".strip()
    request = urllib.request.Request(
        url,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers=headers,
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


def _extract_gemini_content(payload: dict[str, Any]) -> str:
    candidates = payload.get("candidates")
    if isinstance(candidates, list) and candidates:
        content = candidates[0].get("content") if isinstance(candidates[0], dict) else {}
        parts = content.get("parts") if isinstance(content, dict) else []
        if isinstance(parts, list):
            return "\n".join(_string(part.get("text")) for part in parts if isinstance(part, dict)).strip()
    return ""


def _strip_model_reasoning(text: str) -> str:
    value = _string(text)
    if not value:
        return ""
    value = re.sub(r"<think>.*?</think>", "", value, flags=re.IGNORECASE | re.DOTALL).strip()
    if re.match(r"^\s*<think>", value, flags=re.IGNORECASE):
        markers = [
            r"修复后的终稿\s*[:：]",
            r"最终文案\s*[:：]",
            r"口播文案\s*[:：]",
            r"终稿\s*[:：]",
        ]
        for marker in markers:
            parts = re.split(marker, value, maxsplit=1, flags=re.IGNORECASE)
            if len(parts) == 2 and parts[1].strip():
                value = parts[1].strip()
                break
        else:
            lines = [line.strip() for line in value.splitlines() if line.strip()]
            hook_index = 0
            hook_tokens = ("如果", "今天", "凌晨", "我", "谁说", "这", "别", "真的")
            for index, line in enumerate(lines):
                if line.startswith(hook_tokens) and not line.startswith(("问题", "用户", "审核", "要求")):
                    hook_index = index
                    break
            value = "\n".join(lines[hook_index:]).strip()
    value = re.sub(r"^\s*(?:修复后的终稿|最终文案|口播文案|终稿)\s*[:：]\s*", "", value)
    return value.strip()


def _mode_label(content_mode: str) -> str:
    mode_labels = {
        "working_mom": "职场妈妈痛点解决",
        "creator_tips": "短视频/剪辑提效",
        "ai_growth": "AI 学习与职业重塑",
    }
    return mode_labels.get(content_mode, "职场妈妈痛点解决")


def _target_lines(seconds: int) -> int:
    return 6 if seconds <= 35 else 9 if seconds <= 45 else 12


def _load_creator_skills() -> str:
    blocks: list[str] = []
    raw_dirs = [
        os.getenv("CREATOR_SKILLS_DIR", "creator_skills").strip() or "creator_skills",
        os.getenv("OBSIDIAN_SKILLS_DIR", "").strip(),
        "D:/obsMD/Obsidian/vault/CreatorStudioSkills",
        "~/obsidian/CreatorStudioSkills",
    ]
    seen_dirs: set[Path] = set()
    for raw_dir in raw_dirs:
        if not raw_dir:
            continue
        skills_dir = Path(raw_dir).expanduser()
        if not skills_dir.is_absolute():
            skills_dir = ROOT_DIR / skills_dir
        try:
            resolved = skills_dir.resolve()
        except OSError:
            resolved = skills_dir
        if resolved in seen_dirs or not skills_dir.exists():
            continue
        seen_dirs.add(resolved)
        for path in sorted(skills_dir.glob("*.md")):
            try:
                text = path.read_text(encoding="utf-8", errors="replace").strip()
            except OSError:
                continue
            if text:
                blocks.append(f"## {path.stem}\n{text}")
    return "\n\n".join(blocks)[:12000]


def _creator_system_prompt(*, output_mode: str = "draft") -> str:
    suffix = ""
    if output_mode == "revision":
        suffix = "你正在做终稿修复，必须逐条吸收审核意见，保留爆点，删除废话，输出可直接配音的最终文案。"
    custom_skills = _load_creator_skills()
    skills_block = ""
    if custom_skills:
        skills_block = (
            "\n\n以下是用户长期维护的 Creator Skills。它们优先级高于普通表达偏好，"
            "但不得覆盖安全、合规、事实准确和用户本次主题：\n"
            f"{custom_skills}\n"
        )
    return (
        "你是高认知、强共情、有温度的职场妈妈/AI 科技女性 IP 编剧。"
        "只输出最终中文口播文案，不要标题，不要解释，不要分镜，不要括号场景说明。"
        "文案必须第一人称，用“我/我们”自然讲真实经历、情绪共鸣、AI 提效方法和评论区互动。"
        "不要写“毛豆：”“花生：”“合：”“旁白：”等说话标签。"
        "拒绝爹味说教，不准说“你应该”，要说“我当时也崩溃了，直到我发现...”。"
        "语气要口语化、犀利但温暖，允许高级幽默和轻微调侃。"
        "严禁输出思考过程、分析过程、审核过程、<think>标签或项目符号说明。"
        "必须严格围绕用户给定主题，不得改写成其他主题。"
        f"{skills_block}"
        f"{suffix}"
    )


def _creator_user_prompt(
    *,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
    correction: str = "",
) -> str:
    prompt = (
        f"内容类型：{_mode_label(content_mode)}\n"
        f"唯一主题：{topic}\n"
        f"内容目标：{learning_goal}\n"
        f"补充提示：{prompt_hint}\n"
        f"目标时长：{seconds}秒以内\n"
        f"请写{_target_lines(seconds)}句左右，每句单独换行。"
        "要求：开头3秒必须痛点暴击或反常识；中段至少给出一个可落地方法；"
        "每15-20秒有一个金句或情绪高潮；结尾必须引导评论区分享经历或站队；"
        "不得出现角色标签、镜头说明、场景说明、字幕说明。"
    )
    if correction:
        prompt += f"\n必须修复以下问题：\n{correction}"
    return prompt


def _openai_compatible_chat(
    *,
    api_key: str,
    endpoint: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    max_tokens: int | None = None,
    temperature: float | None = None,
) -> tuple[str, dict[str, Any]]:
    request_payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": temperature if temperature is not None else float(os.getenv("SCRIPT_AI_TEMPERATURE", "0.55") or "0.55"),
        "top_p": float(os.getenv("SCRIPT_AI_TOP_P", "0.85") or "0.85"),
        "max_tokens": max_tokens if max_tokens is not None else int(os.getenv("SCRIPT_AI_MAX_TOKENS", "900") or "900"),
    }
    response = _post_json(endpoint, request_payload, api_key=api_key)
    return _extract_chat_content(response), response


def _gemini_generate(
    *,
    api_key: str,
    endpoint: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
) -> tuple[str, dict[str, Any]]:
    url = endpoint.format(model=model)
    separator = "&" if "?" in url else "?"
    url = f"{url}{separator}key={api_key}"
    request_payload = {
        "systemInstruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"role": "user", "parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": float(os.getenv("GEMINI_TEMPERATURE", os.getenv("SCRIPT_AI_TEMPERATURE", "0.55")) or "0.55"),
            "topP": float(os.getenv("GEMINI_TOP_P", os.getenv("SCRIPT_AI_TOP_P", "0.85")) or "0.85"),
            "maxOutputTokens": int(os.getenv("GEMINI_MAX_TOKENS", os.getenv("SCRIPT_AI_MAX_TOKENS", "900")) or "900"),
        },
    }
    response = _post_json(url, request_payload, api_key="")
    return _extract_gemini_content(response), response


def _minimax_chat(system_prompt: str, user_prompt: str, *, output_mode: str = "draft") -> tuple[str, dict[str, Any]]:
    api_key = _env_key("MINIMAX_API_KEY", "MINIMAX_TOKEN")
    if not api_key:
        raise RuntimeError("MINIMAX_API_KEY is required for MiniMax script generation/revision.")
    endpoint = os.getenv("MINIMAX_CHAT_ENDPOINT", MINIMAX_CHAT_ENDPOINT).strip() or MINIMAX_CHAT_ENDPOINT
    model = os.getenv("MINIMAX_MODEL", "MiniMax-M2.1").strip() or "MiniMax-M2.1"
    max_tokens = int(os.getenv("MINIMAX_MAX_TOKENS", os.getenv("SCRIPT_AI_MAX_TOKENS", "1000")) or "1000")
    text, response = _openai_compatible_chat(
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=max_tokens,
    )
    if not _string(text):
        raise RuntimeError(f"MiniMax returned empty content in {output_mode}: {json.dumps(response, ensure_ascii=False)[:500]}")
    return text, response


def _gemini_chat(system_prompt: str, user_prompt: str) -> tuple[str, dict[str, Any]]:
    api_key = _env_key("GEMINI_API_KEY", "GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY is required for Gemini draft generation.")
    model = os.getenv("GEMINI_MODEL", "gemini-2.5-flash").strip() or "gemini-2.5-flash"
    endpoint = os.getenv("GEMINI_ENDPOINT", GEMINI_GENERATE_ENDPOINT).strip() or GEMINI_GENERATE_ENDPOINT
    text, response = _gemini_generate(
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
    )
    if not _string(text):
        raise RuntimeError(f"Gemini returned empty draft: {json.dumps(response, ensure_ascii=False)[:500]}")
    return text, response


def _deepseek_review(script: str, *, topic: str, content_mode: str, learning_goal: str) -> dict[str, Any]:
    api_key = _env_key("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required for DeepSeek review.")
    endpoint = os.getenv("DEEPSEEK_CHAT_ENDPOINT", DEEPSEEK_CHAT_ENDPOINT).strip() or DEEPSEEK_CHAT_ENDPOINT
    if endpoint.rstrip("/") in {"https://api.deepseek.com", "https://api.deepseek.com/v1"}:
        endpoint = f"{endpoint.rstrip('/')}/chat/completions"
    model = os.getenv("DEEPSEEK_MODEL", "deepseek-chat").strip() or "deepseek-chat"
    system_prompt = (
        "你是苛刻但靠谱的短视频总编和合规审核。"
        "只输出 JSON，不要 Markdown。"
        "检查文案是否符合职场妈妈/AI 科技女性 IP，是否有爹味说教、AI腔、跑题、逻辑断裂、缺少钩子、缺少方法、缺少互动、表达风险。"
    )
    user_prompt = (
        f"主题：{topic}\n"
        f"内容类型：{_mode_label(content_mode)}\n"
        f"内容目标：{learning_goal}\n"
        f"待审核文案：\n{script}\n\n"
        "请输出 JSON，字段包含：score(0-100), passed(boolean), issues(array), fix_instructions(array), strongest_line, weakest_line。"
    )
    text, raw = _openai_compatible_chat(
        api_key=api_key,
        endpoint=endpoint,
        model=model,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        max_tokens=int(os.getenv("DEEPSEEK_MAX_TOKENS", "900") or "900"),
        temperature=float(os.getenv("DEEPSEEK_TEMPERATURE", "0.25") or "0.25"),
    )
    try:
        cleaned = re.sub(r"^```(?:json)?|```$", "", _string(text), flags=re.MULTILINE).strip()
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            parsed["_raw_text"] = text
            parsed["_provider"] = "deepseek"
            parsed["_model"] = model
            return parsed
    except Exception:
        pass
    return {
        "score": 0,
        "passed": False,
        "issues": ["DeepSeek did not return parseable JSON."],
        "fix_instructions": [_string(text) or "请重新检查逻辑、钩子、方法和互动。"],
        "_raw_text": text,
        "_raw_response": raw,
        "_provider": "deepseek",
        "_model": model,
    }


def _topic_terms(topic: str, learning_goal: str) -> list[str]:
    text = f"{topic} {learning_goal}"
    candidates = [
        "职场",
        "妈妈",
        "AI",
        "剪辑",
        "视频",
        "提效",
        "焦虑",
        "老板",
        "送娃",
        "迟到",
        "工作流",
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
    system_prompt = _creator_system_prompt()
    user_prompt = _creator_user_prompt(
        topic=topic,
        seconds=seconds,
        prompt_hint=prompt_hint,
        content_mode=content_mode,
        learning_goal=learning_goal,
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


def generate_script_with_review_pipeline(
    *,
    draft_provider: str,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
) -> dict[str, Any]:
    terms = _topic_terms(topic, learning_goal)
    system_prompt = _creator_system_prompt()
    user_prompt = _creator_user_prompt(
        topic=topic,
        seconds=seconds,
        prompt_hint=prompt_hint,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    normalized_provider = _string(draft_provider).lower()
    if normalized_provider in {"gemini", "gemini_minimax", "gemini_deepseek_minimax"}:
        draft_text, draft_response = _gemini_chat(system_prompt, user_prompt)
        draft_source = "gemini"
    elif normalized_provider in {"minimax", "minimax_plan", "minimax_token_plan", "minimax_deepseek"}:
        draft_text, draft_response = _minimax_chat(system_prompt, user_prompt)
        draft_source = "minimax"
    else:
        raise RuntimeError(f"Unsupported reviewed draft provider: {draft_provider}")

    draft_script = normalize_kids_script_text(_strip_model_reasoning(draft_text))
    if not draft_script:
        raise RuntimeError(f"{draft_source} returned empty draft.")

    review = _deepseek_review(
        draft_script,
        topic=topic,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    correction = json.dumps(
        {
            "score": review.get("score"),
            "issues": review.get("issues", []),
            "fix_instructions": review.get("fix_instructions", []),
            "weakest_line": review.get("weakest_line", ""),
        },
        ensure_ascii=False,
    )
    revision_prompt = (
        _creator_user_prompt(
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
            correction=correction,
        )
        + f"\n\n初稿如下：\n{draft_script}\n\n请只输出修复后的终稿。"
    )
    revision_system_prompt = _creator_system_prompt(output_mode="revision")
    if draft_source == "gemini":
        revised_text, revised_response = _gemini_chat(revision_system_prompt, revision_prompt)
        revision_provider = "gemini"
    else:
        revised_text, revised_response = _minimax_chat(
            revision_system_prompt,
            revision_prompt,
            output_mode="revision",
        )
        revision_provider = "minimax"
    final_script = normalize_kids_script_text(_strip_model_reasoning(revised_text))
    if final_script and not _script_matches_topic(final_script, terms):
        correction_prompt = revision_prompt + f"\n\n额外强制：终稿跑题了，必须围绕“{topic} / {learning_goal}”。"
        if draft_source == "gemini":
            revised_text, revised_response = _gemini_chat(revision_system_prompt, correction_prompt)
        else:
            revised_text, revised_response = _minimax_chat(
                revision_system_prompt,
                correction_prompt,
                output_mode="topic_correction",
            )
        final_script = normalize_kids_script_text(_strip_model_reasoning(revised_text))
    if not final_script:
        raise RuntimeError(f"{revision_provider} revision returned empty final script.")
    if not _script_matches_topic(final_script, terms):
        raise RuntimeError(f"{revision_provider} revision returned off-topic content for topic: {topic}")
    final_review = _deepseek_review(
        final_script,
        topic=topic,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    return {
        "script": final_script,
        "provider": f"{draft_source}_deepseek_{revision_provider}_deepseek",
        "draft_provider": draft_source,
        "review_provider": "deepseek",
        "revision_provider": revision_provider,
        "final_review_provider": "deepseek",
        "draft_script": draft_script,
        "review": review,
        "final_review": final_review,
        "draft_raw_response": draft_response,
        "revision_raw_response": revised_response,
    }


def generate_reviewed_draft(
    *,
    draft_provider: str,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
) -> dict[str, Any]:
    system_prompt = _creator_system_prompt()
    user_prompt = _creator_user_prompt(
        topic=topic,
        seconds=seconds,
        prompt_hint=prompt_hint,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    normalized_provider = _string(draft_provider).lower()
    if normalized_provider in {"gemini", "gemini_minimax", "gemini_deepseek_minimax"}:
        draft_text, draft_response = _gemini_chat(system_prompt, user_prompt)
        draft_source = "gemini"
    elif normalized_provider in {"minimax", "minimax_plan", "minimax_token_plan", "minimax_deepseek"}:
        draft_text, draft_response = _minimax_chat(system_prompt, user_prompt)
        draft_source = "minimax"
    else:
        raise RuntimeError(f"Unsupported reviewed draft provider: {draft_provider}")
    draft_script = normalize_kids_script_text(_strip_model_reasoning(draft_text))
    if not draft_script:
        raise RuntimeError(f"{draft_source} returned empty draft.")
    review = _deepseek_review(
        draft_script,
        topic=topic,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    return {
        "script": draft_script,
        "provider": f"{draft_source}_deepseek_draft",
        "draft_provider": draft_source,
        "review_provider": "deepseek",
        "review": review,
        "draft_raw_response": draft_response,
    }


def revise_script_with_feedback(
    *,
    revision_provider: str,
    draft_script: str,
    review: dict[str, Any] | str,
    human_feedback: str,
    topic: str,
    seconds: int,
    prompt_hint: str,
    content_mode: str,
    learning_goal: str,
) -> dict[str, Any]:
    terms = _topic_terms(topic, learning_goal)
    provider = _string(revision_provider).lower()
    if provider in {"gemini_minimax", "gemini_deepseek_minimax"}:
        provider = "gemini"
    if provider in {"minimax_plan", "minimax_token_plan", "minimax_deepseek"}:
        provider = "minimax"
    review_text = review if isinstance(review, str) else json.dumps(review or {}, ensure_ascii=False)
    correction = json.dumps(
        {
            "deepseek_review": review_text,
            "human_feedback": human_feedback,
        },
        ensure_ascii=False,
    )
    revision_prompt = (
        _creator_user_prompt(
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
            correction=correction,
        )
        + f"\n\n初稿如下：\n{draft_script}\n\n请只输出修复后的终稿。"
    )
    system_prompt = _creator_system_prompt(output_mode="revision")
    if provider == "gemini":
        revised_text, revised_response = _gemini_chat(system_prompt, revision_prompt)
    elif provider == "minimax":
        revised_text, revised_response = _minimax_chat(system_prompt, revision_prompt, output_mode="manual_revision")
    else:
        raise RuntimeError(f"Unsupported revision provider: {revision_provider}")
    final_script = normalize_kids_script_text(_strip_model_reasoning(revised_text))
    if not final_script:
        raise RuntimeError(f"{provider} revision returned empty final script.")
    if not _script_matches_topic(final_script, terms):
        raise RuntimeError(f"{provider} revision returned off-topic content for topic: {topic}")
    final_review = _deepseek_review(
        final_script,
        topic=topic,
        content_mode=content_mode,
        learning_goal=learning_goal,
    )
    return {
        "script": final_script,
        "provider": f"{provider}_manual_feedback_deepseek",
        "revision_provider": provider,
        "final_review_provider": "deepseek",
        "final_review": final_review,
        "revision_raw_response": revised_response,
    }


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
    if normalized_provider in {"gemini", "gemini_minimax", "gemini_deepseek_minimax"}:
        return generate_script_with_review_pipeline(
            draft_provider="gemini",
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
        )
    if normalized_provider in {"minimax", "minimax_plan", "minimax_token_plan", "minimax_deepseek"}:
        return generate_script_with_review_pipeline(
            draft_provider="minimax",
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
        )
    if normalized_provider in {"zhipu", "bigmodel", "glm", "zhipu_ai", "third_party"}:
        return generate_kids_script_with_zhipu(
            topic=topic,
            seconds=seconds,
            prompt_hint=prompt_hint,
            content_mode=content_mode,
            learning_goal=learning_goal,
        )
    raise RuntimeError(f"Unsupported script AI provider: {provider}")
