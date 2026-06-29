import os
import shutil
import sqlite3
from datetime import datetime

from telebot import types

from config import DB_PATH


BACKUP_DIR = os.environ.get("ROBUSER_BACKUP_DIR", "/opt/Robuser/backups")
_ui_cache_clear_callback = None


def set_ui_cache_clear_callback(callback):
    global _ui_cache_clear_callback
    _ui_cache_clear_callback = callback


def _ensure_backup_dir():
    os.makedirs(BACKUP_DIR, exist_ok=True)


def _safe_sqlite_backup(src_db_path: str, dst_db_path: str):
    # Works correctly with WAL mode; produces a consistent snapshot.
    _ensure_backup_dir()
    src_conn = sqlite3.connect(src_db_path, timeout=30)
    try:
        src_conn.execute("PRAGMA busy_timeout=30000;")
        dst_conn = sqlite3.connect(dst_db_path, timeout=30)
        try:
            with dst_conn:
                src_conn.backup(dst_conn)
        finally:
            dst_conn.close()
    finally:
        src_conn.close()


def create_db_backup() -> str:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    _ensure_backup_dir()
    dst = os.path.join(BACKUP_DIR, f"robuser_backup_{ts}.sqlite")
    _safe_sqlite_backup(DB_PATH, dst)
    return dst


def validate_backup_db(path_: str) -> tuple[bool, str]:
    required = {
        "delivery_messages",
        "wallets",
        "products",
        "partners",
        "orders",
        "zarinpal_transactions",
        "product_feed",
        "feed_alert_settings",
    }
    try:
        conn = sqlite3.connect(path_, timeout=30)
        try:
            tables = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
                ).fetchall()
            }
        finally:
            conn.close()
        missing = sorted(required - tables)
        if missing:
            return False, f"missing tables: {', '.join(missing)}"
        return True, "ok"
    except Exception as e:
        return False, str(e)


def restore_db_from_backup(backup_path: str) -> str:
    # Replace DB atomically; move old DB to .bak_*
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    bak = f"{DB_PATH}.bak_{ts}"
    tmp = f"{DB_PATH}.restore_{ts}"
    shutil.copy2(backup_path, tmp)

    ok, msg = validate_backup_db(tmp)
    if not ok:
        try:
            os.remove(tmp)
        except Exception:
            pass
        raise RuntimeError(f"backup validation failed: {msg}")

    try:
        conn = sqlite3.connect(DB_PATH, timeout=30)
        try:
            conn.execute("PRAGMA busy_timeout=30000;")
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
        finally:
            conn.close()
    except Exception:
        pass

    if os.path.exists(DB_PATH):
        os.replace(DB_PATH, bak)
    os.replace(tmp, DB_PATH)

    for ext in ("-wal", "-shm"):
        p = DB_PATH + ext
        if os.path.exists(p):
            try:
                os.remove(p)
            except Exception:
                pass
    return bak


def admin_backup_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("ًں“¤ ط®ط±ظˆط¬غŒ/ط¨ع©ط§ظ¾ (ط¯ط§ظ†ظ„ظˆط¯ ظپط§غŒظ„ ط¯غŒطھط§ط¨غŒط³)", callback_data="admin_export_backup"),
        types.InlineKeyboardButton("ًں“¥ ط¨ط§ط²غŒط§ط¨غŒ ط§ط² ط¨ع©ط§ظ¾ (ط¢ظ¾ظ„ظˆط¯ ظپط§غŒظ„)", callback_data="admin_import_backup"),
        types.InlineKeyboardButton("â¬…ï¸ڈ ط¨ط§ط²ع¯ط´طھ", callback_data="admin_settings"),
    )
    return kb


def admin_full_reset_confirm_menu(step: int = 1):
    kb = types.InlineKeyboardMarkup(row_width=2)
    if step == 1:
        kb.add(
            types.InlineKeyboardButton("âœ… ط§ط¯ط§ظ…ظ‡", callback_data="admin_full_reset_2"),
            types.InlineKeyboardButton("â‌Œ ط§ظ†طµط±ط§ظپ", callback_data="admin_settings"),
        )
    else:
        kb.add(
            types.InlineKeyboardButton("ًں”¥ طھط§غŒغŒط¯ ظ†ظ‡ط§غŒغŒ", callback_data="admin_full_reset_do"),
            types.InlineKeyboardButton("â‌Œ ط§ظ†طµط±ط§ظپ", callback_data="admin_settings"),
        )
    return kb


def full_reset_database():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000;")

    try:
        conn.execute("BEGIN IMMEDIATE;")

        tables_to_clear = [
            "products",
            "orders",
            "wallets",
            "wallet_orders",
            "product_feed",
            "zarinpal_transactions",
            "pending_deliveries",
            "tickets",
            "delivery_messages",
            "partners",
        ]

        for table in tables_to_clear:
            try:
                conn.execute(f"DELETE FROM {table};")
            except Exception:
                pass

        try:
            conn.execute(
                """
                DELETE FROM other_services
                WHERE service_key != 'general';
                """
            )
        except Exception:
            pass

        conn.execute("DELETE FROM sqlite_sequence;")
        conn.commit()
    finally:
        conn.close()

    if _ui_cache_clear_callback is not None:
        try:
            _ui_cache_clear_callback()
        except Exception:
            pass
