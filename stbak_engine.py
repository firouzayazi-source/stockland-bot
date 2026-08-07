"""
StockLand Backup Engine v3 — ماژول‌محور + کشف پویای جدول‌های تازه + فایل‌های مدیا +
اعتبارسنجی قبل از ذخیره + بازیابی مهاجرت‌آگاه با بکاپ ایمنی خودکار

نکتهٔ حیاتی این نسخه: قبلاً بکاپ فقط جدول‌هایی رو می‌گرفت که دستی به MODULES اضافه
شده بودن — هر جدول تازه‌ای که فراموش می‌شد اضافه بشه (که طبق مستندات پروژه چندبار
اتفاق افتاده بود)، از بکاپ کامل جا می‌موند. حالا بکاپ «کامل» (mode=full) خودش
جدول‌های پوشش‌نداده رو کشف و اضافه می‌کنه — دیگه نیازی به یادآوری دستی نیست.
"""
import glob, hashlib, io, json, os, sqlite3, zipfile
from datetime import datetime

STBAK_VERSION  = "2.0"
SYSTEM_VERSION = "2.5.0"
DB_VERSION     = "1.0"

# ── تعریف ماژول‌ها (module-based, not table-based) ─────────────────────────
MODULES = {
    "settings": {
        "label": "⚙️ تنظیمات سیستم",
        "tables": [
            "ui_texts_custom", "ui_texts", "other_services",
            "feed_alert_settings", "panel_theme", "admin_preferences",
            "bot_config", "app_content", "daily_checkins", "favorites",
            "user_notifications",
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
    "growth": {
        "label": "🚀 رشد و فروش",
        "tables": ["flash_sales", "winback_log"],
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
    "iphone_valuation": {
        "label": "📱 کارشناسی قیمت آیفون",
        "tables": [
            "iv_models", "iv_storages", "iv_colors", "iv_parts", "iv_capacities",
            "iv_coefficients", "iv_score_weights", "iv_fx_sources",
            "iv_transactions", "iv_valuations",
        ],
        "deps": [],
    },
}

# نامی که کشف خودکار زیرش قرار می‌گیره — همیشه به مانیفست/داده اضافه می‌شه (نه به
# چک‌باکس‌های پنل، چون تعداد/محتواش تا لحظهٔ بکاپ مشخص نیست)
_AUTO_MODULE_KEY = "_auto_discovered"
_AUTO_MODULE_LABEL = "🔍 کشف‌شدهٔ خودکار (جدول‌های تازه)"

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

_MEDIA_ZIP_PREFIX = "media/"


def _media_dir() -> str:
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "app_media")


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


def _all_table_names(conn: sqlite3.Connection) -> list:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' "
        "AND name NOT LIKE 'sqlite_%' AND name != 'sqlite_sequence';"
    ).fetchall()
    return [r[0] for r in rows]


def _known_tables() -> set:
    known = set()
    for mod in MODULES.values():
        known.update(mod["tables"])
    return known


def discover_new_tables(db_path: str) -> list:
    """جدول‌هایی که در دیتابیس واقعی هستن ولی هیچ ماژولی توی MODULES پوشش‌شون نمی‌ده —
    قبلاً باید دستی به MODULES اضافه می‌شدن (قانون پروژه) و چندبار فراموش شده بود.
    بکاپ کامل دیگه به این لیست دستی وابسته نیست."""
    conn = sqlite3.connect(db_path, timeout=30)
    try:
        found = set(_all_table_names(conn))
    finally:
        conn.close()
    return sorted(found - _known_tables())


def _read_table(conn: sqlite3.Connection, table: str) -> list:
    try:
        conn.row_factory = sqlite3.Row
        rows = conn.execute(f"SELECT * FROM \"{table}\";").fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _collect_media_files() -> list:
    """لیست (مسیر مطلق، مسیر داخل zip) همهٔ فایل‌های app_media — عکس محصول، آواتار،
    فایل‌های آموزش، رسیدها و غیره. قبلاً هیچ‌کدوم این‌ها توی بکاپ نبودن."""
    media_dir = _media_dir()
    if not os.path.isdir(media_dir):
        return []
    out = []
    for root, _dirs, files in os.walk(media_dir):
        for fn in files:
            abs_path = os.path.join(root, fn)
            rel_path = os.path.relpath(abs_path, media_dir)
            out.append((abs_path, _MEDIA_ZIP_PREFIX + rel_path.replace(os.sep, "/")))
    return out


def _dry_run_check(db_path: str, data: dict) -> list:
    """اعتبارسنجی «امکان Restore» قبل از ارائهٔ بکاپ به‌عنوان موفق — بدون دست‌زدن به
    دیتابیس واقعی: یک دیتابیس موقت در حافظه می‌سازه، ساختار جدول‌های واقعی رو از
    دیتابیس فعلی کپی می‌کنه، و سعی می‌کنه ردیف‌های بکاپ رو داخلش درج کنه. اگه جایی
    خطا بده، توی manifest به‌عنوان هشدار (نه شکست کامل بکاپ) ثبت می‌شه."""
    warnings = []
    try:
        src = sqlite3.connect(db_path, timeout=30)
        src.row_factory = sqlite3.Row
        scratch = sqlite3.connect(":memory:")
        try:
            schema_rows = src.execute(
                "SELECT name, sql FROM sqlite_master WHERE type='table' AND sql IS NOT NULL;"
            ).fetchall()
            schemas = {r["name"]: r["sql"] for r in schema_rows}
            for mod, sec_data in data.items():
                for table, rows in sec_data.items():
                    if not rows:
                        continue
                    sql = schemas.get(table)
                    if not sql:
                        warnings.append(f"{table}: ساختار جدول در دیتابیس فعلی یافت نشد")
                        continue
                    try:
                        scratch.execute(sql)
                    except Exception as ex:
                        warnings.append(f"{table}: ساخت ساختار آزمایشی ناموفق ({ex})")
                        continue
                    sample = rows[:5]  # فقط چند ردیف اول برای سرعت — هدف تشخیص mismatch ستونیه نه صحت کامل
                    cols = list(sample[0].keys())
                    col_s = ",".join(f'"{c}"' for c in cols)
                    ph = ",".join("?" * len(cols))
                    try:
                        scratch.executemany(
                            f'INSERT INTO "{table}" ({col_s}) VALUES ({ph});',
                            [[r.get(c) for c in cols] for r in sample]
                        )
                    except Exception as ex:
                        warnings.append(f"{table}: درج آزمایشی ناموفق ({ex})")
        finally:
            src.close()
            scratch.close()
    except Exception as ex:
        warnings.append(f"اعتبارسنجی آزمایشی کامل نشد: {ex}")
    return warnings


def create_stbak(db_path: str, modules: list = None, progress_cb=None,
                  include_media: bool = True, validate: bool = True) -> bytes:
    """
    ساخت .stbak — اگه modules=None باشه کامله (و شامل جدول‌های تازه‌کشف‌شده هم می‌شه).
    progress_cb(pct: int) برای آپدیت پیشرفت.
    validate=False فقط برای بکاپ ایمنی داخلی قبل از Restore استفاده می‌شه — چون اون
    بکاپ از خودِ اسکیمای زندهٔ دیتابیس همون لحظه خونده می‌شه، امکان mismatch ستونی
    اصلاً وجود نداره، پس dry-run (که خودش تقریباً دوبرابر کردن هزینهٔ بکاپه چون کل
    داده رو دوباره توی یه دیتابیس آزمایشی درج می‌کنه) لازم نیست. برای بکاپ‌های
    دانلودی/قابل‌بازیابیِ آینده (که ممکنه اسکیمای کد عوض شده باشه) همیشه True بمونه.
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
    total = len(selected) + 1  # +1 برای مرحلهٔ کشف خودکار
    for i, mod in enumerate(selected):
        sec_data = {}
        for table in MODULES[mod]["tables"]:
            sec_data[table] = _read_table(conn, table)
        data[mod] = sec_data
        if progress_cb:
            progress_cb(int(10 + (i + 1) / total * 60))

    new_tables = []
    if mode == "full":
        new_tables = discover_new_tables(db_path)
        if new_tables:
            auto_data = {}
            for table in new_tables:
                auto_data[table] = _read_table(conn, table)
            data[_AUTO_MODULE_KEY] = auto_data
    conn.close()
    if progress_cb:
        progress_cb(75)

    data_json = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
    checksum  = hashlib.sha256(data_json).hexdigest()
    total_rec = sum(len(r) for sd in data.values() for r in sd.values())

    media_files = _collect_media_files() if include_media else []
    media_bytes_total = sum(os.path.getsize(p) for p, _ in media_files) if media_files else 0

    warnings = _dry_run_check(db_path, data) if validate else []

    manifest = {
        "type": "stockland_backup", "backup_format": "stbak",
        "version": STBAK_VERSION, "system_version": SYSTEM_VERSION,
        "database_version": DB_VERSION,
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "backup_mode": mode, "modules": selected,
        "auto_discovered_tables": new_tables,
        "records": total_rec, "checksum": checksum, "checksum_algo": "sha256",
        "media_included": bool(media_files), "media_files": len(media_files),
        "media_bytes": media_bytes_total,
        "validation_warnings": warnings,
    }
    if progress_cb:
        progress_cb(88)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        zf.writestr("manifest.json",
                    json.dumps(manifest, ensure_ascii=False, indent=2).encode())
        zf.writestr("data.json", data_json)
        for abs_path, arc_path in media_files:
            try:
                # عکس/ویدیو از قبل فرمت فشرده‌ست (JPEG/PNG/MP4) — DEFLATE کردنشون
                # فقط CPU هدر می‌ده بدون کاهش حجم، و روی بکاپ‌های با مدیای زیاد
                # (خصوصاً ویدیوی آموزشی) دقیقاً همون کندی گزارش‌شده رو ایجاد می‌کرد.
                zf.write(abs_path, arc_path, compress_type=zipfile.ZIP_STORED)
            except Exception:
                pass  # یک فایل مدیای خراب/غیرقابل‌خواندن نباید کل بکاپ رو متوقف کنه

    raw = buf.getvalue()
    # اعتبارسنجی نهایی خودِ فایل ساخته‌شده — قبل از برگردوندن به‌عنوان بکاپ موفق
    # (بخش «اعتبارسنجی Backup»: سالم بودن فایل + عدم خرابی + کامل بودن چک‌سام)
    validate_stbak(raw)

    if progress_cb:
        progress_cb(100)
    return raw


def _jalali_today_compact() -> str:
    """تاریخ امروز به‌صورت جلالی، فرمت YYYYMMDD (۸ رقم لاتین، بدون جداکننده) —
    بدون وابستگی به پکیج خارجی؛ الگوریتم استاندارد تبدیل میلادی→جلالی."""
    gy, gm, gd = datetime.now().timetuple()[:3]
    g_d_m = [0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334]
    if gy > 1600:
        jy = 979
        gy -= 1600
    else:
        jy = 0
        gy -= 621
    gy2 = gy + 1 if gm > 2 else gy
    days = (365 * gy) + ((gy2 + 3) // 4) - ((gy2 + 99) // 100) + ((gy2 + 399) // 400) - 80 + gd + g_d_m[gm - 1]
    jy += 33 * (days // 12053)
    days %= 12053
    jy += 4 * (days // 1461)
    days %= 1461
    if days > 365:
        jy += (days - 1) // 365
        days = (days - 1) % 365
    if days < 186:
        jm = 1 + days // 31
        jd = 1 + (days % 31)
    else:
        jm = 7 + (days - 186) // 30
        jd = 1 + ((days - 186) % 30)
    return f"{jy:04d}{jm:02d}{jd:02d}"


def stbak_filename(mode: str = "full", backup_dir: str = None, prefix: str = "stockland_backup_") -> str:
    """اسم فایل بکاپ — تاریخ جلالی فشرده (بدون جداکننده، ارقام لاتین)، مثل
    stockland_backup_14050509_full.stbak. اگه backup_dir داده بشه، همون دایرکتوری
    برای برخورد اسم چک می‌شه؛ اگه بکاپ دیگری با همین تاریخ/mode از قبل اونجا
    باشه، پسوند -2, -3, ... اضافه می‌شه (همون پروتکلی که برای بکاپ nginx هم
    استفاده شد) — تا دو بکاپ توی یه روز (مثلاً دستی+خودکار) هم‌نام نشن."""
    jdate = _jalali_today_compact()
    base = f"{prefix}{jdate}_{mode}.stbak"
    if not backup_dir:
        return base
    try:
        existing = set(os.listdir(backup_dir))
    except Exception:
        return base
    if base not in existing:
        return base
    n = 2
    while True:
        candidate = f"{prefix}{jdate}-{n}_{mode}.stbak"
        if candidate not in existing:
            return candidate
        n += 1


class StbakError(Exception):
    pass


def validate_stbak(raw: bytes) -> dict:
    try:
        buf = io.BytesIO(raw)
        if not zipfile.is_zipfile(buf):
            raise StbakError("فایل ZIP معتبر نیست")
        buf.seek(0)
        with zipfile.ZipFile(buf, "r") as zf:
            bad = zf.testzip()
            if bad is not None:
                raise StbakError(f"فایل داخل بکاپ خراب است: {bad}")
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


def _run_all_schema_migrations() -> list:
    """همهٔ توابع ensure_*/init_db شناخته‌شدهٔ پروژه رو صدا می‌زنه — تا ساختار
    دیتابیس (ستون‌های تازه‌اضافه‌شده در نسخه‌های جدیدتر کد + جدول‌های لیزی که
    تا حالا صدا زده نشدن) قبل/بعد از Restore کاملاً به‌روز باشه، حتی اگه بکاپ
    از یه نسخهٔ قدیمی‌تر از کد اومده باشه، یا (روی Postgres) هنوز هیچ‌کدوم از
    مسیرهایی که این جدول‌های لیزی رو می‌سازن اجرا نشده باشن.

    ⚠️ رفع‌شده (کشف‌شده با تست بازیابی یه بکاپ واقعی): نسخهٔ قبلی این تابع فقط
    ۲-۳ تا از ~۲۷ تابع `ensure_*` واقعی پروژه رو صدا می‌زد — روی یه دیتابیس
    Postgres که همهٔ مسیرهای لیزی (تیکت، تنظیمات پنل، چک‌این روزانه، علاقه‌مندی‌ها،
    درگاه‌های پرداخت، آموزش‌ها، ...) هنوز حداقل یک‌بار اجرا نشدن، بازیابی روی
    بیش از ۲۰ جدول با «relation does not exist» شکست می‌خورد. حالا تقریباً
    هر `ensure_*` شناخته‌شدهٔ `db.py` صدا زده می‌شه (idempotent، دقیقاً همون
    الگویی که خودِ اپ در طول اجرای عادی به‌تدریج صدا می‌زنه)."""
    import db as _db
    done, errors = [], []
    calls = [
        ("db.init_db", _db.init_db),
        ("db.ensure_indexes", _db.ensure_indexes),
        ("db.ensure_product_support_schema", _db.ensure_product_support_schema),
        ("db.ensure_discount_table", _db.ensure_discount_table),
        ("db.ensure_subscription_table", _db.ensure_subscription_table),
        ("db.ensure_price_history_schema", _db.ensure_price_history_schema),
        ("db.ensure_referral_schema", _db.ensure_referral_schema),
        ("db.ensure_seller_schema", _db.ensure_seller_schema),
        ("db.ensure_user_extra_schema", _db.ensure_user_extra_schema),
        ("db.ensure_partner_system_schema", _db.ensure_partner_system_schema),
        ("db.ensure_partner_wallet_schema", _db.ensure_partner_wallet_schema),
        ("db.ensure_admin_notes_schema", _db.ensure_admin_notes_schema),
        ("db.ensure_partner_tiers_extended", _db.ensure_partner_tiers_extended),
        ("db.ensure_partner_bank_schema", _db.ensure_partner_bank_schema),
        ("db.ensure_partner_bank_address", _db.ensure_partner_bank_address),
        ("db.ensure_payout_settings_extended", _db.ensure_payout_settings_extended),
        ("db.ensure_feed_batch_schema", _db.ensure_feed_batch_schema),
        ("db.ensure_accounting_schema", _db.ensure_accounting_schema),
        ("db.ensure_ratings_schema", _db.ensure_ratings_schema),
        ("db.ensure_checkin_schema", _db.ensure_checkin_schema),
        ("db.ensure_favorites_schema", _db.ensure_favorites_schema),
        ("db.ensure_notifications_schema", _db.ensure_notifications_schema),
        ("db.ensure_faq_schema", _db.ensure_faq_schema),
        ("db.ensure_card_receipts_schema", _db.ensure_card_receipts_schema),
        ("db.ticket_ensure_schema", _db.ticket_ensure_schema),
        ("db.ensure_ticket_archive_schema", _db.ensure_ticket_archive_schema),
        ("db.ensure_payment_gateways_schema", _db.ensure_payment_gateways_schema),
        ("db.ensure_growth_schema", _db.ensure_growth_schema),
        ("db.ensure_invite_cap_schema", _db.ensure_invite_cap_schema),
        ("db.ensure_app_content_schema", _db.ensure_app_content_schema),
        ("db.ensure_web_login_schema", _db.ensure_web_login_schema),
        ("db.ensure_tutorials_schema", _db.ensure_tutorials_schema),
    ]
    try:
        import iphone_valuation.db as _ivdb
        calls.append(("iphone_valuation.db.ensure_schema", _ivdb.ensure_schema))
    except Exception:
        pass
    try:
        import payment_service as _ps
        calls.append(("payment_service.ensure_schema", _ps.ensure_schema))
    except Exception:
        pass
    try:
        # admin_preferences/admins — تنها ۲ جدول لیزی که در admin_panel.py
        # تعریف شدن نه db.py؛ import محلی (نه سطح ماژول) تا وابستگی
        # چرخه‌ای بین stbak_engine و admin_panel پیش نیاد (این تابع فقط از
        # داخل یه route در admin_panel.py صدا زده می‌شه، پس اون ماژول موقع
        # اجرای واقعی این خط از قبل کامل لود شده).
        import admin_panel as _ap
        calls.append(("admin_panel.ensure_admins_table", _ap.ensure_admins_table))
        calls.append(("admin_panel._ensure_theme_table", _ap._ensure_theme_table))
        calls.append(("admin_panel.ensure_admin_preferences_schema", _ap.ensure_admin_preferences_schema))
        calls.append(("admin_panel.ensure_wallet_admin_log_schema", _ap.ensure_wallet_admin_log_schema))
        calls.append(("admin_panel.ensure_ticket_reply_columns", _ap.ensure_ticket_reply_columns))
    except Exception:
        pass
    for name, fn in calls:
        try:
            fn()
            done.append(name)
        except Exception as ex:
            errors.append(f"{name}: {ex}")
    return errors


def _widen_integer_columns(conn, table: str, target_type: str = "BIGINT") -> bool:
    """فقط زیر Postgres معنی داره (SQLite همیشه ستون‌های INTEGER رو تا ۶۴بیت،
    یا حتی مقدار متنی، بدون شکایت نگه می‌داره — type affinity). یه جدول
    Postgres رو پیدا می‌کنه که ستون(های)ش هنوز INTEGER چهاربایتی‌ان و همون‌ها
    رو به `target_type` عریض می‌کنه — گارد دو کلاس خطای واقعی که موقع بازیابی
    یه بکاپ قدیمی (از دورهٔ SQLite که این محدودیت‌ها اصلاً وجود نداشت) کشف شد:
    ۱) «integer out of range» — مثلاً شناسهٔ کاربر تلگرام که این روزها معمولاً
       از ۲.۱ میلیارد (سقف INTEGER چهاربایتی) بیشتره → BIGINT.
    ۲) «invalid input syntax for type integer» — یه مقدار کاملاً غیرعددی
       (مثل شناسهٔ ویژهٔ متنی سوپرادمین بوت‌استرپ) توی ستونی که اشتباهاً
       INTEGER تعریف شده بود (باید از اول TEXT می‌بود) → TEXT.
    بدون نیاز به دونستن از قبل کدوم ستون‌ها/جدول‌ها ممکنه به این مشکل بخورن.
    برمی‌گردونه True اگه واقعاً ستونی عریض شد (یعنی دوباره امتحان‌کردن insert
    معنی داره)."""
    try:
        cols = conn.execute(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name=? AND data_type='integer';", (table,)
        ).fetchall()
        if not cols:
            return False
        for row in cols:
            col = row[0]
            try:
                conn.execute(f'ALTER TABLE "{table}" ALTER COLUMN "{col}" TYPE {target_type};')
            except Exception:
                pass
        conn.commit()
        return True
    except Exception:
        try: conn.rollback()
        except Exception: pass
        return False


def restore_stbak(raw: bytes, db_path: str, progress_cb=None,
                   safety_backup_dir: str = None) -> dict:
    """بازیابی — با سه تضمین اضافه نسبت به نسخهٔ قبلی:
    ۱) قبل از دست‌زدن به دیتابیس واقعی، اگه safety_backup_dir داده بشه، یک بکاپ
       ایمنی از وضعیت *فعلی* (قبل از بازنویسی) خودکار گرفته می‌شه — تا اگه چیزی خراب
       شد، بشه برگشت (بخش Recovery).
    ۲) قبل و بعد از درج داده، مهاجرت‌های Schema اجرا می‌شن — یعنی اگه بکاپ از نسخهٔ
       قدیمی‌تر کد اومده باشه، ستون‌های تازه از دست نمی‌رن.
    ۳) هر جدول جدا try/except می‌شه (یک جدول ناسازگار کل Restore رو متوقف نمی‌کنه) —
       ولی بر خلاف نسخهٔ قبلی، این خطاها دیگه بی‌صدا قورت داده نمی‌شن، توی errors
       برمی‌گردن و صراحتاً به ادمین نشون داده می‌شن.

    ⚠️ دیالوگ‌آگاه (رفع‌شده): این تابع (فرمت قدیمی ZIP-محور .stbak که این ماژول
    خودش تولید می‌کنه) قبلاً همیشه `sqlite3.connect(db_path)` خام می‌زد — یعنی
    بکاپ‌های قدیمی/از دورهٔ قبل از مهاجرت به Postgres هیچ‌وقت روی دادهٔ واقعی
    Postgres قابل بازیابی نبودن (حتی از طریق CLI مستقیم، نه فقط پنل). حالا از
    `db_conn.get_connection()` استفاده می‌کنه — با هر دو دیالوگ کار می‌کنه.
    `INSERT OR REPLACE` روی جدول تازه `DELETE`شده (بدون داده‌ای که واقعاً
    conflict کنه) برای Postgres هم امنه، چون `db_dialect.translate()` این رو
    به یک `INSERT` سادهٔ پرتابل تبدیل می‌کنه — نیازی به semantics واقعی REPLACE
    نیست، چون جدول از قبل خالی شده."""
    manifest = validate_stbak(raw)
    buf = io.BytesIO(raw)
    import db_conn as _dbc
    is_pg = _dbc.is_postgres()
    with zipfile.ZipFile(buf, "r") as zf:
        data = json.loads(zf.read("data.json").decode())
        media_names = [n for n in zf.namelist() if n.startswith(_MEDIA_ZIP_PREFIX)]

        safety_backup_path = None
        if safety_backup_dir:
            try:
                os.makedirs(safety_backup_dir, exist_ok=True)
                if is_pg:
                    import pg_backup
                    safety_backup_path = pg_backup.create_backup()
                else:
                    safety_raw = create_stbak(db_path, modules=None, include_media=False, validate=False)
                    safety_name = stbak_filename("auto", safety_backup_dir, prefix="pre_restore_safety_")
                    safety_backup_path = os.path.join(safety_backup_dir, safety_name)
                    with open(safety_backup_path, "wb") as f:
                        f.write(safety_raw)
            except Exception:
                safety_backup_path = None  # نبود بکاپ ایمنی نباید جلوی خودِ Restore رو بگیره

        migration_errors_before = _run_all_schema_migrations()

        conn = _dbc.get_connection(db_path)
        if not is_pg:
            conn.execute("PRAGMA foreign_keys=OFF;")
        restored, errors = {}, []
        mods = list(data.items())
        total = len(mods) + 1
        try:
            for i, (mod, sec_data) in enumerate(mods):
                for table, rows in sec_data.items():
                    if not rows:
                        continue
                    try:
                        conn.execute(f'DELETE FROM "{table}";')
                        cols  = list(rows[0].keys())
                        ph    = ",".join("?" * len(cols))
                        col_s = ",".join(f'"{c}"' for c in cols)
                        insert_sql = f'INSERT OR REPLACE INTO "{table}" ({col_s}) VALUES ({ph});'
                        insert_params = [[r.get(c) for c in cols] for r in rows]
                        try:
                            conn.executemany(insert_sql, insert_params)
                        except Exception as ex_insert:
                            # ⚠️ رفع‌شده (کشف‌شده با بازیابی یه بکاپ واقعی روی Postgres):
                            # دو کلاس خطای رایج وقتی بکاپی از دورهٔ SQLite (بدون هیچ
                            # محدودیت نوع/اندازه) روی Postgres بازیابی می‌شه — توضیح
                            # کامل بالای _widen_integer_columns. به‌جای شکست کامل،
                            # ستون(های) INTEGER همین جدول رو عریض می‌کنیم و یک‌بار
                            # دیگه امتحان می‌کنیم.
                            msg = str(ex_insert).lower()
                            target = None
                            if is_pg and "out of range" in msg:
                                target = "BIGINT"
                            elif is_pg and "invalid input syntax for type integer" in msg:
                                target = "TEXT"
                            if target:
                                try: conn.rollback()
                                except Exception: pass
                                if _widen_integer_columns(conn, table, target_type=target):
                                    conn.execute(f'DELETE FROM "{table}";')
                                    conn.executemany(insert_sql, insert_params)
                                else:
                                    raise
                            else:
                                raise
                        conn.commit()
                        restored[table] = len(rows)
                    except Exception as ex:
                        try: conn.rollback()
                        except Exception: pass
                        errors.append(f"{table}: {ex}")
                if progress_cb:
                    progress_cb(int(10 + (i + 1) / total * 70))
        finally:
            conn.close()

        # فایل‌های مدیا
        media_restored = 0
        if media_names:
            media_dir = _media_dir()
            os.makedirs(media_dir, exist_ok=True)
            for name in media_names:
                rel = name[len(_MEDIA_ZIP_PREFIX):]
                if not rel or ".." in rel.split("/"):
                    continue
                dest = os.path.join(media_dir, *rel.split("/"))
                try:
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with zf.open(name) as src_f, open(dest, "wb") as dst_f:
                        dst_f.write(src_f.read())
                    media_restored += 1
                except Exception as ex:
                    errors.append(f"media/{rel}: {ex}")

    migration_errors_after = _run_all_schema_migrations()

    # پاک کردن کش‌های حافظه‌ای شناخته‌شده — نزدیک‌ترین معادل «Reload سرویس» بدون
    # نیاز به ری‌استارت خود پروسه (که چون ربات/پنل/API توی یک پروسه‌ان، از بیرون
    # خودِ همین کد ممکن نیست خودش رو ری‌استارت کنه).
    reload_notes = []
    try:
        import ui_texts
        ui_texts.ui_cache_clear()
        reload_notes.append("ui_texts cache cleared")
    except Exception:
        pass

    if progress_cb:
        progress_cb(100)
    return {
        "manifest": manifest, "restored": restored, "errors": errors,
        "total": sum(restored.values()),
        "media_restored": media_restored,
        "safety_backup_path": safety_backup_path,
        "migration_errors": migration_errors_before + migration_errors_after,
        "reload_notes": reload_notes,
        "reload_recommended": True,
    }


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


# ══════════════════════════════════════════════════════════════════════════
# ─── مدیریت بکاپ‌های محلی (جایگزین pg_backup.py برای نصب‌های SQLite) ────────
# ══════════════════════════════════════════════════════════════════════════
# pg_backup.py مخصوص Postgres است (pg_dump/psql) و روی نصب SQLite تولید (که
# طبق مستندات پروژه همیشه فعلی است) با خطای «DATABASE_URL تنظیم نشده» شکست
# می‌خورد. این توابع همون نقش (بکاپ محلی خودکار روزانه + چرخش + لیست) رو با
# stbak (که واقعاً روی SQLite کار می‌کنه) پیاده می‌کنن.

def save_local_backup(db_path: str, backup_dir: str, modules: list = None,
                       retention: int = 5, include_media: bool = True) -> str:
    """بکاپ می‌گیره، روی دیسک ذخیره می‌کنه، بکاپ‌های قدیمی‌تر از retention رو
    پاک می‌کنه، مسیر فایل تازه رو برمی‌گردونه. معادل SQLite-محورِ pg_backup.create_backup()."""
    os.makedirs(backup_dir, exist_ok=True)
    raw = create_stbak(db_path, modules=modules, include_media=include_media)
    fname = stbak_filename("full" if modules is None else "custom", backup_dir)
    fpath = os.path.join(backup_dir, fname)
    with open(fpath, "wb") as f:
        f.write(raw)
    _rotate_local(backup_dir, retention)
    return fpath


def _rotate_local(backup_dir: str, retention: int) -> None:
    try:
        files = sorted(
            glob.glob(os.path.join(backup_dir, "stockland_backup_*.stbak")),
            key=os.path.getmtime, reverse=True)
        for old in files[max(1, retention):]:
            try:
                os.remove(old)
            except Exception:
                pass
    except Exception:
        pass


def list_local_backups(backup_dir: str) -> list:
    """لیست بکاپ‌های محلی — [{name, size, mtime, path}, ...] — معادل SQLite-محورِ
    pg_backup.list_local_backups()."""
    if not os.path.isdir(backup_dir):
        return []
    out = []
    for f in os.listdir(backup_dir):
        if f.startswith("stockland_backup_") and f.endswith(".stbak"):
            fp = os.path.join(backup_dir, f)
            out.append({
                "name": f,
                "size": os.path.getsize(fp),
                "mtime": os.path.getmtime(fp),
                "path": fp,
            })
    return sorted(out, key=lambda x: x["mtime"], reverse=True)
