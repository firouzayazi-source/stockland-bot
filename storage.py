"""
storage.py — لایه‌ی متمرکز دسترسی به دیتابیس
────────────────────────────────────────────────
همه‌ی جای‌های‌که مستقیماً با SQLite حرف می‌زنند در آینده باید از این ماژول عبور کنند.
این طرح، مهاجرت به PostgreSQL را با کمترین تغییر ممکن می‌کند:

- storage.query(sql, params) → لیست ردیف‌ها
- storage.query_one(sql, params) → یک ردیف یا None
- storage.execute(sql, params) → اجرا و commit
- storage.insert(sql, params) → lastrowid
- storage.transaction() → context manager
- storage.ensure_column(table, col, decl) → مهاجرت ستون (قانون ۱۳)
- storage.now_local() → timestamp محلی (سازگار SQLite/Postgres)
- storage.raw_connection() → اتصال خام (فقط برای کدهایی که هنوز مهاجرت نشده‌اند)

⚠️ مهم: در این فاز، رفتار برنامه هیچ تغییری نمی‌کند. فقط یک لایه انتزاع افزوده می‌شود.
db.py می‌تواند تدریجاً به این لایه مهاجرت کند بدون تأثیر بر بقیه کد.
"""
import sqlite3
import threading
from contextlib import contextmanager
from typing import Any, Iterable, Optional


# ── تنظیم dialect جاری ─────────────────────────────────────────────────────
# در آینده با تغییر این ثابت + swap کردن _raw_connection() به Postgres مهاجرت می‌کنیم.
DIALECT = "sqlite"


# ── قفل نوشتار برای thread-safety (SQLite در حالت WAL هم به این نیاز دارد) ──
_write_lock = threading.RLock()


def _db_path() -> str:
    from config import DB_PATH
    return DB_PATH


def raw_connection() -> sqlite3.Connection:
    """اتصال خام SQLite با تنظیمات استاندارد پروژه (WAL + row_factory)."""
    conn = sqlite3.connect(_db_path(), timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA foreign_keys=ON;")
        conn.execute("PRAGMA busy_timeout=5000;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════════
# ── سطح بالا: انتزاع کوئری ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def query(sql: str, params: Iterable[Any] = ()) -> list:
    """SELECT چندردیفی — لیست ردیف‌ها (به‌صورت sqlite3.Row؛ dict-like)."""
    conn = raw_connection()
    try:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()
    finally:
        conn.close()


def query_one(sql: str, params: Iterable[Any] = ()) -> Optional[sqlite3.Row]:
    """SELECT تک‌ردیفی — Row یا None."""
    conn = raw_connection()
    try:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()
    finally:
        conn.close()


def scalar(sql: str, params: Iterable[Any] = (), default: Any = None) -> Any:
    """SELECT یک مقدار (ستون اول ردیف اول)."""
    row = query_one(sql, params)
    if row is None:
        return default
    try:
        return row[0]
    except (IndexError, KeyError):
        return default


def execute(sql: str, params: Iterable[Any] = ()) -> int:
    """DML (UPDATE/DELETE/INSERT بدون نیاز به lastrowid) — تعداد ردیف‌های تغییریافته."""
    with _write_lock:
        conn = raw_connection()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


def insert(sql: str, params: Iterable[Any] = ()) -> int:
    """INSERT با برگشت lastrowid."""
    with _write_lock:
        conn = raw_connection()
        try:
            cur = conn.execute(sql, tuple(params))
            conn.commit()
            return cur.lastrowid or 0
        finally:
            conn.close()


def executemany(sql: str, seq_of_params: Iterable[Iterable[Any]]) -> int:
    """اجرای batch — تعداد کل تغییرات."""
    with _write_lock:
        conn = raw_connection()
        try:
            cur = conn.executemany(sql, [tuple(p) for p in seq_of_params])
            conn.commit()
            return cur.rowcount
        finally:
            conn.close()


@contextmanager
def transaction():
    """
    Context manager تراکنش. مثال:
        with storage.transaction() as conn:
            conn.execute("UPDATE ...", (...))
            conn.execute("INSERT ...", (...))
    اگر خطا رخ دهد، rollback خودکار.
    """
    conn = raw_connection()
    try:
        with _write_lock:
            yield conn
            conn.commit()
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        raise
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ── مهاجرت اسکیما (قانون ۱۳ — انتزاع سازگار با Postgres آینده) ────────────
# ══════════════════════════════════════════════════════════════════════════════

def table_columns(table: str) -> set:
    """نام همه ستون‌های جدول — SQLite و Postgres سازگار."""
    if DIALECT == "sqlite":
        rows = query(f"PRAGMA table_info({table});")
        return {r[1] for r in rows}
    else:
        rows = query(
            "SELECT column_name FROM information_schema.columns WHERE table_name=%s;",
            (table,))
        return {r[0] for r in rows}


def ensure_column(table: str, col: str, decl: str) -> bool:
    """
    اگر ستون در جدول وجود ندارد، اضافه‌اش می‌کند.
    الگوی استاندارد قانون ۱۳ در انتزاع سازگار SQLite/Postgres.
    Returns: True اگر اضافه شد، False اگر از قبل بود یا خطا رخ داد.
    """
    try:
        if col in table_columns(table):
            return False
    except Exception:
        # جدول وجود ندارد
        return False
    try:
        execute(f"ALTER TABLE {table} ADD COLUMN {col} {decl};")
        return True
    except Exception:
        return False


def table_exists(table: str) -> bool:
    """آیا جدول وجود دارد؟"""
    if DIALECT == "sqlite":
        row = query_one(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?;",
            (table,))
    else:
        row = query_one(
            "SELECT 1 FROM information_schema.tables WHERE table_name=%s;",
            (table,))
    return row is not None


# ══════════════════════════════════════════════════════════════════════════════
# ── انتزاع توابع تاریخ/زمان (Postgres/SQLite سازگار) ──────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def now_local_sql() -> str:
    """SQL fragment برای زمان محلی — استفاده در DEFAULT و در کوئری‌ها."""
    if DIALECT == "sqlite":
        return "datetime('now','localtime')"
    else:
        return "NOW() AT TIME ZONE 'Asia/Tehran'"


def now_local() -> str:
    """تاریخ‌زمان محلی به‌صورت رشته ISO."""
    from datetime import datetime
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ══════════════════════════════════════════════════════════════════════════════
# ── انتزاع INSERT OR IGNORE (سازگار Postgres) ─────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def sql_insert_or_ignore(table: str, columns: list) -> str:
    """
    برمی‌گرداند: SQL string برای INSERT ... کوئری placeholder با ? یا $n.
    SQLite: INSERT OR IGNORE INTO t (a,b) VALUES (?,?)
    Postgres: INSERT INTO t (a,b) VALUES ($1,$2) ON CONFLICT DO NOTHING
    """
    cols = ", ".join(columns)
    if DIALECT == "sqlite":
        placeholders = ", ".join(["?"] * len(columns))
        return f"INSERT OR IGNORE INTO {table} ({cols}) VALUES ({placeholders});"
    else:
        placeholders = ", ".join([f"${i+1}" for i in range(len(columns))])
        return f"INSERT INTO {table} ({cols}) VALUES ({placeholders}) ON CONFLICT DO NOTHING;"


# ══════════════════════════════════════════════════════════════════════════════
# ── سازگاری با کد قدیمی db.py که مستقیماً _get_connection() صدا می‌زند ───
# ══════════════════════════════════════════════════════════════════════════════
# در آینده db.py می‌تواند از storage.raw_connection() استفاده کند.
# فعلاً هر دو موازی کار می‌کنند بدون رگرسیون.
