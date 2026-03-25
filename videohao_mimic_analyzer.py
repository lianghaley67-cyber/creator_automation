from __future__ import annotations

import argparse
import csv
import math
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any

from shared import BASE_DIR, REPORT_DIR


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="分析微信视频号数据并生成仿写策略（标题+30秒脚本）"
    )
    parser.add_argument(
        "--input",
        type=str,
        default=str(BASE_DIR / "data" / "videohao_posts.csv"),
        help="视频号导出数据 CSV 路径",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="",
        help="输出报告路径，默认 reports/videohao_mimic_时间戳.md",
    )
    parser.add_argument("--top", type=int, default=30, help="用于风格抽样的高表现内容数量")
    return parser.parse_args()


COLUMN_ALIASES = {
    "title": ["title", "标题", "作品标题", "视频标题", "内容标题"],
    "publish_time": ["publish_time", "发布时间", "发布日期", "date", "publish_date"],
    "duration_sec": ["duration_sec", "duration", "时长", "视频时长", "时长(s)", "视频时长(s)"],
    "play_count": ["play_count", "play", "播放量", "播放", "观看次数", "曝光量", "阅读量"],
    "like_count": ["like_count", "like", "点赞数", "点赞"],
    "comment_count": ["comment_count", "comment", "评论数", "评论"],
    "share_count": ["share_count", "share", "转发数", "转发", "分享数", "分享"],
    "follow_count": ["follow_count", "follow", "新增关注", "涨粉", "关注数", "粉丝增长"],
    "completion_rate": ["completion_rate", "完播率", "看完率"],
    "avg_watch_sec": ["avg_watch_sec", "平均观看时长", "人均观看时长", "平均播放时长"],
}


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


def zscore(values: list[float]) -> list[float]:
    if not values:
        return []
    mu = mean(values)
    variance = mean([(v - mu) ** 2 for v in values])
    std = math.sqrt(variance)
    if std == 0:
        return [0.0 for _ in values]
    return [(v - mu) / std for v in values]


def detect_hook_type(title: str) -> str:
    t = title or ""
    if "？" in t or "?" in t:
        return "提问钩子"
    if re.search(r"\d+", t):
        return "数字承诺"
    if re.search(r"(不是|而是|别再|先|立刻|马上)", t):
        return "反常识/命令"
    if re.search(r"(焦虑|失业|降薪|没钱|内耗)", t):
        return "痛点共鸣"
    return "陈述判断"


def duration_bucket(sec: float) -> str:
    if sec <= 20:
        return "0-20秒"
    if sec <= 35:
        return "21-35秒"
    if sec <= 60:
        return "36-60秒"
    return "60秒以上"


def detect_theme(title: str) -> str:
    t = (title or "").lower()
    if any(x in t for x in ["焦虑", "失业", "降薪", "压力", "经济"]):
        return "anti_anxiety"
    if any(x in t for x in ["自救", "副业", "收入", "现金流", "找工作", "转行"]):
        return "self_rescue"
    if any(x in t for x in ["自媒体", "视频号", "公众号", "口播", "涨粉", "选题", "起号"]):
        return "self_media"
    return "mixed"


def pick_best_duration(top_rows: list[dict[str, Any]]) -> str:
    groups: dict[str, list[float]] = defaultdict(list)
    for r in top_rows:
        b = duration_bucket(r["duration_sec"])
        groups[b].append(r["score"])
    if not groups:
        return "21-35秒"
    return sorted(groups.items(), key=lambda x: mean(x[1]), reverse=True)[0][0]


def render_title_bank() -> dict[str, list[str]]:
    anti_anxiety = [
        "经济不景气时，先别拼命，先止损",
        "焦虑上头时，普通人先做这3步",
        "降薪后最稳的自救动作，不是加班",
        "你不是不努力，是在低回报里内耗",
        "失业风险变高，先把这张清单做完",
        "普通人抗焦虑：先稳现金流，再谈理想",
        "别被情绪推着走，先做7天行动版",
        "越焦虑越乱花钱？先改这一个动作",
        "经济压力下，先保命再翻盘",
        "晚上总焦虑？睡前做这3件小事",
        "普通人最该补的，不是鸡血，是决策力",
        "不景气不是终点，先把生活稳住",
    ]
    self_rescue = [
        "普通人30天自救：先做这3件事",
        "收入不稳时，先建第二条现金流",
        "副业一直没结果，通常卡在这一步",
        "没资源没人脉，普通人也能自救",
        "先活下来，再活得好：行动版清单",
        "穷忙的根源不是懒，是路径错了",
        "普通人翻身，不靠运气靠复利",
        "自救第一步：把支出和时间都看见",
        "7天验证一个副业值不值得做",
        "别再盲学了，先学能变现的技能",
        "从0到1自救：一周一张复盘表",
        "钱少更要做对顺序：止损、增能、试错",
    ]
    self_media = [
        "0粉丝起号，先别追爆款",
        "普通人做视频号，第一周这样发",
        "不会口播？先用这套短句脚本",
        "没人看不是你不行，是定位太散",
        "做自媒体最稳的增长法，不靠运气",
        "普通人起号：先解决一个具体问题",
        "每天30分钟，也能稳定更新",
        "选题总卡壳？直接套这个公式",
        "做内容先做信任，不先做流量",
        "涨粉慢不可怕，方向错才可怕",
        "公众号+视频号联动，普通人这样做",
        "自媒体变现前，先把这3个指标跑通",
    ]
    return {
        "anti_anxiety": anti_anxiety,
        "self_rescue": self_rescue,
        "self_media": self_media,
    }


def render_script_pack(best_duration: str) -> dict[str, str]:
    anti = f"""### 经济下行抗焦虑（30秒）
- 0-3秒：这两年你累，不是你弱，是环境变了。
- 3-10秒：很多人一焦虑就乱学、乱花、乱选，越忙越慌。
- 10-22秒：今天只做三步：列固定支出；砍一项无效开销；每天20分钟做一个可变现动作。
- 22-27秒：先把下滑停住，比盲目冲刺更重要。
- 27-30秒：想要清单版，评论“自救”，我发你。
- 节奏建议：主打 {best_duration}，每句 8-15 字，句尾留 0.3 秒停顿。"""

    rescue = f"""### 普通人自救（30秒）
- 0-3秒：普通人自救，不是逆天改命，是先活稳。
- 3-10秒：你现在最怕的，不是慢，是今天没动作。
- 10-22秒：三步走：止损现金流；补一个能变现技能；小规模测试副项目。
- 22-27秒：别等准备好再开始，边做边改才是出路。
- 27-30秒：要我那张30天行动表，评论“30天”。
- 节奏建议：主打 {best_duration}，动作句用“第一/第二/第三”提升跟读感。"""

    media = f"""### 普通人做自媒体（30秒）
- 0-3秒：0粉丝起号，先别想爆。
- 3-10秒：多数人做不起来，不是内容差，是定位散。
- 10-22秒：三步：一句话定位；准备20个问题型选题；连续7天固定时间发。
- 22-27秒：你要的不是一条爆款，是可持续输出。
- 27-30秒：评论“起号”，我把模板发你。
- 节奏建议：主打 {best_duration}，关键词重音放在“定位/选题/连续”。"""

    return {
        "anti_anxiety": anti,
        "self_rescue": rescue,
        "self_media": media,
    }


def load_rows(path: Path) -> tuple[list[dict[str, Any]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    return rows, fieldnames


def build_report(rows: list[dict[str, Any]], fieldnames: list[str], top_n: int) -> str:
    col_title = find_column(fieldnames, "title")
    col_time = find_column(fieldnames, "publish_time")
    col_duration = find_column(fieldnames, "duration_sec")
    col_play = find_column(fieldnames, "play_count")
    col_like = find_column(fieldnames, "like_count")
    col_comment = find_column(fieldnames, "comment_count")
    col_share = find_column(fieldnames, "share_count")
    col_follow = find_column(fieldnames, "follow_count")
    col_completion = find_column(fieldnames, "completion_rate")
    col_watch = find_column(fieldnames, "avg_watch_sec")

    if not col_title or not col_play:
        raise ValueError("CSV 至少需要包含标题和播放量列（如 标题/播放量）。")

    parsed: list[dict[str, Any]] = []
    for r in rows:
        title = str(r.get(col_title, "")).strip()
        if not title:
            continue
        play = to_float(r.get(col_play))
        like = to_float(r.get(col_like)) if col_like else 0.0
        comment = to_float(r.get(col_comment)) if col_comment else 0.0
        share = to_float(r.get(col_share)) if col_share else 0.0
        follow = to_float(r.get(col_follow)) if col_follow else 0.0
        completion = to_float(r.get(col_completion)) if col_completion else 0.0
        if completion > 1.0:
            completion = completion / 100.0
        avg_watch_sec = to_float(r.get(col_watch)) if col_watch else 0.0
        duration_sec = to_float(r.get(col_duration)) if col_duration else 30.0
        pub_dt = parse_datetime(str(r.get(col_time, ""))) if col_time else None

        eng = (like + comment + share) / play if play > 0 else 0.0
        follow_per_1k = (follow / play * 1000.0) if play > 0 else 0.0
        parsed.append(
            {
                "title": title,
                "publish_dt": pub_dt,
                "duration_sec": duration_sec,
                "play": play,
                "like": like,
                "comment": comment,
                "share": share,
                "follow": follow,
                "completion": completion,
                "avg_watch_sec": avg_watch_sec,
                "eng_rate": eng,
                "follow_per_1k": follow_per_1k,
                "hook_type": detect_hook_type(title),
                "theme": detect_theme(title),
            }
        )

    if not parsed:
        raise ValueError("CSV 中未解析到有效数据。")

    zs_eng = zscore([x["eng_rate"] for x in parsed])
    zs_play = zscore([x["play"] for x in parsed])
    zs_follow = zscore([x["follow_per_1k"] for x in parsed])
    for i, row in enumerate(parsed):
        row["score"] = (
            0.45 * zs_eng[i]
            + 0.2 * row["completion"]
            + 0.25 * zs_follow[i]
            + 0.1 * zs_play[i]
        )

    parsed.sort(key=lambda x: x["score"], reverse=True)
    top_rows = parsed[: max(1, min(top_n, len(parsed)))]

    hook_counter = Counter([x["hook_type"] for x in top_rows])
    theme_counter = Counter([x["theme"] for x in top_rows])
    duration_group_scores: dict[str, list[float]] = defaultdict(list)
    for x in top_rows:
        duration_group_scores[duration_bucket(x["duration_sec"])].append(x["score"])

    best_duration = pick_best_duration(top_rows)
    best_hours = Counter([x["publish_dt"].hour for x in top_rows if x["publish_dt"] is not None]).most_common(3)
    best_hours_txt = "、".join([f"{h}:00" for h, _ in best_hours]) if best_hours else "暂无（缺发布时间列）"

    title_bank = render_title_bank()
    scripts = render_script_pack(best_duration)

    top_examples = "\n".join(
        [
            f"{idx}. {x['title']} | 分数={x['score']:.3f} | 完播={x['completion']:.2%} | 互动率={x['eng_rate']:.2%}"
            for idx, x in enumerate(top_rows[:10], start=1)
        ]
    )

    duration_lines = []
    for bucket, scores in sorted(duration_group_scores.items(), key=lambda kv: mean(kv[1]), reverse=True):
        duration_lines.append(f"- {bucket}：样本{len(scores)}，平均分{mean(scores):.3f}")
    duration_block = "\n".join(duration_lines) if duration_lines else "- 无"

    hook_lines = "\n".join([f"- {k}：{v}" for k, v in hook_counter.most_common()]) or "- 无"
    theme_lines = "\n".join([f"- {k}：{v}" for k, v in theme_counter.most_common()]) or "- 无"

    report = f"""# 微信视频号仿写分析报告

生成时间：{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
样本总量：{len(parsed)}
高表现样本：Top {len(top_rows)}

## 账号节奏结论（用于模仿）
- 推荐时长区间：**{best_duration}**
- 推荐发布时间段（按高表现样本）：**{best_hours_txt}**
- 建议结构：3秒钩子 -> 7秒共鸣 -> 12秒方法 -> 5秒提醒 -> 3秒CTA

## 高表现内容特征
### 钩子类型分布
{hook_lines}

### 主题分布
{theme_lines}

### 时长表现
{duration_block}

## 高表现样本（前10）
{top_examples}

## 标题库（可直接用）
### 1) 经济下行抗焦虑
{chr(10).join([f"- {x}" for x in title_bank['anti_anxiety']])}

### 2) 普通人自救
{chr(10).join([f"- {x}" for x in title_bank['self_rescue']])}

### 3) 普通人做自媒体
{chr(10).join([f"- {x}" for x in title_bank['self_media']])}

## 30秒脚本（可直接拍）
{scripts['anti_anxiety']}

{scripts['self_rescue']}

{scripts['self_media']}

## 执行建议
1. 每周至少发 6 条：三大主题各 2 条，保持节奏稳定。
2. 每条视频仅讲 1 个痛点 + 3 个动作，避免信息过载。
3. 复盘优先看：完播率、互动率、千次播放涨粉，不先看总播放。
"""
    return report


def main() -> None:
    args = parse_args()
    input_path = Path(args.input).resolve()
    if not input_path.exists():
        raise FileNotFoundError(
            f"未找到输入文件：{input_path}\n请先导出视频号数据为 CSV，并放到该路径。"
        )

    rows, fieldnames = load_rows(input_path)
    report_text = build_report(rows, fieldnames, args.top)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    if args.output.strip():
        out_path = Path(args.output).resolve()
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_path = REPORT_DIR / f"videohao_mimic_{stamp}.md"

    out_path.write_text(report_text, encoding="utf-8")
    print(f"报告已生成: {out_path}")


if __name__ == "__main__":
    main()
