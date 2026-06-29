#!/bin/bash
set -e

PROJECT_PATH="/opt/Robuser"
BACKUP_FILE="$1"

if [ -z "$BACKUP_FILE" ]; then
    echo "Usage: restore_backup.sh /path/to/backup.tar.gz"
    exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
    echo "Backup file not found!"
    exit 1
fi

echo "Stopping services..."
systemctl stop robuser-bot.service 2>/dev/null || true
systemctl stop robuser-internal-api.service 2>/dev/null || true

TMP_DIR="/tmp/robuser_restore_$(date +%s)"
mkdir -p "$TMP_DIR"

echo "Extracting backup..."
tar -xzf "$BACKUP_FILE" -C "$TMP_DIR"

echo "Restoring project files..."
rsync -av \
  --exclude 'venv' \
  --exclude 'restore_backup.sh' \
  "$TMP_DIR/opt/Robuser/" \
  "$PROJECT_PATH/"

echo "Fixing permissions..."
chown -R root:root "$PROJECT_PATH"
chmod -R 755 "$PROJECT_PATH"
chmod -R 700 "$PROJECT_PATH/database"

echo "Cleaning temp..."
rm -rf "$TMP_DIR"

echo "Starting services..."
systemctl daemon-reload
systemctl start robuser-bot.service 2>/dev/null || true
systemctl start robuser-internal-api.service 2>/dev/null || true

echo "Restore completed."
