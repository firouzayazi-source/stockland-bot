from telebot import types
from db import get_root_categories, get_subcategories, get_category_products, is_partner_approved


# ─── منوی اصلی (Reply Keyboard) ─────────────────────────────────────────────

def main_menu(user_id: int = None) -> types.ReplyKeyboardMarkup:
    """منوی اصلی داینامیک — دسته‌های ریشه از DB + دکمه‌های سیستمی"""
    from ui_texts import t, is_main_button_enabled, DEFAULT_UI_TEXTS
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    is_partner = bool(user_id and is_partner_approved(int(user_id)))

    # ردیف ۱+۲: دکمه‌های دسته‌بندی (برای همه یکسان)
    root_cats = get_root_categories(active_only=True)
    if root_cats:
        cat_buttons = []
        for cat in root_cats:
            emoji = (cat["emoji"] or "").strip()
            label = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            cat_buttons.append(types.KeyboardButton(label))
        for i in range(0, len(cat_buttons), 2):
            if i + 1 < len(cat_buttons):
                kb.row(cat_buttons[i], cat_buttons[i + 1])
            else:
                kb.row(cat_buttons[i])

    # ردیف خریدهای من + کیف‌پول (برای همه)
    sys_row1 = []
    if is_main_button_enabled("MAIN_BTN_MY_ORDERS"):
        sys_row1.append(types.KeyboardButton(t("MAIN_BTN_MY_ORDERS", DEFAULT_UI_TEXTS.get("MAIN_BTN_MY_ORDERS", "🧾 خریدهای من"))))
    if is_main_button_enabled("MAIN_BTN_WALLET"):
        sys_row1.append(types.KeyboardButton(t("MAIN_BTN_WALLET", DEFAULT_UI_TEXTS.get("MAIN_BTN_WALLET", "💰 کیف پول"))))
    if sys_row1:
        kb.row(*sys_row1)

    # 🛍 دکمه فروشگاه آنلاین (Mini App) — فقط اگر آدرس تنظیم شده باشد
    try:
        from db import get_cfg
        _wurl = (get_cfg("webapp_url", "") or "").strip()
        if _wurl.startswith("https://"):
            kb.row(types.KeyboardButton(
                t("MAIN_BTN_WEBAPP", DEFAULT_UI_TEXTS.get("MAIN_BTN_WEBAPP", "🛍 فروشگاه آنلاین")),
                web_app=types.WebAppInfo(url=_wurl)))
    except Exception:
        pass

    if is_partner:
        # همکار: پنل همکار (یه ردیف کامل)
        if is_main_button_enabled("MAIN_BTN_PARTNER_PANEL"):
            kb.row(types.KeyboardButton(t("MAIN_BTN_PARTNER_PANEL", DEFAULT_UI_TEXTS.get("MAIN_BTN_PARTNER_PANEL", "🤝 پنل همکار"))))
        # قوانین همکاری — جایگزین راهنما برای همکاران
        kb.row(types.KeyboardButton(t("BTN_PARTNER_GUIDE", DEFAULT_UI_TEXTS.get("BTN_PARTNER_GUIDE", "📖 راهنما و قوانین"))))
    else:
        # کاربر عادی: درخواست همکاری + پشتیبانی (بدون راهنما)
        if is_main_button_enabled("MAIN_BTN_PARTNER_REQUEST"):
            kb.row(types.KeyboardButton(t("MAIN_BTN_PARTNER_REQUEST", DEFAULT_UI_TEXTS.get("MAIN_BTN_PARTNER_REQUEST", "📝 درخواست نمایندگی"))))
        if is_main_button_enabled("MAIN_BTN_SUPPORT"):
            kb.row(types.KeyboardButton(t("MAIN_BTN_SUPPORT", DEFAULT_UI_TEXTS.get("MAIN_BTN_SUPPORT", "👨‍💻 پشتیبانی"))))

    return kb


# ─── نمایش محتوای یک دسته (Inline) ─────────────────────────────────────────

def category_inline_keyboard(cat_id: int, user_id: int = None) -> types.InlineKeyboardMarkup:
    """نمایش زیردسته‌ها یا محصولات یک دسته"""
    from db import get_category, get_subcategories, get_category_products
    kb = types.InlineKeyboardMarkup(row_width=1)

    cat = get_category(cat_id)
    if not cat:
        return kb

    subcats = get_subcategories(cat_id, active_only=True)

    if subcats:
        for sub in subcats:
            emoji = (sub["emoji"] or "").strip()
            label = f"{emoji} {sub['name']}".strip() if emoji else sub["name"]
            kb.add(types.InlineKeyboardButton(label, callback_data=f"cat_{sub['id']}"))
    else:
        products = get_category_products(cat_id, active_only=True)
        if not products:
            kb.add(types.InlineKeyboardButton("محصولی موجود نیست", callback_data="noop"))
        else:
            partner_ok = user_id and is_partner_approved(int(user_id))
            _FA = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
            for p in products:
                pp = p["partner_price"]
                eff = pp if (partner_ok and pp) else p["price"]
                label = f"{p['title']} | {int(eff):,} تومان".translate(_FA)
                kb.add(types.InlineKeyboardButton(label, callback_data=f"cat_{cat_id}_p_{p['id']}"))

    # دکمه بازگشت — فقط برای زیردسته‌ها (دسته‌های ریشه بازگشت ندارند)
    if cat["parent_id"]:
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=f"cat_{cat['parent_id']}"))

    return kb


# ─── کیف پول ────────────────────────────────────────────────────────────────

def wallet_inline_keyboard():
    from ui_texts import t, DEFAULT_UI_TEXTS
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        t("BTN_WALLET_CHARGE", DEFAULT_UI_TEXTS.get("BTN_WALLET_CHARGE", "➕ شارژ حساب")),
        callback_data="wallet_charge"
    ))
    return kb


# ─── منوی ادمین (Inline) ────────────────────────────────────────────────────

def admin_main_inline():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("🧾 مدیریت محصولات", callback_data="admin_products"),
        types.InlineKeyboardButton("📦 مدیریت موجودی", callback_data="admin_feed_panel"),
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
        types.InlineKeyboardButton("🧩 متن دکمه‌ها و پیام‌ها", callback_data="admin_settings"),
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
    kb = types.InlineKeyboardMarkup(row_width=1)
    for k, d in keys:
        label = t(k, d)
        if len(label) > 60:
            label = label[:57] + "..."
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_ui_edit_{k}"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_settings"))
    return kb


# ─── توابع قدیمی (backward compat) ──────────────────────────────────────────

def other_products_menu():
    """backward compat — استفاده از category_inline_keyboard توصیه می‌شه"""
    from db import get_root_categories
    kb = types.InlineKeyboardMarkup(row_width=1)
    cats = get_root_categories(active_only=True)
    for cat in cats:
        emoji = (cat["emoji"] or "").strip()
        label = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
        kb.add(types.InlineKeyboardButton(label, callback_data=f"cat_{cat['id']}"))
    return kb


def admin_other_products_menu():
    """backward compat"""
    from db import get_root_categories
    kb = types.InlineKeyboardMarkup(row_width=1)
    cats = get_root_categories(active_only=False)
    for cat in cats:
        emoji = (cat["emoji"] or "").strip()
        label = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
        kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_cat_{cat['id']}"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_products"))
    return kb
