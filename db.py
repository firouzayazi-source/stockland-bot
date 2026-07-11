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

# الگوهای تاریخ/زمان
_DATE_PATTERNS = [
    # datetime('now','localtime') → NOW()
    (re.compile(r"datetime\(\s*'now'\s*,\s*'localtime'\s*\)", re.I), "NOW()"),
    (re.compile(r"datetime\(\s*'now'\s*\)", re.I), "NOW()"),
    (re.compile(r"date\(\s*'now'\s*,\s*'localtime'\s*\)", re.I), "CURRENT_DATE"),
    (re.compile(r"date\(\s*'now'\s*\)", re.I), "CURRENT_DATE"),
    # strftime('%Y-%m-%d', x) → to_char(x,'YYYY-MM-DD')
    (re.compile(r"strftime\(\s*'%Y-%m-%d'\s*,\s*([^)]+)\)", re.I), r"to_char(\1,'YYYY-MM-DD')"),
    (re.compile(r"strftime\(\s*'%Y-%m'\s*,\s*([^)]+)\)", re.I), r"to_char(\1,'YYYY-MM')"),
]

# INSERT OR IGNORE / INSERT OR REPLACE
_INSERT_IGNORE = re.compile(r"INSERT\s+OR\s+IGNORE\s+INTO", re.I)
_INSERT_REPLACE = re.compile(r"INSERT\s+OR\s+REPLACE\s+INTO", re.I)

# AUTOINCREMENT
_AUTOINC = re.compile(r"INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT", re.I)

# PRAGMA table_info(X) → information_schema query
_PRAGMA_TABLE_INFO = re.compile(r"PRAGMA\s+table_info\(\s*(\w+)\s*\)", re.I)


def translate(sql: str) -> str:
    """کوئری SQLite را به Postgres ترجمه می‌کند. در حالت sqlite بدون تغییر."""
    if not is_postgres():
        return sql

    out = sql

    # ۱) توابع تاریخ
    for pat, repl in _DATE_PATTERNS:
        out = pat.sub(repl, out)

    # ۲) placeholder ? → %s (با حفظ ? داخل رشته‌های نقل‌قولی نمی‌کنیم چون نادر است)
    out = _replace_placeholders(out)

    # ۳) INSERT OR IGNORE → INSERT ... ON CONFLICT DO NOTHING
    if _INSERT_IGNORE.search(out):
        out = _INSERT_IGNORE.sub("INSERT INTO", out)
        if "ON CONFLICT" not in out.upper():
            out = out.rstrip().rstrip(";") + " ON CONFLICT DO NOTHING"

    # ۴) INSERT OR REPLACE → INSERT ... ON CONFLICT DO UPDATE (ساده: DO NOTHING)
    if _INSERT_REPLACE.search(out):
        out = _INSERT_REPLACE.sub("INSERT INTO", out)

    # ۵) AUTOINCREMENT → SERIAL
    out = _AUTOINC.sub("SERIAL PRIMARY KEY", out)

    # ۶) PRAGMA table_info(X) → information_schema equivalent
    m = _PRAGMA_TABLE_INFO.search(out)
    if m:
        table = m.group(1)
        out = (f"SELECT ordinal_position AS cid, column_name AS name, "
               f"data_type AS type, 0 AS notnull, NULL AS dflt_value, 0 AS pk "
               f"FROM information_schema.columns WHERE table_name='{table}' "
               f"ORDER BY ordinal_position")

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
