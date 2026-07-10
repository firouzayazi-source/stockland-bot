#!/usr/bin/env python3
"""
migrate_to_postgres.py — مهاجرت داده از SQLite به PostgreSQL
──────────────────────────────────────────────────────────────
این اسکریپت روی سرور اجرا می‌شود (بعد از نصب Postgres).

مراحل:
  1) به SQLite فعلی وصل می‌شود و ساختار جدول‌ها را می‌خواند
  2) جدول‌ها را در Postgres می‌سازد (با نوع‌های سازگار)
  3) همه‌ی داده‌ها را کپی می‌کند
  4) sequence ها را تنظیم می‌کند

اجرا:
  DATABASE_URL="postgresql://user:pass@localhost/stockland" \\
  SQLITE_PATH="/opt/stockland/app/data/bot.db" \\
  python3 migrate_to_postgres.py

⚠️ قبل از اجرا حتماً بکاپ بگیرید. این اسکریپت داده را فقط می‌خواند از SQLite
   و می‌نویسد در Postgres — به SQLite دست نمی‌زند.
"""
import os
import sys
import sqlite3


# نگاشت نوع SQLite → Postgres
TYPE_MAP = {
    "INTEGER": "BIGINT",
    "REAL": "DOUBLE PRECISION",
    "TEXT": "TEXT",
    "BLOB": "BYTEA",
    "NUMERIC": "NUMERIC",
    "": "TEXT",
}


def sqlite_type_to_pg(sqlite_type: str, is_pk: bool) -> str:
    t = (sqlite_type or "").upper().strip()
    # کلید اصلی AUTOINCREMENT → BIGSERIAL
    if is_pk and "INT" in t:
        return "BIGSERIAL PRIMARY KEY"
    for k, v in TYPE_MAP.items():
        if k and k in t:
            return v
    if "INT" in t:
        return "BIGINT"
    if "CHAR" in t or "CLOB" in t:
        return "TEXT"
    return "TEXT"


def get_tables(sconn) -> list:
    rows = sconn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
    ).fetchall()
    return [r[0] for r in rows]


def get_columns(sconn, table: str) -> list:
    """[(name, type, is_pk), ...]"""
    rows = sconn.execute(f"PRAGMA table_info({table});").fetchall()
    return [(r[1], r[2], bool(r[5])) for r in rows]


def migrate():
    sqlite_path = os.getenv("SQLITE_PATH", "")
    pg_dsn = os.getenv("DATABASE_URL", "")
    if not sqlite_path or not os.path.exists(sqlite_path):
        print(f"❌ SQLITE_PATH نامعتبر: {sqlite_path}")
        sys.exit(1)
    if not pg_dsn:
        print("❌ DATABASE_URL تنظیم نشده")
        sys.exit(1)

    try:
        import psycopg2
    except ImportError:
        print("❌ psycopg2 نصب نیست. اجرا کنید: pip install psycopg2-binary")
        sys.exit(1)

    sconn = sqlite3.connect(sqlite_path)
    sconn.row_factory = sqlite3.Row
    pconn = psycopg2.connect(pg_dsn)
    pcur = pconn.cursor()

    tables = get_tables(sconn)
    print(f"📋 {len(tables)} جدول یافت شد\n")

    for table in tables:
        cols = get_columns(sconn, table)
        if not cols:
            continue

        # ساخت جدول در Postgres
        col_defs = []
        for name, ctype, is_pk in cols:
            pg_type = sqlite_type_to_pg(ctype, is_pk)
            col_defs.append(f'"{name}" {pg_type}')
        create_sql = f'CREATE TABLE IF NOT EXISTS "{table}" ({", ".join(col_defs)});'
        try:
            pcur.execute(f'DROP TABLE IF EXISTS "{table}" CASCADE;')
            pcur.execute(create_sql)
            pconn.commit()
        except Exception as ex:
            print(f"⚠️  {table}: خطای ساخت جدول: {ex}")
            pconn.rollback()
            continue

        # کپی داده
        rows = sconn.execute(f"SELECT * FROM {table};").fetchall()
        if rows:
            col_names = [c[0] for c in cols]
            placeholders = ", ".join(["%s"] * len(col_names))
            quoted_cols = ", ".join(f'"{c}"' for c in col_names)
            insert_sql = f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders});'
            copied = 0
            for row in rows:
                try:
                    pcur.execute(insert_sql, tuple(row))
                    copied += 1
                except Exception as ex:
                    print(f"⚠️  {table} ردیف رد شد: {str(ex)[:60]}")
                    pconn.rollback()
                    continue
            pconn.commit()
            print(f"✅ {table}: {copied}/{len(rows)} ردیف")
        else:
            print(f"✅ {table}: خالی")

        # تنظیم sequence برای کلید اصلی
        pk_col = next((c[0] for c in cols if c[2] and "INT" in (c[1] or "").upper()), None)
        if pk_col:
            try:
                pcur.execute(
                    f'SELECT setval(pg_get_serial_sequence(\'"{table}"\', \'{pk_col}\'), '
                    f'COALESCE((SELECT MAX("{pk_col}") FROM "{table}"), 1));'
                )
                pconn.commit()
            except Exception:
                pconn.rollback()

    sconn.close()
    pconn.close()
    print("\n🎯 مهاجرت کامل شد!")
    print("حالا در env سرویس تنظیم کنید:")
    print("  DB_DIALECT=postgres")
    print(f"  DATABASE_URL={pg_dsn}")
    print("و سرویس را restart کنید.")


if __name__ == "__main__":
    migrate()
