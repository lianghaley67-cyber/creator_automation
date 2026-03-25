from __future__ import annotations

import argparse
import html
import re
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from shared import (
    TOPICS_CSV,
    TOPICS_HEADERS,
    apply_proxy_settings,
    append_csv_row,
    ensure_workspace,
    load_config,
    make_topic_id,
    normalize_title,
    now_str,
    read_csv,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="抓取热点并生成可用选题池")
    parser.add_argument("--config", type=str, default=None, help="配置文件路径，默认使用 config.json")
    parser.add_argument(
        "--max-topics",
        type=int,
        default=None,
        help="本次最多新增多少个选题（覆盖配置文件中的 max_topics_total）",
    )
    return parser.parse_args()


def configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:  # noqa: BLE001
            pass


def render_template(url_template: str, keyword: str) -> str:
    encoded = urllib.parse.quote(keyword)
    return url_template.format(keyword=encoded, keyword_raw=keyword)


def parse_pub_date(raw_date: str) -> tuple[str, float]:
    if not raw_date:
        return "", 72.0
    try:
        dt = parsedate_to_datetime(raw_date)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        local_dt = dt.astimezone()
        hours_old = max(0.0, (datetime.now().astimezone() - local_dt).total_seconds() / 3600)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S"), hours_old
    except (TypeError, ValueError):
        return "", 72.0


def fetch_rss(url: str, timeout: int = 18) -> list[dict[str, Any]]:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (ContentAutomationBot/1.0)"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = resp.read()
    root = ET.fromstring(data)
    items = []
    for item in root.findall(".//item"):
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        source = (item.findtext("source") or "").strip()
        pub_date = (item.findtext("pubDate") or "").strip()

        if not source and link:
            parsed = urllib.parse.urlparse(link)
            source = parsed.netloc

        if title:
            items.append(
                {
                    "title": html.unescape(title),
                    "link": link,
                    "source": source,
                    "pub_date": pub_date,
                }
            )
    return items


def infer_angle(title: str) -> str:
    t = title.lower()
    if re.search(r"(发布|更新|上线|政策|新规|涨价|降价|通告)", t):
        return "做信息差解读：这件事对普通人有什么直接影响"
    if re.search(r"\d", t):
        return "做清单型内容：拆成 3-5 条具体可执行动作"
    if re.search(r"(案例|采访|数据|报告|研究)", t):
        return "做案例复盘：方法-过程-结果-可复制点"
    return "做观点型内容：趋势判断 + 反常识结论 + 行动建议"


def score_item(title: str, hours_old: float, keywords: list[str], seen_norm_titles: set[str]) -> float:
    lower_title = title.lower()
    keyword_hits = sum(1 for kw in keywords if kw.lower() in lower_title)
    recency_score = 2.2 / (1 + hours_old / 24)
    novelty_score = 0.0 if normalize_title(title) in seen_norm_titles else 1.3
    base = 1.0
    return round(base + keyword_hits * 1.8 + recency_score + novelty_score, 3)


def main() -> None:
    configure_console()
    args = parse_args()
    ensure_workspace()
    config = load_config(args.config)
    proxy = apply_proxy_settings(config)
    if proxy:
        print(f"[INFO] 已启用代理: {proxy}")

    topic_cfg = config.get("topic_collection", {})
    keywords = [str(x).strip() for x in topic_cfg.get("keywords", []) if str(x).strip()]
    templates = [str(x).strip() for x in topic_cfg.get("rss_query_templates", []) if str(x).strip()]
    max_topics_total = args.max_topics or int(topic_cfg.get("max_topics_total", 20))

    if not keywords:
        raise ValueError("配置项 topic_collection.keywords 不能为空。")
    if not templates:
        raise ValueError("配置项 topic_collection.rss_query_templates 不能为空。")

    existing_rows = read_csv(TOPICS_CSV)
    existing_ids = {row.get("topic_id", "") for row in existing_rows}
    seen_norm_titles = {normalize_title(row.get("title", "")) for row in existing_rows if row.get("title")}

    candidates: list[dict[str, Any]] = []
    for keyword in keywords:
        for template in templates:
            url = render_template(template, keyword)
            try:
                rss_items = fetch_rss(url)
            except Exception as exc:  # noqa: BLE001
                print(f"[WARN] 抓取失败：{url} -> {exc}")
                continue
            for item in rss_items:
                title = item["title"]
                topic_id = make_topic_id(title)
                if topic_id in existing_ids:
                    continue
                published_at, hours_old = parse_pub_date(item.get("pub_date", ""))
                score = score_item(title, hours_old, keywords, seen_norm_titles)
                candidates.append(
                    {
                        "topic_id": topic_id,
                        "collected_at": now_str(),
                        "title": title,
                        "angle_hint": infer_angle(title),
                        "source": item.get("source", ""),
                        "link": item.get("link", ""),
                        "published_at": published_at,
                        "keyword": keyword,
                        "score": score,
                        "status": "NEW",
                        "used_at": "",
                    }
                )

    # 本次内去重（不同源可能重复）
    deduped: dict[str, dict[str, Any]] = {}
    for row in candidates:
        rid = row["topic_id"]
        old = deduped.get(rid)
        if old is None or float(row["score"]) > float(old["score"]):
            deduped[rid] = row

    selected = sorted(deduped.values(), key=lambda x: float(x["score"]), reverse=True)[:max_topics_total]
    for row in selected:
        append_csv_row(TOPICS_CSV, TOPICS_HEADERS, row)

    print(f"新增选题: {len(selected)} 条")
    if selected:
        print("Top 5 选题：")
        for idx, row in enumerate(selected[:5], start=1):
            print(f"{idx}. {row['title']} | score={row['score']} | 来源={row['source']}")
    print(f"输出文件: {Path(TOPICS_CSV).resolve()}")


if __name__ == "__main__":
    main()
