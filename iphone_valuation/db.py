"""لایهٔ دیتابیس کارشناسی آیفون — جدول‌ها + CRUD خام.

الگوی مهاجرت این پروژه رعایت شده: CREATE TABLE IF NOT EXISTS برای جدول تازه،
به‌علاوه ALTER TABLE در try/except برای ستون‌های بعدی (اگه لازم شد)، پشت یک
فلگ ماژول‌سطح تا هر درخواست دوباره تلاش نکنه.
"""
import json
import time as _time

_SCHEMA_DONE = False

# فهرست کامل مدل‌های آیفون (۲۰۰۷ تا ۲۰۲۵) — نام، سال، ظرفیت‌های استاندارد تولیدشده،
# رنگ‌های استاندارد. فقط برای seed اولیهٔ کاتالوگ؛ قیمت‌ها صفر می‌مونن تا ادمین
# از پنل پرشون کنه — این‌جا فقط مشخصات فنی دستگاهه، نه قیمت.
_IPHONE_CATALOG = [
    ("iPhone", "2007", ["4GB", "8GB", "16GB"], ["مشکی", "نقره‌ای"]),
    ("iPhone 3G", "2008", ["8GB", "16GB"], ["مشکی", "سفید"]),
    ("iPhone 3GS", "2009", ["8GB", "16GB", "32GB"], ["مشکی", "سفید"]),
    ("iPhone 4", "2010", ["8GB", "16GB", "32GB"], ["مشکی", "سفید"]),
    ("iPhone 4S", "2011", ["8GB", "16GB", "32GB", "64GB"], ["مشکی", "سفید"]),
    ("iPhone 5", "2012", ["16GB", "32GB", "64GB"], ["مشکی و اسلیت", "سفید و نقره‌ای"]),
    ("iPhone 5C", "2013", ["8GB", "16GB", "32GB"], ["سفید", "آبی", "سبز", "زرد", "صورتی"]),
    ("iPhone 5S", "2013", ["16GB", "32GB", "64GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone 6", "2014", ["16GB", "32GB", "64GB", "128GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone 6 Plus", "2014", ["16GB", "32GB", "64GB", "128GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone 6s", "2015", ["16GB", "32GB", "64GB", "128GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی", "رزگلد"]),
    ("iPhone 6s Plus", "2015", ["16GB", "32GB", "64GB", "128GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی", "رزگلد"]),
    ("iPhone SE (نسل اول)", "2016", ["16GB", "32GB", "64GB", "128GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی", "رزگلد"]),
    ("iPhone 7", "2016", ["32GB", "128GB", "256GB"],
     ["مشکی مات", "مشکی براق", "نقره‌ای", "طلایی", "رزگلد", "قرمز (PRODUCT RED)"]),
    ("iPhone 7 Plus", "2016", ["32GB", "128GB", "256GB"],
     ["مشکی مات", "مشکی براق", "نقره‌ای", "طلایی", "رزگلد", "قرمز (PRODUCT RED)"]),
    ("iPhone 8", "2017", ["64GB", "256GB"], ["نقره‌ای", "خاکستری فضایی", "طلایی", "قرمز (PRODUCT RED)"]),
    ("iPhone 8 Plus", "2017", ["64GB", "256GB"], ["نقره‌ای", "خاکستری فضایی", "طلایی", "قرمز (PRODUCT RED)"]),
    ("iPhone X", "2017", ["64GB", "256GB"], ["نقره‌ای", "خاکستری فضایی"]),
    ("iPhone XS", "2018", ["64GB", "256GB", "512GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone XS Max", "2018", ["64GB", "256GB", "512GB"], ["خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone XR", "2018", ["64GB", "128GB", "256GB"],
     ["سفید", "مشکی", "آبی", "زرد", "مرجانی", "قرمز (PRODUCT RED)"]),
    ("iPhone 11", "2019", ["64GB", "128GB", "256GB"],
     ["مشکی", "سفید", "سبز", "زرد", "بنفش", "قرمز (PRODUCT RED)"]),
    ("iPhone 11 Pro", "2019", ["64GB", "256GB", "512GB"], ["سبز نیمه‌شب", "خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone 11 Pro Max", "2019", ["64GB", "256GB", "512GB"], ["سبز نیمه‌شب", "خاکستری فضایی", "نقره‌ای", "طلایی"]),
    ("iPhone SE (نسل دوم)", "2020", ["64GB", "128GB", "256GB"], ["مشکی", "سفید", "قرمز (PRODUCT RED)"]),
    ("iPhone 12", "2020", ["64GB", "128GB", "256GB"],
     ["مشکی", "سفید", "آبی", "سبز", "قرمز (PRODUCT RED)", "بنفش"]),
    ("iPhone 12 mini", "2020", ["64GB", "128GB", "256GB"],
     ["مشکی", "سفید", "آبی", "سبز", "قرمز (PRODUCT RED)", "بنفش"]),
    ("iPhone 12 Pro", "2020", ["128GB", "256GB", "512GB"], ["آبی اقیانوسی", "طلایی", "نقره‌ای", "گرافیتی"]),
    ("iPhone 12 Pro Max", "2020", ["128GB", "256GB", "512GB"], ["آبی اقیانوسی", "طلایی", "نقره‌ای", "گرافیتی"]),
    ("iPhone 13", "2021", ["128GB", "256GB", "512GB"],
     ["صورتی", "آبی", "نیمه‌شب", "نور ستاره‌ای", "قرمز (PRODUCT RED)", "سبز"]),
    ("iPhone 13 mini", "2021", ["128GB", "256GB", "512GB"],
     ["صورتی", "آبی", "نیمه‌شب", "نور ستاره‌ای", "قرمز (PRODUCT RED)", "سبز"]),
    ("iPhone 13 Pro", "2021", ["128GB", "256GB", "512GB", "1TB"],
     ["گرافیت", "طلایی", "نقره‌ای", "آبی سیرا", "سبز آلپاین"]),
    ("iPhone 13 Pro Max", "2021", ["128GB", "256GB", "512GB", "1TB"],
     ["گرافیت", "طلایی", "نقره‌ای", "آبی سیرا", "سبز آلپاین"]),
    ("iPhone SE (نسل سوم)", "2022", ["64GB", "128GB", "256GB"], ["نیمه‌شب", "نور ستاره‌ای", "قرمز (PRODUCT RED)"]),
    ("iPhone 14", "2022", ["128GB", "256GB", "512GB"],
     ["نیمه‌شب", "نور ستاره‌ای", "آبی", "بنفش", "قرمز (PRODUCT RED)", "زرد"]),
    ("iPhone 14 Plus", "2022", ["128GB", "256GB", "512GB"],
     ["نیمه‌شب", "نور ستاره‌ای", "آبی", "بنفش", "قرمز (PRODUCT RED)", "زرد"]),
    ("iPhone 14 Pro", "2022", ["128GB", "256GB", "512GB", "1TB"],
     ["مشکی فضایی", "نقره‌ای", "طلایی", "بنفش عمیق"]),
    ("iPhone 14 Pro Max", "2022", ["128GB", "256GB", "512GB", "1TB"],
     ["مشکی فضایی", "نقره‌ای", "طلایی", "بنفش عمیق"]),
    ("iPhone 15", "2023", ["128GB", "256GB", "512GB"], ["مشکی", "آبی", "سبز", "زرد", "صورتی"]),
    ("iPhone 15 Plus", "2023", ["128GB", "256GB", "512GB"], ["مشکی", "آبی", "سبز", "زرد", "صورتی"]),
    ("iPhone 15 Pro", "2023", ["128GB", "256GB", "512GB", "1TB"],
     ["تیتانیوم طبیعی", "تیتانیوم آبی", "تیتانیوم سفید", "تیتانیوم مشکی"]),
    ("iPhone 15 Pro Max", "2023", ["256GB", "512GB", "1TB"],
     ["تیتانیوم طبیعی", "تیتانیوم آبی", "تیتانیوم سفید", "تیتانیوم مشکی"]),
    ("iPhone 16", "2024", ["128GB", "256GB", "512GB"],
     ["مشکی", "سفید", "صورتی", "سبزآبی", "آبی اولترامارین"]),
    ("iPhone 16 Plus", "2024", ["128GB", "256GB", "512GB"],
     ["مشکی", "سفید", "صورتی", "سبزآبی", "آبی اولترامارین"]),
    ("iPhone 16 Pro", "2024", ["128GB", "256GB", "512GB", "1TB"],
     ["تیتانیوم مشکی", "تیتانیوم طبیعی", "تیتانیوم سفید", "تیتانیوم صحرایی"]),
    ("iPhone 16 Pro Max", "2024", ["256GB", "512GB", "1TB"],
     ["تیتانیوم مشکی", "تیتانیوم طبیعی", "تیتانیوم سفید", "تیتانیوم صحرایی"]),
    ("iPhone 16e", "2025", ["128GB", "256GB", "512GB"], ["سفید", "مشکی"]),
    ("iPhone 17", "2025", ["256GB", "512GB"],
     ["مشکی", "سفید", "آبی مه‌آلود", "سبز مریم‌گلی", "اسطوخودوسی"]),
    ("iPhone 17 Air", "2025", ["256GB", "512GB", "1TB"],
     ["مشکی فضایی", "سفید ابری", "طلایی روشن", "آبی آسمانی"]),
    ("iPhone 17 Pro", "2025", ["256GB", "512GB", "1TB"], ["نقره‌ای", "نارنجی کیهانی", "آبی عمیق"]),
    ("iPhone 17 Pro Max", "2025", ["256GB", "512GB", "1TB", "2TB"], ["نقره‌ای", "نارنجی کیهانی", "آبی عمیق"]),
]


# دستهٔ «component» — کدوم قسمت دستگاه خرابه (چندانتخابی، فقط وقتی کاربر وضعیت کلی
# دستگاه رو «نیازمند تعمیر» انتخاب کنه پرسیده می‌شه، چون اونجاست که واقعاً روی
# قیمت اثر داره).
PART_OPTIONS = [("LL", "LL/A"), ("ZA", "ZA/A"), ("CH", "CH/A"), ("OTHER", "سایر")]

# اندازه‌های استاندارد حافظه (برای دراپ‌داون ثبت ظرفیت تازه در پنل — نه محدودیت سختگیرانه،
# "سایر" همیشه به‌عنوان راه‌فرار برای مقدار دلخواه موجوده)
STANDARD_CAPACITIES = ["4GB", "8GB", "16GB", "32GB", "64GB", "128GB", "256GB", "512GB", "1TB", "2TB"]


def capacity_sort_key(label: str):
    """برای مرتب‌سازی برچسب‌های ظرفیت به ترتیب اندازهٔ واقعی (نه الفبایی) — مثلاً
    ۶۴GB باید قبل از ۲۵۶GB بیاد، نه بعدش (که ترتیب رشته‌ای اشتباه می‌ده)."""
    s = (label or "").strip().upper()
    try:
        if s.endswith("TB"):
            return float(s[:-2]) * 1024
        if s.endswith("GB"):
            return float(s[:-2])
        if s.endswith("MB"):
            return float(s[:-2]) / 1024
        return float("".join(ch for ch in s if ch.isdigit() or ch == ".") or 0)
    except ValueError:
        return 0.0


COMPONENT_DEFAULTS = [
    ("component", "comp_faceid", "Face ID", -15, 1),
    ("component", "comp_screen", "صفحه نمایش / تاچ", -20, 2),
    ("component", "comp_camera", "دوربین", -10, 3),
    ("component", "comp_speaker", "اسپیکر", -5, 4),
    ("component", "comp_mic", "میکروفون", -5, 5),
    ("component", "comp_wifi", "وای‌فای", -8, 6),
    ("component", "comp_bluetooth", "بلوتوث", -5, 7),
    ("component", "comp_nfc", "NFC", -3, 8),
    ("component", "comp_wireless_charge", "شارژ بی‌سیم", -5, 9),
    ("component", "comp_buttons", "دکمه‌ها (پاور/صدا)", -5, 10),
]


def _iv_sim_policy(name: str, sort_order: int) -> tuple[str, int]:
    """(dual_sim_parts, esim_only) بر اساس قانون مالک پروژه:
    - مدل‌های Air: فقط eSIM
    - مینی‌ها: همیشه تک‌سیم، مستقل از پارت نامبر
    - قبل از iPhone XS Max (sort_order زیر ۲۰): همیشه تک‌سیم
    - iPhone XS Max تا iPhone 16e (۲۰ تا ۴۷): پارت ZA و CH دوسیم‌ان
    - iPhone 17 به بعد (۴۸+، به‌جز Air که بالاتر مدیریت شد): فقط پارت CH دوسیمه
    - در همهٔ موارد بالا، هر پارت دیگه (از جمله «سایر») تک‌سیمه."""
    if "Air" in name:
        return "", 1
    if "mini" in name:
        return "", 0
    if sort_order < 20:
        return "", 0
    if sort_order >= 48:
        return "CH", 0
    return "ZA,CH", 0


def _conn():
    from db import _get_connection
    return _get_connection()


def ensure_schema():
    global _SCHEMA_DONE
    if _SCHEMA_DONE:
        return
    conn = _conn()
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            series TEXT DEFAULT '',
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            dual_sim_parts TEXT NOT NULL DEFAULT '',
            esim_only INTEGER NOT NULL DEFAULT 0,
            color_pricing INTEGER NOT NULL DEFAULT 0,
            part_pricing INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        # مهاجرت برای نصب‌های قبلی که iv_models رو بدون این ستون‌ها ساخته بودن
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN dual_sim_parts TEXT NOT NULL DEFAULT '';")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN esim_only INTEGER NOT NULL DEFAULT 0;")
            conn.commit()
        except Exception:
            pass
        # color_pricing/part_pricing: کلید روشن/خاموش برای اینکه رنگ/پارت واقعاً روی قیمت این
        # مدل اثر داشته باشن یا نه — پیش‌فرض خاموش (قیمت یکسان)، ادمین آگاهانه روشنش می‌کنه
        # فقط جایی که واقعاً لازمه (مثل iPhone 15 Pro که رنگ‌های مختلف قیمت متفاوت دارن).
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN color_pricing INTEGER NOT NULL DEFAULT 0;")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN part_pricing INTEGER NOT NULL DEFAULT 0;")
            conn.commit()
        except Exception:
            pass
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_capacities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            capacity_label TEXT NOT NULL,
            part_number TEXT NOT NULL DEFAULT '',
            color TEXT NOT NULL DEFAULT '',
            base_price INTEGER NOT NULL DEFAULT 0,
            buy_price_ref INTEGER NOT NULL DEFAULT 0,
            sell_price_ref INTEGER NOT NULL DEFAULT 0,
            fx_ref_rate INTEGER NOT NULL DEFAULT 0,
            demand_percent REAL NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        # مهاجرت برای نصب‌های قبلی که iv_capacities رو بدون این ستون‌ها ساخته بودن — قیمت هر
        # گوشی هم بسته به پارت (LL/ZA/CH/سایر) هم بسته به رنگ فرق می‌کنه، پس این دو ستون برای
        # قیمت‌گذاری دقیق لازمن. ردیف‌های قدیمی part_number=''/color='' می‌مونن و به‌عنوان
        # «قیمت پیش‌فرض بدون پارت/رنگ مشخص» (fallback در resolve_capacity) همچنان کار می‌کنن —
        # هیچ دیتایی از دست نمی‌ره.
        try:
            conn.execute("ALTER TABLE iv_capacities ADD COLUMN part_number TEXT NOT NULL DEFAULT '';")
            conn.commit()
        except Exception:
            pass
        try:
            conn.execute("ALTER TABLE iv_capacities ADD COLUMN color TEXT NOT NULL DEFAULT '';")
            conn.commit()
        except Exception:
            pass
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_coefficients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            option_key TEXT NOT NULL,
            option_label TEXT NOT NULL,
            percent REAL NOT NULL DEFAULT 0,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_score_weights (
            category TEXT PRIMARY KEY,
            weight REAL NOT NULL DEFAULT 0
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_fx_sources (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            url TEXT NOT NULL,
            json_path TEXT NOT NULL DEFAULT 'price',
            priority INTEGER NOT NULL DEFAULT 1,
            active INTEGER NOT NULL DEFAULT 1,
            last_value INTEGER,
            last_fetched_at TEXT,
            last_error TEXT
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            capacity_id INTEGER NOT NULL,
            condition_note TEXT DEFAULT '',
            buy_price INTEGER NOT NULL DEFAULT 0,
            sell_price INTEGER NOT NULL DEFAULT 0,
            sold_at TEXT,
            days_to_sell INTEGER,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_valuations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            model_id INTEGER,
            capacity_id INTEGER,
            color TEXT DEFAULT '',
            part_number TEXT DEFAULT '',
            sim_type TEXT DEFAULT '',
            input_json TEXT DEFAULT '{}',
            market_price INTEGER NOT NULL DEFAULT 0,
            fair_price INTEGER NOT NULL DEFAULT 0,
            buy_price INTEGER NOT NULL DEFAULT 0,
            sell_price INTEGER NOT NULL DEFAULT 0,
            score INTEGER NOT NULL DEFAULT 0,
            verdict TEXT DEFAULT '',
            report_text TEXT DEFAULT '',
            seller_price INTEGER,
            city TEXT DEFAULT '',
            seller_type TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        conn.commit()

        # سیدِ پیش‌فرض ضرایب امتیازدهی — فقط اگه جدول خالیه (اولین اجرا)
        row = conn.execute("SELECT COUNT(*) c FROM iv_score_weights;").fetchone()
        if row and row["c"] == 0:
            defaults = [
                ("condition", 20), ("battery", 20), ("repair", 25), ("registry", 15),
                ("box", 10), ("cosmetic", 20), ("cable", 5), ("features", 5), ("component", 15),
            ]
            for cat, w in defaults:
                conn.execute("INSERT INTO iv_score_weights (category, weight) VALUES (?,?);", (cat, w))
            conn.commit()

        # سیدِ پیش‌فرض ضرایب قیمت — فقط اگه جدول خالیه
        row = conn.execute("SELECT COUNT(*) c FROM iv_coefficients;").fetchone()
        if row and row["c"] == 0:
            defaults = [
                ("battery", "batt_95_100", "باتری ۹۵ تا ۱۰۰٪ (بدون افت)", 0, 1),
                ("battery", "batt_90_94", "باتری ۹۰ تا ۹۴٪ (افت جزئی)", -2, 2),
                ("battery", "batt_85_89", "باتری ۸۵ تا ۸۹٪ (افت متوسط)", -6, 3),
                ("battery", "batt_under_85", "باتری زیر ۸۵٪ (افت زیاد)", -12, 4),
                ("battery", "batt_replaced", "باتری تعویض‌شده (غیراصلی)", -8, 5),
                ("repair", "repair_none", "باز نشده", 0, 1),
                ("repair", "repair_opened", "باز شده (بدون تعمیر خاص)", -5, 2),
                ("repair", "repair_screen", "تعویض صفحه", -10, 3),
                ("repair", "repair_battery", "تعویض باتری", -6, 4),
                ("repair", "repair_board", "تعمیر برد", -25, 5),
                ("repair", "repair_water", "آب‌خوردگی", -35, 6),
                ("registry", "registry_transferable", "رجیستر (مالکیت قابل انتقال)", 0, 1),
                ("registry", "registry_non_transferable", "رجیستر (بدون امکان انتقال)", -5, 2),
                ("registry", "registry_white", "وضعیت سفید", -10, 3),
                ("registry", "registry_unregistered", "بدون رجیستر", -20, 4),
                ("box", "box_original", "پک اصلی کارخانه", 3, 1),
                ("box", "box_repack", "ریپک", -3, 2),
                ("box", "box_none", "بدون کارتن", -6, 3),
                ("cosmetic", "cosmetic_clean", "کاملاً تمیز", 0, 1),
                ("cosmetic", "cosmetic_minor", "خط و خش جزئی", -3, 2),
                ("cosmetic", "cosmetic_medium", "خط و خش متوسط", -7, 3),
                ("cosmetic", "cosmetic_heavy", "خط و خش زیاد", -12, 4),
                ("cosmetic", "cosmetic_frame_hit", "ضربه فریم", -10, 5),
                ("cosmetic", "cosmetic_front_crack", "شکستگی شیشه جلو", -20, 6),
                ("cosmetic", "cosmetic_back_crack", "شکستگی پشت", -15, 7),
                ("cable", "cable_original", "کابل اصلی دارد", 1, 1),
                ("cable", "cable_none", "کابل ندارد", -1, 2),
                ("cable", "cable_fake", "کابل غیر اصلی", -1, 3),
                ("condition", "cond_new", "نو", 5, 1),
                ("condition", "cond_sealed", "پلمپ", 8, 2),
                ("condition", "cond_like_new", "در حد نو", 0, 3),
                ("condition", "cond_used", "کارکرده", -10, 4),
                ("condition", "cond_needs_repair", "نیازمند تعمیر", -30, 5),
            ] + COMPONENT_DEFAULTS
            for cat, key, label, pct, order in defaults:
                conn.execute(
                    "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
                    "VALUES (?,?,?,?,?);", (cat, key, label, pct, order))
            conn.commit()

        # سیدِ کاتالوگ کامل مدل‌های آیفون — فقط اگه جدول خالیه (اولین اجرا).
        # قیمت‌ها صفر می‌مونن؛ این فقط مشخصات فنی (ظرفیت/رنگ استاندارد) رو وارد می‌کنه،
        # ادمین باید بعداً از /admin/iphone/models قیمت هر ظرفیت رو پر کنه.
        row = conn.execute("SELECT COUNT(*) c FROM iv_models;").fetchone()
        if row and row["c"] == 0:
            for order_idx, (name, year, caps, colors) in enumerate(_IPHONE_CATALOG, start=1):
                dual_parts, esim_only = _iv_sim_policy(name, order_idx)
                cur = conn.execute(
                    "INSERT INTO iv_models (name, series, sort_order, dual_sim_parts, esim_only) "
                    "VALUES (?,?,?,?,?);", (name, year, order_idx, dual_parts, esim_only))
                model_id = cur.lastrowid
                for cap_label in caps:
                    conn.execute(
                        "INSERT INTO iv_capacities (model_id, capacity_label, base_price, buy_price_ref, "
                        "sell_price_ref) VALUES (?,?,0,0,0);", (model_id, cap_label))
                for color_idx, color_name in enumerate(colors):
                    conn.execute(
                        "INSERT INTO iv_colors (model_id, name, sort_order) VALUES (?,?,?);",
                        (model_id, color_name, color_idx))
            conn.commit()

        _migrate_registry_options_v2(conn)
        _migrate_sim_policy_v1(conn)
        _migrate_component_category_v1(conn)
        _migrate_battery_label_v1(conn)
        _migrate_condition_weight_v1(conn)
        _migrate_pricing_toggles_v1(conn)
    finally:
        conn.close()
    _SCHEMA_DONE = True


def _migrate_pricing_toggles_v1(conn):
    """color_pricing/part_pricing تازه اضافه شدن و پیش‌فرضشون خاموشه. اگه ادمین از قبل
    (قبل از وجود این فلگ‌ها) واقعاً برای یه مدل چند ردیف با رنگ/پارت متفاوت ثبت کرده بود،
    یعنی عملاً می‌خواسته اثر داشته باشن — پس برای اون مدل‌ها فلگ رو روشن می‌کنیم تا رفتار
    فعلی سیستم عوض نشه. یه‌بار اجرا می‌شه (فلگ در bot_config)."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_PRICING_TOGGLES_MIGRATED", "0") == "1":
        return
    models = conn.execute("SELECT id FROM iv_models;").fetchall()
    for m in models:
        mid = m["id"]
        rows = conn.execute(
            "SELECT DISTINCT color, part_number FROM iv_capacities WHERE model_id=?;", (mid,)).fetchall()
        has_color = any((r["color"] or "").strip() for r in rows)
        has_part = any((r["part_number"] or "").strip() for r in rows)
        conn.execute("UPDATE iv_models SET color_pricing=?, part_pricing=? WHERE id=?;",
                     (1 if has_color else 0, 1 if has_part else 0, mid))
    conn.commit()
    set_cfg("IV_PRICING_TOGGLES_MIGRATED", "1")


def _migrate_condition_weight_v1(conn):
    """دستهٔ «condition» (وضعیت کلی دستگاه) هیچ‌وقت وزن امتیازدهی نداشت — یعنی انتخاب
    «نیازمند تعمیر» روی قیمت اثر می‌ذاشت ولی روی StockLand Score هیچ اثری نداشت.
    این باگ قدیمی رو رفع می‌کنه؛ فقط اگه هنوز وزنی برای این دسته ثبت نشده باشه."""
    conn.execute(
        "INSERT INTO iv_score_weights (category, weight) VALUES ('condition', 20) "
        "ON CONFLICT(category) DO NOTHING;")
    conn.commit()


def _migrate_component_category_v1(conn):
    """دستهٔ تازهٔ «component» (کدوم قسمت خرابه) رو برای دیتابیس‌هایی که قبل از این
    تغییر seed شدن اضافه می‌کنه — فقط اگه این دسته هنوز هیچ گزینه‌ای نداره."""
    row = conn.execute("SELECT COUNT(*) c FROM iv_coefficients WHERE category='component';").fetchone()
    if row and row["c"] == 0:
        for cat, key, label, pct, order in COMPONENT_DEFAULTS:
            conn.execute(
                "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
                "VALUES (?,?,?,?,?);", (cat, key, label, pct, order))
        conn.execute(
            "INSERT INTO iv_score_weights (category, weight) VALUES ('component', 15) "
            "ON CONFLICT(category) DO NOTHING;")
        conn.commit()


def _migrate_battery_label_v1(conn):
    """برچسب «تعویض باتری (توسط تعمیرکار غیرمجاز)» به «تعویض باتری» ساده شد —
    فقط اگه ادمین از قبل دستی تغییرش نداده باشه."""
    conn.execute(
        "UPDATE iv_coefficients SET option_label='تعویض باتری' "
        "WHERE category='repair' AND option_key='repair_battery' "
        "AND option_label='تعویض باتری (توسط تعمیرکار غیرمجاز)';")
    conn.commit()


def _migrate_sim_policy_v1(conn):
    """پر کردن dual_sim_parts/esim_only برای مدل‌هایی که قبل از این تغییر seed شدن
    (ستون‌ها تازه اضافه شدن). یه‌بار طبق sort_order+نام هر مدل اجرا می‌شه؛ بعدش هرچی
    ادمین از پنل خودش تغییر بده دست‌نخورده می‌مونه."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_SIM_POLICY_MIGRATED", "0") == "1":
        return
    rows = conn.execute("SELECT id, name, sort_order FROM iv_models;").fetchall()
    for row in rows:
        dual_parts, esim_only = _iv_sim_policy(row["name"], row["sort_order"])
        conn.execute("UPDATE iv_models SET dual_sim_parts=?, esim_only=? WHERE id=?;",
                     (dual_parts, esim_only, row["id"]))
    conn.commit()
    set_cfg("IV_SIM_POLICY_MIGRATED", "1")


def _migrate_registry_options_v2(conn):
    """مالک پروژه دستهٔ «رجیستری» رو به «وضعیت مالکیت» با گزینه‌های تازه تغییر داد.
    این فقط روی دیتابیس‌هایی اجرا می‌شه که قبلاً با seed قدیمی (چهار گزینهٔ اول)
    پر شده بودن — یه‌بار اجرا می‌شه (فلگ در bot_config)، و اگه ادمین گزینه‌های
    پیش‌فرض رو از پنل حذف کرده باشه، دست‌نخورده می‌مونه."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_REGISTRY_V2_MIGRATED", "0") == "1":
        return
    old_keys = ("registry_registered", "registry_owner_transfer_needed",
                "registry_owner_transferred", "registry_none")
    found = conn.execute(
        "SELECT id FROM iv_coefficients WHERE category='registry' AND option_key IN (?,?,?,?);",
        old_keys).fetchall()
    if found:
        conn.execute(
            "DELETE FROM iv_coefficients WHERE category='registry' AND option_key IN (?,?,?,?);",
            old_keys)
        new_options = [
            ("registry_transferable", "رجیستر (مالکیت قابل انتقال)", 0, 1),
            ("registry_non_transferable", "رجیستر (بدون امکان انتقال)", -5, 2),
            ("registry_white", "وضعیت سفید", -10, 3),
            ("registry_unregistered", "بدون رجیستر", -20, 4),
        ]
        for key, label, pct, order in new_options:
            conn.execute(
                "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
                "VALUES ('registry',?,?,?,?);", (key, label, pct, order))
        conn.commit()
    set_cfg("IV_REGISTRY_V2_MIGRATED", "1")


# ─── مدل‌ها ──────────────────────────────────────────────────────────────

def list_models(active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_models"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def get_model(model_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_models WHERE id=?;", (model_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_model(name: str, series: str = "", sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_models (name, series, sort_order) VALUES (?,?,?);",
            (name.strip(), (series or "").strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_model(model_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "series", "sort_order", "active", "dual_sim_parts", "esim_only",
               "color_pricing", "part_pricing"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_models SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [model_id])
        conn.commit()
    finally:
        conn.close()


def delete_model(model_id: int) -> None:
    """حذف کامل مدل + همهٔ ظرفیت/قیمت‌ها و رنگ‌هاش. تاریخچهٔ کارشناسی‌های قبلی
    (iv_valuations/iv_transactions) دست‌نخورده می‌مونه — فقط model_id توشون یتیم می‌مونه،
    دقیقاً مثل رفتار پروژه با محصولات حذف‌شده در سفارش‌های قدیمی."""
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_capacities WHERE model_id=?;", (model_id,))
        conn.execute("DELETE FROM iv_colors WHERE model_id=?;", (model_id,))
        conn.execute("DELETE FROM iv_models WHERE id=?;", (model_id,))
        conn.commit()
    finally:
        conn.close()


# ─── ظرفیت/قیمت‌ها ───────────────────────────────────────────────────────

def list_capacities(model_id: int | None = None, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_capacities WHERE 1=1"
        params = []
        if model_id is not None:
            q += " AND model_id=?"
            params.append(model_id)
        if active_only:
            q += " AND active=1"
        q += " ORDER BY base_price ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_capacity(cap_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_capacities WHERE id=?;", (cap_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_capacity(model_id: int, capacity_label: str, base_price: int,
                     buy_price_ref: int, sell_price_ref: int,
                     fx_ref_rate: int = 0, demand_percent: float = 0,
                     part_number: str = "", color: str = "") -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_capacities "
            "(model_id, capacity_label, part_number, color, base_price, buy_price_ref, sell_price_ref, "
            "fx_ref_rate, demand_percent) VALUES (?,?,?,?,?,?,?,?,?);",
            (model_id, capacity_label.strip(), (part_number or "").strip().upper(), (color or "").strip(),
             base_price, buy_price_ref, sell_price_ref, fx_ref_rate, demand_percent))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_capacity(cap_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"capacity_label", "part_number", "color", "base_price", "buy_price_ref", "sell_price_ref",
               "fx_ref_rate", "demand_percent", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_capacities SET {', '.join(c+'=?' for c in cols)}, updated_at=datetime('now') WHERE id=?;",
            [fields[c] for c in cols] + [cap_id])
        conn.commit()
    finally:
        conn.close()


def delete_capacity(cap_id: int) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_capacities WHERE id=?;", (cap_id,))
        conn.commit()
    finally:
        conn.close()


def get_capacity_exact(model_id: int, capacity_label: str, part_number: str = "", color: str = "") -> dict | None:
    """ردیف دقیقاً منطبق با (مدل، ظرفیت، پارت، رنگ) رو برمی‌گردونه (یا None) —
    برای upsert_capacity استفاده می‌شه تا تشخیص بده باید ردیف موجود آپدیت بشه یا جدید ساخته بشه."""
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM iv_capacities WHERE model_id=? AND capacity_label=? AND part_number=? "
            "AND color=? LIMIT 1;",
            (model_id, capacity_label.strip(), (part_number or "").strip().upper(), (color or "").strip())
        ).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_capacity(model_id: int, capacity_label: str, base_price: int, buy_price_ref: int,
                     sell_price_ref: int, fx_ref_rate: int = 0, demand_percent: float = 0,
                     part_number: str = "", color: str = "") -> int:
    """ثبت یا به‌روزرسانی قیمت یک ترکیب (ظرفیت+پارت+رنگ) — همون دکمهٔ «ذخیره»ی فرم واحد
    تعریف مدل در پنل؛ اگه این ترکیب دقیق از قبل ثبت شده باشه آپدیت می‌شه (نه رد یا تکراری)،
    وگرنه ردیف تازه ساخته می‌شه. کاربر هیچ‌وقت پیام «قبلاً ثبت شده» نمی‌بینه."""
    existing = get_capacity_exact(model_id, capacity_label, part_number, color)
    if existing:
        update_capacity(existing["id"], base_price=base_price, buy_price_ref=buy_price_ref,
                         sell_price_ref=sell_price_ref, fx_ref_rate=fx_ref_rate,
                         demand_percent=demand_percent, active=1)
        return existing["id"]
    return create_capacity(model_id, capacity_label, base_price, buy_price_ref, sell_price_ref,
                            fx_ref_rate, demand_percent, part_number=part_number, color=color)


def resolve_capacity(model_id: int, capacity_label: str, part_number: str = "", color: str = "") -> dict | None:
    """قیمت دقیق (مدل+ظرفیت+پارت+رنگ) رو پیدا می‌کنه؛ اگه قیمت اختصاصی برای اون ترکیب ثبت
    نشده باشه، به ترتیب اولویت fallback می‌کنه: (پارت دقیق+رنگ دقیق) → (پارت دقیق+رنگ عمومی)
    → (پارت عمومی+رنگ دقیق) → (پارت عمومی+رنگ عمومی) — یعنی ادمین فقط جایی که قیمت واقعاً
    فرق داره لازمه پارت/رنگ مشخص وارد کنه، بقیه از قیمت عمومی‌تر استفاده می‌کنن.

    اگه ادمین از `/admin/iphone/models` اثر رنگ/پارت روی قیمت این مدل رو خاموش کرده باشه
    (iv_models.color_pricing/part_pricing)، همون بعد این‌جا قبل از جست‌وجو صفر می‌شه — یعنی
    کاربر هرچی هم توی ربات انتخاب کرده باشه، قیمت از ردیف عمومی همون مدل خونده می‌شه."""
    ensure_schema()
    model = get_model(model_id)
    if model:
        if not model.get("color_pricing"):
            color = ""
        if not model.get("part_pricing"):
            part_number = ""
    conn = _conn()
    try:
        part = (part_number or "").strip().upper()
        clr = (color or "").strip()
        label = capacity_label.strip()

        def _q(p, c):
            return conn.execute(
                "SELECT * FROM iv_capacities WHERE model_id=? AND capacity_label=? AND part_number=? "
                "AND color=? AND active=1 LIMIT 1;", (model_id, label, p, c)).fetchone()

        row = _q(part, clr)
        if not row and (part or clr):
            row = _q(part, "") or _q("", clr) or _q("", "")
        return dict(row) if row else None
    finally:
        conn.close()


def list_capacity_labels(model_id: int, active_only: bool = True) -> list[str]:
    """برچسب‌های یکتای ظرفیت این مدل، صرف‌نظر از پارت (برای مرحلهٔ انتخاب ظرفیت در ویزارد
    ربات — چون کاربر یه ظرفیت رو انتخاب می‌کنه، نه یه ردیف قیمت خاص)، مرتب‌شده به ترتیب
    اندازهٔ واقعی."""
    caps = list_capacities(model_id=model_id, active_only=active_only)
    labels = sorted({c["capacity_label"] for c in caps}, key=capacity_sort_key)
    return labels


# ─── رنگ‌ها ──────────────────────────────────────────────────────────────

def list_colors(model_id: int, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_colors WHERE model_id=?"
        params = [model_id]
        if active_only:
            q += " AND active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def create_color(model_id: int, name: str, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_colors (model_id, name, sort_order) VALUES (?,?,?);",
            (model_id, name.strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_color(color_id: int) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_colors WHERE id=?;", (color_id,))
        conn.commit()
    finally:
        conn.close()


# ─── ضرایب ───────────────────────────────────────────────────────────────

COEFFICIENT_CATEGORIES = ["condition", "battery", "repair", "registry", "box", "cosmetic", "cable", "component"]


def list_coefficients(category: str | None = None, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_coefficients WHERE 1=1"
        params = []
        if category:
            q += " AND category=?"
            params.append(category)
        if active_only:
            q += " AND active=1"
        q += " ORDER BY category ASC, sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def create_coefficient(category: str, option_key: str, option_label: str,
                        percent: float, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES (?,?,?,?,?);",
            (category, option_key.strip(), option_label.strip(), percent, sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_coefficient(coef_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"option_label", "percent", "sort_order", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_coefficients SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [coef_id])
        conn.commit()
    finally:
        conn.close()


def delete_coefficient(coef_id: int) -> None:
    update_coefficient(coef_id, active=0)


# ─── ضرایب امتیازدهی ─────────────────────────────────────────────────────

def list_score_weights() -> dict:
    ensure_schema()
    conn = _conn()
    try:
        rows = conn.execute("SELECT * FROM iv_score_weights;").fetchall()
        return {r["category"]: r["weight"] for r in rows}
    finally:
        conn.close()


def set_score_weight(category: str, weight: float) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO iv_score_weights (category, weight) VALUES (?,?) "
            "ON CONFLICT(category) DO UPDATE SET weight=excluded.weight;",
            (category, weight))
        conn.commit()
    finally:
        conn.close()


# ─── منابع نرخ ارز ───────────────────────────────────────────────────────

def list_fx_sources(active_only: bool = False) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_fx_sources"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY priority ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def create_fx_source(name: str, url: str, json_path: str = "price", priority: int = 1) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_fx_sources (name, url, json_path, priority) VALUES (?,?,?,?);",
            (name.strip(), url.strip(), json_path.strip() or "price", priority))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_fx_source(source_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "url", "json_path", "priority", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(
            f"UPDATE iv_fx_sources SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
            [fields[c] for c in cols] + [source_id])
        conn.commit()
    finally:
        conn.close()


def delete_fx_source(source_id: int) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_fx_sources WHERE id=?;", (source_id,))
        conn.commit()
    finally:
        conn.close()


def record_fx_fetch(source_id: int, value: int | None, error: str | None) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute(
            "UPDATE iv_fx_sources SET last_value=?, last_fetched_at=datetime('now'), last_error=? WHERE id=?;",
            (value, error, source_id))
        conn.commit()
    finally:
        conn.close()


# ─── تاریخچهٔ معاملات StockLand (برای یادگیری بازار) ─────────────────────

def list_transactions(model_id: int | None = None, limit: int = 50) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_transactions WHERE 1=1"
        params = []
        if model_id is not None:
            q += " AND model_id=?"
            params.append(model_id)
        q += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def create_transaction(model_id: int, capacity_id: int, buy_price: int, sell_price: int,
                        condition_note: str = "", sold_at: str | None = None,
                        days_to_sell: int | None = None) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute(
            "INSERT INTO iv_transactions (model_id, capacity_id, condition_note, buy_price, sell_price, "
            "sold_at, days_to_sell) VALUES (?,?,?,?,?,?,?);",
            (model_id, capacity_id, condition_note, buy_price, sell_price, sold_at, days_to_sell))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def market_data_avg_delta_pct(model_id: int, capacity_id: int, base_price: int) -> float:
    """میانگین درصد اختلاف قیمت فروش واقعی نسبت به قیمت پایه، برای همون مدل+ظرفیت."""
    ensure_schema()
    if base_price <= 0:
        return 0.0
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT sell_price FROM iv_transactions WHERE model_id=? AND capacity_id=? "
            "ORDER BY id DESC LIMIT 20;", (model_id, capacity_id)).fetchall()
        if not rows:
            return 0.0
        deltas = [((r["sell_price"] - base_price) / base_price) * 100 for r in rows if r["sell_price"]]
        return sum(deltas) / len(deltas) if deltas else 0.0
    finally:
        conn.close()


# ─── لاگ کارشناسی‌ها ──────────────────────────────────────────────────────

def create_valuation(**fields) -> int:
    ensure_schema()
    cols = ["user_id", "model_id", "capacity_id", "color", "part_number", "sim_type", "input_json",
            "market_price", "fair_price", "buy_price", "sell_price", "score", "verdict", "report_text",
            "seller_price", "city", "seller_type"]
    values = [fields.get(c) for c in cols]
    conn = _conn()
    try:
        cur = conn.execute(
            f"INSERT INTO iv_valuations ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)});",
            values)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_valuations(limit: int = 50, model_id: int | None = None) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = ("SELECT v.*, m.name AS model_name, c.capacity_label FROM iv_valuations v "
             "LEFT JOIN iv_models m ON m.id=v.model_id "
             "LEFT JOIN iv_capacities c ON c.id=v.capacity_id WHERE 1=1")
        params = []
        if model_id is not None:
            q += " AND v.model_id=?"
            params.append(model_id)
        q += " ORDER BY v.id DESC LIMIT ?;"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_stats() -> dict:
    ensure_schema()
    conn = _conn()
    try:
        total = conn.execute("SELECT COUNT(*) c FROM iv_valuations;").fetchone()["c"]
        today = conn.execute(
            "SELECT COUNT(*) c FROM iv_valuations WHERE date(created_at)=date('now');").fetchone()["c"]
        popular = conn.execute(
            "SELECT m.name, COUNT(*) cnt FROM iv_valuations v LEFT JOIN iv_models m ON m.id=v.model_id "
            "GROUP BY v.model_id ORDER BY cnt DESC LIMIT 5;").fetchall()
        avg_fair = conn.execute("SELECT AVG(fair_price) a FROM iv_valuations WHERE fair_price>0;").fetchone()["a"]
        avg_gap = conn.execute(
            "SELECT AVG((seller_price - fair_price) * 100.0 / fair_price) a FROM iv_valuations "
            "WHERE seller_price IS NOT NULL AND seller_price>0 AND fair_price>0;").fetchone()["a"]
        return {
            "total": total,
            "today": today,
            "popular_models": [dict(r) for r in popular],
            "avg_fair_price": round(avg_fair) if avg_fair else 0,
            "avg_price_gap_pct": round(avg_gap, 1) if avg_gap else 0,
        }
    finally:
        conn.close()
