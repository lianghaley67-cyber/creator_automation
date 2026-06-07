from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

# 项目基础目录配置
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"      # 数据存储目录（选题、历史记录等）
OUTPUT_DIR = BASE_DIR / "outputs"  # 内容输出目录（生成的文案等）
REPORT_DIR = BASE_DIR / "reports"  # 报告输出目录（周报等）

# CSV文件路径
TOPICS_CSV = DATA_DIR / "topics.csv"      # 选题池CSV
HISTORY_CSV = DATA_DIR / "content_history.csv"  # 内容历史记录CSV

# topics.csv 字段定义
TOPICS_HEADERS = [
    "topic_id",      # 选题唯一标识
    "collected_at",  # 采集时间
    "title",         # 选题标题
    "angle_hint",    # 切入角度提示
    "source",        # 来源渠道
    "link",          # 原文链接
    "published_at",  # 原文发布时间
    "keyword",       # 关联关键词
    "score",         # 评分（用于排序）
    "status",        # 状态（NEW/USED/ARCHIVED）
    "used_at",       # 使用时间
]

# content_history.csv 字段定义
HISTORY_HEADERS = [
    "content_id",       # 内容唯一标识
    "created_at",       # 创建时间
    "topic",            # 选题标题
    "primary_title",    # 主标题
    "output_file",      # 输出文件路径
    "channel",          # 发布渠道
    "read_count",       # 阅读数
    "avg_read_time",    # 平均阅读时长（秒）
    "like_count",       # 点赞数
    "share_count",      # 转发数
    "lead_count",       # 私信/加微等线索数
    "completion_rate",  # 完播/读完率（百分比）
]


def ensure_workspace() -> None:
    """
    确保工作目录结构存在，创建必要的目录和CSV文件
    
    该函数在程序启动时调用，确保所有必要的目录和文件都已创建，
    避免后续操作因文件不存在而报错。
    """
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    _ensure_csv(TOPICS_CSV, TOPICS_HEADERS)
    _ensure_csv(HISTORY_CSV, HISTORY_HEADERS)


def _ensure_csv(path: Path, headers: list[str]) -> None:
    """
    确保CSV文件存在，不存在则创建并写入表头
    
    Args:
        path: CSV文件路径
        headers: 表头字段列表
    """
    if path.exists():
        return
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()


def load_config(config_path: str | None = None) -> dict[str, Any]:
    """
    加载配置文件
    
    Args:
        config_path: 配置文件路径，默认为项目根目录的config.json
    
    Returns:
        配置字典，包含账号配置、网络代理、内容策略等
    
    Raises:
        FileNotFoundError: 配置文件不存在时抛出
    """
    path = Path(config_path) if config_path else BASE_DIR / "config.json"
    if not path.exists():
        raise FileNotFoundError(
            f"未找到配置文件: {path}\n请先复制 config.example.json 为 config.json 再修改。"
        )
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def apply_proxy_settings(config: dict[str, Any]) -> str:
    """
    根据配置设置网络代理环境变量
    
    Args:
        config: 配置字典
    
    Returns:
        应用的代理URL，如果未配置则返回空字符串
    
    该函数会设置以下环境变量：
    - HTTP_PROXY / HTTPS_PROXY / http_proxy / https_proxy: 代理地址
    - NO_PROXY / no_proxy: 不走代理的域名列表
    """
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
    """
    读取CSV文件内容
    
    Args:
        path: CSV文件路径
    
    Returns:
        包含所有行的字典列表，每行的key为表头字段名
    
    如果文件不存在，返回空列表。
    """
    if not path.exists():
        return []
    with path.open("r", newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def append_csv_row(path: Path, fieldnames: list[str], row: dict[str, Any]) -> None:
    """
    向CSV文件追加一行数据
    
    Args:
        path: CSV文件路径
        fieldnames: 表头字段列表，用于确保数据格式正确
        row: 要追加的行数据字典
    
    该函数会自动过滤掉不在fieldnames中的字段，并为缺失字段填充空字符串。
    """
    with path.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        safe_row = {k: row.get(k, "") for k in fieldnames}
        writer.writerow(safe_row)


def rewrite_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    """
    重写整个CSV文件（覆盖原有内容）
    
    Args:
        path: CSV文件路径
        fieldnames: 表头字段列表
        rows: 数据行列表
    
    该函数会先写入表头，然后逐行写入数据。
    """
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            safe_row = {k: row.get(k, "") for k in fieldnames}
            writer.writerow(safe_row)


def now_str() -> str:
    """
    获取当前时间的字符串表示
    
    Returns:
        格式化的时间字符串，格式为 "YYYY-MM-DD HH:MM:SS"
    """
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def normalize_title(text: str) -> str:
    """
    标准化标题文本，用于生成唯一标识
    
    Args:
        text: 原始标题文本
    
    Returns:
        标准化后的标题（小写、去除空白和特殊字符）
    
    处理步骤：
    1. 去除首尾空白并转为小写
    2. 移除所有空白字符
    3. 移除非单词和非中文字符
    """
    lowered = text.strip().lower()
    lowered = re.sub(r"\s+", "", lowered)
    lowered = re.sub(r"[^\w\u4e00-\u9fff]", "", lowered)
    return lowered


def make_topic_id(title: str) -> str:
    """
    根据标题生成唯一的topic_id
    
    Args:
        title: 选题标题
    
    Returns:
        12位的SHA1哈希值作为唯一标识
    
    该函数通过对标题进行哈希运算生成唯一ID，确保相同标题生成相同的ID。
    """
    normalized = normalize_title(title) or title
    return hashlib.sha1(normalized.encode("utf-8")).hexdigest()[:12]


def slugify_for_filename(text: str, prefix: str = "topic") -> str:
    """
    将文本转换为适合文件名的格式
    
    Args:
        text: 原始文本
        prefix: 前缀，默认为"topic"
    
    Returns:
        适合作为文件名的字符串
    
    转换规则：
    1. 移除非字母数字字符，替换为连字符
    2. 移除连续的连字符
    3. 限制长度为24个字符
    4. 如果结果为空，使用SHA1哈希值作为备选
    """
    ascii_text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    ascii_text = re.sub(r"-{2,}", "-", ascii_text)[:24]
    if ascii_text:
        return ascii_text
    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return f"{prefix}-{digest}"


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    安全地将值转换为浮点数
    
    Args:
        value: 要转换的值
        default: 转换失败时返回的默认值，默认为0.0
    
    Returns:
        转换后的浮点数，或默认值
    
    如果输入为None、字符串无法转换为数字等情况，返回默认值。
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
