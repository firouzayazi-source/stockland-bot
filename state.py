import json
import os
import sqlite3
from config import ADMIN_ID


STATE = {
    "user": {},
    "admin": {},
}

# Backward compatibility for existing handlers.
user_states = STATE["user"]
admin_states = STATE["admin"]
reseller_signup = {}


def clear_user_state(uid: int):
    user_states.pop(uid, None)


def clear_admin_state(aid: int):
    admin_states.pop(aid, None)


def _db_path() -> str:
    return os.getenv("DB_PATH") or ""


def ensure_admin(user_id: int) -> bool:
    """True if user_id is super admin or an active admin in DB."""
    if user_id == ADMIN_ID:
        return True
    db = _db_path()
    if not db:
        return False
    try:
        conn = sqlite3.connect(db, timeout=5, check_same_thread=False)
        row = conn.execute(
            "SELECT 1 FROM admins WHERE telegram_id=? AND is_active=1 LIMIT 1;",
            (int(user_id),),
        ).fetchone()
        conn.close()
        return row is not None
    except Exception:
        return False


def admin_has_perm(user_id: int, permission: str) -> bool:
    """True if admin has a specific permission. Super admin always True."""
    if user_id == ADMIN_ID:
        return True
    db = _db_path()
    if not db:
        return False
    try:
        conn = sqlite3.connect(db, timeout=5, check_same_thread=False)
        row = conn.execute(
            "SELECT permissions FROM admins WHERE telegram_id=? AND is_active=1 LIMIT 1;",
            (int(user_id),),
        ).fetchone()
        conn.close()
        if not row:
            return False
        perms = json.loads(row[0] or "[]")
        return permission in perms
    except Exception:
        return False
