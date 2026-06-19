from telebot import types

from db import list_other_services
from ui_texts import MAIN_BUTTON_KEYS, t, is_main_button_enabled


# ========= KEYBOARDS =========
def main_menu():
    """Main (reply) menu shown to users.

    Buttons are generated from UI texts (t(...)) and filtered by admin toggle
    is_main_button_enabled(...). Disabled buttons are hidden from the menu.
    """
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

    btn_keys = [
        "MAIN_BTN_OTHER_PRODUCTS",
        "MAIN_BTN_BUY_APPLE_ID",
        "MAIN_BTN_MY_ORDERS",
        "MAIN_BTN_WALLET",
        "MAIN_BTN_PARTNER_REQUEST",
        "MAIN_BTN_PARTNER_PANEL",
        "MAIN_BTN_GUIDE",
        "MAIN_BTN_SUPPORT",
    ]

    visible = [k for k in btn_keys if is_main_button_enabled(k)]
    # Safety: always keep at least one button visible
    if not visible:
        visible = ["MAIN_BTN_SUPPORT"]

    for i in range(0, len(visible), 2):
        left = types.KeyboardButton(t(visible[i]))
        if i + 1 < len(visible):
            right = types.KeyboardButton(t(visible[i + 1]))
            kb.row(left, right)
        else:
            kb.row(left)

    return kb

def other_products_menu():
    """زیرمنوی «سایر محصولات»."""
    kb = types.InlineKeyboardMarkup(row_width=2)

    services = list_other_services(active_only=True)
    if not services:
        return kb    
        #kb.add(types.InlineKeyboardButton("فعلاً سرویسی ثبت نشده", callback_data="noop"))
    else:
        for skey, title, emoji, _is_active in services:
            label = (f"{emoji.strip()} {title}".strip() if (emoji and str(emoji).strip()) else str(title).strip())
            kb.add(types.InlineKeyboardButton(label, callback_data=f"other_cat_{skey}"))

    return kb

def admin_other_products_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)

    services = list_other_services(active_only=False)

    normal_services = []
    general_service = None

    for skey, title, emoji, is_active in services:
        if skey == "general":
            general_service = (skey, title, emoji, is_active)
        else:
            normal_services.append((skey, title, emoji, is_active))

    # اول بقیه دسته‌ها
    for skey, title, emoji, is_active in normal_services:
        label = (f"{emoji.strip()} {title}".strip()
                 if (emoji and str(emoji).strip())
                 else str(title).strip())

        kb.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"admin_products_cat_{skey}"
            ),
            types.InlineKeyboardButton(
                "🗑 حذف",
                callback_data=f"admin_other_del_{skey}"
            )
        )

    # بعد general همیشه آخر
    if general_service:
        skey, title, emoji, is_active = general_service
        label = (f"{emoji.strip()} {title}".strip()
                 if (emoji and str(emoji).strip())
                 else str(title).strip())

        status_icon = "✅" if int(is_active) == 1 else "❌"

        kb.add(
            types.InlineKeyboardButton(
                label,
                callback_data=f"admin_products_cat_{skey}"   # ورود به مدیریت محصولات
            ),
            types.InlineKeyboardButton(
                f"{status_icon}",
                callback_data=f"admin_other_toggle_{skey}"  # فقط toggle
            )
        )

    kb.add(
        types.InlineKeyboardButton("➕ افزودن محصول", callback_data="admin_other_add_service")
    )

    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin_products"))

    return kb

def wallet_inline_keyboard():
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("➕ شارژ حساب", callback_data="wallet_charge"))
    return kb


def admin_main_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🧾 مدیریت محصولات", callback_data="admin_products"),
        types.InlineKeyboardButton("📦  مدیریت بارگذاری محصول", callback_data="admin_feed_panel"),
        types.InlineKeyboardButton("💰 مدیریت کیف پول", callback_data="admin_wallet"),
        types.InlineKeyboardButton("📊 آمار کلی", callback_data="admin_stats"),
        types.InlineKeyboardButton("📦 آخرین سفارش‌ها", callback_data="admin_payments"),
        types.InlineKeyboardButton("🤝 درخواست‌های همکار", callback_data="admin_partner_requests"),
        types.InlineKeyboardButton("⚙️ تنظیمات", callback_data="admin_settings"),
    )
    return kb


def admin_settings_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🧩 تنظیم متن دکمه‌های اصلی", callback_data="admin_ui_main_buttons"),
        types.InlineKeyboardButton("📝 تنظیم متن", callback_data="admin_ui_texts"),
        types.InlineKeyboardButton("🚫 مدیریت دکمه‌های اصلی", callback_data="admin_main_btn_manage"),
        types.InlineKeyboardButton("💾 خروجی/بکاپ و بازیابی", callback_data="admin_backup_menu"),
        types.InlineKeyboardButton("⚠️ ریست کامل دیتابیس", callback_data="admin_full_reset_1"),
        types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"),
    )
    return kb

def admin_main_btn_manage_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    for key in MAIN_BUTTON_KEYS:
        enabled = is_main_button_enabled(key)
        label = ("✅ " if enabled else "❌ ") + t(key)
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_main_btn_toggle_{key}"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_settings"))
    return kb



def admin_ui_list_menu(keys: list[tuple[str, str]]):
    """keys: [(key, default_value)]"""
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, d in keys:
        label = t(k, d)
        if len(label) > 60:
            label = label[:57] + "..."
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_ui_edit_{k}"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_settings"))
    return kb
