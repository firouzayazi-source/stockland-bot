#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:-/opt/Robuser}"

apt update
apt install -y python3 python3-venv python3-pip ca-certificates

cd "$APP_DIR"
python3 -m venv venv
./venv/bin/pip install -U pip setuptools wheel
./venv/bin/pip install -r requirements.txt

echo "OK: venv created and requirements installed."