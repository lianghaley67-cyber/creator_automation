from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterator


BASE_DIR = Path(__file__).resolve().parents[1]
# 支持通过环境变量覆盖工作室数据目录
_studio_dir_override = os.environ.get("CREATOR_STUDIO_DATA_DIR", "").strip()
STUDIO_DIR = Path(_studio_dir_override).expanduser() if _studio_dir_override else BASE_DIR / "studio_runtime"
UPLOADS_DIR = STUDIO_DIR / "uploads"          # 用户上传文件存储目录
OUTPUT_DIR = STUDIO_DIR / "outputs"           # 生成结果输出目录
OUTPUTS_DIR = OUTPUT_DIR                      # 兼容旧模块导入名称
REFERENCES_DIR = STUDIO_DIR / "references"    # 参考资源目录
PORTRAITS_DIR = REFERENCES_DIR / "portraits"  # 人脸肖像目录
VOICE_REFERENCES_DIR = REFERENCES_DIR / "voice_samples"  # 语音参考目录
STATE_FILE = STUDIO_DIR / "studio_state.json" # 状态持久化文件
DATABASE_FILE = STUDIO_DIR / "studio.db"       # SQLite 状态数据库

# 默认状态结构定义
DEFAULT_STATE: dict[str, Any] = {
    "uploads": [],              # 上传记录
    "analyses": [],             # 分析记录
    "persona": None,            # 人设数据
    "jobs": [],                 # 任务记录
    "schedules": [],            # 定时任务
    "wechat_materials": [],     # 微信素材
    "wechat_callback_events": [], # 微信回调事件
    "distribution_tasks": [],   # 多平台分发任务
    "integration_settings": {}, # 渠道配置（不保存 AppSecret）
    "ai_trends": [],            # AI趋势数据
    "obsidian_archives": [],    # Obsidian归档
    "stock_watchlist": [],      # 股票自选与预警
    "stock_analysis_history": [], # 股票AI分析历史
    "stock_skill_runs": [],     # 股票Skill运行历史
    "avatar_settings": {},      # 数字人设置
}


def now_iso() -> str:
    """
    获取当前时间的ISO格式字符串

    Returns:
        ISO 8601格式的时间字符串，如 "2024-01-15T10:30:00"
    """
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix: str) -> str:
    """
    生成带前缀的唯一ID

    Args:
        prefix: ID前缀，用于区分不同类型的记录

    Returns:
        格式为 "prefix_uuid前12位" 的唯一标识

    示例: "upload_a1b2c3d4e5f6"
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def ensure_workspace() -> None:
    """
    确保工作室目录结构存在

    创建所有必要的目录，在应用启动时调用。
    """
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_REFERENCES_DIR.mkdir(parents=True, exist_ok=True)


def _default_state() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_STATE))


def to_media_url(path: str | Path) -> str:
    """
    将本地文件路径转换为可访问的URL路径

    Args:
        path: 本地文件路径

    Returns:
        相对于STUDIO_DIR的URL路径，格式为 "/studio-files/xxx"

    该函数用于生成前端可访问的媒体文件URL。
    """
    resolved = Path(path).resolve()
    relative = resolved.relative_to(STUDIO_DIR.resolve()).as_posix()
    return f"/studio-files/{relative}"


class StudioStore:
    """
    工作室状态存储管理器

    提供线程安全的状态读写操作，基于 SQLite 持久化。
    支持事务性的状态修改操作。
    """

    def __init__(self) -> None:
        """初始化存储管理器，创建数据库并迁移旧 JSON 数据。"""
        ensure_workspace()
        self._lock = threading.Lock()
        self._initialize_database()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(DATABASE_FILE, timeout=30)
        try:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute("PRAGMA synchronous=NORMAL")
            connection.execute("PRAGMA busy_timeout=30000")
            yield connection
        finally:
            connection.close()

    def _initialize_database(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS state_sections (
                    section TEXT PRIMARY KEY,
                    value_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            row_count = int(
                connection.execute("SELECT COUNT(*) FROM state_sections").fetchone()[0]
            )
            if row_count:
                return

            state = _default_state()
            if STATE_FILE.exists():
                raw = STATE_FILE.read_text(encoding="utf-8-sig")
                if raw.strip():
                    loaded = json.loads(raw)
                    if not isinstance(loaded, dict):
                        raise ValueError(f"旧状态文件格式错误: {STATE_FILE}")
                    state.update(loaded)

            self._save_to_connection(connection, state)
            connection.commit()

    def _load_from_connection(self, connection: sqlite3.Connection) -> dict[str, Any]:
        state = _default_state()
        rows = connection.execute(
            "SELECT section, value_json FROM state_sections"
        ).fetchall()
        for section, value_json in rows:
            state[section] = json.loads(value_json)
        return state

    def _save_to_connection(
        self, connection: sqlite3.Connection, state: dict[str, Any]
    ) -> None:
        timestamp = now_iso()
        for section, value in state.items():
            connection.execute(
                """
                INSERT INTO state_sections(section, value_json, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(section) DO UPDATE SET
                    value_json = excluded.value_json,
                    updated_at = excluded.updated_at
                """,
                (section, json.dumps(value, ensure_ascii=False), timestamp),
            )

    def get_state(self) -> dict[str, Any]:
        """
        获取完整状态（线程安全）

        Returns:
            当前完整状态字典的副本
        """
        with self._lock:
            with self._connect() as connection:
                return self._load_from_connection(connection)

    def mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        """
        事务性修改状态（线程安全）

        Args:
            fn: 接收状态字典并返回结果的函数，可在函数中修改状态

        Returns:
            fn函数的返回值

        使用示例:
            result = store.mutate(lambda state: state['counter'] += 1)

        该方法保证读写操作的原子性，避免并发冲突。
        """
        with self._lock:
            with self._connect() as connection:
                connection.execute("BEGIN IMMEDIATE")
                state = self._load_from_connection(connection)
                result = fn(state)
                self._save_to_connection(connection, state)
                connection.commit()
                return result

    def list_section(self, section: str) -> list[dict[str, Any]]:
        """
        获取指定分区的所有记录

        Args:
            section: 分区名称（如 "uploads", "jobs", "analyses"）

        Returns:
            该分区的记录列表副本
        """
        state = self.get_state()
        return list(state.get(section, []))

    def get_persona(self) -> dict[str, Any] | None:
        """
        获取当前人设数据

        Returns:
            人设字典，如果不存在则返回None
        """
        state = self.get_state()
        persona = state.get("persona")
        return dict(persona) if isinstance(persona, dict) else None

    def set_persona(self, persona: dict[str, Any]) -> dict[str, Any]:
        """
        设置人设数据

        Args:
            persona: 人设字典

        Returns:
            设置后的人设数据
        """
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            state["persona"] = persona
            return persona

        return self.mutate(updater)

    def add_record(self, section: str, record: dict[str, Any]) -> dict[str, Any]:
        """
        向指定分区添加记录

        Args:
            section: 分区名称
            record: 要添加的记录字典

        Returns:
            添加后的记录
        """
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            state.setdefault(section, []).append(record)
            return record

        return self.mutate(updater)

    def find_record(self, section: str, record_id: str) -> dict[str, Any] | None:
        """
        根据ID查找记录

        Args:
            section: 分区名称
            record_id: 记录ID

        Returns:
            找到的记录，如果未找到返回None
        """
        state = self.get_state()
        for record in state.get(section, []):
            if str(record.get("id")) == record_id:
                return dict(record)
        return None

    def update_record(self, section: str, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        """
        更新指定记录

        Args:
            section: 分区名称
            record_id: 记录ID
            patch: 要更新的字段键值对

        Returns:
            更新后的完整记录

        Raises:
            KeyError: 记录不存在时抛出
        """
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            for record in state.get(section, []):
                if str(record.get("id")) == record_id:
                    record.update(patch)
                    return dict(record)
            raise KeyError(f"{section} record not found: {record_id}")

        return self.mutate(updater)
