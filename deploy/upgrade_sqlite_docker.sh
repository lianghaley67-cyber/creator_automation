#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-/home/ubuntu/creator_automation}"
cd "$PROJECT_DIR"

echo "[1/6] Backing up current state..."
mkdir -p studio_runtime/backups
timestamp="$(date +%Y%m%d_%H%M%S)"
if [ -f studio_runtime/studio_state.json ]; then
  cp -a studio_runtime/studio_state.json \
    "studio_runtime/backups/studio_state_${timestamp}.json"
fi
if [ -f studio_runtime/studio.db ]; then
  cp -a studio_runtime/studio.db \
    "studio_runtime/backups/studio_${timestamp}.db"
fi

echo "[2/6] Removing known zero-value debug files..."
find studio_runtime -maxdepth 1 -type f \
  \( -name 'debug_sapi*' -o -name 'tmp_edge_test.mp3' \) -delete
find studio_runtime -maxdepth 1 -type f -size 0 -name '*.wav' -delete

echo "[3/6] Building the application..."
docker compose build creator-studio

echo "[4/6] Starting the application and migrating JSON to SQLite..."
docker compose up -d creator-studio

echo "[5/6] Waiting for health check..."
for attempt in $(seq 1 30); do
  if docker exec creator-studio python -c \
    "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=3).read()" \
    >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    docker compose logs --tail=120 creator-studio
    exit 1
  fi
  sleep 2
done

echo "[6/6] Verifying SQLite..."
docker exec -i creator-studio python - <<'PY'
import sqlite3
from pathlib import Path

db = Path("/app/studio_runtime/studio.db")
if not db.exists():
    raise SystemExit("studio.db was not created")
with sqlite3.connect(db) as connection:
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    sections = connection.execute("SELECT COUNT(*) FROM state_sections").fetchone()[0]
print(f"SQLite integrity={integrity}, sections={sections}, path={db}")
PY

echo "Upgrade complete. The old JSON file and timestamped backups were kept."
