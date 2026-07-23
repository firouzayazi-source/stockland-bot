"""
db_conn.py — Connection wrapper سازگار SQLite/PostgreSQL
──────────────────────────────────────────────────────────────
یک wrapper شفاف دور connection که:
  - در حالت SQLite: دقیقاً مثل sqlite3.Connection رفتار می‌کند (بدون سربار)
  - در حالت Postgres: کوئری‌ها را قبل از اجرا ترجمه می‌کند و Row را dict-like می‌کند

هدف: کد موجود db.py/admin_panel.py که conn.execute(sql, params) می‌زند،
بدون تغییر روی هر دو دیتابیس کار کند.
"""
import os


def get_dialect() -> str:
    return os.getenv("DB_DIALECT", "sqlite").lower()


def is_postgres() -> bool:
    return get_dialect() == "postgres"


# ══════════════════════════════════════════════════════════════════════════
# ─── SQLite (پیش‌فرض) ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _sqlite_connection(db_path: str):
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


# ══════════════════════════════════════════════════════════════════════════
# ─── PostgreSQL wrapper ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

class _PgCursor:
    """کورسر سازگار — ترجمه‌ی کوئری + Row dict-like."""
    def __init__(self, real_cursor):
        self._cur = real_cursor

    def execute(self, sql, params=()):
        import db_dialect
        translated = db_dialect.translate(sql)
        self._cur.execute(translated, tuple(params) if params else None)
        return self

    def executemany(self, sql, seq):
        import db_dialect
        translated = db_dialect.translate(sql)
        self._cur.executemany(translated, [tuple(p) for p in seq])
        return self

    def fetchone(self):
        return self._cur.fetchone()

    def fetchall(self):
        return self._cur.fetchall()

    @property
    def lastrowid(self):
        # Postgres: باید از RETURNING استفاده شود؛ اینجا تلاش برای سازگاری
        try:
            r = self._cur.fetchone()
            return r[0] if r else None
        except Exception:
            return None

    @property
    def rowcount(self):
        return self._cur.rowcount

    def close(self):
        self._cur.close()


class _PgConnection:
    """اتصال Postgres سازگار با API که کد فعلی انتظار دارد."""
    def __init__(self, dsn: str):
        import psycopg2
        import psycopg2.extras
        self._conn = psycopg2.connect(dsn)
        self._dict_factory = psycopg2.extras.RealDictCursor

    def execute(self, sql, params=()):
        """conn.execute مستقیم (مثل sqlite) — یک کورسر می‌سازد."""
        import db_dialect
        cur = self._conn.cursor(cursor_factory=self._dict_factory)
        translated = db_dialect.translate(sql)
        cur.execute(translated, tuple(params) if params else None)
        return _PgCursor(cur)

    def cursor(self):
        return _PgCursor(self._conn.cursor(cursor_factory=self._dict_factory))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ══════════════════════════════════════════════════════════════════════════
# ─── نقطه ورود ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def get_connection(db_path: str = ""):
    """
    اتصال مناسب بر اساس DB_DIALECT برمی‌گرداند.
    SQLite: از db_path. Postgres: از DATABASE_URL در env.
    """
    if is_postgres():
        dsn = os.getenv("DATABASE_URL", "")
        if not dsn:
            raise ValueError("DATABASE_URL تنظیم نشده (برای Postgres لازم است)")
        return _PgConnection(dsn)
    else:
        if not db_path:
            from config import DB_PATH
            db_path = DB_PATH
        return _sqlite_connection(db_path)
