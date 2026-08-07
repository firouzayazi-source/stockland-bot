import os
import json
import sqlite3
from datetime import datetime

from config import DB_PATH, BASE_DIR

# اگر DB_PATH در config نسبی باشد، به BASE_DIR وصل میکنیم
DB_FULL_PATH = DB_PATH

# ⚠️ رفع‌شده (کشف‌شده با تست مستقیم روی Postgres واقعی، پاک‌سازی SQLite): چند
# جای کد فقط except sqlite3.IntegrityError می‌زدن تا نقض یکتایی (مثلاً authority
# تکراری تراکنش) رو بی‌صدا مدیریت کنن. زیر Postgres همین خطا از نوع
# psycopg2.IntegrityError است (سلسله‌مراتب استثنای کاملاً جدا، DB-API 2.0) —
# یعنی هیچ‌وقت catch نمی‌شد و به exception خام/۵۰۰ منجر می‌شد. هر دو نوع رو
# پوشش می‌ده، بدون وابستگی سخت به psycopg2 (اگه نصب نبود، فقط sqlite3 کافیه).
try:
    import psycopg2 as _psycopg2_for_errors
    _INTEGRITY_ERRORS = (sqlite3.IntegrityError, _psycopg2_for_errors.IntegrityError)
except ImportError:
    _INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


# ══════════════════════════════════════════════════════════════════════════════
# ─── تقویم شمسی + اعداد فارسی ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

from datetime import date as _date, timedelta as _td

_NRZ = {
    1395:_date(2016,3,20),1396:_date(2017,3,21),1397:_date(2018,3,21),
    1398:_date(2019,3,21),1399:_date(2020,3,20),1400:_date(2021,3,21),
    1401:_date(2022,3,21),1402:_date(2023,3,21),1403:_date(2024,3,20),
    1404:_date(2025,3,20),1405:_date(2026,3,21),1406:_date(2027,3,21),
    1407:_date(2028,3,20),1408:_date(2029,3,20),1409:_date(2030,3,20),
    1410:_date(2031,3,21),
}
_REF_JY, _REF_G = 1403, _NRZ[1403]

def _is_leap_j(jy):
    return (((jy-474)%2820+475)*682)%2816 < 682

def _to_jalali(gy, gm, gd):
    try:
        g = _date(gy, gm, gd)
    except Exception:
        return 1400, 1, 1
    jy = _REF_JY + (g - _REF_G).days // 365
    for _ in range(5):
        if jy in _NRZ:
            nrz = _NRZ[jy]
        else:
            d = 0
            if jy > _REF_JY:
                for y in range(_REF_JY, jy): d += 366 if _is_leap_j(y) else 365
                nrz = _REF_G + _td(days=d)
            else:
                for y in range(jy, _REF_JY): d += 366 if _is_leap_j(y) else 365
                nrz = _REF_G - _td(days=d)
        nxt = _NRZ.get(jy+1, nrz+_td(days=366 if _is_leap_j(jy) else 365))
        if g < nrz: jy -= 1; continue
        if g >= nxt: jy += 1; continue
        break
    diff = (g - nrz).days
    mlen = [31]*6+[30]*5+[30 if _is_leap_j(jy) else 29]
    for jm, ml in enumerate(mlen, 1):
        if diff < ml: return jy, jm, diff+1
        diff -= ml
    return jy, 12, 29


def _jalali_nowruz(jy):
    """تاریخ میلادی نوروز سال شمسی jy — با همون جدول/منطق _to_jalali (برای اطمینان از تبدیل دوطرفهٔ سازگار)."""
    if jy in _NRZ:
        return _NRZ[jy]
    d = 0
    if jy > _REF_JY:
        for y in range(_REF_JY, jy): d += 366 if _is_leap_j(y) else 365
        return _REF_G + _td(days=d)
    for y in range(jy, _REF_JY): d += 366 if _is_leap_j(y) else 365
    return _REF_G - _td(days=d)


def _from_jalali(jy, jm, jd):
    """تبدیل شمسی به میلادی — معکوس دقیق _to_jalali (همون جدول نوروز/طول ماه‌ها، تبدیل دوطرفه تضمین‌شده)."""
    try:
        jy, jm, jd = int(jy), int(jm), int(jd)
        nrz = _jalali_nowruz(jy)
        mlen = [31]*6+[30]*5+[30 if _is_leap_j(jy) else 29]
        jm = max(1, min(12, jm))
        jd = max(1, min(mlen[jm-1], jd))
        g = nrz + _td(days=sum(mlen[:jm-1]) + (jd - 1))
        return g.year, g.month, g.day
    except Exception:
        n = _date.today()
        return n.year, n.month, n.day


def jalali_str_to_gregorian_iso(s: str) -> str:
    """رشتهٔ شمسی «۱۴۰۴/۰۱/۰۱» یا «1404-01-01» رو به ISO میلادی (YYYY-MM-DD) تبدیل می‌کنه.
    ورودی نامعتبر → رشتهٔ خالی."""
    if not s:
        return ""
    s = str(s).strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789"))
    import re
    nums = re.findall(r"\d+", s)
    if len(nums) != 3:
        return ""
    jy, jm, jd = nums
    gy, gm, gd = _from_jalali(jy, jm, jd)
    return f"{gy:04d}-{gm:02d}-{gd:02d}"


_FA_TBL = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")


class _RowCompat:
    """
    پل سازگاری بین tuple و dict برای نتایج کوئری.
    هم product[0] (ایندکس عددی)، هم product["title"] (کلید)، هم product.get("x", default) کار می‌کند.
    برای حفظ سازگاری با کدی که به هر دو شکل به یک ردیف دسترسی دارد.
    """
    __slots__ = ("_row", "_keys")

    def __init__(self, row):
        self._row = row
        try:
            self._keys = list(row.keys())
        except Exception:
            self._keys = []

    def __getitem__(self, k):
        # ایندکس عددی یا کلید رشته‌ای
        if isinstance(k, int):
            return self._row[k]
        return self._row[k]

    def get(self, k, default=None):
        try:
            if k in self._keys:
                return self._row[k]
        except Exception:
            pass
        return default

    def keys(self):
        return self._keys

    def __len__(self):
        return len(self._keys)

    def __iter__(self):
        return iter(self._row)

    def __contains__(self, k):
        return k in self._keys

def fa_date(dt_str, with_time: bool = False) -> str:
    """تبدیل ISO تاریخ به شمسی فارسی."""
    if not dt_str: return "—"
    try:
        s = str(dt_str).strip()[:19].replace("T"," ")
        jy,jm,jd = _to_jalali(int(s[:4]),int(s[5:7]),int(s[8:10]))
        r = f"{jy}/{jm:02d}/{jd:02d}"
        if with_time and len(s) >= 16: r += f"  {s[11:16]}"
        return r.translate(_FA_TBL)
    except Exception:
        return str(dt_str)[:10]

def fa_now(with_time: bool = True) -> str:
    import datetime as _dtt
    now = _dtt.datetime.now()
    jy,jm,jd = _to_jalali(now.year, now.month, now.day)
    r = f"{jy}/{jm:02d}/{jd:02d}"
    if with_time: r += f"  {now.strftime('%H:%M')}"
    return r.translate(_FA_TBL)

if not os.path.isabs(DB_FULL_PATH):
    DB_FULL_PATH = os.path.join(BASE_DIR, DB_PATH)


def _get_connection():
    """
    اتصال دیتابیس — سازگار SQLite/PostgreSQL از طریق db_conn wrapper.
    با DB_DIALECT=postgres + DATABASE_URL به Postgres سوییچ می‌کند،
    بدون نیاز به تغییر کوئری‌ها (ترجمه خودکار).

    ⚠️ رفع‌شده (کشف‌شده هنگام بررسی آمادگی پروژه برای مشتری واقعی، ۲۰۲۶-۰۸-۰۷):
    این تابع — پرکاربردترین نقطهٔ اتصال کل پروژه — قبلاً اگه `db_conn.get_connection()`
    به هر دلیلی (مثلاً یه قطعی موقت شبکهٔ Postgres، یا DATABASE_URL موقتاً نامعتبر)
    استثنا می‌داد، بی‌صدا به یه فایل SQLite محلی fallback می‌کرد. زیر Postgres،
    این یعنی به‌جای شکست آشکار (که قابل تشخیص/لاگ/آلارمه)، اپ ساکت روی یه
    دیتابیس فانتومِ کاملاً جدا از دادهٔ واقعی ادامه می‌داد — دقیقاً همون کلاس
    باگی که بخش ۴۶ رو کلاً به‌وجود آورده بود (pg_backup، admin_panel._db، و…).
    برای یه ربات که قراره پول واقعی کاربر رو جابه‌جا کنه، «ساکت رو دادهٔ اشتباه
    ادامه بده» خیلی خطرناک‌تر از یه خطای آشکاره. حالا فقط زیر SQLite (dev/تست
    محلی) fallback واقعی معنی داره؛ زیر Postgres همون استثنای اصلی دوباره
    پرتاب می‌شه تا caller/لاگ سرور متوجه بشه، نه اینکه بی‌صدا قورت داده بشه.
    """
    import db_conn
    try:
        return db_conn.get_connection(DB_FULL_PATH)
    except Exception:
        if db_conn.is_postgres():
            raise
        # fallback مستقیم SQLite — فقط معنی‌دار وقتی خودِ دیالوگ SQLite است
        conn = sqlite3.connect(DB_FULL_PATH, timeout=30)
        try:
            conn.execute('PRAGMA journal_mode=WAL;')
            conn.execute('PRAGMA busy_timeout=5000;')
            conn.execute('PRAGMA synchronous=NORMAL;')
        except Exception:
            pass
        conn.row_factory = sqlite3.Row
        return conn


def _row_lock_suffix() -> str:
    """`FOR UPDATE ` زیر Postgres، رشتهٔ خالی زیر SQLite.

    توابع اتمیک پروژه (subtract_wallet_balance، claim_next_feed_item،
    claim_daily_checkin، exchange_order و…) قبلاً فقط به `BEGIN IMMEDIATE`
    تکیه می‌کردن — روی SQLite این یه قفل نوشتنِ *کل فایل* می‌گیره، پس SELECT
    اولیهٔ هرکدوم به‌خودی‌خود در برابر race condition ایمن بود. `BEGIN IMMEDIATE`
    روی Postgres اصلاً وجود نداره (`db_dialect.py` حالا به `BEGIN` ساده ترجمه‌ش
    می‌کنه) و مهم‌تر، `BEGIN` سادهٔ Postgres هیچ قفلی از قبل نمی‌گیره — یعنی بدون
    اقدام اضافه، دو تراکنش هم‌زمان می‌تونستن هر دو همون مقدار قدیمی رو بخونن و
    هر دو موفق به آپدیت بشن (kesr دوبل کیف‌پول، claim دوبارهٔ همون آیتم فید،
    و…). رفع: SELECT اولیهٔ هرکدوم `FOR UPDATE` می‌گیره (قفل ردیف Postgres،
    دقیقاً معادل هدف `BEGIN IMMEDIATE` ولی به‌جای کل دیتابیس، فقط همون ردیف —
    حتی بهتر از نظر همزمانی). SQLite این سینتکس رو نداره، پس زیر SQLite این
    تابع رشتهٔ خالی برمی‌گردونه (بدون تغییر رفتار قبلی)."""
    import db_conn
    return "FOR UPDATE " if db_conn.is_postgres() else ""


_DB_INIT_DONE_PATH = None  # مسیر DBای که init_db قبلاً کامل برایش اجرا شده (فلگ per-process)


def init_db(db_path=None):
    """
    ساخت / بهروزرسانی جداول دیتابیس.
    اگر قبلاً ساخته شده باشد، فقط مهاجرتهای لازم را انجام میدهد.
    """
    global DB_FULL_PATH, _DB_INIT_DONE_PATH
    if db_path:
        if not os.path.isabs(db_path):
            DB_FULL_PATH = os.path.join(BASE_DIR, db_path)
        else:
            DB_FULL_PATH = db_path

    # بدون این گارد، bot.py هر /start (از هر کاربر) کل ۱۲ CREATE TABLE + ۱۹ ALTER TABLE
    # این تابع رو دوباره روی همون فایل دیتابیس اجرا می‌کرد — سربار واقعی روی هر پیام
    # + قفل نوشتن روی فایل SQLیت مشترک با پنل. مهاجرت idempotent است، فقط یک‌بار در پروسه کافیه.
    if _DB_INIT_DONE_PATH == DB_FULL_PATH:
        return
    os.makedirs(os.path.dirname(DB_FULL_PATH), exist_ok=True)

    conn = _get_connection()
    try:
        cur = conn.cursor()

        # جدول کیف پول
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )

        # جدول محصولات
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                product_key TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                description TEXT,
                is_active INTEGER NOT NULL DEFAULT 1
            );
            """
        )

        # مهاجرت: ستون قیمت همکار برای محصولات
        try:
            cur.execute("ALTER TABLE products ADD COLUMN partner_price INTEGER;")
        except sqlite3.OperationalError:
            # ستون احتمالاً وجود دارد
            pass

        # مهاجرت: ستونهای حد خرید روزانه برای محصولات
        try:
            cur.execute('ALTER TABLE products ADD COLUMN daily_limit_customer INTEGER DEFAULT 0;')
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute('ALTER TABLE products ADD COLUMN daily_limit_partner INTEGER DEFAULT 0;')
        except sqlite3.OperationalError:
            pass

        # ⚠️ رفع‌شده (بخش ۱۴ آیتم ۳ سند): این ستون در هیچ نسخه‌ای، حتی نصب‌های
        # تازه، ساخته نمی‌شد — دکمهٔ ادمین «فعال‌سازی چت محصول» همیشه بی‌اثر بود
        # چون bot.py._get/_set_product_chat_enabled خطای «no such column» رو
        # بی‌صدا می‌بلعیدن.
        try:
            cur.execute('ALTER TABLE products ADD COLUMN chat_enabled INTEGER DEFAULT 0;')
        except sqlite3.OperationalError:
            pass


        # جدول همکاران (نمایندگان)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS partners (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tg_user_id INTEGER UNIQUE,
                phone TEXT UNIQUE,
                status TEXT NOT NULL DEFAULT 'pending',
                username TEXT,
                full_name TEXT,
                note TEXT,
                city TEXT,
                shop_name TEXT,
                created_at TEXT NOT NULL,
                approved_at TEXT
            );
            """
        )


    
    
        # مهاجرت/ایندکسها برای partners
        try:
            cur.execute("PRAGMA table_info(partners);")
            cols = {row[1] for row in cur.fetchall()}
            # ستونهای اصلی
            if "tg_user_id" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN tg_user_id INTEGER;")
            if "phone" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN phone TEXT;")
            if "status" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN status TEXT NOT NULL DEFAULT 'pending';")
            if "username" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN username TEXT;")
            if "full_name" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN full_name TEXT;")
            if "note" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN note TEXT;")
            if "city" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN city TEXT;")
            if "shop_name" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN shop_name TEXT;")
            if "created_at" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN created_at TEXT;")
            if "approved_at" not in cols:
                cur.execute("ALTER TABLE partners ADD COLUMN approved_at TEXT;")
            # ایندکس یکتا برای جلوگیری از درخواست تکراری
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_phone ON partners(phone);")
            cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_partners_tg_user_id ON partners(tg_user_id);")
        except Exception:
            pass

        # ول سفارشها
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                product_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                buyer_type TEXT
            );
            """
        )
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN buyer_type TEXT;")
        except sqlite3.OperationalError:
            pass
        # وضعیت سفارش: active | returned (برای مورد برگشت محصول)
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN status TEXT DEFAULT 'active';")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN feed_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN returned_at TEXT;")
        except sqlite3.OperationalError:
            pass
        # لینک دوطرفهٔ سفارش قدیم↔جدید در «تعویض کالا» — سفارش قدیم با status='returned'
        # (دقیقاً همون مکانیزم برگشت موجود، بدون نیاز به مقدار تازه‌ای برای status، پس
        # همهٔ ~۱۰ جای کد که از قبل «returned» رو از دید کاربر/گزارش مخفی می‌کنن دست‌نخورده
        # درست کار می‌کنن) + exchange_pair_id به سفارش جدید اشاره می‌کنه و برعکس.
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN exchange_pair_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        # علامت «اصلاح‌شده» — وقتی ادمین از صفحهٔ «ارسال مجدد» یه آیتم جایگزین از
        # همون محصول می‌فرسته (بدون تغییر قیمت/سفارش، فقط جایگزینی محتوای معیوب/اشتباه)،
        # این ستون ست می‌شه تا در لیست سفارش‌ها روشن باشه این تحویل پرداخت اضافی نداشته
        # (بخش ۴۱ CLAUDE.md — «استاندارد» درخواستی مالک پروژه برای وضوح وضعیت پرداخت).
        try:
            cur.execute("ALTER TABLE orders ADD COLUMN resent_at TEXT;")
        except sqlite3.OperationalError:
            pass

        # جدول تراکنشهای زرینپال
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS zarinpal_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                authority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        for col, decl in {
            "payment_type": "TEXT DEFAULT 'wallet'",
            "product_id": "INTEGER",
            "wallet_reserved": "INTEGER DEFAULT 0",
            "total_amount": "INTEGER",
            "buyer_type": "TEXT",
            "ref_id": "TEXT",
            "paid_at": "TEXT",
            "error": "TEXT",
            "gateway": "TEXT DEFAULT 'zarinpal'",
            # اطلاعات تکمیلی نتیجهٔ Verify — فقط برای حسابداری/پیگیری، نه اجباری برای هر
            # درگاه. card_pan از قبل توسط درگاه ماسک‌شده برمی‌گرده (نه شمارهٔ خام کارت).
            "card_pan": "TEXT",
            "card_hash": "TEXT",
            "fee_type": "TEXT",
            "fee": "INTEGER",
        }.items():
            try:
                cur.execute(f"ALTER TABLE zarinpal_transactions ADD COLUMN {col} {decl};")
            except sqlite3.OperationalError:
                pass
        # A1 — Ledger تراکنش: authority باید یکتا باشد (anchor برای ایمنی/ایدِمپوتنسی)
        # اگر DB قدیمی authority تکراری داشته باشد، ابتدا dedupe میکنیم و سپس ایندکس یکتا را میسازیم.
        try:
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
                "ON zarinpal_transactions(authority);"
            )
        except (sqlite3.IntegrityError, sqlite3.OperationalError):
            # نگه داشتن قدیمیترین رکورد هر authority و حذف بقیه
            cur.execute(
                """
                DELETE FROM zarinpal_transactions
                WHERE id NOT IN (
                    SELECT MIN(id) FROM zarinpal_transactions GROUP BY authority
                );
                """
            )
            cur.execute(
                "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
                "ON zarinpal_transactions(authority);"
            )


        # جدول فید محصولات (انبار تحویل خودکار)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS product_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
        # order_id/delivered_at قبلاً فقط داخل claim_next_feed_item (لیزی، هر بار
        # فراخوانی) اضافه می‌شدن — هم برخلاف قاعدهٔ پروژه برای جدول‌های هسته (باید
        # ایگر توی init_db باشن)، هم یه race condition واقعی داشت: با connection
        # pooling فعال (db_conn.py، DB_CONNECTION_POOL=1)، چند ترد هم‌زمان روی یه
        # دیتابیس کاملاً تازه می‌تونستن به‌ترتیب نامنظم دو ALTER رو (که توی یه
        # try/except مشترک بودن) اجرا کنن — اگه order_id قبلاً توسط ترد دیگه اضافه
        # شده بود، ALTER اول همون‌جا Exception می‌داد و ALTER دوم (delivered_at)
        # هیچ‌وقت اجرا نمی‌شد، یعنی «no such column: delivered_at» توی claim بعدی.
        # با تست مستقیم concurrent (۱۵ ترد هم‌زمان روی دیتابیس تازه) کشف شد.
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN order_id INTEGER;")
        except sqlite3.OperationalError:
            pass
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN delivered_at TEXT;")
        except sqlite3.OperationalError:
            pass

        # لینک پیام تحویل ↔ سفارش/فید — لازمه تا «برگشت» پنل بتونه پیام تحویل رو از چت
        # کاربر پاک کنه (بخش ۴۰ CLAUDE.md). قبلاً این جدول فقط لیزی، داخل خودِ
        # order_mark_returned_advanced ساخته می‌شد — یعنی روی یه دیتابیس کاملاً تازه،
        # اگه اولین خرید قبل از اولین «برگشت» ادمین اتفاق می‌افتاد، INSERT مسیرهای
        # تحویل (بات/درگاه/مینی‌اپ) با «no such table» بی‌صدا شکست می‌خورد. الان طبق
        # قاعدهٔ پروژه برای جدول‌های هسته، ایگر اینجاست.
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY, order_id INTEGER,
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL
            );
        """)

        # تنظیمات هشدار کمبود موجودی فید (برای هر محصول)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS feed_alert_settings (
                product_id INTEGER PRIMARY KEY,
                threshold INTEGER NOT NULL DEFAULT 5,
                last_notified_remaining INTEGER,
                updated_at TEXT NOT NULL
            );
            """
        )

        # جدول سرویسهای «سایر محصولات» (زیرشاخههای پویا مثل Gmail/Yahoo و ...)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS other_services (
                service_key TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                emoji TEXT,
                is_active INTEGER NOT NULL DEFAULT 1,
                created_at TEXT NOT NULL
            );
            """
        )

        seed_defaults = os.getenv("SEED_DEFAULT_DATA", "0") == "1"



        # اگر هیچ سرویسی تعریف نشده بود، پیشفرض جیمیل را اضافه کن
        cur.execute("SELECT COUNT(*) FROM other_services;")
        svc_count = cur.fetchone()[0] or 0
        if seed_defaults and svc_count == 0:
            now = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?, ?, ?, ?, ?);",
                ("gmail", "سرویسهای جیمیل", "✉️", 1, now),
            )


        # اگر هیچ محصولی وجود نداشت، چند محصول نمونه اضافه کن
        cur.execute("SELECT COUNT(*) FROM products;")
        count = cur.fetchone()[0] or 0
        if seed_defaults and count == 0:
            sample_products = [
                ("apple", "apple_ready_1", "اپل آیدی آماده ریجن آمریکا", 250000,
                 "تحویل فوری، آمریکا، بدون سوال امنیتی.", 1),
                ("apple", "apple_ready_2", "اپل آیدی آماده ریجن ترکیه", 130000,
                 "تحویل فوری، ترکیه، مناسب خریدهای ارزانتر.", 1),
                ("apple", "apple_ready_3", "ساخت اپل آیدی با ایمیل شما", 170000,
                 "ساخت دستی، تنظیم ریجن مناسب، تحویل ۳۰ دقیقهای.", 1),
                ("gmail", "gmail_ready_1", "جیمیل آماده سنی وریفای شده", 90000,
                 "ایدهآل برای سرویسهای تحریممحور، سنی بالای ۱۸ سال.", 1),
                ("gmail", "gmail_ready_2", "جیمیل اختصاصی با مشخصات شما", 110000,
                 "ساخت اختصاصی، تحویل تا ۱ ساعت.", 1),
            ]
            cur.executemany(
                """
                INSERT INTO products (category, product_key, title, price, description, is_active)
                VALUES (?, ?, ?, ?, ?, ?);
                """,
                sample_products,
            )

        # جدول دستهبندیهای داینامیک (نامحدود، درختی)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL,
                parent_id INTEGER REFERENCES categories(id) ON DELETE CASCADE,
                emoji TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # ستون category_id برای محصولات
        try:
            cur.execute("ALTER TABLE products ADD COLUMN category_id INTEGER REFERENCES categories(id);")
        except sqlite3.OperationalError:
            pass

        # جدول کاربران (برای Broadcast)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                full_name TEXT,
                first_seen TEXT DEFAULT CURRENT_TIMESTAMP,
                last_seen TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # جدول پیامهای تیکت (تاریخچه مکالمه)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                text TEXT,
                media_type TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )

        # جدول متنهای رابط کاربری (UI)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ui_texts (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        conn.commit()
    finally:
        conn.close()

    # ⚡ ساخت ایندکس‌ها برای سرعت — حیاتی برای عملکرد در حجم بالا
    ensure_indexes()

    # ⚠️ کشف‌شده روی سرور تولید واقعی: بعضی جدول‌ها (bot_config، احتمالاً بقیهٔ
    # جدول‌های زیر هم) روی Postgres تولید بدون محدودیت یکتایی واقعی ساخته شده
    # بودن (احتمالاً از migrate_to_postgres.py) — یعنی همهٔ کوئری‌های ON CONFLICT
    # پروژه (بخش ۴۶ سند) با psycopg2.errors.InvalidColumnReference شکست می‌خوردن.
    # این‌جا یک‌بار برای همهٔ جدول‌های شناخته‌شدهٔ ON-CONFLICT-محور به‌طور مرکزی
    # چک/رفع می‌شه (به‌جای پخش‌کردن چک در ۱۵+ نقطهٔ CREATE TABLE پراکنده).
    _ensure_postgres_constraints()

    _DB_INIT_DONE_PATH = DB_FULL_PATH


def _ensure_postgres_constraints() -> None:
    """فقط زیر Postgres کاری می‌کنه (db_conn.ensure_unique_constraint خودش no-op
    می‌شه زیر SQLite). لیست کامل جدول+ستون‌هایی که کد پروژه براشون ON CONFLICT
    می‌زنه (بخش ۴۶ سند)."""
    try:
        import db_conn as _dc
        if not _dc.is_postgres():
            return
        conn = _get_connection()
        try:
            for table, cols in [
                ("bot_config", ["key"]),
                ("users", ["user_id"]),
                ("wallets", ["user_id"]),
                ("admin_preferences", ["admin_id", "key"]),
                ("delivery_messages", ["feed_id"]),
                ("pending_deliveries", ["order_id"]),
                ("partner_bank_info", ["user_id"]),
            ]:
                try:
                    _dc.ensure_unique_constraint(conn, table, cols)
                except Exception:
                    pass
        finally:
            conn.close()
    except Exception:
        pass


_INDEXES_READY = False
_INDEXES_DONE: set = set()  # نام ایندکس‌هایی که قبلاً با موفقیت ساخته شدن (فلگ per-process به‌ازای هر ایندکس)
_ENSURE_PARTNER_TIERS_EXTENDED_DONE = False
_ENSURE_PAYOUT_SETTINGS_EXTENDED_DONE = False
_ENSURE_REFERRAL_SCHEMA_DONE = False
_ENSURE_PARTNER_WALLET_SCHEMA_DONE = False
_ENSURE_PARTNER_SYSTEM_SCHEMA_DONE = False
_ENSURE_PARTNER_BANK_SCHEMA_DONE = False
_ENSURE_PARTNER_BANK_ADDRESS_DONE = False
_ENSURE_INVITE_CAP_SCHEMA_DONE = False
_ENSURE_ACCOUNTING_SCHEMA_DONE = False
_ENSURE_RATINGS_SCHEMA_DONE = False
_ENSURE_CARD_RECEIPTS_SCHEMA_DONE = False
_ENSURE_USER_EXTRA_SCHEMA_DONE = False
_ENSURE_ADMIN_NOTES_SCHEMA_DONE = False
_ENSURE_FAQ_SCHEMA_DONE = False

def ensure_indexes():
    """
    ساخت ایندکس روی ستون‌های پرمصرف — فقط یک‌بار در هر پروسه.
    ⚡ این توابع نتیجه‌ی کوئری‌ها را تغییر نمی‌دهند، فقط سرعت را چند صد برابر می‌کنند.
    بدون ایندکس، هر JOIN/WHERE روی این ستون‌ها = اسکن کامل جدول.
    """
    global _INDEXES_READY
    # مهاجرت ستون‌های orders — فقط یک‌بار (چون ALTER گران است)
    if not _INDEXES_READY:
        _INDEXES_READY = True
        for _col, _decl in [("status", "TEXT DEFAULT 'active'"), ("feed_id", "INTEGER"), ("returned_at", "TEXT")]:
            try:
                _c = _get_connection()
                _c.execute(f"ALTER TABLE orders ADD COLUMN {_col} {_decl};")
                _c.commit(); _c.close()
            except Exception:
                try: _c.close()
                except Exception: pass
    # هر ایندکس در try جدا — اگر جدول/ستون نبود، بی‌صدا رد شود (قانون ۱۳)
    index_defs = [
        # سفارش‌ها — پرمصرف‌ترین: JOIN با users، فیلتر status، جستجوی user_id
        ("idx_orders_user_id",       "orders(user_id)"),
        ("idx_orders_status",        "orders(status)"),
        ("idx_orders_product_id",    "orders(product_id)"),
        # created_at — داشبورد پنل هر بار ۳ کوئری روی این ستون می‌زند (امروز/دیروز/نمودار ۳۰ روزه)؛
        # بدون ایندکس، هر بار اسکن کامل جدول orders (بخش ۲۳ سند — رفع کندی داشبورد)
        ("idx_orders_created_at",    "orders(created_at)"),
        # معرفی‌ها — محاسبه پورسانت و آمار
        ("idx_referrals_referrer",   "referrals(referrer_id)"),
        ("idx_referrals_referred",   "referrals(referred_id)"),
        # کیف‌پول و تراکنش‌ها
        ("idx_wallets_user",         "wallets(user_id)"),
        ("idx_ptx_user",             "partner_transactions(user_id)"),
        ("idx_ppayouts_user",        "partner_payouts(user_id)"),
        ("idx_ppayouts_status",      "partner_payouts(status)"),
        ("idx_pwallets_user",        "partner_wallets(user_id)"),
        # موجودی محصولات — feed
        ("idx_feed_product",         "product_feed(product_id)"),
        ("idx_feed_delivered",       "product_feed(product_id, delivered)"),
        # لوکاپ معکوس order_id→feed_id — order_mark_returned_advanced/exchange_order
        # (بخش ۴۰ سند) هر برگشت/تعویض رو با این چک می‌کنن؛ بدون ایندکس با رشد
        # product_feed هر برگشت یک full-scan کامل جدول می‌شه
        ("idx_feed_order_id",        "product_feed(order_id)"),
        # دسته‌بندی محصولات
        ("idx_products_category",    "products(category)"),
        ("idx_products_active",      "products(is_active)"),
        # کاربران
        ("idx_users_username",       "users(username)"),
        # همکاران
        ("idx_partners_tg",          "partners(tg_user_id)"),
        ("idx_partners_status",      "partners(status)"),
        # فروش فوری
        ("idx_flash_product",        "flash_sales(product_id, is_active)"),
        # امتیازها
        ("idx_ratings_product",      "product_ratings(product_id)"),
        # تیکت‌ها — لیست/فیلتر/شمارندهٔ badge روی status و type، پیام‌ها با subquery
        # همبسته به ازای هر ردیف تیکت (msg_count) — بدون این ایندکس‌ها صفحهٔ تیکت‌ها
        # با رشد داده به‌طور فزاینده کند می‌شه (اسکن کامل جدول در هر بار)
        ("idx_tickets_status",       "tickets(status)"),
        ("idx_tickets_type",         "tickets(type)"),
        # بستن خودکار تیکت راه‌اندازی وابسته موقع برگشت/تعویض سفارش (بخش ۳۶/۴۰ سند)
        # با WHERE order_id=? جست‌وجو می‌کنه — بدون ایندکس full-scan جدول تیکت‌ها
        ("idx_tickets_order_id",     "tickets(order_id)"),
        ("idx_ticket_messages_tid",  "ticket_messages(ticket_id)"),
        # رسیدهای کارت‌به‌کارت — لیست/شمارندهٔ badge روی status
        ("idx_card_receipts_status", "card_receipts(status)"),
        # کدهای تخفیف — validate_discount هر بار با WHERE code=? COLLATE NOCASE
        # جست‌وجو می‌کنه (مسیر hot-path خرید)؛ discount_usage هم با code_id+user_id
        # برای شمارش سقف استفادهٔ هر کاربر (بخش ۲۴ ممیزی)
        ("idx_discount_codes_code",  "discount_codes(code COLLATE NOCASE)"),
        ("idx_discount_usage_cu",    "discount_usage(code_id, user_id)"),
    ]
    # این تابع از ticket_ensure_schema() هم صدا زده می‌شه که هر /start ربات اجراش می‌کنه؛
    # هر ایندکسی که قبلاً با موفقیت ساخته شده رو دیگه دوباره امتحان نمی‌کنیم (فلگ per-process
    # به‌ازای هر ایندکس، نه یک فلگ کلی — چون بعضی جدول‌ها مثل tickets موقع اولین صدازدن از
    # داخل init_db هنوز ساخته نشدن، پس نباید کل حلقه رو یک‌بار-برای-همیشه قفل کرد).
    remaining = [(n, t) for n, t in index_defs if n not in _INDEXES_DONE]
    if not remaining:
        return
    conn = _get_connection()
    try:
        for name, target in remaining:
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {name} ON {target};")
                _INDEXES_DONE.add(name)
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def get_wallet_balance(user_id: int) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
    row = cur.fetchone()
    conn.close()
    if not row:
        return 0
    return int(row[0])


def add_wallet_balance(user_id: int, amount: int) -> int:
    """
    موجودی را افزایش میدهد و موجودی جدید را برمیگرداند.
    """
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
        row = cur.fetchone()
        if row:
            new_balance = int(row[0]) + int(amount)
            cur.execute(
                "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
                (new_balance, now, user_id),
            )
        else:
            new_balance = int(amount)
            cur.execute(
                "INSERT INTO wallets (user_id, balance, updated_at) VALUES (?, ?, ?);",
                (user_id, new_balance, now),
            )
        conn.commit()
        return new_balance
    finally:
        conn.close()


def subtract_wallet_balance(user_id: int, amount: int) -> bool:
    """
    اگر موجودی کافی باشد، مبلغ را کم میکند و True برمیگرداند؛ در غیر این صورت False.
    از BEGIN IMMEDIATE برای جلوگیری از race condition بین دو کسر همزمان (مثلاً
    دبل‌تپ دکمهٔ خرید، یا خرید همزمان از بات و مینی‌اپ) استفاده میشه — همون الگوی
    claim_next_feed_item. تنها نقطهٔ کسر کیف‌پول اصلی باید همینجا باشه؛ هیچ کد
    دیگه‌ای نباید مستقیم روی جدول wallets UPDATE بزنه (بخش ۱ سند مینی‌اپ).
    """
    amount = int(amount)
    conn = _get_connection()
    cur = conn.cursor()
    try:
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute(f"SELECT balance FROM wallets WHERE user_id = ? {_row_lock_suffix()};", (user_id,))
        row = cur.fetchone()
        if not row:
            conn.commit()
            return False
        balance = int(row[0])
        if balance < amount:
            conn.commit()
            return False

        new_balance = balance - amount
        now = datetime.utcnow().isoformat()
        cur.execute(
            "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
            (new_balance, now, user_id),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    return True


def set_wallet_balance(user_id: int, new_balance: int) -> int:
    """
    مستقیماً موجودی کیف پول را روی مقدار دلخواه تنظیم میکند (برای ادمین).
    """
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT balance FROM wallets WHERE user_id = ?;", (user_id,))
        row = cur.fetchone()
        if row:
            cur.execute(
                "UPDATE wallets SET balance = ?, updated_at = ? WHERE user_id = ?;",
                (int(new_balance), now, user_id),
            )
        else:
            cur.execute(
                "INSERT INTO wallets (user_id, balance, updated_at) VALUES (?, ?, ?);",
                (user_id, int(new_balance), now),
            )
        conn.commit()
        return int(new_balance)
    finally:
        conn.close()


# ========= ORDERS =========


def create_order(user_id: int, category: str, title: str, price: int, product_id=None, buyer_type: str | None = None) -> int:
    """
    یک سفارش جدید ثبت میکند و id سفارش را برمیگرداند.
    """
    now = datetime.utcnow().isoformat()
    product_id_str = str(product_id) if product_id is not None else ""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (user_id, category, product_id, title, price, created_at, buyer_type)
            VALUES (?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, category, product_id_str, title, int(price), now, buyer_type),
        )
        order_id = cur.lastrowid
        conn.commit()
        return order_id
    finally:
        conn.close()


def get_recent_orders_by_user(user_id: int, limit: int = 10):
    """۵ خرید آخر برای «🛒 خریدهای من» — سفارش‌های برگشت‌خورده مثل بقیهٔ لیست‌های
    مشابه پروژه (get_user_orders) از دید کاربر مخفی می‌مانند (قانون ۷ پروژه)."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, title, price, created_at
            FROM orders
            WHERE CAST(user_id AS INTEGER) = ?
              AND COALESCE(status,'active') != 'returned'
            ORDER BY id DESC
            LIMIT ?;
            """,
            (int(user_id), limit),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def get_recent_orders_global(limit: int = 15):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, title, price, created_at
            FROM orders
            ORDER BY id DESC
            LIMIT ?;
            """,
            (limit,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


# ========= PRODUCTS =========


def get_products_by_category(category: str):
    """
    محصولات یک دسته را برمیگرداند.
    خروجی همیشه ۷ فیلد است:
    (id, category, title, price, description, is_active, partner_price)
    اگر ستون partner_price وجود نداشت، مقدار آن None خواهد بود.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # بررسی وجود ستون partner_price
        try:
            pass
        except Exception:
            pass
        cur.execute(
            """
            SELECT id, category, title, price, description, is_active,
                   COALESCE(partner_price, 0) AS partner_price
            FROM products
            WHERE category = ?
            ORDER BY id ASC;
            """,
            (category,),
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows

def get_product_by_id(pid: int):
    ensure_product_support_schema()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        select_cols = [
            'id', 'category', 'title', 'price', 'description', 'is_active',
            'COALESCE(partner_price, 0) AS partner_price',
            'COALESCE(daily_limit_customer, 0) AS daily_limit_customer',
            'COALESCE(daily_limit_partner, 0) AS daily_limit_partner',
            "COALESCE(image_url, '') AS image_url",
            "COALESCE(notify_on_restock, 0) AS notify_on_restock",
            "COALESCE(require_terms, 0) AS require_terms",
            "COALESCE(terms_text, '') AS terms_text",
            "created_by", "created_at",
        ]
        cur.execute(
            f"SELECT {', '.join(select_cols)} FROM products WHERE id = ?;",
            (pid,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    # همیشه dict برگردان تا هم [index] هم ["key"] هم .get() کار کند
    # (سازگاری با کدی که product را به هر دو شکل استفاده می‌کند)
    if row is None:
        return None
    return _RowCompat(row)

def update_product_field(pid: int, field: str, value):
    """
    ویرایش فیلدهای مجاز محصول.
    """
    allowed = {"title", "price", "partner_price", "daily_limit_customer", "daily_limit_partner", "description", "is_active"}
    if field not in allowed:
        raise ValueError("Invalid product field")

    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            f"UPDATE products SET {field} = ? WHERE id = ?;",
            (value, pid),
        )
        conn.commit()
    finally:
        conn.close()


def toggle_product_active(pid: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("SELECT is_active FROM products WHERE id = ?;", (pid,))
        row = cur.fetchone()
        if not row:
            return
        current = int(row[0]) or 0
        new_val = 0 if current else 1
        cur.execute(
            "UPDATE products SET is_active = ? WHERE id = ?;",
            (new_val, pid),
        )
        conn.commit()
    finally:
        conn.close()


def add_product(category: str, title: str, price: int, description: str = "", is_active: int = 1, partner_price: int | None = None) -> int:
    """
    یک محصول جدید اضافه میکند و id آن را برمیگرداند.
    product_key یا code بهصورت خودکار از روی عنوان ساخته میشود.
    اگر جدول محصولات ستون product_key یا code داشته باشد، مقدار مناسب در هر ستون درج میشود.
    اگر ستون partner_price وجود داشته باشد و partner_price داده شود، در همان ستون درج میشود.
    """
    # generate slug from title
    slug = "".join(ch if ch.isalnum() else "_" for ch in title)
    slug = slug.lower().strip("_") or "product"
    if len(slug) > 40:
        slug = slug[:40]
    conn = _get_connection()
    cur = conn.cursor()
    # discover columns in products table
    # ⚠️ رفع‌شده (بخش ۱۴ آیتم ۶ سند): قبلاً اینجا `cols = set()` بدون هیچ پر شدنی
    # بود — یعنی 'product_key' in cols همیشه False می‌شد و ستون NOT NULL
    # product_key هیچ‌وقت درج نمی‌شد → ویزارد افزودن محصول با IntegrityError می‌شکست.
    try:
        cols = {row[1] for row in cur.execute("PRAGMA table_info(products);").fetchall()}
    except Exception:
        cols = set()

    # base columns
    col_names = []
    values = []
    # category
    col_names.append("category"); values.append(category)

    # product_key / code handling
    if 'product_key' in cols:
        col_names.append("product_key"); values.append(slug)
    if 'code' in cols:
        col_names.append("code"); values.append(slug)

    col_names.append("title"); values.append(title)
    col_names.append("price"); values.append(int(price))
    col_names.append("description"); values.append(description)
    col_names.append("is_active"); values.append(int(is_active))

    if 'partner_price' in cols and partner_price is not None:
        col_names.append("partner_price"); values.append(int(partner_price))

    placeholders = ", ".join(["?"] * len(col_names))
    sql = f"INSERT INTO products ({', '.join(col_names)}) VALUES ({placeholders});"
    cur.execute(sql, tuple(values))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_product_chat_enabled(product_id: int) -> int:
    """چک chat_enabled برای محصول — از _get_connection() استفاده می‌کنه (به‌جای
    sqlite3.connect خام مستقلی که قبلاً در bot.py بود، بخش ۱۴ آیتم ۳ سند)."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT chat_enabled FROM products WHERE id=? LIMIT 1;", (int(product_id),)).fetchone()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def set_product_chat_enabled(product_id: int, enabled: int) -> None:
    conn = _get_connection()
    try:
        conn.execute("UPDATE products SET chat_enabled=? WHERE id=?;", (int(enabled), int(product_id)))
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def delete_product(product_id: int) -> None:
    """حذف واقعی (Hard Delete) یک محصول بر اساس id.

    علاوه بر حذف رکورد محصول، آیتمهای فید مرتبط با آن نیز پاک میشوند تا رکورد یتیم باقی نماند.
    """
    conn = _get_connection()
    cur = conn.cursor()
    # پاکسازی فیدهای مرتبط (در صورت وجود)
    try:
        cur.execute("DELETE FROM product_feed WHERE product_id = ?;", (product_id,))
    except Exception:
        # اگر جدول/ستون وجود نداشت، حذف محصول را انجام بده
        pass
    cur.execute("DELETE FROM products WHERE id = ?;", (product_id,))
    conn.commit()
    conn.close()



# ========= STATS =========


def get_stats():
    """برگشت آمار کلی: (تعداد کیفها، جمع موجودیها، تعداد سفارشها، مجموع فروش، تعداد محصولات فعال)"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        # کیف پولها
        cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
        wallet_row = cur.fetchone()
        total_wallets = wallet_row[0] or 0
        total_balance = wallet_row[1] or 0
        # سفارشها
        cur.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders;")
        order_row = cur.fetchone()
        total_orders = order_row[0] or 0
        total_sales = order_row[1] or 0
        # محصولات فعال
        cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
        active_products = cur.fetchone()[0] or 0
    finally:
        conn.close()
    return total_wallets, total_balance, total_orders, total_sales, active_products
def create_zarinpal_pending_transaction(user_id: int, amount: int, authority: str) -> bool:
    """یک رکورد pending برای authority میسازد. اگر authority قبلا ثبت شده باشد False برمیگرداند."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            INSERT INTO zarinpal_transactions (user_id, amount, authority, status, created_at)
            VALUES (?, ?, ?, 'pending', ?);
            """,
            (int(user_id), int(amount), str(authority), now),
        )
        conn.commit()
        return True
    except _INTEGRITY_ERRORS:
        return False
    finally:
        conn.close()


def get_zarinpal_transaction(authority: str):
    """برگشت: dict یا None"""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, user_id, amount, authority, status, created_at
            FROM zarinpal_transactions
            WHERE authority = ?
            LIMIT 1;
            """,
            (str(authority),),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return {
        "id": row[0],
        "user_id": row[1],
        "amount": row[2],
        "authority": row[3],
        "status": row[4],
        "created_at": row[5],
    }


def update_zarinpal_status(authority: str, new_status: str, expected_current: str | None = None) -> int:
    """status را تغییر میدهد. اگر expected_current داده شود فقط وقتی status فعلی همان باشد update میکند.
    خروجی: تعداد ردیفهای تغییرکرده (0 یا 1).
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if expected_current is None:
            cur.execute(
                "UPDATE zarinpal_transactions SET status = ? WHERE authority = ?;",
                (str(new_status), str(authority)),
            )
        else:
            cur.execute(
                "UPDATE zarinpal_transactions SET status = ? WHERE authority = ? AND status = ?;",
                (str(new_status), str(authority), str(expected_current)),
            )
        conn.commit()
        changed = cur.rowcount or 0
        return int(changed)
    finally:
        conn.close()


    cur = conn.cursor()

    # کیف پولها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(balance), 0) FROM wallets;")
    wallet_row = cur.fetchone()
    total_wallets = wallet_row[0] or 0
    total_balance = wallet_row[1] or 0

    # سفارشها
    cur.execute("SELECT COUNT(*), COALESCE(SUM(price), 0) FROM orders;")
    order_row = cur.fetchone()
    total_orders = order_row[0] or 0
    total_sales = order_row[1] or 0

    # محصولات فعال
    cur.execute("SELECT COUNT(*) FROM products WHERE is_active = 1;")
    active_products = cur.fetchone()[0] or 0

    conn.close()
    return total_wallets, total_balance, total_orders, total_sales, active_products


# ========= PRODUCT FEED (انبار تحویل خودکار) =========


def add_feed_items(product_id: int, items):
    """
    چند آیتم را برای یک محصول ثبت میکند.
    تکراریها ثبت میشوند اما flagged میشوند.
    Returns: {"added": int, "duplicates": list}
    """
    if not items:
        return {"added": 0, "duplicates": []}

    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        # پیدا کردن تکراریها
        duplicates = []
        for item in items:
            existing = conn.execute(
                "SELECT id FROM product_feed WHERE product_id=? AND data=? AND delivered=0 LIMIT 1;",
                (product_id, item)
            ).fetchone()
            if existing:
                duplicates.append(item)

        # ثبت همه (اعم از تکراری)
        rows = [(product_id, item, 0, now) for item in items]
        conn.executemany(
            "INSERT INTO product_feed (product_id, data, delivered, created_at) VALUES (?, ?, ?, ?);",
            rows,
        )
        conn.commit()
        return {"added": len(rows), "duplicates": duplicates}
    finally:
        conn.close()


def get_feed_stats(product_id: int):
    """
    تعداد کل، تعداد تحویل نشده، تعداد تحویل شده را برمیگرداند.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ?;",
            (product_id,),
        )
        total = cur.fetchone()[0] or 0

        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ? AND delivered = 0;",
            (product_id,),
        )
        remaining = cur.fetchone()[0] or 0

        delivered = total - remaining
    finally:
        conn.close()
    return total, remaining, delivered


def claim_next_feed_item(product_id: int, order_id: int = None):
    """
    اتمیک: اولین آیتم تحویلنشده را claim میکند (delivered=1) و برمیگرداند: (feed_id, data) یا None.
    از BEGIN IMMEDIATE برای جلوگیری از race condition در خریدهای همزمان استفاده میشه.
    """
    conn = _get_connection()
    cur = conn.cursor()
    try:
        # migration fallback — این ستون‌ها الان ایگر توی init_db اضافه می‌شن (بالای
        # همین فایل)؛ این بلوک فقط برای دیتابیس‌هایی که هنوز init_db تازه رو ندیدن
        # نگه داشته شده. هر ALTER جدا try/except داره — قبلاً هر دو تو یه try
        # مشترک بودن که یه race condition واقعی داشت (جزئیات بالای init_db).
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN order_id INTEGER;")
            conn.commit()
        except Exception:
            pass
        try:
            cur.execute("ALTER TABLE product_feed ADD COLUMN delivered_at TEXT;")
            conn.commit()
        except Exception:
            pass

        cur.execute("BEGIN IMMEDIATE;")
        cur.execute(
            f"""SELECT id, data FROM product_feed
               WHERE product_id=? AND delivered=0
               ORDER BY id ASC LIMIT 1 {_row_lock_suffix()};""",
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            conn.commit()
            return None

        feed_id, feed_data = row[0], row[1]

        # چک مضاعف: مطمئن شو این آیتم قبلاً تحویل داده نشده
        cur.execute("SELECT delivered FROM product_feed WHERE id=?;", (feed_id,))
        chk = cur.fetchone()
        if not chk or chk[0] != 0:
            conn.rollback()
            return None

        cur.execute(
            "UPDATE product_feed SET delivered=1, order_id=?, delivered_at=datetime('now') WHERE id=? AND delivered=0;",
            (order_id, feed_id),
        )
        if cur.rowcount != 1:
            conn.rollback()
            return None

        conn.commit()
        return feed_id, feed_data
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_next_feed_item(product_id: int):
    """
    Deprecated (non-atomic). Use claim_next_feed_item.
    Retained for backward compatibility.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, data
            FROM product_feed
            WHERE product_id = ? AND delivered = 0
            ORDER BY id ASC
            LIMIT 1;
            """,
            (product_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    if not row:
        return None
    return row[0], row[1]


def mark_feed_item_delivered(feed_id: int):
    """
    Marks a feed item delivered. Prefer claim_next_feed_item for user delivery path.
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE product_feed SET delivered = 1 WHERE id = ?;",
            (feed_id,),
        )
        conn.commit()
    finally:
        conn.close()



def list_feed_items(product_id: int, delivered: int | None = None, limit: int = 10, offset: int = 0):
    """لیست آیتمهای فید یک محصول را برمیگرداند.

    delivered:
      - None: همه
      - 0: فقط تحویلنشده
      - 1: فقط تحویلشده
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()

        if delivered is None:
            cur.execute(
                """
                SELECT id, data, delivered, created_at
                FROM product_feed
                WHERE product_id = ?
                ORDER BY delivered ASC, id DESC
                LIMIT ? OFFSET ?;
                """,
                (product_id, int(limit), int(offset)),
            )
        else:
            cur.execute(
                """
                SELECT id, data, delivered, created_at
                FROM product_feed
                WHERE product_id = ? AND delivered = ?
                ORDER BY id DESC
                LIMIT ? OFFSET ?;
                """,
                (product_id, int(delivered), int(limit), int(offset)),
            )

        rows = cur.fetchall() or []
    finally:
        conn.close()
    return rows


def count_feed_items(product_id: int, delivered: int | None = None) -> int:
    conn = _get_connection()
    cur = conn.cursor()
    if delivered is None:
        cur.execute("SELECT COUNT(*) FROM product_feed WHERE product_id = ?;", (product_id,))
    else:
        cur.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id = ? AND delivered = ?;",
            (product_id, int(delivered)),
        )
    n = cur.fetchone()[0] or 0
    conn.close()
    return int(n)


def get_available_stock(product_id: int) -> int:
    """تعداد آیتم موجود (تحویل‌نشده) این محصول — منبع واحد تشخیص «ناموجود» در کل پروژه."""
    return count_feed_items(product_id, delivered=0)


def set_feed_item_delivered(feed_id: int, delivered: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE product_feed SET delivered = ? WHERE id = ?;",
            (int(1 if delivered else 0), int(feed_id)),
        )
        conn.commit()
    finally:
        conn.close()


def delete_feed_item(feed_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM product_feed WHERE id = ?;", (int(feed_id),))
        conn.commit()
    finally:
        conn.close()



def list_other_services(active_only: bool = True):
    """لیست سرویسهای «سایر محصولات» را برمیگرداند."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if active_only:
            cur.execute(
                "SELECT service_key, title, COALESCE(emoji,''), is_active FROM other_services WHERE is_active=1 ORDER BY title;"
            )
        else:
            cur.execute(
                "SELECT service_key, title, COALESCE(emoji,''), is_active FROM other_services ORDER BY title;"
            )
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def add_other_service(service_key: str, title: str, emoji: str = "🧩") -> bool:
    """یک سرویس جدید اضافه میکند. اگر کلید تکراری باشد False برمیگرداند."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?, ?, ?, 1, ?);",
            (service_key, title, emoji, now),
        )
        conn.commit()
        return True
    except _INTEGRITY_ERRORS:
        return False
    finally:
        conn.close()


def delete_other_service(service_key: str, delete_products: bool = True) -> None:
    """یک سرویس را حذف میکند. در صورت delete_products محصولات و فیدهای آن سرویس هم پاک میشود."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        if delete_products:
            # حذف فیدهای مربوط به محصولات این دسته
            cur.execute(
                "DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category=?);",
                (service_key,),
            )
            # حذف محصولات این دسته
            cur.execute("DELETE FROM products WHERE category=?;", (service_key,))
        # حذف خود سرویس
        cur.execute("DELETE FROM other_services WHERE service_key=?;", (service_key,))
        conn.commit()
    finally:
        conn.close()

# ========= FEED ALERT SETTINGS =========

def get_feed_alert_setting(product_id: int):
    """برمیگرداند: (threshold, last_notified_remaining). اگر تنظیمی نبود threshold=5."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "SELECT threshold, last_notified_remaining FROM feed_alert_settings WHERE product_id=?;",
            (product_id,),
        )
        row = cur.fetchone()
        if not row:
            threshold = 5
            last = None
            now = datetime.utcnow().isoformat()
            cur.execute(
                "INSERT OR IGNORE INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?);",
                (product_id, threshold, now),
            )
            conn.commit()
            return threshold, last
        return int(row[0]), row[1]
    finally:
        conn.close()


def set_feed_alert_threshold(product_id: int, threshold: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, ?, NULL, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET threshold=excluded.threshold, updated_at=excluded.updated_at;",
            (product_id, int(threshold), now),
        )
        conn.commit()
    finally:
        conn.close()


def reset_feed_alert_notification(product_id: int):
    """پس از شارژ مجدد موجودی، هشدار قبلی ریست میشود تا دوباره ارسال شود."""
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, NULL, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=NULL, updated_at=excluded.updated_at;",
            (product_id, now),
        )
        conn.commit()
    finally:
        conn.close()


def set_feed_alert_last_notified(product_id: int, remaining: int):
    now = datetime.utcnow().isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?, 5, ?, ?) "
            "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=excluded.last_notified_remaining, updated_at=excluded.updated_at;",
            (product_id, int(remaining), now),
        )
        conn.commit()
    finally:
        conn.close()

# =====================
# Partner / Reseller API
# =====================

def upsert_partner_request(tg_user_id: int, phone: str, username: str = "", full_name: str = "", note: str = "", city: str = "", shop_name: str = ""):
    """ثبت درخواست نمایندگی.

    سیاست فعلی: هر کاربر/شماره فقط یکبار میتواند درخواست ثبت کند.
    بنابراین اگر رکوردی وجود داشته باشد، وضعیت آن را به pending برنمیگردانیم.
    - pending: فقط اطلاعات پروفایل را بهروزرسانی میکنیم (بدون تغییر created_at)
    - approved: فقط اطلاعات پروفایل را بهروزرسانی میکنیم (بدون تغییر approved_at)
    - rejected: فقط اطلاعات پروفایل را بهروزرسانی میکنیم
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec='seconds')

        cur.execute("SELECT id, status, created_at, approved_at FROM partners WHERE tg_user_id = ? OR phone = ? ORDER BY id DESC LIMIT 1;", (tg_user_id, phone))
        row = cur.fetchone()

        if row:
            pid, st, created_at, approved_at = row[0], (row[1] or "").strip().lower(), row[2], row[3]
            if st == "pending":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            elif st == "approved":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            elif st == "rejected":
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
            else:
                # وضعیتهای ناشناخته: مثل pending رفتار کن
                cur.execute(
                    """
                    UPDATE partners
                    SET tg_user_id = ?, phone = ?, username = ?, full_name = ?, note = ?,
                        city = COALESCE(?, city), shop_name = COALESCE(?, shop_name)
                    WHERE id = ?;
                    """,
                    (tg_user_id, phone, username, full_name, note, city or None, shop_name or None, pid),
                )
        else:
            cur.execute(
                """
                INSERT OR IGNORE INTO partners (tg_user_id, phone, status, username, full_name, note, city, shop_name, created_at)
                VALUES (?, ?, 'pending', ?, ?, ?, ?, ?, ?);
                """,
                (tg_user_id, phone, username, full_name, note, city, shop_name, now),
            )

        conn.commit()
    finally:
        conn.close()



def update_partner_city_shop(tg_user_id: int, city: str = "", shop_name: str = ""):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE partners SET city = COALESCE(?, city), shop_name = COALESCE(?, shop_name) WHERE tg_user_id = ?;",
            (city or None, shop_name or None, tg_user_id),
        )
        conn.commit()
    finally:
        conn.close()


def get_partner_by_user_id(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
            FROM partners WHERE tg_user_id = ? ORDER BY id DESC LIMIT 1;
            """,
            (tg_user_id,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row


def get_partner_by_phone(phone: str):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT id, tg_user_id, phone, status, username, full_name, note, created_at, approved_at
            FROM partners WHERE phone = ? ORDER BY id DESC LIMIT 1;
            """,
            (phone,),
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row

def list_partner_requests(status: str | None = None, query: str | None = None, limit: int = 50, offset: int = 0):
    """لیست درخواستهای همکار با امکان فیلتر وضعیت و جستجو.

    خروجی: (id, tg_user_id, phone, username, full_name, city, shop_name, status, created_at, approved_at)
    """
    conn = _get_connection()
    try:
        cur = conn.cursor()
        sql = """
            SELECT id, tg_user_id, phone, username, full_name, city, shop_name, status, created_at, approved_at
            FROM partners
            WHERE 1=1
        """
        params: list = []
        if status:
            sql += " AND status = ?"
            params.append(status)
        if query:
            q = f"%{query.strip()}%"
            # LOWER(...) LIKE LOWER(?) — یوزرنیم تلگرام همیشه لاتینه؛ LIKE خام
            # روی SQLite حساس به بزرگ/کوچیک نیست ولی روی Postgres هست (بخش ۵۲).
            sql += " AND (LOWER(phone) LIKE LOWER(?) OR LOWER(username) LIKE LOWER(?) OR LOWER(full_name) LIKE LOWER(?) OR LOWER(city) LIKE LOWER(?) OR LOWER(shop_name) LIKE LOWER(?))"
            params.extend([q, q, q, q, q])
        sql += " ORDER BY id DESC LIMIT ? OFFSET ?;"
        params.extend([int(limit), int(offset)])
        cur.execute(sql, params)
        rows = cur.fetchall()
    finally:
        conn.close()
    return rows


def list_pending_partners():
    # برای سازگاری با کدهای قبلی
    return list_partner_requests(status='pending', query=None, limit=200, offset=0)

def approve_partner(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        now = datetime.utcnow().isoformat(timespec='seconds')
        cur.execute(
            """UPDATE partners SET status='approved', approved_at=? WHERE tg_user_id=?;""",
            (now, tg_user_id),
        )
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    if changed > 0:
        _pay_pending_referral_rewards_for(tg_user_id)
    return changed > 0


def _pay_pending_referral_rewards_for(referrer_id: int) -> None:
    """بعد از تأیید همکاری، پاداش عضویت معرفی‌های قبلی این کاربر (از زمانی که هنوز
    همکار نبود، پس پاداش‌شون به‌عمد رد شده بود توسط pay_signup_referral_reward) رو
    الان که همکار تأییدشده، حساب می‌کنه — طبق درخواست صریح مالک پروژه («وقتی که
    درخواست همکاری داد و همکار شد بیاد تو چرخه و پاداش... براش محاسبه بشه»)."""
    try:
        conn = _get_connection()
        try:
            pending = conn.execute(
                "SELECT referred_id FROM referrals WHERE referrer_id=? AND rewarded=0;",
                (referrer_id,)
            ).fetchall()
        finally:
            conn.close()
        for row in pending:
            try:
                pay_signup_referral_reward(referrer_id, int(row[0]))
            except Exception:
                pass
    except Exception:
        pass

def reject_partner(tg_user_id: int):
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("UPDATE partners SET status='rejected' WHERE tg_user_id=?;", (tg_user_id,))
        conn.commit()
        changed = cur.rowcount
    finally:
        conn.close()
    return changed > 0

def is_partner_approved(tg_user_id: int) -> bool:
    conn = _get_connection()
    try:
        ok = conn.execute(
            "SELECT 1 FROM partners WHERE tg_user_id=? AND status='approved' LIMIT 1;",
            (tg_user_id,)
        ).fetchone() is not None
        return ok
    finally:
        conn.close()


def count_user_product_orders_today(user_id: int, product_id: int | None = None, buyer_type: str | None = None) -> int:
    """
    Count how many orders this user placed today (optionally per product).
    If orders table has buyer_type column, it will be respected.
    buyer_type example values typically: 'customer' / 'partner'

    ⚠️ رفع‌شده (ممیزی کامل پروژه، پاک‌سازی SQLite): این تابع قبلاً **دوبار** تعریف
    شده بود (نسخهٔ اول کاملاً مرده/سایه‌خورده بود، هیچ‌وقت اجرا نمی‌شد — حذف شد).
    نسخهٔ زنده هم با sqlite3.connect خام (مستقل از DB_DIALECT) و کوئری‌های
    کاملاً SQLite-only (`sqlite_master`, بدون _get_connection) کار می‌کرد —
    روی Postgres همیشه با خطا/دادهٔ فانتوم به except می‌افتاد و 0 برمی‌گردوند،
    یعنی محدودیت خرید روزانه (daily_limit_customer/partner) عملاً هیچ‌وقت
    اعمال نمی‌شد. حالا از _get_connection() استفاده می‌کنه — orders جدول
    هسته‌ایه (همیشه توسط init_db ساخته می‌شه)، پس چک وجود جدول هم حذف شد.
    """
    import datetime
    conn = _get_connection()
    try:
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(orders);").fetchall()}
        if "user_id" not in cols or "created_at" not in cols:
            return 0

        today = datetime.date.today().isoformat()  # YYYY-MM-DD

        q = "SELECT COUNT(1) AS c FROM orders WHERE user_id=? AND created_at LIKE ?"
        params = [user_id, today + "%"]

        if product_id is not None and "product_id" in cols:
            q += " AND product_id=?"
            params.append(product_id)

        if buyer_type and "buyer_type" in cols:
            q += " AND buyer_type=?"
            params.append(buyer_type)

        r = conn.execute(q, params).fetchone()
        return int(r["c"] if r else 0)
    except Exception:
        return 0
    finally:
        conn.close()

# ========= UI TEXTS =========

def get_ui_text(key: str) -> str | None:
    conn = _get_connection()
    cur = conn.cursor()
    cur.execute("SELECT value FROM ui_texts WHERE key=? LIMIT 1;", (key,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def set_ui_text(key: str, value: str) -> None:
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO ui_texts(key, value, updated_at) VALUES(?,?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
            (key, value, datetime.now().isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


def delete_ui_text(key: str) -> None:
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM ui_texts WHERE key=?;", (key,))
        conn.commit()
    finally:
        conn.close()


def list_ui_texts(prefix: str | None = None) -> list[tuple[str, str, str]]:
    conn = _get_connection()
    cur = conn.cursor()
    if prefix:
        cur.execute(
            "SELECT key, value, updated_at FROM ui_texts WHERE key LIKE ? ORDER BY key ASC;",
            (f"{prefix}%",),
        )
    else:
        cur.execute("SELECT key, value, updated_at FROM ui_texts ORDER BY key ASC;")
    rows = cur.fetchall() or []
    conn.close()
    return rows


# ========= CATEGORIES =========

def get_root_categories(active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM categories WHERE parent_id IS NULL {where} ORDER BY sort_order, name;"
        ).fetchall()
    finally:
        conn.close()


def get_subcategories(parent_id: int, active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM categories WHERE parent_id=? {where} ORDER BY sort_order, name;",
            (parent_id,)
        ).fetchall()
    finally:
        conn.close()


def get_category(cat_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories WHERE id=? LIMIT 1;", (cat_id,)).fetchone()
    finally:
        conn.close()


def get_category_by_slug(slug: str):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories WHERE slug=? LIMIT 1;", (slug,)).fetchone()
    finally:
        conn.close()


def get_category_products(cat_id: int, active_only: bool = True) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "AND is_active=1" if active_only else ""
        return conn.execute(
            f"SELECT * FROM products WHERE category_id=? {where} ORDER BY id;",
            (cat_id,)
        ).fetchall()
    finally:
        conn.close()


_CAT_BTN_CACHE = {"t": 0.0, "map": {}}

def _cat_btn_map() -> dict:
    """نقشه متن دکمه ← دسته ریشه — کش ۲۰ ثانیه (این تابع در فیلتر هر پیام صدا می‌خورد)."""
    import time as _t
    now = _t.time()
    if now - _CAT_BTN_CACHE["t"] < 20:
        return _CAT_BTN_CACHE["map"]
    m = {}
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        for cat in conn.execute(
            "SELECT * FROM categories WHERE parent_id IS NULL AND is_active=1;"
        ).fetchall():
            emoji = (cat["emoji"] or "").strip()
            btn = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            m[btn] = dict(cat)
    except Exception:
        pass
    finally:
        conn.close()
    _CAT_BTN_CACHE["t"] = now
    _CAT_BTN_CACHE["map"] = m
    return m


def cat_btn_cache_clear():
    _CAT_BTN_CACHE["t"] = 0.0


def get_category_by_button_text(text: str):
    """یافتن دسته ریشه بر اساس متن دکمه Reply Keyboard — از کش."""
    return _cat_btn_map().get((text or "").strip())


def _legacy_get_category_by_button_text(text: str):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cats = conn.execute(
            "SELECT * FROM categories WHERE parent_id IS NULL AND is_active=1;"
        ).fetchall()
        text = (text or "").strip()
        for cat in cats:
            emoji = (cat["emoji"] or "").strip()
            btn = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            if btn == text:
                return cat
        return None
    finally:
        conn.close()


def create_category(name: str, parent_id: int | None, emoji: str = "", sort_order: int = 0) -> int:
    slug = "".join(c if c.isalnum() else "_" for c in name).lower()[:40]
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            "INSERT INTO categories (name, slug, parent_id, emoji, sort_order, is_active, created_at) VALUES (?,?,?,?,?,1,?);",
            (name.strip(), slug, parent_id, emoji.strip(), sort_order, now)
        )
        cat_id = cur.lastrowid
        conn.commit()
        return cat_id
    finally:
        conn.close()


def update_category(cat_id: int, name: str, emoji: str, sort_order: int, is_active: int) -> None:
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE categories SET name=?, emoji=?, sort_order=?, is_active=? WHERE id=?;",
            (name.strip(), emoji.strip(), sort_order, is_active, cat_id)
        )
        conn.commit()
    finally:
        conn.close()


def delete_category(cat_id: int) -> None:
    """حذف دسته و همه زیردستهها و محصولات مرتبط"""
    conn = _get_connection()
    try:
        conn.execute("PRAGMA foreign_keys=ON;")
        # پیدا کردن همه IDs به صورت recursive
        all_ids = _collect_category_ids(conn, cat_id)
        for cid in all_ids:
            conn.execute("DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category_id=?);", (cid,))
            conn.execute("DELETE FROM products WHERE category_id=?;", (cid,))
        conn.execute("DELETE FROM categories WHERE id IN ({});".format(",".join("?" * len(all_ids))), all_ids)
        conn.commit()
    finally:
        conn.close()


def _collect_category_ids(conn, cat_id: int) -> list:
    ids = [cat_id]
    children = conn.execute("SELECT id FROM categories WHERE parent_id=?;", (cat_id,)).fetchall()
    for child in children:
        ids.extend(_collect_category_ids(conn, child[0]))
    return ids


def get_category_path(cat_id: int) -> list:
    """مسیر کامل از ریشه تا دسته (breadcrumb)"""
    path = []
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        cid = cat_id
        while cid:
            cat = conn.execute("SELECT * FROM categories WHERE id=? LIMIT 1;", (cid,)).fetchone()
            if not cat:
                break
            path.insert(0, cat)
            cid = cat["parent_id"]
    finally:
        conn.close()
    return path


def toggle_category(cat_id: int) -> None:
    conn = _get_connection()
    try:
        conn.execute("UPDATE categories SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (cat_id,))
        conn.commit()
    finally:
        conn.close()


def get_all_categories_flat() -> list:
    """همه دستهها برای نمایش در select box پنل"""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM categories ORDER BY parent_id NULLS FIRST, sort_order, name;").fetchall()
    finally:
        conn.close()


def add_product_with_category(category_id: int, title: str, price: int, partner_price: int | None,
                               limit_c: int, limit_p: int, description: str) -> int:
    slug = "".join(c if c.isalnum() else "_" for c in title).lower()[:40] or "product"
    conn = _get_connection()
    try:
        cat = conn.execute("SELECT slug FROM categories WHERE id=? LIMIT 1;", (category_id,)).fetchone()
        cat_slug = cat[0] if cat else str(category_id)
        cur = conn.execute(
            """INSERT INTO products (category, category_id, product_key, title, price, partner_price,
               daily_limit_customer, daily_limit_partner, description, is_active)
               VALUES (?,?,?,?,?,?,?,?,?,1);""",
            (cat_slug, category_id, slug, title.strip(), price,
             partner_price if partner_price and partner_price > 0 else None,
             limit_c, limit_p, description.strip())
        )
        pid = cur.lastrowid
        conn.commit()
        return pid
    finally:
        conn.close()


# ========= USERS (Broadcast) =========

def upsert_user(user_id: int, username: str | None = None, full_name: str | None = None) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            """INSERT INTO users (user_id, username, full_name, first_seen, last_seen)
               VALUES (?,?,?,?,?)
               ON CONFLICT(user_id) DO UPDATE SET
                 username=excluded.username,
                 full_name=excluded.full_name,
                 last_seen=excluded.last_seen;""",
            (user_id, username, full_name, now, now)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_broadcast_users(target: str = "all", product_id: int | None = None,
                        category_id: int | None = None) -> list[int]:
    """بازگرداندن لیست user_id برای broadcast بر اساس target"""
    conn = _get_connection()
    try:
        if target == "all":
            rows = conn.execute("SELECT user_id FROM users ORDER BY user_id;").fetchall()
        elif target == "buyers":
            rows = conn.execute("SELECT DISTINCT user_id FROM orders ORDER BY user_id;").fetchall()
        elif target == "non_buyers":
            rows = conn.execute("""
                SELECT u.user_id FROM users u
                LEFT JOIN orders o ON u.user_id = o.user_id
                WHERE o.user_id IS NULL ORDER BY u.user_id;
            """).fetchall()
        elif target == "product" and product_id:
            rows = conn.execute(
                "SELECT DISTINCT user_id FROM orders WHERE product_id=? ORDER BY user_id;",
                (str(product_id),)
            ).fetchall()
        elif target == "category" and category_id:
            rows = conn.execute("""
                SELECT DISTINCT o.user_id FROM orders o
                JOIN products p ON CAST(o.product_id AS INTEGER) = p.id
                WHERE p.category_id=? ORDER BY o.user_id;
            """, (category_id,)).fetchall()
        else:
            rows = []
        return [int(r[0]) for r in rows]
    finally:
        conn.close()


def get_users_stats() -> dict:
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        buyers = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders;").fetchone()[0]
        return {"total": total, "buyers": buyers, "non_buyers": total - buyers}
    finally:
        conn.close()


# ========= TICKET MESSAGES =========

def save_ticket_message(ticket_id: int, sender: str, text: str | None,
                         media_type: str | None = None) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, media_type, created_at) VALUES (?,?,?,?,?);",
            (ticket_id, sender, text, media_type, now)
        )
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def get_ticket_messages(ticket_id: int) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC;",
            (ticket_id,)
        ).fetchall()
    finally:
        conn.close()


def get_all_tickets(status: str | None = None, limit: int = 100) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE t.status=?" if status else ""
        params = (status, limit) if status else (limit,)
        return conn.execute(f"""
            SELECT t.*, p.title as product_title,
                   (SELECT COUNT(*) FROM ticket_messages tm WHERE tm.ticket_id=t.id) as msg_count
            FROM tickets t
            LEFT JOIN products p ON t.product_id=p.id
            {where} ORDER BY t.id DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


def get_ticket_by_id(ticket_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT t.*, p.title as product_title
            FROM tickets t LEFT JOIN products p ON t.product_id=p.id
            WHERE t.id=? LIMIT 1;
        """, (ticket_id,)).fetchone()
    finally:
        conn.close()


def update_ticket_status(ticket_id: int, status: str) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        if status == "closed":
            conn.execute(
                "UPDATE tickets SET status=?, closed_at=?, closed_by='admin' WHERE id=?;",
                (status, now, ticket_id)
            )
        else:
            conn.execute("UPDATE tickets SET status=? WHERE id=?;", (status, ticket_id))
        conn.commit()
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# TICKET SYSTEM v2
# ═══════════════════════════════════════════════════════════════════════════

TICKET_MAX_USER_MSGS = 3  # max consecutive user messages before admin must reply


def ticket_ensure_schema() -> None:
    """Create v2 ticket tables (migration-safe)."""
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL DEFAULT 'support',
                user_id INTEGER NOT NULL,
                product_id INTEGER DEFAULT 0,
                order_id INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'waiting_admin',
                user_msg_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                closed_at TEXT
            );
        """)
        # migration: add columns to old schema
        for col, typedef in [
            ("type",           "TEXT NOT NULL DEFAULT 'support'"),
            ("order_id",       "INTEGER DEFAULT 0"),
            ("user_msg_count", "INTEGER DEFAULT 0"),
            ("updated_at",     "TEXT"),
            ("feed_id",        "INTEGER DEFAULT NULL"),
            ("feed_data",      "TEXT DEFAULT NULL"),
            ("setup_status",   "TEXT DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} {typedef};")
            except Exception:
                pass

        conn.execute("""
            CREATE TABLE IF NOT EXISTS ticket_messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                sender TEXT NOT NULL,
                text TEXT,
                media_type TEXT,
                media_file_id TEXT,
                source TEXT NOT NULL DEFAULT 'telegram',
                created_at TEXT NOT NULL
            );
        """)
        # migration: add missing columns
        for col, typedef in [
            ("source",        "TEXT NOT NULL DEFAULT 'telegram'"),
            ("media_file_id", "TEXT"),
            ("file_name",     "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE ticket_messages ADD COLUMN {col} {typedef};")
            except Exception:
                pass

        conn.commit()
    finally:
        conn.close()
    # ایندکس‌های tickets/ticket_messages پس از ساخت‌شان (همون الگوی ensure_growth_schema)
    try:
        ensure_indexes()
    except Exception:
        pass


def ticket_create(user_id: int, type_: str = "support",
                  product_id: int = 0, order_id: int = 0,
                  feed_id: int = None, feed_data: str = None,
                  setup_status: str = None) -> int:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        initial_status = "waiting_info" if type_ == "product_setup" else "waiting_admin"
        if setup_status:
            initial_status = setup_status
        cur = conn.execute(
            """INSERT INTO tickets (type, user_id, product_id, order_id,
               status, setup_status, feed_id, feed_data, user_msg_count, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,0,?,?);""",
            (type_, user_id, product_id, order_id,
             initial_status, setup_status or initial_status,
             feed_id, feed_data, now, now)
        )
        ticket_id = cur.lastrowid
        conn.commit()
        return int(ticket_id)
    finally:
        conn.close()


def ticket_get(ticket_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM tickets WHERE id=? LIMIT 1;", (ticket_id,)).fetchone()
    finally:
        conn.close()


def ticket_get_open_support(user_id: int):
    """آخرین تیکت پشتیبانی باز کاربر."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? AND type='support' AND status!='closed' "
            "ORDER BY id DESC LIMIT 1;",
            (user_id,)
        ).fetchone()
    finally:
        conn.close()


def ticket_get_open_by_type(user_id: int, type_: str):
    """آخرین تیکت باز کاربر با نوع مشخص (مثلاً support یا partner_support)."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? AND type=? AND status!='closed' "
            "ORDER BY id DESC LIMIT 1;",
            (user_id, type_)
        ).fetchone()
    finally:
        conn.close()


def ticket_get_open_product(user_id: int, order_id: int):
    """تیکت محصول باز برای یک سفارش خاص."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM tickets WHERE user_id=? AND order_id=? AND type='product' "
            "AND status!='closed' LIMIT 1;",
            (user_id, order_id)
        ).fetchone()
    finally:
        conn.close()


def ticket_add_message(ticket_id: int, sender: str, text: str | None,
                        media_type: str | None = None, source: str = "telegram",
                        media_file_id: str | None = None, file_name: str | None = None) -> int:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        cur = conn.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, media_type, media_file_id, file_name, source, created_at) "
            "VALUES (?,?,?,?,?,?,?,?);",
            (ticket_id, sender, text, media_type, media_file_id, file_name, source, now)
        )
        msg_id = cur.lastrowid
        conn.execute("UPDATE tickets SET updated_at=? WHERE id=?;", (now, ticket_id))
        conn.commit()
        return int(msg_id)
    finally:
        conn.close()


def ticket_user_sent(ticket_id: int) -> int:
    """کاربر پیام فرستاد — وضعیت و counter رو آپدیت کن. returns new count."""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='waiting_admin', "
            "user_msg_count = user_msg_count + 1, updated_at=? WHERE id=?;",
            (now, ticket_id)
        )
        conn.commit()
        row = conn.execute("SELECT user_msg_count FROM tickets WHERE id=?;", (ticket_id,)).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def ticket_admin_replied(ticket_id: int) -> None:
    """ادمین پاسخ داد — counter ریست، وضعیت → waiting_user."""
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='waiting_user', user_msg_count=0, updated_at=? WHERE id=?;",
            (now, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()


def ticket_close(ticket_id: int) -> None:
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "UPDATE tickets SET status='closed', closed_at=?, updated_at=? WHERE id=?;",
            (now, now, ticket_id)
        )
        conn.commit()
    finally:
        conn.close()


def ticket_get_messages(ticket_id: int) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC;", (ticket_id,)
        ).fetchall()
    finally:
        conn.close()


def ticket_count_waiting() -> int:
    """تعداد تیکتهایی که ادمین باید پاسخ بده (badge count)."""
    conn = _get_connection()
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status='waiting_admin';"
        ).fetchone()[0])
    finally:
        conn.close()


def ticket_get_all(status: str | None = None, type_: str | None = None,
                   limit: int = 100) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        wheres, params = [], []
        if status:
            wheres.append("t.status=?"); params.append(status)
        if type_:
            wheres.append("t.type=?"); params.append(type_)
        w = "WHERE " + " AND ".join(wheres) if wheres else ""
        params.append(limit)
        return conn.execute(f"""
            SELECT t.*,
                   (SELECT COUNT(*) FROM ticket_messages m WHERE m.ticket_id=t.id) AS msg_count,
                   (SELECT text FROM ticket_messages m WHERE m.ticket_id=t.id ORDER BY m.id DESC LIMIT 1) AS last_msg
            FROM tickets t {w}
            ORDER BY CASE t.status WHEN 'waiting_admin' THEN 0 WHEN 'waiting_user' THEN 1 ELSE 2 END,
                     t.updated_at DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


def ticket_toggle_product_chat(product_id: int) -> bool:
    """Toggle chat_enabled for a product. Returns new state."""
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE products SET chat_enabled=CASE WHEN chat_enabled=1 THEN 0 ELSE 1 END WHERE id=?;",
            (product_id,)
        )
        conn.commit()
        row = conn.execute("SELECT chat_enabled FROM products WHERE id=?;", (product_id,)).fetchone()
        return bool(row[0] if row else 0)
    finally:
        conn.close()


# ═══════════════════════════════════════════════════════════════════════════
# ORDER MANAGEMENT — برگشت محصول (مورد ۴)
# ═══════════════════════════════════════════════════════════════════════════

def order_get(order_id: int):
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
    finally:
        conn.close()


def order_set_feed_id(order_id: int, feed_id: int) -> None:
    """ذخیره feed_id مربوط به سفارش (برای برگشت)."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE orders SET feed_id=? WHERE id=?;", (int(feed_id), int(order_id)))
        conn.commit()
    finally:
        conn.close()


def order_mark_returned_advanced(
    order_id: int,
    product_action: str = "restore",   # 'restore' | 'delete'
    wallet_action: str = "none",        # 'none' | 'full' | 'custom_add' | 'custom_deduct'
    custom_amount: int = 0,
) -> dict:
    """
    برگشت پیشرفته:
    - product_action: restore (به موجودی برگرد) یا delete (حذف دائم)
    - wallet_action: none | full | custom_add | custom_deduct
    """
    from datetime import datetime as _dt
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        order = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
        if not order:
            return {"ok": False, "error": "سفارش یافت نشد"}
        if (order["status"] or "active") == "returned":
            return {"ok": False, "error": "این سفارش قبلاً برگشت خورده"}

        price = int(order["price"] or 0)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY, order_id INTEGER,
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL
            );
        """)

        # feed_id — اولویت با reverse lookup مستقیم روی product_feed.order_id (بخش ۴۰
        # CLAUDE.md). این ستون همیشه توسط claim_next_feed_item ست می‌شه، برخلاف
        # orders.feed_id/delivery_messages که فقط بعضی از سه مسیر تحویل (بات/درگاه/
        # مینی‌اپ) واقعاً پرش می‌کردن — قبلاً همین باعث می‌شد «بازگشت به موجودی» برای
        # سفارش‌های تحویل‌شده از مسیر خرید مستقیم بات (finalize_product_order) کاملاً
        # بی‌اثر باشه، بدون هیچ خطایی.
        fr = conn.execute("SELECT id FROM product_feed WHERE order_id=? LIMIT 1;", (order_id,)).fetchone()
        feed_id = fr["id"] if fr else None
        if not feed_id:
            try:
                feed_id = order["feed_id"]
            except Exception:
                feed_id = None
        if not feed_id:
            dm = conn.execute("SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;", (order_id,)).fetchone()
            if dm:
                feed_id = dm["feed_id"]

        # پیام تحویل
        chat_id = message_id = None
        if feed_id:
            dmsg = conn.execute("SELECT chat_id,message_id FROM delivery_messages WHERE feed_id=? LIMIT 1;", (feed_id,)).fetchone()
            if dmsg:
                chat_id, message_id = dmsg["chat_id"], dmsg["message_id"]

        # تکلیف محصول فید
        if feed_id:
            if product_action == "restore":
                conn.execute("UPDATE product_feed SET delivered=0, order_id=NULL, delivered_at=NULL WHERE id=?;", (int(feed_id),))
            else:  # delete
                conn.execute("DELETE FROM product_feed WHERE id=?;", (int(feed_id),))

        # تکلیف کیفپول
        wallet_delta = 0
        if wallet_action == "full":
            wallet_delta = price
        elif wallet_action == "custom_add":
            wallet_delta = abs(custom_amount)
        elif wallet_action == "custom_deduct":
            wallet_delta = -abs(custom_amount)

        if wallet_delta != 0:
            user_id = order["user_id"]
            existing = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
            if existing:
                new_bal = max(0, int(existing["balance"]) + wallet_delta)
                conn.execute("UPDATE wallets SET balance=?, updated_at=datetime('now') WHERE user_id=?;", (new_bal, user_id))
            else:
                new_bal = max(0, wallet_delta)
                conn.execute("INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,datetime('now'));", (user_id, new_bal))

        now = _dt.utcnow().isoformat()
        conn.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;", (now, order_id))

        # بستن تیکت(های) راه‌اندازی محصول وابسته به این سفارش — طبق درخواست صریح
        # مالک پروژه («وقتی محصول عودت میخوره باید از صفحه چت هم پاک بشه انگار
        # اصلا نخریده»). محتوای قدیمی تیکت (مثلاً اطلاعات اکانتی که قبلاً تحویل
        # داده شده) دست‌نخورده در دیتابیس می‌مونه (برای ادمین/تاریخچه)، ولی بستن
        # تیکت یعنی کاربر دیگه نمی‌تونه از طریق دکمهٔ «💬 ادامه گفتگو»/«ارسال
        # اطلاعات» قدیمی وارد اون مکالمه بشه — همون مسیر استانداردی که برای هر
        # تیکت بستهٔ دیگه از قبل در _ticket_v2_handle_user_message رعایت می‌شه.
        conn.execute(
            "UPDATE tickets SET status='closed', closed_at=?, updated_at=? "
            "WHERE order_id=? AND status != 'closed';",
            (now, now, order_id)
        )
        conn.commit()

        return {
            "ok": True, "feed_id": feed_id, "product_id": order["product_id"],
            "chat_id": chat_id, "message_id": message_id,
            "user_id": order["user_id"], "title": order["title"], "price": price,
            "wallet_delta": wallet_delta,
        }
    except Exception as ex:
        conn.rollback()
        return {"ok": False, "error": str(ex)[:100]}
    finally:
        conn.close()


def exchange_order(
    old_order_id: int,
    new_product_id: int,
    old_product_action: str = "restore",   # 'restore' | 'delete'
    wallet_delta: int = 0,                 # مثبت = بازگشت به کاربر (قیمت جدید ارزون‌تر)، منفی = کسر (قیمت جدید گرون‌تر)
) -> dict:
    """
    تعویض کالا — سفارش قدیم رو با همون مکانیزم برگشت موجود می‌بنده (status='returned'،
    یعنی همهٔ جاهایی که از قبل «returned» رو از دید کاربر/گزارش مالی مخفی می‌کنن،
    بدون هیچ تغییری درست کار می‌کنن)، یک آیتم تازه از محصول مقصد claim می‌کنه، یک
    سفارش کاملاً جدید براش می‌سازه (خودش با status='active' عادی در فروش/حسابداری
    لحاظ می‌شه)، و دو سفارش رو با exchange_pair_id به هم لینک می‌کنه. اختلاف قیمت
    (wallet_delta) مستقیم روی کیف‌پول اعمال می‌شه — دقیقاً همون الگوی مقداردهی مستقیم
    order_mark_returned_advanced (نه subtract_wallet_balance، چون این یه override
    دستی ادمینه، نه خرید خودکار کاربر).
    """
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        old = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (old_order_id,)).fetchone()
        if not old:
            return {"ok": False, "error": "سفارش یافت نشد"}
        if (old["status"] or "active") != "active":
            return {"ok": False, "error": "این سفارش قبلاً برگشت/تعویض شده"}

        new_product = conn.execute("SELECT * FROM products WHERE id=?;", (new_product_id,)).fetchone()
        if not new_product:
            return {"ok": False, "error": "محصول مقصد یافت نشد"}

        # claim اتمیک یه آیتم تازه از محصول مقصد — قبل از هر تغییری روی سفارش قدیم،
        # چون اگه موجودی نبود باید همون‌جا با خطای واضح متوقف بشیم (سفارش قدیم دست‌نخورده بمونه)
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        cur.execute(
            f"SELECT id, data FROM product_feed WHERE product_id=? AND delivered=0 ORDER BY id ASC LIMIT 1 {_row_lock_suffix()};",
            (new_product_id,)
        )
        feed_row = cur.fetchone()
        if not feed_row:
            conn.rollback()
            return {"ok": False, "error": "موجودی محصول مقصد خالی است"}
        new_feed_id, new_feed_data = feed_row["id"], feed_row["data"]

        old_user_id = old["user_id"]
        old_price = int(old["price"] or 0)
        new_price = int(new_product["price"] or 0)

        # feed قدیم — دقیقاً همون منطق order_mark_returned_advanced (بخش ۴۰ CLAUDE.md):
        # اولویت با reverse lookup مستقیم روی product_feed.order_id
        cur.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY, order_id INTEGER,
                chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL
            );
        """)
        ofr = cur.execute("SELECT id FROM product_feed WHERE order_id=? LIMIT 1;", (old_order_id,)).fetchone()
        old_feed_id = ofr["id"] if ofr else None
        if not old_feed_id:
            try:
                old_feed_id = old["feed_id"]
            except Exception:
                old_feed_id = None
        if not old_feed_id:
            dm = cur.execute("SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;", (old_order_id,)).fetchone()
            if dm:
                old_feed_id = dm["feed_id"]
        old_chat_id = old_message_id = None
        if old_feed_id:
            dmsg = cur.execute("SELECT chat_id,message_id FROM delivery_messages WHERE feed_id=? LIMIT 1;", (old_feed_id,)).fetchone()
            if dmsg:
                old_chat_id, old_message_id = dmsg["chat_id"], dmsg["message_id"]
            if old_product_action == "restore":
                cur.execute("UPDATE product_feed SET delivered=0, order_id=NULL, delivered_at=NULL WHERE id=?;", (int(old_feed_id),))
            else:
                cur.execute("DELETE FROM product_feed WHERE id=?;", (int(old_feed_id),))

        now = datetime.utcnow().isoformat()
        cur.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;", (now, old_order_id))

        # بستن تیکت راه‌اندازی محصولِ سفارش قدیم — دقیقاً همون منطق order_mark_returned_advanced
        cur.execute(
            "UPDATE tickets SET status='closed', closed_at=?, updated_at=? "
            "WHERE order_id=? AND status != 'closed';",
            (now, now, old_order_id)
        )

        # سفارش جدید
        cur.execute(
            "INSERT INTO orders (user_id, category, product_id, title, price, created_at, buyer_type, status, feed_id) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, 'active', ?);",
            (old_user_id, new_product["category"], str(new_product_id),
             new_product["title"], new_price, now, old["buyer_type"], new_feed_id)
        )
        new_order_id = cur.lastrowid
        cur.execute("UPDATE product_feed SET delivered=1, order_id=?, delivered_at=? WHERE id=?;",
                    (new_order_id, now, new_feed_id))

        # لینک دوطرفه
        cur.execute("UPDATE orders SET exchange_pair_id=? WHERE id=?;", (new_order_id, old_order_id))
        cur.execute("UPDATE orders SET exchange_pair_id=? WHERE id=?;", (old_order_id, new_order_id))

        # تسویهٔ اختلاف قیمت روی کیف‌پول
        if wallet_delta != 0:
            existing = cur.execute("SELECT balance FROM wallets WHERE user_id=?;", (old_user_id,)).fetchone()
            if existing:
                new_bal = max(0, int(existing["balance"]) + wallet_delta)
                cur.execute("UPDATE wallets SET balance=?, updated_at=datetime('now') WHERE user_id=?;", (new_bal, old_user_id))
            else:
                new_bal = max(0, wallet_delta)
                cur.execute("INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,datetime('now'));", (old_user_id, new_bal))

        conn.commit()
        return {
            "ok": True,
            "old_order_id": old_order_id, "new_order_id": new_order_id,
            "old_chat_id": old_chat_id, "old_message_id": old_message_id,
            "user_id": old_user_id, "old_title": old["title"], "new_title": new_product["title"],
            "old_price": old_price, "new_price": new_price, "wallet_delta": wallet_delta,
            "new_feed_data": new_feed_data,
        }
    except Exception as ex:
        conn.rollback()
        return {"ok": False, "error": str(ex)[:150]}
    finally:
        conn.close()


def get_exchange_pair(order_id: int) -> dict | None:
    """اگه این سفارش طرف یه تعویض بود، جزئیات سفارش جفتش رو برمی‌گردونه."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT o2.* FROM orders o1 JOIN orders o2 ON o2.id = o1.exchange_pair_id
            WHERE o1.id=? AND o1.exchange_pair_id IS NOT NULL;
        """, (order_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def list_exchanges(limit: int = 100) -> list:
    """گزارش تعویض‌ها — سفارش‌های قدیمِ برگشتی که واقعاً یه سفارش جدید جایگزینشون شده
    (exchange_pair_id ست شده)، برای صفحهٔ گزارش‌گیری پنل."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("""
            SELECT o1.id AS old_order_id, o1.title AS old_title, o1.price AS old_price,
                   o1.returned_at AS exchanged_at, o1.user_id,
                   o2.id AS new_order_id, o2.title AS new_title, o2.price AS new_price
            FROM orders o1
            JOIN orders o2 ON o2.id = o1.exchange_pair_id
            WHERE o1.status='returned' AND o1.exchange_pair_id IS NOT NULL AND o1.id < o2.id
            ORDER BY o1.id DESC LIMIT ?;
        """, (limit,)).fetchall()]
    finally:
        conn.close()


def order_mark_returned(order_id: int) -> dict:
    """Backward compat — restore to inventory, no wallet change."""
    return order_mark_returned_advanced(order_id, product_action="restore", wallet_action="none")
    """
    برگشت محصول:
      - وضعیت سفارش → 'returned'
      - اگر feed_id موجود باشد، آیتم فید به delivered=0 برمیگردد (موجودی +1)
    return: {ok, feed_id, product_id, chat_id, message_id, user_id, title}
    """
    from datetime import datetime as _dt
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        order = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (order_id,)).fetchone()
        if not order:
            return {"ok": False, "error": "سفارش یافت نشد"}
        if (order["status"] or "active") == "returned":
            return {"ok": False, "error": "این سفارش قبلاً برگشت خورده"}

        feed_id = order["feed_id"] if "feed_id" in order.keys() else None

        # اطمینان از وجود جدول delivery_messages
        conn.execute("""
            CREATE TABLE IF NOT EXISTS delivery_messages (
                feed_id INTEGER PRIMARY KEY,
                order_id INTEGER,
                chat_id INTEGER NOT NULL,
                message_id INTEGER NOT NULL,
                created_at TEXT NOT NULL
            );
        """)

        # اگر feed_id در orders نبود، از delivery_messages بگیر
        if not feed_id:
            dm = conn.execute(
                "SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;", (order_id,)
            ).fetchone()
            if dm:
                feed_id = dm["feed_id"]

        # پیام تحویل در چت کاربر
        chat_id = message_id = None
        if feed_id:
            dmsg = conn.execute(
                "SELECT chat_id, message_id FROM delivery_messages WHERE feed_id=? LIMIT 1;", (feed_id,)
            ).fetchone()
            if dmsg:
                chat_id = dmsg["chat_id"]
                message_id = dmsg["message_id"]

        # بازگرداندن موجودی: feed item → delivered=0
        if feed_id:
            conn.execute("UPDATE product_feed SET delivered=0 WHERE id=?;", (int(feed_id),))

        # علامتگذاری سفارش بهعنوان برگشتی
        now = _dt.utcnow().isoformat()
        conn.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;", (now, order_id))
        conn.commit()

        return {
            "ok": True,
            "feed_id": feed_id,
            "product_id": order["product_id"],
            "chat_id": chat_id,
            "message_id": message_id,
            "user_id": order["user_id"],
            "title": order["title"],
        }
    finally:
        conn.close()


def order_update(order_id: int, title: str = None, price: int = None) -> bool:
    """ویرایش عنوان/قیمت سفارش."""
    conn = _get_connection()
    try:
        sets, params = [], []
        if title is not None:
            sets.append("title=?"); params.append(title)
        if price is not None:
            sets.append("price=?"); params.append(int(price))
        if not sets:
            return False
        params.append(int(order_id))
        conn.execute(f"UPDATE orders SET {', '.join(sets)} WHERE id=?;", params)
        conn.commit()
        return True
    finally:
        conn.close()


def order_stats_returned() -> dict:
    """آمار سفارشهای برگشتی."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM orders;").fetchone()[0]
        returned = conn.execute("SELECT COUNT(*) FROM orders WHERE status='returned';").fetchone()[0]
        returned_sum = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='returned';"
        ).fetchone()[0]
        return {"total": int(total), "returned": int(returned), "returned_sum": int(returned_sum)}
    finally:
        conn.close()


def feed_returned_count(product_id: int) -> int:
    """تعداد آیتمهای برگشتی یک محصول (سفارشهای returned با این product_id)."""
    conn = _get_connection()
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM orders WHERE product_id=? AND status='returned';",
            (str(product_id),)
        ).fetchone()[0])
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── کد تخفیف ───────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_discount_table():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_codes (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                code            TEXT    UNIQUE NOT NULL COLLATE NOCASE,
                type            TEXT    NOT NULL DEFAULT 'percent',  -- 'percent' | 'fixed' | 'wallet'
                value           INTEGER NOT NULL DEFAULT 0,
                max_value       INTEGER DEFAULT 0,    -- سقف تخفیف (برای درصدی) — 0=نامحدود
                min_amount      INTEGER DEFAULT 0,    -- حداقل مبلغ سفارش
                max_uses        INTEGER DEFAULT 0,    -- 0=نامحدود
                max_uses_per_user INTEGER DEFAULT 0,  -- 0=نامحدود
                used_count      INTEGER DEFAULT 0,
                product_id      INTEGER DEFAULT NULL, -- NULL=همه محصولات
                category_id     INTEGER DEFAULT NULL, -- NULL=همه دستهها
                first_buy_only  INTEGER DEFAULT 0,    -- فقط اولین خرید
                vip_only        INTEGER DEFAULT 0,    -- فقط کاربران VIP
                starts_at       TEXT    DEFAULT NULL,
                expires_at      TEXT    DEFAULT NULL,
                is_active       INTEGER DEFAULT 1,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                description     TEXT    DEFAULT '',
                owner_user_id   INTEGER DEFAULT NULL, -- NULL=کد عمومی، پرشده=کد شخصیِ فقط همون کاربر
                source          TEXT    DEFAULT '',    -- 'winback'|'wheel'|'referral'|... (منبع صدور)
                source_ref_id   INTEGER DEFAULT NULL   -- شناسهٔ رکورد منبع (مثلاً wheel_spins.id)
            );
        """)
        # migration: ستونهایی که در نسخههای بعدی به جدول اضافه شدند
        for col, default in [
            ("max_value",         "INTEGER DEFAULT 0"),
            ("min_amount",        "INTEGER DEFAULT 0"),
            ("max_uses",          "INTEGER DEFAULT 0"),
            ("max_uses_per_user", "INTEGER DEFAULT 0"),
            ("used_count",        "INTEGER DEFAULT 0"),
            ("product_id",        "INTEGER DEFAULT NULL"),
            ("category_id",       "INTEGER DEFAULT NULL"),
            ("first_buy_only",    "INTEGER DEFAULT 0"),
            ("vip_only",          "INTEGER DEFAULT 0"),
            ("starts_at",         "TEXT DEFAULT NULL"),
            ("expires_at",        "TEXT DEFAULT NULL"),
            ("is_active",         "INTEGER DEFAULT 1"),
            ("description",       "TEXT DEFAULT ''"),
            ("owner_user_id",     "INTEGER DEFAULT NULL"),
            ("source",            "TEXT DEFAULT ''"),
            ("source_ref_id",     "INTEGER DEFAULT NULL"),
        ]:
            try:
                conn.execute(f"ALTER TABLE discount_codes ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
        conn.execute("""
            CREATE TABLE IF NOT EXISTS discount_usage (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                code_id     INTEGER NOT NULL,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER,
                used_at     TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(code_id) REFERENCES discount_codes(id)
            );
        """)
        # ─── مهاجرت: افزودن ستون‌های جدید به جدول‌های قدیمی ───────────────
        try:
            existing = {r[1] for r in conn.execute("PRAGMA table_info(discount_codes);").fetchall()}
            for col, decl in [
                ("max_value",         "INTEGER DEFAULT 0"),
                ("min_amount",        "INTEGER DEFAULT 0"),
                ("max_uses",          "INTEGER DEFAULT 0"),
                ("max_uses_per_user", "INTEGER DEFAULT 0"),
                ("used_count",        "INTEGER DEFAULT 0"),
                ("product_id",        "INTEGER DEFAULT NULL"),
                ("category_id",       "INTEGER DEFAULT NULL"),
                ("first_buy_only",    "INTEGER DEFAULT 0"),
                ("vip_only",          "INTEGER DEFAULT 0"),
                ("starts_at",         "TEXT DEFAULT NULL"),
                ("expires_at",        "TEXT DEFAULT NULL"),
                ("is_active",         "INTEGER DEFAULT 1"),
                ("description",       "TEXT DEFAULT ''"),
                ("owner_user_id",     "INTEGER DEFAULT NULL"),
                ("source",            "TEXT DEFAULT ''"),
                ("source_ref_id",     "INTEGER DEFAULT NULL"),
            ]:
                if col not in existing:
                    conn.execute(f"ALTER TABLE discount_codes ADD COLUMN {col} {decl};")
        except Exception:
            pass
        conn.commit()
        try:
            conn.execute("CREATE INDEX IF NOT EXISTS idx_discount_codes_owner ON discount_codes(owner_user_id);")
            conn.commit()
        except Exception:
            pass
    finally:
        conn.close()


def validate_discount(code: str, product_id: int = None, category_id: int = None,
                      amount: int = 0, user_id: int = None) -> dict:
    """اعتبارسنجی جامع کد تخفیف."""
    ensure_discount_table()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    # ⚠️ رفع‌شده (کشف‌شده حین تست مستقیم گردونهٔ شانس روی Postgres واقعی): starts_at/
    # expires_at با datetime('now','localtime') ذخیره می‌شن — فرمت "YYYY-MM-DD HH:MM:SS"
    # (جداکنندهٔ فاصله). قبلاً این‌جا با datetime.utcnow().isoformat() ("...THH:MM:SS.ffffff"،
    # جداکنندهٔ T + میکروثانیه) مقایسه می‌شد؛ چون در مقایسهٔ لغوی رشته ' '(0x20) < 'T'(0x54)
    # همیشه برقراره، هر کدی که انقضاش *همون روز* باشه (دقیقاً سناریوی جوایز گردونه با
    # اعتبار ۱ تا ۲۴ ساعته) همیشه اشتباهاً «منقضی‌شده» تشخیص داده می‌شد — یه باگ واقعاً
    # موجود که فقط با تاریخ فردا/بعد قابل مشاهده نبود (تفاوت رقم روز جبرانش می‌کرد).
    now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
    try:
        # ⚠️ COLLATE NOCASE خاص SQLite است — با LOWER(code)=LOWER(?) جایگزین شد که
        # روی هر دو دیالوگ case-insensitive کار می‌کنه (بخش پاک‌سازی SQLite سند)
        row = conn.execute(
            "SELECT * FROM discount_codes WHERE LOWER(code)=LOWER(?) AND is_active=1 LIMIT 1;",
            (code.strip(),)
        ).fetchone()
        if not row:
            return {"valid": False, "error": "کد تخفیف یافت نشد یا غیرفعال است"}
        if row["max_uses"] > 0 and row["used_count"] >= row["max_uses"]:
            return {"valid": False, "error": "ظرفیت این کد تمام شده است"}
        if row["starts_at"] and row["starts_at"] > now:
            return {"valid": False, "error": "این کد هنوز فعال نشده است"}
        if row["expires_at"] and row["expires_at"] < now:
            return {"valid": False, "error": "کد تخفیف منقضی شده است"}
        if row["min_amount"] > 0 and amount < row["min_amount"]:
            return {"valid": False, "error": f"حداقل مبلغ سفارش {row['min_amount']:,} تومان است"}
        if row["product_id"] and product_id and int(row["product_id"]) != int(product_id):
            return {"valid": False, "error": "این کد برای محصول دیگری است"}
        if row["category_id"] and category_id and int(row["category_id"]) != int(category_id):
            return {"valid": False, "error": "این کد برای دستهبندی دیگری است"}
        # کد شخصی (owner_user_id ست‌شده — مثلاً جایزهٔ گردونه/winback) فقط برای صاحبش
        # معتبره؛ حتی اگه کد به هر طریقی لو بره، کاربر دیگه نمی‌تونه ازش استفاده کنه.
        if row["owner_user_id"] is not None:
            if not user_id or int(row["owner_user_id"]) != int(user_id):
                return {"valid": False, "error": "این کد مخصوص شماست و برای شما قابل استفاده نیست"}
        if user_id:
            if row["max_uses_per_user"] > 0:
                uses = conn.execute(
                    "SELECT COUNT(*) FROM discount_usage WHERE code_id=? AND user_id=?;",
                    (row["id"], user_id)
                ).fetchone()[0]
                if uses >= row["max_uses_per_user"]:
                    return {"valid": False, "error": "سقف استفاده شما از این کد تمام شده است"}
            if row["first_buy_only"]:
                has_order = conn.execute(
                    "SELECT COUNT(*) FROM orders WHERE CAST(user_id AS INTEGER)=? "
                    "AND COALESCE(status,'active') != 'returned';",
                    (int(user_id),)
                ).fetchone()[0]
                if has_order > 0:
                    return {"valid": False, "error": "این کد فقط برای اولین خرید است"}
            if row["vip_only"]:
                # VIP = کاربر دارای برچسب VIP یا همکار تأییدشده
                is_vip = False
                try:
                    tag_row = conn.execute(
                        "SELECT tags FROM users WHERE CAST(user_id AS INTEGER)=?;", (int(user_id),)
                    ).fetchone()
                    if tag_row and tag_row["tags"] and "vip" in str(tag_row["tags"]).lower():
                        is_vip = True
                except Exception:
                    pass
                if not is_vip:
                    try:
                        pr = conn.execute(
                            "SELECT 1 FROM partners WHERE CAST(tg_user_id AS INTEGER)=? AND status='approved' LIMIT 1;",
                            (int(user_id),)
                        ).fetchone()
                        is_vip = bool(pr)
                    except Exception:
                        pass
                if not is_vip:
                    return {"valid": False, "error": "این کد مخصوص کاربران VIP است"}

        # محاسبه تخفیف
        if row["type"] == "percent":
            discount = int(amount * row["value"] / 100)
            if row["max_value"] > 0:
                discount = min(discount, row["max_value"])
        elif row["type"] == "fixed":
            discount = row["value"]
        elif row["type"] == "wallet":
            discount = row["value"]  # اعتبار کیفپول
        else:
            discount = 0
        discount = min(discount, amount)

        return {
            "valid": True, "discount_amount": discount, "type": row["type"],
            "value": row["value"], "code_id": row["id"], "error": None,
            "description": row["description"] or ""
        }
    finally:
        conn.close()


def issue_personal_discount_code(user_id: int, disc_type: str, value: int, *,
                                  expire_hours: int = 0, max_value: int = 0,
                                  description: str = "", source: str = "",
                                  source_ref_id: int = None, code_prefix: str = "SL") -> dict:
    """موتور مشترک صدور کد تخفیف **شخصی** یک‌بارمصرف — تک‌منبع حقیقت برای هر مکانیزم
    پاداشی که نیاز به کد شخصی داره (گردونهٔ شانس، بازگردانی کاربر/winback، و هر
    مکانیزم آینده مثل معرفی/تولد). خودِ `discount_codes`/`validate_discount` تغییر
    نمی‌کنه — فقط owner_user_id ست می‌شه که مالکیت رو در validate_discount اجرایی
    می‌کنه. `disc_type` دقیقاً همون واژگان ستون discount_codes.type است: 'percent'
    یا 'fixed' (نوع 'wallet' معنی نداره چون اعتبار کیف‌پول مسیر جدای خودش رو داره،
    نه از این تابع). برمی‌گردونه: {code, code_id, expires_at} یا {code:''} در صورت
    شکست پس از چند تلاش (برخورد تصادفی کد، عملاً نزدیک به غیرممکن)."""
    if disc_type not in ("percent", "fixed"):
        raise ValueError(f"disc_type نامعتبر: {disc_type}")
    ensure_discount_table()
    import random, string
    conn = _get_connection()
    try:
        expires_at = None
        if expire_hours and expire_hours > 0:
            row = conn.execute(
                "SELECT datetime('now','localtime', ?) AS v;", (f"+{int(expire_hours)} hours",)
            ).fetchone()
            expires_at = row["v"] if row else None
        for _ in range(8):
            code = code_prefix + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
            try:
                cur = conn.execute(
                    "INSERT INTO discount_codes "
                    "(code, type, value, max_value, max_uses, max_uses_per_user, is_active, "
                    "expires_at, description, owner_user_id, source, source_ref_id) "
                    "VALUES (?,?,?,?,1,1,1,?,?,?,?,?);",
                    (code, disc_type, int(value), int(max_value or 0), expires_at, description,
                     int(user_id), source or "", source_ref_id)
                )
                code_id = cur.lastrowid
                conn.commit()
                return {"code": code, "code_id": code_id, "expires_at": expires_at}
            except _INTEGRITY_ERRORS:
                conn.rollback()
                continue
        return {"code": "", "code_id": None, "expires_at": None}
    finally:
        conn.close()


def list_user_personal_codes(user_id: int) -> list[dict]:
    """صفحهٔ «جوایز من» — همهٔ کدهای شخصی این کاربر، از هر منبعی (گردونه/winback/...)،
    با وضعیت زنده (قابل‌استفاده/منقضی/مصرف‌شده) — بدون نیاز به جدول جدا، چون
    owner_user_id+used_count/max_uses همون چیزیه که لازمه."""
    ensure_discount_table()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT * FROM discount_codes WHERE owner_user_id=? ORDER BY id DESC;", (user_id,)
        ).fetchall()
        # فرمت «now» باید دقیقاً با فرمت ذخیرهٔ expires_at (datetime('now','localtime'))
        # یکی باشه، نه isoformat() با جداکنندهٔ T — همون رفع بخش بالای validate_discount.
        now = datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')
        out = []
        for r in rows:
            d = dict(r)
            if d["used_count"] >= d["max_uses"] and d["max_uses"] > 0:
                status = "used"
            elif d["expires_at"] and d["expires_at"] < now:
                status = "expired"
            elif not d["is_active"]:
                status = "inactive"
            else:
                status = "active"
            d["status"] = status
            out.append(d)
        return out
    finally:
        conn.close()


def use_discount(code_id: int, user_id: int = None, order_id: int = None):
    """ثبت استفاده از کد."""
    conn = _get_connection()
    try:
        conn.execute("UPDATE discount_codes SET used_count=used_count+1 WHERE id=?;", (code_id,))
        if user_id:
            conn.execute(
                "INSERT INTO discount_usage (code_id,user_id,order_id) VALUES (?,?,?);",
                (code_id, user_id, order_id)
            )
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── اشتراک موجودی ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_subscription_table():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_subscriptions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TEXT    DEFAULT (datetime('now','localtime')),
                notified   INTEGER DEFAULT 0,
                UNIQUE(user_id, product_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def subscribe_stock(user_id: int, product_id: int) -> bool:
    """ثبت اشتراک موجودی. True=جدید، False=قبلاً ثبت شده."""
    ensure_subscription_table()
    conn = _get_connection()
    try:
        # ⚠️ SELECT changes() خاص SQLite است و روی Postgres همیشه 1 برمی‌گرده (بخش
        # پاک‌سازی SQLite سند) — به‌جاش از cursor.rowcount استفاده شد که هم روی
        # sqlite3 هم psycopg2 درست کار می‌کنه (تست شد: 1=درج واقعی، 0=تداخل/نادیده)
        cur = conn.execute(
            "INSERT OR IGNORE INTO stock_subscriptions (user_id, product_id) VALUES (?,?);",
            (user_id, product_id)
        )
        changed = cur.rowcount
        conn.commit()
        return bool(changed and changed > 0)
    finally:
        conn.close()


def get_stock_subscribers(product_id: int) -> list:
    """لیست کاربرانی که اشتراک این محصول دارند و هنوز نوتیف نگرفتن."""
    ensure_subscription_table()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT user_id FROM stock_subscriptions WHERE product_id=? AND notified=0;",
            (product_id,)
        ).fetchall()
        return [r[0] for r in rows]
    finally:
        conn.close()


def mark_subscriptions_notified(product_id: int):
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE stock_subscriptions SET notified=1 WHERE product_id=?;",
            (product_id,)
        )
        conn.commit()
    finally:
        conn.close()


def reset_subscriptions_on_restock(product_id: int):
    """وقتی موجودی اومد، اشتراکها رو reset کن برای دور بعد."""
    conn = _get_connection()
    try:
        conn.execute(
            "DELETE FROM stock_subscriptions WHERE product_id=? AND notified=1;",
            (product_id,)
        )
        conn.commit()
    finally:
        conn.close()


def list_stock_requests() -> list:
    """همهٔ درخواست‌های «اطلاع‌رسانی موجود شدن» — برای مدیریت پنل ادمین، جدیدترین اول."""
    ensure_subscription_table()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("""
            SELECT s.id, s.user_id, s.product_id, s.created_at, s.notified,
                   p.title AS product_title,
                   (SELECT COUNT(*) FROM product_feed f WHERE f.product_id=p.id AND f.delivered=0) AS product_stock,
                   u.full_name
            FROM stock_subscriptions s
            LEFT JOIN products p ON p.id = s.product_id
            LEFT JOIN users u ON u.user_id = s.user_id
            ORDER BY s.id DESC;
        """).fetchall()]
    finally:
        conn.close()


def delete_stock_request(request_id: int) -> None:
    ensure_subscription_table()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM stock_subscriptions WHERE id=?;", (request_id,))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── پشتیبانی اختصاصی محصول ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

_ENSURE_PRODUCT_SUPPORT_SCHEMA_DONE = False

def ensure_product_support_schema():
    """اضافه کردن ستونهای setup + عکس محصول به products."""
    global _ENSURE_PRODUCT_SUPPORT_SCHEMA_DONE
    if _ENSURE_PRODUCT_SUPPORT_SCHEMA_DONE:
        return
    _ENSURE_PRODUCT_SUPPORT_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        for col, default in [
            ("support_after_purchase", "INTEGER DEFAULT 0"),
            ("setup_message", "TEXT DEFAULT ''"),
            ("image_url", "TEXT DEFAULT ''"),
            ("notify_on_restock", "INTEGER DEFAULT 0"),
            ("require_terms", "INTEGER DEFAULT 0"),
            ("terms_text", "TEXT DEFAULT ''"),
            ("created_by", "INTEGER"),
            ("created_at", "TEXT"),
        ]:
            try:
                conn.execute(f"ALTER TABLE products ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_product_support_flag(product_id: int) -> bool:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT support_after_purchase FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        conn.close()


def get_product_require_terms(product_id: int) -> bool:
    """آیا این محصول نیاز به تأیید قوانین خرید قبل از پرداخت داره؟ (بخش ۷ سند مینی‌اپ)."""
    ensure_product_support_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT require_terms FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        conn.close()


def get_product_terms_text(product_id: int) -> str:
    """متن قوانین خرید این محصول — اگه ادمین متن اختصاصی برای همین محصول ثبت کرده باشه
    (products.terms_text) همون برمی‌گرده؛ وگرنه متن پیش‌فرض عمومی (bot_config.PURCHASE_TERMS_TEXT)
    که از /admin/settings/purchase-terms قابل ویرایشه. دقیقاً همون الگوی setup_message
    (متن اختصاصی هر محصول)، فقط با یک fallback سراسری اضافه چون این متن قبلاً همیشه
    سراسری بود و محصولات موجود که require_terms روشن دارن نباید یک‌دفعه متن خالی ببینن."""
    ensure_product_support_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT terms_text FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        text = (row[0] if row else "") or ""
    except Exception:
        text = ""
    finally:
        conn.close()
    text = text.strip()
    if text:
        return text
    return (get_cfg("PURCHASE_TERMS_TEXT", "") or "").strip()


# ══════════════════════════════════════════════════════════════════════════════
# ─── تاریخچهٔ تغییر قیمت محصول (بخش ۹.۱ سند مینی‌اپ) ──────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

_PRICE_HISTORY_SCHEMA_DONE = False

def ensure_price_history_schema():
    global _PRICE_HISTORY_SCHEMA_DONE
    if _PRICE_HISTORY_SCHEMA_DONE:
        return
    _PRICE_HISTORY_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_price_history (
                id                 INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id         INTEGER NOT NULL,
                old_price          INTEGER,
                new_price          INTEGER,
                old_partner_price  INTEGER,
                new_partner_price  INTEGER,
                changed_by         INTEGER,
                changed_at         TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def log_price_change(product_id: int, old_price, new_price,
                      old_partner_price=None, new_partner_price=None,
                      changed_by: int = None) -> None:
    """فقط وقتی واقعاً قیمت فروش یا قیمت همکاری عوض شده باشه ثبت می‌شه — تغییر بقیهٔ
    فیلدهای محصول (عنوان، توضیحات، ...) اینجا اثری نداره."""
    old_price = int(old_price or 0)
    new_price = int(new_price or 0)
    old_partner_price = int(old_partner_price or 0)
    new_partner_price = int(new_partner_price or 0)
    if old_price == new_price and old_partner_price == new_partner_price:
        return
    ensure_price_history_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO product_price_history (product_id,old_price,new_price,old_partner_price,new_partner_price,changed_by) "
            "VALUES (?,?,?,?,?,?);",
            (product_id, old_price, new_price, old_partner_price, new_partner_price, changed_by)
        )
        conn.commit()
    finally:
        conn.close()


def get_price_history(product_id: int, limit: int = 20) -> list:
    ensure_price_history_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM product_price_history WHERE product_id=? ORDER BY id DESC LIMIT ?;",
            (product_id, limit)
        ).fetchall()]
    finally:
        conn.close()


def get_product_setup_message(product_id: int) -> str:
    """متن راهنما برای کاربر هنگام راهاندازی محصول."""
    conn = _get_connection()
    try:
        row = conn.execute("SELECT setup_message FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return (row[0] or "").strip() if row else ""
    except Exception:
        return ""
    finally:
        conn.close()


def get_product_notify_on_restock(product_id: int) -> bool:
    """آیا وقتی این محصول ناموجود است، دکمهٔ «موجود شد اطلاع بده» به‌جای خرید نشون داده بشه."""
    ensure_product_support_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT notify_on_restock FROM products WHERE id=? LIMIT 1;", (product_id,)).fetchone()
        return bool(row and row[0])
    except Exception:
        return False
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم معرفی کاربران ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_referral_schema():
    global _ENSURE_REFERRAL_SCHEMA_DONE
    if _ENSURE_REFERRAL_SCHEMA_DONE:
        return
    _ENSURE_REFERRAL_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS referral_settings (
                id              INTEGER PRIMARY KEY DEFAULT 1,
                reward_amount   INTEGER DEFAULT 5000,
                is_active       INTEGER DEFAULT 1,
                updated_at      TEXT    DEFAULT (datetime('now','localtime'))
            );
            INSERT OR IGNORE INTO referral_settings (id) VALUES (1);

            CREATE TABLE IF NOT EXISTS referrals (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                referrer_id     INTEGER NOT NULL,
                referred_id     INTEGER NOT NULL UNIQUE,
                rewarded        INTEGER DEFAULT 0,
                reward_amount   INTEGER DEFAULT 0,
                first_order_id  INTEGER DEFAULT NULL,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                rewarded_at     TEXT    DEFAULT NULL
            );
        """)
        # مهاجرت max_invites در referral_settings (قانون ۱۳)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(referral_settings);").fetchall()}
            if "max_invites" not in cols:
                conn.execute("ALTER TABLE referral_settings ADD COLUMN max_invites INTEGER DEFAULT 0;")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def get_referral_settings() -> dict:
    ensure_referral_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM referral_settings WHERE id=1;").fetchone()
        d = dict(row) if row else {"reward_amount": 5000, "is_active": 1}
        # فاز ۲: رفع باگ ریشه‌ای پاداش صفر — اگه صفره یعنی تنظیم نشده، پیش‌فرض ۵۰۰۰
        if int(d.get("reward_amount") or 0) <= 0:
            d["reward_amount"] = 5000
        d.setdefault("max_invites", 0)
        d.setdefault("is_active", 1)
        return d
    finally:
        conn.close()


def register_referral(referrer_id: int, referred_id: int) -> bool:
    """ثبت معرفی — False اگه قبلاً ثبت شده."""
    ensure_referral_schema()
    conn = _get_connection()
    try:
        # چک اول (سازگار هر دو dialect)
        existing = conn.execute(
            "SELECT 1 FROM referrals WHERE referred_id=? LIMIT 1;",
            (referred_id,)).fetchone()
        if existing:
            conn.close()
            return False
        conn.execute(
            "INSERT INTO referrals (referrer_id, referred_id) VALUES (?,?);",
            (referrer_id, referred_id))
        conn.commit()
        return True
    except Exception:
        return False
    finally:
        try: conn.close()
        except Exception: pass


def process_referral_reward(referred_id: int, order_id: int) -> dict:
    """
    اگه کاربر اولین خریدش رو کرده و معرف داره → پاداش بده.
    Returns: {rewarded, referrer_id, amount}
    """
    ensure_referral_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        ref = conn.execute(
            "SELECT * FROM referrals WHERE referred_id=? AND rewarded=0 LIMIT 1;",
            (referred_id,)
        ).fetchone()
        if not ref:
            return {"rewarded": False}

        settings = conn.execute("SELECT * FROM referral_settings WHERE id=1;").fetchone()
        amount   = int(settings["reward_amount"] if settings else 5000)

        # اضافه کردن به کیفپول همکاری (نه کیفپول اصلی)
        credit_partner_wallet(ref["referrer_id"], amount,
                              note=f"پاداش معرفی — سفارش #{order_id}")

        conn.execute("""UPDATE referrals SET rewarded=1, reward_amount=?, first_order_id=?,
            rewarded_at=datetime('now') WHERE id=?;""", (amount, order_id, ref["id"]))
        conn.commit()
        return {"rewarded": True, "referrer_id": ref["referrer_id"], "amount": amount}
    finally:
        conn.close()


def process_referral_commission(referred_id: int, order_id: int, order_price: int) -> dict:
    """
    پورسانت روی خرید دعوت‌شده — فقط برای معرفِ همکار تأییدشده:
      1. اگر سطح معرف مبلغ ثابت (commission_fixed) دارد → همان مبلغ
      2. وگرنه اگر سطح درصد (commission_percent) دارد → درصدی از مبلغ سفارش
      3. وگرنه → درصد عمومی از partner_commission
    Returns: {paid, referrer_id, amount, tier_name}
    """
    ensure_referral_schema()
    ensure_partner_tiers_extended()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        ref = conn.execute(
            "SELECT referrer_id FROM referrals WHERE referred_id=? LIMIT 1;",
            (referred_id,)
        ).fetchone()
        if not ref:
            return {"paid": False}
        referrer_id = int(ref["referrer_id"])
        # ← مورد ۱۰: فقط همکار تأییدشده پورسانت می‌گیرد
        if not _is_approved_partner(referrer_id):
            return {"paid": False}

        # تنظیمات عمومی پورسانت
        gset = conn.execute("SELECT * FROM partner_commission WHERE id=1;").fetchone()
        if gset and not int(gset["is_active"] or 0):
            return {"paid": False}
        global_pct = float(gset["percent"] if gset else 5.0)
        min_order  = int(gset["min_order"] if gset else 0)
        max_payout = int(gset["max_payout"] if gset else 0)

        if min_order > 0 and order_price < min_order:
            return {"paid": False}

        # سطح معرف
        try:
            order_count = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE CAST(user_id AS INTEGER)=? AND buyer_type='partner';",
                (referrer_id,)
            ).fetchone()[0]
        except Exception:
            order_count = 0
        # سطح فعلی — اگه خریدی ندارد، پایین‌ترین سطح (کمترین min_orders)
        tier = conn.execute("""
            SELECT * FROM partner_tiers WHERE min_orders <= ?
            ORDER BY min_orders DESC LIMIT 1;
        """, (order_count,)).fetchone()
        if not tier:
            tier = conn.execute(
                "SELECT * FROM partner_tiers ORDER BY min_orders ASC LIMIT 1;"
            ).fetchone()

        tier_name  = tier["name"] if tier else "—"
        tier_fixed = int(tier["commission_fixed"] or 0) if tier and "commission_fixed" in tier.keys() else 0
        tier_pct   = float(tier["commission_percent"] or 0) if tier and "commission_percent" in tier.keys() else 0.0

        if tier_fixed > 0:
            amount = tier_fixed
        elif tier_pct > 0:
            amount = int(order_price * tier_pct / 100)
        else:
            # سطح تنظیم نشده → درصد عمومی (fallback اضطراری)
            amount = int(order_price * global_pct / 100)

        if max_payout > 0:
            amount = min(amount, max_payout)
        if amount <= 0:
            return {"paid": False}
    finally:
        conn.close()

    wallet = credit_referrer(referrer_id, amount,
                             note=f"پاداش فروش — سفارش #{order_id} (سطح {tier_name})")
    return {"paid": True, "referrer_id": referrer_id, "amount": amount,
            "tier_name": tier_name, "wallet": wallet}




def check_and_notify_tier_up(user_id: int) -> dict | None:
    """سطح فعلی و قبلی همکار را مقایسه می‌کند — اگر ارتقا یافته، اطلاعات برمی‌گرداند."""
    ensure_partner_tiers_extended()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # تعداد خریدهای همکاری
        order_count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE CAST(user_id AS INTEGER)=? "
            "AND buyer_type='partner' AND COALESCE(status,'active')!='returned';",
            (user_id,)).fetchone()[0]
        tiers = conn.execute(
            "SELECT * FROM partner_tiers ORDER BY min_orders ASC;"
        ).fetchall()
        if not tiers:
            return None
        # سطح فعلی
        cur_tier = tiers[0]
        for t in tiers:
            if order_count >= int(t["min_orders"] or 0):
                cur_tier = t
        # سطح ثبت‌شده در پارتنر (notified_tier)
        pr = conn.execute(
            "SELECT notified_tier FROM partners WHERE CAST(tg_user_id AS INTEGER)=?;",
            (user_id,)).fetchone()
        old_tier_id = int(pr["notified_tier"] or 0) if pr and pr["notified_tier"] else 0
        new_tier_id = int(cur_tier["id"])
        if new_tier_id > old_tier_id:
            # به‌روزرسانی ستون notified_tier
            conn.execute(
                "UPDATE partners SET notified_tier=? WHERE CAST(tg_user_id AS INTEGER)=?;",
                (new_tier_id, user_id))
            conn.commit()
            return {"tier": dict(cur_tier), "old_tier_id": old_tier_id}
        return None
    except Exception:
        return None
    finally:
        conn.close()

def get_referral_stats(referrer_id: int) -> dict:
    ensure_referral_schema()
    conn = _get_connection()
    try:
        total    = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?;", (referrer_id,)).fetchone()[0]
        rewarded = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        earned   = conn.execute("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        return {"total": total, "rewarded": rewarded, "earned": int(earned)}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم فروشندگان ──────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

SELLER_LEVELS = [
    {"id":1,"name":"برنز",  "emoji":"🥉","min_sales":0,  "commission":50000},
    {"id":2,"name":"نقره",  "emoji":"🥈","min_sales":5,  "commission":70000},
    {"id":3,"name":"طلایی", "emoji":"🥇","min_sales":20, "commission":100000},
    {"id":4,"name":"الماس", "emoji":"💎","min_sales":50, "commission":300000},
]

def ensure_seller_schema():
    conn = _get_connection()
    try:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS seller_levels (
                id              INTEGER PRIMARY KEY,
                name            TEXT    NOT NULL,
                emoji           TEXT    DEFAULT '',
                min_sales       INTEGER DEFAULT 0,
                commission      INTEGER DEFAULT 50000,
                updated_at      TEXT    DEFAULT (datetime('now','localtime'))
            );

            CREATE TABLE IF NOT EXISTS sellers (
                user_id         INTEGER PRIMARY KEY,
                code            TEXT    UNIQUE NOT NULL,
                level_id        INTEGER DEFAULT 1,
                status          TEXT    DEFAULT 'active',
                total_sales     INTEGER DEFAULT 0,
                total_earned    INTEGER DEFAULT 0,
                wallet_balance  INTEGER DEFAULT 0,
                custom_commission INTEGER DEFAULT NULL,
                invited_users   INTEGER DEFAULT 0,
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                updated_at      TEXT    DEFAULT (datetime('now','localtime')),
                FOREIGN KEY(level_id) REFERENCES seller_levels(id)
            );

            CREATE TABLE IF NOT EXISTS seller_commissions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id       INTEGER NOT NULL,
                order_id        INTEGER NOT NULL,
                buyer_id        INTEGER NOT NULL,
                product_id      INTEGER,
                product_title   TEXT    DEFAULT '',
                order_amount    INTEGER DEFAULT 0,
                commission      INTEGER DEFAULT 0,
                level_id        INTEGER DEFAULT 1,
                status          TEXT    DEFAULT 'earned',
                created_at      TEXT    DEFAULT (datetime('now','localtime')),
                paid_at         TEXT    DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS seller_payouts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                seller_id       INTEGER NOT NULL,
                amount          INTEGER NOT NULL,
                status          TEXT    DEFAULT 'pending',
                card_number     TEXT    DEFAULT '',
                card_name       TEXT    DEFAULT '',
                requested_at    TEXT    DEFAULT (datetime('now','localtime')),
                processed_at    TEXT    DEFAULT NULL,
                admin_note      TEXT    DEFAULT ''
            );
        """)
        # seed default levels
        for lv in SELLER_LEVELS:
            conn.execute("""INSERT OR IGNORE INTO seller_levels (id,name,emoji,min_sales,commission)
                VALUES (?,?,?,?,?);""", (lv["id"],lv["name"],lv["emoji"],lv["min_sales"],lv["commission"]))
        conn.commit()
    finally:
        conn.close()


def _gen_seller_code() -> str:
    import random, string
    while True:
        code = "STLAND-" + "".join(random.choices(string.digits, k=4))
        conn = _get_connection()
        exists = conn.execute("SELECT 1 FROM sellers WHERE code=?;", (code,)).fetchone()
        conn.close()
        if not exists:
            return code


def seller_activate(user_id: int) -> str:
    """فعالسازی فروشنده — کد میسازه."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        existing = conn.execute("SELECT code FROM sellers WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            return existing["code"]
        code = _gen_seller_code()
        conn.execute("INSERT INTO sellers (user_id,code) VALUES (?,?);", (user_id, code))
        conn.commit()
        return code
    finally:
        conn.close()


def seller_get(user_id: int) -> dict | None:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT s.*, sl.name as level_name, sl.emoji as level_emoji,
                   sl.commission as level_commission, sl.min_sales as level_min,
                   (SELECT sl2.min_sales FROM seller_levels sl2 WHERE sl2.id=s.level_id+1 LIMIT 1) as next_min
            FROM sellers s JOIN seller_levels sl ON sl.id=s.level_id
            WHERE s.user_id=?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def seller_is_active(user_id: int) -> bool:
    ensure_seller_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT status FROM sellers WHERE user_id=? AND status='active';", (user_id,)).fetchone()
        return bool(row)
    finally:
        conn.close()


def seller_get_commission(seller_id: int, product_id: int = None) -> int:
    """محاسبه پورسانت — اختصاصی اگه داشت، وگرنه سطح."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        s = conn.execute("""
            SELECT s.custom_commission, sl.commission
            FROM sellers s JOIN seller_levels sl ON sl.id=s.level_id
            WHERE s.user_id=? AND s.status='active';
        """, (seller_id,)).fetchone()
        if not s:
            return 0
        return int(s["custom_commission"] if s["custom_commission"] else s["commission"])
    finally:
        conn.close()


def seller_record_sale(seller_id: int, order_id: int, buyer_id: int,
                        product_id: int, product_title: str, order_amount: int) -> int:
    """ثبت فروش و پورسانت — returns commission amount."""
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        s = conn.execute("SELECT * FROM sellers WHERE user_id=? AND status='active';", (seller_id,)).fetchone()
        if not s:
            return 0
        commission = seller_get_commission(seller_id, product_id)
        now = datetime.utcnow().isoformat()
        conn.execute("""
            INSERT INTO seller_commissions
                (seller_id,order_id,buyer_id,product_id,product_title,order_amount,commission,level_id,created_at)
            VALUES (?,?,?,?,?,?,?,?,?);
        """, (seller_id, order_id, buyer_id, product_id, product_title, order_amount, commission, s["level_id"], now))

        new_sales = int(s["total_sales"]) + 1
        new_earned = int(s["total_earned"]) + commission
        new_wallet = int(s["wallet_balance"]) + commission

        # بررسی ارتقای سطح
        new_level = s["level_id"]
        levels = conn.execute("SELECT * FROM seller_levels ORDER BY min_sales DESC;").fetchall()
        for lv in levels:
            if new_sales >= lv["min_sales"]:
                new_level = lv["id"]
                break

        conn.execute("""
            UPDATE sellers SET total_sales=?, total_earned=?, wallet_balance=?,
            level_id=?, invited_users=invited_users+1, updated_at=? WHERE user_id=?;
        """, (new_sales, new_earned, new_wallet, new_level, now, seller_id))
        conn.commit()
        return commission
    finally:
        conn.close()


def seller_request_payout(seller_id: int, amount: int, card_number: str, card_name: str) -> dict:
    ensure_seller_schema()
    conn = _get_connection()
    try:
        s = conn.execute("SELECT wallet_balance FROM sellers WHERE user_id=?;", (seller_id,)).fetchone()
        if not s or int(s[0]) < amount:
            return {"ok": False, "error": "موجودی کافی نیست"}
        conn.execute("""INSERT INTO seller_payouts (seller_id,amount,card_number,card_name)
            VALUES (?,?,?,?);""", (seller_id, amount, card_number, card_name))
        conn.execute("UPDATE sellers SET wallet_balance=wallet_balance-? WHERE user_id=?;", (amount, seller_id))
        conn.commit()
        return {"ok": True}
    finally:
        conn.close()


def seller_list_all() -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT s.*, sl.name as level_name, sl.emoji as level_emoji,
                   u.full_name, u.username
            FROM sellers s
            JOIN seller_levels sl ON sl.id=s.level_id
            LEFT JOIN users u ON u.user_id=s.user_id
            ORDER BY s.total_sales DESC;
        """).fetchall()
    finally:
        conn.close()


def seller_list_payouts(status: str = None) -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = f"WHERE p.status='{status}'" if status else ""
        return conn.execute(f"""
            SELECT p.*, s.code, u.full_name, u.username
            FROM seller_payouts p
            JOIN sellers s ON s.user_id=p.seller_id
            LEFT JOIN users u ON u.user_id=p.seller_id
            {where} ORDER BY p.id DESC LIMIT 200;
        """).fetchall()
    finally:
        conn.close()


def seller_update(seller_id: int, **kwargs):
    ensure_seller_schema()
    conn = _get_connection()
    try:
        allowed = {"status","level_id","custom_commission","wallet_balance"}
        sets = ", ".join(f"{k}=?" for k in kwargs if k in allowed)
        vals = [v for k,v in kwargs.items() if k in allowed]
        if sets:
            conn.execute(f"UPDATE sellers SET {sets}, updated_at=datetime('now') WHERE user_id=?;",
                         vals + [seller_id])
            conn.commit()
    finally:
        conn.close()


def seller_payout_update(payout_id: int, status: str, note: str = ""):
    ensure_seller_schema()
    conn = _get_connection()
    try:
        p = conn.execute("SELECT seller_id, amount, status FROM seller_payouts WHERE id=?;", (payout_id,)).fetchone()
        if not p:
            return
        if p[2] != "pending":
            return
        conn.execute("UPDATE seller_payouts SET status=?,admin_note=?,processed_at=datetime('now') WHERE id=?;",
                     (status, note, payout_id))
        # اگه رد شد پول برگرده
        if status == "rejected":
            conn.execute("UPDATE sellers SET wallet_balance=wallet_balance+? WHERE user_id=?;", (p[1], p[0]))
        conn.commit()
    finally:
        conn.close()


def seller_get_levels() -> list:
    ensure_seller_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM seller_levels ORDER BY id;").fetchall()
    finally:
        conn.close()


# ── درخواست فروشندگی (جایگزین درخواست نمایندگی) ──────────────────────────────

def seller_apply(user_id: int, full_name: str, phone: str, city: str, shop_name: str, note: str = "") -> bool:
    """ثبت درخواست فروشندگی — ذخیره در partner_requests برای بررسی ادمین."""
    try:
        upsert_partner_request(
            tg_user_id=user_id, phone=phone, username="",
            full_name=full_name, note=note, city=city, shop_name=shop_name
        )
        return True
    except Exception:
        return False


def seller_pending_applications() -> list:
    """درخواستهای در انتظار فروشندگی."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT p.*, u.username
            FROM partners p
            LEFT JOIN users u ON u.user_id=p.tg_user_id
            WHERE p.status='pending'
            ORDER BY p.created_at DESC LIMIT 100;
        """).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


def seller_approve_application(user_id: int) -> str:
    """تأیید درخواست: approve در partners + activate در sellers."""
    approve_partner(user_id)
    code = seller_activate(user_id)
    return code


# ─── ستونهای اضافی کاربران (یادداشت، برچسب، مسدودسازی) ──────────────────────

def ensure_user_extra_schema():
    global _ENSURE_USER_EXTRA_SCHEMA_DONE
    if _ENSURE_USER_EXTRA_SCHEMA_DONE:
        return
    _ENSURE_USER_EXTRA_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        for col, default in [
            ("admin_note", "TEXT DEFAULT ''"),
            ("tags",       "TEXT DEFAULT ''"),
            ("is_blocked", "INTEGER DEFAULT 0"),
            ("avatar_url", "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE users ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_user_avatar(user_id: int) -> str:
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT avatar_url FROM users WHERE user_id=?;", (user_id,)).fetchone()
        return (row["avatar_url"] if row else "") or ""
    finally:
        conn.close()


def set_user_avatar(user_id: int, url: str) -> None:
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO users (user_id, avatar_url) VALUES (?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET avatar_url=excluded.avatar_url;",
            (user_id, url))
        conn.commit()
    finally:
        conn.close()


def get_user_full(user_id: int) -> dict | None:
    ensure_user_extra_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT u.*,
                   COALESCE(w.balance,0) AS balance,
                   (SELECT COUNT(*) FROM orders o WHERE CAST(o.user_id AS INTEGER)=u.user_id AND o.status='active') AS order_count,
                   (SELECT 1 FROM partners p WHERE p.tg_user_id=u.user_id AND p.status='approved' LIMIT 1) AS is_partner
            FROM users u
            LEFT JOIN wallets w ON w.user_id=u.user_id
            WHERE u.user_id=?;
        """, (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_user_note(user_id: int, note: str, tags: str = None):
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        if tags is not None:
            conn.execute("UPDATE users SET admin_note=?, tags=? WHERE user_id=?;", (note, tags, user_id))
        else:
            conn.execute("UPDATE users SET admin_note=? WHERE user_id=?;", (note, user_id))
        conn.commit()
    finally:
        conn.close()


def toggle_user_block(user_id: int) -> bool:
    ensure_user_extra_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("SELECT is_blocked FROM users WHERE user_id=?;", (user_id,)).fetchone()
        new_val = 0 if (cur and cur[0]) else 1
        conn.execute("UPDATE users SET is_blocked=? WHERE user_id=?;", (new_val, user_id))
        conn.commit()
        return bool(new_val)
    finally:
        conn.close()


def get_user_orders(user_id: int, limit: int = 20) -> list:
    """سفارش‌های کاربر — سفارش‌های برگشت‌خورده نمایش داده نمی‌شوند."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT * FROM orders
            WHERE CAST(user_id AS INTEGER)=?
              AND COALESCE(status,'active') != 'returned'
            ORDER BY id DESC LIMIT ?;
        """, (user_id, limit)).fetchall()
    finally:
        conn.close()


def get_user_tickets(user_id: int, limit: int = 20) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT * FROM tickets WHERE user_id=?
            ORDER BY id DESC LIMIT ?;
        """, (user_id, limit)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


# ─── سیستم سطوح و تنظیمات همکاری ────────────────────────────────────────────

def ensure_partner_system_schema():
    """جداول سطوح همکاری + تنظیمات پورسانت."""
    global _ENSURE_PARTNER_SYSTEM_SCHEMA_DONE
    if _ENSURE_PARTNER_SYSTEM_SCHEMA_DONE:
        return
    _ENSURE_PARTNER_SYSTEM_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        # سطوح همکاری
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_tiers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                icon TEXT DEFAULT '🥉',
                min_orders INTEGER DEFAULT 0,
                sort_order INTEGER DEFAULT 0
            );
        """)
        # تنظیمات پورسانت همکاری
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_commission (
                id INTEGER PRIMARY KEY CHECK (id=1),
                percent REAL DEFAULT 5.0,
                min_order INTEGER DEFAULT 0,
                max_payout INTEGER DEFAULT 0,
                is_active INTEGER DEFAULT 1,
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()

        # سطوح پیشفرض اگه خالی بود — با پورسانت و متن تبریک
        cnt = conn.execute("SELECT COUNT(*) FROM partner_tiers;").fetchone()[0]
        if cnt == 0:
            defaults = [
                ("برنز", "🥉", 0, 1),
                ("نقره‌ای", "🥈", 10, 2),
                ("طلایی", "🥇", 30, 3),
                ("الماس", "💎", 70, 4),
            ]
            conn.executemany(
                "INSERT INTO partner_tiers (name,icon,min_orders,sort_order) VALUES (?,?,?,?);",
                defaults
            )
            conn.commit()

        # تنظیمات پیشفرض
        c2 = conn.execute("SELECT COUNT(*) FROM partner_commission;").fetchone()[0]
        if c2 == 0:
            conn.execute("INSERT INTO partner_commission (id,percent,min_order,max_payout,is_active) VALUES (1,5.0,0,0,1);")
            # مهاجرت ستون notified_tier در جدول partners
        try:
            conn.execute("ALTER TABLE partners ADD COLUMN notified_tier INTEGER DEFAULT 0;")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def get_partner_tiers() -> list:
    ensure_partner_system_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM partner_tiers ORDER BY sort_order, min_orders;").fetchall()
    finally:
        conn.close()


def save_partner_tier(tier_id, name, icon, min_orders):
    ensure_partner_system_schema()
    conn = _get_connection()
    try:
        if tier_id:
            conn.execute("UPDATE partner_tiers SET name=?,icon=?,min_orders=? WHERE id=?;",
                         (name, icon, min_orders, tier_id))
        else:
            mx = conn.execute("SELECT COALESCE(MAX(sort_order),0)+1 FROM partner_tiers;").fetchone()[0]
            conn.execute("INSERT INTO partner_tiers (name,icon,min_orders,sort_order) VALUES (?,?,?,?);",
                         (name, icon, min_orders, mx))
        conn.commit()
    finally:
        conn.close()


def delete_partner_tier(tier_id):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM partner_tiers WHERE id=?;", (tier_id,))
        conn.commit()
    finally:
        conn.close()


def get_partner_commission() -> dict:
    ensure_partner_system_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_commission WHERE id=1;").fetchone()
        return dict(row) if row else {"percent": 5.0, "min_order": 0, "max_payout": 0, "is_active": 1}
    finally:
        conn.close()


def save_partner_commission(percent, min_order, max_payout, is_active):
    ensure_partner_system_schema()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_commission
            SET percent=?,min_order=?,max_payout=?,is_active=?,updated_at=datetime('now') WHERE id=1;""",
            (percent, min_order, max_payout, is_active))
        conn.commit()
    finally:
        conn.close()


def get_partner_order_count(tg_user_id: int) -> int:
    """تعداد خریدهای همکاری (با قیمت همکار)."""
    conn = _get_connection()
    try:
        n = conn.execute("""
            SELECT COUNT(*) FROM orders
            WHERE CAST(user_id AS INTEGER)=? AND buyer_type='partner';
        """, (tg_user_id,)).fetchone()[0]
        return int(n or 0)
    except Exception:
        return 0
    finally:
        conn.close()


def get_partner_tier_for(order_count: int) -> dict:
    """سطح فعلی بر اساس تعداد خرید — شامل photo_file_id."""
    ensure_partner_tiers_extended()
    tiers = get_partner_tiers()
    current = None
    for t in tiers:
        if order_count >= t["min_orders"]:
            current = t
    if current is None and tiers:
        current = tiers[0]
    return dict(current) if current else {"name": "برنز", "icon": "🥉", "min_orders": 0, "photo_file_id": ""}


def get_referral_stats_for(referrer_id: int) -> dict:
    """آمار کلی زیرمجموعههای یک معرف."""
    conn = _get_connection()
    try:
        total = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=?;", (referrer_id,)).fetchone()[0]
        rewarded = conn.execute("SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        total_reward = conn.execute("SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE referrer_id=? AND rewarded=1;", (referrer_id,)).fetchone()[0]
        return {"total": int(total or 0), "rewarded": int(rewarded or 0), "total_reward": int(total_reward or 0)}
    except Exception:
        return {"total": 0, "rewarded": 0, "total_reward": 0}
    finally:
        conn.close()


def get_partner_team_stats(referrer_id: int) -> dict:
    """تیم فروش دوسطحی یک همکار — دقیقاً همون کوئری cb_partner_sub_stats در bot.py،
    فقط به‌جای متن HTML، دادهٔ خام برمی‌گردونه (برای مصرف مینی‌اپ/API)."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT r.referred_id AS sid,
                   COALESCE(u.full_name, u.username, 'کاربر ' || r.referred_id) AS name,
                   COALESCE(o.cnt, 0)   AS order_count,
                   COALESCE(o.total, 0) AS total_spent,
                   COALESCE(r2.cnt, 0)  AS own_subs
            FROM referrals r
            LEFT JOIN users u ON CAST(u.user_id AS INTEGER) = r.referred_id
            LEFT JOIN (
                SELECT CAST(user_id AS INTEGER) AS ouid, COUNT(*) AS cnt, SUM(price) AS total
                FROM orders WHERE COALESCE(status,'active') != 'returned'
                GROUP BY CAST(user_id AS INTEGER)
            ) o ON o.ouid = r.referred_id
            LEFT JOIN (
                SELECT referrer_id, COUNT(*) AS cnt FROM referrals GROUP BY referrer_id
            ) r2 ON r2.referrer_id = r.referred_id
            WHERE r.referrer_id = ?
            ORDER BY total_spent DESC, order_count DESC
            LIMIT 30;
        """, (referrer_id,)).fetchall()
        members = [{"user_id": r["sid"], "name": r["name"], "order_count": int(r["order_count"]),
                    "total_spent": int(r["total_spent"]), "own_subs": int(r["own_subs"])} for r in rows]
        return {
            "members": members,
            "total_members": len(members),
            "total_orders": sum(m["order_count"] for m in members),
            "total_spent": sum(m["total_spent"] for m in members),
        }
    except Exception:
        return {"members": [], "total_members": 0, "total_orders": 0, "total_spent": 0}
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── کیفپول همکاری ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_partner_wallet_schema():
    global _ENSURE_PARTNER_WALLET_SCHEMA_DONE
    if _ENSURE_PARTNER_WALLET_SCHEMA_DONE:
        return
    _ENSURE_PARTNER_WALLET_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_wallets (
                user_id   INTEGER PRIMARY KEY,
                balance   INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_transactions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                type       TEXT NOT NULL,
                amount     INTEGER NOT NULL,
                note       TEXT DEFAULT '',
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_payouts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id      INTEGER NOT NULL,
                amount       INTEGER NOT NULL,
                status       TEXT DEFAULT 'pending',
                admin_note   TEXT DEFAULT '',
                created_at   TEXT DEFAULT (datetime('now')),
                processed_at TEXT
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_payout_settings (
                id            INTEGER PRIMARY KEY CHECK (id=1),
                min_amount    INTEGER DEFAULT 50000,
                max_amount    INTEGER DEFAULT 0,
                max_per_month INTEGER DEFAULT 2,
                is_active     INTEGER DEFAULT 1,
                updated_at    TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        # پیشفرض تنظیمات تسویه
        cnt = conn.execute("SELECT COUNT(*) FROM partner_payout_settings;").fetchone()[0]
        if cnt == 0:
            conn.execute("INSERT INTO partner_payout_settings (id) VALUES (1);")
            conn.commit()
    finally:
        conn.close()


def get_partner_wallet_balance(user_id: int) -> int:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        return int(row[0] or 0) if row else 0
    finally:
        conn.close()


def credit_partner_wallet(user_id: int, amount: int, note: str = "") -> int:
    """واریز پورسانت به کیفپول همکاری. Returns new balance."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        existing = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE partner_wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (amount, user_id))
        else:
            conn.execute("INSERT INTO partner_wallets (user_id, balance) VALUES (?,?);", (user_id, amount))
        conn.execute("INSERT INTO partner_transactions (user_id, type, amount, note) VALUES (?,?,?,?);",
                     (user_id, "credit", amount, note))
        conn.commit()
        row = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        return int(row[0] or 0)
    finally:
        conn.close()


def transfer_partner_to_main(user_id: int, amount: int) -> dict:
    """انتقال از کیفپول همکاری به کیفپول اصلی."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        bal = conn.execute("SELECT balance FROM partner_wallets WHERE user_id=?;", (user_id,)).fetchone()
        current = int(bal[0] or 0) if bal else 0
        if current < amount:
            return {"ok": False, "error": "موجودی کافی نیست"}
        if amount <= 0:
            return {"ok": False, "error": "مبلغ نامعتبر"}
        # کسر از partner wallet
        conn.execute("UPDATE partner_wallets SET balance=balance-?, updated_at=datetime('now') WHERE user_id=?;",
                     (amount, user_id))
        conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                     (user_id, "transfer_out", amount, "انتقال به کیفپول اصلی"))
        # واریز به کیفپول اصلی
        existing = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (amount, user_id))
        else:
            conn.execute("INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,datetime('now'));",
                         (user_id, amount))
        conn.commit()
        return {"ok": True, "transferred": amount}
    finally:
        conn.close()


def get_partner_payout_settings() -> dict:
    ensure_partner_wallet_schema()
    ensure_payout_settings_extended()  # ← حیاتی: بدون این فراخوانی، ستون‌های متنی اصلاً در DB وجود ندارند
    _TEXT_DEFAULTS = {
        "guide_text": (
            "📤 <b>شرایط و راهنمای درخواست تسویه</b>\n\n"
            "برای ثبت درخواست تسویه، موارد زیر را رعایت کنید:\n\n"
            "۱. اطلاعات حساب بانکی (شبا و نام صاحب حساب) باید ثبت شده باشد\n"
            "۲. موجودی کیف‌پول همکاری باید به حداقل تعیین‌شده رسیده باشد\n"
            "۳. پس از ثبت درخواست، تیم مالی آن را بررسی و تأیید می‌کند\n"
            "۴. پرداخت معمولاً ظرف ۴۸ ساعت کاری انجام می‌شود\n\n"
            "⚠️ درخواست‌های با اطلاعات نادرست یا مغایرت حساب رد خواهند شد."
        ),
        "approval_message": (
            "✅ <b>درخواست تسویه شما تأیید شد!</b>\n\n"
            "💰 مبلغ درخواستی به حساب بانکی ثبت‌شده واریز خواهد شد.\n"
            "⏰ پردازش: ۲۴ تا ۴۸ ساعت کاری\n\n"
            "ممنون از همکاری شما 🙏"
        ),
        "rejection_message": (
            "❌ <b>درخواست تسویه رد شد</b>\n\n"
            "درخواست تسویه شما تأیید نشد. لطفاً موارد زیر را بررسی کنید:\n"
            "• صحت اطلاعات حساب بانکی\n"
            "• کافی بودن موجودی\n\n"
            "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید 💬"
        ),
    }
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_payout_settings WHERE id=1;").fetchone()
        if row:
            d = dict(row)
            # نکته حیاتی: حتی اگه ردیف در DB وجود دارد، فیلدهای متنیِ خالی
            # (سرور قدیمی که قبل از این آپدیت یک‌بار ذخیره شده) با پیش‌فرض حرفه‌ای پر شوند
            for key, default_text in _TEXT_DEFAULTS.items():
                if not (d.get(key) or "").strip():
                    d[key] = default_text
            d.setdefault("min_amount", 50000)
            d.setdefault("max_amount", 0)
            d.setdefault("max_per_month", 2)
            d.setdefault("is_active", 1)
            d.setdefault("review_hours", 48)
            return d
        return {
            "min_amount": 50000, "max_amount": 0, "max_per_month": 2,
            "is_active": 1, "review_hours": 48,
            **_TEXT_DEFAULTS,
        }
    finally:
        conn.close()


def save_partner_payout_settings(min_amount, max_amount, max_per_month, is_active):
    ensure_partner_wallet_schema()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_payout_settings
            SET min_amount=?, max_amount=?, max_per_month=?, is_active=?, updated_at=datetime('now')
            WHERE id=1;""", (min_amount, max_amount, max_per_month, is_active))
        conn.commit()
    finally:
        conn.close()


def request_partner_payout(user_id: int, amount: int) -> dict:
    """ثبت درخواست تسویه."""
    ensure_partner_wallet_schema()
    settings = get_partner_payout_settings()
    if not settings.get("is_active"):
        return {"ok": False, "error": "تسویه در حال حاضر غیرفعال است"}
    bal = get_partner_wallet_balance(user_id)
    if amount > bal:
        return {"ok": False, "error": "موجودی کافی نیست"}
    min_a = int(settings.get("min_amount") or 0)
    max_a = int(settings.get("max_amount") or 0)
    if min_a and amount < min_a:
        return {"ok": False, "error": f"حداقل مبلغ تسویه {min_a:,} تومان است"}
    if max_a and amount > max_a:
        return {"ok": False, "error": f"حداکثر مبلغ تسویه {max_a:,} تومان است"}
    # بررسی تعداد ماهانه
    max_pm = int(settings.get("max_per_month") or 0)
    if max_pm:
        conn = _get_connection()
        try:
            cnt = conn.execute("""
                SELECT COUNT(*) FROM partner_payouts
                WHERE user_id=? AND status IN ('pending','approved')
                AND strftime('%Y-%m', created_at)=strftime('%Y-%m','now');
            """, (user_id,)).fetchone()[0]
        finally:
            conn.close()
        if cnt >= max_pm:
            return {"ok": False, "error": f"سقف {max_pm} درخواست در ماه تکمیل شده"}
    conn = _get_connection()
    try:
        # کسر موقت از کیفپول
        conn.execute("UPDATE partner_wallets SET balance=balance-?, updated_at=datetime('now') WHERE user_id=?;",
                     (amount, user_id))
        conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                     (user_id, "payout_request", amount, "درخواست تسویه"))
        conn.execute("INSERT INTO partner_payouts (user_id,amount,status) VALUES (?,?,'pending');",
                     (user_id, amount))
        conn.commit()
        row = conn.execute("SELECT last_insert_rowid();").fetchone()
        return {"ok": True, "payout_id": row[0]}
    finally:
        conn.close()


def process_partner_payout(payout_id: int, approve: bool, admin_note: str = "") -> dict:
    """تأیید یا رد تسویه توسط ادمین."""
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        pay = conn.execute("SELECT * FROM partner_payouts WHERE id=?;", (payout_id,)).fetchone()
        if not pay:
            return {"ok": False, "error": "درخواست یافت نشد"}
        if pay["status"] != "pending":
            return {"ok": False, "error": "درخواست قبلاً پردازش شده"}
        new_status = "approved" if approve else "rejected"
        conn.execute("""UPDATE partner_payouts SET status=?, admin_note=?, processed_at=datetime('now')
            WHERE id=?;""", (new_status, admin_note, payout_id))
        if not approve:
            # رد شد → برگردان به کیفپول
            conn.execute("UPDATE partner_wallets SET balance=balance+?, updated_at=datetime('now') WHERE user_id=?;",
                         (pay["amount"], pay["user_id"]))
            conn.execute("INSERT INTO partner_transactions (user_id,type,amount,note) VALUES (?,?,?,?);",
                         (pay["user_id"], "payout_rejected", pay["amount"], "رد تسویه — برگشت موجودی"))
        conn.commit()
        return {"ok": True, "user_id": pay["user_id"], "amount": pay["amount"], "approved": approve}
    finally:
        conn.close()


def get_partner_transactions(user_id: int, limit: int = 20) -> list:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""SELECT * FROM partner_transactions WHERE user_id=?
            ORDER BY id DESC LIMIT ?;""", (user_id, limit)).fetchall()
    finally:
        conn.close()


def get_partner_payouts(user_id: int = None, status: str = "", limit: int = 50) -> list:
    ensure_partner_wallet_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        wheres, params = [], []
        if user_id:
            wheres.append("p.user_id=?"); params.append(user_id)
        if status:
            wheres.append("p.status=?"); params.append(status)
        where_sql = ("WHERE " + " AND ".join(wheres)) if wheres else ""
        params.append(limit)
        return conn.execute(f"""
            SELECT p.*, u.full_name, u.username
            FROM partner_payouts p
            LEFT JOIN users u ON u.user_id=p.user_id
            {where_sql}
            ORDER BY p.id DESC LIMIT ?;
        """, params).fetchall()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── لاگ اقدامات ادمین — نسخهٔ مستقل از Request برای bot.py ──────────────────
# ══════════════════════════════════════════════════════════════════════════════

def log_admin_action(admin_id, action: str, section: str = "", details: str = "") -> None:
    """ثبت اقدام ادمین در همون جدول admin_logs که admin_panel._log() ازش استفاده
    می‌کنه — برای اقداماتی که از خودِ ربات (نه پنل وب) انجام می‌شن، مثل شارژ/کسر
    دستی کیف‌پول کاربر، که قبلاً هیچ ردی در تاریخچهٔ لاگ‌های ادمین نمی‌ذاشتن.
    هیچ‌وقت exception نمی‌ده (دقیقاً مثل _log() پنل)."""
    try:
        conn = _get_connection()
        try:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS admin_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    admin_id   INTEGER,
                    admin_name TEXT,
                    action     TEXT NOT NULL,
                    section    TEXT,
                    details    TEXT,
                    ip         TEXT,
                    created_at TEXT NOT NULL DEFAULT (datetime('now','localtime'))
                );
            """)
            conn.execute("ALTER TABLE admin_logs ADD COLUMN result TEXT DEFAULT 'ok';")
        except Exception:
            pass
        conn.execute(
            "INSERT INTO admin_logs (admin_id,admin_name,action,section,details,ip,result) VALUES (?,?,?,?,?,?,?);",
            (str(admin_id), f"admin#{admin_id}", action, section, (details or "")[:500], "bot", "ok")
        )
        conn.commit()
    except Exception:
        pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


# ══════════════════════════════════════════════════════════════════════════════
# ─── دفتر یادداشت مدیران ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_admin_notes_schema():
    global _ENSURE_ADMIN_NOTES_SCHEMA_DONE
    if _ENSURE_ADMIN_NOTES_SCHEMA_DONE:
        return
    _ENSURE_ADMIN_NOTES_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_notes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                author     TEXT NOT NULL,
                text       TEXT NOT NULL,
                status     TEXT DEFAULT 'open',
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admin_note_replies (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                note_id    INTEGER NOT NULL,
                author     TEXT NOT NULL,
                text       TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_admin_notes(status: str = "") -> list:
    ensure_admin_notes_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE n.status=?" if status else ""
        params = (status,) if status else ()
        return conn.execute(f"""
            SELECT n.*,
                   (SELECT COUNT(*) FROM admin_note_replies r WHERE r.note_id=n.id) AS reply_count
            FROM admin_notes n {where}
            ORDER BY n.status='open' DESC, n.updated_at DESC;
        """, params).fetchall()
    finally:
        conn.close()


def get_admin_note(note_id: int) -> dict | None:
    ensure_admin_notes_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        n = conn.execute("SELECT * FROM admin_notes WHERE id=?;", (note_id,)).fetchone()
        if not n:
            return None
        replies = conn.execute(
            "SELECT * FROM admin_note_replies WHERE note_id=? ORDER BY id;", (note_id,)
        ).fetchall()
        return {"note": dict(n), "replies": [dict(r) for r in replies]}
    finally:
        conn.close()


def create_admin_note(author: str, text: str) -> int:
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("INSERT INTO admin_notes (author, text) VALUES (?,?);", (author, text))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def add_admin_note_reply(note_id: int, author: str, text: str):
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        conn.execute("INSERT INTO admin_note_replies (note_id,author,text) VALUES (?,?,?);",
                     (note_id, author, text))
        conn.execute("UPDATE admin_notes SET updated_at=datetime('now') WHERE id=?;", (note_id,))
        conn.commit()
    finally:
        conn.close()


def toggle_admin_note_status(note_id: int) -> str:
    ensure_admin_notes_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("SELECT status FROM admin_notes WHERE id=?;", (note_id,)).fetchone()
        new_status = "done" if (cur and cur[0] == "open") else "open"
        conn.execute("UPDATE admin_notes SET status=?,updated_at=datetime('now') WHERE id=?;",
                     (new_status, note_id))
        conn.commit()
        return new_status
    finally:
        conn.close()


def delete_admin_note(note_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM admin_note_replies WHERE note_id=?;", (note_id,))
        conn.execute("DELETE FROM admin_notes WHERE id=?;", (note_id,))
        conn.commit()
    finally:
        conn.close()


# ─── ستونهای اضافی partner_tiers ────────────────────────────────────────────

def ensure_partner_tiers_extended():
    global _ENSURE_PARTNER_TIERS_EXTENDED_DONE
    if _ENSURE_PARTNER_TIERS_EXTENDED_DONE:
        return
    ensure_partner_system_schema()  # ابتدا جدول پایه ساخته شود (قبل از set flag)
    _ENSURE_PARTNER_TIERS_EXTENDED_DONE = True
    conn = _get_connection()
    try:
        for col, default in [
            ("commission_percent", "REAL DEFAULT 0"),
            ("commission_fixed",  "INTEGER DEFAULT 0"),
            ("color",             "TEXT DEFAULT '#6B7280'"),
            ("description",       "TEXT DEFAULT ''"),
            ("photo_file_id",     "TEXT DEFAULT ''"),
            # فاز ۲: سقف و حداقل per-tier
            ("min_order_amount",  "INTEGER DEFAULT 0"),   # حداقل مبلغ خرید برای دریافت پورسانت
            ("max_payout",        "INTEGER DEFAULT 0"),   # سقف پورسانت هر خرید
            ("levelup_message",   "TEXT DEFAULT ''"),     # متن پیام تبریک ارتقا اختصاصی
            ("commission_type",   "TEXT DEFAULT 'percent'"),  # 'percent' یا 'fixed' — رادیویی
        ]:
            try:
                conn.execute(f"ALTER TABLE partner_tiers ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── اطلاعات بانکی همکار ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_partner_bank_schema():
    global _ENSURE_PARTNER_BANK_SCHEMA_DONE
    if _ENSURE_PARTNER_BANK_SCHEMA_DONE:
        return
    _ENSURE_PARTNER_BANK_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS partner_bank_info (
                user_id     INTEGER PRIMARY KEY,
                full_name   TEXT DEFAULT '',
                card_number TEXT DEFAULT '',
                iban        TEXT DEFAULT '',
                updated_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        import db_conn as _dc
        _dc.ensure_unique_constraint(conn, "partner_bank_info", ["user_id"])
        # migration: ستون آدرس + صاحب حساب
        for _mc, _md in [("address", "TEXT DEFAULT ''"), ("owner_name", "TEXT DEFAULT ''")]:
            try:
                conn.execute(f"ALTER TABLE partner_bank_info ADD COLUMN {_mc} {_md};")
                conn.commit()
            except Exception:
                pass
            pass
    finally:
        conn.close()


def get_partner_bank_info(user_id: int) -> dict | None:
    ensure_partner_bank_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_bank_info WHERE user_id=?;", (user_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def save_partner_bank_info(user_id: int, full_name: str, card_number: str, iban: str):
    ensure_partner_bank_schema()
    conn = _get_connection()
    try:
        existing = conn.execute("SELECT user_id FROM partner_bank_info WHERE user_id=?;", (user_id,)).fetchone()
        if existing:
            conn.execute("UPDATE partner_bank_info SET full_name=?,card_number=?,iban=?,updated_at=datetime('now') WHERE user_id=?;",
                         (full_name, card_number, iban, user_id))
        else:
            conn.execute("INSERT INTO partner_bank_info (user_id,full_name,card_number,iban) VALUES (?,?,?,?);",
                         (user_id, full_name, card_number, iban))
        conn.commit()
    finally:
        conn.close()


def get_partner_profile(user_id: int) -> dict:
    """پروفایل کامل همکار — نام/فروشگاه/شهر از partners + آدرس/کارت/شبا/صاحب‌حساب از
    partner_bank_info. دقیقاً همون دو منبعی که _show_partner_profile در bot.py می‌خونه،
    برای مصرف مینی‌اپ."""
    ensure_partner_bank_schema(); ensure_partner_bank_address()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        p = conn.execute("SELECT full_name, shop_name, city FROM partners WHERE tg_user_id=?;", (user_id,)).fetchone()
    finally:
        conn.close()
    bank = get_partner_bank_info(user_id)
    return {
        "name": ((p["full_name"] if p else "") or ""),
        "shop_name": ((p["shop_name"] if p else "") or ""),
        "city": ((p["city"] if p else "") or ""),
        "address": ((bank["address"] if bank else "") or ""),
        "card_number": ((bank["card_number"] if bank else "") or ""),
        "iban": ((bank["iban"] if bank else "") or ""),
        "bank_owner_name": ((bank["full_name"] if bank else "") or ""),
    }


_PARTNER_PROFILE_FIELD_MAP = {
    "name": ("partners", "full_name"),
    "shop_name": ("partners", "shop_name"),
    "city": ("partners", "city"),
    "address": ("partner_bank_info", "address"),
    "card_number": ("partner_bank_info", "card_number"),
    "iban": ("partner_bank_info", "iban"),
    "bank_owner_name": ("partner_bank_info", "full_name"),
}


def update_partner_profile_field(user_id: int, field: str, value: str):
    """ذخیرهٔ یک فیلد پروفایل همکار — دقیقاً همون منطق _pedit_save در bot.py، برای
    استفادهٔ مشترک ربات و API مینی‌اپ. `field` فقط از _PARTNER_PROFILE_FIELD_MAP
    (لیست ثابت داخلی) اجازه داره، پس نام ستون هیچ‌وقت از ورودی خام کاربر ساخته نمی‌شه."""
    if field not in _PARTNER_PROFILE_FIELD_MAP:
        raise ValueError(f"unknown partner profile field: {field}")
    table, col = _PARTNER_PROFILE_FIELD_MAP[field]
    ensure_partner_bank_schema(); ensure_partner_bank_address()
    conn = _get_connection()
    try:
        if table == "partners":
            conn.execute(f"UPDATE partners SET {col}=? WHERE tg_user_id=?;", (value, user_id))
        else:
            existing = conn.execute("SELECT user_id FROM partner_bank_info WHERE user_id=?;", (user_id,)).fetchone()
            if existing:
                conn.execute(f"UPDATE partner_bank_info SET {col}=?,updated_at=datetime('now') WHERE user_id=?;", (value, user_id))
            else:
                conn.execute(f"INSERT INTO partner_bank_info (user_id,{col}) VALUES (?,?);", (user_id, value))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── حسابداری موجودی (feed batch) ───────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_feed_batch_schema():
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS feed_batches (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id      INTEGER NOT NULL,
                purchase_price  INTEGER DEFAULT 0,
                side_cost       INTEGER DEFAULT 0,
                item_count      INTEGER DEFAULT 0,
                notes           TEXT DEFAULT '',
                created_at      TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            conn.execute("ALTER TABLE product_feed ADD COLUMN batch_id INTEGER DEFAULT NULL;")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()


def create_feed_batch(product_id: int, purchase_price: int, side_cost: int, item_count: int, notes: str = "") -> int:
    ensure_feed_batch_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO feed_batches (product_id,purchase_price,side_cost,item_count,notes) VALUES (?,?,?,?,?);",
            (product_id, purchase_price, side_cost, item_count, notes)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def link_batch_to_feed(product_id: int, batch_id: int, offset: int, count: int):
    """لینک کردن آخرین count آیتم به batch_id."""
    ensure_feed_batch_schema()
    conn = _get_connection()
    try:
        conn.execute("""
            UPDATE product_feed SET batch_id=?
            WHERE id IN (
                SELECT id FROM product_feed
                WHERE product_id=? AND batch_id IS NULL AND delivered=0
                ORDER BY id DESC LIMIT ?
            );
        """, (batch_id, product_id, count))
        conn.commit()
    finally:
        conn.close()


# ─── migration آدرس در partner_bank_info ────────────────────────────────────

def ensure_partner_bank_address():
    global _ENSURE_PARTNER_BANK_ADDRESS_DONE
    if _ENSURE_PARTNER_BANK_ADDRESS_DONE:
        return
    ensure_partner_bank_schema()  # جدول پایه partner_bank_info
    _ENSURE_PARTNER_BANK_ADDRESS_DONE = True
    conn = _get_connection()
    try:
        conn.execute("ALTER TABLE partner_bank_info ADD COLUMN address TEXT DEFAULT '';")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


# ─── تنظیمات تسویه — فیلدهای اضافی ────────────────────────────────────────

def ensure_payout_settings_extended():
    global _ENSURE_PAYOUT_SETTINGS_EXTENDED_DONE
    if _ENSURE_PAYOUT_SETTINGS_EXTENDED_DONE:
        return
    ensure_partner_wallet_schema()  # جدول پایه partner_payout_settings باید وجود داشته باشد
    _ENSURE_PAYOUT_SETTINGS_EXTENDED_DONE = True
    conn = _get_connection()
    try:
        for col, default in [
            ("review_hours",        "INTEGER DEFAULT 48"),
            ("guide_text",          "TEXT DEFAULT ''"),
            ("approval_message",    "TEXT DEFAULT ''"),
            ("rejection_message",   "TEXT DEFAULT ''"),
        ]:
            try:
                conn.execute(f"ALTER TABLE partner_payout_settings ADD COLUMN {col} {default};")
                conn.commit()
            except Exception:
                pass
    finally:
        conn.close()


def get_payout_settings_full() -> dict:
    ensure_payout_settings_extended()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM partner_payout_settings WHERE id=1;").fetchone()
        if row:
            return dict(row)
        return {
            "min_amount": 50000, "max_amount": 0, "max_per_month": 2,
            "is_active": 1, "review_hours": 48,
            "guide_text": (
                "📤 <b>شرایط و راهنمای درخواست تسویه</b>\n\n"
                "برای ثبت درخواست تسویه، موارد زیر را رعایت کنید:\n\n"
                "۱. اطلاعات حساب بانکی (شبا و نام صاحب حساب) باید ثبت شده باشد\n"
                "۲. موجودی کیف‌پول همکاری باید به حداقل تعیین‌شده رسیده باشد\n"
                "۳. پس از ثبت درخواست، تیم مالی آن را بررسی و تأیید می‌کند\n"
                "۴. پرداخت معمولاً ظرف ۴۸ ساعت کاری انجام می‌شود\n\n"
                "⚠️ درخواست‌های با اطلاعات نادرست یا مغایرت حساب رد خواهند شد."
            ), "approval_message": (
                "✅ <b>درخواست تسویه شما تأیید شد!</b>\n\n"
                "💰 مبلغ درخواستی به حساب بانکی ثبت‌شده واریز خواهد شد.\n"
                "⏰ پردازش: ۲۴ تا ۴۸ ساعت کاری\n\n"
                "ممنون از همکاری شما 🙏"
            ), "rejection_message": (
                "❌ <b>درخواست تسویه رد شد</b>\n\n"
                "درخواست تسویه شما تأیید نشد. لطفاً موارد زیر را بررسی کنید:\n"
                "• صحت اطلاعات حساب بانکی\n"
                "• کافی بودن موجودی\n\n"
                "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید 💬"
            ),
        }
    finally:
        conn.close()


def save_payout_settings_full(data: dict):
    ensure_payout_settings_extended()
    conn = _get_connection()
    try:
        conn.execute("""UPDATE partner_payout_settings
            SET min_amount=?, max_amount=?, max_per_month=?, is_active=?,
                review_hours=?, guide_text=?, approval_message=?, rejection_message=?,
                updated_at=datetime('now')
            WHERE id=1;""",
            (data.get("min_amount",50000), data.get("max_amount",0),
             data.get("max_per_month",2), data.get("is_active",1),
             data.get("review_hours",48), data.get("guide_text",""),
             data.get("approval_message",""), data.get("rejection_message","")))
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── سیستم حسابداری (Light Accounting) ──────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_accounting_schema():
    """ساخت جداول حسابداری."""
    global _ENSURE_ACCOUNTING_SCHEMA_DONE
    if _ENSURE_ACCOUNTING_SCHEMA_DONE:
        return
    _ENSURE_ACCOUNTING_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        # هزینهها
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                title       TEXT NOT NULL,
                category    TEXT DEFAULT 'سایر',
                amount      INTEGER NOT NULL DEFAULT 0,
                expense_date TEXT DEFAULT (date('now')),
                description TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        # فاز ۴: ستون‌های نوع پرداخت و طرف حساب
        for col, decl in [
            ("payment_type", "TEXT DEFAULT 'expense'"),   # expense/salary/partner_payout/other
            ("payee_name",   "TEXT DEFAULT ''"),          # نام پرسنل/همکار/گیرنده
        ]:
            try:
                conn.execute(f"ALTER TABLE expenses ADD COLUMN {col} {decl};")
            except Exception:
                pass
        # دستهبندی هزینهها
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expense_categories (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                name  TEXT UNIQUE NOT NULL
            );
        """)
        # دستههای پیشفرض — فاز ۴ گسترده‌تر
        defaults = ['تبلیغات','سرور و هاست','دامنه','حقوق پرسنل','پرداخت همکار',
                    'اینترنت','تجهیزات','مالیات','آب و برق','بازاریابی','سایر']
        for cat in defaults:
            try:
                conn.execute("INSERT OR IGNORE INTO expense_categories (name) VALUES (?);", (cat,))
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()


def get_accounting_kpis(date_from: str = "", date_to: str = "") -> dict:
    """محاسبه KPI های اصلی حسابداری.
    ⚠️ رفع‌شده (کشف‌شده روی Postgres واقعی): این تابع feed_batches رو بدون صدا
    زدن ensure_feed_batch_schema() اول کوئری می‌کرد — روی نصب تازه (جدول لیزی،
    هنوز ساخته نشده) خطا می‌گرفت. روی SQLite این خطا فقط همون یک try/except رو
    تحت تأثیر قرار می‌داد، ولی روی Postgres یک کوئری شکست‌خورده کل تراکنش رو
    poison می‌کنه — هر کوئری بعدی روی همون conn (حتی توی try/except جدا) با
    «current transaction is aborted» شکست می‌خورد. رفع: هم ensure_feed_batch_schema
    اول صدا زده می‌شه (رفع ریشه‌ای، اکثر مواقع اصلاً به except نمی‌رسه)، هم هر
    except این تابع صریحاً rollback می‌کنه (دفاع در عمق برای بقیهٔ سناریوها)."""
    ensure_feed_batch_schema()
    conn = _get_connection()
    try:
        where_order = ""
        order_params = []
        if date_from:
            where_order += " AND date(o.created_at) >= ?"
            order_params.append(date_from)
        if date_to:
            where_order += " AND date(o.created_at) <= ?"
            order_params.append(date_to)

        # فروش کل
        total_sales = conn.execute(
            f"SELECT COALESCE(SUM(price),0) FROM orders o WHERE status='active'{where_order};",
            order_params
        ).fetchone()[0]

        # فروش امروز
        today_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND date(created_at)=date('now');"
        ).fetchone()[0]

        # فروش این ماه
        month_sales = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE status='active' AND strftime('%Y-%m',created_at)=strftime('%Y-%m','now');"
        ).fetchone()[0]

        # تعداد سفارش
        total_orders = conn.execute(
            f"SELECT COUNT(*) FROM orders o WHERE status='active'{where_order};",
            order_params
        ).fetchone()[0]

        # فروش مستقیم در برابر فروش همکاری — قبلاً فقط توی صفحهٔ جداگانهٔ «گزارش مالی» بود
        direct_sales = conn.execute(
            f"SELECT COALESCE(SUM(price),0) FROM orders o WHERE status='active' AND (buyer_type!='partner' OR buyer_type IS NULL){where_order};",
            order_params
        ).fetchone()[0]
        partner_sales = conn.execute(
            f"SELECT COALESCE(SUM(price),0) FROM orders o WHERE status='active' AND buyer_type='partner'{where_order};",
            order_params
        ).fetchone()[0]

        # هزینه خرید — محصولات تحویل‌شده (با batch + بدون batch)
        try:
            # ۱) آیتم‌هایی که batch و purchase_price دارن
            batch_cost = conn.execute("""
                SELECT COALESCE(SUM(
                    CASE WHEN fb.item_count > 0
                    THEN (fb.purchase_price + CAST(fb.side_cost AS REAL)/fb.item_count)
                    ELSE fb.purchase_price END
                ), 0)
                FROM product_feed pf
                JOIN feed_batches fb ON pf.batch_id = fb.id
                WHERE pf.delivered = 1;
            """).fetchone()[0]
        except Exception:
            try: conn.rollback()
            except Exception: pass
            batch_cost = 0
        try:
            # ۲) آیتم‌هایی بدون batch (txt import) — تعداد تحویل‌شده × قیمت محصول
            no_batch_cost = conn.execute("""
                SELECT COALESCE(SUM(COALESCE(p.partner_price, p.price)), 0)
                FROM product_feed pf
                JOIN products p ON pf.product_id = p.id
                WHERE pf.delivered = 1 AND (pf.batch_id IS NULL OR pf.batch_id = 0);
            """).fetchone()[0]
        except Exception:
            try: conn.rollback()
            except Exception: pass
            no_batch_cost = 0
        total_cost = int(batch_cost) + int(no_batch_cost)

        # پورسانت پرداختی — مجموع کامل واریزهای پورسانت به کیف‌پول همکاری، هم پاداش
        # اولین خرید (process_referral_reward) هم پورسانت زنجیره‌ای هر خرید بعدی
        # (process_referral_commission). قبلاً این عدد فقط از جدول referrals محاسبه
        # می‌شد که تنها پاداش اولین خرید رو ثبت می‌کنه — پورسانت مستمر هر خرید بعدی
        # (که مستقیم به partner_transactions واریز می‌شه، نه به referrals) اصلاً لحاظ
        # نمی‌شد و «سود خالص» رو به‌طور واقعی بیشتر از واقعیت نشون می‌داد.
        try:
            commission_q = "SELECT COALESCE(SUM(amount),0) FROM partner_transactions WHERE type='credit'"
            commission_params = []
            if date_from:
                commission_q += " AND date(created_at)>=?"
                commission_params.append(date_from)
            if date_to:
                commission_q += " AND date(created_at)<=?"
                commission_params.append(date_to)
            total_commission = conn.execute(commission_q + ";", commission_params).fetchone()[0]
        except Exception:
            try: conn.rollback()
            except Exception: pass
            total_commission = 0

        # هزینههای ثبتشده
        exp_q = "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE 1=1"
        exp_params = []
        if date_from: exp_q += " AND expense_date>=?"; exp_params.append(date_from)
        if date_to:   exp_q += " AND expense_date<=?"; exp_params.append(date_to)
        total_expenses = conn.execute(exp_q + ";", exp_params).fetchone()[0]

        # تسویههای انجام شده
        try:
            payouts_done = conn.execute("SELECT COUNT(*), COALESCE(SUM(amount),0) FROM partner_payouts WHERE status='approved';").fetchone()
            payout_count = int(payouts_done[0] or 0)
            payout_total = int(payouts_done[1] or 0)
        except Exception:
            try: conn.rollback()
            except Exception: pass
            payout_count = payout_total = 0

        # موجودی انبار + ارزش
        try:
            stock_count = conn.execute("SELECT COUNT(*) FROM product_feed WHERE delivered=0;").fetchone()[0]
        except Exception:
            try: conn.rollback()
            except Exception: pass
            stock_count = 0
        try:
            stock_value = conn.execute("""
                SELECT COALESCE(SUM(p.price), 0)
                FROM product_feed pf
                JOIN products p ON pf.product_id = p.id
                WHERE pf.delivered = 0;
            """).fetchone()[0]
        except Exception:
            try: conn.rollback()
            except Exception: pass
            stock_value = 0

        gross_profit = int(total_sales or 0) - int(total_cost or 0)
        net_profit   = gross_profit - int(total_commission or 0) - int(total_expenses or 0)

        avg_profit = int(net_profit / total_orders) if total_orders else 0
        margin_pct = round((net_profit / total_sales) * 100, 1) if total_sales else 0

        return {
            "today_sales":       int(today_sales or 0),
            "month_sales":       int(month_sales or 0),
            "total_sales":       int(total_sales or 0),
            "direct_sales":      int(direct_sales or 0),
            "partner_sales":     int(partner_sales or 0),
            "total_orders":      int(total_orders or 0),
            "total_cost":        int(total_cost or 0),
            "total_commission":  int(total_commission or 0),
            "total_expenses":    int(total_expenses or 0),
            "gross_profit":      gross_profit,
            "net_profit":        net_profit,
            "payout_count":      payout_count,
            # ⚠️ رفع‌شده: قبلاً اینجا status='paid' چک می‌شد که هیچ‌وقت مقداردهی نمی‌شه
            # (process_partner_payout فقط 'approved'/'rejected' ثبت می‌کنه) — یعنی
            # «مانده صندوق» روی صفحهٔ حسابداری هیچ‌وقت واقعاً تسویه‌های پرداخت‌شده رو
            # کم نمی‌کرد. مقدار صحیح همون payout_total (status='approved') هست.
            "total_payouts":     payout_total,
            "payout_total":      payout_total,
            "stock_count":       int(stock_count or 0),
            "avg_profit":        avg_profit,
            "margin_pct":        margin_pct,
        }
    finally:
        conn.close()


def get_product_accounting(limit: int = 20) -> list:
    """گزارش حسابداری به تفکیک محصول.
    ⚠️ رفع‌شده (کشف‌شده روی Postgres واقعی): feed_batches جدول لیزیه (فقط با
    ensure_feed_batch_schema ساخته می‌شه) — این تابع بدون صداکردنش مستقیم بهش
    join می‌زد؛ روی نصب تازه با «relation does not exist» کرش می‌کرد."""
    ensure_feed_batch_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                p.id, p.title,
                COUNT(o.id)              AS sale_count,
                COALESCE(SUM(o.price),0) AS total_revenue,
                COALESCE((
                    SELECT AVG(fb.purchase_price) FROM feed_batches fb WHERE fb.product_id=p.id
                ),0)                     AS avg_cost,
                COALESCE((
                    SELECT fb.purchase_price FROM feed_batches fb WHERE fb.product_id=p.id ORDER BY fb.id DESC LIMIT 1
                ),0)                     AS last_cost,
                COALESCE((
                    SELECT COUNT(*) FROM product_feed pf WHERE pf.product_id=p.id AND pf.delivered=0
                ),0)                     AS stock
            FROM products p
            LEFT JOIN orders o ON o.title=p.title AND o.status='active'
            GROUP BY p.id
            ORDER BY total_revenue DESC
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_partner_accounting(limit: int = 20) -> list:
    """گزارش حسابداری به تفکیک همکار."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute("""
            SELECT
                u.user_id, u.full_name, u.username,
                COUNT(o.id)              AS sale_count,
                COALESCE(SUM(o.price),0) AS total_sales,
                COALESCE((
                    SELECT SUM(r.reward_amount) FROM referrals r
                    WHERE r.referrer_id=u.user_id AND r.rewarded=1
                ),0)                     AS commission_paid
            FROM users u
            JOIN partners pt ON pt.tg_user_id=u.user_id AND pt.status='approved'
            LEFT JOIN orders o ON CAST(o.user_id AS INTEGER)=u.user_id AND o.status='active' AND o.buyer_type='partner'
            GROUP BY u.user_id
            ORDER BY total_sales DESC
            LIMIT ?;
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_cashflow(date_from: str = "", date_to: str = "", limit: int = 100) -> list:
    """گردش مالی — همه رویدادهای مالی."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        where = "WHERE 1=1"
        params = []
        if date_from: where += " AND date(created_at)>=?"; params.append(date_from)
        if date_to:   where += " AND date(created_at)<=?"; params.append(date_to)
        params.append(limit)
        rows = conn.execute(f"""
            SELECT * FROM (
                SELECT created_at, 'فروش' as type, title as description,
                       price as amount, 'income' as direction
                FROM orders WHERE status='active'
                UNION ALL
                SELECT created_at, 'شارژ کیفپول' as type,
                       CAST(user_id AS TEXT) as description,
                       amount, 'income' as direction
                FROM zarinpal_transactions WHERE status='success'
                UNION ALL
                SELECT created_at, 'هزینه' as type,
                       title || ' (' || category || ')' as description,
                       amount, 'expense' as direction
                FROM expenses
                UNION ALL
                SELECT created_at, 'پورسانت' as type,
                       CAST(referrer_id AS TEXT) as description,
                       reward_amount as amount, 'expense' as direction
                FROM referrals WHERE rewarded=1
            ) {where}
            ORDER BY created_at DESC LIMIT ?;
        """, params).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── CRUD هزینهها ────────────────────────────────────────────────────────────

def get_expenses(date_from="", date_to="", category="", limit=100) -> list:
    conn = _get_connection(); conn.row_factory = sqlite3.Row
    try:
        where = "WHERE 1=1"
        params = []
        if date_from: where += " AND expense_date>=?"; params.append(date_from)
        if date_to:   where += " AND expense_date<=?"; params.append(date_to)
        if category:  where += " AND category=?"; params.append(category)
        params.append(limit)
        return [dict(r) for r in conn.execute(
            f"SELECT * FROM expenses {where} ORDER BY expense_date DESC, id DESC LIMIT ?;", params
        ).fetchall()]
    finally: conn.close()


def create_expense(title: str, category: str, amount: int,
                   expense_date: str = "", description: str = "",
                   payment_type: str = "expense", payee_name: str = "") -> int:
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO expenses (title,category,amount,expense_date,description,payment_type,payee_name) "
            "VALUES (?,?,?,?,?,?,?);",
            (title, category, amount, expense_date or datetime.utcnow().strftime('%Y-%m-%d'),
             description, payment_type, payee_name)
        )
        conn.commit(); return cur.lastrowid
    finally: conn.close()


def delete_expense(eid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM expenses WHERE id=?;", (eid,))
        conn.commit()
    finally: conn.close()


def get_expense_categories() -> list:
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT name FROM expense_categories ORDER BY id;").fetchall()
        return [r[0] for r in rows]
    finally: conn.close()


def add_expense_category(name: str):
    ensure_accounting_schema()
    conn = _get_connection()
    try:
        conn.execute("INSERT OR IGNORE INTO expense_categories (name) VALUES (?);", (name,))
        conn.commit()
    finally: conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── فاز ۱: امتیازدهی + FAQ ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def ensure_ratings_schema():
    global _ENSURE_RATINGS_SCHEMA_DONE
    if _ENSURE_RATINGS_SCHEMA_DONE:
        return
    _ENSURE_RATINGS_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment     TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(order_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def save_rating(user_id: int, order_id: int, product_id: int, rating: int, comment: str = "") -> bool:
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        # ⚠️ SELECT changes() خاص SQLite بود، روی Postgres همیشه truthy می‌شد —
        # جایگزین با cursor.rowcount (پرتابل SQLite/Postgres)
        cur = conn.execute("""INSERT OR IGNORE INTO product_ratings
            (user_id, order_id, product_id, rating, comment) VALUES (?,?,?,?,?);""",
            (user_id, order_id, product_id, rating, comment))
        changed = cur.rowcount
        conn.commit()
        return bool(changed and changed > 0)
    finally:
        conn.close()


def get_product_rating(product_id: int) -> dict:
    """میانگین امتیاز و تعداد نظرات یک محصول."""
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        row = conn.execute("""
            SELECT COUNT(*) as cnt, ROUND(AVG(rating),1) as avg
            FROM product_ratings WHERE product_id=?;
        """, (product_id,)).fetchone()
        return {"count": int(row[0] or 0), "avg": float(row[1] or 0)}
    finally:
        conn.close()


def get_product_ratings_list(product_id: int, limit: int = 20) -> list:
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("""
            SELECT pr.rating, pr.comment, pr.created_at, u.full_name
            FROM product_ratings pr
            LEFT JOIN users u ON u.user_id=pr.user_id
            WHERE pr.product_id=? ORDER BY pr.id DESC LIMIT ?;
        """, (product_id, limit)).fetchall()]
    finally:
        conn.close()


def has_rated_order(order_id: int) -> bool:
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        return conn.execute(
            "SELECT COUNT(*) FROM product_ratings WHERE order_id=?;", (order_id,)
        ).fetchone()[0] > 0
    finally:
        conn.close()


def get_all_ratings(limit: int = 200) -> list:
    """همهٔ نظرات/امتیازها برای مدیریت پنل ادمین — جدیدترین اول."""
    ensure_ratings_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("""
            SELECT pr.id, pr.rating, pr.comment, pr.created_at, pr.user_id, pr.product_id,
                   p.title AS product_title, u.full_name
            FROM product_ratings pr
            LEFT JOIN products p ON p.id = pr.product_id
            LEFT JOIN users u ON u.user_id = pr.user_id
            ORDER BY pr.id DESC LIMIT ?;
        """, (limit,)).fetchall()]
    finally:
        conn.close()


def delete_rating(rating_id: int) -> None:
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM product_ratings WHERE id=?;", (rating_id,))
        conn.commit()
    finally:
        conn.close()


# ─── سرزدن روزانه (پاداش کوچک برای باز کردن اپ هر روز) ────────────────────────

_ENSURE_CHECKIN_SCHEMA_DONE = False

def ensure_checkin_schema():
    global _ENSURE_CHECKIN_SCHEMA_DONE
    if _ENSURE_CHECKIN_SCHEMA_DONE:
        return
    _ENSURE_CHECKIN_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_checkins (
                user_id      INTEGER PRIMARY KEY,
                last_date    TEXT NOT NULL,
                streak       INTEGER NOT NULL DEFAULT 0,
                total_claims INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_checkin_status(user_id: int) -> dict:
    """وضعیت سرزدن روزانه — available یعنی امروز هنوز پاداش گرفته نشده."""
    ensure_checkin_schema()
    from datetime import date as _d
    today = _d.today().isoformat()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT last_date, streak FROM daily_checkins WHERE user_id=?;", (user_id,)
        ).fetchone()
        if not row:
            return {"available": True, "streak": 0}
        return {"available": row["last_date"] != today, "streak": int(row["streak"] or 0)}
    finally:
        conn.close()


def claim_daily_checkin(user_id: int, reward: int) -> dict:
    """اتمیک: اگه امروز هنوز پاداش نگرفته، کیف‌پول رو شارژ می‌کنه و streak رو به‌روز می‌کنه.
    برمی‌گردونه: {claimed, streak, reward}."""
    ensure_checkin_schema()
    from datetime import date as _d, timedelta as _td2
    today = _d.today()
    today_s = today.isoformat()
    yesterday_s = (today - _td2(days=1)).isoformat()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        row = cur.execute(
            f"SELECT last_date, streak FROM daily_checkins WHERE user_id=? {_row_lock_suffix()};", (user_id,)
        ).fetchone()
        if row and row["last_date"] == today_s:
            conn.rollback()
            return {"claimed": False, "streak": int(row["streak"] or 0), "reward": 0}
        new_streak = (int(row["streak"] or 0) + 1) if (row and row["last_date"] == yesterday_s) else 1
        if row:
            cur.execute(
                "UPDATE daily_checkins SET last_date=?, streak=?, total_claims=total_claims+1 WHERE user_id=?;",
                (today_s, new_streak, user_id),
            )
        else:
            cur.execute(
                "INSERT INTO daily_checkins (user_id, last_date, streak, total_claims) VALUES (?,?,?,1);",
                (user_id, today_s, new_streak),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
    add_wallet_balance(user_id, reward)
    return {"claimed": True, "streak": new_streak, "reward": reward}


# ─── علاقه‌مندی‌ها (Wishlist) ──────────────────────────────────────────────────

_ENSURE_FAVORITES_SCHEMA_DONE = False

def ensure_favorites_schema():
    global _ENSURE_FAVORITES_SCHEMA_DONE
    if _ENSURE_FAVORITES_SCHEMA_DONE:
        return
    _ENSURE_FAVORITES_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS favorites (
                user_id    INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                PRIMARY KEY (user_id, product_id)
            );
        """)
        conn.commit()
    finally:
        conn.close()


def add_favorite(user_id: int, product_id: int) -> None:
    ensure_favorites_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO favorites (user_id, product_id, created_at) VALUES (?,?,datetime('now'));",
            (user_id, product_id),
        )
        conn.commit()
    finally:
        conn.close()


def remove_favorite(user_id: int, product_id: int) -> None:
    ensure_favorites_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM favorites WHERE user_id=? AND product_id=?;", (user_id, product_id))
        conn.commit()
    finally:
        conn.close()


def get_favorite_ids(user_id: int) -> set:
    ensure_favorites_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT product_id FROM favorites WHERE user_id=?;", (user_id,)).fetchall()
        return {int(r[0]) for r in rows}
    finally:
        conn.close()


def is_favorite(user_id: int, product_id: int) -> bool:
    ensure_favorites_schema()
    conn = _get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM favorites WHERE user_id=? AND product_id=?;", (user_id, product_id)
        ).fetchone() is not None
    finally:
        conn.close()


def get_product_favoriters(product_id: int) -> list:
    """کاربرانی که این محصول رو به علاقه‌مندی اضافه کردن — برای اطلاع‌رسانی موجود شدن/فروش فوری."""
    ensure_favorites_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT user_id FROM favorites WHERE product_id=?;", (product_id,)).fetchall()
        return [int(r[0]) for r in rows]
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── گردونهٔ شانس (Wheel of Fortune) — سیستم پاداش عمومی مینی‌اپ ──────────────
# ══════════════════════════════════════════════════════════════════════════════
# معماری: wheel_campaigns (کمپین‌ها، فقط یکی هم‌زمان فعال) → wheel_prizes (جوایز
# هر کمپین، کاملاً از پنل قابل‌مدیریت، بدون هیچ عدد/متن هاردکد) → wheel_spins
# (هم لاگ کامل تاریخچه هم تنها منبع شمارش محدودیت روزانه — یک جدول، دو مصرف).
# جایزهٔ نوع کیف‌پول از طریق add_wallet_balance موجود صادر می‌شه؛ جایزهٔ نوع کد
# تخفیف از طریق issue_personal_discount_code (پایین‌تر) که موتور discount_codes
# موجود رو گسترش می‌ده، نه یه سیستم موازی. انتخاب جایزه/منطق اتمیک در core/wheel.py.

_ENSURE_WHEEL_SCHEMA_DONE = False

WHEEL_PRIZE_TYPES = ("wallet_credit", "discount_percent", "discount_fixed", "extra_spin", "no_win", "physical_gift")

_WHEEL_SETTINGS_DEFAULTS = {
    "enabled": 0,
    "title": "🎡 چرخ‌گردون شانس",
    "description": "هر روز یک شانس رایگان برای بردن جایزه!",
    "banner_url": "",
    "primary_color": "#6366F1",
    "theme": "default",
    "daily_spin_limit": 1,
    "reset_hour": 0,
    "animation_enabled": 1,
    "animation_duration_ms": 4200,
    "result_display_duration_ms": 3500,
    "sound_enabled": 1,
    "haptic_enabled": 1,
    "show_odds": 0,
}


def ensure_wheel_schema():
    global _ENSURE_WHEEL_SCHEMA_DONE
    if _ENSURE_WHEEL_SCHEMA_DONE:
        return
    _ENSURE_WHEEL_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wheel_campaigns (
                id               INTEGER PRIMARY KEY AUTOINCREMENT,
                title            TEXT NOT NULL,
                starts_at        TEXT,
                ends_at          TEXT,
                active           INTEGER NOT NULL DEFAULT 0,
                daily_spin_limit INTEGER,
                theme_json       TEXT NOT NULL DEFAULT '{}',
                sort_order       INTEGER NOT NULL DEFAULT 0,
                created_at       TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wheel_prizes (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                campaign_id       INTEGER NOT NULL,
                title             TEXT NOT NULL,
                icon              TEXT NOT NULL DEFAULT '🎁',
                color             TEXT NOT NULL DEFAULT '#6366F1',
                prize_type        TEXT NOT NULL DEFAULT 'no_win',
                value             INTEGER NOT NULL DEFAULT 0,
                max_discount_value INTEGER NOT NULL DEFAULT 0,
                weight            REAL NOT NULL DEFAULT 1,
                total_limit       INTEGER NOT NULL DEFAULT 0,
                daily_limit       INTEGER NOT NULL DEFAULT 0,
                issued_count      INTEGER NOT NULL DEFAULT 0,
                validity_hours    INTEGER NOT NULL DEFAULT 0,
                active            INTEGER NOT NULL DEFAULT 1,
                sort_order        INTEGER NOT NULL DEFAULT 0,
                description       TEXT NOT NULL DEFAULT '',
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wheel_spins (
                id                INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id           INTEGER NOT NULL,
                campaign_id       INTEGER,
                prize_id          INTEGER,
                prize_type        TEXT NOT NULL DEFAULT '',
                prize_title       TEXT NOT NULL DEFAULT '',
                amount            INTEGER NOT NULL DEFAULT 0,
                discount_code     TEXT NOT NULL DEFAULT '',
                discount_code_id  INTEGER,
                status            TEXT NOT NULL DEFAULT 'issued',
                ip                TEXT NOT NULL DEFAULT '',
                device_fingerprint TEXT NOT NULL DEFAULT '',
                session_id        TEXT NOT NULL DEFAULT '',
                created_at        TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        # شمارندهٔ روزانهٔ اتمیک — تنها راه امن جلوگیری از دبل‌اسپین هم‌زمان (به‌جای
        # COUNT(*) روی wheel_spins که یه مجموعه‌ست و قفل‌پذیر نیست، دقیقاً الگوی
        # daily_checkins: یک ردیف per user+day که با SELECT...FOR UPDATE قفل می‌شه).
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wheel_daily_usage (
                user_id     INTEGER NOT NULL,
                campaign_id INTEGER NOT NULL,
                usage_date  TEXT NOT NULL,
                spins_used  INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (user_id, campaign_id, usage_date)
            );
        """)
        for _name, _target in [
            ("idx_wheel_prizes_campaign",   "wheel_prizes(campaign_id)"),
            ("idx_wheel_spins_user",        "wheel_spins(user_id, created_at)"),
            ("idx_wheel_spins_prize",       "wheel_spins(prize_id)"),
            ("idx_wheel_spins_campaign",    "wheel_spins(campaign_id, created_at)"),
        ]:
            try:
                conn.execute(f"CREATE INDEX IF NOT EXISTS {_name} ON {_target};")
            except Exception:
                pass
        conn.commit()

        # سید اولیه — فقط اگه هیچ کمپینی وجود نداره (نصب تازه)؛ صرفاً داده (مثل seed
        # iv_coefficients)، نه منطق هاردکد — همه‌چیز بعدش از پنل قابل ویرایش/حذفه.
        row = conn.execute("SELECT COUNT(*) c FROM wheel_campaigns;").fetchone()
        if row and row["c"] == 0:
            cur = conn.execute(
                "INSERT INTO wheel_campaigns (title, active, sort_order) VALUES (?,1,0);",
                ("کمپین پیش‌فرض",)
            )
            camp_id = cur.lastrowid
            defaults = [
                # title, icon, color, ptype, value, validity_hours, weight, description
                ("۵ هزار تومان جایزه", "💵", "#22C55E", "wallet_credit", 5000, 0, 1, "شانس دوباره امتحان کن!"),
                ("۱۰ هزار تومان جایزه", "💰", "#16A34A", "wallet_credit", 10000, 0, 0.5, ""),
                ("۱۰٪ تخفیف خرید بعدی", "🏷", "#F59E0B", "discount_percent", 10, 24, 1, "روی خرید بعدیت اعمال می‌شه"),
                ("۲۰٪ تخفیف خرید بعدی", "🎫", "#EA580C", "discount_percent", 20, 24, 0.3, ""),
                ("یک چرخش دیگه!", "🔄", "#6366F1", "extra_spin", 1, 0, 1.5, ""),
                ("این بار شانس نیاوردی", "😅", "#6B7280", "no_win", 0, 0, 3, "فردا دوباره امتحان کن"),
            ]
            for title, icon, color, ptype, value, val_hours, weight, desc in defaults:
                conn.execute(
                    "INSERT INTO wheel_prizes (campaign_id, title, icon, color, prize_type, value, "
                    "validity_hours, weight, description) VALUES (?,?,?,?,?,?,?,?,?);",
                    (camp_id, title, icon, color, ptype, value, val_hours, weight, desc)
                )
            conn.commit()
    finally:
        conn.close()


def get_wheel_settings() -> dict:
    return get_cfg_json("WHEEL_SETTINGS", _WHEEL_SETTINGS_DEFAULTS)


def save_wheel_settings(values: dict) -> None:
    merged = dict(_WHEEL_SETTINGS_DEFAULTS)
    merged.update(get_wheel_settings())
    merged.update({k: v for k, v in values.items() if k in _WHEEL_SETTINGS_DEFAULTS})
    set_cfg("WHEEL_SETTINGS", json.dumps(merged, ensure_ascii=False))


# ─── کمپین‌ها ──────────────────────────────────────────────────────────────

def list_wheel_campaigns() -> list[dict]:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM wheel_campaigns ORDER BY sort_order ASC, id DESC;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wheel_campaign(campaign_id: int) -> dict | None:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM wheel_campaigns WHERE id=?;", (campaign_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def get_active_wheel_campaign() -> dict | None:
    """کمپین فعال فعلی — طبق «همیشه فقط یکی» (اجرا در set_active_wheel_campaign)."""
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        now = datetime.utcnow().isoformat()
        row = conn.execute(
            "SELECT * FROM wheel_campaigns WHERE active=1 "
            "AND (starts_at IS NULL OR starts_at<=?) AND (ends_at IS NULL OR ends_at>=?) "
            "ORDER BY id DESC LIMIT 1;", (now, now)
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_wheel_campaign(title: str, starts_at: str = None, ends_at: str = None,
                           daily_spin_limit: int = None, theme_json: str = "{}", sort_order: int = 0) -> int:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO wheel_campaigns (title, starts_at, ends_at, daily_spin_limit, theme_json, sort_order) "
            "VALUES (?,?,?,?,?,?);",
            (title.strip(), starts_at or None, ends_at or None, daily_spin_limit, theme_json or "{}", sort_order)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_wheel_campaign(campaign_id: int, **fields) -> None:
    ensure_wheel_schema()
    allowed = {"title", "starts_at", "ends_at", "daily_spin_limit", "theme_json", "sort_order"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _get_connection()
    try:
        conn.execute(f"UPDATE wheel_campaigns SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
                     [fields[c] for c in cols] + [campaign_id])
        conn.commit()
    finally:
        conn.close()


def set_active_wheel_campaign(campaign_id: int) -> None:
    """اتمیک: همه رو غیرفعال می‌کنه، بعد فقط همینو فعال — تضمین «همیشه فقط یک کمپین فعال»
    در سطح دیتابیس، نه با تکیه به انضباط ادمین."""
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE wheel_campaigns SET active=0;")
        conn.execute("UPDATE wheel_campaigns SET active=1 WHERE id=?;", (campaign_id,))
        conn.commit()
    finally:
        conn.close()


def deactivate_all_wheel_campaigns() -> None:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE wheel_campaigns SET active=0;")
        conn.commit()
    finally:
        conn.close()


def delete_wheel_campaign(campaign_id: int) -> None:
    """کسکید — جوایز همون کمپین هم حذف می‌شن؛ wheel_spins دست‌نخورده می‌مونه (خودش
    prize_title/prize_type رو denormalize کرده، دقیقاً مثل رفتار delete_model در
    iphone_valuation — تاریخچه یتیم می‌مونه ولی دقیق و خوانا باقی می‌مونه)."""
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM wheel_prizes WHERE campaign_id=?;", (campaign_id,))
        conn.execute("DELETE FROM wheel_campaigns WHERE id=?;", (campaign_id,))
        conn.commit()
    finally:
        conn.close()


# ─── جوایز ─────────────────────────────────────────────────────────────────

def list_wheel_prizes(campaign_id: int, active_only: bool = False) -> list[dict]:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        q = "SELECT * FROM wheel_prizes WHERE campaign_id=?"
        if active_only:
            q += " AND active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, (campaign_id,)).fetchall()]
    finally:
        conn.close()


def get_wheel_prize(prize_id: int) -> dict | None:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        row = conn.execute("SELECT * FROM wheel_prizes WHERE id=?;", (prize_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_wheel_prize(campaign_id: int, title: str, prize_type: str, **fields) -> int:
    if prize_type not in WHEEL_PRIZE_TYPES:
        raise ValueError(f"نوع جایزهٔ نامعتبر: {prize_type}")
    ensure_wheel_schema()
    allowed = {"icon", "color", "value", "max_discount_value", "weight", "total_limit",
               "daily_limit", "validity_hours", "active", "sort_order", "description"}
    cols = ["campaign_id", "title", "prize_type"] + [k for k in fields if k in allowed]
    vals = [campaign_id, title.strip(), prize_type] + [fields[k] for k in fields if k in allowed]
    conn = _get_connection()
    try:
        cur = conn.execute(
            f"INSERT INTO wheel_prizes ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))});", vals)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_wheel_prize(prize_id: int, **fields) -> None:
    ensure_wheel_schema()
    allowed = {"title", "icon", "color", "prize_type", "value", "max_discount_value", "weight",
               "total_limit", "daily_limit", "validity_hours", "active", "sort_order", "description"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    if "prize_type" in fields and fields["prize_type"] not in WHEEL_PRIZE_TYPES:
        raise ValueError(f"نوع جایزهٔ نامعتبر: {fields['prize_type']}")
    conn = _get_connection()
    try:
        conn.execute(f"UPDATE wheel_prizes SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
                     [fields[c] for c in cols] + [prize_id])
        conn.commit()
    finally:
        conn.close()


def delete_wheel_prize(prize_id: int) -> None:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM wheel_prizes WHERE id=?;", (prize_id,))
        conn.commit()
    finally:
        conn.close()


def try_claim_wheel_prize_slot(prize_id: int) -> bool:
    """افزایش اتمیک issued_count فقط اگه هنوز به total_limit نرسیده — دقیقاً الگوی
    UPDATE شرطی+rowcount در claim_next_feed_item (بخش ۵۱ سند)، برای محدودیت
    عمری/سخت هر جایزه. اگه total_limit=0 (نامحدود)، همیشه موفقه."""
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            "UPDATE wheel_prizes SET issued_count=issued_count+1 "
            "WHERE id=? AND (total_limit=0 OR issued_count<total_limit);",
            (prize_id,)
        )
        ok = cur.rowcount > 0
        conn.commit()
        return ok
    finally:
        conn.close()


def count_wheel_prize_issued_today(prize_id: int) -> int:
    """شمارش نرم (best-effort) برای اعمال daily_limit هر جایزه — بر خلاف total_limit
    (که با شمارندهٔ اتمیک سخت‌گیرانه‌ست)، این یه محدودیت روزانهٔ نرم‌تره؛ در بار
    همزمان خیلی سنگین ممکنه به‌ندرت یکی-دو واحد از سقف رد بشه — مستندشده، پذیرفته‌شده."""
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT COUNT(*) c FROM wheel_spins WHERE prize_id=? AND created_at>=?;",
            (prize_id, (datetime.utcnow().date()).isoformat())
        ).fetchone()
        return int(row["c"] or 0) if row else 0
    finally:
        conn.close()


# ─── مصرف روزانه (قفل اتمیک ضدتقلب) ────────────────────────────────────────

def try_consume_wheel_spin(user_id: int, campaign_id: int, usage_date: str, daily_limit: int) -> dict:
    """اتمیک: اگه سقف چرخش امروز پر نشده، یک واحد مصرف می‌کنه و True برمی‌گردونه.
    دقیقاً الگوی claim_daily_checkin (بخش ۵۱ سند) — BEGIN + قفل ردیف + آپدیت/درج
    داخل همون تراکنش، تا دو چرخش هم‌زمان نتونن هر دو رد شن."""
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        cur = conn.cursor()
        cur.execute("BEGIN IMMEDIATE;")
        row = cur.execute(
            f"SELECT spins_used FROM wheel_daily_usage WHERE user_id=? AND campaign_id=? AND usage_date=? "
            f"{_row_lock_suffix()};", (user_id, campaign_id, usage_date)
        ).fetchone()
        used = int(row["spins_used"]) if row else 0
        if daily_limit > 0 and used >= daily_limit:
            conn.rollback()
            return {"ok": False, "remaining": 0}
        if row:
            cur.execute(
                "UPDATE wheel_daily_usage SET spins_used=spins_used+1 "
                "WHERE user_id=? AND campaign_id=? AND usage_date=?;",
                (user_id, campaign_id, usage_date)
            )
        else:
            cur.execute(
                "INSERT INTO wheel_daily_usage (user_id, campaign_id, usage_date, spins_used) VALUES (?,?,?,1);",
                (user_id, campaign_id, usage_date)
            )
        conn.commit()
        remaining = (daily_limit - used - 1) if daily_limit > 0 else -1
        return {"ok": True, "remaining": remaining}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def get_wheel_spins_remaining_today(user_id: int, campaign_id: int, usage_date: str, daily_limit: int) -> int:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT spins_used FROM wheel_daily_usage WHERE user_id=? AND campaign_id=? AND usage_date=?;",
            (user_id, campaign_id, usage_date)
        ).fetchone()
        used = int(row["spins_used"]) if row else 0
        if daily_limit <= 0:
            return -1
        return max(0, daily_limit - used)
    finally:
        conn.close()


def grant_extra_wheel_spins(user_id: int, campaign_id: int, usage_date: str, count: int) -> None:
    """جایزهٔ نوع «چرخش اضافه» — مصرف امروز رو (حداکثر تا صفر) کم می‌کنه تا کاربر
    بدون نیاز به فردا شدن، بلافاصله بتونه دوباره بچرخونه."""
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        # ⚠️ MAX(a,b) اسکالر دوآرگومانی خاص SQLite است؛ روی Postgres MAX فقط
        # aggregate است (معادل اسکالرش GREATEST). به‌جای دوتا کوئری متفاوت،
        # CASE...WHEN پرتابل روی هر دو دیالوگ استفاده شد.
        conn.execute(
            "UPDATE wheel_daily_usage SET spins_used=CASE WHEN spins_used > ? THEN spins_used-? ELSE 0 END "
            "WHERE user_id=? AND campaign_id=? AND usage_date=?;",
            (int(count or 0), int(count or 0), user_id, campaign_id, usage_date)
        )
        conn.commit()
    finally:
        conn.close()


def insert_wheel_spin(**fields) -> int:
    ensure_wheel_schema()
    allowed = {"user_id", "campaign_id", "prize_id", "prize_type", "prize_title", "amount",
               "discount_code", "discount_code_id", "status", "ip", "device_fingerprint", "session_id"}
    cols = [k for k in fields if k in allowed]
    conn = _get_connection()
    try:
        cur = conn.execute(
            f"INSERT INTO wheel_spins ({', '.join(cols)}) VALUES ({', '.join('?'*len(cols))});",
            [fields[c] for c in cols]
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ─── تاریخچه/آمار (پنل ادمین) ───────────────────────────────────────────────

def list_wheel_spins(user_q: str = "", prize_type: str = "", campaign_id: int = None,
                      date_from: str = "", date_to: str = "", limit: int = 50, offset: int = 0) -> list[dict]:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        where, params = [], []
        if user_q:
            where.append(
                "(CAST(s.user_id AS TEXT) LIKE ? OR LOWER(COALESCE(u.username,'')) LIKE LOWER(?) "
                "OR LOWER(COALESCE(u.full_name,'')) LIKE LOWER(?))"
            )
            like = f"%{user_q}%"
            params += [like, like, like]
        if prize_type:
            where.append("s.prize_type=?")
            params.append(prize_type)
        if campaign_id:
            where.append("s.campaign_id=?")
            params.append(campaign_id)
        if date_from:
            where.append("s.created_at>=?")
            params.append(date_from)
        if date_to:
            where.append("s.created_at<=?")
            params.append(date_to)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT s.*, COALESCE(u.username,'') AS username, COALESCE(u.full_name,'') AS full_name "
            f"FROM wheel_spins s LEFT JOIN users u ON u.user_id=s.user_id {w} "
            f"ORDER BY s.id DESC LIMIT ? OFFSET ?;", (*params, limit, offset)
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_wheel_stats(date_from: str = "", date_to: str = "") -> dict:
    ensure_wheel_schema()
    conn = _get_connection()
    try:
        where, params = [], []
        if date_from:
            where.append("created_at>=?")
            params.append(date_from)
        if date_to:
            where.append("created_at<=?")
            params.append(date_to)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        today = datetime.utcnow().date().isoformat()
        spins_today = conn.execute(
            "SELECT COUNT(*) c FROM wheel_spins WHERE created_at>=?;", (today,)
        ).fetchone()["c"]
        unique_users = conn.execute(
            f"SELECT COUNT(DISTINCT user_id) c FROM wheel_spins {w};", params
        ).fetchone()["c"]
        total_spins = conn.execute(f"SELECT COUNT(*) c FROM wheel_spins {w};", params).fetchone()["c"]
        no_win = conn.execute(
            f"SELECT COUNT(*) c FROM wheel_spins {w}{' AND ' if w else 'WHERE '}prize_type='no_win';", params
        ).fetchone()["c"]
        win_rate = round(100 * (1 - (no_win / total_spins)), 1) if total_spins else 0
        wallet_paid = conn.execute(
            f"SELECT COALESCE(SUM(amount),0) c FROM wheel_spins {w}{' AND ' if w else 'WHERE '}prize_type='wallet_credit';",
            params
        ).fetchone()["c"]
        discount_issued = conn.execute(
            f"SELECT COUNT(*) c FROM wheel_spins {w}{' AND ' if w else 'WHERE '}"
            f"prize_type IN ('discount_percent','discount_fixed');", params
        ).fetchone()["c"]
        discount_used = conn.execute(
            f"SELECT COUNT(*) c FROM wheel_spins {w}{' AND ' if w else 'WHERE '}"
            f"prize_type IN ('discount_percent','discount_fixed') AND status='used';", params
        ).fetchone()["c"]
        discount_rate = round(100 * discount_used / discount_issued, 1) if discount_issued else 0
        top_prizes = conn.execute(
            f"SELECT prize_title, COUNT(*) c FROM wheel_spins {w} GROUP BY prize_title "
            f"ORDER BY c DESC LIMIT 5;", params
        ).fetchall()
        daily = conn.execute(
            "SELECT DATE(created_at) d, COUNT(*) c FROM wheel_spins "
            "WHERE created_at>=DATE('now','-30 day') GROUP BY DATE(created_at) ORDER BY d ASC;"
        ).fetchall()
        return {
            "spins_today": int(spins_today or 0),
            "unique_users": int(unique_users or 0),
            "total_spins": int(total_spins or 0),
            "win_rate": win_rate,
            "wallet_paid": int(wallet_paid or 0),
            "discount_issued": int(discount_issued or 0),
            "discount_used": int(discount_used or 0),
            "discount_rate": discount_rate,
            "top_prizes": [dict(r) for r in top_prizes],
            "daily": [dict(r) for r in daily],
        }
    finally:
        conn.close()


# ─── اعلان‌های مینی‌اپ (تاریخچه، مکمل پیام تلگرام) ─────────────────────────────

_ENSURE_NOTIFICATIONS_SCHEMA_DONE = False

def ensure_notifications_schema():
    global _ENSURE_NOTIFICATIONS_SCHEMA_DONE
    if _ENSURE_NOTIFICATIONS_SCHEMA_DONE:
        return
    _ENSURE_NOTIFICATIONS_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_notifications (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id    INTEGER NOT NULL,
                icon       TEXT DEFAULT '🔔',
                title      TEXT NOT NULL,
                body       TEXT DEFAULT '',
                is_read    INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def add_notification(user_id: int, title: str, body: str = "", icon: str = "🔔") -> None:
    ensure_notifications_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO user_notifications (user_id, icon, title, body) VALUES (?,?,?,?);",
            (user_id, icon, title, body),
        )
        conn.commit()
    finally:
        conn.close()


def get_notifications(user_id: int, limit: int = 30) -> list:
    ensure_notifications_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT id, icon, title, body, is_read, created_at FROM user_notifications "
            "WHERE user_id=? ORDER BY id DESC LIMIT ?;", (user_id, limit)
        ).fetchall()]
    finally:
        conn.close()


def has_unread_notifications(user_id: int) -> bool:
    ensure_notifications_schema()
    conn = _get_connection()
    try:
        return conn.execute(
            "SELECT 1 FROM user_notifications WHERE user_id=? AND is_read=0 LIMIT 1;", (user_id,)
        ).fetchone() is not None
    finally:
        conn.close()


def mark_notifications_read(user_id: int) -> None:
    ensure_notifications_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE user_notifications SET is_read=1 WHERE user_id=? AND is_read=0;", (user_id,))
        conn.commit()
    finally:
        conn.close()


# ─── FAQ ─────────────────────────────────────────────────────────────────────

def ensure_faq_schema():
    global _ENSURE_FAQ_SCHEMA_DONE
    if _ENSURE_FAQ_SCHEMA_DONE:
        return
    _ENSURE_FAQ_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_faqs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id  INTEGER NOT NULL,
                question    TEXT NOT NULL,
                answer      TEXT NOT NULL,
                sort_order  INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
    finally:
        conn.close()


def get_product_faqs(product_id: int) -> list:
    ensure_faq_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM product_faqs WHERE product_id=? ORDER BY sort_order, id;",
            (product_id,)
        ).fetchall()]
    finally:
        conn.close()


def add_product_faq(product_id: int, question: str, answer: str) -> int:
    ensure_faq_schema()
    conn = _get_connection()
    try:
        mx = conn.execute(
            "SELECT COALESCE(MAX(sort_order),0)+1 FROM product_faqs WHERE product_id=?;",
            (product_id,)
        ).fetchone()[0]
        cur = conn.execute(
            "INSERT INTO product_faqs (product_id,question,answer,sort_order) VALUES (?,?,?,?);",
            (product_id, question, answer, mx)
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_product_faq(faq_id: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM product_faqs WHERE id=?;", (faq_id,))
        conn.commit()
    finally:
        conn.close()


# ─── Maintenance Mode ─────────────────────────────────────────────────────────

_MAINT_CACHE = {"t": 0.0, "v": False}

def get_maintenance_mode() -> bool:
    import time as _t
    now = _t.time()
    if now - _MAINT_CACHE["t"] < 10:
        return _MAINT_CACHE["v"]
    _MAINT_CACHE["t"] = now
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS bot_config
            (key TEXT PRIMARY KEY, value TEXT);""")
        row = conn.execute("SELECT value FROM bot_config WHERE key='maintenance';").fetchone()
        _MAINT_CACHE["v"] = bool(row and row[0] == "1")
        return _MAINT_CACHE["v"]
    except Exception:
        return False
    finally:
        conn.close()


def set_maintenance_mode(enabled: bool):
    _MAINT_CACHE["t"] = 0.0
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS bot_config
            (key TEXT PRIMARY KEY, value TEXT);""")
        import db_conn as _dc
        _dc.ensure_unique_constraint(conn, "bot_config", ["key"])
        # ⚠️ INSERT OR REPLACE (خاص SQLite) به ON CONFLICT تبدیل شد — پرتابل بین
        # SQLite/Postgres، بدون نیاز به ترجمهٔ db_dialect (بخش پاک‌سازی SQLite سند)
        conn.execute(
            "INSERT INTO bot_config (key,value) VALUES ('maintenance',?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            ("1" if enabled else "0",))
        conn.commit()
    finally:
        conn.close()


# ─── رسیدهای کارتبهکارت ────────────────────────────────────────────────────

def ensure_card_receipts_schema():
    global _ENSURE_CARD_RECEIPTS_SCHEMA_DONE
    if _ENSURE_CARD_RECEIPTS_SCHEMA_DONE:
        return
    _ENSURE_CARD_RECEIPTS_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS card_receipts (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id     INTEGER NOT NULL,
            amount      INTEGER NOT NULL,
            file_id     TEXT NOT NULL,
            status      TEXT DEFAULT 'pending',
            admin_note  TEXT DEFAULT '',
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now'))
        );""")
        conn.commit()
    finally:
        conn.close()
    try:
        ensure_indexes()
    except Exception:
        pass


def save_card_receipt(user_id: int, amount: int, file_id: str) -> int:
    ensure_card_receipts_schema()
    conn = _get_connection()
    try:
        from db_conn import is_postgres as _is_pg
        if _is_pg():
            # Postgres: lastrowid کار نمی‌کند — باید RETURNING id استفاده شود
            cur = conn.execute(
                "INSERT INTO card_receipts (user_id,amount,file_id) VALUES (?,?,?) RETURNING id;",
                (user_id, amount, file_id))
            row = cur.fetchone()
            conn.commit()
            if row is None:
                return 0
            return int(row["id"] if hasattr(row, "keys") else row[0])
        cur = conn.execute(
            "INSERT INTO card_receipts (user_id,amount,file_id) VALUES (?,?,?);",
            (user_id, amount, file_id))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def get_card_receipts(status: str = "pending") -> list:
    ensure_card_receipts_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        if status:
            rows = conn.execute("""
                SELECT r.*, u.full_name, u.username
                FROM card_receipts r
                LEFT JOIN users u ON u.user_id=r.user_id
                WHERE r.status=? ORDER BY r.id DESC LIMIT 100;
            """, (status,)).fetchall()
        else:
            rows = conn.execute("""
                SELECT r.*, u.full_name, u.username
                FROM card_receipts r
                LEFT JOIN users u ON u.user_id=r.user_id
                ORDER BY r.id DESC LIMIT 100;
            """).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def count_card_receipts(status: str = "pending") -> int:
    """معادل سبک get_card_receipts فقط برای شمارش (بدون JOIN/fetch کامل ردیف‌ها) —
    برای badgeهایی که فقط تعداد لازم دارن، نه خودِ داده."""
    ensure_card_receipts_schema()
    conn = _get_connection()
    try:
        if status:
            n = conn.execute("SELECT COUNT(*) FROM card_receipts WHERE status=?;", (status,)).fetchone()[0]
        else:
            n = conn.execute("SELECT COUNT(*) FROM card_receipts;").fetchone()[0]
        return int(n or 0)
    finally:
        conn.close()


def update_card_receipt(rid: int, status: str, note: str = "", amount: int = None):
    conn = _get_connection()
    try:
        if amount is not None:
            conn.execute("""UPDATE card_receipts SET status=?,admin_note=?,amount=?,updated_at=datetime('now')
                WHERE id=?;""", (status, note, amount, rid))
        else:
            conn.execute("""UPDATE card_receipts SET status=?,admin_note=?,updated_at=datetime('now')
                WHERE id=?;""", (status, note, rid))
        conn.commit()
    finally:
        conn.close()


# ─── آرشیو و حذف تیکتها ──────────────────────────────────────────────────────

def ensure_ticket_archive_schema():
    # روی نصب کاملاً تازه، اگه ادمین قبل از اولین تعامل بات با تیکت‌ها وارد
    # پنل بشه، جدول tickets هنوز از ticket_ensure_schema() (فقط از bot.py صدا
    # زده می‌شه) ساخته نشده — این‌جا هم صداش می‌زنیم (idempotent، CREATE TABLE
    # IF NOT EXISTS) تا PRAGMA/ALTER زیر هیچ‌وقت روی جدول ناموجود شکست نخوره.
    ticket_ensure_schema()
    conn = _get_connection()
    try:
        cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets);").fetchall()]
        if "archived" not in cols:
            conn.execute("ALTER TABLE tickets ADD COLUMN archived INTEGER DEFAULT 0;")
        conn.commit()
    finally:
        conn.close()


def archive_ticket(tid: int):
    ensure_ticket_archive_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tickets SET archived=1 WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


def unarchive_ticket(tid: int):
    ensure_ticket_archive_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tickets SET archived=0 WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


def delete_ticket(tid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM ticket_messages WHERE ticket_id=?;", (tid,))
        conn.execute("DELETE FROM tickets WHERE id=?;", (tid,))
        conn.commit()
    finally:
        conn.close()


# ─── حذف رسیدهای کارتبهکارت ─────────────────────────────────────────────────

def delete_card_receipt(rid: int):
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM card_receipts WHERE id=?;", (rid,))
        conn.commit()
    finally:
        conn.close()


def delete_all_card_receipts():
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM card_receipts;")
        conn.commit()
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════════
# ─── 🚀 لایه رشد و فروش — Flash Sale، بازگردانی، لیدربرد، نظرات، رمزارز ────
# ══════════════════════════════════════════════════════════════════════════════

import json as _json
import time as _time

_CFG_CACHE: dict = {}
_CFG_TTL = 60  # ثانیه


def get_cfg(key: str, default: str = "") -> str:
    """خواندن تنظیم از bot_config با کش ۶۰ ثانیه‌ای."""
    now = _time.time()
    hit = _CFG_CACHE.get(key)
    if hit and now - hit[1] < _CFG_TTL:
        return hit[0]
    val = default
    conn = _get_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")
        import db_conn as _dc
        _dc.ensure_unique_constraint(conn, "bot_config", ["key"])
        row = conn.execute("SELECT value FROM bot_config WHERE key=?;", (key,)).fetchone()
        if row is not None and row[0] is not None:
            val = str(row[0])
    except Exception:
        pass
    finally:
        conn.close()
    _CFG_CACHE[key] = (val, now)
    return val


def set_cfg(key: str, value) -> None:
    conn = _get_connection()
    try:
        conn.execute("CREATE TABLE IF NOT EXISTS bot_config (key TEXT PRIMARY KEY, value TEXT);")
        import db_conn as _dc
        _dc.ensure_unique_constraint(conn, "bot_config", ["key"])
        conn.execute(
            "INSERT INTO bot_config (key,value) VALUES (?,?) "
            "ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
            (key, str(value)))
        conn.commit()
    finally:
        conn.close()
    _CFG_CACHE.pop(key, None)


def get_cfg_json(key: str, default: dict) -> dict:
    raw = get_cfg(key, "")
    if not raw:
        return dict(default)
    try:
        d = dict(default)
        d.update(_json.loads(raw))
        return d
    except Exception:
        return dict(default)


# ─── درگاه‌های پرداخت چند‌گانه (مدیریت از پنل) ────────────────────────────────
# تنظیمات هر درگاه در این جدول ذخیره می‌شه، نه در .env — یعنی ادمین می‌تونه بدون
# ری‌دیپلوی درگاه اضافه/حذف/فعال/غیرفعال کنه و ترتیب اولویت failover رو عوض کنه.
# ⚠️ credentials به‌صورت JSON متنی (بدون رمزنگاری) ذخیره می‌شه — دقیقاً همون سطح امنیتی
# که پروژه از قبل برای رازها در .env داره (بخش ۱۳ CLAUDE.md). چون در دسترس‌بودن پرداخت
# مهم‌تر از رمزنگاری‌در‌سکون مرچنت‌آیدیه (که به‌تنهایی امکان برداشت پول نمی‌ده)، عمداً
# fail-closed نشده. کلید هیچ‌وقت به HTML پنل برنمی‌گرده (فقط وضعیت «ثبت‌شده/نشده»).
_PAYGW_SCHEMA_READY = False


def ensure_payment_gateways_schema():
    global _PAYGW_SCHEMA_READY
    if _PAYGW_SCHEMA_READY:
        return
    _PAYGW_SCHEMA_READY = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payment_gateways (
                gateway     TEXT PRIMARY KEY,
                enabled     INTEGER NOT NULL DEFAULT 0,
                priority    INTEGER NOT NULL DEFAULT 100,
                credentials TEXT NOT NULL DEFAULT '{}',
                sandbox     INTEGER NOT NULL DEFAULT 0,
                updated_at  TEXT
            );""")
        conn.commit()
    finally:
        conn.close()


def list_payment_gateways() -> list:
    """همهٔ ردیف‌های تنظیم درگاه (فقط اونهایی که ادمین یه‌بار ذخیره کرده) — برای پنل."""
    ensure_payment_gateways_schema()
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT gateway, enabled, priority, credentials, sandbox, updated_at "
            "FROM payment_gateways ORDER BY priority ASC, gateway ASC;").fetchall()
        out = []
        for r in rows:
            try:
                creds = _json.loads(r[3] or "{}")
            except Exception:
                creds = {}
            out.append({"gateway": r[0], "enabled": int(r[1] or 0), "priority": int(r[2] or 100),
                        "credentials": creds, "sandbox": int(r[4] or 0), "updated_at": r[5]})
        return out
    finally:
        conn.close()


def get_payment_gateway(gateway: str) -> dict | None:
    ensure_payment_gateways_schema()
    conn = _get_connection()
    try:
        r = conn.execute(
            "SELECT gateway, enabled, priority, credentials, sandbox, updated_at "
            "FROM payment_gateways WHERE gateway=?;", (gateway,)).fetchone()
        if not r:
            return None
        try:
            creds = _json.loads(r[3] or "{}")
        except Exception:
            creds = {}
        return {"gateway": r[0], "enabled": int(r[1] or 0), "priority": int(r[2] or 100),
                "credentials": creds, "sandbox": int(r[4] or 0), "updated_at": r[5]}
    finally:
        conn.close()


def save_payment_gateway(gateway: str, enabled: int, priority: int,
                          credentials: dict, sandbox: int = 0) -> None:
    """upsert تنظیم یک درگاه. credentials یه دیکشنریه که JSON می‌شه."""
    ensure_payment_gateways_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "INSERT INTO payment_gateways (gateway, enabled, priority, credentials, sandbox, updated_at) "
            "VALUES (?,?,?,?,?,datetime('now')) "
            "ON CONFLICT(gateway) DO UPDATE SET enabled=excluded.enabled, priority=excluded.priority, "
            "credentials=excluded.credentials, sandbox=excluded.sandbox, updated_at=excluded.updated_at;",
            (gateway, int(enabled), int(priority), _json.dumps(credentials, ensure_ascii=False), int(sandbox)))
        conn.commit()
    finally:
        conn.close()


def get_active_payment_gateways() -> list:
    """درگاه‌های فعال، مرتب بر اساس اولویت صعودی — پایهٔ failover در payment_service.
    فقط درگاه‌هایی که enabled=1 هستن و حداقل یه فیلد اعتبار غیرخالی دارن (یا sandbox روشنه)."""
    active = []
    for g in list_payment_gateways():
        if not g["enabled"]:
            continue
        has_cred = bool(g["sandbox"]) or any((str(v).strip() for v in (g["credentials"] or {}).values()))
        if has_cred:
            active.append(g)
    return active


_GROWTH_SCHEMA_READY = False

def ensure_growth_schema():
    """جدول‌های فروش فوری و بازگردانی + مهاجرت رسیدها — فقط یک‌بار در هر پروسه."""
    global _GROWTH_SCHEMA_READY
    if _GROWTH_SCHEMA_READY:
        return
    _GROWTH_SCHEMA_READY = True
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS flash_sales (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                percent    INTEGER NOT NULL,
                starts_at  TEXT NOT NULL,
                ends_at    TEXT NOT NULL,
                is_active  INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now','localtime'))
            );""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS winback_log (
                id      INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                code_id INTEGER,
                sent_at TEXT DEFAULT (datetime('now','localtime'))
            );""")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS product_ratings (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER NOT NULL,
                order_id    INTEGER NOT NULL,
                product_id  INTEGER NOT NULL,
                rating      INTEGER NOT NULL CHECK(rating BETWEEN 1 AND 5),
                comment     TEXT DEFAULT '',
                created_at  TEXT DEFAULT (datetime('now')),
                UNIQUE(order_id)
            );""")
        # مهاجرت card_receipts برای رمزارز (قانون ۱۳)
        try:
            cols = {r[1] for r in conn.execute("PRAGMA table_info(card_receipts);").fetchall()}
            if cols:
                if "method" not in cols:
                    conn.execute("ALTER TABLE card_receipts ADD COLUMN method TEXT DEFAULT 'card';")
                if "txid" not in cols:
                    conn.execute("ALTER TABLE card_receipts ADD COLUMN txid TEXT DEFAULT '';")
        except Exception:
            pass
        conn.commit()
    finally:
        conn.close()
    # ایندکس‌های جدول‌های growth (flash_sales, product_ratings) پس از ساخت‌شان
    try:
        ensure_indexes()
    except Exception:
        pass


# ─── ۳) فروش فوری (Flash Sale) ────────────────────────────────────────────

def create_flash_sale(product_id: int, percent: int, hours: int) -> int:
    ensure_growth_schema()
    conn = _get_connection()
    try:
        # فقط یک فروش فعال برای هر محصول
        conn.execute("UPDATE flash_sales SET is_active=0 WHERE product_id=?;", (product_id,))
        cur = conn.execute("""
            INSERT INTO flash_sales (product_id, percent, starts_at, ends_at)
            VALUES (?,?, datetime('now','localtime'), datetime('now','localtime', ?));
        """, (product_id, max(1, min(90, int(percent))), f"+{int(hours)} hours"))
        conn.commit()
        try: flash_map_invalidate()
        except Exception: pass
        return cur.lastrowid
    finally:
        conn.close()


def deactivate_flash_sale(sale_id: int):
    conn = _get_connection()
    try:
        conn.execute("UPDATE flash_sales SET is_active=0 WHERE id=?;", (sale_id,))
        conn.commit()
        try: flash_map_invalidate()
        except Exception: pass
    finally:
        conn.close()


def get_flash_sale(product_id: int):
    """فروش فوری فعال محصول — dict یا None."""
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("""
            SELECT *, CAST((julianday(ends_at)-julianday('now','localtime'))*24*60 AS INTEGER) AS mins_left
            FROM flash_sales
            WHERE product_id=? AND is_active=1
              AND datetime('now','localtime') BETWEEN starts_at AND ends_at
            ORDER BY id DESC LIMIT 1;
        """, (product_id,)).fetchone()
        if not row:
            return None
        mins = max(0, int(row["mins_left"] or 0))
        if mins >= 60:
            left = f"{mins//60} ساعت و {mins%60} دقیقه"
        else:
            left = f"{mins} دقیقه"
        return {"id": row["id"], "percent": int(row["percent"]),
                "ends_at": row["ends_at"], "mins_left": mins, "left_str": left}
    finally:
        conn.close()


def batch_flash_percents(product_ids: list) -> dict:
    """نسخهٔ batch سبک get_flash_sale — فقط درصد فعال هر محصول (نه شیء کامل با
    mins_left/left_str)، چون همینو مصرف‌کننده‌های لیستی (list_products،
    favorite_products، api_categories) لازم دارن. یک کوئری برای کل لیست به‌جای
    یک کوئری جدا به‌ازای هر محصول (رفع N+1، بخش ۲ فاز ۲ ممیزی). کلید غایب در
    خروجی یعنی فروش فوری فعالی نداره."""
    if not product_ids:
        return {}
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        placeholders = ",".join("?" * len(product_ids))
        rows = conn.execute(f"""
            SELECT product_id, percent FROM flash_sales
            WHERE product_id IN ({placeholders}) AND is_active=1
              AND datetime('now','localtime') BETWEEN starts_at AND ends_at
            ORDER BY id DESC;
        """, tuple(product_ids)).fetchall()
        out = {}
        for r in rows:
            pid = int(r["product_id"])
            if pid not in out:  # اولین (جدیدترین، چون ORDER BY id DESC) رو نگه دار
                out[pid] = int(r["percent"])
        return out
    finally:
        conn.close()


def batch_product_ratings(product_ids: list) -> dict:
    """نسخهٔ batch get_product_rating — یک کوئری GROUP BY برای کل لیست."""
    if not product_ids:
        return {}
    ensure_ratings_schema()
    conn = _get_connection()
    try:
        placeholders = ",".join("?" * len(product_ids))
        rows = conn.execute(f"""
            SELECT product_id, COUNT(*) as cnt, ROUND(AVG(rating),1) as avg
            FROM product_ratings WHERE product_id IN ({placeholders})
            GROUP BY product_id;
        """, tuple(product_ids)).fetchall()
        return {int(r[0]): {"count": int(r[1] or 0), "avg": float(r[2] or 0)} for r in rows}
    finally:
        conn.close()


def batch_available_stock(product_ids: list) -> dict:
    """نسخهٔ batch get_available_stock — یک کوئری GROUP BY برای کل لیست.
    کلید غایب یعنی موجودی صفر (هیچ ردیف product_feed تحویل‌نشده‌ای نداره)."""
    if not product_ids:
        return {}
    conn = _get_connection()
    try:
        placeholders = ",".join("?" * len(product_ids))
        rows = conn.execute(f"""
            SELECT product_id, COUNT(*) as cnt FROM product_feed
            WHERE product_id IN ({placeholders}) AND delivered=0
            GROUP BY product_id;
        """, tuple(product_ids)).fetchall()
        return {int(r[0]): int(r[1] or 0) for r in rows}
    finally:
        conn.close()


def partner_price_applies(price, partner_price, partner_ok: bool) -> bool:
    """آیا قیمت همکاری باید به‌جای قیمت اصلی اعمال بشه؟ باید مثبت و کمتر از قیمت
    اصلی باشه، فقط برای همکار تأییدشده. قبلاً همین شرط عیناً در ۵ جای جدا bot.py
    تکرار شده بود (بخش ۲۲ فاز ۲ ممیزی) — منبع واحد یعنی هر تغییر آیندهٔ این قاعده
    فقط یه‌جا لازمه اعمال بشه، نه ریسک جا موندن یکی از مسیرهای خرید."""
    return bool(partner_ok and partner_price and int(partner_price) > 0 and int(partner_price) < int(price))


def apply_flash_price(product_id: int, price: int):
    """(قیمت نهایی، فروش‌فوری یا None)"""
    try:
        sale = get_flash_sale(product_id)
        if sale:
            return max(0, int(price) - int(price) * sale["percent"] // 100), sale
    except Exception:
        pass
    return int(price), None


def list_flash_sales(limit: int = 30) -> list:
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT f.*, COALESCE(p.title,'#'||f.product_id) AS title,
                   (datetime('now','localtime') BETWEEN f.starts_at AND f.ends_at AND f.is_active=1) AS live
            FROM flash_sales f LEFT JOIN products p ON p.id=f.product_id
            ORDER BY f.id DESC LIMIT ?;
        """, (limit,)).fetchall()
    finally:
        conn.close()


# ─── ۶) امتیاز محصول ─────────────────────────────────────────────────────

def save_product_rating(user_id: int, order_id: int, product_id: int, rating: int) -> bool:
    ensure_growth_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT OR IGNORE INTO product_ratings (user_id,order_id,product_id,rating) VALUES (?,?,?,?);",
            (user_id, order_id, product_id, max(1, min(5, int(rating)))))
        ok = cur.rowcount
        conn.commit()
        return bool(ok and ok > 0)
    finally:
        conn.close()


# نکته: get_product_rating نسخه dict قدیمی (بالاتر در همین فایل) مرجع است.


# ─── ۲) پیشنهاد بعد از خرید (Upsell) ─────────────────────────────────────

def get_upsell_products(product_id: int, category_id, limit: int = 2) -> list:
    """پرفروش‌های موجودِ همان دسته، غیر از محصول خریداری‌شده."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT p.id, p.title, p.price, p.category_id,
                   (SELECT COUNT(*) FROM product_feed f WHERE f.product_id=p.id AND f.delivered=0) AS stock,
                   (SELECT COUNT(*) FROM orders o WHERE o.product_id=p.id
                        AND COALESCE(o.status,'active')!='returned') AS sold
            FROM products p
            WHERE p.id != ? AND COALESCE(p.is_active,1)=1
              AND (? IS NULL OR p.category_id = ?)
            GROUP BY p.id
            HAVING (SELECT COUNT(*) FROM product_feed f WHERE f.product_id=p.id AND f.delivered=0) > 0
            ORDER BY sold DESC, p.id DESC
            LIMIT ?;
        """, (product_id, category_id, category_id, limit)).fetchall()
    except Exception:
        return []
    finally:
        conn.close()


# ─── ۱) کمپین بازگردانی (Win-back) ────────────────────────────────────────

WINBACK_DEFAULTS = {
    "enabled": 0, "days_inactive": 14, "percent": 15,
    "expire_days": 3, "cooldown_days": 30, "hour": 11, "batch": 30,
    "message": ("سلام {name} 👋\n\nدلمون برات تنگ شده! 💜\n"
                "یه هدیه مخصوص خودت داریم:\n\n"
                "🎁 کد تخفیف <code>{code}</code> — {percent}٪ تخفیف\n"
                "⏳ فقط تا {days} روز اعتبار داره!\n\n"
                "همین حالا از منوی فروشگاه استفاده‌ش کن 🛍"),
}


def get_winback_settings() -> dict:
    return get_cfg_json("winback", WINBACK_DEFAULTS)


def find_winback_candidates(days_inactive: int, cooldown_days: int, batch: int = 30) -> list:
    """کاربرانی که خرید داشته‌اند ولی N روز است نخریده‌اند و اخیراً پیام نگرفته‌اند."""
    ensure_growth_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        # ⚠️ Postgres سخت‌گیر GROUP BY: هر ستون غیر-aggregate باید در GROUP BY یا
        # داخل یک تابع aggregate باشه (برخلاف SQLite که مقدار دلخواه برمی‌داره).
        # چون join یک‌به‌یکه، MAX() روی نام معنی رو عوض نمی‌کنه، فقط قانون رو رعایت می‌کنه.
        return conn.execute("""
            SELECT CAST(o.user_id AS INTEGER) AS uid,
                   MAX(COALESCE(u.full_name, u.username, '')) AS name,
                   MAX(o.created_at) AS last_order
            FROM orders o
            LEFT JOIN users u ON CAST(u.user_id AS INTEGER)=CAST(o.user_id AS INTEGER)
            WHERE COALESCE(o.status,'active') != 'returned'
            GROUP BY CAST(o.user_id AS INTEGER)
            HAVING MAX(o.created_at) < datetime('now','localtime', ?)
               AND NOT EXISTS (
                   SELECT 1 FROM winback_log w
                   WHERE w.user_id = CAST(o.user_id AS INTEGER)
                     AND w.sent_at > datetime('now','localtime', ?)
               )
            ORDER BY last_order ASC
            LIMIT ?;
        """, (f"-{int(days_inactive)} days", f"-{int(cooldown_days)} days", int(batch))).fetchall()
    finally:
        conn.close()


def create_winback_code(user_id: int, percent: int, expire_days: int) -> str:
    """کد تخفیف شخصی یک‌بارمصرف برای بازگردانی کاربر — برمی‌گرداند: متن کد.
    از موتور مشترک issue_personal_discount_code استفاده می‌کنه (نه منطق تکراری)؛
    یعنی این کد هم مثل جوایز گردونه owner-locked می‌شه و توی «جوایز من» دیده می‌شه."""
    result = issue_personal_discount_code(
        user_id, "percent", int(percent),
        expire_hours=int(expire_days) * 24,
        description=f"بازگردانی کاربر {user_id}",
        source="winback", code_prefix="WB",
    )
    code = result.get("code") or ""
    if code and result.get("code_id"):
        conn = _get_connection()
        try:
            conn.execute("INSERT INTO winback_log (user_id, code_id) VALUES (?,?);",
                         (user_id, result["code_id"]))
            conn.commit()
        finally:
            conn.close()
    return code


# ─── ۴) لیدربرد هفتگی همکاران ────────────────────────────────────────────

LEADERBOARD_DEFAULTS = {
    "enabled": 0, "weekday": 4,  # 4 = جمعه (Mon=0)
    "rewards": "100000,60000,30000",
    "message": ("🏆 <b>نتایج مسابقه هفتگی همکاران</b>\n\n"
                "تبریک! شما در جایگاه {rank} این هفته قرار گرفتید 🎉\n"
                "🛒 فروش شما: {count} سفارش\n"
                "🎁 جایزه: <b>{reward}</b> تومان به کیف‌پول همکاری شما اضافه شد.\n\n"
                "هفته بعد هم منتظرتیم 💪"),
}


def get_leaderboard_settings() -> dict:
    return get_cfg_json("leaderboard", LEADERBOARD_DEFAULTS)


def weekly_top_partners(limit: int = 3) -> list:
    """برترین همکاران ۷ روز اخیر بر اساس تعداد خرید همکاری."""
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("""
            SELECT CAST(user_id AS INTEGER) AS uid, COUNT(*) AS cnt,
                   COALESCE(SUM(price),0) AS total
            FROM orders
            WHERE buyer_type='partner'
              AND COALESCE(status,'active') != 'returned'
              AND created_at > datetime('now','localtime','-7 days')
            GROUP BY CAST(user_id AS INTEGER)
            ORDER BY cnt DESC, total DESC
            LIMIT ?;
        """, (limit,)).fetchall()
    finally:
        conn.close()


# ─── ۷) تنظیمات رمزارز / کانال / تبلیغ / وب‌اپ ────────────────────────────

# شماره کارت مقصد کارت‌به‌کارت — قبلاً هم در bot.py هم api.py مستقل هاردکد شده
# بود (دو نسخهٔ جدا از یه مقدار)؛ یعنی تغییر کارت بانکی نیاز به ویرایش دو فایل
# و دیپلوی داشت، با ریسک واقعی جا موندن یکی و نمایش کارت قدیمی به بخشی از
# کاربرها. مقادیر پیش‌فرض زیر دقیقاً همون مقادیر قبلاً هاردکدشده‌ن — یعنی تا
# وقتی ادمین از پنل تغییرش نده، رفتار برای کاربر نهایی کاملاً یکسان می‌مونه.
CARD2CARD_DEFAULTS = {"card_number": "6037701608004393", "card_name": "سید فیروز ایازی"}

CRYPTO_DEFAULTS = {"enabled": 0, "usdt_trc20": "", "trx": "",
                   "note": ("💡 <b>راهنمای پرداخت رمزارز:</b>\n\n""۱. مبلغ به تومان را وارد کنید\n""۲. به آدرس نشان‌داده‌شده واریز کنید\n""۳. TXID (هش تراکنش) را برای ما ارسال کنید\n\n""⏳ پس از تأیید تراکنش (معمولاً ۱۵-۳۰ دقیقه)، کیف‌پول شارژ می‌شود.")}
SOCIAL_DEFAULTS = {"channel_id": "", "sale_post": 0, "rating": 1, "upsell": 1,
                   "sale_post_text": (
                       "✅ <b>فروش موفق!</b>\n\n"
                       "🛍 محصول «{title}» همین الان خریداری شد.\n\n"
                       "از ربات ما خرید کنید — تحویل آنی و تضمینی 🚀"
                   )}
PROMO_DEFAULTS  = {"text": (
    "🎁 دعوت ویژه به استوک‌لند!\n"
    "فروشگاه دیجیتال با تحویل آنی، پشتیبانی ۲۴ ساعته و قیمت‌های واقعاً رقابتی — دقیقاً چیزی که دنبالشی.\n\n"
    "همین الان با لینک بالا عضو شو و هدیهٔ خوش‌آمدگویی رایگان بگیر 🎉"
)}


def get_crypto_settings() -> dict:
    return get_cfg_json("crypto", CRYPTO_DEFAULTS)


def get_card2card_settings() -> dict:
    """کارت مقصد کارت‌به‌کارت — منبع واحد برای هم ربات هم مینی‌اپ (بخش ۲۲ فاز ۲ ممیزی)."""
    return get_cfg_json("card2card", CARD2CARD_DEFAULTS)


def get_social_settings() -> dict:
    return get_cfg_json("social", SOCIAL_DEFAULTS)


def get_promo_settings() -> dict:
    settings = get_cfg_json("promo", PROMO_DEFAULTS)
    # خودترمیمی: نسخه‌های قدیمی‌تر متن پیش‌فرض رو با تگ HTML تلگرام (<b>...</b>) ذخیره
    # می‌کردن — درست فقط وقتی ربات با parse_mode=HTML داخل چت می‌فرستادش، ولی همین متن
    # خام مستقیم توی لینک اشتراک‌گذاری t.me/share/url هم می‌ره که متن ساده‌ست، پس تگ‌ها
    # خام توی پیام نهایی ظاهر می‌شدن. اگه ردیف ذخیره‌شده در bot_config هنوز همون امضای
    # خراب رو داره (چه پیش‌فرض قدیمی، چه یه ذخیرهٔ قبلی از پنل که این متن رو بی‌تغییر
    # دوباره ست کرده)، به‌جای نمایش دوبارهٔ باگ، به پیش‌فرض تازه (بدون تگ) برمی‌گردیم.
    text = str(settings.get("text") or "")
    if "<b>" in text or "</b>" in text:
        settings = dict(PROMO_DEFAULTS)
    return settings


def save_crypto_receipt(user_id: int, amount: int, network: str, txid: str) -> int:
    """رسید رمزارز — در همان جدول card_receipts با method مجزا."""
    ensure_card_receipts_schema()
    ensure_growth_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "INSERT INTO card_receipts (user_id, amount, file_id, method, txid) VALUES (?,?,?,?,?);",
            (user_id, amount, "", f"crypto_{network}", txid.strip()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


# ─── ۶) پاداش عضویت (به‌جای اولین خرید) + مسیریابی کیف‌پول ─────────────────

def _is_approved_partner(user_id: int) -> bool:
    conn = _get_connection()
    try:
        r = conn.execute(
            "SELECT 1 FROM partners WHERE CAST(tg_user_id AS INTEGER)=? AND status='approved' LIMIT 1;",
            (int(user_id),)).fetchone()
        return bool(r)
    except Exception:
        return False
    finally:
        conn.close()


def credit_referrer(referrer_id: int, amount: int, note: str) -> str:
    """پرداخت به معرف — همکار → کیف همکاری، کاربر عادی → کیف اصلی. برمی‌گرداند نوع کیف."""
    if _is_approved_partner(referrer_id):
        credit_partner_wallet(referrer_id, amount, note=note)
        return "partner"
    add_wallet_balance(referrer_id, amount)
    return "main"




def ensure_invite_cap_schema():
    """ستون invite_count در جدول users."""
    global _ENSURE_INVITE_CAP_SCHEMA_DONE
    if _ENSURE_INVITE_CAP_SCHEMA_DONE:
        return
    _ENSURE_INVITE_CAP_SCHEMA_DONE = True
    conn = _get_connection()
    try:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(users);").fetchall()}
        if "invite_count" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN invite_count INTEGER DEFAULT 0;")
        if "invite_cap_reset" not in cols:
            conn.execute("ALTER TABLE users ADD COLUMN invite_cap_reset INTEGER DEFAULT 0;")
        conn.commit()
    except Exception:
        pass
    finally:
        conn.close()


def check_invite_cap(referrer_id: int) -> dict:
    """بررسی سقف دعوت — {ok, count, cap, reset_needed}."""
    from db import get_cfg_json
    settings = get_cfg_json("referral_settings_ext", {
        "max_invites": 0, "cap_reset_on_purchase": 1})
    cap = int(settings.get("max_invites") or 0)
    if cap <= 0:
        return {"ok": True, "count": 0, "cap": 0}
    ensure_invite_cap_schema()
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT invite_count, invite_cap_reset FROM users WHERE CAST(user_id AS INTEGER)=?;",
            (referrer_id,)).fetchone()
        count = int(row[0] if row else 0)
        reset = int(row[1] if row else 0)
        return {"ok": count < cap or bool(reset), "count": count, "cap": cap,
                "reset_after_purchase": int(settings.get("cap_reset_on_purchase") or 1)}
    finally:
        conn.close()


def increment_invite_count(referrer_id: int):
    ensure_invite_cap_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE users SET invite_count=COALESCE(invite_count,0)+1 WHERE CAST(user_id AS INTEGER)=?;",
            (referrer_id,))
        conn.commit()
    finally:
        conn.close()


def reset_invite_cap_after_purchase(user_id: int):
    """بعد از خرید، سقف دعوت مجدداً فعال می‌شود."""
    ensure_invite_cap_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE users SET invite_count=0, invite_cap_reset=0 WHERE CAST(user_id AS INTEGER)=?;",
            (user_id,))
        conn.commit()
    finally:
        conn.close()

def pay_signup_referral_reward(referrer_id: int, referred_id: int) -> dict:
    """پاداش ثابت معرفی — همان لحظه عضویت، فقط یک‌بار (قفل با پرچم rewarded).
    Returns: {paid, amount, wallet}

    ⚠️ فقط همکار تأییدشده پاداش دعوت می‌گیرد — طبق درخواست صریح مالک پروژه («برای
    کاربر عادی غیرفعال، با همکار شدن فعال بشه»، بخش ۳۹ CLAUDE.md). این چک قبل از
    مقداردهی پرچم `rewarded=1` انجام می‌شه (نه بعدش، مثل نسخهٔ قبلی) — چون قبلاً
    اگه معرف همکار نبود، ردیف همچنان `rewarded=1` می‌شد بدون واریز واقعی، یعنی
    اگه بعداً همون کاربر همکار می‌شد، دیگه هیچ‌وقت واجد شرایط این پاداش نمی‌شد
    (چون شرط `rewarded=0` دیگه true نبود) — دقیقاً برعکس خواستهٔ مالک پروژه.
    مسیر جبرانی: `approve_partner()` بعد از تأیید، خودش این تابع رو برای همهٔ
    معرفی‌های قبلی هنوز-جایزه‌نگرفتهٔ همون کاربر دوباره صدا می‌زنه."""
    ensure_referral_schema()
    if not _is_approved_partner(referrer_id):
        return {"paid": False}
    settings = get_referral_settings()
    if not settings.get("is_active"):
        return {"paid": False}
    amount = int(settings.get("reward_amount") or 0)
    if amount <= 0:
        return {"paid": False}
    conn = _get_connection()
    try:
        # چک اول: آیا قبلاً پاداش داده شده؟
        row = conn.execute(
            "SELECT id FROM referrals WHERE referrer_id=? AND referred_id=? AND rewarded=0 LIMIT 1;",
            (referrer_id, referred_id)).fetchone()
        if not row:
            return {"paid": False}
        conn.execute(
            "UPDATE referrals SET rewarded=1, reward_amount=?, rewarded_at=datetime('now','localtime') "
            "WHERE referrer_id=? AND referred_id=? AND rewarded=0;",
            (amount, referrer_id, referred_id))
        conn.commit()
    finally:
        conn.close()
    wallet = credit_referrer(referrer_id, amount,
                             note=f"پاداش معرفی کاربر {referred_id}")
    return {"paid": True, "amount": amount, "wallet": wallet}


_FLASH_MAP_CACHE = {"t": 0.0, "map": {}}

def get_active_flash_map() -> dict:
    """{product_id: percent} فروش‌های فوری زنده — کش ۳۰ ثانیه برای لیبل لیست‌ها."""
    now = _time.time()
    if now - _FLASH_MAP_CACHE["t"] < 30:
        return _FLASH_MAP_CACHE["map"]
    ensure_growth_schema()
    m = {}
    conn = _get_connection()
    try:
        for r in conn.execute("""
            SELECT product_id, percent FROM flash_sales
            WHERE is_active=1 AND datetime('now','localtime') BETWEEN starts_at AND ends_at;"""):
            m[int(r[0])] = int(r[1])
    except Exception:
        pass
    finally:
        conn.close()
    _FLASH_MAP_CACHE["t"] = now
    _FLASH_MAP_CACHE["map"] = m
    return m


def flash_map_invalidate():
    _FLASH_MAP_CACHE["t"] = 0.0


# ══════════════════════════════════════════════════════════════════════════
# ─── App Content (PWA) — آموزش/اخبار/امکانات ─────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
_ENSURE_APP_CONTENT_DONE = False

def ensure_app_content_schema():
    """جدول محتوای اپ PWA — الگوی مشابه card_receipts (سازگار SQLite/PG)."""
    global _ENSURE_APP_CONTENT_DONE
    if _ENSURE_APP_CONTENT_DONE:
        return
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS app_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL DEFAULT 'news',
                title TEXT NOT NULL,
                body TEXT DEFAULT '',
                image_url TEXT DEFAULT '',
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now'))
            );
        """)
        try:
            conn.execute("ALTER TABLE app_content ADD COLUMN link_url TEXT DEFAULT '';")
            conn.commit()
        except Exception:
            pass
        conn.commit()
        _ENSURE_APP_CONTENT_DONE = True
    finally:
        conn.close()


def add_app_content(kind: str, title: str, body: str = "", image_url: str = "", link_url: str = "") -> int:
    ensure_app_content_schema()
    conn = _get_connection()
    try:
        from db_conn import is_postgres as _is_pg
        if _is_pg():
            cur = conn.execute(
                "INSERT INTO app_content (kind,title,body,image_url,link_url) VALUES (?,?,?,?,?) RETURNING id;",
                (kind, title, body, image_url, link_url))
            row = cur.fetchone()
            conn.commit()
            if row is None:
                return 0
            return int(row["id"] if hasattr(row, "keys") else row[0])
        cur = conn.execute(
            "INSERT INTO app_content (kind,title,body,image_url,link_url) VALUES (?,?,?,?,?);",
            (kind, title, body, image_url, link_url))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_app_content(cid: int, kind: str, title: str, body: str,
                       image_url: str, is_active: int, link_url: str = "") -> None:
    ensure_app_content_schema()
    conn = _get_connection()
    try:
        conn.execute(
            "UPDATE app_content SET kind=?, title=?, body=?, image_url=?, is_active=?, link_url=? WHERE id=?;",
            (kind, title, body, image_url, int(is_active), link_url, int(cid)))
        conn.commit()
    finally:
        conn.close()


def delete_app_content(cid: int) -> None:
    ensure_app_content_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM app_content WHERE id=?;", (int(cid),))
        conn.commit()
    finally:
        conn.close()


def get_app_content(kind: str | None = None, active_only: bool = True, limit: int = 100) -> list:
    ensure_app_content_schema()
    conn = _get_connection()
    try:
        q = "SELECT * FROM app_content WHERE 1=1"
        params = []
        if kind:
            q += " AND kind=?"
            params.append(kind)
        if active_only:
            q += " AND is_active=1"
        q += " ORDER BY id DESC LIMIT ?;"
        params.append(int(limit))
        rows = conn.execute(q, tuple(params)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_app_content_item(cid: int):
    ensure_app_content_schema()
    conn = _get_connection()
    try:
        r = conn.execute("SELECT * FROM app_content WHERE id=?;", (int(cid),)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
# ─── ورود وب‌سایت با تأیید داخل ربات (دیپ‌لینک weblogin_TOKEN) ─────────────
# ══════════════════════════════════════════════════════════════════════════
_ENSURE_WEB_LOGIN_DONE = False


def ensure_web_login_schema():
    global _ENSURE_WEB_LOGIN_DONE
    if _ENSURE_WEB_LOGIN_DONE:
        return
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS web_login_tokens (
                token TEXT PRIMARY KEY,
                status TEXT DEFAULT 'pending',
                user_id INTEGER,
                created_at INTEGER DEFAULT 0
            );
        """)
        conn.commit()
        _ENSURE_WEB_LOGIN_DONE = True
    finally:
        conn.close()


def create_web_login_token(token: str) -> None:
    ensure_web_login_schema()
    import time as _t
    now = int(_t.time())
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM web_login_tokens WHERE created_at < ?;", (now - 86400,))
        conn.execute("INSERT INTO web_login_tokens (token, status, created_at) VALUES (?, 'pending', ?);",
                     (token, now))
        conn.commit()
    finally:
        conn.close()


def confirm_web_login_token(token: str, user_id: int) -> bool:
    """توسط ربات صدا زده می‌شه وقتی کاربر روی دیپ‌لینک weblogin_TOKEN بزنه — True یعنی واقعاً تأیید ثبت شد."""
    ensure_web_login_schema()
    conn = _get_connection()
    try:
        cur = conn.execute(
            "UPDATE web_login_tokens SET status='confirmed', user_id=? WHERE token=? AND status='pending';",
            (user_id, token))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def get_web_login_token(token: str):
    ensure_web_login_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        return conn.execute("SELECT * FROM web_login_tokens WHERE token=?;", (token,)).fetchone()
    finally:
        conn.close()


def consume_web_login_token(token: str):
    """توکن تأییدشده رو اتمیک به 'used' تغییر می‌ده و ردیف رو برمی‌گردونه — فقط یک‌بار
    موفق می‌شه، حتی اگه چندبار poll بشه (جلوگیری از replay: قبلاً هر poll روی توکن
    'confirmed' یه سشن تازه صادر می‌کرد، یعنی هرکی مقدار توکن رو (مثلاً از لاگ/referrer)
    گیر می‌آورد تا سقف پاکسازی ۲۴ساعته می‌تونست بی‌نهایت سشن برای اون کاربر بسازه).
    None یعنی توکن قبلاً استفاده شده یا هنوز تأیید نشده."""
    ensure_web_login_schema()
    conn = _get_connection()
    conn.row_factory = sqlite3.Row
    try:
        row = conn.execute("SELECT * FROM web_login_tokens WHERE token=? AND status='confirmed';", (token,)).fetchone()
        if not row:
            return None
        cur = conn.execute("UPDATE web_login_tokens SET status='used' WHERE token=? AND status='confirmed';", (token,))
        conn.commit()
        return dict(row) if cur.rowcount > 0 else None
    finally:
        conn.close()


def get_user_full_name(user_id: int) -> str:
    conn = _get_connection()
    try:
        row = conn.execute("SELECT full_name FROM users WHERE user_id=? LIMIT 1;", (int(user_id),)).fetchone()
        if not row:
            return ""
        return (row["full_name"] if hasattr(row, "keys") else row[0]) or ""
    except Exception:
        return ""
    finally:
        conn.close()


# ══════════════════════════════════════════════════════════════════════════
# ─── آموزش — CMS داخلی کامل (فاز ۲) ────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════
_ENSURE_TUTORIALS_DONE = False

_TUTORIAL_COLUMNS = (
    "title", "cover_image", "short_desc", "body", "gallery",
    "video_upload", "video_link", "download_file", "download_label",
    "category_id", "tags", "status", "publish_date", "sort_order", "featured",
)


def ensure_tutorials_schema():
    global _ENSURE_TUTORIALS_DONE
    if _ENSURE_TUTORIALS_DONE:
        return
    conn = _get_connection()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tutorial_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tutorials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                cover_image TEXT DEFAULT '',
                short_desc TEXT DEFAULT '',
                body TEXT DEFAULT '',
                gallery TEXT DEFAULT '[]',
                video_upload TEXT DEFAULT '',
                video_link TEXT DEFAULT '',
                download_file TEXT DEFAULT '',
                download_label TEXT DEFAULT '',
                category_id INTEGER DEFAULT 0,
                tags TEXT DEFAULT '[]',
                status TEXT DEFAULT 'draft',
                publish_date TEXT DEFAULT '',
                sort_order INTEGER DEFAULT 0,
                featured INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );
        """)
        conn.commit()
        _ENSURE_TUTORIALS_DONE = True
    finally:
        conn.close()


def add_tutorial_category(name: str, slug: str = "") -> int:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        cur = conn.execute("INSERT INTO tutorial_categories (name, slug) VALUES (?, ?);",
                           (name.strip(), (slug or name).strip()))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_tutorial_category(cid: int) -> None:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM tutorial_categories WHERE id=?;", (int(cid),))
        conn.execute("UPDATE tutorials SET category_id=0 WHERE category_id=?;", (int(cid),))
        conn.commit()
    finally:
        conn.close()


def get_tutorial_categories() -> list:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT * FROM tutorial_categories ORDER BY sort_order, id;").fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def get_all_tutorial_tags() -> list:
    """همهٔ برچسب‌های استفاده‌شده تو آموزش‌ها — بدون جدول جدا، فقط aggregate از ستون tags."""
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        rows = conn.execute("SELECT tags FROM tutorials;").fetchall()
        out = set()
        for r in rows:
            try:
                for t in json.loads(r["tags"] if hasattr(r, "keys") else r[0] or "[]"):
                    if t:
                        out.add(t)
            except Exception:
                pass
        return sorted(out)
    finally:
        conn.close()


def add_tutorial(**fields) -> int:
    ensure_tutorials_schema()
    cols = [c for c in _TUTORIAL_COLUMNS if c in fields]
    conn = _get_connection()
    try:
        placeholders = ",".join(["?"] * len(cols))
        cur = conn.execute(
            f"INSERT INTO tutorials ({','.join(cols)}) VALUES ({placeholders});",
            tuple(fields[c] for c in cols),
        )
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_tutorial(tid: int, **fields) -> None:
    ensure_tutorials_schema()
    cols = [c for c in _TUTORIAL_COLUMNS if c in fields]
    if not cols:
        return
    conn = _get_connection()
    try:
        set_clause = ",".join(f"{c}=?" for c in cols)
        conn.execute(
            f"UPDATE tutorials SET {set_clause}, updated_at=datetime('now') WHERE id=?;",
            tuple(fields[c] for c in cols) + (int(tid),),
        )
        conn.commit()
    finally:
        conn.close()


def delete_tutorial(tid: int) -> None:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        conn.execute("DELETE FROM tutorials WHERE id=?;", (int(tid),))
        conn.commit()
    finally:
        conn.close()


def set_tutorial_status(tid: int, status: str) -> None:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tutorials SET status=?, updated_at=datetime('now') WHERE id=?;",
                     (status, int(tid)))
        conn.commit()
    finally:
        conn.close()


def increment_tutorial_views(tid: int) -> None:
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        conn.execute("UPDATE tutorials SET view_count=view_count+1 WHERE id=?;", (int(tid),))
        conn.commit()
    finally:
        conn.close()


def get_tutorial(tid: int):
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        r = conn.execute("SELECT * FROM tutorials WHERE id=?;", (int(tid),)).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def get_tutorials(category_id: int = None, tag: str = None, status: str = None,
                  q: str = None, sort: str = "newest", limit: int = 50, offset: int = 0) -> list:
    """لیست آموزش‌ها — برای پنل (status=None یعنی همه) و PWA (status='published').
    sort: newest | oldest | popular"""
    ensure_tutorials_schema()
    conn = _get_connection()
    try:
        query = "SELECT * FROM tutorials WHERE 1=1"
        params = []
        if status:
            query += " AND status=?"
            params.append(status)
        if category_id:
            query += " AND category_id=?"
            params.append(int(category_id))
        if q:
            # LOWER(...) LIKE LOWER(?) — پرتابل بین SQLite/Postgres (بخش ۵۲)
            query += " AND (LOWER(title) LIKE LOWER(?) OR LOWER(short_desc) LIKE LOWER(?))"
            like = f"%{q}%"
            params += [like, like]
        rows = conn.execute(query, tuple(params)).fetchall()
        items = [dict(r) for r in rows]
        if tag:
            items = [it for it in items if tag in (json.loads(it.get("tags") or "[]"))]
        if sort == "popular":
            items.sort(key=lambda it: (-(it.get("featured") or 0), -(it.get("view_count") or 0), -(it["id"])))
        elif sort == "oldest":
            items.sort(key=lambda it: it["id"])
        else:  # newest
            items.sort(key=lambda it: (-(it.get("featured") or 0), -(it.get("sort_order") or 0), -(it["id"])))
        return items[offset:offset + limit]
    finally:
        conn.close()
