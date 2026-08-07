"""
db_conn.py — Connection wrapper سازگار SQLite/PostgreSQL
──────────────────────────────────────────────────────────────
یک wrapper شفاف دور connection که:
  - در حالت SQLite: دقیقاً مثل sqlite3.Connection رفتار می‌کند (بدون سربار)
  - در حالت Postgres: کوئری‌ها را قبل از اجرا ترجمه می‌کند و Row را dict-like می‌کند

هدف: کد موجود db.py/admin_panel.py که conn.execute(sql, params) می‌زند،
بدون تغییر روی هر دو دیتابیس کار کند.
"""
import logging
import os
import threading

logger = logging.getLogger("stockland.db_conn")


def get_dialect() -> str:
    return os.getenv("DB_DIALECT", "sqlite").lower()


def is_postgres() -> bool:
    return get_dialect() == "postgres"


def _pool_enabled() -> bool:
    return os.getenv("DB_CONNECTION_POOL", "0") == "1"


# ══════════════════════════════════════════════════════════════════════════
# ─── SQLite (پیش‌فرض) ──────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _open_sqlite_connection(db_path: str):
    import sqlite3
    conn = sqlite3.connect(db_path, timeout=30, check_same_thread=False)
    try:
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA busy_timeout=5000;")
        conn.execute("PRAGMA foreign_keys=ON;")
        # synchronous=FULL (پیش‌فرض SQLite) برای WAL بیش از حد محافظه‌کارانه‌ست؛
        # NORMAL هم امنه (تحت WAL هیچ corruption‌ای در crash نداره) هم سریع‌تر —
        # چون این یه تنظیم per-connection است (نه persist روی فایل دیتابیس)،
        # باید همین‌جا کنار بقیهٔ PRAGMA ها روی هر اتصال تازه ست بشه.
        conn.execute("PRAGMA synchronous=NORMAL;")
    except Exception:
        pass
    conn.row_factory = sqlite3.Row
    return conn


class _PooledSqliteConnection:
    """رَپِر دور sqlite3.Connection برای connection pooling per-thread —
    close() واقعاً اتصال رو نمی‌بنده، فقط برمی‌گردونه به pool (که همون خودشه،
    چون هر ترد فقط یک اتصال مخصوص خودش داره). این طراحی عمداً محافظه‌کارانه‌ست
    (بخش ۴ گزارش ممیزی این آیتم رو با «ریسک اجرا متوسط تا بالا» علامت زده بود):
    قبل از تحویل یه اتصالِ cache‌شده به فراخوان تازه، اگه transaction بازِ
    جامونده‌ای پیدا بشه (نشونهٔ یه باگ commit/rollback جای دیگه که هیچ‌وقت
    نباید اتفاق بیفته، ولی این کد فرض نمی‌کنه صد در صد هیچ‌جا رخ نمی‌ده)،
    به‌جای اینکه بی‌صدا اون transaction ناخواسته با کوئری بعدی merge بشه،
    صریحاً rollback و لاگ هشدار می‌شه — fail-safe به‌جای fail-silent."""

    def __init__(self, conn):
        object.__setattr__(self, "_real", conn)

    def close(self):
        pass  # عمدی — بازگشت به pool، نه بستن واقعی

    def real_close(self):
        self._real.close()

    def __getattr__(self, name):
        return getattr(self._real, name)

    def __setattr__(self, name, value):
        setattr(self._real, name, value)


_thread_pool = threading.local()


def _pooled_sqlite_connection(db_path: str):
    cached = getattr(_thread_pool, "conn", None)
    cached_path = getattr(_thread_pool, "path", None)
    if cached is not None and cached_path == db_path:
        if cached._real.in_transaction:
            logger.warning(
                "Pooled SQLite connection had a dangling open transaction — "
                "rolling back defensively before reuse (thread=%s)",
                threading.current_thread().name,
            )
            try:
                cached._real.rollback()
            except Exception:
                logger.exception("Defensive rollback on pooled connection failed")
        return cached
    if cached is not None:
        try:
            cached.real_close()
        except Exception:
            pass
    pooled = _PooledSqliteConnection(_open_sqlite_connection(db_path))
    _thread_pool.conn = pooled
    _thread_pool.path = db_path
    return pooled


def _sqlite_connection(db_path: str):
    # پیش‌فرض خاموش — طبق توصیهٔ صریح گزارش ممیزی (بخش ۴)، این تغییر فقط با
    # env var DB_CONNECTION_POOL=1 صریحاً فعال می‌شه، نه به‌صورت پیش‌فرض روشن.
    # رفتار پیش‌فرض فعلی (اتصال تازه به‌ازای هر فراخوانی) دست‌نخورده می‌مونه.
    if _pool_enabled():
        return _pooled_sqlite_connection(db_path)
    return _open_sqlite_connection(db_path)


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

    def __iter__(self):
        """⚠️ رفع‌شده (کشف‌شده روی سرور تولید واقعی، نه سندباکس): sqlite3.Cursor
        مستقیم iterable است (`for row in conn.execute(...)`) — الگویی که کد
        موجود پروژه در چند جا استفاده می‌کنه (مثلاً payment_service.ensure_schema:
        `{row["name"] for row in conn.execute("PRAGMA table_info(...)")}`). قبلاً
        _PgCursor این متد رو نداشت → TypeError: '_PgCursor' object is not
        iterable → کل سرویس در startup کرش می‌کرد. psycopg2 cursor خودش
        native iterable است، فقط delegate می‌کنیم."""
        return iter(self._cur)

    @property
    def lastrowid(self):
        """معادل sqlite3.Cursor.lastrowid.
        ⚠️ رفع‌شده (کشف‌شده با تست مستقیم روی Postgres واقعی): تلاش قبلی برای
        fetchone() مستقیم روی نتیجهٔ INSERT همیشه شکست می‌خورد چون کد موجود
        پروژه در ~۳۶ نقطه (db.py/iphone_valuation/db.py/payment_service.py)
        هیچ‌وقت RETURNING به دستور INSERT اضافه نمی‌کنه — نتیجه همیشه None بود
        (مثلاً add_product() سکوت می‌کرد و None برمی‌گردوند). راه‌حل درست:
        lastval() مقدار سکانسی که آخرین‌بار در همین سشن با nextval() (که هر
        INSERT روی ستون SERIAL خودکار صداش می‌زنه) گرفته شده رو برمی‌گردونه —
        دقیقاً معادل SQLite lastrowid، بدون نیاز به تغییر خودِ INSERT."""
        try:
            self._cur.execute("SELECT lastval();")
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
    """اتصال Postgres سازگار با API که کد فعلی انتظار دارد.
    ⚠️ رفع‌شده (کشف‌شده با تست مستقیم روی Postgres واقعی، نه فقط خوندن کد):
    قبلاً از RealDictCursor استفاده می‌شد که فقط دسترسی row['col'] رو پشتیبانی
    می‌کنه، نه row[0] — در حالی که کد موجود پروژه (db.py/bot.py/admin_panel.py)
    جاهای زیادی row[0]/row[1] (اندیس عددی) می‌زنه، دقیقاً مثل sqlite3.Row که هم
    اندیس عددی هم نام ستون رو پشتیبانی می‌کنه. DictCursor دقیقاً همین رفتار
    دوگانه رو داره (تست شد) — جایگزین RealDictCursor شد."""
    def __init__(self, dsn: str):
        import psycopg2
        import psycopg2.extras
        self._conn = psycopg2.connect(dsn)
        self._dict_factory = psycopg2.extras.DictCursor

    def execute(self, sql, params=()):
        """conn.execute مستقیم (مثل sqlite) — یک کورسر می‌سازد."""
        import db_dialect
        cur = self._conn.cursor(cursor_factory=self._dict_factory)
        translated = db_dialect.translate(sql)
        cur.execute(translated, tuple(params) if params else None)
        return _PgCursor(cur)

    def executemany(self, sql, seq):
        """⚠️ رفع‌شده (کشف با تست): کد پروژه در ۴ نقطه (db.py، bulk feed upload
        در admin_panel.py، seed سطوح همکاری) `conn.executemany(...)` مستقیم روی
        connection صدا می‌زنه — sqlite3.Connection این متد رو داره ولی _PgConnection
        نداشت → AttributeError. حالا مثل execute() یک کورسر می‌سازه و روش
        executemany می‌زنه (خودِ _PgCursor.executemany ترجمهٔ SQL رو انجام می‌ده)."""
        cur = _PgCursor(self._conn.cursor(cursor_factory=self._dict_factory))
        cur.executemany(sql, seq)
        return cur

    def cursor(self):
        return _PgCursor(self._conn.cursor(cursor_factory=self._dict_factory))

    def commit(self):
        self._conn.commit()

    def rollback(self):
        self._conn.rollback()

    def close(self):
        self._conn.close()


# ══════════════════════════════════════════════════════════════════════════
# ─── رفع محدودیت یکتایی گمشده (کشف‌شده روی سرور تولید واقعی) ───────────────
# ══════════════════════════════════════════════════════════════════════════

_UNIQUE_CONSTRAINT_CHECKED: set = set()  # فلگ per-process، مثل الگوهای مشابه پروژه


def ensure_unique_constraint(conn, table: str, columns: list) -> None:
    """⚠️ فقط زیر Postgres معنی داره: کشف شد که بعضی جدول‌ها (مثل bot_config) روی
    Postgres تولید واقعی از قبل (احتمالاً توسط migrate_to_postgres.py یا یه مسیر
    دستی دیگه) بدون محدودیت یکتایی واقعی ساخته شده بودن — یعنی
    `CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT)`
    چون جدول از قبل با ستون‌های ساده (بدون PK واقعی) وجود داشت، بی‌اثر بود.
    نتیجه: `ON CONFLICT(key)` با psycopg2.errors.InvalidColumnReference
    («there is no unique or exclusion constraint») شکست می‌خورد — دقیقاً همون
    خطایی که در iphone_valuation.db._migrate_registry_options_v2 → db.set_cfg
    روی سرور واقعی رخ داد.

    این تابع (idempotent، فلگ per-process) سعی می‌کنه محدودیت یکتایی رو اضافه
    کنه؛ اگه داده‌های تکراری از قبل باشن (چون بدون constraint واقعی هیچ‌چیزی
    جلوی درج تکراری رو نمی‌گرفت)، اول safe-dedup می‌کنه (فقط جدیدترین ردیف هر
    ترکیب کلید رو نگه می‌داره، بر اساس ctid) و دوباره امتحان می‌کنه. هیچ‌وقت
    exception پرتاب نمی‌کنه — بدترین حالت: constraint اضافه نمی‌شه و همون خطای
    قبلی روی ON CONFLICT باقی می‌مونه، ولی بدون کرش کل مسیر migration."""
    if not is_postgres():
        return
    cache_key = (table, tuple(columns))
    if cache_key in _UNIQUE_CONSTRAINT_CHECKED:
        return
    # اگه جدول هنوز اصلاً وجود نداره (مثلاً یه ensure_* lazy دیگه هنوز صداش نشده)،
    # بی‌صدا رد شو — این حالت طبیعیه، نه خطا؛ کش نمی‌کنیم چون ممکنه جدول بعداً ساخته بشه.
    try:
        exists = conn.execute(
            "SELECT 1 FROM information_schema.tables WHERE table_name=?;", (table,)
        ).fetchone()
        if not exists:
            return
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
        return
    cname = f"{table}_{'_'.join(columns)}_uq"
    cols_csv = ", ".join(columns)
    try:
        conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {cname} UNIQUE ({cols_csv});")
        conn.commit()
        _UNIQUE_CONSTRAINT_CHECKED.add(cache_key)
        return
    except Exception:
        try:
            conn.rollback()
        except Exception:
            pass
    # شکست اول یعنی یا constraint از قبل هست (بی‌خطر، کاری لازم نیست) یا دادهٔ
    # تکراری داره (چون هیچ‌وقت واقعاً یکتایی اعمال نمی‌شد) — سعی در پاکسازی امن
    try:
        cond = " AND ".join(f"a.{c}=b.{c}" for c in columns)
        conn.execute(f"DELETE FROM {table} a USING {table} b WHERE a.ctid < b.ctid AND {cond};")
        conn.commit()
        conn.execute(f"ALTER TABLE {table} ADD CONSTRAINT {cname} UNIQUE ({cols_csv});")
        conn.commit()
        _UNIQUE_CONSTRAINT_CHECKED.add(cache_key)
    except Exception as ex:
        try:
            conn.rollback()
        except Exception:
            pass
        logger.warning("ensure_unique_constraint(%s, %s) failed: %s", table, columns, ex)


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
