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
    ],
}
