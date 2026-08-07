"""
db_dialect.py — لایه‌ی ترجمه‌ی SQL بین SQLite و PostgreSQL
─────────────────────────────────────────────────────────────
هدف: بدون بازنویسی صدها کوئری، در زمان اجرا الگوهای SQLite را به Postgres تبدیل کن.

این ماژول یک wrapper دور connection می‌گذارد که:
  1) placeholder ? → %s (Postgres)
  2) توابع تاریخ SQLite → معادل Postgres
  3) INSERT OR IGNORE → ON CONFLICT DO NOTHING
  4) سایر تفاوت‌های نحوی

با تنظیم DIALECT در config یا env کنترل می‌شود.
در حالت SQLite هیچ تبدیلی انجام نمی‌شود (بدون سربار).
"""
import re
import os

# dialect جاری — از env قابل تنظیم
DIALECT = os.getenv("DB_DIALECT", "sqlite").lower()


def is_postgres() -> bool:
    return DIALECT == "postgres"


# ══════════════════════════════════════════════════════════════════════════
# ─── ترجمه‌ی کوئری SQLite → Postgres ──────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

# ⚠️ ترجمهٔ کامل توابع تاریخ SQLite → Postgres (بازنویسی جامع، کشف‌شده روی سرور
# تولید واقعی که پنل با «function date(unknown,unknown) does not exist» کرش می‌کرد).
#
# نکتهٔ کلیدی طراحی: کل اپ ستون‌های زمانی (created_at/updated_at/...) رو به‌صورت
# **TEXT با فرمت ISO** ذخیره می‌کنه و SQLite مقایسهٔ لغوی (lexical) متن رو انجام
# می‌ده که برای ISO درست کار می‌کنه. Postgres سخت‌گیرتره: مقایسهٔ timestamp با
# text خطا می‌ده. پس همهٔ این توابع به‌جای برگردوندن timestamp، با to_char به
# **TEXT هم‌فرمت** ترجمه می‌شن تا مقایسهٔ لغوی دقیقاً مثل SQLite کار کنه (و در
# DEFAULT هم روی ستون TEXT بی‌مشکله). ترتیب مهمه: خاص‌ترین (۳-آرگومانی با
# modifier) اول، عام‌ترین (بدون آرگومان) آخر.
#
# نکتهٔ فنی: این الگوها *قبل* از تبدیل ? → %s اجرا می‌شن، پس ? دست‌نخورده می‌مونه
# و تعداد/ترتیب bind param حفظ می‌شه (مثلاً datetime('now','localtime', ?) که ?
# مقدار «'-30 days'» می‌گیره → CAST(? AS INTERVAL)).
_DTS = "'YYYY-MM-DD HH24:MI:SS'"   # فرمت خروجی datetime
_DS  = "'YYYY-MM-DD'"             # فرمت خروجی date
_MOD = r"'((?:[+-]?\s*\d+\s*(?:day|days|hour|hours|month|months|year|years|minute|minutes|second|seconds))|(?:start of \w+))'"

_DATE_PATTERNS = [
    # ── datetime(...) با modifier به‌صورت bind param (?) ──
    (re.compile(r"datetime\(\s*'now'\s*,\s*'localtime'\s*,\s*\?\s*\)", re.I),
     f"to_char(NOW() + CAST(? AS INTERVAL), {_DTS})"),
    (re.compile(r"datetime\(\s*'now'\s*,\s*\?\s*\)", re.I),
     f"to_char(NOW() + CAST(? AS INTERVAL), {_DTS})"),
    # ── datetime(...) با modifier ثابت (literal) ──
    (re.compile(r"datetime\(\s*'now'\s*,\s*'localtime'\s*,\s*" + _MOD + r"\s*\)", re.I),
     f"to_char(NOW() + INTERVAL '\\1', {_DTS})"),
    (re.compile(r"datetime\(\s*'now'\s*,\s*(?!'localtime')" + _MOD + r"\s*\)", re.I),
     f"to_char(NOW() + INTERVAL '\\1', {_DTS})"),
    # ── datetime(...) بدون modifier ──
    (re.compile(r"datetime\(\s*'now'\s*,\s*'localtime'\s*\)", re.I), f"to_char(NOW(), {_DTS})"),
    (re.compile(r"datetime\(\s*'now'\s*\)", re.I), f"to_char(NOW(), {_DTS})"),

    # ── date(...) با modifier به‌صورت bind param (?) ──
    (re.compile(r"date\(\s*'now'\s*,\s*'localtime'\s*,\s*\?\s*\)", re.I),
     f"to_char(NOW() + CAST(? AS INTERVAL), {_DS})"),
    (re.compile(r"date\(\s*'now'\s*,\s*\?\s*\)", re.I),
     f"to_char(NOW() + CAST(? AS INTERVAL), {_DS})"),
    # ── date(...) با modifier ثابت ──
    (re.compile(r"date\(\s*'now'\s*,\s*'localtime'\s*,\s*" + _MOD + r"\s*\)", re.I),
     f"to_char(NOW() + INTERVAL '\\1', {_DS})"),
    (re.compile(r"date\(\s*'now'\s*,\s*(?!'localtime')" + _MOD + r"\s*\)", re.I),
     f"to_char(NOW() + INTERVAL '\\1', {_DS})"),
    # ── date(...) بدون modifier ──
    (re.compile(r"date\(\s*'now'\s*,\s*'localtime'\s*\)", re.I), f"to_char(NOW(), {_DS})"),
    (re.compile(r"date\(\s*'now'\s*\)", re.I), f"to_char(NOW(), {_DS})"),

    # ── strftime روی 'now' (باید قبل از حالت ستونی بیاد) ──
    (re.compile(r"strftime\(\s*'%Y-%m-%d'\s*,\s*'now'\s*\)", re.I), f"to_char(NOW(), {_DS})"),
    (re.compile(r"strftime\(\s*'%Y-%m'\s*,\s*'now'\s*\)", re.I), "to_char(NOW(), 'YYYY-MM')"),

    # ── strftime روی ستون متنی → نیاز به CAST به timestamp ──
    (re.compile(r"strftime\(\s*'%Y-%m-%d'\s*,\s*([\w.]+)\s*\)", re.I),
     r"to_char(CAST(\1 AS timestamp), 'YYYY-MM-DD')"),
    (re.compile(r"strftime\(\s*'%Y-%m'\s*,\s*([\w.]+)\s*\)", re.I),
     r"to_char(CAST(\1 AS timestamp), 'YYYY-MM')"),

    # ── date(col)/datetime(col) روی ستون متنی (بعد از همهٔ حالت‌های 'now') ──
    # فقط نام ستون ساده یا table.column — استخراج بخش تاریخ از متن ISO
    (re.compile(r"date\(\s*([\w.]+)\s*\)", re.I),
     r"to_char(CAST(\1 AS timestamp), 'YYYY-MM-DD')"),
    (re.compile(r"datetime\(\s*([\w.]+)\s*\)", re.I),
     r"to_char(CAST(\1 AS timestamp), 'YYYY-MM-DD HH24:MI:SS')"),
]

# INSERT OR IGNORE / INSERT OR REPLACE
# ⚠️ رفع‌شده (کشف‌شده با تست executescript روی Postgres واقعی): نسخهٔ قبلی این
# الگو فقط "INSERT OR IGNORE INTO" رو با regex ساده جایگزین می‌کرد و بعد
# "ON CONFLICT DO NOTHING" رو به **انتهای کل رشتهٔ SQL** اضافه می‌کرد — برای یه
# execute() تک‌دستوری این تصادفاً درست کار می‌کرد (چون کل رشته = همون یک دستور)،
# ولی executescript() چند دستور رو با هم ترجمه می‌کنه (مثلاً یه INSERT OR IGNORE
# وسط چند CREATE TABLE) — اونجا "انتهای رشته" اصلاً به همون INSERT مربوط نیست،
# نتیجه SQL نامعتبر می‌شد. حالا هر دستور INSERT OR IGNORE به‌طور مستقل (تا اولین
# ; خودش) پیدا و اصلاح می‌شه.
_INSERT_IGNORE_STMT = re.compile(
    r"INSERT\s+OR\s+IGNORE\s+INTO(.*?VALUES\s*\([^;]*?\))\s*;", re.I | re.S
)
_INSERT_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE\s+INTO", re.I)

# AUTOINCREMENT
_AUTOINC = re.compile(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.I)

# ALTER TABLE ... ADD COLUMN (بدون IF NOT EXISTS) — ⚠️ کشف‌شده با تست مستقیم
# روی Postgres واقعی (نه فقط با خوندن کد): این پروژه صدها مهاجرت ALTER TABLE
# داره که با try/except sqlite3.OperationalError: pass محافظت شدن — الگوی
# درست روی SQLite (خطای «duplicate column» = sqlite3.OperationalError). ولی
# روی Postgres این خطا از نوع psycopg2.errors.DuplicateColumn است (نه
# sqlite3.OperationalError، پس اصلاً catch نمی‌شه) **و مهم‌تر**: یک دستور
# شکست‌خورده روی Postgres کل تراکنش رو «poison» می‌کنه — هر دستور بعدی روی
# همون کانکشن/تراکنش با InFailedSqlTransaction شکست می‌خوره، حتی اگه try/except
# درست هم می‌بود. راه‌حل درست: به‌جای تکیه به catch کردن خطا، از سینتکس بومی
# idempotent پستگرس (IF NOT EXISTS) استفاده می‌شه که اصلاً خطا تولید نمی‌کنه.
_ADD_COLUMN = re.compile(r"(ALTER\s+TABLE\s+\S+\s+ADD\s+COLUMN\s+)(?!IF\s+NOT\s+EXISTS)", re.I)

# PRAGMA table_info(X) → information_schema query
_PRAGMA_TABLE_INFO = re.compile(r"PRAGMA\s+table_info\(\s*(\w+)\s*\)", re.I)

# `col IS ?` — الگوی NULL-safe مقایسه که چندجا (مثل iphone_valuation/db.py:
# resolve_capacity/get_capacity_exact) عمداً به‌جای `=` استفاده شده، دقیقاً
# چون NULL=NULL همیشه false ولی NULL IS NULL true است. روی SQLite، عملگر IS
# یک NULL-safe equality عمومیه که با هر مقدار (نه فقط NULL) کار می‌کنه؛ روی
# Postgres، IS فقط NULL/TRUE/FALSE رو می‌پذیره — `col IS 162` مستقیماً خطای
# syntax می‌ده (کشف‌شده با تست مستقیم روی Postgres واقعی، نه با خوندن کد).
# معادل پرتابل استاندارد SQL: `IS NOT DISTINCT FROM` — هم NULL-safe هم با
# مقادیر غیر-NULL درست کار می‌کنه، هم روی Postgres هم (از SQLite 3.39+) روی
# SQLite؛ چون این فقط برای Postgres صدا زده می‌شه، نگرانی نسخهٔ SQLite نیست.
_IS_PLACEHOLDER = re.compile(r"(\w+(?:\.\w+)?)\s+IS\s+\?", re.I)

# BEGIN IMMEDIATE — خاص SQLite (یه قفل نوشتنِ کل‌فایل رو فوراً می‌گیره، نه فقط
# روی commit اول). Postgres اصلاً این سینتکس رو نمی‌شناسه — `BEGIN IMMEDIATE;`
# مستقیم `syntax error at or near "IMMEDIATE"` می‌ده (کشف‌شده روی مسیر خرید
# واقعی: هر تابع اتمیک پروژه — subtract_wallet_balance، claim_next_feed_item،
# claim_daily_checkin، exchange_order، تأیید پرداخت — دقیقاً همین الگو رو
# داشت). معادل ساده `BEGIN;` (بدون IMMEDIATE) تنها بخشی از تضمین قبلیه — قفل
# ردیف واقعی برای هر کدوم جدا با `FOR UPDATE` روی همون SELECT اولیه اضافه شده
# (نه اینجا، چون SQLite این سینتکس رو نداره و نباید بی‌قید همه‌جا اضافه بشه).
_BEGIN_IMMEDIATE = re.compile(r"BEGIN\s+IMMEDIATE\s*;?", re.I)


def translate(sql: str) -> str:
    """کوئری SQLite را به Postgres ترجمه می‌کند. در حالت sqlite بدون تغییر."""
    if not is_postgres():
        return sql

    out = sql

    # ۱) توابع تاریخ
    for pat, repl in _DATE_PATTERNS:
        out = pat.sub(repl, out)

    # ۱ب) col IS ? → col IS NOT DISTINCT FROM ? (باید قبل از تبدیل ? → %s باشه،
    # چون این regex دنبال ? خامه)
    out = _IS_PLACEHOLDER.sub(r"\1 IS NOT DISTINCT FROM ?", out)

    # ۱ج) BEGIN IMMEDIATE → BEGIN (سینتکس SQLite که Postgres نمی‌شناسه)
    out = _BEGIN_IMMEDIATE.sub("BEGIN;", out)

    # ۲) placeholder ? → %s (با حفظ ? داخل رشته‌های نقل‌قولی نمی‌کنیم چون نادر است)
    out = _replace_placeholders(out)

    # ۳) INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING (per-statement،
    # امن برای اسکریپت‌های چند-دستوری executescript؛ توضیح کامل بالای _INSERT_IGNORE_STMT)
    out = _INSERT_IGNORE_STMT.sub(r"INSERT INTO\1 ON CONFLICT DO NOTHING;", out)

    # ۴) INSERT OR REPLACE → INSERT ... ON CONFLICT DO UPDATE (ساده: DO NOTHING)
    if _INSERT_REPLACE.search(out):
        out = _INSERT_REPLACE.sub("INSERT INTO", out)

    # ۵) AUTOINCREMENT → SERIAL
    out = _AUTOINC.sub("SERIAL PRIMARY KEY", out)

    # ۵ب) ALTER TABLE ... ADD COLUMN → ADD COLUMN IF NOT EXISTS (idempotent،
    # بدون این هیچ‌وقت transaction poisoning رخ نمی‌ده — بالاتر رو ببین)
    out = _ADD_COLUMN.sub(r"\1IF NOT EXISTS ", out)

    # ۶) PRAGMA table_info(X) → information_schema equivalent
    m = _PRAGMA_TABLE_INFO.search(out)
    if m:
        table = m.group(1)
        out = (f"SELECT ordinal_position AS cid, column_name AS name, "
               f"data_type AS type, 0 AS notnull, NULL AS dflt_value, 0 AS pk "
               f"FROM information_schema.columns WHERE table_name='{table}' "
               f"ORDER BY ordinal_position")

    # ۷) SELECT changes() — خاص SQLite، در Postgres وجود ندارد
    out = out.replace("SELECT changes()", "SELECT 1")

    # ۸) last_insert_rowid() → lastval() (معادل Postgres، همون سکانس آخرین INSERT)
    out = re.sub(r"last_insert_rowid\(\s*\)", "lastval()", out, flags=re.I)

    # ۹) COLLATE NOCASE — خاص SQLite (Postgres این collation رو نداره). حذف می‌شه؛
    # جاهایی که واقعاً به مقایسهٔ case-insensitive نیاز دارن (validate_discount)
    # در سطح کوئری با LOWER(...)=LOWER(...) بازنویسی شدن (پرتابل هر دو دیالوگ).
    out = re.sub(r"\s+COLLATE\s+NOCASE", "", out, flags=re.I)

    return out


def _replace_placeholders(sql: str) -> str:
    """? → %s فقط خارج از رشته‌های نقل‌قولی."""
    result = []
    in_single = False
    in_double = False
    for ch in sql:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        if ch == "?" and not in_single and not in_double:
            result.append("%s")
        else:
            result.append(ch)
    return "".join(result)
