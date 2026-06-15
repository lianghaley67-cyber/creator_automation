#!/usr/bin/env python3
"""Safely update Creator Studio .env on the server.

Usage examples:
    python3 deploy/update_env.py --from-stdin --restart
    python3 deploy/update_env.py --set TAVILY_API_KEY=xxx --set AI_TRENDS_ENABLED=true --restart

The script preserves comments, backs up the old .env, and never prints secret values.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"

IMPORTANT_KEYS = [
    "ZHIPUAI_API_KEY",
    "GEMINI_API_KEY",
    "MINIMAX_API_KEY",
    "DEEPSEEK_API_KEY",
    "TAVILY_API_KEY",
    "GITEE_ACCESS_TOKEN",
    "WECHAT_CALLBACK_TOKEN",
    "WECHAT_APP_ID",
    "WECHAT_APP_SECRET",
    "WECHAT_THUMB_MEDIA_ID",
    "XIAOHONGSHU_PUBLISH_TOKEN",
    "CREATOR_STUDIO_PUBLIC_BASE_URL",
    "AI_TRENDS_ENABLED",
    "AI_TRENDS_TIME",
    "OBSIDIAN_REPO_OWNER",
    "OBSIDIAN_REPO_NAME",
    "OBSIDIAN_ARCHIVE_DIR",
]


def parse_env_lines(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key:
            values[key] = value.strip().strip('"').strip("'")
    return values


def upsert_env(existing_text: str, updates: dict[str, str]) -> str:
    seen: set[str] = set()
    output: list[str] = []
    for raw in existing_text.splitlines():
        stripped = raw.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            key = stripped.split("=", 1)[0].strip()
            if key in updates:
                output.append(f"{key}={updates[key]}")
                seen.add(key)
                continue
        output.append(raw)
    missing = [key for key in updates if key not in seen]
    if missing:
        if output and output[-1].strip():
            output.append("")
        output.append("# Added by deploy/update_env.py")
        for key in missing:
            output.append(f"{key}={updates[key]}")
    return "\n".join(output).rstrip() + "\n"


def print_status(values: dict[str, str]) -> None:
    for key in IMPORTANT_KEYS:
        print(f"{key}: {'OK' if values.get(key) else 'EMPTY'}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Update Creator Studio .env safely.")
    parser.add_argument("--from-stdin", action="store_true", help="Read KEY=value lines from standard input.")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE", help="Set one env value.")
    parser.add_argument("--restart", action="store_true", help="Restart creator-studio after updating.")
    args = parser.parse_args()

    updates: dict[str, str] = {}
    for item in args.set:
        if "=" not in item:
            raise SystemExit(f"Invalid --set value: {item}. Expected KEY=VALUE.")
        key, value = item.split("=", 1)
        updates[key.strip()] = value.strip()

    if args.from_stdin:
        print("Paste KEY=VALUE lines, then press Ctrl+D:")
        import sys

        updates.update(parse_env_lines(sys.stdin.read()))

    if not updates:
        current = parse_env_lines(ENV_FILE.read_text(encoding="utf-8", errors="replace") if ENV_FILE.exists() else "")
        print_status(current)
        return

    if not ENV_FILE.exists():
        if ENV_EXAMPLE.exists():
            shutil.copy2(ENV_EXAMPLE, ENV_FILE)
        else:
            ENV_FILE.write_text("", encoding="utf-8")

    backup = ENV_FILE.with_name(f".env.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    shutil.copy2(ENV_FILE, backup)

    original = ENV_FILE.read_text(encoding="utf-8", errors="replace")
    ENV_FILE.write_text(upsert_env(original, updates), encoding="utf-8")

    print(f"Updated {ENV_FILE}")
    print(f"Backup: {backup}")
    print_status(parse_env_lines(ENV_FILE.read_text(encoding="utf-8", errors="replace")))

    if args.restart:
        subprocess.run(["sudo", "systemctl", "restart", "creator-studio"], check=True)
        subprocess.run(["sudo", "systemctl", "status", "creator-studio", "--no-pager"], check=False)


if __name__ == "__main__":
    main()
