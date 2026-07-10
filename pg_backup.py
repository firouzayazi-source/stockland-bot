"""
pg_backup.py — موتور بکاپ PostgreSQL
──────────────────────────────────────────────────────────────
جایگزین سیستم قدیمی .stbak (که برای SQLite بود).
از pg_dump/pg_restore استفاده می‌کند.

خروجی: فایل .sql.gz (فشرده) با نام تاریخ‌دار.
سه مقصد: محلی (۳ بکاپ آخر) + کانال تلگرام + Google Drive.
"""
import os
import gzip
import time
import shutil
import logging
import subprocess
from urllib.parse import urlparse

logger = logging.getLogger("pg_backup")

BACKUP_DIR = "/opt/stockland/data/backups"
LOCAL_RETENTION = 3   # ۳ بکاپ محلی آخر


def _parse_dsn() -> dict:
    """DATABASE_URL را به اجزا تجزیه می‌کند."""
    dsn = os.getenv("DATABASE_URL", "")
    if not dsn:
        raise ValueError("DATABASE_URL تنظیم نشده")
    p = urlparse(dsn)
    return {
        "host": p.hostname or "localhost",
        "port": str(p.port or 5432),
        "user": p.username or "",
        "password": p.password or "",
        "dbname": (p.path or "/").lstrip("/"),
    }


def backup_filename() -> str:
    return f"pg_backup_{time.strftime('%Y%m%d_%H%M%S')}.sql.gz"


def create_backup() -> str:
    """
    بکاپ کامل با pg_dump می‌گیرد، فشرده می‌کند، در BACKUP_DIR ذخیره می‌کند.
    مسیر فایل ساخته‌شده را برمی‌گرداند.
    """
    os.makedirs(BACKUP_DIR, exist_ok=True)
    creds = _parse_dsn()
    fname = backup_filename()
    fpath = os.path.join(BACKUP_DIR, fname)

    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]

    # pg_dump → stdout → gzip → file
    cmd = [
        "pg_dump",
        "-h", creds["host"], "-p", creds["port"],
        "-U", creds["user"], "-d", creds["dbname"],
        "--no-owner", "--no-privileges", "--clean", "--if-exists",
    ]
    try:
        with gzip.open(fpath, "wb") as gz:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
            for chunk in iter(lambda: proc.stdout.read(65536), b""):
                gz.write(chunk)
            proc.stdout.close()
            err = proc.stderr.read().decode(errors="ignore")
            rc = proc.wait()
        if rc != 0:
            try: os.remove(fpath)
            except Exception: pass
            raise RuntimeError(f"pg_dump خطا: {err[:200]}")
        logger.info("backup created: %s (%d bytes)", fname, os.path.getsize(fpath))
        _rotate_local()
        return fpath
    except FileNotFoundError:
        raise RuntimeError("pg_dump نصب نیست (apt install postgresql-client)")


def _rotate_local():
    """فقط ۳ بکاپ محلی آخر را نگه می‌دارد."""
    try:
        files = sorted(
            [os.path.join(BACKUP_DIR, f) for f in os.listdir(BACKUP_DIR)
             if f.startswith("pg_backup_") and f.endswith(".sql.gz")],
            key=os.path.getmtime, reverse=True)
        for old in files[LOCAL_RETENTION:]:
            try:
                os.remove(old)
                logger.info("removed old backup: %s", os.path.basename(old))
            except Exception:
                pass
    except Exception as ex:
        logger.warning("rotation failed: %s", ex)


def list_local_backups() -> list:
    """لیست بکاپ‌های محلی — [{name, size, mtime}, ...]"""
    if not os.path.isdir(BACKUP_DIR):
        return []
    out = []
    for f in os.listdir(BACKUP_DIR):
        if f.startswith("pg_backup_") and f.endswith(".sql.gz"):
            fp = os.path.join(BACKUP_DIR, f)
            out.append({
                "name": f,
                "size": os.path.getsize(fp),
                "mtime": os.path.getmtime(fp),
                "path": fp,
            })
    return sorted(out, key=lambda x: x["mtime"], reverse=True)


def restore_backup(filepath: str) -> dict:
    """
    بازیابی از فایل .sql.gz — با psql اجرا می‌شود.
    ⚠️ داده‌های فعلی را جایگزین می‌کند (--clean در dump).
    """
    if not os.path.exists(filepath):
        return {"ok": False, "error": "فایل موجود نیست"}
    creds = _parse_dsn()
    env = os.environ.copy()
    env["PGPASSWORD"] = creds["password"]
    try:
        # gunzip → psql
        with gzip.open(filepath, "rb") as gz:
            proc = subprocess.Popen(
                ["psql", "-h", creds["host"], "-p", creds["port"],
                 "-U", creds["user"], "-d", creds["dbname"]],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, env=env)
            out, err = proc.communicate(gz.read())
        if proc.returncode != 0:
            return {"ok": False, "error": err.decode(errors="ignore")[:200]}
        return {"ok": True}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:200]}


# ══════════════════════════════════════════════════════════════════════════
# ─── بکاپ کامل + آپلود به مقاصد ابری (غیرهمزمان) ─────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def run_full_backup() -> dict:
    """
    بکاپ می‌گیرد + به مقاصد ابری فعال آپلود می‌کند (غیرهمزمان).
    برای اجرای خودکار روزانه و دکمه دستی پنل.
    """
    try:
        fpath = create_backup()
    except Exception as ex:
        logger.error("backup failed: %s", ex)
        return {"ok": False, "error": str(ex)[:200]}

    # آپلود ابری از طریق backup_uploader (که thread جدا می‌سازد)
    try:
        from backup_uploader import upload_backup
        upload_backup(fpath)
    except Exception as ex:
        logger.warning("cloud upload skipped: %s", ex)

    return {"ok": True, "file": os.path.basename(fpath),
            "size": os.path.getsize(fpath)}
