from db import get_ui_text, set_ui_text


# ========= UI TEXTS (Editable) =========

DEFAULT_UI_TEXTS = {
    # Main menu buttons (ReplyKeyboard)
    "MAIN_BTN_OTHER_PRODUCTS": "سایر محصولات فروشگاه 🛍",
    "MAIN_BTN_BUY_APPLE_ID": "سرویس اپل آیدی 📱",
    "MAIN_BTN_MY_ORDERS": "خرید های من 🧾",
    "MAIN_BTN_WALLET": "کیف پول 💰",
    "MAIN_BTN_PARTNER_REQUEST": "درخواست نمایندگی 📝",
    "MAIN_BTN_PARTNER_PANEL": "پنل همکار 🤝",
    "MAIN_BTN_GUIDE": "راهنما 🔑",
    "MAIN_BTN_SUPPORT": "پشتیبانی 👨‍💻",
    "SUPPORT_TEXT": "برای ارتباط با پشتیبانی، یکی از روش‌های زیر را استفاده کنید:\n1️⃣ ارسال پیام مستقیم به پشتیبان: @YourSupportUsername\n2️⃣ ارسال پیام در همینجا؛ پیام شما برای ادمین فوروارد خواهد شد.",
    "HELP_TEXT": "راهنمای استفاده از ربات:\n\n📱 خرید اپل آیدی: انتخاب سرویس و پرداخت از کیف پول.\n💰 کیف پول: مشاهده موجودی و شارژ.\n🧾 خریدهای من: مشاهده آخرین سفارش‌ها.\n📝 درخواست نمایندگی: ارسال درخواست برای همکاری.\n👨‍💻 پشتیبانی: ارتباط با تیم پشتیبانی.",
    # Captions / fixed texts (extend as needed)
    "TXT_MAIN_MENU_TITLE": "منوی اصلی",
}

_ui_cache: dict[str, str] = {}


def t(key: str, default: str | None = None) -> str:
    """Get UI text by key with DB override + safe fallback."""
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


# ========= MAIN BUTTON ENABLE/DISABLE (Admin Controlled) =========

MAIN_BUTTON_KEYS = [
    "MAIN_BTN_OTHER_PRODUCTS",
    "MAIN_BTN_BUY_APPLE_ID",
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
    # default enabled
    raw = t(_main_btn_flag_key(btn_key), "1")
    s = str(raw).strip().lower()
    return s not in ("0", "false", "off", "no")

def set_main_button_enabled(btn_key: str, enabled: bool) -> None:
    set_ui_text(_main_btn_flag_key(btn_key), "1" if enabled else "0")
    # clear cached values for this flag
    _ui_cache.pop(_main_btn_flag_key(btn_key), None)


def ui_cache_clear() -> None:
    _ui_cache.clear()
