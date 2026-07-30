"""لایهٔ دیتابیس کارشناسی آیفون — جدول‌ها + CRUD خام.

الگوی مهاجرت این پروژه رعایت شده: CREATE TABLE IF NOT EXISTS برای جدول تازه،
به‌علاوه ALTER TABLE در try/except برای ستون‌های بعدی (اگه لازم شد)، پشت یک
فلگ ماژول‌سطح تا هر درخواست دوباره تلاش نکنه.
"""
import json
import re
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

# سری اصالت دستگاه — برچسب‌ها طبق متن دقیق مالک پروژه (۲۰۲۶-۰۷-۳۰)؛ ارقام ۳/۴/۵ عمداً
# لاتین‌ان (نه فارسی) چون دکمهٔ اینلاین تلگرام از پچ اعداد فارسی سراسری بات عبور نمی‌کنه.
_GRADE_DEFAULTS = [
    ("grade", "grade_m", "سری اصلی M", 0, 1),
    ("grade", "grade_n", "سری تعویض اپل N", -10, 2),
    ("grade", "grade_f", "سری رفرش‌شده F", -25, 3),
    ("grade", "grade_p", "سری ارتقایافته P", 0, 4),
    ("grade", "grade_3", "سری 3 نمونه تست اپل", 0, 5),
    ("grade", "grade_4", "سری 4 پارت نامشخص", 0, 6),
    ("grade", "grade_5", "سری 5 اپل بدون گارانتی", -15, 7),
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


def _iv_series_for_model_name(name: str) -> str:
    """گروه نسل/سری رو از روی اسم مدل حدس می‌زنه — فقط برای classifier اولیهٔ مهاجرت
    یک‌بارهٔ iv_series استفاده می‌شه (_migrate_iv_series_v1)؛ بعد از مهاجرت، تخصیص
    مدل→سری کاملاً دیتای قابل‌ویرایش از پنله، نه قانون هاردکد همیشگی."""
    name = name or ""
    if "SE" in name:
        return "iPhone SE"
    if name.strip() == "iPhone":
        return "iPhone (نسل اول)"
    if name.startswith("iPhone X"):
        return "iPhone X"
    m = re.search(r"iPhone (\d+)", name)
    if m:
        return f"iPhone {m.group(1)}"
    return "سایر"


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
        # grade_pricing: دقیقاً همون الگوی color_pricing/part_pricing — آیا سری اصالت
        # (M/N/F/P/۳/۴/۵) روی قیمت *ردیفِ دقیق* این مدل اثر داره یا نه. این کاملاً جدا و
        # موازی با دستهٔ سراسری «grade» در iv_coefficients هست (که همیشه به‌صورت درصدی
        # روی هر مدلی اعمال می‌شه) — این فلگ فقط کنترل می‌کنه که آیا می‌شه برای یک مدل
        # خاص، به‌ازای یک سری خاص، یک قیمت پایهٔ دقیقاً متفاوت (نه فقط درصدی) هم ثبت کرد.
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN grade_pricing INTEGER NOT NULL DEFAULT 0;")
            conn.commit()
        except Exception:
            pass
        # capacity_pricing: همون الگوی سه توگل بالا، ولی پیش‌فرضش برعکسه — روشن (۱). دلیل:
        # تقریباً همیشه ظرفیت روی قیمت اثر داره؛ بی‌اثر بودنش (مثلاً مدل‌های خیلی قدیمی/ارزون
        # که ظرفیت دیگه فرقی نمی‌کنه) استثناست، نه قاعده — برخلاف رنگ/پارت/سری اصالت که
        # پیش‌فرض بی‌اثرن و ادمین آگاهانه روشنشون می‌کنه. وقتی خاموش بشه، storage_id قبل از
        # resolve به NULL صفر می‌شه (دقیقاً مثل رفتار رنگ/پارت/سری اصالت در resolve_capacity)
        # — یعنی برای این مدل، صرف‌نظر از ظرفیتی که کاربر توی ویزارد انتخاب کرده، از ردیف
        # قیمت عمومی (بدون ظرفیت خاص) استفاده می‌شه؛ خودِ سؤال ظرفیت در ویزارد برای
        # نمایش/شناسایی دستگاه همچنان همیشه پرسیده می‌شه.
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN capacity_pricing INTEGER NOT NULL DEFAULT 1;")
            conn.commit()
        except Exception:
            pass
        # iv_series — گروه‌بندی نسل/سری مدل‌ها (مثل «آیفون ۱۱»، «آیفون X») برای اولین مرحلهٔ
        # ویزارد ربات؛ کاملاً جدا از ستون قدیمی iv_models.series (که فقط سال انتشار رو نگه
        # می‌داره و صرفاً برای نمایش «(سال)» در پنل استفاده می‌شه — دست‌نخورده می‌مونه).
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_series (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        try:
            conn.execute("ALTER TABLE iv_models ADD COLUMN series_id INTEGER;")
            conn.commit()
        except Exception:
            pass
        # iv_storages/iv_parts — نرمال‌سازی: به‌جای متن آزاد روی خودِ ردیف قیمت، هر ظرفیت و
        # هر پارت یه ردیف مستقل با id هست و ردیف قیمت فقط شناسه رو نگه می‌داره.
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_storages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        # iv_repair_parts — کاتالوگ مشترک قطعات برای دو دستهٔ ضریب موازی «component» (معیوب،
        # از قبل موجود) و «replaced» (تعویض‌شده، تازه) — هر دو با option_key یکسان = این کد.
        # این جدول فقط لایهٔ مدیریتیه (یک صفحهٔ ادمین برای هر دو درصد)؛ pricing_engine/
        # scoring_engine مستقیم هیچ‌وقت ازش نمی‌خونن، فقط از iv_coefficients.
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_repair_parts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL UNIQUE,
            label TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1
        );""")
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_capacities (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            storage_id INTEGER,
            color_id INTEGER,
            part_id INTEGER,
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
        # مهاجرت برای نصب‌های قبلی — capacity_label/part_number/color (متن آزاد) به
        # storage_id/part_id/color_id (شناسه، جدول‌های نرمال‌شدهٔ بالا) تبدیل می‌شن.
        # ستون‌های متنی قدیمی برای امنیت داده حذف نمی‌شن، فقط دیگه منبع حقیقت نیستن —
        # از این به بعد فقط شناسه‌ها خونده/نوشته می‌شن.
        for col, ddl in (
            ("part_number", "part_number TEXT NOT NULL DEFAULT ''"),
            ("color", "color TEXT NOT NULL DEFAULT ''"),
            ("storage_id", "storage_id INTEGER"),
            ("color_id", "color_id INTEGER"),
            ("part_id", "part_id INTEGER"),
            # grade_id: بعد سوم fallback قیمت (کنار part_id/color_id) — اشاره به id ردیف
            # iv_coefficients (category='grade')، نه یه جدول جدا؛ چون سری اصالت سراسریه.
            ("grade_id", "grade_id INTEGER"),
        ):
            try:
                conn.execute(f"ALTER TABLE iv_capacities ADD COLUMN {ddl};")
                conn.commit()
            except Exception:
                pass
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_colors (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            sort_order INTEGER NOT NULL DEFAULT 0,
            active INTEGER NOT NULL DEFAULT 1,
            price_percent REAL NOT NULL DEFAULT 0
        );""")
        # price_percent: درصد اثر این رنگ روی قیمت پایه (مثلاً -10 یعنی ۱۰٪ کمتر) — لایهٔ
        # سادهٔ تازه‌ای که ADD می‌شه، مستقل از مکانیزم قدیمی ردیف قیمت اختصاصی هر رنگ
        # (iv_capacities.color_id) که دست‌نخورده می‌مونه؛ اگه ادمین برای مدلی از قبل قیمت
        # دقیق جداگانه به‌ازای هر رنگ ثبت کرده، همون همچنان کار می‌کنه — این ستون فقط
        # برای مدل‌هایی که ادمین می‌خواد ساده‌تر (یک قیمت پایه + درصد رنگ) مدیریت کنه اضافه شده.
        try:
            conn.execute("ALTER TABLE iv_colors ADD COLUMN price_percent REAL NOT NULL DEFAULT 0;")
            conn.commit()
        except Exception:
            pass
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
        # درخواست‌های «می‌خوام بفروشم» از ربات — چه بعد از محاسبهٔ قیمت عادی، چه از مسیر
        # سری‌های توقف‌محاسبه (P/3/4) که قیمت توافقیه. صرفاً یه لید ساده برای ادمینه که
        # باهاش تماس بگیره — نه یه سیستم تیکت/مکالمهٔ دوطرفه (اون از قبل جای دیگه‌ای هست).
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_sell_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            city TEXT DEFAULT '',
            model_id INTEGER,
            model_name TEXT DEFAULT '',
            grade_key TEXT DEFAULT '',
            summary_text TEXT DEFAULT '',
            estimated_price INTEGER,
            status TEXT NOT NULL DEFAULT 'new',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );""")
        # لاگ کامل هر تحلیل AI (بخش «کارشناس مکمل هوش مصنوعی») — برای ممیزی/پیگیری هزینه در
        # پنل. request_context/response خام JSON هستن؛ adjustment_percent همون مقداریه که
        # بعد از clamp+گیت اطمینان واقعاً اعمال شده، نه لزوماً چیزی که مدل خواسته بود.
        conn.execute("""CREATE TABLE IF NOT EXISTS iv_ai_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            valuation_id INTEGER,
            model_id INTEGER,
            capacity_id INTEGER,
            provider TEXT DEFAULT '',
            model_name TEXT DEFAULT '',
            request_context TEXT DEFAULT '{}',
            response_json TEXT DEFAULT '{}',
            adjustment_percent REAL NOT NULL DEFAULT 0,
            confidence INTEGER NOT NULL DEFAULT 0,
            final_price INTEGER,
            warnings TEXT DEFAULT '[]',
            error TEXT DEFAULT '',
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

        # سیدِ پیش‌فرض جدول پارت‌ها — سراسری (نه به‌ازای مدل)، فقط اگه خالیه
        row = conn.execute("SELECT COUNT(*) c FROM iv_parts;").fetchone()
        if row and row["c"] == 0:
            for code, label in PART_OPTIONS:
                if code == "OTHER":
                    continue  # «سایر» یه ردیف واقعی نیست، یعنی «هیچ پارت مشخصی» (part_id=NULL)
                conn.execute("INSERT INTO iv_parts (code, label, sort_order) VALUES (?,?,?);",
                             (code, label, len(PART_OPTIONS)))
            conn.commit()

        # سیدِ کاتالوگ کامل مدل‌های آیفون — فقط اگه جدول خالیه (اولین اجرا).
        # هیچ ردیف قیمتی خودکار ساخته نمی‌شه — فقط مشخصات فنی (ظرفیت/رنگ استاندارد،
        # جدول iv_storages/iv_colors) وارد می‌شه؛ ادمین باید از /admin/iphone/prices
        # قیمت واقعی رو ثبت کنه («سیستم فقط رکوردهایی که ادمین ثبت کرده نشون بده»).
        row = conn.execute("SELECT COUNT(*) c FROM iv_models;").fetchone()
        if row and row["c"] == 0:
            for order_idx, (name, year, caps, colors) in enumerate(_IPHONE_CATALOG, start=1):
                dual_parts, esim_only = _iv_sim_policy(name, order_idx)
                cur = conn.execute(
                    "INSERT INTO iv_models (name, series, sort_order, dual_sim_parts, esim_only) "
                    "VALUES (?,?,?,?,?);", (name, year, order_idx, dual_parts, esim_only))
                model_id = cur.lastrowid
                for cap_idx, cap_label in enumerate(caps):
                    conn.execute(
                        "INSERT INTO iv_storages (model_id, label, sort_order) VALUES (?,?,?);",
                        (model_id, cap_label, cap_idx))
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
        _migrate_normalize_pricing_v2(conn)
        _migrate_iv_series_v1(conn)
        _migrate_repair_parts_catalog_v1(conn)
        _migrate_replaced_category_v1(conn)
        _migrate_repair_vs_replaced_v1(conn)
        _migrate_condition_merge_new_sealed_v1(conn)
        _migrate_grade_category_v1(conn)
        _migrate_grade_labels_v1(conn)
    finally:
        conn.close()
    _SCHEMA_DONE = True


def _migrate_normalize_pricing_v2(conn):
    """قبلاً capacity_label/part_number/color متن آزاد روی خودِ ردیف قیمت ذخیره می‌شد؛
    حالا storage_id/part_id/color_id (شناسه، نه متن) هستن. این مهاجرت یه‌بار همهٔ ردیف‌های
    قدیمی رو بر اساس متن‌شون به شناسهٔ متناظر در iv_storages/iv_parts/iv_colors وصل می‌کنه —
    اگه ظرفیت/رنگی که قبلاً متنی ثبت شده بود هنوز جدول نرمال‌شده نداشت (مثلاً ادمین دستی
    «سایر» زده بود)، همون‌جا یه ردیف تازه براش می‌سازه تا هیچ دیتایی گم نشه."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_NORMALIZE_PRICING_MIGRATED", "0") == "1":
        return
    rows = conn.execute(
        "SELECT id, model_id, capacity_label, part_number, color FROM iv_capacities "
        "WHERE storage_id IS NULL;").fetchall()
    storage_cache: dict[tuple[int, str], int] = {}
    color_cache: dict[tuple[int, str], int] = {}
    part_cache: dict[str, int] = {}
    for r in conn.execute("SELECT id, code FROM iv_parts;").fetchall():
        part_cache[r["code"]] = r["id"]

    def _storage_id(model_id, label):
        label = (label or "").strip()
        if not label:
            return None
        key = (model_id, label)
        if key in storage_cache:
            return storage_cache[key]
        row = conn.execute(
            "SELECT id FROM iv_storages WHERE model_id=? AND label=?;", (model_id, label)).fetchone()
        if row:
            sid = row["id"]
        else:
            cur = conn.execute(
                "INSERT INTO iv_storages (model_id, label, sort_order) VALUES (?,?,?);",
                (model_id, label, int(capacity_sort_key(label))))
            sid = cur.lastrowid
        storage_cache[key] = sid
        return sid

    def _color_id(model_id, name):
        name = (name or "").strip()
        if not name:
            return None
        key = (model_id, name)
        if key in color_cache:
            return color_cache[key]
        row = conn.execute(
            "SELECT id FROM iv_colors WHERE model_id=? AND name=?;", (model_id, name)).fetchone()
        if row:
            cid = row["id"]
        else:
            cur = conn.execute("INSERT INTO iv_colors (model_id, name) VALUES (?,?);", (model_id, name))
            cid = cur.lastrowid
        color_cache[key] = cid
        return cid

    def _part_id(code):
        code = (code or "").strip().upper()
        return part_cache.get(code)  # نبود (مثلاً "OTHER") یعنی NULL — بدون پارت مشخص

    for r in rows:
        sid = _storage_id(r["model_id"], r["capacity_label"])
        cid = _color_id(r["model_id"], r["color"])
        pid = _part_id(r["part_number"])
        conn.execute("UPDATE iv_capacities SET storage_id=?, color_id=?, part_id=? WHERE id=?;",
                     (sid, cid, pid, r["id"]))
    conn.commit()
    set_cfg("IV_NORMALIZE_PRICING_MIGRATED", "1")


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


# درصد پیش‌فرض «تعویض‌شده» برای هر قطعه — تقریباً نصف درصد منفی همون قطعه در دستهٔ
# «معیوب» (component)، چون قطعهٔ تعویض‌شدهٔ سالم بهتر از خراب ولی بدتر از اصلیه.
_REPLACED_DEFAULT_PERCENT = {
    "comp_faceid": -8, "comp_screen": -10, "comp_camera": -5, "comp_speaker": -3,
    "comp_mic": -3, "comp_wifi": -4, "comp_bluetooth": -3, "comp_nfc": -2,
    "comp_wireless_charge": -3, "comp_buttons": -3,
}


def _migrate_iv_series_v1(conn):
    """گروه‌بندی نسل/سری مدل‌ها — یه‌بار اجرا می‌شه: ۱۶ سری (بر اساس _iv_series_for_model_name)
    seed می‌شن و هر مدلی که هنوز series_id نداره بهشون وصل می‌شه. بعدش کاملاً از پنل
    قابل‌ویرایش/جابه‌جاییه — این فقط یه classifier اولیه‌ست، نه قانون همیشگی."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_SERIES_MIGRATED", "0") == "1":
        return
    models = conn.execute("SELECT id, name FROM iv_models WHERE series_id IS NULL;").fetchall()
    series_cache: dict[str, int] = {
        r["name"]: r["id"] for r in conn.execute("SELECT id, name FROM iv_series;").fetchall()
    }
    order_counter = len(series_cache)
    for m in models:
        sname = _iv_series_for_model_name(m["name"])
        sid = series_cache.get(sname)
        if sid is None:
            cur = conn.execute("INSERT INTO iv_series (name, sort_order) VALUES (?,?);",
                                (sname, order_counter))
            sid = cur.lastrowid
            series_cache[sname] = sid
            order_counter += 1
        conn.execute("UPDATE iv_models SET series_id=? WHERE id=?;", (sid, m["id"]))
    conn.commit()
    set_cfg("IV_SERIES_MIGRATED", "1")


def _migrate_repair_parts_catalog_v1(conn):
    """کاتالوگ مشترک قطعات (iv_repair_parts) رو فقط اگه خالیه، از گزینه‌های *فعلی* دستهٔ
    «component» seed می‌کنه — نه فقط پیش‌فرض‌های هاردکد، تا گزینه‌هایی که ادمین قبلاً از
    پنل اضافه کرده هم پوشش داده بشن. باید قبل از _migrate_replaced_category_v1 اجرا بشه."""
    row = conn.execute("SELECT COUNT(*) c FROM iv_repair_parts;").fetchone()
    if not row or row["c"] != 0:
        return
    comp_rows = conn.execute(
        "SELECT option_key, option_label, sort_order FROM iv_coefficients "
        "WHERE category='component' ORDER BY sort_order ASC, id ASC;").fetchall()
    for r in comp_rows:
        conn.execute(
            "INSERT OR IGNORE INTO iv_repair_parts (code, label, sort_order) VALUES (?,?,?);",
            (r["option_key"], r["option_label"], r["sort_order"]))
    conn.commit()


def _migrate_replaced_category_v1(conn):
    """دستهٔ تازهٔ «replaced» (قطعات تعویض‌شده — جدا از «معیوب») رو فقط اگه هنوز هیچ
    ردیفی نداره، به‌ازای هر ردیف iv_repair_parts می‌سازه (با درصد پیش‌فرض نصف‌شده) +
    وزن امتیازدهی مخصوص خودش."""
    row = conn.execute("SELECT COUNT(*) c FROM iv_coefficients WHERE category='replaced';").fetchone()
    if row and row["c"] != 0:
        return
    parts = conn.execute("SELECT code, label, sort_order FROM iv_repair_parts;").fetchall()
    for p in parts:
        pct = _REPLACED_DEFAULT_PERCENT.get(p["code"], -5)
        conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES ('replaced',?,?,?,?);", (p["code"], p["label"], pct, p["sort_order"]))
    conn.execute(
        "INSERT INTO iv_score_weights (category, weight) VALUES ('replaced', 10) "
        "ON CONFLICT(category) DO NOTHING;")
    conn.commit()


def _migrate_repair_vs_replaced_v1(conn):
    """قبل از وجود دستهٔ granular «replaced»، دو گزینهٔ repair_screen/repair_battery توی
    دستهٔ «repair» به‌عنوان جایگزین خام «قطعه تعویض‌شده» عمل می‌کردن — الان با مولتی‌سلکت
    replaced تداخل/دوبل‌شمارش دارن. soft-deactivate (نه حذف) می‌شن، یه‌بار، تا repair
    فقط توصیف‌کنندهٔ شدت/تاریخچهٔ سرویس بمونه (باز شدن/تعمیر برد/آب‌خوردگی)، نه یک قطعهٔ خاص."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_REPAIR_VS_REPLACED_MIGRATED", "0") == "1":
        return
    conn.execute(
        "UPDATE iv_coefficients SET active=0 WHERE category='repair' "
        "AND option_key IN ('repair_screen','repair_battery');")
    conn.commit()
    set_cfg("IV_REPAIR_VS_REPLACED_MIGRATED", "1")


def _migrate_condition_merge_new_sealed_v1(conn):
    """مالک پروژه خواست «نو» و «پلمپ» یک گزینهٔ واحد بشن (از دید کاربر یکیه) — این
    مهاجرت دو گزینهٔ قدیمی رو soft-deactivate می‌کنه (نه حذف، تا اگه ادمین قبلاً روشون
    دستی درصد عوض کرده بود داده گم نشه) و یه گزینهٔ ادغام‌شدهٔ تازه می‌سازه. درصد گزینهٔ
    تازه = همون درصد «پلمپ» قدیم (بالاترین حالت، چون این گزینه بهترین وضعیت ممکنه)."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_CONDITION_MERGE_NEW_SEALED_MIGRATED", "0") == "1":
        return
    conn.execute(
        "UPDATE iv_coefficients SET active=0 WHERE category='condition' "
        "AND option_key IN ('cond_new','cond_sealed');")
    row = conn.execute(
        "SELECT COUNT(*) c FROM iv_coefficients WHERE category='condition' AND option_key='cond_new_sealed';"
    ).fetchone()
    if row and row["c"] == 0:
        conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES ('condition','cond_new_sealed','نو / پلمپ',8,1);")
    conn.commit()
    set_cfg("IV_CONDITION_MERGE_NEW_SEALED_MIGRATED", "1")


def _migrate_grade_category_v1(conn):
    """دستهٔ تازهٔ «grade» (سری اصالت دستگاه: M اصلی/N تعویضی اپل/F رفرش‌شده/P ادیت‌شده/
    ۳ نمونهٔ تست اپل/۴ پارت نامشخص/۵ سایر) — دقیقاً مثل هر دستهٔ ضریب دیگه، فقط داده،
    هیچ کد تازه‌ای توی pricing_engine/scoring_engine لازم نداره (قبلاً category-agnostic
    هستن). گزینه‌های P/3/4 در ویزارد ربات محاسبهٔ قیمت رو کلاً متوقف می‌کنن (بخش bot.py)،
    پس درصدشون عملاً بی‌اثره؛ همچنان یه مقدار پیش‌فرض دارن که اگه بعداً ادمین این
    short-circuit رو خواست غیرفعال کنه، رفتار منطقی داشته باشه."""
    row = conn.execute("SELECT COUNT(*) c FROM iv_coefficients WHERE category='grade';").fetchone()
    if row and row["c"] == 0:
        for cat, key, label, pct, order in _GRADE_DEFAULTS:
            conn.execute(
                "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
                "VALUES (?,?,?,?,?);", (cat, key, label, pct, order))
        conn.execute(
            "INSERT INTO iv_score_weights (category, weight) VALUES ('grade', 10) "
            "ON CONFLICT(category) DO NOTHING;")
        conn.commit()


def _migrate_grade_labels_v1(conn):
    """مالک پروژه متن دقیق برچسب هر سری اصالت رو مشخص کرد (بخش زیر مهاجرت قبلی حدسی
    بود) — این‌جا برچسب‌های ۷ گزینه یک‌بار به متن نهایی به‌روزرسانی می‌شن. طبق درخواست
    صریح، ارقام سری‌های ۳/۴/۵ حتماً لاتین بمونن (نه فارسی) — چون دکمه‌های اینلاین ربات
    اصلاً از پچ اعداد فارسی سراسری عبور نمی‌کنن (فقط متن پیام/کپشن پچ می‌شه، نه
    reply_markup)، همین‌جا نوشتنشون با رقم لاتین کافیه."""
    from db import get_cfg, set_cfg
    if get_cfg("IV_GRADE_LABELS_MIGRATED", "0") == "1":
        return
    for cat, key, label, _pct, _order in _GRADE_DEFAULTS:
        conn.execute(
            "UPDATE iv_coefficients SET option_label=? WHERE category=? AND option_key=?;",
            (label, cat, key))
    conn.commit()
    set_cfg("IV_GRADE_LABELS_MIGRATED", "1")


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
    allowed = {"name", "series", "series_id", "sort_order", "active", "dual_sim_parts", "esim_only",
               "color_pricing", "part_pricing", "grade_pricing", "capacity_pricing"}
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
# iv_capacities از این به بعد فقط شناسه نگه می‌داره (storage_id/color_id/part_id)؛
# ولی همهٔ توابع زیر رشته‌های خوانا (capacity_label/color/part_number) رو هم از طریق
# JOIN برمی‌گردونن تا bot.py/service.py که این کلیدها رو مستقیم می‌خونن دست‌نخورده بمونن.

_CAP_SELECT = """SELECT c.id, c.model_id, c.storage_id, c.color_id, c.part_id, c.grade_id,
    COALESCE(s.label, '') AS capacity_label,
    COALESCE(p.code, '') AS part_number,
    COALESCE(cl.name, '') AS color,
    COALESCE(g.option_key, '') AS grade_key,
    COALESCE(g.option_label, '') AS grade_label,
    c.base_price, c.buy_price_ref, c.sell_price_ref, c.fx_ref_rate, c.demand_percent,
    c.active, c.updated_at
FROM iv_capacities c
LEFT JOIN iv_storages s ON s.id = c.storage_id
LEFT JOIN iv_parts p ON p.id = c.part_id
LEFT JOIN iv_colors cl ON cl.id = c.color_id
LEFT JOIN iv_coefficients g ON g.id = c.grade_id"""


def list_capacities(model_id: int | None = None, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = _CAP_SELECT + " WHERE 1=1"
        params = []
        if model_id is not None:
            q += " AND c.model_id=?"
            params.append(model_id)
        if active_only:
            q += " AND c.active=1"
        q += " ORDER BY c.base_price ASC, c.id ASC;"
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_capacity(cap_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute(_CAP_SELECT + " WHERE c.id=?;", (cap_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_capacity(model_id: int, storage_id: int | None, base_price: int,
                     buy_price_ref: int, sell_price_ref: int,
                     fx_ref_rate: int = 0, demand_percent: float = 0,
                     part_id: int | None = None, color_id: int | None = None,
                     grade_id: int | None = None) -> int:
    ensure_schema()
    conn = _conn()
    try:
        # capacity_label ستون قدیمیه که هنوز NOT NULL بدون DEFAULT روی دیتابیس‌های قدیمیه
        # (SQLite نمی‌تونه NOT NULL رو بدون rebuild کامل جدول بردار) — دیگه منبع حقیقت نیست
        # (storage_id هست)، فقط برای رد نشدن از این constraint رشتهٔ خالی می‌فرستیم.
        cur = conn.execute(
            "INSERT INTO iv_capacities "
            "(model_id, storage_id, part_id, color_id, grade_id, capacity_label, base_price, buy_price_ref, "
            "sell_price_ref, fx_ref_rate, demand_percent) VALUES (?,?,?,?,?,?,?,?,?,?,?);",
            (model_id, storage_id, part_id, color_id, grade_id, "", base_price, buy_price_ref, sell_price_ref,
             fx_ref_rate, demand_percent))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_capacity(cap_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"storage_id", "part_id", "color_id", "grade_id", "base_price", "buy_price_ref",
               "sell_price_ref", "fx_ref_rate", "demand_percent", "active"}
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


def get_capacity_exact(model_id: int, storage_id: int | None, part_id: int | None = None,
                        color_id: int | None = None, grade_id: int | None = None) -> dict | None:
    """ردیف دقیقاً منطبق با (مدل، ظرفیت، پارت، رنگ، سری اصالت — با شناسه) رو برمی‌گردونه
    (یا None) — برای upsert_capacity استفاده می‌شه. مقایسهٔ NULL-safe با IS (نه =، چون
    NULL=NULL توی SQL همیشه false برمی‌گرده) — storage_id هم از ۲۰۲۶-۰۷-۳۰ می‌تونه NULL باشه
    (مدل‌هایی که ظرفیت روش قیمت رو عوض نمی‌کنه، iv_models.capacity_pricing)."""
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute(
            "SELECT * FROM iv_capacities WHERE model_id=? AND storage_id IS ? AND part_id IS ? "
            "AND color_id IS ? AND grade_id IS ? LIMIT 1;",
            (model_id, storage_id, part_id, color_id, grade_id)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def upsert_capacity(model_id: int, storage_id: int | None, base_price: int, buy_price_ref: int,
                     sell_price_ref: int, fx_ref_rate: int = 0, demand_percent: float = 0,
                     part_id: int | None = None, color_id: int | None = None,
                     grade_id: int | None = None) -> int:
    """ثبت یا به‌روزرسانی قیمت یک ترکیب (ظرفیت+پارت+رنگ+سری اصالت) — اگه این ترکیب دقیق از
    قبل ثبت شده باشه آپدیت می‌شه (نه رد یا تکراری)، وگرنه ردیف تازه ساخته می‌شه. کاربر
    هیچ‌وقت پیام «قبلاً ثبت شده» نمی‌بینه."""
    existing = get_capacity_exact(model_id, storage_id, part_id, color_id, grade_id)
    if existing:
        update_capacity(existing["id"], base_price=base_price, buy_price_ref=buy_price_ref,
                         sell_price_ref=sell_price_ref, fx_ref_rate=fx_ref_rate,
                         demand_percent=demand_percent, active=1)
        return existing["id"]
    return create_capacity(model_id, storage_id, base_price, buy_price_ref, sell_price_ref,
                            fx_ref_rate, demand_percent, part_id=part_id, color_id=color_id,
                            grade_id=grade_id)


def _find_storage_id(model_id: int, label: str) -> int | None:
    label = (label or "").strip()
    if not label:
        return None
    conn = _conn()
    try:
        row = conn.execute("SELECT id FROM iv_storages WHERE model_id=? AND label=?;",
                            (model_id, label)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _find_color_id(model_id: int, name: str) -> int | None:
    name = (name or "").strip()
    if not name:
        return None
    conn = _conn()
    try:
        row = conn.execute("SELECT id FROM iv_colors WHERE model_id=? AND name=?;",
                            (model_id, name)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _find_part_id(code: str) -> int | None:
    code = (code or "").strip().upper()
    if not code:
        return None
    conn = _conn()
    try:
        row = conn.execute("SELECT id FROM iv_parts WHERE code=?;", (code,)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def _find_coefficient_id(category: str, option_key: str) -> int | None:
    """id ردیف iv_coefficients — برای سری اصالت (grade) که برخلاف رنگ/پارت یه جدول
    کاتالوگ جدا نداره، همون ردیف دستهٔ سراسری `iv_coefficients` مرجع resolve_capacity هم
    هست (بعد سوم fallback قیمت، کنار color_id/part_id)."""
    option_key = (option_key or "").strip()
    if not option_key:
        return None
    conn = _conn()
    try:
        row = conn.execute("SELECT id FROM iv_coefficients WHERE category=? AND option_key=?;",
                            (category, option_key)).fetchone()
        return row["id"] if row else None
    finally:
        conn.close()


def resolve_capacity(model_id: int, capacity_label: str, part_number: str = "", color: str = "",
                      grade: str = "") -> dict | None:
    """قیمت دقیق (مدل+ظرفیت+پارت+رنگ+سری اصالت) رو پیدا می‌کنه؛ اگه قیمت اختصاصی برای اون
    ترکیب ثبت نشده باشه، fallback می‌کنه از دقیق‌ترین ترکیب (کمترین بعدِ عمومی) به سمت
    عمومی‌ترین (هر چهار بعد NULL) — یعنی ادمین فقط جایی که قیمت واقعاً فرق داره لازمه
    ظرفیت/پارت/رنگ/سری مشخص وارد کنه، بقیه از قیمت عمومی‌تر استفاده می‌کنن.

    ورودی‌ها همچنان رشته‌ن (نه شناسه) چون ویزارد ربات با برچسب/کلید کار می‌کنه، نه id —
    این تابع خودش قبل از جست‌وجو رشته‌ها رو به شناسهٔ متناظر تبدیل می‌کنه. `grade` همون
    option_key دستهٔ سراسری `iv_coefficients(category='grade')` هست (مثل 'grade_n')، نه
    یه نام آزاد مثل رنگ.

    اگه ادمین اثر رنگ/پارت/سری/ظرفیت روی قیمت این مدل رو خاموش کرده باشه
    (iv_models.color_pricing/part_pricing/grade_pricing/capacity_pricing)، همون بعد این‌جا
    قبل از جست‌وجو صفر می‌شه — یعنی کاربر هرچی هم توی ویزارد انتخاب کرده باشه، قیمت از
    ردیف عمومی همون مدل خونده می‌شه. capacity_label نامعتبر (که اصلاً به هیچ ظرفیت
    ثبت‌شده‌ای برای این مدل نمی‌خوره) مستقل از این توگل همیشه None برمی‌گردونه — چون خودِ
    سؤال ظرفیت در ویزارد همیشه پرسیده می‌شه (برای شناسایی دستگاه)، این حالت یعنی یه
    برچسب واقعاً نامعتبر رسیده، نه اینکه ظرفیت بی‌اثره."""
    ensure_schema()
    model = get_model(model_id)
    if model:
        if not model.get("color_pricing"):
            color = ""
        if not model.get("part_pricing"):
            part_number = ""
        if not model.get("grade_pricing"):
            grade = ""
    found_storage_id = _find_storage_id(model_id, capacity_label)
    if found_storage_id is None:
        return None
    storage_id = None if (model and not model.get("capacity_pricing", 1)) else found_storage_id
    part_id = _find_part_id(part_number) if part_number else None
    color_id = _find_color_id(model_id, color) if color else None
    grade_id = _find_coefficient_id("grade", grade) if grade else None
    conn = _conn()
    try:
        def _q(s, p, c, g):
            return conn.execute(
                _CAP_SELECT + " WHERE c.model_id=? AND c.storage_id IS ? AND c.part_id IS ? "
                "AND c.color_id IS ? AND c.grade_id IS ? AND c.active=1 LIMIT 1;",
                (model_id, s, p, c, g)).fetchone()

        storage_candidates = [storage_id, None] if storage_id is not None else [None]
        part_candidates = [part_id, None] if part_id is not None else [None]
        color_candidates = [color_id, None] if color_id is not None else [None]
        grade_candidates = [grade_id, None] if grade_id is not None else [None]
        # ترکیب‌ها رو از دقیق‌ترین (کمترین None) به عمومی‌ترین مرتب می‌کنیم — یعنی ادمین
        # فقط جایی که واقعاً قیمت فرق داره لازمه دقیق وارد کنه.
        combos = sorted(
            {(s, p, c, g) for s in storage_candidates for p in part_candidates
             for c in color_candidates for g in grade_candidates},
            key=lambda t: sum(1 for x in t if x is None))
        for s, p, c, g in combos:
            row = _q(s, p, c, g)
            if row:
                return dict(row)
        return None
    finally:
        conn.close()


def list_capacity_labels(model_id: int, active_only: bool = True) -> list[str]:
    """برچسب‌های یکتای ظرفیت این مدل (برای مرحلهٔ انتخاب ظرفیت در ویزارد ربات)، مرتب‌شده
    به ترتیب اندازهٔ واقعی — مستقیم از iv_storages، نه از ردیف‌های قیمت (چون یه ظرفیت
    ممکنه هنوز هیچ قیمتی نداشته باشه ولی باید همچنان قابل‌انتخاب باشه)."""
    return [s["label"] for s in list_storages(model_id, active_only=active_only)]


# ─── ظرفیت‌ها (iv_storages) ─────────────────────────────────────────────

def list_storages(model_id: int, active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_storages WHERE model_id=?"
        params = [model_id]
        if active_only:
            q += " AND active=1"
        rows = [dict(r) for r in conn.execute(q, params).fetchall()]
        rows.sort(key=lambda s: capacity_sort_key(s["label"]))
        return rows
    finally:
        conn.close()


def get_storage(storage_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_storages WHERE id=?;", (storage_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_storage(model_id: int, label: str, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO iv_storages (model_id, label, sort_order) VALUES (?,?,?);",
                            (model_id, label.strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def delete_storage(storage_id: int) -> None:
    """حذف یه ظرفیت + همهٔ ردیف‌های قیمتی که بهش وابسته‌ان (چون storage_id اجباریه، ردیف
    قیمت بدون ظرفیت معنی نداره — برخلاف رنگ/پارت که NULL‌شون می‌کنیم، نه حذف کامل)."""
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("DELETE FROM iv_capacities WHERE storage_id=?;", (storage_id,))
        conn.execute("DELETE FROM iv_storages WHERE id=?;", (storage_id,))
        conn.commit()
    finally:
        conn.close()


# ─── پارت‌ها (iv_parts، سراسری — نه به‌ازای مدل) ────────────────────────

def list_parts(active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_parts"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def get_part(part_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_parts WHERE id=?;", (part_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_part(code: str, label: str, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO iv_parts (code, label, sort_order) VALUES (?,?,?);",
                            (code.strip().upper(), label.strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_part(part_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"code", "label", "sort_order", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(f"UPDATE iv_parts SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
                     [fields[c] for c in cols] + [part_id])
        conn.commit()
    finally:
        conn.close()


def delete_part(part_id: int) -> None:
    """حذف یه پارت — ردیف‌های قیمتی که بهش وابسته بودن NULL می‌شن (یعنی «بدون پارت مشخص»/
    عمومی می‌شن)، نه حذف کامل؛ چون پارت برخلاف ظرفیت اختیاریه، از دست رفتن قیمت درست نیست."""
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("UPDATE iv_capacities SET part_id=NULL WHERE part_id=?;", (part_id,))
        conn.execute("DELETE FROM iv_parts WHERE id=?;", (part_id,))
        conn.commit()
    finally:
        conn.close()


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


def get_color(color_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_colors WHERE id=?;", (color_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_color(color_id: int, **fields) -> None:
    """ویرایش نام نمایشی رنگ (مثلاً «نور ستاره‌ای» → «سفید» چون بازار ایران به این اسم
    می‌شناستش — رنگ جدید تعریف نمی‌شه، همون رنگ اصلی فقط اسمش عوض می‌شه) + ترتیب/فعال‌بودن
    + درصد اثر روی قیمت (`price_percent`)."""
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "sort_order", "active", "price_percent"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(f"UPDATE iv_colors SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
                     [fields[c] for c in cols] + [color_id])
        conn.commit()
    finally:
        conn.close()


def delete_color(color_id: int) -> None:
    """حذف یه رنگ — ردیف‌های قیمتی وابسته NULL می‌شن (عمومی/بدون رنگ مشخص)، نه حذف کامل؛
    مثل delete_part، از دست رفتن قیمت ثبت‌شده به‌خاطر پاک‌کردن یه گزینهٔ کاتالوگ درست نیست."""
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("UPDATE iv_capacities SET color_id=NULL WHERE color_id=?;", (color_id,))
        conn.execute("DELETE FROM iv_colors WHERE id=?;", (color_id,))
        conn.commit()
    finally:
        conn.close()


# ─── سری/نسل‌ها (iv_series) — گروه‌بندی مدل‌ها برای مرحلهٔ اول ویزارد ربات ──

def list_series(active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_series"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def get_series(series_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_series WHERE id=?;", (series_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def create_series(name: str, sort_order: int = 0) -> int:
    ensure_schema()
    conn = _conn()
    try:
        cur = conn.execute("INSERT INTO iv_series (name, sort_order) VALUES (?,?);",
                            (name.strip(), sort_order))
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def update_series(series_id: int, **fields) -> None:
    ensure_schema()
    if not fields:
        return
    allowed = {"name", "sort_order", "active"}
    cols = [k for k in fields if k in allowed]
    if not cols:
        return
    conn = _conn()
    try:
        conn.execute(f"UPDATE iv_series SET {', '.join(c+'=?' for c in cols)} WHERE id=?;",
                     [fields[c] for c in cols] + [series_id])
        conn.commit()
    finally:
        conn.close()


def delete_series(series_id: int) -> None:
    """حذف نرم — مدل‌های وابسته سری‌شون NULL می‌شه (نه حذف مدل)، دقیقاً مثل delete_part/
    delete_color: پاک‌کردن یه گزینهٔ گروه‌بندی نباید داده/قیمت مدل رو از بین ببره."""
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("UPDATE iv_models SET series_id=NULL WHERE series_id=?;", (series_id,))
        conn.execute("DELETE FROM iv_series WHERE id=?;", (series_id,))
        conn.commit()
    finally:
        conn.close()


def list_bot_visible_series() -> list[dict]:
    """فقط سری‌هایی که حداقل یک مدل فعال با حداقل یک ردیف قیمت فعال دارن — تا ویزارد
    ربات هیچ‌وقت گزینهٔ بن‌بست (سری بدون هیچ مدل/قیمتی) نشون نده."""
    ensure_schema()
    conn = _conn()
    try:
        q = """SELECT DISTINCT s.* FROM iv_series s
               JOIN iv_models m ON m.series_id = s.id AND m.active = 1
               JOIN iv_capacities c ON c.model_id = m.id AND c.active = 1
               WHERE s.active = 1
               ORDER BY s.sort_order ASC, s.id ASC;"""
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def list_bot_visible_models(series_id: int) -> list[dict]:
    """مدل‌های فعال یک سری که حداقل یک ردیف قیمت فعال دارن — همون فیلتر «بدون بن‌بست»."""
    ensure_schema()
    conn = _conn()
    try:
        q = """SELECT DISTINCT m.* FROM iv_models m
               JOIN iv_capacities c ON c.model_id = m.id AND c.active = 1
               WHERE m.series_id = ? AND m.active = 1
               ORDER BY m.sort_order ASC, m.id ASC;"""
        return [dict(r) for r in conn.execute(q, (series_id,)).fetchall()]
    finally:
        conn.close()


# ─── کاتالوگ مشترک قطعات تعمیر (iv_repair_parts) ────────────────────────────
# لایهٔ مدیریتیه برای مدیریت هم‌زمان دو دستهٔ ضریب موازی «component» (معیوب) و
# «replaced» (تعویض‌شده) با یک صفحهٔ ادمین واحد. خودِ pricing_engine/scoring_engine
# مستقیم از این جدول نمی‌خونن — فقط iv_coefficients.

def list_repair_parts(active_only: bool = True) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_repair_parts"
        if active_only:
            q += " WHERE active=1"
        q += " ORDER BY sort_order ASC, id ASC;"
        return [dict(r) for r in conn.execute(q).fetchall()]
    finally:
        conn.close()


def create_repair_part(code: str, label: str, defective_percent: float = 0,
                        replaced_percent: float = 0, sort_order: int = 0) -> int:
    """یه ردیف iv_repair_parts + یه ردیف iv_coefficients توی هرکدوم از دو دستهٔ
    component/replaced (با option_key یکسان = code) رو هم‌زمان می‌سازه."""
    ensure_schema()
    conn = _conn()
    try:
        code = code.strip()
        label = label.strip()
        cur = conn.execute("INSERT INTO iv_repair_parts (code, label, sort_order) VALUES (?,?,?);",
                            (code, label, sort_order))
        part_id = cur.lastrowid
        conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES ('component',?,?,?,?);", (code, label, defective_percent, sort_order))
        conn.execute(
            "INSERT INTO iv_coefficients (category, option_key, option_label, percent, sort_order) "
            "VALUES ('replaced',?,?,?,?);", (code, label, replaced_percent, sort_order))
        conn.commit()
        return part_id
    finally:
        conn.close()


def update_repair_part(part_id: int, label: str | None = None,
                        defective_percent: float | None = None,
                        replaced_percent: float | None = None,
                        active: int | None = None) -> None:
    """ویرایش یک قطعه — label/active روی خودِ iv_repair_parts و هر دو ردیف iv_coefficients
    (component+replaced با option_key=code) اعمال می‌شه؛ هر درصد فقط روی دستهٔ خودش."""
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT code FROM iv_repair_parts WHERE id=?;", (part_id,)).fetchone()
        if not row:
            return
        code = row["code"]
        part_fields, part_params = [], []
        if label is not None:
            part_fields.append("label=?"); part_params.append(label)
        if active is not None:
            part_fields.append("active=?"); part_params.append(active)
        if part_fields:
            conn.execute(f"UPDATE iv_repair_parts SET {', '.join(part_fields)} WHERE id=?;",
                         part_params + [part_id])
        for category, pct in (("component", defective_percent), ("replaced", replaced_percent)):
            coef_fields, coef_params = [], []
            if label is not None:
                coef_fields.append("option_label=?"); coef_params.append(label)
            if pct is not None:
                coef_fields.append("percent=?"); coef_params.append(pct)
            if active is not None:
                coef_fields.append("active=?"); coef_params.append(active)
            if coef_fields:
                conn.execute(
                    f"UPDATE iv_coefficients SET {', '.join(coef_fields)} "
                    "WHERE category=? AND option_key=?;", coef_params + [category, code])
        conn.commit()
    finally:
        conn.close()


def delete_repair_part(part_id: int) -> None:
    """soft-delete — خودِ قطعه + هر دو ردیف ضریب وابسته‌اش غیرفعال می‌شن (نه حذف کامل)،
    مثل الگوی delete_coefficient موجود، تا تاریخچهٔ کارشناسی‌های قبلی معتبر بمونه."""
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT code FROM iv_repair_parts WHERE id=?;", (part_id,)).fetchone()
        if not row:
            return
        code = row["code"]
        conn.execute("UPDATE iv_repair_parts SET active=0 WHERE id=?;", (part_id,))
        conn.execute(
            "UPDATE iv_coefficients SET active=0 WHERE category IN ('component','replaced') "
            "AND option_key=?;", (code,))
        conn.commit()
    finally:
        conn.close()


# ─── ضرایب ───────────────────────────────────────────────────────────────

COEFFICIENT_CATEGORIES = ["condition", "battery", "repair", "registry", "box", "cosmetic", "cable",
                           "component", "replaced", "grade"]

# سه گزینهٔ سری اصالت که محاسبهٔ قیمت رو کلاً متوقف می‌کنن و به‌جاش پیام «توافقی» +
# دکمهٔ «می‌خوام بفروشم» نشون داده می‌شه (bot.py) — یک‌جا تعریف شده تا ربات و پنل
# هردو از همین منبع بخونن، نه هاردکد جدا.
GRADE_STOP_CALC_KEYS = {"grade_p", "grade_3", "grade_4"}


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


def recent_valuations_for_capacity(model_id: int, capacity_id: int, limit: int = 10) -> list[dict]:
    """آخرین کارشناسی‌های واقعی همین مدل+ظرفیت — برای تشخیص روند قیمت توسط کارشناس AI
    (بخش «کارشناس مکمل هوش مصنوعی»)، جدا از تراکنش‌های واقعی iv_transactions."""
    ensure_schema()
    conn = _conn()
    try:
        rows = conn.execute(
            "SELECT fair_price, market_price, score, created_at FROM iv_valuations "
            "WHERE model_id=? AND capacity_id=? ORDER BY id DESC LIMIT ?;",
            (model_id, capacity_id, limit)).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


# ─── کارشناس مکمل هوش مصنوعی ──────────────────────────────────────────────

def create_ai_analysis(**fields) -> int:
    ensure_schema()
    cols = ["valuation_id", "model_id", "capacity_id", "provider", "model_name",
            "request_context", "response_json", "adjustment_percent", "confidence",
            "final_price", "warnings", "error"]
    values = [fields.get(c) for c in cols]
    conn = _conn()
    try:
        cur = conn.execute(
            f"INSERT INTO iv_ai_analyses ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)});",
            values)
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_ai_analyses(limit: int = 50) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = ("SELECT a.*, m.name AS model_name_join, c.capacity_label FROM iv_ai_analyses a "
             "LEFT JOIN iv_models m ON m.id=a.model_id "
             "LEFT JOIN iv_capacities c ON c.id=a.capacity_id "
             "ORDER BY a.id DESC LIMIT ?;")
        return [dict(r) for r in conn.execute(q, (limit,)).fetchall()]
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


# ─── درخواست‌های «می‌خوام بفروشم» ────────────────────────────────────────

def create_sell_request(**fields) -> int:
    ensure_schema()
    allowed = {"user_id", "user_name", "phone", "city", "model_id", "model_name",
               "grade_key", "summary_text", "estimated_price", "status"}
    cols = [k for k in fields if k in allowed]
    conn = _conn()
    try:
        cur = conn.execute(
            f"INSERT INTO iv_sell_requests ({', '.join(cols)}) VALUES ({', '.join('?' for _ in cols)});",
            [fields[c] for c in cols])
        conn.commit()
        return cur.lastrowid
    finally:
        conn.close()


def list_sell_requests(status: str | None = None, limit: int = 100) -> list[dict]:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT * FROM iv_sell_requests WHERE 1=1"
        params = []
        if status:
            q += " AND status=?"
            params.append(status)
        q += " ORDER BY id DESC LIMIT ?;"
        params.append(limit)
        return [dict(r) for r in conn.execute(q, params).fetchall()]
    finally:
        conn.close()


def get_sell_request(req_id: int) -> dict | None:
    ensure_schema()
    conn = _conn()
    try:
        row = conn.execute("SELECT * FROM iv_sell_requests WHERE id=?;", (req_id,)).fetchone()
        return dict(row) if row else None
    finally:
        conn.close()


def update_sell_request_status(req_id: int, status: str) -> None:
    ensure_schema()
    conn = _conn()
    try:
        conn.execute("UPDATE iv_sell_requests SET status=? WHERE id=?;", (status, req_id))
        conn.commit()
    finally:
        conn.close()


def count_sell_requests(status: str | None = None) -> int:
    ensure_schema()
    conn = _conn()
    try:
        q = "SELECT COUNT(*) c FROM iv_sell_requests WHERE 1=1"
        params = []
        if status:
            q += " AND status=?"
            params.append(status)
        return conn.execute(q, params).fetchone()["c"]
    finally:
        conn.close()
