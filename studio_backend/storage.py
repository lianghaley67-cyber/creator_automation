from __future__ import annotations

import json
import os
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable


BASE_DIR = Path(__file__).resolve().parents[1]
_studio_dir_override = os.environ.get("CREATOR_STUDIO_DATA_DIR", "").strip()
STUDIO_DIR = Path(_studio_dir_override).expanduser() if _studio_dir_override else BASE_DIR / "studio_runtime"
UPLOADS_DIR = STUDIO_DIR / "uploads"
OUTPUTS_DIR = STUDIO_DIR / "outputs"
REFERENCES_DIR = STUDIO_DIR / "references"
PORTRAITS_DIR = REFERENCES_DIR / "portraits"
VOICE_REFERENCES_DIR = REFERENCES_DIR / "voice_samples"
STATE_FILE = STUDIO_DIR / "studio_state.json"

DEFAULT_STATE: dict[str, Any] = {
    "uploads": [],
    "analyses": [],
    "persona": None,
    "jobs": [],
    "schedules": [],
    "wechat_materials": [],
    "ai_trends": [],
    "obsidian_archives": [],
    "avatar_settings": {},
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def make_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def ensure_workspace() -> None:
    STUDIO_DIR.mkdir(parents=True, exist_ok=True)
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    PORTRAITS_DIR.mkdir(parents=True, exist_ok=True)
    VOICE_REFERENCES_DIR.mkdir(parents=True, exist_ok=True)
    if not STATE_FILE.exists():
        STATE_FILE.write_text(json.dumps(DEFAULT_STATE, ensure_ascii=False, indent=2), encoding="utf-8")


def to_media_url(path: str | Path) -> str:
    resolved = Path(path).resolve()
    relative = resolved.relative_to(STUDIO_DIR.resolve()).as_posix()
    return f"/studio-files/{relative}"


class StudioStore:
    def __init__(self) -> None:
        ensure_workspace()
        self._lock = threading.Lock()

    def _load_unlocked(self) -> dict[str, Any]:
        raw = STATE_FILE.read_text(encoding="utf-8-sig")
        if not raw.strip():
            return json.loads(json.dumps(DEFAULT_STATE))
        state = json.loads(raw)
        for key, value in DEFAULT_STATE.items():
            state.setdefault(key, [] if isinstance(value, list) else value)
        return state

    def _save_unlocked(self, state: dict[str, Any]) -> None:
        STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def get_state(self) -> dict[str, Any]:
        with self._lock:
            return self._load_unlocked()

    def mutate(self, fn: Callable[[dict[str, Any]], Any]) -> Any:
        with self._lock:
            state = self._load_unlocked()
            result = fn(state)
            self._save_unlocked(state)
            return result

    def list_section(self, section: str) -> list[dict[str, Any]]:
        state = self.get_state()
        return list(state.get(section, []))

    def get_persona(self) -> dict[str, Any] | None:
        state = self.get_state()
        persona = state.get("persona")
        return dict(persona) if isinstance(persona, dict) else None

    def set_persona(self, persona: dict[str, Any]) -> dict[str, Any]:
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            state["persona"] = persona
            return persona

        return self.mutate(updater)

    def add_record(self, section: str, record: dict[str, Any]) -> dict[str, Any]:
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            state.setdefault(section, []).append(record)
            return record

        return self.mutate(updater)

    def find_record(self, section: str, record_id: str) -> dict[str, Any] | None:
        state = self.get_state()
        for record in state.get(section, []):
            if str(record.get("id")) == record_id:
                return dict(record)
        return None

    def update_record(self, section: str, record_id: str, patch: dict[str, Any]) -> dict[str, Any]:
        def updater(state: dict[str, Any]) -> dict[str, Any]:
            for record in state.get(section, []):
                if str(record.get("id")) == record_id:
                    record.update(patch)
                    return dict(record)
            raise KeyError(f"{section} record not found: {record_id}")

        return self.mutate(updater)
