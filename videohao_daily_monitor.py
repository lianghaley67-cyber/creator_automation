from __future__ import annotations

import argparse
import csv
import hashlib
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from shared import BASE_DIR, REPORT_DIR, load_config


COLUMN_ALIASES = {
    "title": ["title", "标题", "作品标题", "视频标题", "内容标题"],
    "publish_time": ["publish_time", "发布时间", "发布日期", "date", "publish_date", "时间", "日期"],
    "account": ["account", "账号", "作者", "发布账号", "博主", "创作者"],
    "duration_sec": ["duration_sec", "duration", "时长", "视频时长", "时长(s)", "视频时长(s)"],
    "play_count": ["play_count", "play", "播放量", "播放", "观看次数", "曝光量", "阅读量"],
    "like_count": ["like_count", "like", "点赞数", "点赞", "喜欢"],
    "comment_count": ["comment_count", "comment", "评论数", "评论"],
    "share_count": ["share_count", "share", "转发数", "转发", "分享数", "分享"],
    "follow_count": ["follow_count", "follow", "新增关注", "涨粉", "关注数", "粉丝增长", "关注"],
    "completion_rate": ["completion_rate", "完播率", "看完率"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="每日视频号相关内容统计 + 自动出新文案")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径，默认 config.json")
    parser.add_argument(
        "--input",
        type=str,
        default=str(BASE_DIR / "data" / "videohao_posts.csv"),
        help="视频号导出 CSV 路径",
    )
    parser.add_argument("--days", type=int, default=3, help="统计最近 N 天，默认 3")
    parser.add_argument("--top", type=int, default=15, help="分析 Top 样本数量，默认 15")
    parser.add_argument("--mock", action="store_true", help="生成文案时使用 mock")
    parser.add_argument("--mock-on-quota", action="store_true", help="额度不足自动降级 mock")
    parser.add_argument("--python-exe", type=str, default=sys.executable, help="调用脚本的 Python 路径")
    parser.add_argument("--output", type=str, default="", help="日报输出路径，默认 reports/videohao_daily_*.md")
    parser.add_argument(
        "--ready-output",
        type=str,
        default="",
        help="可直接录制文案输出路径，默认 outputs/ready_30_40s_*.md",
    )
    parser.add_argument(
        "--library-output",
        type=str,
        default="",
        help="新奇特分析脚本库输出路径，默认 outputs/script_library_*.md",
    )
    parser.add_argument("--use-latest-download", action="store_true", help="自动读取下载目录最新 CSV 作为输入")
    parser.add_argument("--watch-dir", type=str, default="", help="下载目录路径（配合 --use-latest-download）")
    parser.add_argument("--latest-max-age-hours", type=int, default=48, help="最新数据最大允许小时数，超出则告警")
    parser.add_argument(
        "--allow-demo-data",
        action="store_true",
        help="允许使用模板演示数据（默认关闭，防止误用）",
    )
    return parser.parse_args()


def norm_key(text: str) -> str:
    t = text.strip().lower()
    t = re.sub(r"[\s_\-()（）\[\]【】:：/\\]+", "", t)
    return t


def find_column(fieldnames: list[str], canonical: str) -> str | None:
    alias_norm = {norm_key(x) for x in COLUMN_ALIASES.get(canonical, [])}
    mapping = {norm_key(f): f for f in fieldnames}
    for a in alias_norm:
        if a in mapping:
            return mapping[a]
    return None


def parse_datetime(value: str) -> datetime | None:
    text = (value or "").strip()
    if not text:
        return None
    fmts = [
        "%Y-%m-%d %H:%M:%S",
        "%Y/%m/%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%Y/%m/%d %H:%M",
        "%Y-%m-%d",
        "%Y/%m/%d",
    ]
    for fmt in fmts:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def to_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    text = str(value).strip().replace(",", "")
    if not text:
        return default
    text = text.replace("%", "")
    m = re.match(r"^-?\d+(\.\d+)?", text)
    if not m:
        return default
    return float(m.group(0))


def detect_series(title: str, theme_keywords: dict[str, list[str]]) -> str:
    low = title.lower()
    for series, keywords in theme_keywords.items():
        if any(kw.lower() in low for kw in keywords):
            return series
    return "mixed"


def canonical_series(series: str) -> str:
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
    return mapping.get(series, series)


def normalize_topic_text(text: str) -> str:
    t = (text or "").strip().lower()
    t = re.sub(r"\s+", "", t)
    t = re.sub(r"[^\w\u4e00-\u9fff]", "", t)
    return t


def default_topic_pool() -> dict[str, list[str]]:
    return {
        "people_recap": [
            "我把一条低播放视频拆开后，发现真正拖后腿的不是选题",
            "为什么有些视频看起来一般却能留人？我复盘后只改了一个动作",
            "普通人做复盘最容易犯的错：一上来就改脚本，而不是先看流失点",
            "我用对照组复盘一条视频，第二条不是爆了，但明显更稳了",
            "复盘不是找谁对谁错，而是找到下一条最省力的增长点",
            "同一个题材，为什么今天比昨天更难留人？我复盘后得到一个反常识结论",
            "视频发完别急着删，我靠一条失败样本反而跑出新方向",
            "普通人做视频复盘，先盯这3个秒点，比盯总播放更有用",
            "我复盘时最有用的不是数据截图，而是一句观众会划走的话",
            "你以为复盘很复杂？其实每天20分钟就能把账号从乱变稳",
        ],
        "people_videohao": [
            "普通人做视频号别急着找爆款，我先把发布流程做轻了",
            "我把起号动作砍到3步后，更新反而更稳定",
            "为什么你越努力越没结果？可能是每条都在重新开机",
            "先做问题库，不先做题材库，这个方法让我少走很多弯路",
            "视频号起号期最反常识的一点：先追完成率，不先追峰值播放",
            "我做了一个小实验：只改开头前一句，完播感觉完全不同",
            "普通人0基础做视频号，先别卷数量，先卷可复用流程",
            "同样30秒内容，为什么有的像聊天有的像念稿？关键在结构顺序",
            "如果你总是断更，先改日程，不先改能力",
            "我把选题从灵感制改成清单制后，创作焦虑明显下降",
        ],
        "people_shooting": [
            "我以前一开拍就僵，后来发现问题不在表达，在呼吸顺序",
            "拍视频最反常识的一点：会拆段的人，比一次过的人更快进步",
            "普通人拍摄卡壳，不是嘴笨，是开场动作没准备好",
            "我用20秒循环练习法，三天就把镜头尴尬降下来了",
            "你以为要设备升级，结果我先改停顿就更自然了",
            "拍摄时最实用的不是台词，而是删掉3个书面词",
            "我把废镜头留下来复盘后，才知道自己每次都卡在同一句",
            "普通人拍口播别先追流畅，先追松弛，反而更好看",
            "为什么你拍完总不敢发？我用一个小动作把这个坎过了",
            "手机拍视频先别整复杂景别，先把第一句说顺",
        ],
    }


def load_recent_history_topic_keys(limit: int = 120) -> set[str]:
    history_path = (BASE_DIR / "data" / "content_history.csv").resolve()
    if not history_path.exists():
        return set()

    try:
        with history_path.open("r", encoding="utf-8-sig", newline="") as f:
            rows = list(csv.DictReader(f))
    except Exception:  # noqa: BLE001
        return set()

    keys: set[str] = set()
    for row in rows[-limit:]:
        topic = str(row.get("topic", "")).strip()
        if topic:
            keys.add(normalize_topic_text(topic))
    return keys


def build_topic_pool(
    monitor_cfg: dict[str, Any],
    fallback_topics: dict[str, str],
) -> dict[str, list[str]]:
    pool = default_topic_pool()
    user_pool = monitor_cfg.get("topic_pool", {})
    if isinstance(user_pool, dict):
        for raw_series, values in user_pool.items():
            series = canonical_series(str(raw_series).strip())
            if not isinstance(values, list):
                continue
            merged = list(pool.get(series, []))
            for v in values:
                t = str(v).strip()
                if t and t not in merged:
                    merged.append(t)
            pool[series] = merged

    for raw_series, fallback in fallback_topics.items():
        series = canonical_series(str(raw_series).strip())
        text = str(fallback).strip()
        if not text:
            continue
        existing = pool.get(series, [])
        if text not in existing:
            existing.append(text)
        pool[series] = existing

    return pool


def _merge_unique_topics(values: list[str]) -> list[str]:
    merged: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw).strip()
        if not text:
            continue
        key = normalize_topic_text(text)
        if not key or key in seen:
            continue
        seen.add(key)
        merged.append(text)
    return merged


def _seeded_topic_order(candidates: list[str], seed: int) -> list[str]:
    ranked = sorted(
        _merge_unique_topics(candidates),
        key=lambda x: hashlib.sha256(f"{seed}|{x}".encode("utf-8")).hexdigest(),
    )
    return ranked


def generate_breakout_topics(series: str, seed: int, count: int = 18) -> list[str]:
    """Generate dynamic breakout topics so we are not locked to static pools."""
    if series == "people_recap":
        templates = [
            "你以为{myth}，我复盘后先看{action}，结果{result}",
            "这条没爆我没删，反而去看{action}：{result}",
            "复盘别先看总播放，我只盯{action}，然后{result}",
            "我把“{myth}”这个执念停掉一周，最后我发现{result}",
        ]
        myths = [
            "脸不够上镜",
            "设备不够贵",
            "平台不给流量",
            "表达不够高级",
            "一定要一次拍完",
        ]
        actions = [
            "前3秒划走点",
            "评论区第一句",
            "废片里重复卡壳点",
            "开头那一句口头禅",
            "同题材AB开场对照",
        ]
        results = [
            "完播不一定暴涨但稳定了",
            "评论区开始有人认真聊了",
            "拍摄焦虑明显降了",
            "更新频率终于能扛住",
            "我终于知道该改哪一步",
        ]
    elif series == "people_videohao":
        templates = [
            "想涨粉别先{myth}，先做这个动作：{action}，普通人也能{result}",
            "我拿7天做实验：把“{action}”固定后，{result}",
            "起号期最反常识的一点：别先{myth}，先把{action}做稳",
            "同样30秒，我只改了{action}，最后{result}",
        ]
        myths = [
            "追热点",
            "堆更新数量",
            "狂学剪辑特效",
            "每天换新赛道",
            "追爆款",
        ]
        actions = [
            "开头第一句做成翻车现场",
            "固定发布时间和发布动作",
            "每条只讲一个问题",
            "先做选题清单再写稿",
            "结尾改成二选一提问",
        ]
        results = [
            "稳住连更，不再三天打鱼",
            "把互动质量先拉起来",
            "不再像随机发朋友圈",
            "把内容节奏拉顺",
            "在低播放里也能拿到有效反馈",
        ]
    else:
        templates = [
            "拍口播别先{myth}，先做这个动作：{action}，你会发现{result}",
            "我以前一开拍就僵，后来把{action}放到开机前，结果{result}",
            "镜头尴尬不一定是脸的问题，多半是{action}没做，导致{result}",
            "别追一次拍完，我改成{action}后，居然{result}",
        ]
        myths = [
            "背完整台词",
            "硬练播音腔",
            "买设备再开拍",
            "一镜到底才专业",
            "表情管理越多越好",
        ]
        actions = [
            "10秒呼吸+微笑启动",
            "20秒拆段拍摄",
            "每句压到15字内",
            "镜头旁1厘米定点看",
            "先讲一个今天翻车的小事",
        ]
        results = [
            "声音一下子松下来了",
            "卡壳次数比以前少一半",
            "整个人看起来像聊天不是背稿",
            "拍完敢发，不再无限重录",
            "观众更愿意停下来听完",
        ]

    combos: list[str] = []
    for tpl in templates:
        for myth in myths:
            for action in actions:
                result = results[(seed + len(combos)) % len(results)]
                combos.append(tpl.format(myth=myth, action=action, result=result))

    ordered = _seeded_topic_order(combos, seed=seed)
    return ordered[: max(3, count)]


def inject_breakout_topics(
    topic_pool: dict[str, list[str]],
    daily_series: list[str],
    day_seed: int,
    breakout_count: int,
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    breakout_map: dict[str, list[str]] = {}
    for idx, raw in enumerate(daily_series):
        series = canonical_series(raw)
        generated = generate_breakout_topics(series, seed=day_seed + idx * 97, count=breakout_count)
        breakout_map[series] = generated
        merged = _merge_unique_topics(generated + topic_pool.get(series, []))
        topic_pool[series] = merged
    return topic_pool, breakout_map


def calc_score(play: float, like: float, comment: float, share: float, follow: float, completion: float) -> float:
    eng = (like + comment + share) / play if play > 0 else 0.0
    follow_per_1k = (follow / play * 1000.0) if play > 0 else 0.0
    return eng * 100 + completion * 100 + follow_per_1k * 0.6


def duration_bucket(sec: float) -> str:
    if sec <= 20:
        return "0-20秒"
    if sec <= 35:
        return "21-35秒"
    if sec <= 60:
        return "36-60秒"
    return "60秒以上"


def pick_topic_for_series(
    series: str,
    target_rows: list[dict[str, Any]],
    related_rows: list[dict[str, Any]],
    fallback_topics: dict[str, str],
) -> tuple[str, str]:
    series_target = [x for x in target_rows if x["series"] == series]
    if series_target:
        return series_target[0]["title"], "target_data"
    series_related = [x for x in related_rows if x["series"] == series]
    if series_related:
        return series_related[0]["title"], "related_data"

    # 回退兼容：保持旧行为
    return fallback_topics.get(series, "普通人如何在压力下稳住自己并持续行动"), "fallback"


def pick_topic_with_pool_and_history(
    series: str,
    target_rows: list[dict[str, Any]],
    related_rows: list[dict[str, Any]],
    fallback_topics: dict[str, str],
    topic_pool: dict[str, list[str]],
    priority_topics: list[str],
    recent_topic_keys: set[str],
    used_topic_keys: set[str],
    day_seed: int,
) -> tuple[str, str]:
    """Pick topic by priority: data signal -> fresh pool -> rotated pool."""
    priority_fresh: list[str] = []
    for topic in priority_topics:
        key = normalize_topic_text(topic)
        if not key:
            continue
        if key in recent_topic_keys or key in used_topic_keys:
            continue
        priority_fresh.append(topic)
    if priority_fresh:
        picked = priority_fresh[day_seed % len(priority_fresh)]
        used_topic_keys.add(normalize_topic_text(picked))
        return picked, "breakout_fresh"

    chosen, source = pick_topic_for_series(series, target_rows, related_rows, fallback_topics)
    chosen_key = normalize_topic_text(chosen)
    if chosen and chosen_key and chosen_key not in recent_topic_keys and chosen_key not in used_topic_keys:
        used_topic_keys.add(chosen_key)
        return chosen, source

    pool = topic_pool.get(series, [])
    if not pool:
        if chosen_key:
            used_topic_keys.add(chosen_key)
        return chosen, source

    fresh_candidates: list[str] = []
    for topic in pool:
        key = normalize_topic_text(topic)
        if not key:
            continue
        if key in recent_topic_keys or key in used_topic_keys:
            continue
        fresh_candidates.append(topic)

    if fresh_candidates:
        picked = fresh_candidates[day_seed % len(fresh_candidates)]
        used_topic_keys.add(normalize_topic_text(picked))
        return picked, "pool_fresh"

    rotate_start = day_seed % len(pool)
    for idx in range(len(pool)):
        picked = pool[(rotate_start + idx) % len(pool)]
        key = normalize_topic_text(picked)
        if not key:
            continue
        if key in used_topic_keys:
            continue
        used_topic_keys.add(key)
        return picked, "pool_rotate"

    if chosen_key:
        used_topic_keys.add(chosen_key)
    return chosen, source


def run_content_generator(
    python_exe: str,
    config_path: str | None,
    series: str,
    topic: str,
    mock: bool,
    mock_on_quota: bool,
) -> tuple[int, str, str]:
    cmd = [
        python_exe,
        str((BASE_DIR / "content_generator.py").resolve()),
        "--series",
        series,
        "--topic",
        topic,
    ]
    if config_path:
        cmd.extend(["--config", config_path])
    if mock:
        cmd.append("--mock")
    elif mock_on_quota:
        cmd.append("--mock-on-quota")

    proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    output = (proc.stdout or "") + ("\n" + proc.stderr if proc.stderr else "")
    generated = ""
    for line in output.splitlines():
        if line.strip().startswith("已生成:"):
            generated = line.split("已生成:", 1)[1].strip()
            break
    return proc.returncode, generated, output.strip()


def extract_lines_between(lines: list[str], start_pat: str, stop_prefix: str = "## ") -> list[str]:
    inside = False
    buf: list[str] = []
    for raw in lines:
        line = raw.rstrip("\n")
        if not inside and line.strip().startswith(start_pat):
            inside = True
            continue
        if inside:
            if line.strip().startswith(stop_prefix):
                break
            buf.append(line)
    return [x for x in buf if x.strip()]


def parse_generated_content(path: str) -> dict[str, Any]:
    file_path = Path(path)
    if not file_path.exists():
        return {"top_titles": [], "script_lines": [], "topic": "", "series": ""}

    text = file_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    title_lines = extract_lines_between(lines, "## 标题候选", stop_prefix="## ")
    script_lines = extract_lines_between(lines, "## 30-40秒口播文案（节奏版）", stop_prefix="## ")
    if not script_lines:
        script_lines = extract_lines_between(lines, "## 30秒口播文案（节奏版）", stop_prefix="## ")

    top_titles: list[str] = []
    for line in title_lines:
        m = re.match(r"^\s*\d+\.\s*(.+)$", line.strip())
        if m:
            top_titles.append(m.group(1).strip())
        if len(top_titles) >= 3:
            break

    topic = ""
    series = ""
    for line in lines[:20]:
        if line.startswith("选题："):
            topic = line.split("：", 1)[1].strip()
        if line.startswith("栏目："):
            series = line.split("：", 1)[1].strip()

    return {
        "top_titles": top_titles,
        "script_lines": script_lines,
        "topic": topic,
        "series": series,
    }


def series_label(series: str) -> str:
    mapping = {
        "people_recap": "普通人视频复盘",
        "people_videohao": "视频号实操教学",
        "people_shooting": "拍视频学习经验",
        "girl_recap": "普通人视频复盘",
        "girl_videohao": "视频号实操教学",
        "girl_shooting": "拍视频学习经验",
        "anti_anxiety": "经济下行抗焦虑",
        "self_rescue": "普通人自救",
        "self_media": "普通人做自媒体",
    }
    return mapping.get(series, series)


def get_daily_series(monitor_cfg: dict[str, Any]) -> list[str]:
    default_series = ["people_recap", "people_videohao", "people_shooting"]
    raw = monitor_cfg.get("daily_series", default_series)
    if not isinstance(raw, list):
        return default_series

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw:
        key = canonical_series(str(item).strip())
        if not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(key)
    return cleaned or default_series


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def load_flexible_csv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    raw_lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if not raw_lines:
        return [], []

    header_idx = None
    for i, line in enumerate(raw_lines):
        if ("标题" in line or "title" in line.lower() or "时间" in line) and ("播放" in line or "play" in line.lower()):
            header_idx = i
            break

    if header_idx is None:
        # 回退：按首行尝试
        header_idx = 0

    content = "\n".join(raw_lines[header_idx:])
    reader = csv.DictReader(content.splitlines())
    fieldnames = reader.fieldnames or []
    rows = list(reader)
    return fieldnames, rows


def find_latest_csv(folder: Path) -> Path | None:
    if not folder.exists():
        return None
    candidates: list[Path] = []
    for p in folder.glob("*.csv"):
        try:
            if p.is_file():
                candidates.append(p)
        except OSError:
            continue
    if not candidates:
        return None
    return sorted(candidates, key=lambda x: x.stat().st_mtime, reverse=True)[0]


def line_after_colon(text: str) -> str:
    if "：" in text:
        return text.split("：", 1)[1].strip()
    if ":" in text:
        return text.split(":", 1)[1].strip()
    return text.strip()


def build_script_library_text(
    generated_paths: dict[str, str],
    daily_series: list[str],
    input_path: Path,
    data_mode_text: str,
    data_age_hours: float,
    days: int,
) -> str:
    cards: list[str] = []
    for series in daily_series:
        parsed = parse_generated_content(generated_paths.get(series, ""))
        script_lines = parsed.get("script_lines", [])
        hook = ""
        odd_view = ""
        micro_test = ""
        close_question = ""
        for line in script_lines:
            stripped = line.strip()
            if stripped.startswith("- 0-4秒："):
                hook = line_after_colon(stripped)
            elif stripped.startswith("- 4-12秒："):
                odd_view = line_after_colon(stripped)
            elif "微实验：" in stripped:
                micro_test = stripped.split("微实验：", 1)[1].strip()
            elif stripped.startswith("- 34-40秒："):
                close_question = line_after_colon(stripped)
        top_titles = parsed.get("top_titles", [])
        cards.append(
            f"""### {series_label(series)}
- 今日选题：{parsed.get('topic', '')}
- 标题候选 TOP3：{" / ".join(top_titles[:3]) if top_titles else "暂无"}
- 新（反常识钩子）：{hook or "暂无"}
- 奇（意外角度）：{odd_view or "暂无"}
- 特（24h微实验）：{micro_test or "暂无"}
- 互动收口：{close_question or "暂无"}
"""
        )

    templates = """## 可复用模板（新奇特）
1. 反常识钩子模板：你以为X / 其实先做Y。
2. 奇观点模板：多数人卡在A / 真正有效的是B（反直觉动作）。
3. 特实验模板：今天只改一个变量：把X改成Y，24小时后看Z指标变化。
4. 互动结尾模板：你最卡哪一步：A/B/C？留言我按评论拆解。
"""

    return f"""# 视频号新奇特分析脚本库

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
数据文件：{input_path}
数据模式：{data_mode_text}
数据新鲜度：约 {data_age_hours:.1f} 小时前更新
统计窗口：最近 {days} 天

## 今日脚本卡片
{chr(10).join(cards)}

{templates}
"""


def main() -> None:
    args = parse_args()
    config = load_config(args.config)

    monitor_cfg = config.get("videohao_monitor", {})
    daily_series = get_daily_series(monitor_cfg)
    target_accounts = [str(x) for x in monitor_cfg.get("target_accounts", ["福饱饱6", "福饱饱"])]
    theme_keywords = monitor_cfg.get(
        "theme_keywords",
        {
            "people_recap": ["复盘", "数据", "完播", "播放", "点赞", "评论", "拆解", "留存"],
            "people_videohao": ["视频号", "起号", "选题", "标题", "封面", "发布时间", "涨粉", "运营"],
            "people_shooting": ["拍摄", "镜头", "口播", "布光", "收音", "剪辑", "出镜", "表达"],
        },
    )
    fallback_topics_raw = monitor_cfg.get(
        "fallback_topics",
        {
            "people_recap": "普通人如何做一次有效的视频复盘并找到下一条增长点",
            "people_videohao": "普通人做视频号的三步实操方法：选题、标题、发布",
            "people_shooting": "普通人拍视频如何克服镜头尴尬并稳定输出",
        },
    )

    fallback_topics: dict[str, str] = {}
    if isinstance(fallback_topics_raw, dict):
        for raw_series, raw_topic in fallback_topics_raw.items():
            key = canonical_series(str(raw_series).strip())
            val = str(raw_topic).strip()
            if key and val and key not in fallback_topics:
                fallback_topics[key] = val

    topic_pool = build_topic_pool(monitor_cfg, fallback_topics)
    history_limit_raw = monitor_cfg.get("topic_history_window", 120)
    try:
        history_limit = max(1, int(history_limit_raw))
    except (TypeError, ValueError):
        history_limit = 120
    recent_topic_keys = load_recent_history_topic_keys(limit=history_limit)
    breakout_enabled = bool(monitor_cfg.get("breakout_enabled", True))
    breakout_count_raw = monitor_cfg.get("breakout_count", 24)
    try:
        breakout_count = max(6, int(breakout_count_raw))
    except (TypeError, ValueError):
        breakout_count = 24
    day_seed_base = int(datetime.now().strftime("%Y%m%d"))
    breakout_topics_map: dict[str, list[str]] = {}
    if breakout_enabled:
        topic_pool, breakout_topics_map = inject_breakout_topics(
            topic_pool=topic_pool,
            daily_series=daily_series,
            day_seed=day_seed_base,
            breakout_count=breakout_count,
        )

    login_cfg = config.get("videohao_login", {})
    watch_dir = Path(args.watch_dir.strip() or str(login_cfg.get("watch_dir", Path.home() / "Downloads"))).resolve()
    if args.use_latest_download:
        latest_csv = find_latest_csv(watch_dir)
        if not latest_csv:
            raise FileNotFoundError(f"未在下载目录找到 CSV: {watch_dir}")
        input_path = latest_csv.resolve()
        print(f"[INFO] 已自动使用最新数据文件: {input_path}")
    else:
        input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(
            f"未找到数据文件: {input_path}\n请把视频号导出 CSV 放到该路径。"
        )
    now_ts = datetime.now().timestamp()
    data_age_hours = max(0.0, (now_ts - input_path.stat().st_mtime) / 3600.0)
    if data_age_hours > max(1, args.latest_max_age_hours):
        print(
            f"[WARN] 当前数据文件较旧：约 {data_age_hours:.1f} 小时前更新，"
            "可能不是视频号最新数据。"
        )
    template_path = (BASE_DIR / "data" / "videohao_posts_template.csv").resolve()
    if template_path.exists() and not args.allow_demo_data:
        if sha256_of_file(input_path) == sha256_of_file(template_path):
            raise ValueError(
                "检测到你当前使用的是模板演示数据（videohao_posts_template.csv），"
                "不是后台真实导出。\n请先把真实 CSV 覆盖到 data/videohao_posts.csv 再运行。"
            )

    fieldnames, source_rows = load_flexible_csv(input_path)

    col_title = find_column(fieldnames, "title")
    col_time = find_column(fieldnames, "publish_time")
    col_account = find_column(fieldnames, "account")
    col_duration = find_column(fieldnames, "duration_sec")
    col_play = find_column(fieldnames, "play_count")
    col_like = find_column(fieldnames, "like_count")
    col_comment = find_column(fieldnames, "comment_count")
    col_share = find_column(fieldnames, "share_count")
    col_follow = find_column(fieldnames, "follow_count")
    col_completion = find_column(fieldnames, "completion_rate")

    if not col_play:
        raise ValueError("CSV 至少需要包含 播放量（如 播放/播放量）列。")
    if not col_title and not col_time:
        raise ValueError("CSV 需要至少包含 标题 或 时间 列之一。")

    cutoff = datetime.now() - timedelta(days=args.days)
    parsed_rows: list[dict[str, Any]] = []
    all_rows: list[dict[str, Any]] = []
    aggregate_mode = col_title is None
    for row in source_rows:
        date_text = str(row.get(col_time, "")).strip() if col_time else ""
        title = str(row.get(col_title, "")).strip() if col_title else f"日汇总 {date_text}"
        if not title:
            title = "日汇总"

        pub_dt = parse_datetime(str(row.get(col_time, ""))) if col_time else None

        account = str(row.get(col_account, "")).strip() if col_account else ""
        play = to_float(row.get(col_play))
        like = to_float(row.get(col_like)) if col_like else 0.0
        comment = to_float(row.get(col_comment)) if col_comment else 0.0
        share = to_float(row.get(col_share)) if col_share else 0.0
        follow = to_float(row.get(col_follow)) if col_follow else 0.0
        completion = to_float(row.get(col_completion)) if col_completion else 0.0
        if completion > 1:
            completion = completion / 100
        duration = to_float(row.get(col_duration)) if col_duration else 30.0

        series = canonical_series(detect_series(title, theme_keywords)) if not aggregate_mode else "mixed"
        account_hit = any(x.lower() in account.lower() for x in target_accounts) if account else False
        related = True if aggregate_mode else (series != "mixed" or account_hit)
        score = calc_score(play, like, comment, share, follow, completion)

        row_obj = {
            "title": title,
            "account": account,
            "publish_dt": pub_dt,
            "duration_sec": duration,
            "play": play,
            "like": like,
            "comment": comment,
            "share": share,
            "follow": follow,
            "completion": completion,
            "series": series,
            "account_hit": account_hit,
            "related": related,
            "score": score,
        }
        all_rows.append(row_obj)

        if pub_dt and pub_dt < cutoff:
            continue
        parsed_rows.append(row_obj)

    if not parsed_rows:
        parsed_rows = list(all_rows)
        if parsed_rows:
            print(f"[WARN] 最近 {args.days} 天无数据，已回退到全量数据继续生成。")
        else:
            raise ValueError("CSV 中没有可用数据，请检查标题/播放量字段。")

    related_rows = [x for x in parsed_rows if x["related"]]
    related_rows.sort(key=lambda x: x["score"], reverse=True)
    related_rows = related_rows[: max(1, args.top)]

    target_rows = [x for x in related_rows if x["account_hit"]]
    target_rows.sort(key=lambda x: x["score"], reverse=True)

    best_hours = Counter([x["publish_dt"].hour for x in related_rows if x["publish_dt"]]).most_common(3)
    best_hours_txt = "、".join([f"{h}:00" for h, _ in best_hours]) if best_hours else "暂无"

    duration_counter = Counter([duration_bucket(x["duration_sec"]) for x in related_rows])
    duration_txt = "、".join([f"{k}({v})" for k, v in duration_counter.most_common()]) if duration_counter else "暂无"

    theme_counter = Counter([x["series"] for x in related_rows])
    theme_txt = "、".join([f"{k}({v})" for k, v in theme_counter.most_common()]) if theme_counter else "暂无"

    generated_paths: dict[str, str] = {}
    generation_logs: dict[str, str] = {}
    selected_topics: dict[str, str] = {}
    topic_sources: dict[str, str] = {}
    used_topic_keys: set[str] = set()
    for series in daily_series:
        canonical_key = canonical_series(series)
        day_seed = int(datetime.now().strftime("%Y%m%d")) + sum(ord(ch) for ch in canonical_key)
        topic, topic_source = pick_topic_with_pool_and_history(
            series=canonical_key,
            target_rows=target_rows,
            related_rows=related_rows,
            fallback_topics=fallback_topics,
            topic_pool=topic_pool,
            priority_topics=breakout_topics_map.get(canonical_key, []) if breakout_enabled else [],
            recent_topic_keys=recent_topic_keys,
            used_topic_keys=used_topic_keys,
            day_seed=day_seed,
        )
        code, output_path, output_text = run_content_generator(
            python_exe=args.python_exe,
            config_path=args.config,
            series=canonical_key,
            topic=topic,
            mock=args.mock,
            mock_on_quota=args.mock_on_quota,
        )
        selected_topics[series] = topic
        topic_sources[series] = topic_source
        if code == 0 and output_path:
            generated_paths[series] = output_path
        generation_logs[series] = f"[topic_source={topic_source}] {topic}\n{output_text}".strip()

    top_related_lines = "\n".join(
        [
            f"{i}. {x['title']} | 账号={x['account'] or '未知'} | 分数={x['score']:.2f} | 完播={x['completion']:.2%}"
            for i, x in enumerate(related_rows[:10], start=1)
        ]
    )
    top_target_lines = "\n".join(
        [
            f"{i}. {x['title']} | 分数={x['score']:.2f} | 完播={x['completion']:.2%}"
            for i, x in enumerate(target_rows[:8], start=1)
        ]
    ) or f"（未在当前数据中识别到重点账号记录，请确认 CSV 是否包含账号列。目标账号：{', '.join(target_accounts)}）"

    generated_lines = []
    for series in daily_series:
        p = generated_paths.get(series)
        if p:
            generated_lines.append(f"- {series_label(series)}: {p}")
        else:
            generated_lines.append(f"- {series_label(series)}: 生成失败，请查看日志")
    generated_txt = "\n".join(generated_lines)
    topic_pick_txt = "\n".join(
        [
            f"- {series_label(series)} | source={topic_sources.get(series, 'unknown')} | topic={selected_topics.get(series, '')}"
            for series in daily_series
        ]
    )

    generation_log_sections = []
    for series in daily_series:
        generation_log_sections.append(f"### {series_label(series)}\n{generation_logs.get(series, '')}\n")
    generation_logs_text = "\n".join(generation_log_sections)

    daily_series_labels = ", ".join(series_label(s) for s in daily_series)

    report = f"""# 视频号每日监控日报

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
数据文件：{input_path}
数据新鲜度：约 {data_age_hours:.1f} 小时前更新
统计窗口：最近 {args.days} 天
数据模式：{"按天汇总" if aggregate_mode else "按视频明细"}
总样本：{len(parsed_rows)} | 相关样本：{len(related_rows)} | 重点账号样本：{len(target_rows)}
今日生成栏目：{daily_series_labels}

## 今日节奏结论
- 推荐时段：{best_hours_txt}
- 推荐时长分布：{duration_txt}
- 相关主题分布：{theme_txt}
- 发布结构建议：4秒反差钩子 -> 8秒共鸣 -> 16秒三步动作 -> 6秒反转 -> 6秒互动CTA

## 重点账号观察（高分样本）
{top_target_lines}

## 主题相关高分样本（前10）
{top_related_lines}

## 今日自动生成文案文件
{generated_txt}

## 今日选题说明
{topic_pick_txt}

## 生成日志（失败排查）
{generation_logs_text}
"""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output.strip():
        report_path = Path(args.output).resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = REPORT_DIR / f"videohao_daily_{stamp}.md"

    report_path.write_text(report, encoding="utf-8")
    print(f"日报已生成: {report_path}")

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if args.ready_output.strip():
        ready_path = Path(args.ready_output).resolve()
    else:
        ready_path = (BASE_DIR / "outputs" / f"ready_30_40s_{stamp}.md").resolve()
    ready_path.parent.mkdir(parents=True, exist_ok=True)

    blocks: list[str] = []
    for series in daily_series:
        p = generated_paths.get(series, "")
        parsed = parse_generated_content(p) if p else {"top_titles": [], "script_lines": [], "topic": "", "series": ""}
        title_line = parsed["top_titles"][0] if parsed["top_titles"] else parsed.get("topic", "")
        script_block = "\n".join(parsed["script_lines"]) if parsed["script_lines"] else "（未提取到30-40秒脚本）"
        blocks.append(
            f"""## {series_label(series)}
选题：{parsed.get('topic', '')}
推荐标题：{title_line}

30-40秒口播（直接录）：
{script_block}
"""
        )

    ready_text = f"""# 今日可直接录制文案（30-40秒）

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
数据窗口：最近 {args.days} 天
数据新鲜度：约 {data_age_hours:.1f} 小时前更新
重点账号：{", ".join(target_accounts)}
今日生成栏目：{daily_series_labels}

使用说明：
1. 每条脚本直接照读即可。
2. 句尾按标点停顿，控制在 30-40 秒。
3. 优先使用“推荐标题”发布。

{chr(10).join(blocks)}
"""
    ready_path.write_text(ready_text, encoding="utf-8")
    print(f"可直接录制文案: {ready_path}")

    if args.library_output.strip():
        library_path = Path(args.library_output).resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        library_path = (BASE_DIR / "outputs" / f"script_library_{stamp}.md").resolve()
    library_path.parent.mkdir(parents=True, exist_ok=True)
    data_mode_text = "按天汇总" if aggregate_mode else "按视频明细"
    library_text = build_script_library_text(
        generated_paths=generated_paths,
        daily_series=daily_series,
        input_path=input_path,
        data_mode_text=data_mode_text,
        data_age_hours=data_age_hours,
        days=args.days,
    )
    library_path.write_text(library_text, encoding="utf-8")
    print(f"新奇特脚本库: {library_path}")

    for series in daily_series:
        if series in generated_paths:
            print(f"{series_label(series)} 文案: {generated_paths[series]}")


if __name__ == "__main__":
    main()
