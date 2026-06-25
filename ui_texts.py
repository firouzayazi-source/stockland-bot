from db import get_ui_text, set_ui_text

# ═══════════════════════════════════════════════════════════════════════════
#  DEFAULT_UI_TEXTS — همه متن‌های ربات از اینجا قابل ویرایش است
# ═══════════════════════════════════════════════════════════════════════════

DEFAULT_UI_TEXTS = {

    # ─── دکمه‌های منوی اصلی ────────────────────────────────────────────────
    "MAIN_BTN_MY_ORDERS":        "خریدهای من 🧾",
    "MAIN_BTN_WALLET":           "کیف پول 💰",
    "MAIN_BTN_PARTNER_REQUEST":  "درخواست نمایندگی 📝",
    "MAIN_BTN_PARTNER_PANEL":    "پنل همکار 🤝",
    "MAIN_BTN_GUIDE":            "راهنما 🔑",
    "MAIN_BTN_SUPPORT":          "پشتیبانی 👨‍💻",

    # ─── پیام‌های خوش‌آمدگویی ─────────────────────────────────────────────
    "MSG_WELCOME":
        "سلام {name} 👋\n\nبه ربات فروش سرویس خوش آمدید.\n"
        "از منوی زیر، سرویس مورد نظر خود را انتخاب کنید.",
    "MSG_BTN_DISABLED":   "این بخش در حال حاضر غیرفعال است.",

    # ─── کیف پول ──────────────────────────────────────────────────────────
    "MSG_WALLET_BALANCE":
        "💰 موجودی کیف پول شما: <b>{balance}</b> تومان",
    "MSG_WALLET_SELECT_METHOD":
        "لطفاً روش پرداخت را انتخاب کنید:",
    "MSG_WALLET_AMOUNT_REQUEST":
        "مقدار شارژ کیف پول را به تومان ارسال کنید.\nحداقل مبلغ: <b>{min_amount}</b> تومان",
    "MSG_WALLET_AMOUNT_INVALID":
        "⚠️ مبلغ نامعتبر است. لطفاً یک عدد صحیح وارد کنید.",
    "MSG_WALLET_MIN_AMOUNT":
        "⚠️ حداقل مبلغ شارژ <b>{min_amount}</b> تومان است.",
    "MSG_WALLET_TOPUP_SUCCESS":
        "✅ کیف پول شما با موفقیت شارژ شد.\n"
        "مبلغ: <b>{amount}</b> تومان\n"
        "کد پیگیری: <code>{ref_id}</code>",
    "WALLET_QUICK_AMOUNTS": "10000,50000,100000,500000",
    "BTN_WALLET_CHARGE":  "➕ شارژ حساب",
    "BTN_WALLET_GATEWAY": "🌐 درگاه پرداخت",
    "BTN_WALLET_CARD":    "💳 کارت به کارت",

    # ─── جریان خرید ───────────────────────────────────────────────────────
    "MSG_PURCHASE_REDIRECT":
        "برای تکمیل پرداخت روی دکمه زیر بزنید.\n"
        "پس از پرداخت موفق، نتیجه به‌صورت خودکار برای شما ارسال می‌شود.",
    "MSG_PURCHASE_CANCELLED": "❌ خرید لغو شد.",
    "MSG_PURCHASE_SUCCESS":
        "✅ خرید موفق!\n\n"
        "شماره سفارش: <b>#{order_id}</b>\n"
        "سرویس: <b>{title}</b>\n"
        "مبلغ: <b>{price}</b> تومان\n\n"
        "<code>{feed_data}</code>",
    "MSG_PURCHASE_QUEUED":
        "✅ سفارش ثبت شد.\n\n"
        "شماره سفارش: <b>#{order_id}</b>\n"
        "سرویس: <b>{title}</b>\n"
        "موجودی تکمیل است. به محض شارژ ارسال می‌شود.",
    "MSG_PURCHASE_NO_STOCK":
        "⚠️ موجودی این سرویس به پایان رسیده است.\n"
        "سفارش شما در صف انتظار قرار گرفت.",
    "MSG_INSUFFICIENT_BALANCE":
        "⚠️ موجودی کیف پول شما کافی نیست.\n"
        "موجودی فعلی: <b>{balance}</b> تومان\n"
        "مبلغ مورد نیاز: <b>{price}</b> تومان",
    "MSG_DAILY_LIMIT_REACHED":
        "⛔ سقف خرید روزانه این محصول ({limit} عدد) برای شما تکمیل شده است.\n"
        "لطفاً فردا دوباره اقدام کنید.",

    # ─── پرداخت ───────────────────────────────────────────────────────────
    "MSG_PAYMENT_ERROR":
        "⚠️ خطا در ارتباط با سیستم پرداخت. لطفاً چند لحظه بعد دوباره تلاش کنید.",
    "MSG_PAYMENT_BTN":    "ورود به درگاه پرداخت 💳",

    # ─── سفارش‌ها ─────────────────────────────────────────────────────────
    "MSG_NO_ORDERS":     "شما هنوز هیچ خریدی انجام نداده‌اید.",
    "MSG_ORDERS_HEADER": "📋 آخرین خریدهای شما:",

    # ─── پشتیبانی و راهنما ────────────────────────────────────────────────
    "SUPPORT_TEXT":
        "برای ارتباط با پشتیبانی پیام خود را ارسال کنید.\n"
        "تیم پشتیبانی در اسرع وقت پاسخ می‌دهند.",
    "HELP_TEXT":
        "📖 راهنمای استفاده از ربات:\n\n"
        "💰 <b>کیف پول:</b> مشاهده موجودی و شارژ حساب\n"
        "🧾 <b>خریدهای من:</b> مشاهده آخرین سفارش‌ها\n"
        "📝 <b>درخواست نمایندگی:</b> ارسال درخواست همکاری\n"
        "👨‍💻 <b>پشتیبانی:</b> ارتباط با تیم پشتیبانی",

    # ─── همکاران ──────────────────────────────────────────────────────────
    "MSG_PARTNER_ALREADY":
        "✅ شما قبلاً به عنوان همکار تأیید شده‌اید.\n"
        "از پنل همکار استفاده کنید.",
    "MSG_PARTNER_PENDING":
        "⏳ درخواست شما در حال بررسی است.\nلطفاً منتظر بمانید.",
    "MSG_PARTNER_APPROVED":
        "🎉 تبریک! درخواست نمایندگی شما تأیید شد.\n"
        "اکنون می‌توانید از پنل همکار استفاده کنید.",
    "MSG_PARTNER_REJECTED":
        "❌ متأسفانه درخواست نمایندگی شما رد شد.\n"
        "برای اطلاعات بیشتر با پشتیبانی تماس بگیرید.",
    "MSG_PARTNER_REQUEST_SENT":
        "✅ درخواست شما ثبت شد.\n"
        "پس از بررسی، نتیجه اعلام خواهد شد.",
    "MSG_PARTNER_PHONE_REQUEST":
        "لطفاً شماره موبایل خود را وارد کنید:",
    "MSG_PARTNER_CITY_REQUEST":
        "لطفاً شهر خود را وارد کنید:",
    "MSG_PARTNER_SHOP_REQUEST":
        "لطفاً نام فروشگاه یا کانال خود را وارد کنید:",
    "PARTNER_GUIDE_TEXT":
        "📖 <b>راهنمای همکاری در فروش</b>\n\n"
        "متن راهنمای همکاری توسط مدیر تنظیم نشده است.\n"
        "برای اطلاعات بیشتر با پشتیبانی در تماس باشید.",

    # ─── عناوین UI ────────────────────────────────────────────────────────
    "TXT_MAIN_MENU_TITLE":   "منوی اصلی",
    "TXT_SELECT_CATEGORY":   "لطفاً یکی از دسته‌بندی‌های زیر را انتخاب کنید:",
    "TXT_SELECT_PRODUCT":    "لطفاً یکی از سرویس‌های زیر را انتخاب کنید:",
    "TXT_NO_PRODUCTS":       "در حال حاضر محصولی در این دسته موجود نیست.",
    "TXT_BACK_BTN":          "🔙 بازگشت",
    "TXT_BACK_MAIN_BTN":     "🔙 بازگشت به منو",
    "TXT_CANCEL_BTN":        "❌ انصراف",
}

# ─── Cache & accessor ──────────────────────────────────────────────────────

_ui_cache: dict[str, str] = {}


def t(key: str, default: str | None = None) -> str:
    """دریافت متن UI از DB با fallback به پیش‌فرض."""
    if default is None:
        default = DEFAULT_UI_TEXTS.get(key, key)
    if key in _ui_cache:
        return _ui_cache[key]
    try:
        v = get_ui_text(key)
    except Exception:
        v = None
    if v is None or str(v).strip() == "":
        v = default
    _ui_cache[key] = v
    return v


def tf(key: str, **kwargs) -> str:
    """دریافت متن با format — t(key).format(**kwargs)"""
    return t(key).format(**kwargs)


def ui_cache_clear() -> None:
    _ui_cache.clear()


# ─── Main Button enable/disable ───────────────────────────────────────────

MAIN_BUTTON_KEYS = [
    "MAIN_BTN_MY_ORDERS",
    "MAIN_BTN_WALLET",
    "MAIN_BTN_PARTNER_REQUEST",
    "MAIN_BTN_PARTNER_PANEL",
    "MAIN_BTN_GUIDE",
    "MAIN_BTN_SUPPORT",
]


def _main_btn_flag_key(btn_key: str) -> str:
    return f"MAIN_BTN_ENABLED_{btn_key}"


def is_main_button_enabled(btn_key: str) -> bool:
    raw = t(_main_btn_flag_key(btn_key), "1")
    return str(raw).strip().lower() not in ("0", "false", "off", "no")


def set_main_button_enabled(btn_key: str, enabled: bool) -> None:
    set_ui_text(_main_btn_flag_key(btn_key), "1" if enabled else "0")
    _ui_cache.pop(_main_btn_flag_key(btn_key), None)

# ─── Text group definitions (for admin panel display) ─────────────────────

TEXT_GROUPS = {
    "دکمه‌های منو": [
        "MAIN_BTN_MY_ORDERS", "MAIN_BTN_WALLET",
        "MAIN_BTN_PARTNER_REQUEST", "MAIN_BTN_PARTNER_PANEL",
        "MAIN_BTN_GUIDE", "MAIN_BTN_SUPPORT",
        "BTN_WALLET_CHARGE", "BTN_WALLET_GATEWAY", "BTN_WALLET_CARD",
        "TXT_BACK_BTN", "TXT_BACK_MAIN_BTN", "TXT_CANCEL_BTN",
    ],
    "پیام‌های اصلی": [
        "MSG_WELCOME", "MSG_BTN_DISABLED", "TXT_MAIN_MENU_TITLE",
        "TXT_SELECT_CATEGORY", "TXT_SELECT_PRODUCT", "TXT_NO_PRODUCTS",
    ],
    "کیف پول": [
        "MSG_WALLET_BALANCE", "MSG_WALLET_SELECT_METHOD",
        "MSG_WALLET_AMOUNT_REQUEST", "MSG_WALLET_AMOUNT_INVALID",
        "MSG_WALLET_MIN_AMOUNT", "MSG_WALLET_TOPUP_SUCCESS",
        "WALLET_QUICK_AMOUNTS",
    ],
    "جریان خرید": [
        "MSG_PURCHASE_REDIRECT", "MSG_PURCHASE_CANCELLED",
        "MSG_PURCHASE_SUCCESS", "MSG_PURCHASE_QUEUED",
        "MSG_PURCHASE_NO_STOCK", "MSG_INSUFFICIENT_BALANCE",
        "MSG_DAILY_LIMIT_REACHED", "MSG_PAYMENT_ERROR", "MSG_PAYMENT_BTN",
    ],
    "سفارش‌ها": [
        "MSG_NO_ORDERS", "MSG_ORDERS_HEADER",
    ],
    "پشتیبانی و راهنما": [
        "SUPPORT_TEXT", "HELP_TEXT",
    ],
    "همکاران": [
        "MSG_PARTNER_ALREADY", "MSG_PARTNER_PENDING",
        "MSG_PARTNER_APPROVED", "MSG_PARTNER_REJECTED",
        "MSG_PARTNER_REQUEST_SENT", "MSG_PARTNER_PHONE_REQUEST",
        "MSG_PARTNER_CITY_REQUEST", "MSG_PARTNER_SHOP_REQUEST",
        "PARTNER_GUIDE_TEXT",
    ],
}

# توضیح هر کلید — کجا نمایش داده می‌شود
TEXT_DESCRIPTIONS = {
    # دکمه‌های منو
    "MAIN_BTN_MY_ORDERS":        "دکمه Reply Keyboard | منوی اصلی",
    "MAIN_BTN_WALLET":           "دکمه Reply Keyboard | منوی اصلی",
    "MAIN_BTN_PARTNER_REQUEST":  "دکمه Reply Keyboard | منوی اصلی — برای کاربران عادی",
    "MAIN_BTN_PARTNER_PANEL":    "دکمه Reply Keyboard | منوی اصلی — فقط برای همکاران تأیید‌شده",
    "MAIN_BTN_GUIDE":            "دکمه Reply Keyboard | منوی اصلی",
    "MAIN_BTN_SUPPORT":          "دکمه Reply Keyboard | منوی اصلی",
    "BTN_WALLET_CHARGE":         "دکمه Inline | زیر موجودی کیف‌پول",
    "BTN_WALLET_GATEWAY":        "دکمه Inline | انتخاب روش پرداخت",
    "BTN_WALLET_CARD":           "دکمه Inline | انتخاب روش پرداخت",
    "TXT_BACK_BTN":              "دکمه Inline | بازگشت به دسته قبلی",
    "TXT_BACK_MAIN_BTN":         "دکمه Inline | بازگشت به منوی اصلی",
    "TXT_CANCEL_BTN":            "دکمه Inline | لغو خرید",
    # پیام‌های اصلی
    "MSG_WELCOME":               "پیام | بعد از /start — {name} = نام کاربر",
    "MSG_BTN_DISABLED":          "پیام | وقتی بخشی غیرفعال است",
    "TXT_MAIN_MENU_TITLE":       "عنوان | در برخی پیام‌های منو",
    "TXT_SELECT_CATEGORY":       "پیام | بالای لیست دسته‌بندی‌ها",
    "TXT_SELECT_PRODUCT":        "پیام | بالای لیست محصولات",
    "TXT_NO_PRODUCTS":           "پیام | وقتی دسته محصولی ندارد",
    # کیف پول
    "MSG_WALLET_BALANCE":        "پیام | نمایش موجودی — {balance} = مبلغ",
    "MSG_WALLET_SELECT_METHOD":  "پیام | انتخاب روش شارژ",
    "MSG_WALLET_AMOUNT_REQUEST": "پیام | درخواست مبلغ شارژ — {min_amount} = حداقل",
    "MSG_WALLET_AMOUNT_INVALID": "پیام خطا | مبلغ وارد‌شده عدد نیست",
    "MSG_WALLET_MIN_AMOUNT":     "پیام خطا | مبلغ کمتر از حداقل — {min_amount} = حداقل",
    "MSG_WALLET_TOPUP_SUCCESS":  "پیام موفق | بعد از شارژ — {amount} = مبلغ، {ref_id} = کد پیگیری",
    "WALLET_QUICK_AMOUNTS":      "فیلد تنظیمات | مبالغ سریع کیف‌پول، با کاما جدا کن — مثال: 10000,50000,100000,500000 (خالی=پنهان)",
    # جریان خرید
    "MSG_PURCHASE_REDIRECT":     "پیام | قبل از انتقال به درگاه پرداخت",
    "MSG_PURCHASE_CANCELLED":    "پیام | بعد از لغو خرید",
    "MSG_PURCHASE_SUCCESS":      "پیام موفق | بعد از خرید — {order_id}، {title}، {price}، {feed_data}",
    "MSG_PURCHASE_QUEUED":       "پیام | خرید ثبت شد ولی موجودی ندارد — {order_id}، {title}",
    "MSG_PURCHASE_NO_STOCK":     "پیام | موجودی تمام شد",
    "MSG_INSUFFICIENT_BALANCE":  "پیام خطا | موجودی کافی نیست — {balance}، {price}",
    "MSG_DAILY_LIMIT_REACHED":   "پیام خطا | سقف روزانه — {limit} = سقف",
    "MSG_PAYMENT_ERROR":         "پیام خطا | خطای درگاه پرداخت",
    "MSG_PAYMENT_BTN":           "دکمه Inline | ورود به درگاه پرداخت",
    # سفارش‌ها
    "MSG_NO_ORDERS":             "پیام | وقتی کاربر هنوز خریدی ندارد",
    "MSG_ORDERS_HEADER":         "عنوان | بالای لیست سفارش‌ها",
    # پشتیبانی
    "SUPPORT_TEXT":              "پیام | بعد از فشردن دکمه پشتیبانی",
    "HELP_TEXT":                 "پیام | بعد از فشردن دکمه راهنما — از HTML پشتیبانی می‌کند",
    # همکاران
    "MSG_PARTNER_ALREADY":       "پیام | کاربر قبلاً تأیید شده",
    "MSG_PARTNER_PENDING":       "پیام | درخواست در صف بررسی",
    "MSG_PARTNER_APPROVED":      "پیام | بعد از تأیید همکار",
    "MSG_PARTNER_REJECTED":      "پیام | بعد از رد درخواست",
    "MSG_PARTNER_REQUEST_SENT":  "پیام | بعد از ارسال درخواست",
    "MSG_PARTNER_PHONE_REQUEST": "پیام | درخواست شماره موبایل",
    "MSG_PARTNER_CITY_REQUEST":  "پیام | درخواست شهر",
    "MSG_PARTNER_SHOP_REQUEST":  "پیام | درخواست نام فروشگاه",
    "PARTNER_GUIDE_TEXT":        "متن کامل | راهنمای همکاری در فروش — از HTML پشتیبانی می‌کند",
}
