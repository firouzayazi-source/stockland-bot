import json
import os
import sqlite3
import threading as _threading
import time as _time
from config import ADMIN_ID


class _TrackedDict(dict):
    """دیکشنری state با ردیابی زمان آخرین ست‌شدن هر کلید در یک دیکشنری موازی
    جدا (نه داخل خودِ مقدار ذخیره‌شده) — یعنی هیچ کد موجودی که این state‌ها رو
    می‌خونه یا serialize می‌کنه تحت تأثیر قرار نمی‌گیره. برای پاک‌سازی دورهٔ
    state‌های رهاشدهٔ خیلی قدیمی (بخش فاز ۳ ممیزی) — قبلاً user_states/
    admin_states هیچ‌وقت پاک نمی‌شدن، یعنی روی سرور طولانی‌مدت بدون ری‌استارت
    رشد بی‌پایان حافظه داشتن."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._ts = {}

    def __setitem__(self, key, value):
        super().__setitem__(key, value)
        self._ts[key] = _time.time()

    def pop(self, key, *default):
        self._ts.pop(key, None)
        return super().pop(key, *default)

    def __delitem__(self, key):
        self._ts.pop(key, None)
        super().__delitem__(key)

    def cleanup_stale(self, max_age_seconds: int) -> int:
        now = _time.time()
        stale = [k for k, t in list(self._ts.items()) if now - t > max_age_seconds]
        for k in stale:
            self.pop(k, None)
        return len(stale)


STATE = {
    "user": _TrackedDict(),
    "admin": _TrackedDict(),
}

# Backward compatibility for existing handlers.
user_states = STATE["user"]
admin_states = STATE["admin"]
reseller_signup = _TrackedDict()

# ۶ ساعت — یه مکالمهٔ چندمرحله‌ای واقعی هیچ‌وقت این‌قدر طول نمی‌کشه (طبق مستندات
# پروژه، ری‌استارت ربات هم همین state‌ها رو کامل پاک می‌کنه، پس این فقط برای
# سروری که هفته‌ها بدون ری‌استارت بالاست و کاربر state رو رها کرده لازمه).
_STATE_TTL_SECONDS = 6 * 3600


def _state_cleanup_loop():
    while True:
        _time.sleep(1800)
        try:
            user_states.cleanup_stale(_STATE_TTL_SECONDS)
            admin_states.cleanup_stale(_STATE_TTL_SECONDS)
            reseller_signup.cleanup_stale(_STATE_TTL_SECONDS)
        except Exception:
            pass


_threading.Thread(target=_state_cleanup_loop, daemon=True, name="state-ttl-cleanup").start()


def clear_user_state(uid: int):
    user_states.pop(uid, None)


def clear_admin_state(aid: int):
    admin_states.pop(aid, None)


def _db_path() -> str:
    return os.getenv("DB_PATH") or ""


def _state_db_connect():
    """⚠️ رفع‌شده (ممیزی کامل پروژه، پاک‌سازی SQLite): قبلاً همیشه sqlite3.connect
    خام می‌زد، مستقل از DB_DIALECT — یعنی چک دسترسی ادمین‌های ثانویه (غیر از
    ADMIN_ID سوپرادمین) روی سرور Postgres همیشه شکست می‌خورد (except→False)."""
    import db_conn
    return db_conn.get_connection(_db_path())


def ensure_admin(user_id: int) -> bool:
    """True if user_id is super admin or an active admin in DB."""
    if user_id == ADMIN_ID:
        return True
    if not _db_path():
        return False
    try:
        conn = _state_db_connect()
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
    if not _db_path():
        return False
    try:
        conn = _state_db_connect()
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
