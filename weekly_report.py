from __future__ import annotations

import argparse
import math
import re
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from shared import (
    HISTORY_CSV,
    REPORT_DIR,
    TOPICS_CSV,
    ensure_workspace,
    read_csv,
    safe_float,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="生成内容复盘周报")
    parser.add_argument("--days", type=int, default=7, help="统计最近 N 天，默认 7")
    parser.add_argument("--top", type=int, default=5, help="展示 Top 内容条数，默认 5")
    return parser.parse_args()


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def parse_time(raw: str) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None


def extract_keywords(text: str) -> list[str]:
    words = re.findall(r"[A-Za-z0-9\u4e00-\u9fff]{2,}", text)
    stop = {"我们", "你们", "他们", "这个", "那个", "一个", "可以", "就是", "以及", "如何"}
    return [w for w in words if w not in stop]


def safe_div(a: float, b: float) -> float:
    return 0.0 if b == 0 else a / b


def main() -> None:
    configure_console()
    args = parse_args()
    ensure_workspace()

    now = datetime.now()
    cutoff = now - timedelta(days=args.days)
    all_rows = read_csv(HISTORY_CSV)
    rows: list[dict[str, str]] = []
    for row in all_rows:
        created_at = parse_time(row.get("created_at", ""))
        if created_at and created_at >= cutoff:
            rows.append(row)

    if not rows:
        print(f"最近 {args.days} 天没有发布记录。请先运行 content_generator.py 并补充数据。")
        return

    posts = len(rows)
    total_reads = sum(safe_float(r.get("read_count")) for r in rows)
    total_leads = sum(safe_float(r.get("lead_count")) for r in rows)
    avg_completion = safe_div(sum(safe_float(r.get("completion_rate")) for r in rows), posts)
    avg_read_time = safe_div(sum(safe_float(r.get("avg_read_time")) for r in rows), posts)
    avg_like = safe_div(sum(safe_float(r.get("like_count")) for r in rows), posts)
    lead_per_1000 = safe_div(total_leads * 1000, total_reads)

    top_by_read = sorted(rows, key=lambda x: safe_float(x.get("read_count")), reverse=True)[: args.top]
    top_by_lead = sorted(rows, key=lambda x: safe_float(x.get("lead_count")), reverse=True)[: args.top]

    keyword_counter = Counter()
    median_lead = sorted(safe_float(r.get("lead_count")) for r in rows)[math.floor((posts - 1) / 2)]
    for row in rows:
        if safe_float(row.get("lead_count")) >= median_lead:
            keyword_counter.update(extract_keywords(row.get("topic", "")))
            keyword_counter.update(extract_keywords(row.get("primary_title", "")))
    hot_keywords = [kw for kw, _ in keyword_counter.most_common(8)]

    topic_rows = read_csv(TOPICS_CSV)
    next_topics = [
        r
        for r in sorted(topic_rows, key=lambda x: safe_float(x.get("score")), reverse=True)
        if (r.get("status") or "").upper() == "NEW"
    ][:5]

    report_title = f"内容周复盘（{cutoff.strftime('%Y-%m-%d')} ~ {now.strftime('%Y-%m-%d')}）"
    report_body = [f"# {report_title}", ""]
    report_body.append("## 核心数据")
    report_body.append(f"- 发布篇数：{posts}")
    report_body.append(f"- 总阅读：{int(total_reads)}")
    report_body.append(f"- 总线索（私信/加微/成交前动作）：{int(total_leads)}")
    report_body.append(f"- 千次阅读线索数：{lead_per_1000:.2f}")
    report_body.append(f"- 平均完播/读完率：{avg_completion:.2f}%")
    report_body.append(f"- 平均阅读时长：{avg_read_time:.2f} 秒")
    report_body.append(f"- 平均点赞：{avg_like:.2f}")
    report_body.append("")

    report_body.append("## 阅读 Top 内容")
    for idx, row in enumerate(top_by_read, start=1):
        report_body.append(
            f"{idx}. {row.get('primary_title', row.get('topic', ''))} | "
            f"阅读={safe_float(row.get('read_count')):.0f} | "
            f"线索={safe_float(row.get('lead_count')):.0f}"
        )
    report_body.append("")

    report_body.append("## 线索 Top 内容")
    for idx, row in enumerate(top_by_lead, start=1):
        report_body.append(
            f"{idx}. {row.get('primary_title', row.get('topic', ''))} | "
            f"线索={safe_float(row.get('lead_count')):.0f} | "
            f"完播率={safe_float(row.get('completion_rate')):.2f}%"
        )
    report_body.append("")

    report_body.append("## 下周优先关键词")
    if hot_keywords:
        report_body.append("- " + " / ".join(hot_keywords))
    else:
        report_body.append("- 暂无明显关键词，请补充更多发布数据后再判断。")
    report_body.append("")

    report_body.append("## 建议动作")
    report_body.append("1. 把“线索 Top 内容”的结构重写 2 个新角度继续测试。")
    report_body.append("2. 阅读高但线索低的内容，强化结尾 CTA 和私信诱因。")
    report_body.append("3. 对完播率低于平均值的内容，压缩开头 10 秒信息密度。")
    report_body.append("")

    report_body.append("## 下周候选选题（自动从选题池提取）")
    if next_topics:
        for idx, row in enumerate(next_topics, start=1):
            report_body.append(
                f"{idx}. {row.get('title', '')} | score={safe_float(row.get('score')):.2f} | "
                f"角度：{row.get('angle_hint', '')}"
            )
    else:
        report_body.append("- 当前没有 NEW 选题，请先运行 topic_collector.py。")

    report_text = "\n".join(report_body).strip() + "\n"
    output_path = REPORT_DIR / f"weekly_report_{now.strftime('%Y%m%d_%H%M%S')}.md"
    output_path.write_text(report_text, encoding="utf-8")

    print(f"周报已生成: {Path(output_path).resolve()}")


if __name__ == "__main__":
    main()
