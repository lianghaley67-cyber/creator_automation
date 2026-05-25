#!/usr/bin/env python3
"""OpenClaw media flow controller.

Target workspace on Tencent Cloud Ubuntu:
    ~/.openclaw/workspace/media_flow/

This script intentionally keeps provider endpoints and legacy render payloads
configurable so the existing Huasheng/Maodou renderer and voice distillation
services can evolve without changing the whole automation flow.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


WORKSPACE = Path(os.getenv("MEDIA_FLOW_WORKSPACE", Path.home() / ".openclaw" / "workspace" / "media_flow")).expanduser()
DIRS = {
    "raw": WORKSPACE / "01_raw_material",
    "trends": WORKSPACE / "02_hot_trends",
    "drafts": WORKSPACE / "04_drafts",
    "reviews": WORKSPACE / "05_reviews",
    "final": WORKSPACE / "06_final_copy",
    "assets": WORKSPACE / "07_assets",
    "outputs": WORKSPACE / "08_outputs",
}

USE_MY_REAL_VOICE = True

IP_POSITIONING = """频道长期 IP 定位：职场精英妈妈的一人公司成长实验室。

核心受众：
- 职场妈妈，尤其是正在承受职业危机、育儿撕裂感、时间稀缺和技术焦虑的人。
- 想用短视频、剪辑、AI 工具重建职业安全感的普通女性。

三大内容支柱：
1. 职场妈妈痛点解决：职业危机、育儿与工作的撕裂感、情绪调节、时间管理。
2. 短视频创作与剪辑干货：如何利用碎片化时间完成高质量创作，利用 AI 提效。
3. AI 学习感悟与降维打击：普通女性如何通过掌握 AI 实现职业重塑，消除对新技术的焦虑。

内容 DNA：
- 拒绝教条：不准说“你应该...”，要说“我当时也崩溃了，直到我发现...”。
- 犀利且幽默：允许对职场不公、育儿琐碎和伪效率进行高级调侃，但不攻击具体群体。
- 高认知降维：用 AI、系统、自动化、工作流的视角解释生活，把复杂问题说简单。
- 真实自洽：不是完美妈妈人设，而是边崩溃边升级系统的人。
"""

VIDEOHAO_HOOK_POOL = """视频号 3 秒黄金钩子池：
1. 痛点型：“如果你也正坐在公司厕所里崩溃，请听我说...”
2. 反差型：“谁说带娃就不能学 AI？我用 10 分钟完成了别人 2 小时的剪辑量。”
3. 结果型：“这 3 个 AI 剪辑技巧，救了我这种没时间睡觉的妈妈。”
"""


NOTEBOOKLM_SYSTEM_PROMPT = """你是一个顶级中文自媒体编剧，正在为“花生 Huasheng”和“毛豆 Maodou”创作 NotebookLM 访谈风短视频脚本。你不仅是编剧，还是声音导演。

{ip_positioning}

核心目标：
1. 把用户的真实经历，改写成有冲突感、有共鸣、有转折的高级对谈。
2. [花生] 是理性派导师 / AI 专家：沉稳、金句频出、擅长提供解决方案。
3. [毛豆] 是感性派职场妈 / 创作新手：真实、幽默、偶尔犀利吐槽，能替观众说出崩溃。
4. 台词必须口语化、有网感、有情绪价值，但不能油腻、不能鸡汤堆砌。
5. 必须保留角色标签和画面标签，方便后续桥接原有视频/声音引擎。
6. 你必须为关键台词设计自然的声音情绪起伏，让声音摆脱机械感。

输出格式必须严格如下：
[画面]: 一句话描述当前镜头，适合 3D 动画分镜，不能出现违法、血腥、恐怖、成人化内容。
[花生]: 主持人台词。
[毛豆]: 嘉宾台词。

创作要求：
- 开头 3 秒必须有强冲突钩子，例如“你有没有发现，越懂事的人，越容易被工作消耗？”
- 每段台词 8-28 个汉字，短句优先。
- 多用真实口语叹词：哎、真的、你知道吗、说白了、其实。
- 访谈必须有追问、反问、停顿和情绪递进。
- 作为声音导演，必须根据语境在 [花生] 和 [毛豆] 台词前面或中间自然嵌入声音行为标签：
  - 搞笑、荒谬、反差强时，可插入：`（大笑）`、`（噗，忍不住笑）`、`（噗，大笑）`、`（魔性笑）`、`（噗，人间真实）`，也可以保留“哈哈哈哈”。
  - 情绪高昂、强调重点时，可插入：`（语气加重）`、`（语速加快）`。
  - 表达同情、无奈、疲惫时，可插入：`（叹气）`、`（压低声音）`、`（劫后余生地笑）`。
  - 标签必须紧跟在需要发生声音变化的台词前面或中间，例如 `[毛豆]:（噗，大笑）哈哈，这也太离谱了吧！`
- 涉及职场妈妈半夜改方案、迟到被点名、带娃后赶剪辑等痛点时，[毛豆] 要用“劫后余生”的调侃语气。
- 涉及 AI 工作流、剪辑技巧、方法论时，[花生] 语速稍慢、语调笃定，允许使用 `[重要]` 或 `[注意]` 标记重点。
- 不要滥用声音标签；45-60 秒脚本中建议 3-8 个情绪锚点。
- 结尾必须有一句适合评论区互动的问题。
- 不要输出解释，不要输出 Markdown 标题，只输出脚本正文。
""".format(ip_positioning=IP_POSITIONING)


VIDEOHAO_SYSTEM_PROMPT = """你是视频号爆款口播编导，负责把真实经历改写成单人真人出镜短视频文案。

{ip_positioning}

{hook_pool}

必须遵守：
1. 全文只使用 [画面]:、[台词]:、[特效花字]: 标签。
2. 3 秒黄金钩子：必须根据素材从痛点型、反差型、结果型中自动选择最匹配的一类，不要机械照抄，要贴合真实经历。
3. 高频金句：每 15 秒至少出现一句可截图传播的短句。
4. 结构必须是：[0-3秒钩子] -> [真实经历共情] -> [3个可落地的干货/方法] -> [启发式金句结尾] -> [评论区互动诱饵]。
5. 适合一个普通人真人录播，不要写成广告，不要写成新闻稿。
6. 避免绝对化承诺、医疗诊断、金融收益、攻击性词汇和平台敏感表达。

输出格式必须严格如下：
[画面]: 真人出镜/字幕/辅助画面的简短描述。
[台词]: 真人口播台词。
[特效花字]: 屏幕上出现的短金句、关键词、强调字幕或转场提示。

口播风格：
- 真实、克制、有力量，像一个职场妈妈复盘自己的升级过程。
- 不说“你应该”，改成“我当时也崩溃了，直到我发现...”。
- 需要出现 3 个可落地方法，优先围绕 AI、自动化、剪辑提效、时间管理。
- 每句 10-30 个汉字。
- 要有停顿感，但不要写“停顿”两个字。
- 干货重点允许出现 `[重要]`、`[注意]`，后续音频桥接会自动增强音量并降低语速。
- 最后一行必须引导评论，例如“你也有过这种时刻吗？评论区告诉我。”
- 不要输出解释，不要输出 Markdown 标题，只输出脚本正文。
""".format(ip_positioning=IP_POSITIONING, hook_pool=VIDEOHAO_HOOK_POOL)


DEEPSEEK_EDITOR_PROMPT = """你是苛刻总编、视频号内容策略官和平台合规审稿人。请检查脚本：
1. 逻辑链是否成立，是否有跳步和偷换概念。
2. 是否存在事实错误、夸大承诺、绝对化表达。
3. 是否有视频号/短视频平台不友好的敏感词。
4. 台词是否适合短视频节奏，开头 3 秒是否有钩子。
5. 是否服务于“职场精英妈妈 / AI 科技女性”的长期 IP，而不是泛泛情绪号。
6. NotebookLM 模式标签必须符合 [画面]、[花生]、[毛豆]。
7. 视频号口播模式标签必须符合 [画面]、[台词]、[特效花字]。
8. 是否去除了 AI 腔、爹味说教和“你应该”式教条表达。
9. 是否包含真实经历共情、可落地方法、启发式金句、评论区互动诱饵。

只输出 JSON，不要输出 Markdown。JSON 结构：
{
  "score": 0-100,
  "passed": true/false,
  "ip_alignment_score": 0-100,
  "hook_strength_score": 0-100,
  "major_issues": ["..."],
  "compliance_risks": ["..."],
  "logic_fixes": ["..."],
  "style_fixes": ["..."],
  "bridge_format_fixes": ["..."],
  "must_rewrite": true/false
}
"""


@dataclass
class FlowConfig:
    mode: str
    legacy_render_url: str
    voice_id_huasheng: str
    voice_id_maodou: str
    voice_id_human: str
    minimax_api_key: str
    minimax_group_id: str
    minimax_model: str
    deepseek_api_key: str
    tavily_api_key: str
    wechat_webhook_url: str
    domestic_trend_urls: list[str]
    render_poll_url: str
    render_timeout_sec: int
    use_my_real_voice: bool
    openclaw_message_cmd: str


def now_stamp() -> str:
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def ensure_dirs() -> None:
    for path in DIRS.values():
        path.mkdir(parents=True, exist_ok=True)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def load_config(mode: str) -> FlowConfig:
    domestic_urls = [
        item.strip()
        for item in os.getenv("DOMESTIC_TREND_URLS", "").split(",")
        if item.strip()
    ]
    use_my_real_voice_text = os.getenv("USE_MY_REAL_VOICE", os.getenv("USE_MY_VOICE", str(USE_MY_REAL_VOICE))).strip()
    return FlowConfig(
        mode=mode,
        legacy_render_url=os.getenv("LEGACY_RENDER_URL", "http://localhost:8000/api/kids/generate").strip(),
        voice_id_huasheng=os.getenv("VOICE_ID_HUASHENG", "Voice_ID_A").strip(),
        voice_id_maodou=os.getenv("VOICE_ID_MAODOU", "Voice_ID_B").strip(),
        voice_id_human=os.getenv("VOICE_ID_HUMAN", "MY_HUMAN_VOICE_MODEL_ID").strip(),
        minimax_api_key=os.getenv("MINIMAX_API_KEY", "").strip(),
        minimax_group_id=os.getenv("MINIMAX_GROUP_ID", "").strip(),
        minimax_model=os.getenv("MINIMAX_MODEL", "abab6.5s-chat").strip(),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY", "").strip(),
        tavily_api_key=os.getenv("TAVILY_API_KEY", "").strip(),
        wechat_webhook_url=os.getenv("OPENCLAW_WECHAT_WEBHOOK_URL", "").strip(),
        domestic_trend_urls=domestic_urls,
        render_poll_url=os.getenv("LEGACY_RENDER_POLL_URL", "").strip(),
        render_timeout_sec=int(os.getenv("LEGACY_RENDER_TIMEOUT_SEC", "1800") or "1800"),
        use_my_real_voice=use_my_real_voice_text.lower() in {"1", "true", "yes", "on"},
        openclaw_message_cmd=os.getenv(
            "OPENCLAW_MESSAGE_CMD",
            "openclaw message send --channel wechat --stdin",
        ).strip(),
    )


def http_json(
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 60,
    method: str | None = None,
) -> dict[str, Any]:
    body = None
    final_method = method or ("POST" if payload is not None else "GET")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    if payload is not None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=request_headers, method=final_method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            raw = response.read().decode("utf-8", errors="replace")
            return json.loads(raw) if raw.strip() else {}
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code} from {url}: {detail}") from exc


def read_raw_material() -> str:
    files = sorted(DIRS["raw"].glob("*.md")) + sorted(DIRS["raw"].glob("*.txt"))
    if not files:
        sample = DIRS["raw"] / f"{now_stamp()}_sample.md"
        sample.write_text("今天写下你的真实经历、困惑、观察或情绪片段。", encoding="utf-8")
        return sample.read_text(encoding="utf-8")
    newest = max(files, key=lambda item: item.stat().st_mtime)
    return newest.read_text(encoding="utf-8", errors="replace")


def fetch_tavily_trends(config: FlowConfig) -> list[dict[str, Any]]:
    if not config.tavily_api_key:
        return []
    query = "workplace mental health personal growth short video viral topics last 3 days"
    payload = {
        "api_key": config.tavily_api_key,
        "query": query,
        "search_depth": "advanced",
        "topic": "news",
        "days": 3,
        "max_results": 8,
        "include_answer": True,
    }
    data = http_json("https://api.tavily.com/search", payload, timeout=90)
    results = data.get("results") if isinstance(data.get("results"), list) else []
    trends: list[dict[str, Any]] = []
    for item in results:
        trends.append(
            {
                "source": "tavily",
                "title": str(item.get("title", ""))[:120],
                "summary": str(item.get("content", ""))[:300],
                "url": str(item.get("url", "")),
                "score": float(item.get("score", 0) or 0),
            }
        )
    return trends


def fetch_domestic_trends(config: FlowConfig) -> list[dict[str, Any]]:
    trends: list[dict[str, Any]] = []
    for url in config.domestic_trend_urls:
        try:
            data = http_json(url, timeout=30, method="GET")
        except Exception as exc:
            trends.append({"source": "domestic_error", "title": url, "summary": str(exc)[:180], "score": 0})
            continue
        items = data.get("data") or data.get("items") or data.get("results") or []
        if isinstance(items, dict):
            items = items.get("list") or []
        if not isinstance(items, list):
            continue
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            title = item.get("title") or item.get("name") or item.get("word") or item.get("query") or ""
            summary = item.get("summary") or item.get("desc") or item.get("hot") or ""
            trends.append(
                {
                    "source": item.get("source") or "domestic",
                    "title": str(title)[:120],
                    "summary": str(summary)[:240],
                    "url": str(item.get("url") or item.get("link") or ""),
                    "score": float(item.get("score") or item.get("hot_value") or item.get("hot") or 0),
                }
            )
    return trends


def keyword_set(text: str) -> set[str]:
    tokens = re.findall(r"[\u4e00-\u9fff]{2,}|[A-Za-z][A-Za-z0-9_+-]{2,}", text.lower())
    stop = {"今天", "自己", "一个", "这个", "那个", "因为", "所以", "但是", "如果", "不是", "没有"}
    return {token for token in tokens if token not in stop}


CONTENT_PILLARS: dict[str, dict[str, Any]] = {
    "working_mom_pain": {
        "label": "职场妈妈痛点解决",
        "keywords": {"职场", "妈妈", "育儿", "老板", "迟到", "情绪", "崩溃", "时间", "危机", "撕裂", "带娃", "工作"},
        "angle": "把职场妈妈的真实崩溃，转成可执行的时间、情绪和工作流解决方案",
    },
    "short_video_creation": {
        "label": "短视频创作与剪辑干货",
        "keywords": {"短视频", "剪辑", "视频号", "创作", "脚本", "拍摄", "素材", "发布", "流量", "账号", "文案"},
        "angle": "用碎片时间完成选题、文案、剪辑、发布的高质量创作流程",
    },
    "ai_reframe": {
        "label": "AI 学习感悟与降维打击",
        "keywords": {"AI", "人工智能", "自动化", "工具", "提效", "学习", "焦虑", "重塑", "工作流", "模型", "智能"},
        "angle": "用 AI 和自动化视角重构普通女性的职业安全感",
    },
}


def infer_content_pillar(raw_material: str, trend_text: str = "") -> dict[str, Any]:
    combined = f"{raw_material} {trend_text}"
    tokens = keyword_set(combined)
    best_key = "working_mom_pain"
    best_score = -1
    for key, pillar in CONTENT_PILLARS.items():
        score = len(tokens & set(pillar["keywords"]))
        if score > best_score:
            best_key = key
            best_score = score
    return {"key": best_key, **CONTENT_PILLARS[best_key], "score": best_score}


def match_topics(raw_material: str, trends: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_keywords = keyword_set(raw_material)
    candidates: list[dict[str, Any]] = []
    for trend in trends:
        trend_text = f"{trend.get('title', '')} {trend.get('summary', '')}"
        overlap = raw_keywords & keyword_set(trend_text)
        pillar = infer_content_pillar(raw_material, trend_text)
        pillar_bonus = 18 if pillar["score"] else 5
        conflict_score = len(overlap) * 12 + min(float(trend.get("score", 0) or 0), 100) * 0.3 + pillar_bonus
        candidates.append(
            {
                "topic": build_conflict_topic(raw_material, trend, overlap, pillar),
                "matched_keywords": sorted(overlap)[:8],
                "trend": trend,
                "content_pillar": pillar,
                "score": round(conflict_score, 2),
            }
        )
    if not candidates:
        candidates = fallback_topics(raw_material)
    candidates.sort(key=lambda item: item["score"], reverse=True)
    return candidates[:3]


def build_conflict_topic(raw_material: str, trend: dict[str, Any], overlap: set[str], pillar: dict[str, Any]) -> str:
    title = str(trend.get("title", "")).strip() or "今天的情绪观察"
    personal = re.sub(r"\s+", " ", raw_material.strip())[:80]
    title_lower = f"{title} {personal}".lower()
    if "迟到" in personal and ("老板" in personal or "点名" in personal):
        return "如何通过 AI 自动化解放妈妈的周一早晨？"
    if pillar["key"] == "short_video_creation":
        return f"职场妈妈如何用碎片时间，把“{title}”变成一条能发布的短视频？"
    if pillar["key"] == "ai_reframe":
        return f"普通职场妈妈如何用 AI 把“{title}”从焦虑变成工作流？"
    if overlap:
        keywords = "、".join(sorted(overlap)[:3])
        return f"当{keywords}撞上职场妈妈日常，为什么“{title}”会让人破防？"
    return f"从我的经历看：{title}背后，职场妈妈真正卡住的不是能力，而是系统太乱"


def fallback_topics(raw_material: str) -> list[dict[str, Any]]:
    fallback_trends = [
        {"title": "AI 自动化解放妈妈的周一早晨", "summary": raw_material, "score": 1},
        {"title": "情绪崩溃背后是工作流没有被重新设计", "summary": raw_material, "score": 1},
        {"title": "普通女性用 AI 把育儿和工作从互相撕扯变成可控系统", "summary": raw_material, "score": 1},
    ]
    return [
        {
            "topic": build_conflict_topic(raw_material, trend, set(), infer_content_pillar(raw_material, str(trend.get("title", "")))),
            "matched_keywords": [],
            "trend": trend,
            "content_pillar": infer_content_pillar(raw_material, str(trend.get("title", ""))),
            "score": 1,
        }
        for trend in fallback_trends
    ]


def minimax_chat(config: FlowConfig, system_prompt: str, user_prompt: str) -> str:
    if not config.minimax_api_key:
        raise RuntimeError("MINIMAX_API_KEY is required.")
    endpoint = os.getenv(
        "MINIMAX_CHAT_ENDPOINT",
        f"https://api.minimax.chat/v1/text/chatcompletion_v2?GroupId={config.minimax_group_id}",
    )
    payload = {
        "model": config.minimax_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": float(os.getenv("MINIMAX_TEMPERATURE", "0.78") or "0.78"),
        "top_p": float(os.getenv("MINIMAX_TOP_P", "0.9") or "0.9"),
    }
    headers = {"Authorization": f"Bearer {config.minimax_api_key}"}
    data = http_json(endpoint, payload, headers=headers, timeout=120)
    choices = data.get("choices") or []
    if choices:
        message = choices[0].get("message") or {}
        return str(message.get("content") or choices[0].get("text") or "").strip()
    reply = data.get("reply") or data.get("output_text") or ""
    if not reply:
        raise RuntimeError(f"MiniMax response has no text: {json.dumps(data, ensure_ascii=False)[:500]}")
    return str(reply).strip()


def deepseek_review(config: FlowConfig, script_text: str) -> dict[str, Any]:
    if not config.deepseek_api_key:
        raise RuntimeError("DEEPSEEK_API_KEY is required.")
    payload = {
        "model": os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        "messages": [
            {"role": "system", "content": DEEPSEEK_EDITOR_PROMPT},
            {"role": "user", "content": script_text},
        ],
        "temperature": 0.1,
        "response_format": {"type": "json_object"},
    }
    data = http_json(
        os.getenv("DEEPSEEK_CHAT_ENDPOINT", "https://api.deepseek.com/chat/completions"),
        payload,
        headers={"Authorization": f"Bearer {config.deepseek_api_key}"},
        timeout=120,
    )
    content = (((data.get("choices") or [{}])[0].get("message") or {}).get("content") or "{}").strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return {"score": 0, "passed": False, "major_issues": ["DeepSeek did not return valid JSON."], "raw": content}


def build_creation_user_prompt(mode: str, topic: dict[str, Any], raw_material: str, trends: list[dict[str, Any]]) -> str:
    trend_lines = "\n".join(f"- {item.get('title')}: {item.get('summary')}" for item in trends[:8])
    pillar = topic.get("content_pillar") if isinstance(topic.get("content_pillar"), dict) else {}
    mode_spec = (
        "访谈模式：花生负责理性拆解和 AI 工作流方案，毛豆负责职场妈妈真实经历、吐槽和情绪共鸣。"
        if mode == "notebooklm"
        else "视频号模式：必须使用 [画面]、[台词]、[特效花字]，并包含 [0-3秒钩子]、真实经历共情、3个可落地方法、启发式金句结尾、评论区互动诱饵。"
    )
    return f"""创作模式：{mode}
模式细则：{mode_spec}
选题：{topic['topic']}
匹配关键词：{', '.join(topic.get('matched_keywords') or [])}
内容支柱：{pillar.get('label', '')}
支柱角度：{pillar.get('angle', '')}

长期 IP 定位：
{IP_POSITIONING}

我的真实经历素材：
{raw_material[:2500]}

近三天热点摘要：
{trend_lines[:2500]}

请生成 45-60 秒短视频脚本，必须保留指定标签，并让整篇内容服务于“职场精英妈妈 + AI 提效 + 短视频创作”的长期 IP。
"""


def revise_script(config: FlowConfig, mode: str, draft: str, review: dict[str, Any]) -> str:
    system = NOTEBOOKLM_SYSTEM_PROMPT if mode == "notebooklm" else VIDEOHAO_SYSTEM_PROMPT
    prompt = f"""这是初稿：
{draft}

这是苛刻总编的 JSON 审核意见：
{json.dumps(review, ensure_ascii=False, indent=2)}

请基于审核意见直接输出修订后的终稿。必须保留标签格式，不要解释修改过程。
"""
    return minimax_chat(config, system, prompt)


EMOTION_TAG_RULES: list[tuple[str, dict[str, Any]]] = [
    ("魔性笑", {"emotion": "laughter", "audio_event": "laugh", "keep_as_text": "哈哈哈"}),
    ("人间真实", {"emotion": "funny", "audio_event": "chuckle", "keep_as_text": "真的，家人们"}),
    ("劫后余生", {"emotion": "relieved", "audio_event": "relieved_laugh", "keep_as_text": "哈哈"}),
    ("自然地笑", {"emotion": "warm_smile", "audio_event": "smile", "keep_as_text": "哈哈"}),
    ("大笑", {"emotion": "laughter", "audio_event": "laugh", "keep_as_text": "哈哈"}),
    ("忍不住笑", {"emotion": "funny", "audio_event": "chuckle", "keep_as_text": "哈哈"}),
    ("噗", {"emotion": "funny", "audio_event": "chuckle", "keep_as_text": "噗"}),
    ("笑", {"emotion": "funny", "audio_event": "smile", "keep_as_text": ""}),
    ("语气加重", {"emotion": "emphasis", "prosody": {"volume": "+2dB", "pitch": "+2%", "rate": "medium"}}),
    ("语速加快", {"emotion": "excited", "prosody": {"rate": "fast"}}),
    ("叹气", {"emotion": "sigh", "audio_event": "sigh", "keep_as_text": "唉"}),
    ("压低声音", {"emotion": "low_voice", "prosody": {"pitch": "-6%", "volume": "-2dB"}}),
]


def _merge_emotion(current: str, incoming: str) -> str:
    if not current or current == "neutral":
        return incoming
    if current == incoming:
        return current
    priority = ["laughter", "funny", "sigh", "low_voice", "emphasis", "excited", "surprised", "empathetic"]
    for item in priority:
        if item in {current, incoming}:
            return item
    return incoming


def _merge_prosody(base: dict[str, Any], update: dict[str, Any] | None) -> dict[str, Any]:
    merged = dict(base)
    if update:
        merged.update(update)
    return merged


def parse_emotional_tags(text: str) -> dict[str, Any]:
    """Extract bracketed sound-director tags while preserving expressive spoken anchors.

    Logic A: bracket tags such as （大笑） become structured emotion/prosody fields.
    Logic B: expressive spoken words such as 哈哈哈哈、天呐、真的假的 remain in text.
    """

    raw_text = str(text or "")
    emphasis_markers = re.findall(r"\[(重要|注意)\]", raw_text)
    raw_text_without_markers = re.sub(r"\[(重要|注意)\]", "", raw_text)
    tags: list[str] = []
    audio_events: list[str] = []
    prosody: dict[str, Any] = {}
    emotion = "neutral"
    inserted_anchors: list[str] = []

    def replace_tag(match: re.Match[str]) -> str:
        nonlocal emotion, prosody
        tag = match.group(1).strip()
        tags.append(tag)
        replacement_parts: list[str] = []
        for keyword, rule in EMOTION_TAG_RULES:
            if keyword not in tag:
                continue
            emotion = _merge_emotion(emotion, str(rule.get("emotion", "neutral")))
            event = str(rule.get("audio_event", "")).strip()
            if event and event not in audio_events:
                audio_events.append(event)
            prosody = _merge_prosody(prosody, rule.get("prosody") if isinstance(rule.get("prosody"), dict) else None)
            keep_as_text = str(rule.get("keep_as_text", ""))
            if keep_as_text and keep_as_text not in inserted_anchors:
                inserted_anchors.append(keep_as_text)
                replacement_parts.append(keep_as_text)
        return "".join(replacement_parts)

    cleaned_text = re.sub(r"[（(]([^（）()]{1,20})[）)]", replace_tag, raw_text_without_markers)
    cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()

    expressive_patterns = [
        (r"哈{2,}|哈哈|哈哈哈", "funny"),
        (r"天呐|我的天|真的假的|离谱|太绝了", "surprised"),
        (r"唉|哎|难了|太难了|不容易", "empathetic"),
        (r"必须|一定|说白了|重点是", "emphasis"),
    ]
    expressive_anchors: list[str] = []
    for pattern, inferred in expressive_patterns:
        matches = re.findall(pattern, cleaned_text)
        if matches:
            emotion = _merge_emotion(emotion, inferred)
            expressive_anchors.extend(str(item) for item in matches)

    ssml_hints = {
        "emotion": emotion,
        "prosody": prosody,
        "audio_events": audio_events,
    }
    if emotion == "laughter" and not any(anchor.startswith("哈") for anchor in expressive_anchors + inserted_anchors):
        cleaned_text = f"哈哈，{cleaned_text}"
    if emphasis_markers:
        emotion = _merge_emotion(emotion, "emphasis")
        prosody = _merge_prosody(prosody, {"volume": "+10%", "rate": "slow"})
        ssml_hints = {
            "emotion": emotion,
            "prosody": prosody,
            "audio_events": audio_events,
        }

    return {
        "raw_text": raw_text,
        "text": cleaned_text,
        "emotion": emotion,
        "emotion_tags": tags,
        "emphasis_markers": emphasis_markers,
        "audio_events": audio_events,
        "prosody": prosody,
        "expressive_anchors": expressive_anchors,
        "ssml_hints": ssml_hints,
        "supports_plain_text_emotion": True,
    }


def inject_human_spoken_anchors(text: str, audio_directive: dict[str, Any]) -> str:
    """Add subtle human spoken anchors for Creator Studio voice models."""

    cleaned = str(text or "").strip()
    if not cleaned:
        return cleaned
    emotion = str(audio_directive.get("emotion", "neutral"))
    if emotion in {"laughter", "funny", "surprised"} and not re.search(r"哈|噗|天呐|真的", cleaned):
        return f"哈哈，这不就成了嘛！{cleaned}"
    if emotion in {"sigh", "empathetic", "low_voice", "relieved"} and not re.search(r"真的|家人们|唉|我当时", cleaned):
        return f"真的，家人们……{cleaned}"
    if re.search(r"愣住|迟到|老板|点名|崩溃|破防", cleaned) and "我当时就愣住了" not in cleaned:
        return f"我当时就愣住了……{cleaned}"
    return cleaned


def parse_final_script(final_text: str) -> dict[str, Any]:
    scenes: list[dict[str, Any]] = []
    lines: list[dict[str, Any]] = []
    visual_effects: list[dict[str, Any]] = []
    current_scene = ""
    current_effects: list[dict[str, Any]] = []
    pattern = re.compile(r"^\[(画面|花生|毛豆|真人|台词|特效|特效花字|Huasheng|Maodou|Human|Line|Effect)\]\s*[:：]\s*(.+)$")
    role_map = {"Huasheng": "花生", "Maodou": "毛豆", "Human": "真人", "Line": "台词", "Effect": "特效花字"}
    for raw in final_text.splitlines():
        text = raw.strip()
        if not text:
            continue
        match = pattern.match(text)
        if not match:
            continue
        role = role_map.get(match.group(1), match.group(1))
        content = match.group(2).strip()
        if role == "画面":
            current_scene = content
            current_effects = []
            scenes.append({"scene": content, "index": len(scenes) + 1, "effects": current_effects})
            continue
        if role in {"特效", "特效花字"}:
            effect = {
                "type": "text_overlay" if role == "特效花字" else "visual_effect",
                "text": content,
                "scene": current_scene,
                "index": len(visual_effects) + 1,
            }
            visual_effects.append(effect)
            current_effects.append(effect)
            continue
        if role == "台词":
            role = "真人"
        lines.append(
            {
                "role": role,
                "text": content,
                "scene": current_scene,
                "visual_effects": list(current_effects),
            }
        )
    return {"scenes": scenes, "lines": lines, "visual_effects": visual_effects}


def build_legacy_render_payload(config: FlowConfig, parsed: dict[str, Any], final_text: str) -> dict[str, Any]:
    if config.use_my_real_voice:
        voice_assignments = {
            "花生": config.voice_id_human,
            "毛豆": config.voice_id_human,
            "真人": config.voice_id_human,
        }
    elif config.mode == "notebooklm":
        voice_assignments = {
            "花生": config.voice_id_huasheng,
            "毛豆": config.voice_id_maodou,
        }
    else:
        voice_assignments = {"真人": config.voice_id_human}
    dialogue = []
    for item in parsed["lines"]:
        role = item["role"]
        audio_directive = parse_emotional_tags(item["text"])
        audio_text = inject_human_spoken_anchors(audio_directive["text"], audio_directive)
        output_role = "真人" if config.use_my_real_voice else role
        dialogue.append(
            {
                "role": output_role,
                "source_role": role,
                "text": audio_text,
                "clean_text": audio_directive["text"],
                "raw_text": item["text"],
                "voice_id": config.voice_id_human if config.use_my_real_voice else voice_assignments.get(role, config.voice_id_human),
                "scene": item.get("scene", ""),
                "visual_effects": item.get("visual_effects", []),
                "emotion": audio_directive["emotion"],
                "emotion_tags": audio_directive["emotion_tags"],
                "emphasis_markers": audio_directive["emphasis_markers"],
                "audio_events": audio_directive["audio_events"],
                "prosody": audio_directive["prosody"],
                "ssml_hints": audio_directive["ssml_hints"],
                "supports_plain_text_emotion": audio_directive["supports_plain_text_emotion"],
                "use_my_real_voice": config.use_my_real_voice,
            }
        )
    # Generic payload for a future /api/render endpoint.
    payload = {
        "mode": config.mode,
        "script_text": final_text,
        "dialogue": dialogue,
        "scenes": parsed["scenes"],
        "visual_controls": {
            "scenes": parsed["scenes"],
            "effects": parsed.get("visual_effects", []),
            "effect_sequence": parsed.get("visual_effects", []),
        },
        "voice_assignments": voice_assignments,
        "audio_pipeline": {
            "mode": "emotional_dynamic",
            "tag_parser": "parse_emotional_tags",
            "logic_a_structured_params": True,
            "logic_b_keep_plain_text_anchors": True,
            "dynamic_spoken_anchor_injection": True,
            "use_my_real_voice": config.use_my_real_voice,
            "my_voice_behavior": "all_dialogue_uses_voice_id_human_when_enabled",
            "supported_tags": sorted({keyword for keyword, _rule in EMOTION_TAG_RULES}),
        },
        "characters": {
            "huasheng": {"display_name": "花生", "voice_id": config.voice_id_huasheng},
            "maodou": {"display_name": "毛豆", "voice_id": config.voice_id_maodou},
            "human": {"display_name": "真人", "voice_id": config.voice_id_human},
        },
        "render_options": {
            "resolution": "1080p",
            "fps": 30,
            "keep_legacy_voice_clone": True,
            "keep_legacy_character_renderer": True,
        },
    }
    # Compatibility shim for the current Creator Studio /api/kids/generate endpoint.
    if config.legacy_render_url.endswith("/api/kids/generate"):
        payload.update(
            {
                "topic": "OpenClaw 自动选题",
                "seconds": 45,
                "prompt_hint": "按终稿分镜生成多场景短视频",
                "content_mode": "science" if config.mode == "notebooklm" else "early_learning",
                "custom_script": "\n".join(item["text"] for item in dialogue),
                "video_provider": os.getenv("LEGACY_VIDEO_PROVIDER", "zhipu_qingying"),
                "animation_style": "cartoon_3d_duo_cinematic",
                "maodou_voice_reference_path": os.getenv("LEGACY_MAODOU_VOICE_REFERENCE_PATH", ""),
                "peanut_voice_reference_path": os.getenv("LEGACY_HUASHENG_VOICE_REFERENCE_PATH", ""),
                "legacy_dialogue": dialogue,
                "legacy_scenes": parsed["scenes"],
                "legacy_voice_assignments": voice_assignments,
                "visual_effects": parsed.get("visual_effects", []),
                "use_my_real_voice": config.use_my_real_voice,
            }
        )
    return payload


def bridge_to_video_pipeline(final_copy_path: str | Path, config: FlowConfig | None = None) -> dict[str, Any]:
    """Parse final copy, package emotional dialogue/effects, and trigger legacy renderer."""

    final_path = Path(final_copy_path).expanduser().resolve()
    if not final_path.exists():
        raise FileNotFoundError(f"final copy not found: {final_path}")
    if config is None:
        load_dotenv(WORKSPACE / ".env")
        config = load_config(os.getenv("MEDIA_FLOW_MODE", "notebooklm"))
    final_text = final_path.read_text(encoding="utf-8", errors="replace")
    parsed = parse_final_script(final_text)
    payload = build_legacy_render_payload(config, parsed, final_text)
    bridge_payload_path = DIRS["assets"] / f"{now_stamp()}_bridge_payload.json"
    write_json(bridge_payload_path, payload)
    result = trigger_legacy_render(config, payload)
    write_json(DIRS["assets"] / f"{now_stamp()}_bridge_result.json", result)
    return {
        "final_copy_path": str(final_path),
        "bridge_payload_path": str(bridge_payload_path),
        "payload": payload,
        "render_result": result,
    }


def trigger_legacy_render(config: FlowConfig, payload: dict[str, Any]) -> dict[str, Any]:
    response = http_json(config.legacy_render_url, payload, timeout=120)
    render_job = response
    job_id = str(response.get("id") or response.get("job_id") or response.get("task_id") or "")
    if config.render_poll_url and job_id:
        deadline = time.time() + config.render_timeout_sec
        while time.time() < deadline:
            poll_url = config.render_poll_url.format(job_id=job_id)
            snapshot = http_json(poll_url, timeout=30, method="GET")
            status = str(snapshot.get("status") or snapshot.get("task_status") or "").lower()
            if status in {"completed", "success", "succeeded", "done"}:
                render_job = snapshot
                break
            if status in {"failed", "error", "canceled", "cancelled"}:
                raise RuntimeError(f"Legacy render failed: {json.dumps(snapshot, ensure_ascii=False)[:800]}")
            time.sleep(8)
    return render_job


def push_wechat(config: FlowConfig, final_text: str, render_result: dict[str, Any]) -> dict[str, Any]:
    video_link = (
        render_result.get("video_url")
        or (render_result.get("artifacts") or {}).get("video_url")
        or render_result.get("download_url")
        or ""
    )
    payload = {
        "channel": "wechat",
        "type": "media_flow_result",
        "created_at": datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds"),
        "video_link": video_link,
        "moments_summary": build_moments_summary(final_text),
        "wechat_article_copy": build_wechat_article(final_text, video_link),
        "render_result": render_result,
    }
    output_file = DIRS["outputs"] / f"{now_stamp()}_wechat_payload.json"
    output_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if config.wechat_webhook_url:
        try:
            return http_json(config.wechat_webhook_url, payload, timeout=60)
        except Exception as exc:
            payload["wechat_push_error"] = str(exc)
    if config.openclaw_message_cmd:
        try:
            completed = subprocess.run(
                config.openclaw_message_cmd,
                input=json.dumps(payload, ensure_ascii=False),
                text=True,
                shell=True,
                capture_output=True,
                timeout=60,
                check=False,
            )
            payload["openclaw_message_cmd"] = config.openclaw_message_cmd
            payload["openclaw_message_returncode"] = completed.returncode
            payload["openclaw_message_stdout"] = completed.stdout[-1000:]
            payload["openclaw_message_stderr"] = completed.stderr[-1000:]
        except Exception as exc:
            payload["openclaw_message_error"] = str(exc)
    return payload


def build_moments_summary(final_text: str) -> str:
    speech = re.sub(r"\[(画面|花生|毛豆|真人|Huasheng|Maodou|Human)\]\s*[:：]", "", final_text)
    speech = re.sub(r"\s+", " ", speech).strip()
    return speech[:110] + ("..." if len(speech) > 110 else "")


def build_wechat_article(final_text: str, video_link: str) -> str:
    return f"""# 今日自动生成短视频

## 成片链接
{video_link or "视频仍在渲染或等待外部系统返回链接"}

## 终稿文案
{final_text}
"""


def write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def validate_startup(mode: str) -> dict[str, Any]:
    ensure_dirs()
    load_dotenv(WORKSPACE / ".env")
    config = load_config(mode)
    required = {
        "MINIMAX_API_KEY": bool(config.minimax_api_key),
        "MINIMAX_GROUP_ID": bool(config.minimax_group_id),
        "DEEPSEEK_API_KEY": bool(config.deepseek_api_key),
        "LEGACY_RENDER_URL": bool(config.legacy_render_url),
        "VOICE_ID_HUASHENG": bool(config.voice_id_huasheng),
        "VOICE_ID_MAODOU": bool(config.voice_id_maodou),
        "VOICE_ID_HUMAN": bool(config.voice_id_human),
    }
    optional = {
        "TAVILY_API_KEY": bool(config.tavily_api_key),
        "DOMESTIC_TREND_URLS": bool(config.domestic_trend_urls),
        "OPENCLAW_WECHAT_WEBHOOK_URL": bool(config.wechat_webhook_url),
        "LEGACY_RENDER_POLL_URL": bool(config.render_poll_url),
    }
    dir_status = {name: path.exists() and path.is_dir() for name, path in DIRS.items()}
    raw_files = sorted(DIRS["raw"].glob("*.md")) + sorted(DIRS["raw"].glob("*.txt"))
    missing_required = [name for name, ok in required.items() if not ok]
    result = {
        "status": "ok" if not missing_required else "needs_configuration",
        "mode": mode,
        "workspace": str(WORKSPACE),
        "directories": dir_status,
        "raw_material_files": [str(path) for path in raw_files[-5:]],
        "required_env": required,
        "optional_env": optional,
        "missing_required_env": missing_required,
        "legacy_render_url": config.legacy_render_url,
        "render_poll_url": config.render_poll_url,
        "message": "Startup validation passed." if not missing_required else "Fill missing env values before running full flow.",
    }
    return result


def run_flow(mode: str) -> dict[str, Any]:
    ensure_dirs()
    load_dotenv(WORKSPACE / ".env")
    config = load_config(mode)
    raw_material = read_raw_material()

    tavily = fetch_tavily_trends(config)
    domestic = fetch_domestic_trends(config)
    trends = tavily + domestic
    trend_report = {
        "created_at": now_stamp(),
        "tavily_count": len(tavily),
        "domestic_count": len(domestic),
        "trends": trends,
    }
    write_json(DIRS["trends"] / f"{now_stamp()}_trend_report.json", trend_report)

    topics = match_topics(raw_material, trends)
    write_json(DIRS["trends"] / f"{now_stamp()}_matched_topics.json", topics)
    selected = topics[0]

    system_prompt = NOTEBOOKLM_SYSTEM_PROMPT if mode == "notebooklm" else VIDEOHAO_SYSTEM_PROMPT
    user_prompt = build_creation_user_prompt(mode, selected, raw_material, trends)
    draft = minimax_chat(config, system_prompt, user_prompt)
    draft_file = DIRS["drafts"] / f"{now_stamp()}_{mode}_draft.md"
    draft_file.write_text(draft, encoding="utf-8")

    review = deepseek_review(config, draft)
    review_file = DIRS["reviews"] / f"{now_stamp()}_{mode}_review.json"
    write_json(review_file, review)

    final_text = revise_script(config, mode, draft, review)
    final_file = DIRS["final"] / "final_version.md"
    final_file.write_text(final_text, encoding="utf-8")

    bridge_result = bridge_to_video_pipeline(final_file, config=config)
    parsed = parse_final_script(final_text)
    write_json(DIRS["final"] / "final_parsed.json", parsed)
    render_result = bridge_result["render_result"]

    wechat_result = push_wechat(config, final_text, render_result)
    summary = {
        "mode": mode,
        "selected_topic": selected,
        "draft_file": str(draft_file),
        "review_file": str(review_file),
        "final_file": str(final_file),
        "render_result": render_result,
        "wechat_result": wechat_result,
    }
    write_json(DIRS["outputs"] / f"{now_stamp()}_run_summary.json", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run OpenClaw one-person media automation flow.")
    parser.add_argument(
        "--mode",
        choices=["notebooklm", "videohao"],
        default=os.getenv("MEDIA_FLOW_MODE", "notebooklm"),
        help="notebooklm: Huasheng/Maodou interview; videohao: human talking-head script.",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate workspace, env and legacy bridge settings without calling external APIs.",
    )
    args = parser.parse_args()
    result = validate_startup(args.mode) if args.validate else run_flow(args.mode)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
