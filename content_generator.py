from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

from shared import (
    HISTORY_CSV,
    HISTORY_HEADERS,
    OUTPUT_DIR,
    TOPICS_CSV,
    TOPICS_HEADERS,
    apply_proxy_settings,
    append_csv_row,
    ensure_workspace,
    load_config,
    make_topic_id,
    now_str,
    read_csv,
    rewrite_csv,
    safe_float,
    slugify_for_filename,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成 30-40 秒短视频成片文案（标题+口播+封面+配音）")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径，默认使用 config.json")
    parser.add_argument("--topic", type=str, default=None, help="直接指定选题标题")
    parser.add_argument("--topic-id", type=str, default=None, help="从 topics.csv 指定 topic_id 生成")
    parser.add_argument(
        "--series",
        type=str,
        default="auto",
        choices=[
            "auto",
            "people_recap",
            "people_videohao",
            "people_shooting",
            "girl_recap",
            "girl_videohao",
            "girl_shooting",
            "anti_anxiety",
            "self_rescue",
            "self_media",
        ],
        help=(
            "指定主题：auto 自动判断，或 "
            "people_recap/people_videohao/people_shooting（兼容旧系列键）"
        ),
    )
    parser.add_argument("--mock", action="store_true", help="不调用 API，输出演示模板")
    parser.add_argument("--mock-on-quota", action="store_true", help="当配额不足时自动降级 mock")
    return parser.parse_args()


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def sanitize_api_key(value: str | None) -> str:
    if not value:
        return ""
    key = value.strip()
    if (key.startswith('"') and key.endswith('"')) or (key.startswith("'") and key.endswith("'")):
        key = key[1:-1].strip()
    return key


def read_user_env_api_key_windows() -> str:
    if os.name != "nt":
        return ""
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as env_key:
            value, _ = winreg.QueryValueEx(env_key, "OPENAI_API_KEY")
            return sanitize_api_key(str(value))
    except Exception:  # noqa: BLE001
        return ""


def resolve_api_key() -> str:
    key = sanitize_api_key(os.getenv("OPENAI_API_KEY", ""))
    if key:
        return key
    return read_user_env_api_key_windows()


def choose_topic(topic_arg: str | None, topic_id: str | None) -> tuple[str, str | None]:
    if topic_arg:
        return topic_arg.strip(), topic_id

    rows = read_csv(TOPICS_CSV)
    new_rows = [r for r in rows if (r.get("status") or "").upper() == "NEW"]
    if topic_id:
        for row in new_rows:
            if row.get("topic_id") == topic_id:
                return row.get("title", "").strip(), row.get("topic_id")
        raise ValueError(f"未找到 topic_id={topic_id} 的 NEW 选题。")

    if not new_rows:
        raise ValueError("topics.csv 中没有状态为 NEW 的选题。请先运行 topic_collector.py。")

    new_rows.sort(key=lambda r: safe_float(r.get("score", 0.0)), reverse=True)
    chosen = new_rows[0]
    return chosen.get("title", "").strip(), chosen.get("topic_id")


def get_series_profiles(config: dict[str, Any]) -> dict[str, dict[str, Any]]:
    defaults: dict[str, dict[str, Any]] = {
        "people_recap": {
            "label": "普通人视频复盘",
            "core_goal": "把一条视频的结果讲明白，沉淀下一条可执行动作",
            "audience_pain": "发完就焦虑、看不懂数据、复盘抓不住重点",
            "framework": "结果反馈 -> 关键拆解 -> 明日动作",
            "scene": "发布后播放波动、评论少、完播不稳",
        },
        "people_videohao": {
            "label": "视频号实操教学",
            "core_goal": "把视频号运营方法讲成可马上照做的清单",
            "audience_pain": "不会选题、不会起标题、发了没人看",
            "framework": "常见误区 -> 三步实操 -> 发布检查",
            "scene": "0粉起号、周更不稳、流量忽高忽低",
        },
        "people_shooting": {
            "label": "拍视频学习经验",
            "core_goal": "降低拍摄门槛，让普通人用手机也能拍出稳定质感",
            "audience_pain": "怕镜头、口播卡壳、拍完不敢发",
            "framework": "卡点诊断 -> 三步练习 -> 复盘强化",
            "scene": "居家拍摄、通勤碎片时间练口播、单人出镜",
        },
        # 兼容旧系列命名
        "girl_recap": {
            "label": "普通人视频复盘",
            "core_goal": "把一条视频的结果讲明白，沉淀下一条可执行动作",
            "audience_pain": "发完就焦虑、看不懂数据、复盘抓不住重点",
            "framework": "结果反馈 -> 关键拆解 -> 明日动作",
            "scene": "发布后播放波动、评论少、完播不稳",
        },
        "girl_videohao": {
            "label": "视频号实操教学",
            "core_goal": "把视频号运营方法讲成可马上照做的清单",
            "audience_pain": "不会选题、不会起标题、发了没人看",
            "framework": "常见误区 -> 三步实操 -> 发布检查",
            "scene": "0粉起号、周更不稳、流量忽高忽低",
        },
        "girl_shooting": {
            "label": "拍视频学习经验",
            "core_goal": "降低拍摄门槛，让普通人用手机也能拍出稳定质感",
            "audience_pain": "怕镜头、口播卡壳、拍完不敢发",
            "framework": "卡点诊断 -> 三步练习 -> 复盘强化",
            "scene": "居家拍摄、通勤碎片时间练口播、单人出镜",
        },
        "anti_anxiety": {
            "label": "普通人视频复盘",
            "core_goal": "把一条视频的结果讲明白，沉淀下一条可执行动作",
            "audience_pain": "发完就焦虑、看不懂数据、复盘抓不住重点",
            "framework": "结果反馈 -> 关键拆解 -> 明日动作",
            "scene": "发布后播放波动、评论少、完播不稳",
        },
        "self_rescue": {
            "label": "视频号实操教学",
            "core_goal": "把视频号运营方法讲成可马上照做的清单",
            "audience_pain": "不会选题、不会起标题、发了没人看",
            "framework": "常见误区 -> 三步实操 -> 发布检查",
            "scene": "0粉起号、周更不稳、流量忽高忽低",
        },
        "self_media": {
            "label": "拍视频学习经验",
            "core_goal": "降低拍摄门槛，让普通人用手机也能拍出稳定质感",
            "audience_pain": "怕镜头、口播卡壳、拍完不敢发",
            "framework": "卡点诊断 -> 三步练习 -> 复盘强化",
            "scene": "居家拍摄、通勤碎片时间练口播、单人出镜",
        },
    }
    cfg_profiles = config.get("content_strategy", {}).get("series_profiles", {})
    if not isinstance(cfg_profiles, dict):
        return defaults

    merged = dict(defaults)
    for key, value in cfg_profiles.items():
        if key in merged and isinstance(value, dict):
            merged[key] = {**merged[key], **value}
    return merged


def infer_series(topic: str, series_arg: str, config: dict[str, Any]) -> str:
    if series_arg != "auto":
        return series_arg

    low = topic.lower()
    recap_keywords = ("复盘", "数据", "完播", "播放", "点赞", "评论", "拆解", "发布后")
    videohao_keywords = ("视频号", "起号", "选题", "标题", "封面", "发布时间", "涨粉", "运营")
    shooting_keywords = ("拍摄", "镜头", "口播", "布光", "收音", "剪辑", "脚本", "出镜", "表达")

    if any(k in low for k in recap_keywords):
        return "people_recap"
    if any(k in low for k in videohao_keywords):
        return "people_videohao"
    if any(k in low for k in shooting_keywords):
        return "people_shooting"

    # 兼容旧主题词
    anxiety_keywords = ("焦虑", "失业", "降薪", "经济", "内卷", "裁员", "压力")
    rescue_keywords = ("自救", "副业", "收入", "现金流", "储蓄", "转行", "求职")
    media_keywords = ("自媒体", "公众号", "个人ip")
    if any(k in low for k in anxiety_keywords):
        return "anti_anxiety"
    if any(k in low for k in rescue_keywords):
        return "self_rescue"
    if any(k in low for k in media_keywords):
        return "self_media"

    default_series = str(config.get("content_strategy", {}).get("default_series", "people_recap")).strip()
    allowed = {
        "people_recap",
        "people_videohao",
        "people_shooting",
        "girl_recap",
        "girl_videohao",
        "girl_shooting",
        "anti_anxiety",
        "self_rescue",
        "self_media",
    }
    if default_series in allowed:
        return default_series
    return "people_recap"


def canonical_series_key(series_key: str) -> str:
    mapping = {
        "people_recap": "people_recap",
        "people_videohao": "people_videohao",
        "people_shooting": "people_shooting",
        "girl_recap": "people_recap",
        "girl_videohao": "people_videohao",
        "girl_shooting": "people_shooting",
        "anti_anxiety": "people_recap",
        "self_rescue": "people_videohao",
        "self_media": "people_shooting",
    }
    return mapping.get(series_key, series_key)


def build_novelty_kit(topic: str, series_key: str) -> dict[str, str]:
    seed = int(make_topic_id(f"{series_key}-{topic}")[:8], 16)

    common_memory = [
        "先做小样本，再谈大增长",
        "先找可复制动作，再找天赋状态",
        "先做减法，把一个点打穿",
        "先把失败设计进流程，反而更稳",
        "先稳定输出，再追爆发曲线",
    ]
    common_questions = [
        "你更卡开头、方法段、还是结尾互动？",
        "如果今天只改一个点，你会改镜头、文案、还是节奏？",
        "你会先追播放还是先追完播，为什么？",
        "你最想先拿下哪一关：选题、拍摄、发布？",
    ]

    pools: dict[str, dict[str, list[str]]] = {
        "people_recap": {
            "hooks": [
                "你以为数据差是能力差 / 其实常常是顺序错了。",
                "你以为复盘是检讨 / 其实它更像找增长漏洞。",
                "你以为要等爆款再分析 / 其实小样本最值钱。",
                "你以为播放低就没救 / 其实有时只是开头3秒跑偏。",
            ],
            "odd_views": [
                "先看被划走的秒点，比看总播放更有用",
                "先复盘失败样本，比复盘成功样本更快提速",
                "先改结构，不先改情绪",
                "先做一条对照组，再谈算法喜好",
            ],
            "micro_tests": [
                "今天只测一个变量：同主题只改开头前一句",
                "今晚做一个20分钟快复盘：删掉中段1句废话再录",
                "下一条先做A/B开头稿，每版只讲20秒",
                "明天只验证一个点：结尾多一个互动问题",
            ],
            "title_spices": [
                "先别怪算法，先怪顺序",
                "复盘不是自责，是提速器",
                "低播放也能挖出增长点",
            ],
        },
        "people_videohao": {
            "hooks": [
                "你以为起号要学100招 / 其实先跑通1个小闭环。",
                "你以为没流量是运气差 / 其实常卡在每条都重启。",
                "你以为选题越多越好 / 其实先做窄更容易起势。",
                "你以为爆款靠灵感 / 其实靠可复用流程。",
            ],
            "odd_views": [
                "先做废片预算，反而更快出成片",
                "先固定发布动作，再优化内容细节",
                "先做问题库，不先做题材库",
                "先追完成率，不先追播放峰值",
            ],
            "micro_tests": [
                "今天只做一个实验：同题写10个开头，选最短的拍",
                "今晚只测一个变量：封面主词从形容词改成动词",
                "下一条先按30秒骨架拍，再补花活镜头",
                "明天固定同一时段发布，连续3条看趋势",
            ],
            "title_spices": [
                "先跑通，再跑快",
                "起号先做减法",
                "流量不稳先稳流程",
            ],
        },
        "people_shooting": {
            "hooks": [
                "你以为拍不好是不上镜 / 其实先输在第一口气。",
                "你以为镜头尴尬靠硬扛 / 其实靠动作脚本。",
                "你以为要一次拍完才专业 / 其实会拆段才专业。",
                "你以为声音难听没救 / 其实先改节奏就能提升。",
            ],
            "odd_views": [
                "先练停顿，不先练语速",
                "先练呼吸，再练表情",
                "先拍短段，再拼长段",
                "先把废镜头留着复盘，别急着删",
            ],
            "micro_tests": [
                "今天只做一个20秒镜头循环：同一句录3版挑最松弛",
                "今晚只练开场前10秒呼吸+微笑启动",
                "下一条只改一个点：每句末尾多停0.5秒",
                "明天拍前先读一遍口语稿，删掉3个书面词",
            ],
            "title_spices": [
                "会拆段比一次过更快",
                "镜头感先练呼吸",
                "拍摄先求自然再求华丽",
            ],
        },
    }
    pool = pools.get(series_key, pools["people_recap"])

    def pick(options: list[str], offset: int) -> str:
        return options[(seed + offset) % len(options)]

    return {
        "hook": pick(pool["hooks"], 0),
        "odd_view": pick(pool["odd_views"], 1),
        "micro_test": pick(pool["micro_tests"], 2),
        "title_spice": pick(pool["title_spices"], 3),
        "memory_point": pick(common_memory, 4),
        "question": pick(common_questions, 5),
    }


def build_system_prompt(config: dict[str, Any], series_profile: dict[str, Any]) -> str:
    profile = config.get("account_profile", {})
    style_notes = config.get("content_strategy", {}).get(
        "style_notes",
        [
            "先痛点，后方法",
            "短句有停顿，读起来有节奏",
            "拒绝鸡汤，强调生活可执行",
            "每条内容给本周动作",
        ],
    )
    style_line = "；".join(str(x).strip() for x in style_notes if str(x).strip())
    return (
        "你是短视频内容总编，擅长写真人口播。"
        "任务是输出可直接开拍的 30-40 秒短视频成片包。"
        f"账号定位：{profile.get('positioning', '普通人成长与自救')}。"
        f"受众：{profile.get('audience', '有现实压力的普通人')}。"
        f"口吻：{profile.get('tone', '真诚、直接、反鸡汤')}。"
        f"栏目：{series_profile.get('label', '')}。"
        f"栏目目标：{series_profile.get('core_goal', '')}。"
        f"核心场景：{series_profile.get('scene', '')}。"
        f"写作约束：{style_line}。"
        "必须输出简体中文，且每条建议都贴近日常生活场景。"
        "风格要求：诙谐但不油腻，像一个清醒又幽默的朋友。"
        "表达姿态：像朋友聊天，不像上课；少术语、少官话、多生活口语。"
        "整体氛围：积极、轻松、有推进感。"
        "表达要求：每8-10秒至少一个记忆点（反转、类比、自嘲、反差其一）。"
        "互动要求：结尾必须抛出一个可讨论的问题，让观众愿意评论。"
        "观点要求：每条必须包含新奇特三元素："
        "1个反常识观点（新）+ 1个出人意料类比或角度（奇）+ 1个24小时可验证的小实验（特）。"
        "禁止空泛观点，必须可执行、可验证。"
        "不能低俗，不能悬浮，不能鸡汤。"
    )


def build_short_video_prompt(topic: str, config: dict[str, Any], series_profile: dict[str, Any]) -> str:
    cta = config.get("account_profile", {}).get("cta", "评论区告诉我你最卡的一步")
    return f"""
选题：{topic}
栏目：{series_profile.get('label', '')}
结构框架：{series_profile.get('framework', '')}

请严格按以下结构输出，不能缺项：

## 标题候选（10条）
要求：每条 14-22 字，口语化，不夸张，不虚假承诺。
并且至少 3 条包含反常识表达（如 先别做X，先做Y）。

## 30-40秒口播文案（节奏版）
按时间轴输出：
- 0-4秒：反差钩子（1句）
- 4-12秒：现实共鸣（1-2句）
- 12-28秒：可执行方法（3步，必须具体）
- 28-34秒：反转/复盘记忆点（1句）
- 34-40秒：行动号召+互动提问（1句，围绕 {cta}）

要求：
1. 总时长控制在 30-40 秒可读完。
2. 每句尽量短，适合真人口播，读起来有停顿感。
3. 方法必须贴近日常，不要宏大叙事。
4. 口播里要有轻幽默（反差/自嘲/比喻），氛围积极轻松，但不低俗。
5. 在建议停顿的位置用“/”标记，方便录制卡节奏。
6. 开头必须有“反差钩子”，让人愿意继续听。
7. 28-34秒这句必须带一个“转折记忆点”。
8. 最后一句必须包含可互动问题，能引发讨论。
9. 结尾禁止引导关注公众号、私信口令、站外导流；结尾句不要使用引号。
10. 文案里必须显式包含：
   - 1个反常识观点（新）
   - 1个意外类比/新角度（奇）
   - 1个24小时内可执行的微实验动作（特）
11. 方法段至少有一个“只改一个变量”的测试动作。
12. 口吻必须像朋友聊天，允许口语词，不要老师讲课腔。
13. 少用术语堆砌，尽量用生活化表达。

## 封面实现方案
输出以下字段：
- 封面主标题（<=12字）
- 封面副标题（<=14字）
- 画面建议（人物状态、场景、构图）
- 配色和字体建议（给出 2 套可选）
- 制作步骤（手机可执行，按 1/2/3/4 步）

## 配音执行方案
输出以下字段：
- 情绪基调
- 语速建议（字/分钟）
- 停顿点（标注 3-5 个）
- 重音词（5 个以内）
- 录音参数（手机录音距离、环境、降噪建议）

## 发布补充
- 视频文案（80-120字）
- 评论区引导（1句）
- 话题标签（6个）
""".strip()


def call_openai_responses(
    api_key: str,
    model: str,
    system_prompt: str,
    user_prompt: str,
    temperature: float = 0.7,
    base_url: str = "https://api.openai.com",
) -> str:
    endpoint = base_url.rstrip("/") + "/v1/responses"
    payload: dict[str, Any] = {
        "model": model,
        "input": [
            {"role": "system", "content": [{"type": "input_text", "text": system_prompt}]},
            {"role": "user", "content": [{"type": "input_text", "text": user_prompt}]},
        ],
    }
    if temperature is not None:
        payload["temperature"] = temperature

    def extract_api_error(error_text: str) -> tuple[str, str]:
        try:
            data = json.loads(error_text)
            err = data.get("error", {})
            return str(err.get("code") or ""), str(err.get("message") or "")
        except Exception:  # noqa: BLE001
            return "", ""

    def build_http_error_message(status_code: int, error_text: str) -> str:
        err_code, err_msg = extract_api_error(error_text)
        if err_code == "insufficient_quota":
            return (
                "OpenAI API 请求失败: HTTP 429 (insufficient_quota)\n"
                "你的 API 账户额度不足。请到 Billing 充值/开通后重试：\n"
                "https://platform.openai.com/settings/organization/billing\n"
                "临时可用 --mock 或 --mock-on-quota 继续跑流程。"
            )
        if err_code == "invalid_api_key":
            return (
                "OpenAI API 请求失败: HTTP 401 (invalid_api_key)\n"
                "当前 API Key 无效。请在 https://platform.openai.com/api-keys 新建 key 后重新设置。"
            )
        if err_msg:
            return f"OpenAI API 请求失败: HTTP {status_code}\n{err_msg}"
        return f"OpenAI API 请求失败: HTTP {status_code}\n{error_text}"

    def should_retry_without_temperature(status_code: int, error_text: str, current_payload: dict[str, Any]) -> bool:
        if status_code != 400 or "temperature" not in current_payload:
            return False
        text = error_text.lower()
        return ("unsupported parameter" in text and "temperature" in text) or (
            "not supported with this model" in text and "temperature" in text
        )

    def post_once(current_payload: dict[str, Any]) -> dict[str, Any]:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps(current_payload).encode("utf-8"),
            method="POST",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            return json.loads(resp.read().decode("utf-8"))

    try:
        data = post_once(payload)
    except urllib.error.HTTPError as exc:
        err_text = exc.read().decode("utf-8", errors="ignore")
        if should_retry_without_temperature(exc.code, err_text, payload):
            retry_payload = dict(payload)
            retry_payload.pop("temperature", None)
            print("[INFO] 当前模型不支持 temperature，已自动重试（不带 temperature）")
            try:
                data = post_once(retry_payload)
            except urllib.error.HTTPError as retry_exc:
                retry_text = retry_exc.read().decode("utf-8", errors="ignore")
                raise RuntimeError(build_http_error_message(retry_exc.code, retry_text)) from retry_exc
            except urllib.error.URLError as retry_exc:
                raise RuntimeError(f"OpenAI API 连接失败: {retry_exc}") from retry_exc
        else:
            raise RuntimeError(build_http_error_message(exc.code, err_text)) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"OpenAI API 连接失败: {exc}") from exc

    return extract_text_from_response(data)


def extract_text_from_response(data: dict[str, Any]) -> str:
    output_text = data.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    chunks: list[str] = []
    for item in data.get("output", []):
        if not isinstance(item, dict):
            continue
        for content in item.get("content", []):
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str):
                    chunks.append(text.strip())

    if chunks:
        return "\n\n".join(part for part in chunks if part)

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        message = choices[0].get("message", {})
        msg_content = message.get("content", "")
        if isinstance(msg_content, str) and msg_content.strip():
            return msg_content.strip()

    raise RuntimeError(f"无法解析模型输出，返回字段如下: {list(data.keys())}")


def build_mock_short_form(topic: str, series_key: str, series_profile: dict[str, Any], cta: str) -> str:
    label = series_profile.get("label", "普通人成长")
    canonical = canonical_series_key(series_key)
    novelty = build_novelty_kit(topic, canonical)

    if canonical == "people_videohao":
        titles = f"""1. {novelty['title_spice']}：普通人做视频号别先求爆款
2. 先做废片预算，起号反而更快
3. 你不是不会做号，是每条都从零开荒
4. 别先卷数量，先卷可复用流程
5. 起号第一周，先把稳定更新做出来
6. 发了没人看，先改一个变量再重发
7. 先做问题库，不先做题材库
8. 普通人做视频号，先把流程跑轻
9. 流量忽高忽低？先固定发布动作
10. 起号别靠玄学，靠可复盘系统"""
        script = f"""- 0-4秒：{novelty['hook']}
- 4-12秒：说句大白话，围绕{topic}，很多人不是不会做 / 是一上来就想全做对。{novelty['odd_view']}。
- 12-28秒：咱们今天不整虚的 / 先定1类人群和1个问题 / 再备10条问题型标题 / 最后固定一周3更，先稳住再提速。今日微实验：{novelty['micro_test']}。
- 28-34秒：{novelty['memory_point']} / 你会感觉整个人没那么乱了。
- 34-40秒：{cta}；{novelty['question']}"""
        cover_main, cover_sub = "普通人起号法", "新奇特三步跑通"
        tone = "像会讲梗的陪跑教练，轻松但有推进感。"
        tags = "#视频号运营 #普通人做自媒体 #起号 #选题 #内容增长 #实操复盘"
        desc = (
            f"{label}别靠玄学。围绕{topic}，今天给你新奇特三件套：反常识观点、意外角度、24小时微实验。"
            "先把可复制流程跑通，再追爆发。"
        )
    elif canonical == "people_shooting":
        titles = f"""1. {novelty['title_spice']}：拍视频别先追一次过
2. 普通人出镜紧张，先改呼吸再改表情
3. 拍不好不是不上镜，是动作顺序错了
4. 会拆段的人，反而更快拍出自然感
5. 镜头尴尬别硬扛，先做20秒循环
6. 手机拍视频，先练停顿不先练语速
7. 口播总卡壳？先删3个书面词
8. 新手拍摄最值钱的是失败样本
9. 拍摄练习别贪多，先拿下一个变量
10. 不靠设备堆料，也能拍出稳定质感"""
        script = f"""- 0-4秒：{novelty['hook']}
- 4-12秒：我以前也这样，围绕{topic}，一开拍就僵 / 脑子是清醒的，脸先下线。{novelty['odd_view']}。
- 12-28秒：给你一套好上手的 / 先写口语短句，每句不超15字 / 再做10秒呼吸+微笑启动 / 最后20秒一段一段拍，后期再拼。今日微实验：{novelty['micro_test']}。
- 28-34秒：{novelty['memory_point']} / 你会更快找到自然状态。
- 34-40秒：{cta}；{novelty['question']}"""
        cover_main, cover_sub = "拍摄不尴尬", "先练新奇特3步"
        tone = "轻松、有鼓励感，像一起练镜头感的朋友。"
        tags = "#拍摄技巧 #口播训练 #普通人出镜 #视频号拍摄 #手机拍视频 #表达训练"
        desc = (
            f"{label}不是拼设备，而是拼方法。围绕{topic}，先用新奇特三件套做小实验，"
            "再把有效动作固化成自己的拍摄流程。"
        )
    else:
        titles = f"""1. {novelty['title_spice']}：这条视频复盘后我改了顺序
2. 复盘别先看播放，先看被划走的秒点
3. 数据差不等于你差，可能只是结构错位
4. 普通人复盘，先抓一个变量就够
5. 低播放也能挖出增长点
6. 复盘不是自责，是下一条提速器
7. 先改开头再改中段，效果更明显
8. 小样本复盘，常比大爆款更有用
9. 先复盘失败样本，进步反而更快
10. 看完这条，你会更会复盘自己的视频"""
        script = f"""- 0-4秒：{novelty['hook']}
- 4-12秒：咱先别急着emo，围绕{topic}，发完焦虑很正常 / 但先别给自己下结论。{novelty['odd_view']}。
- 12-28秒：复盘就干三件事 / 看前3秒有没有把人留住 / 看中段有没有废话 / 看结尾有没有互动动作。今日微实验：{novelty['micro_test']}。
- 28-34秒：{novelty['memory_point']} / 先改透一个点，比一口气全改更靠谱。
- 34-40秒：{cta}；{novelty['question']}"""
        cover_main, cover_sub = "视频复盘法", "新奇特破卡点"
        tone = "真诚里带幽默，像一起打怪升级的队友。"
        tags = "#视频复盘 #普通人做自媒体 #视频号成长 #内容优化 #口播节奏 #互动文案"
        desc = (
            f"{label}不是检讨大会，而是增长工具。围绕{topic}，今天用新奇特三件套："
            "反常识观点、意外角度、24小时微实验，帮你把下一条做得更稳。"
        )

    return f"""## 标题候选（10条）
{titles}

## 30-40秒口播文案（节奏版）
{script}

## 封面实现方案
- 封面主标题（<=12字）：{cover_main}
- 封面副标题（<=14字）：{cover_sub}
- 画面建议（人物状态、场景、构图）：近景半身，眼神看镜头，背景用工位或家里书桌，人物占画面 2/3。
- 配色和字体建议（给出 2 套可选）：
  方案A：黑底+亮黄字，字体用思源黑体 Heavy；
  方案B：米白底+深红字，字体用阿里巴巴普惠体 Bold。
- 制作步骤（手机可执行，按 1/2/3/4 步）：
  1. 用手机拍正面半身图；
  2. 在剪映封面加主标题+副标题；
  3. 主标题放中上，副标题放右下；
  4. 导出后检查小屏可读性再发布。

## 配音执行方案
- 情绪基调：{tone}
- 语速建议（字/分钟）：230-270 字/分钟。
- 停顿点（标注 3-5 个）：反常识钩子后停0.3秒；方法三步之间各停0.2秒；微实验前停0.3秒；结尾提问前停0.2秒。
- 重音词（5 个以内）：反常识、变量、实验、复盘、稳定。
- 录音参数（手机录音距离、环境、降噪建议）：手机距离嘴 15-20cm；关门窗；用剪映轻降噪+压限。

## 发布补充
- 视频文案（80-120字）：{desc}
- 评论区引导（1句）：{novelty['question']}
- 话题标签（6个）：{tags}
"""


def extract_primary_title(content_text: str, fallback: str) -> str:
    in_title_block = False
    for raw_line in content_text.splitlines():
        line = raw_line.strip()
        if line.startswith("## 标题候选"):
            in_title_block = True
            continue
        if in_title_block and line.startswith("## "):
            break
        if in_title_block:
            m = re.match(r"^\d+\.\s*(.+)$", line)
            if m:
                return m.group(1).strip()

    m_cover = re.search(r"封面主标题[^：:]*[:：]\s*(.+)", content_text)
    if m_cover:
        return m_cover.group(1).strip()
    return fallback


def mark_topic_used(topic_id: str | None) -> None:
    if not topic_id:
        return
    rows = read_csv(TOPICS_CSV)
    changed = False
    for row in rows:
        if row.get("topic_id") == topic_id and (row.get("status") or "").upper() == "NEW":
            row["status"] = "USED"
            row["used_at"] = now_str()
            changed = True
            break
    if changed:
        rewrite_csv(TOPICS_CSV, TOPICS_HEADERS, rows)


def main() -> None:
    configure_console()
    args = parse_args()
    ensure_workspace()
    config = load_config(args.config)

    proxy = apply_proxy_settings(config)
    if proxy:
        print(f"[INFO] 已启用代理: {proxy}")

    topic, resolved_topic_id = choose_topic(args.topic, args.topic_id)
    resolved_topic_id = resolved_topic_id or make_topic_id(topic)
    series_key = infer_series(topic, args.series, config)
    series_profile = get_series_profiles(config).get(series_key, {})

    print(f"选题: {topic}")
    print(f"栏目: {series_profile.get('label', series_key)}")

    cta = config.get("account_profile", {}).get("cta", "评论区告诉我你最卡的一步")
    system_prompt = build_system_prompt(config, series_profile)
    user_prompt = build_short_video_prompt(topic, config, series_profile)

    if args.mock:
        content_text = build_mock_short_form(topic, series_key, series_profile, cta)
        model_name = "mock-template"
    else:
        api_key = resolve_api_key()
        if not api_key:
            raise RuntimeError("未检测到 OPENAI_API_KEY 环境变量。可先使用 --mock 测试流程。")

        llm_cfg = config.get("llm", {})
        model_name = str(llm_cfg.get("model", "gpt-5-mini"))
        temperature = float(llm_cfg.get("temperature", 0.7))
        base_url = str(llm_cfg.get("base_url", "https://api.openai.com"))

        try:
            content_text = call_openai_responses(
                api_key=api_key,
                model=model_name,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=temperature,
                base_url=base_url,
            )
        except RuntimeError as exc:
            msg = str(exc)
            if args.mock_on_quota and "insufficient_quota" in msg:
                print("[WARN] 检测到 API 配额不足，已自动降级为 mock 生成。")
                content_text = build_mock_short_form(topic, series_key, series_profile, cta)
                model_name = f"{model_name} (mock-on-quota)"
            else:
                raise

    now = datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    slug = slugify_for_filename(topic, prefix="topic")
    series_file_key = series_key.replace("girl_", "people_")
    output_path = OUTPUT_DIR / f"{stamp}_{series_file_key}_{slug}.md"

    full_text = f"""# 30-40秒短视频成片包

生成时间：{now.strftime("%Y-%m-%d %H:%M:%S")}
选题：{topic}
栏目：{series_profile.get('label', series_key)}
模型：{model_name}

{content_text}
"""
    output_path.write_text(full_text, encoding="utf-8")

    primary_title = extract_primary_title(content_text, fallback=topic)
    history_row = {
        "content_id": f"{now.strftime('%Y%m%d')}-{resolved_topic_id[:8]}",
        "created_at": now.strftime("%Y-%m-%d %H:%M:%S"),
        "topic": topic,
        "primary_title": primary_title,
        "output_file": str(output_path.resolve()),
        "channel": "视频号",
        "read_count": "0",
        "avg_read_time": "0",
        "like_count": "0",
        "share_count": "0",
        "lead_count": "0",
        "completion_rate": "0",
    }
    append_csv_row(HISTORY_CSV, HISTORY_HEADERS, history_row)
    mark_topic_used(resolved_topic_id)

    print(f"已生成: {output_path.resolve()}")
    print(f"已写入发布记录: {Path(HISTORY_CSV).resolve()}")


if __name__ == "__main__":
    main()
