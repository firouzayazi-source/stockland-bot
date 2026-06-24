"""
StockLand Backup Engine — فرمت اختصاصی .stbak
ZIP(manifest.json + data.json) با پسوند .stbak
"""
import hashlib, io, json, os, sqlite3, zipfile
from datetime import datetime

STBAK_VERSION   = "1.0"
SYSTEM_VERSION  = "2.4.1"
DB_VERSION      = "1.0"

# جداول و وابستگی‌ها
ALL_SECTIONS = {
    "users":           {"tables": ["users"],              "deps": []},
    "categories":      {"tables": ["categories"],         "deps": []},
    "products":        {"tables": ["products"],           "deps": ["categories"]},
    "orders":          {"tables": ["orders"],             "deps": ["users", "products"]},
    "wallets":         {"tables": ["wallets", "wallet_orders", "zarinpal_transactions"], "deps": ["users"]},
    "product_feed":    {"tables": ["product_feed"],       "deps": ["products"]},
    "tickets":         {"tables": ["tickets", "ticket_messages"], "deps": ["users"]},
    "partners":        {"tables": ["partners"],           "deps": ["users"]},
    "discount_codes":  {"tables": ["discount_codes", "discount_usage"], "deps": []},
    "referrals":       {"tables": ["referrals", "referral_settings"], "deps": []},
    "logs":            {"tables": ["admin_logs"],         "deps": []},
    "settings":        {"tables": ["ui_texts_custom", "other_services", "feed_alert_settings"], "deps": []},
}

SECTION_LABELS = {
    "users": "کاربران", "categories": "دسته‌بندی‌ها", "products": "محصولات",
    "orders": "سفارش‌ها", "wallets": "کیف‌پول", "product_feed": "موجودی",
    "tickets": "تیکت‌ها", "partners": "همکاران", "discount_codes": "کدهای تخفیف",
    "referrals": "معرفی", "logs": "لاگ‌ها", "settings": "تنظیمات",
}

# وابستگی‌های هوشمند — اگه section انتخاب شد، اینا هم باید باشن
SMART_DEPS = {
    "products":     ["categories"],
    "orders":       ["users", "products"],
    "wallets":      ["users"],
    "product_feed": ["products"],
    "tickets":      ["users"],
    "partners":     ["users"],
}


def resolve_sections(selected: list[str]) -> list[str]:
    """حل وابستگی‌ها — sections مورد نیاز را برمی‌گرداند."""
    result = set(selected)
    for s in list(result):
        for dep in SMART_DEPS.get(s, []):
            result.add(dep)
    # ترتیب صحیح برای restore
    order = list(ALL_SECTIONS.keys())
    return [s for s in order if s in result]


def _read_table(conn: sqlite3.Connection, table: str) -> list[dict]:
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM {table};").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _count_records(data: dict) -> int:
    return sum(len(rows) for rows in data.values())


def create_stbak(db_path: str, sections: list[str] | None = None,
                 backup_mode: str = "full") -> bytes:
    """
    ساخت فایل .stbak و برگرداندن bytes آن.
    sections=None → بکاپ کامل
    """
    if sections is None:
        sections = list(ALL_SECTIONS.keys())
        backup_mode = "full"
    else:
        sections = resolve_sections(sections)
        backup_mode = "custom"

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000;")

    # خواندن داده‌ها
    data: dict[str, dict[str, list]] = {}
    for sec in sections:
        sec_data = {}
        for table in ALL_SECTIONS[sec]["tables"]:
            sec_data[table] = _read_table(conn, table)
        data[sec] = sec_data
    conn.close()

    # ساخت JSON داده‌ها
    data_json = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    checksum   = hashlib.sha256(data_json).hexdigest()

    # Manifest
    manifest = {
        "type":            "stockland_backup",
        "backup_format":   "stbak",
        "version":         STBAK_VERSION,
        "system_version":  SYSTEM_VERSION,
        "database_version": DB_VERSION,
        "created_at":      datetime.now().isoformat(timespec="seconds"),
        "backup_mode":     backup_mode,
        "sections":        sections,
        "section_labels":  {s: SECTION_LABELS.get(s, s) for s in sections},
        "records":         _count_records(data),
        "checksum":        checksum,
        "checksum_algo":   "sha256",
    }
    manifest_json = json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8")

    # ZIP → .stbak bytes
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json", manifest_json)
        zf.writestr("data.json",     data_json)
    return buf.getvalue()


def stbak_filename(mode: str = "full") -> str:
    ts = datetime.now().strftime("%Y_%m_%d_%H%M")
    return f"stockland_backup_{ts}_{mode}.stbak"


# ── Restore ──────────────────────────────────────────────────────────────────

class StbakError(Exception):
    pass


def validate_stbak(raw: bytes) -> dict:
    """
    اعتبارسنجی فایل .stbak — manifest + checksum.
    Returns manifest dict if valid. Raises StbakError otherwise.
    """
    try:
        buf = io.BytesIO(raw)
        if not zipfile.is_zipfile(buf):
            raise StbakError("فایل ZIP معتبر نیست — احتمالاً فایل خراب است")
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            if "manifest.json" not in names:
                raise StbakError("فایل manifest.json داخل بکاپ یافت نشد")
            if "data.json" not in names:
                raise StbakError("فایل data.json داخل بکاپ یافت نشد")
            manifest  = json.loads(zf.read("manifest.json").decode("utf-8"))
            data_json = zf.read("data.json")
    except StbakError:
        raise
    except Exception as ex:
        raise StbakError(f"خطا در خواندن فایل: {ex}")

    # بررسی type
    if manifest.get("type") != "stockland_backup":
        raise StbakError("این فایل متعلق به سیستم StockLand نیست")

    # بررسی checksum
    actual = hashlib.sha256(data_json).hexdigest()
    if actual != manifest.get("checksum"):
        raise StbakError("Checksum مطابقت ندارد — فایل بکاپ خراب یا دستکاری شده است")

    # بررسی نسخه فرمت
    fmt = manifest.get("version", "")
    if fmt and fmt != STBAK_VERSION:
        raise StbakError(f"نسخه فرمت {fmt} با نسخه فعلی {STBAK_VERSION} سازگار نیست")

    return manifest


def restore_stbak(raw: bytes, db_path: str) -> dict:
    """
    بازیابی از .stbak.
    Returns summary dict.
    """
    manifest = validate_stbak(raw)
    buf = io.BytesIO(raw)
    with zipfile.ZipFile(buf, "r") as zf:
        data: dict = json.loads(zf.read("data.json").decode("utf-8"))

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=OFF;")

    restored = {}
    errors   = []

    try:
        with conn:
            for sec, sec_data in data.items():
                for table, rows in sec_data.items():
                    if not rows:
                        continue
                    try:
                        # پاک کردن جدول قبل از درج
                        conn.execute(f"DELETE FROM {table};")
                        if rows:
                            cols   = list(rows[0].keys())
                            ph     = ", ".join("?" * len(cols))
                            col_s  = ", ".join(f'"{c}"' for c in cols)
                            sql    = f'INSERT OR REPLACE INTO {table} ({col_s}) VALUES ({ph});'
                            conn.executemany(sql, [[r.get(c) for c in cols] for r in rows])
                        restored[table] = len(rows)
                    except Exception as ex:
                        errors.append(f"{table}: {ex}")
    finally:
        conn.close()

    return {
        "manifest": manifest,
        "restored": restored,
        "errors":   errors,
        "total":    sum(restored.values()),
    }


# ── Factory Reset ─────────────────────────────────────────────────────────────

RESET_SECTIONS = {
    "users":          ["users"],
    "categories":     ["categories"],
    "products":       ["products", "product_feed"],
    "orders":         ["orders", "pending_deliveries"],
    "wallets":        ["wallets", "wallet_orders", "zarinpal_transactions"],
    "tickets":        ["tickets", "ticket_messages"],
    "partners":       ["partners"],
    "discount_codes": ["discount_codes", "discount_usage"],
    "referrals":      ["referrals"],
    "logs":           ["admin_logs"],
}

RESET_LABELS = {
    "users": "کاربران", "categories": "دسته‌بندی‌ها", "products": "محصولات + موجودی",
    "orders": "سفارش‌ها", "wallets": "کیف‌پول", "tickets": "تیکت‌ها",
    "partners": "همکاران", "discount_codes": "کدهای تخفیف",
    "referrals": "معرفی", "logs": "لاگ‌ها",
}

# اگه یه section حذف بشه، اینا هم باید حذف بشن
RESET_DEPS = {
    "users":      ["orders", "wallets", "tickets", "partners", "referrals"],
    "products":   ["orders", "product_feed"],
    "categories": ["products"],
}


def resolve_reset_sections(selected: list[str]) -> list[str]:
    result = set(selected)
    for s in list(result):
        for dep in RESET_DEPS.get(s, []):
            result.add(dep)
    return list(result)


def factory_reset(db_path: str, sections: list[str] | None = None) -> dict:
    """
    ریست انتخابی یا کامل.
    sections=None → ریست کامل
    """
    if sections is None:
        sections = list(RESET_SECTIONS.keys())
    else:
        sections = resolve_reset_sections(sections)

    tables_to_clear = []
    for sec in sections:
        tables_to_clear.extend(RESET_SECTIONS.get(sec, []))
    tables_to_clear = list(dict.fromkeys(tables_to_clear))  # dedup حفظ ترتیب

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000;")
    conn.execute("PRAGMA foreign_keys=OFF;")
    cleared = {}
    errors  = []
    try:
        with conn:
            for t in tables_to_clear:
                try:
                    cnt = conn.execute(f"SELECT COUNT(*) FROM {t};").fetchone()[0]
                    conn.execute(f"DELETE FROM {t};")
                    cleared[t] = cnt
                except Exception as ex:
                    errors.append(f"{t}: {ex}")
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name IN ({});".format(
                    ",".join(f'"{t}"' for t in tables_to_clear)))
            except Exception:
                pass
    finally:
        conn.close()

    return {"cleared": cleared, "errors": errors,
            "total_deleted": sum(cleared.values())}
