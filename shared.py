from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "outputs"
REPORT_DIR = BASE_DIR / "reports"

TOPICS_CSV = DATA_DIR / "topics.csv"
HISTORY_CSV = DATA_DIR / "content_history.csv"

TOPICS_HEADERS = [
    "topic_id",
    "collected_at",
    "title",
    "angle_hint",
    "source",
    "link",
    "published_at",
    "keyword",
    "score",
    "status",
    "used_at",
]

HISTORY_HEADERS = [
    "content_id",
    "created_at",
    "topic",
    "primary_title",
    "output_file",
    "channel",
    "read_count",
    "avg_read_time",
    "like_count",
    "share_count",
    "lead_count",
    "completion_rate",
]


def ensure_workspace() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_csv(TOPICS_CSV, TOPICS_HEADERS)
    _ensure_csv(HISTORY_CSV, HISTORY_HEADERS)


def _ensure_csv(path: Path, headers: list[str]) -> None:
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()


def load_config(config_path: str | None = None) -> dict[str, Any]:
    path = Path(config_path) if config_path else BASE_DIR / "config.json"
    if not path.exists():
        raise FileNotFoundError(
            f"未找到配置文件: {path}\n请先复制 config.example.json 为 config.json 再修改。"
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_proxy_settings(config: dict[str, Any]) -> str:
    network_cfg = config.get("network", {})
    if not isinstance(network_cfg, dict):
        return ""

    proxy_url = str(network_cfg.get("proxy_url", "")).strip()
    no_proxy = str(network_cfg.get("no_proxy", "")).strip()

    if proxy_url:
        for key in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            os.environ[key] = proxy_url
    if no_proxy:
        for key in ("NO_PROXY", "no_proxy"):
            os.environ[key] = no_proxy

    return proxy_url


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        safe_row = {k: row.get(k, "") for k in fieldnames}
        writer.writerow(safe_row)


def rewrite_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            safe_row = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(safe_row)


def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_title(text: str) -> str:
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", "", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]", "", lowered)
    return lowered


def make_topic_id(title: str) -> str:
    normalized = normalize_title(title) or title
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def slugify_for_filename(text: str, prefix: str = "topic") -> str:
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    ascii_text = re.sub(r"-{2,}", "-", ascii_text)[:24]
    if ascii_text:
        return ascii_text
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
