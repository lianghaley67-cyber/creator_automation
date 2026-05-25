#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="${PROJECT_DIR:-$HOME/creator_automation}"
SERVICE_USER="${SERVICE_USER:-$(whoami)}"
PYTHON_BIN="${PYTHON_BIN:-python3.10}"

cd "$PROJECT_DIR"

echo "[1/7] Installing system packages..."
sudo apt update
sudo apt install -y software-properties-common curl ca-certificates gnupg git nginx ffmpeg build-essential

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  sudo add-apt-repository -y ppa:deadsnakes/ppa
  sudo apt update
  sudo apt install -y python3.10 python3.10-venv python3.10-dev
fi

if ! command -v node >/dev/null 2>&1 || ! node --version | grep -Eq '^v(20|22|24)\.'; then
  curl -fsSL https://deb.nodesource.com/setup_24.x | sudo -E bash -
  sudo apt install -y nodejs
fi

echo "[2/7] Creating Python virtual environment..."
"$PYTHON_BIN" -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip wheel setuptools
pip install -r studio_backend/requirements.txt

echo "[3/7] Installing frontend dependencies and building dist..."
cd studio_frontend
npm ci || npm install
npm run build
cd "$PROJECT_DIR"

echo "[4/7] Preparing runtime folders..."
mkdir -p studio_runtime/uploads studio_runtime/outputs studio_runtime/references logs

if [ ! -f .env ]; then
  cp .env.example .env
  echo "Created .env from .env.example. Edit it before generating scripts/videos."
fi

echo "[5/7] Installing systemd service..."
sudo cp deploy/creator-studio.service /etc/systemd/system/creator-studio.service
sudo sed -i "s#User=ubuntu#User=$SERVICE_USER#g" /etc/systemd/system/creator-studio.service
sudo sed -i "s#/home/ubuntu/creator_automation#$PROJECT_DIR#g" /etc/systemd/system/creator-studio.service
sudo systemctl daemon-reload
sudo systemctl enable creator-studio
sudo systemctl restart creator-studio

echo "[6/7] Installing Nginx reverse proxy..."
sudo cp deploy/creator-studio.nginx.conf /etc/nginx/sites-available/creator-studio
sudo ln -sf /etc/nginx/sites-available/creator-studio /etc/nginx/sites-enabled/creator-studio
sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl reload nginx

echo "[7/7] Verifying service..."
sleep 2
curl -fsS http://127.0.0.1:8000/api/health
echo
echo "Creator Studio is running. Open your server public IP or configured domain in a browser."
