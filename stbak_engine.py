"""
StockLand Backup Engine v2 — ماژول‌محور با وابستگی هوشمند
"""
import hashlib, io, json, os, sqlite3, zipfile
from datetime import datetime

STBAK_VERSION  = "1.0"
SYSTEM_VERSION = "2.4.1"
DB_VERSION     = "1.0"

# ── تعریف ماژول‌ها (module-based, not table-based) ─────────────────────────
MODULES = {
    "settings": {
        "label": "⚙️ تنظیمات سیستم",
        "tables": [
            "ui_texts_custom", "ui_texts", "other_services",
            "feed_alert_settings", "panel_theme", "admin_preferences",
            "bot_config",
        ],
        "deps": [],
    },
    "admins": {
        "label": "🛡 ادمین‌ها",
        "tables": ["admins"],
        "deps": [],
    },
    "users": {
        "label": "👥 کاربران",
        "tables": ["users"],
        "deps": [],
    },
    "wallets": {
        "label": "💰 کیف‌پول",
        "tables": ["wallets", "wallet_orders", "zarinpal_transactions",
                   "card_receipts", "wallet_admin_log"],
        "deps": ["users"],
    },
    "categories": {
        "label": "🗂 دسته‌بندی‌ها",
        "tables": ["categories"],
        "deps": [],
    },
    "products": {
        "label": "📦 محصولات",
        "tables": ["products", "product_feed", "stock_subscriptions", "feed_batches",
                   "product_faqs", "product_ratings"],
        "deps": ["categories"],
    },
    "orders": {
        "label": "🧾 سفارش‌ها",
        "tables": ["orders", "pending_deliveries", "delivery_messages"],
        "deps": ["users", "products"],
    },
    "tickets": {
        "label": "🎫 تیکت‌ها و گفتگوها",
        "tables": ["tickets", "ticket_messages"],
        "deps": ["users"],
    },
    "partners": {
        "label": "🤝 همکاران",
        "tables": [
            "partners",
            "partner_tiers", "partner_commission",
            "partner_wallets", "partner_transactions",
            "partner_payouts", "partner_payout_settings",
            "partner_bank_info",
        ],
        "deps": ["users"],
    },
    "sellers": {
        "label": "🛍 فروشندگان",
        "tables": ["sellers", "seller_levels", "seller_commissions", "seller_payouts"],
        "deps": ["users"],
    },
    "accounting": {
        "label": "📊 حسابداری و هزینه‌ها",
        "tables": ["expenses", "expense_categories"],
        "deps": [],
    },
    "discounts": {
        "label": "🏷 کدهای تخفیف",
        "tables": ["discount_codes", "discount_usage"],
        "deps": [],
    },
    "referrals": {
        "label": "👤 معرفی کاربران",
        "tables": ["referrals", "referral_settings"],
        "deps": ["users"],
    },
    "notes": {
        "label": "📝 یادداشت مدیران",
        "tables": ["admin_notes", "admin_note_replies"],
        "deps": [],
    },
    "logs": {
        "label": "📋 لاگ‌ها",
        "tables": ["admin_logs"],
        "deps": [],
    },
}

# backward compat aliases
ALL_SECTIONS   = MODULES
SECTION_LABELS = {k: v["label"] for k, v in MODULES.items()}
RESET_LABELS   = SECTION_LABELS.copy()

# وابستگی‌های هوشمند — اگه X انتخاب شد، اینا هم اضافه می‌شن
SMART_DEPS = {mod: MODULES[mod]["deps"] for mod in MODULES}

# وابستگی‌های ریست معکوس — اگه X ریست شد، اینا هم باید ریست بشن
RESET_CASCADE = {
    "users":      ["wallets", "orders", "tickets", "partners", "referrals"],
    "categories": ["products"],
    "products":   ["orders"],
    "partners":   [],  # partner data is self-contained
}


def resolve_sections(selected: list) -> list:
    """وابستگی‌های forward را حل می‌کند."""
    result = set(selected)
    changed = True
    while changed:
        changed = False
        for s in list(result):
            for dep in SMART_DEPS.get(s, []):
                if dep not in result:
                    result.add(dep)
                    changed = True
    return [m for m in MODULES if m in result]


def resolve_reset(selected: list) -> list:
    """وابستگی‌های cascade برای ریست را حل می‌کند."""
    result = set(selected)
    changed = True
    while changed:
        changed = False
        for s in list(result):
            for dep in RESET_CASCADE.get(s, []):
                if dep not in result:
                    result.add(dep)
                    changed = True
    return [m for m in MODULES if m in result]


def _read_table(conn: sqlite3.Connection, table: str) -> list:
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM \"{table}\";").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def create_stbak(db_path: str, modules: list = None, progress_cb=None) -> bytes:
    """
    ساخت .stbak — اگه modules=None باشه کامله.
    progress_cb(pct: int) برای آپدیت پیشرفت.
    """
    if modules is None:
        selected = list(MODULES.keys())
        mode = "full"
    else:
        selected = resolve_sections(modules)
        mode = "custom"

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA busy_timeout=30000;")

    data = {}
    total = len(selected)
    for i, mod in enumerate(selected):
        sec_data = {}
        for table in MODULES[mod]["tables"]:
            sec_data[table] = _read_table(conn, table)
        data[mod] = sec_data
        if progress_cb:
            progress_cb(int(10 + (i + 1) / total * 70))
    conn.close()

    data_json = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    checksum  = hashlib.sha256(data_json).hexdigest()
    total_rec = sum(len(r) for sd in data.values() for r in sd.values())

    manifest = {
        "type": "stockland_backup", "backup_format": "stbak",
        "version": STBAK_VERSION, "system_version": SYSTEM_VERSION,
        "database_version": DB_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "backup_mode": mode, "modules": selected,
        "records": total_rec, "checksum": checksum, "checksum_algo": "sha256",
    }
    if progress_cb:
        progress_cb(85)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode())
        zf.writestr("data.json", data_json)

    if progress_cb:
        progress_cb(100)
    return buf.getvalue()


def stbak_filename(mode: str = "full") -> str:
    ts = datetime.now().strftime("%Y_%m_%d_%H%M")
    return f"stockland_backup_{ts}_{mode}.stbak"


class StbakError(Exception):
    pass


def validate_stbak(raw: bytes) -> dict:
    try:
        buf = io.BytesIO(raw)
        if not zipfile.is_zipfile(buf):
            raise StbakError("فایل ZIP معتبر نیست")
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            names = zf.namelist()
            if "manifest.json" not in names:
                raise StbakError("manifest.json یافت نشد")
            if "data.json" not in names:
                raise StbakError("data.json یافت نشد")
            manifest  = json.loads(zf.read("manifest.json").decode())
            data_json = zf.read("data.json")
    except StbakError:
        raise
    except Exception as ex:
        raise StbakError(f"خطا در خواندن فایل: {ex}")

    if manifest.get("type") != "stockland_backup":
        raise StbakError("این فایل متعلق به StockLand نیست")
    if hashlib.sha256(data_json).hexdigest() != manifest.get("checksum"):
        raise StbakError("Checksum مطابقت ندارد — فایل خراب است")
    return manifest


def restore_stbak(raw: bytes, db_path: str, progress_cb=None) -> dict:
    manifest = validate_stbak(raw)
    buf = io.BytesIO(raw)
    with zipfile.ZipFile(buf, "r") as zf:
        data = json.loads(zf.read("data.json").decode())

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys=OFF;")
    restored, errors = {}, []
    mods = list(data.items())
    total = len(mods)
    try:
        with conn:
            for i, (mod, sec_data) in enumerate(mods):
                for table, rows in sec_data.items():
                    if not rows:
                        continue
                    try:
                        conn.execute(f'DELETE FROM "{table}";')
                        cols  = list(rows[0].keys())
                        ph    = ",".join("?" * len(cols))
                        col_s = ",".join(f'"{c}"' for c in cols)
                        conn.executemany(
                            f'INSERT OR REPLACE INTO "{table}" ({col_s}) VALUES ({ph});',
                            [[r.get(c) for c in cols] for r in rows]
                        )
                        restored[table] = len(rows)
                    except Exception as ex:
                        errors.append(f"{table}: {ex}")
                if progress_cb:
                    progress_cb(int(10 + (i + 1) / total * 85))
    finally:
        conn.close()

    if progress_cb:
        progress_cb(100)
    return {"manifest": manifest, "restored": restored,
            "errors": errors, "total": sum(restored.values())}


def factory_reset(db_path: str, modules: list = None, progress_cb=None) -> dict:
    if modules is None:
        selected = list(MODULES.keys())
    else:
        selected = resolve_reset(modules)

    tables = []
    for mod in selected:
        tables.extend(MODULES.get(mod, {}).get("tables", []))
    tables = list(dict.fromkeys(tables))

    conn = sqlite3.connect(db_path, timeout=30)
    conn.execute("PRAGMA foreign_keys=OFF;")
    cleared, errors = {}, []
    total = len(tables)
    try:
        with conn:
            for i, t in enumerate(tables):
                try:
                    cnt = conn.execute(f'SELECT COUNT(*) FROM "{t}";').fetchone()[0]
                    conn.execute(f'DELETE FROM "{t}";')
                    cleared[t] = cnt
                except Exception as ex:
                    errors.append(f"{t}: {ex}")
                if progress_cb:
                    progress_cb(int(10 + (i + 1) / total * 85))
            try:
                conn.execute("DELETE FROM sqlite_sequence WHERE name IN ({});".format(
                    ",".join(f'"{t}"' for t in tables)))
            except Exception:
                pass
    finally:
        conn.close()

    if progress_cb:
        progress_cb(100)
    return {"cleared": cleared, "errors": errors,
            "total_deleted": sum(cleared.values())}
