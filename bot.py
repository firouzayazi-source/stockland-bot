import os
import logging
from datetime import datetime, timedelta
import random
import string
import requests
import logging

logger = logging.getLogger("inox_bot")
import requests
import telebot
from telebot import types
from telebot import apihelper
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

# Telegram networking timeouts (stability)
apihelper.CONNECT_TIMEOUT = 15
apihelper.READ_TIMEOUT = 60
import re
import time
import threading
import html
from db import subtract_wallet_balance
from db import (
    init_db,
    DB_FULL_PATH,
    get_wallet_balance,
    add_wallet_balance,
    subtract_wallet_balance,
    set_wallet_balance,
    create_order,
    get_recent_orders_by_user,
    get_recent_orders_global,
    get_products_by_category,
    get_product_by_id,
    update_product_field,
    toggle_product_active,
    add_product,
    delete_product,
    get_stats,
    claim_next_feed_item,
    add_feed_items,
    get_feed_stats,
    list_feed_items,
    count_feed_items,
    set_feed_item_delivered,
    delete_feed_item,
    get_feed_alert_setting,
    set_feed_alert_threshold,
    reset_feed_alert_notification,
    set_feed_alert_last_notified,
    list_other_services,
    add_other_service,
    delete_other_service,
    upsert_partner_request,
    list_pending_partners,
    list_partner_requests,
    approve_partner,
    reject_partner,
    update_partner_city_shop,
    is_partner_approved,
    get_partner_by_user_id,
    get_partner_by_phone,
    count_user_product_orders_today,
    get_ui_text,
    set_ui_text,
    delete_ui_text,
    list_ui_texts,
    # دسته‌بندی داینامیک
    get_root_categories,
    get_subcategories,
    get_category,
    get_category_products,
    get_category_by_button_text,
    get_category_path,
    # کاربران و تیکت
    upsert_user,
    # کد تخفیف
    validate_discount, use_discount,
    # اشتراک موجودی
    subscribe_stock, get_stock_subscribers, mark_subscriptions_notified,
    reset_subscriptions_on_restock,
    # پشتیبانی محصول
    get_product_support_flag, ensure_product_support_schema, get_product_setup_message,
)
from services.payments import start_wallet_charge_payment
from config import (
    BOT_TOKEN,
    ADMIN_ID,
    BASE_DIR,
    DB_PATH,
    ZARINPAL_SANDBOX,
    BASE_CALLBACK_URL,
    MIN_TOPUP_AMOUNT,
)
from state import (
    STATE,
    user_states,
    reseller_signup,
    admin_states,
    clear_user_state,
    clear_admin_state,
    ensure_admin,
    admin_has_perm,
)
from backup_tools import (
    BACKUP_DIR,
    _ensure_backup_dir,
    create_db_backup,
    validate_backup_db,
    restore_db_from_backup,
    admin_backup_menu,
    admin_full_reset_confirm_menu,
    full_reset_database,
    set_ui_cache_clear_callback,
)
from ui_texts import (
    DEFAULT_UI_TEXTS,
    MAIN_BUTTON_KEYS,
    t,
    tf,
    is_main_button_enabled,
    set_main_button_enabled,
    ui_cache_clear,
)
from keyboards import (
    main_menu,
    other_products_menu,
    admin_other_products_menu,
    wallet_inline_keyboard,
    admin_main_inline,
    admin_settings_menu,
    admin_main_btn_manage_menu,
    admin_ui_list_menu,
    category_inline_keyboard,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("inox_bot")


class _BotExceptionHandler(telebot.ExceptionHandler):
    """گیرنده مرکزی همه خطاهای handler ها — بدون این، باگ‌های آینده بی‌صدا گم می‌شدند.
    خطا را کامل لاگ می‌کند و یک هشدار (rate-limited) به ادمین می‌فرستد."""
    _last_alert_ts = 0.0
    _ALERT_COOLDOWN = 60  # حداکثر یک پیام هشدار در هر ۶۰ ثانیه

    def handle(self, exception):
        import traceback, time as _t
        tb = traceback.format_exc()
        logger.error("Unhandled bot exception: %s\n%s", exception, tb)
        now = _t.time()
        if now - _BotExceptionHandler._last_alert_ts > _BotExceptionHandler._ALERT_COOLDOWN:
            _BotExceptionHandler._last_alert_ts = now
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"⚠️ <b>خطای داخلی ربات</b>\n<code>{str(exception)[:300]}</code>\n\n"
                    f"جزئیات کامل در لاگ سرور (journalctl) موجود است.",
                    parse_mode="HTML",
                )
            except Exception:
                pass
        return True  # جلوگیری از crash مجدد و توقف پردازش این آپدیت


try:
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", exception_handler=_BotExceptionHandler())
except TypeError:
    # نسخه قدیمی‌تر pyTelegramBotAPI که exception_handler را پشتیبانی نمی‌کند
    logger.warning("telebot نسخه فعلی از exception_handler پشتیبانی نمی‌کند — fallback به حالت معمولی")
    bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
set_ui_cache_clear_callback(ui_cache_clear)


# ══════════════════════════════════════════════════════════════════════════════
# ─── اعداد فارسی — تبدیل سراسری همه پیام‌های خروجی ربات ────────────────────
# ══════════════════════════════════════════════════════════════════════════════
import re as _fa_re
_FA_DIGIT_MAP = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")
# لینک‌ها، بلوک‌های code/pre، یوزرنیم‌ها و دستورات دست نمی‌خورند
_FA_SKIP_RE = _fa_re.compile(
    r'(<code>.*?</code>|<pre>.*?</pre>|https?://[^\s<]+|t\.me/[^\s<]+|@\w+|/\w+)',
    _fa_re.S
)

def _fa_digits(text):
    """تبدیل ارقام لاتین به فارسی — به‌جز لینک‌ها و بلوک‌های کد."""
    if not isinstance(text, str) or not text:
        return text
    parts = _FA_SKIP_RE.split(text)
    return "".join(p if i % 2 else p.translate(_FA_DIGIT_MAP)
                   for i, p in enumerate(parts) if p is not None)

# پچ توابع ارسال — یک‌بار، سراسری
_orig_send_message = bot.send_message
def _fa_send_message(chat_id, text, *args, **kwargs):
    return _orig_send_message(chat_id, _fa_digits(text), *args, **kwargs)
bot.send_message = _fa_send_message

_orig_edit_message_text = bot.edit_message_text
def _fa_edit_message_text(text, *args, **kwargs):
    return _orig_edit_message_text(_fa_digits(text), *args, **kwargs)
bot.edit_message_text = _fa_edit_message_text

_orig_reply_to = bot.reply_to
def _fa_reply_to(message, text, *args, **kwargs):
    return _orig_reply_to(message, _fa_digits(text), *args, **kwargs)
bot.reply_to = _fa_reply_to

_orig_send_photo = bot.send_photo
def _fa_send_photo(chat_id, photo, *args, **kwargs):
    if "caption" in kwargs:
        kwargs["caption"] = _fa_digits(kwargs["caption"])
    return _orig_send_photo(chat_id, photo, *args, **kwargs)
bot.send_photo = _fa_send_photo

_orig_answer_cbq = bot.answer_callback_query
def _fa_answer_cbq(callback_query_id, text=None, *args, **kwargs):
    return _orig_answer_cbq(callback_query_id, _fa_digits(text) if text else text, *args, **kwargs)
bot.answer_callback_query = _fa_answer_cbq

_orig_edit_caption = bot.edit_message_caption
def _fa_edit_caption(caption=None, *args, **kwargs):
    return _orig_edit_caption(_fa_digits(caption) if caption else caption, *args, **kwargs)
bot.edit_message_caption = _fa_edit_caption


# ══════════════════════════════════════════════════════════════════════════════
# ─── Rate Limiting ربات ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

import time as _rl_time
_rl_msg_store: dict = {}   # uid → list[float]
_rl_cb_store:  dict = {}   # uid → list[float]
_RL_MSG_MAX   = 10    # حداکثر ۱۰ پیام در ۱۰ ثانیه
_RL_MSG_WIN   = 10.0
_RL_CB_MAX    = 20    # حداکثر ۲۰ callback در ۱۵ ثانیه
_RL_CB_WIN    = 15.0


def _rate_check(store: dict, uid: int, max_count: int, window: float) -> bool:
    """True = مجاز ، False = بلاک. ادمین هرگز بلاک نمی‌شه."""
    try:
        if int(uid) == int(ADMIN_ID):
            return True
    except Exception:
        pass
    now = _rl_time.time()
    ts_list = store.get(uid, [])
    ts_list = [t for t in ts_list if now - t < window]
    store[uid] = ts_list
    if len(ts_list) >= max_count:
        return False
    ts_list.append(now)
    return True


@bot.message_handler(
    func=lambda m: not _rate_check(_rl_msg_store, m.from_user.id, _RL_MSG_MAX, _RL_MSG_WIN),
    content_types=["text", "photo", "document", "voice", "video", "audio", "sticker"]
)
def _rl_msg_blocked(message):
    """کاربر خیلی سریع پیام فرستاده — نادیده گرفته می‌شه (بی‌صدا)."""
    pass


@bot.callback_query_handler(
    func=lambda c: not _rate_check(_rl_cb_store, c.from_user.id, _RL_CB_MAX, _RL_CB_WIN)
)
def _rl_cb_blocked(call):
    """Callback خیلی سریع — فقط acknowledge، بدون پردازش."""
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass


def send_product_detail(chat_id_or_msg, product, category=None, user_id=None, message=None, cat_id=None):
    """نمایش جزئیات محصول.
    
    از هر دو روش قدیمی (category TEXT) و جدید (cat_id INT) پشتیبانی می‌کند.
    """
    # handle both chat_id (int) and message object
    if hasattr(chat_id_or_msg, 'chat'):
        msg_obj = chat_id_or_msg
        chat_id = msg_obj.chat.id
        if user_id is None and hasattr(msg_obj, 'from_user'):
            user_id = msg_obj.from_user.id
    else:
        chat_id = chat_id_or_msg
        msg_obj = message

    # product می‌تونه tuple یا sqlite3.Row باشه
    if hasattr(product, 'keys'):
        pid = product["id"]
        category = category or product.get("category") or str(product.get("category_id", ""))
        title = product["title"]
        price = product["price"]
        description = product.get("description")
        is_active = product.get("is_active", 1)
        partner_price = product.get("partner_price")
        daily_lim_c = product.get("daily_limit_customer") or 0
        daily_lim_p = product.get("daily_limit_partner") or 0
        if cat_id is None:
            cat_id = product.get("category_id")
    else:
        pid, category, title, price, description, is_active = product[0:6]
        partner_price = product[6] if len(product) > 6 else None
        daily_lim_c = product[7] if len(product) > 7 else 0
        daily_lim_p = product[8] if len(product) > 8 else 0

    # تعیین back_cb
    if cat_id:
        back_cb = f"cat_{cat_id}"
    else:
        back_cb = f"back_list_{category}"

    partner_ok = (user_id is not None) and is_partner_approved(int(user_id))
    eff_price = partner_price if (partner_ok and partner_price) else price
    from db import apply_flash_price as _afp
    eff_price, _flash_sale = _afp(int(pid), int(eff_price))

    # بررسی سقف خرید روزانه
    if user_id is not None:
        buyer_type = "partner" if partner_ok else "customer"
        limit_val = int((daily_lim_p if buyer_type == "partner" else daily_lim_c) or 0)
        if limit_val > 0:
            cnt = count_user_product_orders_today(int(user_id), int(pid), buyer_type=buyer_type)
            if cnt >= limit_val:
                kb_limit = types.InlineKeyboardMarkup()
                kb_limit.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb))
                bot.send_message(
                    chat_id,
                    f"نام سرویس: <b>{title}</b>\n\n"
                    f"⛔️ سقف خرید روزانه‌ی این محصول ({limit_val} عدد) برای شما تکمیل شده است.\n"
                    f"لطفاً فردا دوباره اقدام کنید.",
                    reply_markup=kb_limit,
                    parse_mode="HTML",
                )
                return

    wallet_balance = get_wallet_balance(user_id) if user_id else 0

    # امتیاز محصول
    rating_text = ""
    try:
        from db import get_product_rating, ensure_ratings_schema
        ensure_ratings_schema()
        r = get_product_rating(int(pid))
        if r["count"] > 0:
            stars = "⭐️" * round(r["avg"]) + f"  {r['avg']}/5"
            rating_text = f"\n{stars} ({r['count']} نظر)"
    except Exception:
        pass

    # FAQ
    faq_text = ""
    try:
        faq_text = _build_faq_text(int(pid))
    except Exception:
        pass

    # ضمانت
    guarantee = _build_guarantee_text()

    # مورد ۵: نمایش قیمت عادی خط‌خورده برای همکار
    partner_ok_view = (user_id and is_partner_approved(int(user_id)))
    if _flash_sale:
        _price_line = f"قیمت: <s>{int(price):,}</s> ← <b>{eff_price:,}</b> تومان 🔥\n"
    elif partner_ok_view and product[6] and int(product[6]) < int(price):
        saving = int(price) - int(eff_price)
        pct = round(saving * 100 / int(price))
        _price_line = (
            f"قیمت مشتری عادی: <s>{int(price):,}</s>\n"
            f"💚 قیمت همکاری شما: <b>{eff_price:,}</b> تومان\n"
            f"💰 سود شما: <b>{saving:,} تومان ({pct}٪)</b>\n"
        )
    else:
        _price_line = f"قیمت: <b>{eff_price:,}</b> تومان\n"

    text = (
        f"{_flash_badge(pid, _flash_sale, price, eff_price)}"
        f"نام سرویس: <b>{title}</b>{rating_text}\n"
        f"{_price_line}\n"
        f"{description or 'بدون توضیحات'}"
        f"{faq_text}"
        f"{guarantee}"
    )

    # مستقیم به خلاصه سفارش (بدون صفحه واسط)
    _show_order_summary(chat_id, user_id, product, category, pid)




# ================== CLEAN CHAT (DELETE ONLY LAST "DELIVERY" MESSAGE) ==================
# هدف: فقط پیام تحویل محصول (که شامل اطلاعات/فایل محصول است) پاک شود، نه منوها و پیام‌های عادی.
LAST_DELIVERY = {}  # chat_id -> message_id

def try_delete_last_delivery(chat_id: int):
    """Delete the last delivery message we sent to this chat (if any)."""
    mid = LAST_DELIVERY.get(chat_id)
    if not mid:
        return
    try:
        bot.delete_message(chat_id, mid)
    except Exception:
        pass
    LAST_DELIVERY.pop(chat_id, None)

def _remember_delivery(msg):
    try:
        LAST_DELIVERY[msg.chat.id] = msg.message_id
    except Exception:
        pass


# ================== PENDING AUTO-DELIVERY QUEUE (WHEN FEED IS EMPTY) ==================
# هدف: وقتی محصول محصول خالی است، سفارش در صف "pending" ثبت شود و به محض اضافه شدن محصول، خودکار تحویل گردد.

def _db_conn():
    import sqlite3
    return sqlite3.connect(DB_FULL_PATH)

def ensure_pending_schema():
    """Create / migrate pending_deliveries table (best-effort, backward compatible)."""
    try:
        conn = _db_conn()
        try:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pending_deliveries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id INTEGER UNIQUE,
                    user_id INTEGER,
                    chat_id INTEGER,
                    product_id INTEGER,
                    product_title TEXT,
                    price INTEGER,
                    status TEXT DEFAULT 'pending',
                    feed_id INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    delivered_at TEXT
                );
                """
            )
            # Add missing columns if table existed before (SQLite safe migration)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(pending_deliveries);").fetchall()}
            needed = {
                "order_id": "INTEGER UNIQUE",
                "user_id": "INTEGER",
                "chat_id": "INTEGER",
                "product_id": "INTEGER",
                "product_title": "TEXT",
                "price": "INTEGER",
                "status": "TEXT DEFAULT 'pending'",
                "feed_id": "INTEGER",
                "created_at": "TEXT DEFAULT CURRENT_TIMESTAMP",
                "delivered_at": "TEXT",
            }
            for col, decl in needed.items():
                if col not in cols:
                    conn.execute(f"ALTER TABLE pending_deliveries ADD COLUMN {col} {decl};")
            conn.commit()
        finally:
            conn.close()
    except Exception:
        # never block bot start
        pass

def enqueue_pending_delivery(order_id: int, user_id: int, chat_id: int, product_id: int, title: str, price: int):
    try:
        if int(_get_product_chat_enabled(int(product_id))) == 1:
            return False
    except Exception:
        pass
    ensure_pending_schema()
    try:
        conn = _db_conn()
        try:
            conn.execute(
                """
                INSERT OR REPLACE INTO pending_deliveries
                    (order_id, user_id, chat_id, product_id, product_title, price, status, feed_id)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL);
                """,
                (int(order_id), int(user_id), int(chat_id), int(product_id), str(title), int(price)),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

def _mark_pending_delivered(order_id: int, feed_id: int):
    try:
        conn = _db_conn()
        try:
            conn.execute(
                "UPDATE pending_deliveries SET status='delivered', feed_id=?, delivered_at=CURRENT_TIMESTAMP WHERE order_id=?;",
                (int(feed_id), int(order_id)),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        pass

def _send_delivery_to_user(chat_id: int, order_id: int, pid: int, title: str, eff_price: int, feed_id: int, feed_data: str):
    delivery_text = (
        "✅ <b>محصول شما آماده شد</b>\n\n"
        f"Order ID: <b>#{order_id}</b>\n"
        f"محصول: <b>{html.escape(str(title))}</b> (#{pid})\n"
        f"Feed ID: <b>{feed_id}</b>\n\n"
        f"<code>{html.escape(str(feed_data))}</code>"
    )
    try_delete_last_delivery(chat_id)
    _delivery_msg = bot.send_message(chat_id, delivery_text, parse_mode="HTML")
    _remember_delivery(_delivery_msg)

    # ذخیره دائمی پیام تحویل برای امکان «برگشت» از پنل
    try:
        import sqlite3 as _sq3
        from datetime import datetime as _dt2
        _c = _sq3.connect(DB_FULL_PATH)
        try:
            _c.execute(
                "INSERT OR REPLACE INTO delivery_messages (feed_id, order_id, chat_id, message_id, created_at) "
                "VALUES (?,?,?,?,?);",
                (int(feed_id), int(order_id), int(chat_id), int(_delivery_msg.message_id), _dt2.utcnow().isoformat())
            )
            _c.commit()
        finally:
            _c.close()
    except Exception as _ex:
        logger.error("delivery_messages insert failed: %s", _ex)

    # ذخیره feed_id در orders برای برگشت
    try:
        from db import order_set_feed_id
        order_set_feed_id(int(order_id), int(feed_id))
    except Exception:
        pass

def try_dispatch_pending_for_product(product_id: int, limit: int = 50) -> int:
    """
    Try to dispatch pending orders for a product using available feed items.
    Returns number of dispatched orders.
    """
    try:
        if int(_get_product_chat_enabled(int(product_id))) == 1:
            return 0
    except Exception:
        pass
    ensure_pending_schema()
    dispatched = 0
    try:
        conn = _db_conn()
        rows = conn.execute(
            """
            SELECT order_id, user_id, chat_id, product_id, product_title, COALESCE(price,0)
            FROM pending_deliveries
            WHERE product_id=? AND status='pending'
            ORDER BY id ASC
            LIMIT ?;
            """,
            (int(product_id), int(limit)),
        ).fetchall()
        conn.close()
    except Exception:
        rows = []

    for order_id, user_id, chat_id, pid, title, price in rows:
        feed_item = claim_next_feed_item(int(pid))
        if not feed_item:
            break

        try:
            feed_id, feed_data = feed_item
        except Exception:
            try:
                feed_id, feed_data, _ = feed_item
            except Exception:
                feed_id, feed_data = (None, None)

        if feed_id is None:
            break

        try:
            _send_delivery_to_user(int(chat_id), int(order_id), int(pid), str(title), int(price), int(feed_id), str(feed_data))
        except Exception:
            # if delivery fails, revert delivered flag back? keep pending so it can be retried.
            try:
                # mark feed item as undelivered (rollback best-effort)
                set_feed_item_delivered(int(feed_id), 0)
            except Exception:
                pass
            continue

        _mark_pending_delivered(int(order_id), int(feed_id))
        dispatched += 1

        # notify admin
        try:
            bot.send_message(
                ADMIN_ID,
                "📤 <b>تحویل خودکار از صف</b>\n\n"
                f"Order ID: #{int(order_id)}\n"
                f"User ID: <code>{int(user_id)}</code>\n"
                f"محصول: {html.escape(str(title))} (#{int(pid)})\n"
                f"Feed ID: {int(feed_id)}",
                parse_mode="HTML",
            )
        except Exception:
            pass

        # low stock alert check (reuse existing logic)
        try:
            total_f, remaining_f, delivered_f = get_feed_stats(int(pid))
            threshold_f, last_f = get_feed_alert_setting(int(pid))
            if remaining_f <= threshold_f and (last_f is None or int(last_f) != int(remaining_f)):
                bot.send_message(
                    ADMIN_ID,
                    "⚠️ <b>هشدار کمبود موجودی</b>\n\n"
                    f"محصول: {html.escape(str(title))} (#{int(pid)})\n"
                    f"باقی‌مانده: <b>{remaining_f}</b> از <b>{total_f}</b>\n"
                    f"آستانه: <b>{threshold_f}</b>",
                    parse_mode="HTML",
                )
                set_feed_alert_last_notified(int(pid), remaining_f)
        except Exception:
            pass

    return dispatched


# ================== DELIVERY MESSAGE TRACKING (PERSISTENT) ==================
# هدف: وقتی آیتم محصول «تحویل» شد، پیام تحویل همان آیتم در چت مشتری ذخیره شود تا با «برگشت» از پنل ادمین همان پیام پاک شود.
# نکته: Order ID با Feed ID فرق دارد. برای جلوگیری از سردرگمی، ارتباط feed_id <-> order_id را هم ذخیره می‌کنیم.
def _ensure_delivery_table():
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        try:
            _conn.execute(
                """CREATE TABLE IF NOT EXISTS delivery_messages (
                    feed_id INTEGER PRIMARY KEY,
                    order_id INTEGER,
                    chat_id INTEGER NOT NULL,
                    message_id INTEGER NOT NULL,
                    created_at TEXT NOT NULL
                );"""
            )

            # مهاجرت نرم: اگر جدول قبلاً ساخته شده و ستون order_id ندارد، اضافه‌اش کن.
            cols = [r[1] for r in _conn.execute("PRAGMA table_info(delivery_messages);").fetchall()]
            if "order_id" not in cols:
                try:
                    _conn.execute("ALTER TABLE delivery_messages ADD COLUMN order_id INTEGER;")
                except Exception:
                    pass

            _conn.commit()
        finally:
            _conn.close()
    except Exception:
        pass



# ================== PRODUCT CHAT (TICKET) ==================
# قابلیت چت برای هر محصول (اختیاری). اگر برای محصول فعال شود، بعد از خرید/تحویل یک تیکت باز می‌شود
# و تا زمانی که کاربر یا ادمین آن را ببندند، پیام‌های کاربر به ادمین و پاسخ ادمین به کاربر ارسال می‌شود.


# ═══════════════════════════════════════════════════════════════════════════
# TICKET SYSTEM v2 — طراحی از صفر
# ═══════════════════════════════════════════════════════════════════════════

from db import (
    ticket_ensure_schema, ticket_create, ticket_get, ticket_get_open_support,
    ticket_get_open_product, ticket_add_message, ticket_user_sent,
    ticket_admin_replied, ticket_close, ticket_get_messages,
    ticket_count_waiting, ticket_get_all, TICKET_MAX_USER_MSGS,
)

BOT_BASE_URL = os.getenv("BOT_WEBHOOK_URL", "").rstrip("/")
PANEL_URL = "https://panel.stland.ir/admin"


def _get_product_chat_enabled(product_id: int) -> int:
    """چک chat_enabled برای محصول."""
    try:
        import sqlite3 as _sq3
        _c = _sq3.connect(DB_FULL_PATH)
        try:
            row = _c.execute("SELECT chat_enabled FROM products WHERE id=? LIMIT 1;", (int(product_id),)).fetchone()
            return int(row[0] or 0) if row else 0
        finally:
            _c.close()
    except Exception:
        return 0


def _set_product_chat_enabled(product_id: int, enabled: int) -> None:
    try:
        import sqlite3 as _sq3
        _c = _sq3.connect(DB_FULL_PATH)
        try:
            _c.execute("UPDATE products SET chat_enabled=? WHERE id=?;", (int(enabled), int(product_id)))
            _c.commit()
        finally:
            _c.close()
    except Exception:
        pass


def _tg_send_to_user(user_id: int, text: str, reply_markup=None, parse_mode="HTML") -> bool:
    """ارسال پیام به کاربر از طریق ربات."""
    try:
        bot.send_message(int(user_id), text, reply_markup=reply_markup, parse_mode=parse_mode)
        return True
    except Exception as ex:
        logger.error("_tg_send_to_user(%s) failed: %s", user_id, ex)
        return False


# ─── Keyboards ──────────────────────────────────────────────────────────────

def _ticket_user_kb(ticket_id: int, has_messages: bool = False) -> types.InlineKeyboardMarkup:
    """هیچ دکمه‌ای نمایش داده نمی‌شه — جریان از طریق پیام‌های متنی مدیریت می‌شه."""
    return types.InlineKeyboardMarkup()


def _is_real_message(msg_text: str, content_type: str) -> bool:
    """آیا این پیام واقعی و معتبر است؟"""
    # رسانه‌ها بدون متن هم معتبرن
    if content_type in ("photo", "document", "voice", "video", "audio"):
        return True
    if content_type != "text":
        return False  # استیکر، animation و... قبول نیست
    if not msg_text or not msg_text.strip():
        return False
    text = msg_text.strip()
    if len(text) <= 2:
        return False
    import unicodedata
    non_emoji = [c for c in text if unicodedata.category(c) not in ('So','Sk','Sm','Sc')]
    if len("".join(non_emoji).strip()) <= 1:
        return False
    return True


def _ticket_has_user_message(ticket_id: int) -> bool:
    try:
        from db import _get_connection
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ticket_messages WHERE ticket_id=? AND sender='user';",
            (ticket_id,)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count > 0
    except Exception:
        return False


def _ticket_real_msg_count(ticket_id: int) -> int:
    """تعداد پیام‌های واقعی کاربر در تیکت."""
    try:
        from db import _get_connection
        conn = _get_connection()
        cur = conn.cursor()
        cur.execute(
            "SELECT COUNT(*) FROM ticket_messages WHERE ticket_id=? AND sender='user';",
            (ticket_id,)
        )
        count = cur.fetchone()[0]
        conn.close()
        return count
    except Exception:
        return 0


TICKET_MAX_USER_MSGS = 3


def _ticket_admin_kb(ticket_id: int, user_id: int) -> types.InlineKeyboardMarkup:
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ پاسخ از تلگرام", callback_data=f"ticket_v2_reply_{ticket_id}_{user_id}"),
        types.InlineKeyboardButton("🔒 بستن تیکت", callback_data=f"ticket_v2_admin_close_{ticket_id}"),
    )
    kb.add(types.InlineKeyboardButton("🌐 پاسخ از پنل", url=f"{PANEL_URL}/tickets/{ticket_id}"))
    return kb


# ─── Support Ticket Flow (کاربر) ─────────────────────────────────────────────

def _support_ticket_start(chat_id: int, user_id: int) -> None:
    """ایجاد یا ادامه تیکت پشتیبانی — کاربر مستقیم وارد گفتگو می‌شه."""
    ticket_ensure_schema()
    existing = ticket_get_open_support(user_id)
    if existing:
        ticket_id = existing["id"]
        user_states[user_id] = {"mode": "ticket_v2", "ticket_id": ticket_id}
        has_msg = _ticket_has_user_message(ticket_id)
        kb = _ticket_user_kb(ticket_id, has_messages=has_msg)
        bot.send_message(
            chat_id,
            f"💬 ادامه مکالمه تیکت <b>#{ticket_id}</b>\n\n"
            "پیام خود را ارسال کنید، پشتیبانی در اولین فرصت پاسخ خواهد داد.",
            reply_markup=kb, parse_mode="HTML"
        )
    else:
        ticket_id = ticket_create(user_id, type_="support")
        user_states[user_id] = {"mode": "ticket_v2", "ticket_id": ticket_id}
        # ابتدا بدون دکمه پایان — فقط راهنما
        kb = _ticket_user_kb(ticket_id, has_messages=False)
        bot.send_message(
            chat_id,
            "💬 <b>پشتیبانی آنلاین</b>\n\n"
            "پیام خود را ارسال کنید، پشتیبانی در اولین فرصت پاسخ خواهد داد.\n\n"
            "⚠️ لطفاً مشکل خود را در یک پیام کامل توضیح دهید.",
            reply_markup=kb, parse_mode="HTML"
        )


def _is_menu_or_system_button(text: str) -> bool:
    """آیا این پیام یک دکمه/دستور است که باید از چت خارج کند؟"""
    if not text:
        return False
    text = text.strip()

    # ۱. هر دستوری که با / شروع شود (/start, /help, ...)
    if text.startswith("/"):
        return True

    # ۲. دکمه‌های سیستمی منوی اصلی
    try:
        system_keys = (
            "MAIN_BTN_MY_ORDERS", "MAIN_BTN_WALLET", "MAIN_BTN_PARTNER_REQUEST",
            "MAIN_BTN_PARTNER_PANEL", "BTN_PARTNER_GUIDE", "MAIN_BTN_SUPPORT", "MAIN_BTN_INVITE",
            "MAIN_BTN_OTHER_PRODUCTS", "MAIN_BTN_BUY_APPLE_ID",
        )
        for key in system_keys:
            val = t(key, DEFAULT_UI_TEXTS.get(key, ""))
            if val and text == val:
                return True
    except Exception:
        pass

    # ۳. دکمه‌های دسته‌بندی (داینامیک)
    try:
        from db import get_root_categories
        for cat in get_root_categories(active_only=True):
            emoji = (cat["emoji"] or "").strip()
            label = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
            if text == label:
                return True
    except Exception:
        pass

    # ۴. دکمه‌های ثابت شناخته‌شده
    known_buttons = (
        "🔙 بازگشت", "🔙 بازگشت به منو", "❌ انصراف", "🏠 منوی اصلی",
        "بازگشت", "انصراف", "منوی اصلی", "🛒 خرید", "📜 قوانین",
    )
    if text in known_buttons:
        return True

    return False


def _exit_chat_if_needed(message) -> bool:
    """
    استاندارد سراسری: اگر کاربر وسط چت/تیکت کاری غیر از پیام‌دادن کرد،
    خودکار از حالت چت خارج شود و پیام در تیکت ثبت نشود.
    خروجی: True اگر از چت خارج شد (یعنی نباید ادامه داد).
    """
    uid = message.from_user.id
    st  = user_states.get(uid, {})
    if st.get("mode") != "ticket_v2":
        return False  # اصلاً در حالت چت نیست

    txt = message.text or ""

    # حالت ۱: دکمه منو یا دستور → خروج + انتقال به handler مربوطه
    if message.content_type == "text" and _is_menu_or_system_button(txt):
        clear_user_state(uid)
        try:
            bot.process_new_messages([message])
        except Exception:
            pass
        return True

    return False


def _ticket_v2_handle_user_message(message) -> None:
    """handler اصلی پیام کاربر به تیکت."""
    uid = message.from_user.id

    # ── استاندارد سراسری: اگر کاری غیر چت کرد، خودکار خارج شو ──────────────
    if _exit_chat_if_needed(message):
        return  # از چت خارج شد، پیام در تیکت ثبت نشد

    st = user_states.get(uid, {})
    ticket_id = st.get("ticket_id")

    if not ticket_id:
        clear_user_state(uid)
        bot.send_message(message.chat.id, "مکالمه بسته شده است.", reply_markup=main_menu(user_id=uid))
        return

    ticket = ticket_get(int(ticket_id))
    if not ticket or ticket["status"] == "closed":
        clear_user_state(uid)
        bot.send_message(message.chat.id, "این مکالمه بسته شده است.", reply_markup=main_menu(user_id=uid))
        return

    # ─── Anti-spam: سقف ۳ پیام واقعی متوالی ────────────────────────────────
    cur_count = int(ticket["user_msg_count"] or 0)
    if cur_count >= TICKET_MAX_USER_MSGS:
        bot.reply_to(message,
            f"⏳ لطفاً منتظر پاسخ پشتیبانی بمانید.\n"
            "پس از پاسخ، می‌توانید ادامه دهید.")
        return

    # ─── بررسی واقعی بودن پیام ───────────────────────────────────────────
    # متن یا caption (برای عکس/ویدیو)
    txt = (message.text or message.caption or "").strip()
    if not _is_real_message(txt, message.content_type):
        bot.reply_to(message,
            "لطفاً پیام متنی یا عکس/فایل معتبر ارسال کنید.\n"
            "(استیکر و ایموجی تنها قبول نمی‌شود)")
        return

    media = message.content_type if message.content_type != "text" else None
    file_id = None
    if media:
        try:
            if message.content_type == "photo":
                file_id = message.photo[-1].file_id
            elif message.content_type == "document":
                file_id = message.document.file_id
            elif message.content_type == "video":
                file_id = message.video.file_id
            elif message.content_type == "audio":
                file_id = message.audio.file_id
            elif message.content_type == "voice":
                file_id = message.voice.file_id
        except Exception:
            pass

    ticket_add_message(
        int(ticket_id), "user",
        txt or f"[{message.content_type}]",
        media_type=media,
        media_file_id=file_id
    )
    new_count = ticket_user_sent(int(ticket_id))

    # بعد از اولین پیام — تأیید
    if new_count == 1:
        bot.send_message(message.chat.id,
            "✅ پیام شما دریافت شد.\n"
            "پشتیبانی در اولین فرصت پاسخ خواهد داد. 🙏\n\n"
            f"({TICKET_MAX_USER_MSGS - new_count} پیام دیگر می‌توانید ارسال کنید)"
        )

    elif new_count >= TICKET_MAX_USER_MSGS:
        # بستن سهمیه — تا پاسخ ادمین
        user_states.pop(uid, None)
        bot.send_message(message.chat.id,
            "✅ پیام شما ثبت شد.\n\n"
            "🔒 <b>گفتگو در انتظار پاسخ پشتیبانی است.</b>\n"
            "پس از پاسخ پشتیبانی، می‌توانید ادامه دهید.",
            parse_mode="HTML"
        )
    else:
        bot.send_message(message.chat.id,
            f"✅ پیام دریافت شد. ({TICKET_MAX_USER_MSGS - new_count} پیام دیگر)"
        )

    # ─── نوتیف به ادمین — فقط اولین پیام از هر batch ─────────────────────
    if new_count == 1:
        # تشخیص نوع تیکت برای نمایش بهتر به ادمین
        try:
            _tk = ticket_get(int(ticket_id))
            _ttype = (_tk["type"] if _tk and "type" in _tk.keys() else "support") or "support"
        except Exception:
            _ttype = "support"
        type_label = {
            "support": "🔵 پشتیبانی",
            "product_setup": "🟢 راه‌اندازی محصول",
            "partner_support": "🤝 همکاران",
        }.get(_ttype, "🔵 پشتیبانی")

        panel_url = f"https://panel.stland.ir/admin/tickets/{ticket_id}"
        notif_kb = types.InlineKeyboardMarkup()
        notif_kb.add(types.InlineKeyboardButton("🌐 مشاهده در پنل", url=panel_url))
        try:
            bot.send_message(ADMIN_ID,
                f"🔔 پیام جدید — {type_label}\n"
                f"تیکت <b>#{ticket_id}</b> | کاربر: <code>{uid}</code>",
                reply_markup=notif_kb, parse_mode="HTML")
        except Exception as ex:
            logger.error("Admin notification failed: %s", ex)


# ─── Handler پیام‌های متنی کاربر در حالت تیکت ────────────────────────────────

@bot.message_handler(
    func=lambda m: (
        not ensure_admin(m.from_user.id) or
        user_states.get(m.from_user.id, {}).get("mode") == "ticket_v2"
    ) and user_states.get(m.from_user.id, {}).get("mode") == "ticket_v2"
)
def _handle_ticket_v2_text(message):
    _ticket_v2_handle_user_message(message)


@bot.message_handler(
    func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "ticket_v2",
    content_types=["photo", "document", "video", "audio", "voice", "sticker"]
)
def _handle_ticket_v2_media(message):
    _ticket_v2_handle_user_message(message)


# ─── /start و /admin ──────────────────────────────────────────────────────

@bot.message_handler(commands=["admin", "panel"])
def handle_admin_command(message):
    uid = message.from_user.id
    if not ensure_admin(uid):
        return
    panel_url = "https://panel.stland.ir/admin/"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🌐 ورود به پنل مدیریت", url=panel_url),
        types.InlineKeyboardButton("🎫 تیکت‌ها", url=panel_url + "tickets"),
        types.InlineKeyboardButton("📦 محصولات", url=panel_url + "products"),
        types.InlineKeyboardButton("🗃 موجودی", url=panel_url + "feed"),
        types.InlineKeyboardButton("🧾 سفارش‌ها", url=panel_url + "orders"),
    )
    bot.send_message(uid, "🛍 پنل مدیریت استوک لند:", reply_markup=kb)


MAINTENANCE_MSG = (
    "🚧 ربات در حال بروزرسانی است.\n"
    "به‌زودی با امکانات جدید بازخواهیم گشت.\n"
    "از شکیبایی شما سپاسگزاریم. ❤️"
)

# ─── Rate Limiter ─────────────────────────────────────────────────────────────
# جلوگیری از flood: حداکثر 15 پیام در 10 ثانیه برای هر کاربر
import collections as _collections, time as _time

_rate_limits: dict = {}  # {user_id: deque of timestamps}
_RATE_MAX_MSGS = 15
_RATE_WINDOW   = 10.0   # ثانیه
_rate_last_cleanup = _time.monotonic()

def _is_rate_limited(uid: int) -> bool:
    """True اگه کاربر بیش از حد مجاز پیام بفرسته."""
    global _rate_last_cleanup
    if uid == ADMIN_ID:
        return False
    now = _time.monotonic()
    # هر ۵ دقیقه یه‌بار کاربرهای قدیمی رو پاک کن
    if now - _rate_last_cleanup > 300:
        dead = [k for k, dq in _rate_limits.items()
                if not dq or dq[-1] < now - _RATE_WINDOW * 3]
        for k in dead:
            del _rate_limits[k]
        _rate_last_cleanup = now
    dq = _rate_limits.setdefault(uid, _collections.deque())
    while dq and dq[0] < now - _RATE_WINDOW:
        dq.popleft()
    if len(dq) >= _RATE_MAX_MSGS:
        return True
    dq.append(now)
    return False

@bot.message_handler(func=lambda m: _is_rate_limited(m.from_user.id),
                     content_types=["text","photo","document","voice","video","sticker"])
def rate_limit_blocker(message):
    pass  # بدون پاسخ — جلوگیری از amplification attack

@bot.callback_query_handler(func=lambda c: _is_rate_limited(c.from_user.id))
def rate_limit_blocker_cb(call):
    try:
        bot.answer_callback_query(call.id)  # فقط dismiss می‌کنه، پیامی نمی‌ده
    except Exception:
        pass
# ─────────────────────────────────────────────────────────────────────────────

@bot.message_handler(func=lambda m: _check_maintenance(m), content_types=["text","photo","document","voice","video"])
def maintenance_blocker(message):
    bot.send_message(message.chat.id, MAINTENANCE_MSG)

@bot.callback_query_handler(func=lambda c: _check_maintenance_cb(c))
def maintenance_blocker_cb(call):
    bot.answer_callback_query(call.id, "🚧 ربات در حال بروزرسانی است.", show_alert=True)

def _check_maintenance(message) -> bool:
    try:
        if message.from_user.id == ADMIN_ID:
            return False
        from db import get_maintenance_mode
        return get_maintenance_mode()
    except Exception:
        return False

def _check_maintenance_cb(call) -> bool:
    try:
        if call.from_user.id == ADMIN_ID:
            return False
        from db import get_maintenance_mode
        return get_maintenance_mode()
    except Exception:
        return False


@bot.message_handler(commands=["start"])
def handle_start(message):
    init_db(DB_PATH)
    ticket_ensure_schema()

    uid       = message.from_user.id
    username  = message.from_user.username
    full_name = ((message.from_user.first_name or "") + " " + (message.from_user.last_name or "")).strip()

    try:
        upsert_user(uid, username, full_name)
    except Exception:
        pass

    # بررسی لینک معرفی: /start ref_12345 یا /start STLAND-4521
    args = message.text.split() if message.text else []
    if len(args) > 1:
        arg = args[1]
        if arg.startswith("ref_"):
            # سیستم معرفی کاربران عادی
            try:
                referrer_id = int(arg[4:])
                if referrer_id != uid:
                    from db import register_referral, get_referral_settings, ensure_referral_schema
                    ensure_referral_schema()
                    settings = get_referral_settings()
                    if settings.get("is_active"):
                        from db import check_invite_cap, increment_invite_count
                        _cap = check_invite_cap(referrer_id)
                        if not _cap["ok"]:
                            # سقف پر است
                            try:
                                _cap_msg = (
                                    "\u2705 \u06cc\u06a9 \u062f\u0648\u0633\u062a "
                                    "\u062c\u062f\u06cc\u062f \u0628\u0627 \u0644\u06cc\u0646\u06a9 "
                                    "\u0634\u0645\u0627 \u0639\u0636\u0648 \u0634\u062f!\n\n"
                                    "\u26a0\ufe0f \u0634\u0645\u0627 \u0628\u0647 \u0633\u0642\u0641 "
                                    "\u062f\u0631\u06cc\u0627\u0641\u062a \u067e\u0627\u062f\u0627\u0634 "
                                    "\u062f\u0639\u0648\u062a \u0631\u0633\u06cc\u062f\u0647\u200c\u0627\u06cc\u062f.\n"
                                    "\u0628\u0631\u0627\u06cc \u0641\u0639\u0627\u0644\u200c\u0633\u0627\u0632\u06cc "
                                    "\u0645\u062c\u062f\u062f\u060c \u062d\u062f\u0627\u0642\u0644 "
                                    "\u06cc\u06a9 \u062e\u0631\u06cc\u062f \u0645\u0648\u0641\u0642 "
                                    "\u0627\u0646\u062c\u0627\u0645 \u062f\u0647\u06cc\u062f."
                                )
                                bot.send_message(referrer_id, _cap_msg)
                            except Exception:
                                pass
                            return  # ثبت نمی‌شود
                        is_new = register_referral(referrer_id, uid)
                        if is_new:
                            increment_invite_count(referrer_id)
                        # 🔎 لاگ تشخیصی — برای ردیابی معرفی‌های ثبت‌نشده
                        try:
                            if is_new:
                                logger.info("REFERRAL ✅ ثبت شد: %s → %s", referrer_id, uid)
                            else:
                                from db import _get_connection as _gc
                                _c = _gc()
                                _ex = _c.execute("SELECT referrer_id FROM referrals WHERE referred_id=?;", (uid,)).fetchone()
                                _c.close()
                                logger.warning("REFERRAL ⛔ ثبت نشد: %s → %s | معرف قبلی: %s",
                                               referrer_id, uid, (_ex[0] if _ex else "—"))
                        except Exception:
                            pass
                    else:
                        logger.warning("REFERRAL ⛔ سیستم معرفی غیرفعال است — %s → %s", referrer_id, uid)
                    if settings.get("is_active"):
                        # پاداش عضویت + اطلاع‌رسانی به معرف — فقط برای عضویت جدید
                        if is_new:
                            try:
                                from db import pay_signup_referral_reward
                                pr = pay_signup_referral_reward(referrer_id, uid)
                                new_name = (full_name or username or "کاربر جدید").strip()
                                msg = (
                                    "🎉 <b>خبر خوب!</b>\n\n"
                                    f"«{new_name}» با لینک دعوت شما به ربات پیوست."
                                )
                                if pr.get("paid"):
                                    wallet_lbl = "کیف‌پول همکاری" if pr.get("wallet") == "partner" else "کیف‌پول"
                                    msg += f"\n\n💰 پاداش عضویت: <b>{pr['amount']:,}</b> تومان به {wallet_lbl} شما اضافه شد!"
                                msg += (
                                    "\n\n💸 از این پس با هر خرید ایشان، پورسانت هم دریافت می‌کنید.\n"
                                    "هرچه تیم فروش شما بزرگ‌تر شود، درآمد شما بیشتر می‌شود 💪"
                                )
                                bot.send_message(referrer_id, msg, parse_mode="HTML")
                            except Exception:
                                pass
            except Exception:
                pass


    text = tf("MSG_WELCOME", name=full_name or "دوست عزیز")
    bot.send_message(message.chat.id, text, reply_markup=main_menu(user_id=uid), parse_mode="HTML")



@bot.message_handler(commands=["referral", "invite"])
def handle_referral_cmd(message):
    """دستور /invite — همان نمای یکپارچه دعوت دوستان."""
    return _send_invite_view(message.chat.id, message.from_user.id)





def _display_order_no(order_id) -> int | None:
    """شماره نمایشی سفارش — فعلاً همان ID."""
    try:
        return int(order_id)
    except Exception:
        return None





def format_price(amount):
    try:
        amount = int(amount)
    except Exception:
        return str(amount)
    return f"{amount:,} تومان"


def admin_partner_requests_menu():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📥 در انتظار", callback_data="admin_partner_list_pending"),
        types.InlineKeyboardButton("✅ تایید شده", callback_data="admin_partner_list_approved"),
        types.InlineKeyboardButton("❌ رد شده", callback_data="admin_partner_list_rejected"),
        types.InlineKeyboardButton("🔍 جستجو", callback_data="admin_partner_search"),
        types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"),
    )
    return kb


def send_partner_list(chat_id: int, status: str | None = None, query: str | None = None):
    rows = list_partner_requests(status=status, query=query, limit=50, offset=0)

    def h(x):
        return html.escape(str(x)) if x is not None else "-"

    title_parts = []
    if status:
        title_parts.append({"pending": "در انتظار", "approved": "تایید شده", "rejected": "رد شده"}.get(status, status))
    else:
        title_parts.append("همه")
    if query:
        title_parts.append(f"جستجو: {h(query)}")

    bot.send_message(
        chat_id,
        f"🤝 لیست درخواست‌های همکار ({' | '.join(title_parts)})\nنتیجه: {len(rows)}",
        reply_markup=admin_partner_requests_menu(),
    )
    if not rows:
        return

    for _id, tg_uid, phone, username, full_name, city, shop_name, st, created_at, approved_at in rows:
        lines = [
            "📌 درخواست نمایندگی",
            f"User ID: {h(tg_uid)}",
            f"Username: @{h(username) if username else '-'}",
            f"Name: {h(full_name)}",
            f"Phone: {h(phone)}",
            f"City: {h(city)}",
            f"Shop: {h(shop_name)}",
            f"Status: {h(st)}",
            f"Created: {h(created_at)}",
        ]
        if approved_at:
            lines.append(f"Approved: {h(approved_at)}")
        txt = "\n".join(lines)

        kb = types.InlineKeyboardMarkup(row_width=3)
        kb.add(types.InlineKeyboardButton("✏️ ویرایش", callback_data=f"admin_partner_edit_{tg_uid}"))
        if st == "pending":
            kb.add(
                types.InlineKeyboardButton("✅ تایید", callback_data=f"admin_partner_approve_{tg_uid}"),
                types.InlineKeyboardButton("❌ رد", callback_data=f"admin_partner_reject_{tg_uid}"),
            )
        bot.send_message(chat_id, txt, reply_markup=kb)


def safe_int(text):
    try:
        return int(str(text).strip())
    except Exception:
        return None


def parse_feed_bulk_items(raw: str) -> list[str]:
    """Parse admin bulk feed input."""
    raw = raw or ""
    lines = raw.splitlines()
    delim_re = re.compile(r"^\s*\*{3,}\s*$")

    if any(delim_re.match(ln) for ln in lines):
        blocks: list[list[str]] = []
        cur: list[str] = []
        for ln in lines:
            if delim_re.match(ln):
                blk = "\n".join(cur).strip()
                if blk:
                    blocks.append([blk])
                cur = []
            else:
                cur.append(ln.rstrip("\n"))
        blk = "\n".join(cur).strip()
        if blk:
            blocks.append([blk])
        return [b[0] for b in blocks]

    return [ln.strip() for ln in lines if ln.strip()]


# ========= WALLET / ZARINPAL =========


def can_submit_partner_request(tg_user_id: int, phone: str | None = None):
    """سیاست درخواست نمایندگی (One-time only)"""
    if phone:
        try:
            row_p = get_partner_by_phone(phone)
        except Exception as e:
            logging.exception("get_partner_by_phone failed: %s", e)
            row_p = None
        if row_p:
            status = (row_p[3] or "").strip().lower()
            if status == "approved":
                return False, "این شماره قبلاً به عنوان همکار تایید شده است و امکان ارسال درخواست جدید ندارد."
            if status == "pending":
                return False, "برای این شماره قبلاً درخواست ثبت شده و در انتظار بررسی ادمین است."
            if status == "rejected":
                return False, "برای این شماره قبلاً درخواست رد شده است. برای بررسی مجدد با پشتیبانی تماس بگیرید."
            return False, "برای این شماره قبلاً درخواست ثبت شده است."

    try:
        row_u = get_partner_by_user_id(tg_user_id)
    except Exception as e:
        logging.exception("get_partner_by_user_id failed: %s", e)
        row_u = None

    if row_u:
        status = (row_u[3] or "").strip().lower()
        if status == "approved":
            return False, "شما قبلاً به عنوان همکار تایید شده‌اید و امکان ارسال درخواست جدید ندارید."
        if status == "pending":
            return False, "درخواست نمایندگی شما قبلاً ثبت شده و در انتظار بررسی ادمین است."
        if status == "rejected":
            return False, "درخواست شما قبلاً رد شده است. برای بررسی مجدد با پشتیبانی تماس بگیرید."
        return False, "شما قبلاً درخواست نمایندگی ثبت کرده‌اید."

    return True, None

   #============== رفع محدودیت نام وارد کردن محصول =========

def _make_service_key(title: str) -> str:
    """
    تولید کلید سرویس بدون محدودیت خاص.
    فقط فاصله حذف می‌شود و طول محدود می‌شود.
    """
    t = (title or "").strip()

    if not t:
        return "svc_" + "".join(random.choice(string.digits) for _ in range(6))

    # تبدیل فاصله به _
    safe = t.replace(" ", "_")

    return safe[:32]


def start_wallet_charge(message):
    uid = message.from_user.id

    # مبالغ سریع از تنظیمات
    quick_amounts = _get_quick_amounts()

    if quick_amounts:
        kb = types.InlineKeyboardMarkup(row_width=2)
        btns = [types.InlineKeyboardButton(
            f"💵 {a:,} تومان", callback_data=f"quick_charge_{a}"
        ) for a in quick_amounts]
        kb.add(*btns)
        kb.add(types.InlineKeyboardButton("✏️ مبلغ دلخواه", callback_data="wallet_charge_custom"))
        bot.send_message(
            message.chat.id,
            tf("MSG_WALLET_AMOUNT_REQUEST", min_amount=f"{MIN_TOPUP_AMOUNT:,}"),
            reply_markup=kb,
            parse_mode="HTML"
        )
    else:
        bot.send_message(
            message.chat.id,
            tf("MSG_WALLET_AMOUNT_REQUEST", min_amount=f"{MIN_TOPUP_AMOUNT:,}"),
            parse_mode="HTML"
        )
        user_states[uid] = {"mode": "wallet_charge_amount"}
        bot.register_next_step_handler(message, process_wallet_charge_amount)


def _get_quick_amounts() -> list[int]:
    """خواندن مبالغ سریع از تنظیمات DB"""
    try:
        from db import get_ui_text
        raw = get_ui_text("WALLET_QUICK_AMOUNTS")
        if not raw:
            return [10_000, 50_000, 100_000, 500_000]
        parts = [p.strip() for p in raw.split(",")]
        amounts = [int(p) for p in parts if p.isdigit() and int(p) > 0]
        return amounts
    except Exception:
        return [10_000, 50_000, 100_000, 500_000]


def process_wallet_charge_amount(message):
    uid = message.from_user.id
    text = (message.text or "").strip()

    # اگه کاربر دکمه منو یا /cancel زد، state رو پاک کن
    if text.startswith("/") or get_category_by_button_text(text):
        clear_user_state(uid)
        bot.send_message(message.chat.id, "عملیات شارژ لغو شد.", reply_markup=main_menu(user_id=uid))
        # اگه دسته بود، نمایشش بده
        cat = get_category_by_button_text(text)
        if cat:
            _show_category(message.chat.id, cat["id"], user_id=uid)
        return

    # چک کن متن دکمه‌های سیستمی (کیف‌پول، سفارش و ...) بود
    system_buttons = [
        t("MAIN_BTN_MY_ORDERS",      DEFAULT_UI_TEXTS.get("MAIN_BTN_MY_ORDERS", "")),
        t("MAIN_BTN_WALLET",         DEFAULT_UI_TEXTS.get("MAIN_BTN_WALLET", "")),
        t("BTN_PARTNER_GUIDE",       DEFAULT_UI_TEXTS.get("BTN_PARTNER_GUIDE", "")),
        t("MAIN_BTN_SUPPORT",        DEFAULT_UI_TEXTS.get("MAIN_BTN_SUPPORT", "")),
        t("MAIN_BTN_PARTNER_REQUEST",DEFAULT_UI_TEXTS.get("MAIN_BTN_PARTNER_REQUEST", "")),
        t("MAIN_BTN_PARTNER_PANEL",  DEFAULT_UI_TEXTS.get("MAIN_BTN_PARTNER_PANEL", "")),
        t("MAIN_BTN_INVITE",         DEFAULT_UI_TEXTS.get("MAIN_BTN_INVITE", "")),
    ]
    if text in system_buttons:
        clear_user_state(uid)
        bot.send_message(message.chat.id, "عملیات شارژ لغو شد.", reply_markup=main_menu(user_id=uid))
        return

    text_clean = text.replace(",", "").replace("،", "")
    amount = safe_int(text_clean)

    if amount is None:
        bot.reply_to(message, tf("MSG_WALLET_AMOUNT_INVALID"))
        bot.register_next_step_handler(message, process_wallet_charge_amount)
        return

    if amount < MIN_TOPUP_AMOUNT:
        bot.reply_to(message, tf("MSG_WALLET_MIN_AMOUNT", min_amount=f"{MIN_TOPUP_AMOUNT:,}"))
        bot.register_next_step_handler(message, process_wallet_charge_amount)
        return

    clear_user_state(uid)
    start_wallet_charge_payment(bot, message, uid, amount, clear_user_state)

def start_product_payment(
    bot,
    message,
    uid,
    amount,
    reserved_wallet_amount=0,
    product_id=None
):
    from services.payments import start_wallet_charge_payment

    # اجبار نوع پرداخت به product
    start_wallet_charge_payment(
        bot=bot,
        message=message,
        uid=uid,
        amount=amount,
        clear_user_state=clear_user_state,
        payment_type="product",
        product_id=product_id,
        wallet_reserved=reserved_wallet_amount
    )

  
# ========= PRODUCTS UI =========


import sqlite3
from datetime import datetime
import html


_BOT_USERNAME_CACHE = {"v": ""}

def _bot_username() -> str:
    """یوزرنیم ربات — فقط یک‌بار از API گرفته می‌شود (حذف تأخیر شبکه از هر بازدید)."""
    if not _BOT_USERNAME_CACHE["v"]:
        try:
            _BOT_USERNAME_CACHE["v"] = bot.get_me().username or ""
        except Exception:
            return ""
    return _BOT_USERNAME_CACHE["v"]

def _flash_badge(pid, sale, base_price, eff_price) -> str:
    """بنر برجسته فروش فوری: تخفیف + شمارش معکوس + موجودی محدود."""
    if not sale:
        return ""
    try:
        from db import get_feed_stats
        _tot, _rem, _dlv = get_feed_stats(int(pid))
        stock = int(_rem or 0)
    except Exception:
        stock = None
    saving = max(0, int(base_price) - int(eff_price))
    lines = [
        "🔥⚡️ <b>فــروش فــوری</b> ⚡️🔥",
        f"🏷 <b>{sale['percent']}٪ تخفیف</b> — سود شما: <b>{saving:,}</b> تومان",
        f"⏰ فقط تا <b>{sale['left_str']}</b> دیگر!",
    ]
    if stock is not None and 0 < stock <= 10:
        lines.append(f"⚡ عجله کنید — تنها <b>{stock}</b> عدد باقی مانده!")
    lines.append("━━━━━━━━━━━━━━━")
    return "\n".join(lines) + "\n"


def finalize_product_order(call, uid, product, category, eff_price, wallet_used=0):

    pid = int(product[0])
    title = product[2]
    buyer_type = "partner" if is_partner_approved(uid) else "customer"

    # جلوگیری از دوباره کلیک
    try:
        bot.edit_message_reply_markup(
            call.message.chat.id,
            call.message.message_id,
            reply_markup=None
        )
    except:
        pass

    # ----------------------------
    # بررسی سقف خرید روزانه
    # ----------------------------
    daily_lim_c = product[7] if len(product) > 7 else 0
    daily_lim_p = product[8] if len(product) > 8 else 0
    limit_val = daily_lim_p if buyer_type == "partner" else daily_lim_c
    limit_val = int(limit_val or 0)

    if limit_val > 0:
        cnt = count_user_product_orders_today(uid, pid, buyer_type=buyer_type)
        if cnt >= limit_val:
            bot.answer_callback_query(
                call.id,
                f"سقف خرید روزانه ({limit_val}) تکمیل شده",
                show_alert=True
            )
            return

    # ----------------------------
    # بررسی و کسر موجودی (نسخه قطعی)
    # ----------------------------
    conn = sqlite3.connect(DB_FULL_PATH)
    try:
        cur = conn.cursor()

        cur.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,))
        row = cur.fetchone()

        if not row:
            bot.answer_callback_query(call.id, "کیف پول یافت نشد", show_alert=True)
            return

        current_balance = int(row[0])

        if current_balance < eff_price:
            bot.answer_callback_query(call.id, "موجودی کافی نیست", show_alert=True)
            return

        new_balance = current_balance - eff_price

        cur.execute(
            "UPDATE wallets SET balance=?, updated_at=? WHERE user_id=?",
            (new_balance, datetime.utcnow().isoformat(), uid)
        )
        conn.commit()
    finally:
        conn.close()

    # ----------------------------
    # ایجاد سفارش
    # ----------------------------
    order_id = create_order(
        uid,
        category,
        title,
        eff_price,
        product_id=pid,
        buyer_type=buyer_type
    )

    # پورسانت سطحی — روی «هر» خرید زیرمجموعه (درصد یا مبلغ ثابت سطح معرف)
    try:
        from db import process_referral_commission
        comm = process_referral_commission(uid, order_id, eff_price)
        if comm.get("paid"):
            try:
                _wl = "کیف‌پول همکاری" if comm.get("wallet") == "partner" else "کیف‌پول"
                bot.send_message(comm["referrer_id"],
                    f"💸 <b>پورسانت جدید!</b>\n\n"
                    f"یکی از دعوت‌شده‌های شما خرید کرد و\n"
                    f"💰 <b>{comm['amount']:,}</b> تومان پورسانت (سطح {comm['tier_name']}) "
                    f"به {_wl} شما اضافه شد.",
                    parse_mode="HTML")
            except Exception:
                pass
    except Exception:
        pass

    # مورد ۶: بررسی Level Up بعد از هر خرید همکاری
    try:
        from db import check_and_notify_tier_up
        lu = check_and_notify_tier_up(uid)
        if lu:
            t = lu["tier"]
            comm_lbl = (f"{int(t.get('commission_fixed') or 0):,} تومان ثابت"
                        if int(t.get("commission_fixed") or 0) > 0
                        else f"{t.get('commission_percent') or 0}٪")
            desc = str(t.get("description") or "").strip()
            tier_icon = t.get("icon","⭐")
            tier_name = t.get("name","")
            _sep = "\n"
            lvl_msg = (
                tier_icon + " <b>\u062a\u0628\u0631\u06cc\u06a9! \u0628\u0647 \u0633\u0637\u062d \u00ab" + tier_name + "\u00bb \u0627\u0631\u062a\u0642\u0627 \u06cc\u0627\u0641\u062a\u06cc\u062f!</b>\n\n"
                "\U0001f4b0 \u067e\u0648\u0631\u0633\u0627\u0646\u062a \u062c\u062f\u06cc\u062f: <b>" + comm_lbl + "</b> \u0627\u0632 \u0647\u0631 \u0641\u0631\u0648\u0634\n"
            )
            if desc:
                lvl_msg += "\u2728 " + desc + "\n"
            lvl_msg += "\n\U0001f4aa \u062a\u06cc\u0645 \u0641\u0631\u0648\u0634 \u0634\u0645\u0627 \u0631\u0634\u062f \u0645\u06cc\u200c\u06a9\u0646\u062f \u2014 \u0627\u062f\u0627\u0645\u0647 \u062f\u0647\u06cc\u062f!"
            try: bot.send_message(uid, lvl_msg, parse_mode="HTML")
            except Exception: pass
    except Exception:
        pass

    # مورد ۷ج: reset سقف دعوت بعد از خرید
    try:
        from db import reset_invite_cap_after_purchase
        reset_invite_cap_after_purchase(uid)
    except Exception:
        pass

    # 🚀 پست کانال + امتیازدهی + Upsell (با تأخیر، بعد از تحویل)
    try:
        _cat_for_upsell = None
        try:
            _cat_for_upsell = product.get("category_id") if isinstance(product, dict) else None
        except Exception:
            pass
        _after_purchase_extras(uid, call.message.chat.id, order_id, pid, _cat_for_upsell, title)
    except Exception:
        pass


    # ----------------------------
    # تحویل فوری در صورت وجود موجودی
    # ----------------------------
    # ── اول چک کن نیاز به راه‌اندازی داره یا نه ──────────────────────────
    try:
        ensure_product_support_schema()
        if get_product_support_flag(pid):
            from db import ticket_create, ticket_ensure_schema, ticket_add_message, get_product_setup_message
            ticket_ensure_schema()

            setup_msg = get_product_setup_message(pid) or "اطلاعات مورد نیاز را در این گفتگو ارسال کنید."

            tid = ticket_create(
                uid, type_="product_setup",
                product_id=pid, order_id=order_id,
                feed_id=None,
                feed_data=None,
                setup_status="waiting_info"
            )
            ticket_add_message(tid, "admin",
                f"📦 سفارش #{order_id} — {title}\n\n{setup_msg}",
                media_type=None)

            kb_setup = types.InlineKeyboardMarkup()
            kb_setup.add(types.InlineKeyboardButton(
                "💬 ارسال اطلاعات", callback_data=f"ticket_v2_open_{tid}"
            ))
            bot.send_message(
                call.message.chat.id,
                f"✅ سفارش #{order_id} ثبت شد.\n\n"
                f"📦 <b>{title}</b>\n\n"
                f"🟡 <b>{setup_msg}</b>\n\n"
                "پشتیبانی پس از دریافت اطلاعات، محصول را تحویل می‌دهد.",
                parse_mode="HTML", reply_markup=kb_setup
            )
            try:
                bot.send_message(ADMIN_ID,
                    f"🟢 <b>گفتگوی راه‌اندازی محصول</b>\n"
                    f"سفارش: #{order_id} | محصول: {title}\n"
                    f"کاربر: <code>{uid}</code> | تیکت: #{tid}",
                    parse_mode="HTML")
            except Exception:
                pass
            return  # ← هیچ feed claim نمی‌شه
    except Exception as _se:
        logger.error("product_setup error: %s", _se)

    # ── محصول معمولی: claim از DB ─────────────────────────────────────────
    feed_item = claim_next_feed_item(pid, order_id=order_id)

    if feed_item:
        feed_id, feed_data = feed_item

        # تحویل عادی
        bot.send_message(
            call.message.chat.id,
            f"سفارش ثبت و تحویل شد ✅\n\n"
            f"شماره سفارش: #{order_id}\n"
            f"سرویس: {title}\n"
            f"مبلغ: {eff_price:,} تومان\n"
            f"موجودی فعلی: {new_balance:,} تومان\n\n"
            f"<code>{html.escape(str(feed_data))}</code>",
            parse_mode="HTML"
        )
        # ارسال درخواست امتیازدهی
        try:
            _send_rating_request(call.message.chat.id, uid, order_id, pid, title)
        except Exception:
            pass
        try:
            bot.send_message(ADMIN_ID,
                f"📦 تحویل فوری\nOrder: #{order_id} | User: {uid}\n{title} — {eff_price:,} ت")
        except Exception:
            pass

    else:
        # ثبت در صف pending
        enqueue_pending_delivery(order_id, uid, call.message.chat.id, pid, title, eff_price)

        bot.send_message(
            call.message.chat.id,
            f"سفارش ثبت شد ✅\n\n"
            f"اما فعلاً موجودی این محصول تکمیل شده است.\n"
            f"شکیبا باشید در اولین فرصت توسط ادمین ارسال خواهد شد.\n\n"
            f"موجودی فعلی: {new_balance:,} تومان"
        )

        try:
            bot.send_message(
                ADMIN_ID,
                "⚠️ سفارش بدون موجودی\n\n"
                f"Order ID: #{order_id}\n"
                f"User ID: {uid}\n"
                f"محصول: {title} (#{pid})\n"
                f"مبلغ: {eff_price:,} تومان"
            )
        except:
            pass

def send_products_menu(chat_id, category, admin_view=False, user_id=None):
    products = get_products_by_category(category)
    if not products:
        if admin_view:
            kb = types.InlineKeyboardMarkup(row_width=1)
            kb.add(types.InlineKeyboardButton(
                "➕ افزودن محصول جدید", callback_data=f"admin_new_product_{category}"
            ))
            kb.add(types.InlineKeyboardButton(
                "🔙 بازگشت به دسته‌ها", callback_data="admin_products"
            ))
            bot.send_message(chat_id, "محصولی برای این دسته ثبت نشده است.", reply_markup=kb)
        else:
            bot.send_message(chat_id, "در حال حاضر محصولی برای این دسته ثبت نشده است.")
        return

    kb = types.InlineKeyboardMarkup(row_width=1)
    partner_ok = (not admin_view) and (user_id is not None) and is_partner_approved(int(user_id))
    has_visible = False
    for p in products:
        pid, _, title, price, desc, is_active, partner_price = p
        if not admin_view and not is_active:
            continue
        has_visible = True
        if admin_view:
            status_icon = "✅" if is_active else "❌"
            text = f"{status_icon} {title} | {price:,} تومان"
            cb = f"admin_product_{pid}"
        else:
            eff_price = partner_price if (partner_ok and partner_price) else price
            from db import apply_flash_price as _afp
            eff_price, _flash_sale = _afp(int(pid), int(eff_price))
            text = f"{title} | {eff_price:,} تومان"
            cb = f"{category}_select_{pid}"
        kb.add(types.InlineKeyboardButton(text, callback_data=cb))

    if not has_visible and not admin_view:
        bot.send_message(chat_id, "در حال حاضر محصولی برای این دسته ثبت نشده است.")
        return

    if admin_view:
        kb.add(types.InlineKeyboardButton("➕ افزودن محصول جدید", callback_data=f"admin_new_product_{category}"))
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="admin_products"))
    else:
        back_cb = "back_main" if category == "apple" else "other_categories"
        kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb))

    bot.send_message(chat_id, "لطفا یکی از سرویس‌های زیر را انتخاب کنید:", reply_markup=kb)

#======================= ORDER SUMMARY + DISCOUNT =======================

def _get_eff_price(product, uid):
    """قیمت موثر بر اساس همکار یا مشتری بودن + فروش فوری."""
    price = product[3]
    partner_price = product[6] if len(product) > 6 else None
    partner_ok = is_partner_approved(uid)
    base = partner_price if (partner_ok and partner_price) else price
    from db import apply_flash_price
    eff, _ = apply_flash_price(int(product[0]), int(base))
    return eff


def _show_order_summary(chat_id, uid, product, category, pid):
    """نمایش خلاصه سفارش — با پشتیبانی از پرداخت ترکیبی و فروش فوری."""
    title     = product[2]
    # قیمت پایه (بدون فلش) برای نمایش خط‌خورده
    _p = product[3]
    _pp = product[6] if len(product) > 6 else None
    raw_base  = _pp if (is_partner_approved(uid) and _pp) else _p
    from db import apply_flash_price, get_flash_sale
    base, _fl = apply_flash_price(int(pid), int(raw_base))

    state     = user_states.get(uid, {})
    # 🔥 در فروش فوری، کد تخفیف غیرفعال است — اگر قبلاً اعمال شده، حذف شود
    if _fl and state.get("applied_discount"):
        state.pop("applied_discount", None)
        state.pop("applied_code", None)
        user_states[uid] = state
    discount  = int(state.get("applied_discount", 0))
    code_name = state.get("applied_code", "")
    final     = max(0, base - discount)
    wallet_bal = get_wallet_balance(uid)

    lines = [f"🛒 <b>{title}</b>\n"]
    if _fl:
        lines.append(f"⚡️ <b>فروش فوری {_fl['percent']}٪ فعال است!</b> ⏰ تا {_fl['left_str']} دیگر")
        lines.append(f"مبلغ کالا: <s>{int(raw_base):,}</s> ← <b>{base:,}</b> تومان 🔥")
        lines.append("🎟 در زمان فروش فوری، کد تخفیف قابل استفاده نیست.")
    else:
        lines.append(f"مبلغ کالا: <b>{base:,}</b> تومان")
    if discount > 0:
        lines.append(f"🎟 کد تخفیف: <code>{code_name}</code>")
        lines.append(f"💸 تخفیف: <b>−{discount:,}</b> تومان")
    lines.append(f"\n💰 مبلغ قابل پرداخت: <b>{final:,}</b> تومان")
    if 0 < wallet_bal < final:
        lines.append(f"👛 موجودی کیف‌پول: <b>{wallet_bal:,}</b> تومان")
        lines.append(f"💳 باقیمانده از درگاه: <b>{final - wallet_bal:,}</b> تومان")

    kb = types.InlineKeyboardMarkup(row_width=1)

    if wallet_bal >= final:
        # پرداخت کامل از کیف‌پول
        kb.add(types.InlineKeyboardButton(
            f"💳 پرداخت با کیف‌پول — {final:,} تومان",
            callback_data=f"confirm_wallet_{category}_{pid}"
        ))
        kb.add(types.InlineKeyboardButton(
            "🌐 پرداخت از درگاه",
            callback_data=f"confirm_full_{category}_{pid}"
        ))
    elif 0 < wallet_bal < final:
        # پرداخت ترکیبی
        kb.add(types.InlineKeyboardButton(
            f"💳 پرداخت ترکیبی (کیف‌پول + {final-wallet_bal:,} ت از درگاه)",
            callback_data=f"confirm_wallet_{category}_{pid}"
        ))
        kb.add(types.InlineKeyboardButton(
            f"🌐 پرداخت کامل از درگاه — {final:,} تومان",
            callback_data=f"confirm_full_{category}_{pid}"
        ))
    else:
        # فقط درگاه
        kb.add(types.InlineKeyboardButton(
            f"🌐 پرداخت از درگاه — {final:,} تومان",
            callback_data=f"confirm_full_{category}_{pid}"
        ))

    if _fl:
        pass  # 🔥 فروش فوری — دکمه کد تخفیف نمایش داده نمی‌شود
    elif discount > 0:
        kb.row(
            types.InlineKeyboardButton("🔄 تغییر کد", callback_data=f"enter_code_{category}_{pid}"),
            types.InlineKeyboardButton("🗑 حذف کد",   callback_data=f"remove_code_{category}_{pid}")
        )
    else:
        kb.add(types.InlineKeyboardButton(
            "🎟 کد تخفیف دارم",
            callback_data=f"enter_code_{category}_{pid}"
        ))
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="cancel_purchase"))
    bot.send_message(chat_id, "\n".join(lines), parse_mode="HTML", reply_markup=kb)




# ─── ورود کد تخفیف ──────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("enter_code_"))
def handle_enter_code(call):
    uid  = call.from_user.id
    suf  = call.data[len("enter_code_"):]
    # 🔥 فروش فوری فعال → کد تخفیف مسدود
    try:
        _pid_chk = int(suf.rsplit("_", 1)[-1])
        from db import get_flash_sale
        if get_flash_sale(_pid_chk):
            bot.answer_callback_query(call.id,
                "⚡️ در زمان فروش فوری، کد تخفیف قابل استفاده نیست.", show_alert=True)
            return
    except Exception:
        pass
    # ذخیره info برای برگشت بعد از کد
    user_states.setdefault(uid, {})["code_context"] = suf
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ انصراف", callback_data=f"code_cancel_{suf}"))
    bot.send_message(call.message.chat.id,
        "🎟 کد تخفیف خود را ارسال کنید:", reply_markup=kb)
    bot.register_next_step_handler(call.message, _handle_code_input)
    bot.answer_callback_query(call.id)


def _handle_code_input(message):
    uid  = message.from_user.id
    code = (message.text or "").strip().upper()
    if not code:
        return
    state   = user_states.get(uid, {})
    context = state.get("code_context", "")
    # parse category و pid از context
    parts = context.rsplit("_", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.send_message(message.chat.id, "❌ خطا — دوباره امتحان کنید"); return
    category, pid_str = parts[0], parts[1]
    pid     = int(pid_str)
    product = get_product_by_id(pid)
    if not product:
        bot.send_message(message.chat.id, "❌ محصول یافت نشد"); return

    base   = _get_eff_price(product, uid)
    # 🔥 فروش فوری فعال → کد تخفیف پذیرفته نمی‌شود
    from db import get_flash_sale as _gfs
    if _gfs(pid):
        user_states.setdefault(uid, {}).pop("code_context", None)
        bot.send_message(message.chat.id,
            "⚡️ این محصول در <b>فروش فوری</b> است و کد تخفیف قابل استفاده نیست.\n"
            "قیمت ویژه به‌صورت خودکار اعمال شده 🔥", parse_mode="HTML")
        _show_order_summary(message.chat.id, uid, product, category, pid)
        return
    result = validate_discount(code, product_id=pid, amount=base, user_id=uid)
    if not result["valid"]:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🔙 بازگشت به سفارش",
            callback_data=f"code_cancel_{context}"))
        bot.send_message(message.chat.id, f"❌ {result['error']}", reply_markup=kb)
        return

    use_discount(result["code_id"], user_id=uid)
    state["applied_discount"]  = result["discount_amount"]
    state["applied_code"]      = code
    state["discount_code_id"]  = result["code_id"]
    user_states[uid]           = state
    _show_order_summary(message.chat.id, uid, product, category, pid)


@bot.callback_query_handler(func=lambda c: c.data.startswith("code_cancel_"))
def handle_code_cancel(call):
    uid     = call.from_user.id
    context = call.data[len("code_cancel_"):]
    parts   = context.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        pid     = int(parts[1])
        category = parts[0]
        product  = get_product_by_id(pid)
        if product:
            _show_order_summary(call.message.chat.id, uid, product, category, pid)
    bot.answer_callback_query(call.id)


@bot.callback_query_handler(func=lambda c: c.data.startswith("remove_code_"))
def handle_remove_code(call):
    uid = call.from_user.id
    state = user_states.get(uid, {})
    state.pop("applied_discount", None)
    state.pop("applied_code", None)
    user_states[uid] = state
    context = call.data[len("remove_code_"):]
    parts   = context.rsplit("_", 1)
    if len(parts) == 2 and parts[1].isdigit():
        product = get_product_by_id(int(parts[1]))
        if product:
            _show_order_summary(call.message.chat.id, uid, product, parts[0], int(parts[1]))
    bot.answer_callback_query(call.id, "کد تخفیف حذف شد")


# ─── پرداخت نهایی ────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("do_pay_"))
def handle_do_pay(call):
    uid     = call.from_user.id
    context = call.data[len("do_pay_"):]
    parts   = context.rsplit("_", 1)
    if len(parts) != 2 or not parts[1].isdigit():
        bot.answer_callback_query(call.id, "خطا", show_alert=True); return
    category, pid_str = parts[0], parts[1]
    pid     = int(pid_str)
    product = get_product_by_id(pid)
    if not product:
        bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True); return

    exceeded, limit_val = _daily_limit_exceeded(uid, product, pid)
    if exceeded:
        bot.answer_callback_query(call.id, f"سقف روزانه ({limit_val}) تکمیل شد", show_alert=True); return

    base      = _get_eff_price(product, uid)
    discount  = int(user_states.get(uid, {}).get("applied_discount", 0))
    eff_price = max(0, base - discount)

    # state رو پاک می‌کنیم (code_id قبلاً در _handle_code_input مصرف شده)
    state = user_states.get(uid, {})
    state.pop("applied_discount", None)
    state.pop("applied_code", None)
    state.pop("discount_code_id", None)
    state.pop("pay_type", None)
    state.pop("code_context", None)
    state.pop("discount_asked", None)
    user_states[uid] = state

    wallet_balance = get_wallet_balance(uid)

    if wallet_balance >= eff_price:
        # کیف‌پول کافیه
        finalize_product_order(call, uid, product, category, eff_price)
    else:
        # ارسال به درگاه
        from services.payments import start_wallet_charge_payment
        start_wallet_charge_payment(
            bot=bot, message=call.message, uid=uid, amount=eff_price,
            clear_user_state=clear_user_state,
            payment_type="product", product_id=pid, wallet_reserved=0
        )
    bot.answer_callback_query(call.id)


# ─── deprecated handlers (backward compat) ───────────────────────────────────
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_nodiscount_"))
def handle_pay_nodiscount(call):
    uid = call.from_user.id
    pending_cb = user_states.get(uid, {}).get("pending_cb", "")
    if not pending_cb:
        bot.answer_callback_query(call.id, "خطا", show_alert=True); return
    user_states.setdefault(uid, {})["discount_asked"] = True
    call.data = pending_cb
    if pending_cb.startswith("confirm_full_"):
        handle_confirm_full(call)
    else:
        handle_confirm_wallet(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("discount_start_"))
def handle_discount_start(call): pass

@bot.callback_query_handler(func=lambda c: c.data.startswith("discount_skip_"))
def handle_discount_skip(call): pass


def _daily_limit_exceeded(uid, product, pid):
    """True if the user's daily purchase cap for this product is reached."""
    partner_ok = is_partner_approved(int(uid))
    buyer_type = "partner" if partner_ok else "customer"
    daily_lim_c = product[7] if len(product) > 7 else 0
    daily_lim_p = product[8] if len(product) > 8 else 0
    limit_val = int((daily_lim_p if buyer_type == "partner" else daily_lim_c) or 0)
    if limit_val <= 0:
        return False, 0
    cnt = count_user_product_orders_today(int(uid), int(pid), buyer_type=buyer_type)
    return (cnt >= limit_val), limit_val


@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_full_"))
def handle_confirm_full(call):

    parts = call.data.split("_")
    if len(parts) < 4:
        bot.answer_callback_query(call.id, "داده نامعتبر است", show_alert=True)
        return

    pid_str = parts[-1]
    category = "_".join(parts[2:-1])

    if not pid_str.isdigit():
        bot.answer_callback_query(call.id, "شناسه محصول نامعتبر است", show_alert=True)
        return

    pid = int(pid_str)
    uid = call.from_user.id

    product = get_product_by_id(pid)
    if not product:
        bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
        return

    exceeded, limit_val = _daily_limit_exceeded(uid, product, pid)
    if exceeded:
        bot.answer_callback_query(call.id, f"سقف خرید روزانه ({limit_val}) تکمیل شده است.", show_alert=True)
        return

    title  = product[2]
    price  = product[3]
    partner_price = product[6] if len(product) > 6 else None
    partner_ok    = is_partner_approved(uid)
    eff_price     = partner_price if (partner_ok and partner_price) else price

    # تخفیف اعمال شده از _show_order_summary
    discount  = int(user_states.get(uid, {}).get("applied_discount", 0))
    eff_price = max(0, eff_price - discount)

    # پاک کردن state
    user_states.pop(uid, None)

    from services.payments import start_wallet_charge_payment
    start_wallet_charge_payment(
        bot=bot,
        message=call.message,
        uid=uid,
        amount=eff_price,
        clear_user_state=clear_user_state,
        payment_type="product",
        product_id=pid,
        wallet_reserved=0
    )
    
#======================== confirm_wallet =====================
@bot.callback_query_handler(func=lambda call: call.data.startswith("confirm_wallet_"))
def handle_confirm_wallet(call):
    parts = call.data.split("_")
    if len(parts) < 4:
        bot.answer_callback_query(call.id, "داده نامعتبر است", show_alert=True)
        return
    pid_str = parts[-1]
    category = "_".join(parts[2:-1])
    if not pid_str.isdigit():
        bot.answer_callback_query(call.id, "شناسه محصول نامعتبر است", show_alert=True)
        return
    pid = int(pid_str)
    uid = call.from_user.id

    product = get_product_by_id(pid)
    if not product:
        bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
        return

    exceeded, limit_val = _daily_limit_exceeded(uid, product, pid)
    if exceeded:
        bot.answer_callback_query(call.id, f"سقف خرید روزانه ({limit_val}) تکمیل شده است.", show_alert=True)
        return

    title = product[2]
    price = product[3]
    partner_price = product[6] if len(product) > 6 else None
    partner_ok = is_partner_approved(uid)
    eff_price = partner_price if (partner_ok and partner_price) else price
    from db import apply_flash_price as _afp
    eff_price, _flash_sale = _afp(int(pid), int(eff_price))

    # تخفیف اعمال شده از _show_order_summary
    discount = int(user_states.get(uid, {}).get("applied_discount", 0))
    eff_price = max(0, eff_price - discount)

    # پاک کردن state (discount حفظ می‌شه تا finalize)
    st = user_states.pop(uid, {})
    wallet_used = 0
    wallet_balance = get_wallet_balance(uid)
    if wallet_balance >= eff_price:
        finalize_product_order(call, uid, product, category, eff_price)
        return

    # 🔵 پرداخت ترکیبی: بخشی از کیف پول، بقیه از درگاه.
    # مبلغ درگاه نباید کمتر از حداقل مجاز درگاه شود؛ در غیر این صورت
    # سهم کیف پول را کم می‌کنیم تا سهم درگاه به حداقل برسد.
    gateway_amount = max(MIN_TOPUP_AMOUNT, eff_price - wallet_balance)
    wallet_reserved = eff_price - gateway_amount
    if wallet_reserved < 0:
        wallet_reserved = 0
        gateway_amount = eff_price

    from services.payments import start_wallet_charge_payment

    start_wallet_charge_payment(
        bot=bot,
        message=call.message,
        uid=uid,
        amount=gateway_amount,
        clear_user_state=clear_user_state,
        payment_type="product",
        product_id=pid,
        wallet_reserved=wallet_reserved
    )
    
    
@bot.callback_query_handler(func=lambda c: c.data.startswith("pay_nodiscount_"))
def handle_pay_nodiscount(call):
    uid = call.from_user.id
    pending_cb = user_states.get(uid, {}).get("pending_cb", "")
    if not pending_cb:
        bot.answer_callback_query(call.id, "خطا — دوباره امتحان کنید", show_alert=True)
        return
    user_states.setdefault(uid, {})["discount_asked"] = True
    call.data = pending_cb
    if pending_cb.startswith("confirm_full_"):
        handle_confirm_full(call)
    else:
        handle_confirm_wallet(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("discount_start_"))
def handle_discount_start(call):
    pass  # deprecated — kept for compat


@bot.callback_query_handler(func=lambda c: c.data.startswith("discount_skip_"))
def handle_discount_skip(call):
    pass  # deprecated


def _process_discount_code(message):
    """کاربر کد تخفیف تایپ کرد."""
    uid = message.from_user.id
    code = (message.text or "").strip()

    # اگه پیام واقعی نیست نادیده بگیر
    if not code or len(code) < 2:
        return

    state = user_states.get(uid, {})
    pid = state.get("pid", 0)
    category = state.get("category", "")
    eff_price = state.get("eff_price", 0)
    pending_cb = state.get("pending_cb", "")

    result = validate_discount(code, product_id=pid, amount=eff_price, user_id=uid)

    if not result["valid"]:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            f"✅ ادامه بدون تخفیف — {eff_price:,} تومان",
            callback_data=f"pay_nodiscount_{category}_{pid}"
        ))
        bot.send_message(message.chat.id,
            f"❌ {result['error']}", reply_markup=kb)
        return

    discount = result["discount_amount"]
    use_discount(result["code_id"], user_id=uid)
    final_price = max(0, eff_price - discount)

    state["applied_discount"] = discount
    state["eff_price"] = final_price
    user_states[uid] = state

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        f"✅ پرداخت — {final_price:,} تومان",
        callback_data=pending_cb
    ))
    bot.send_message(message.chat.id,
        f"✅ کد تخفیف اعمال شد!\n"
        f"🎟 تخفیف: <b>{discount:,}</b> تومان\n"
        f"💳 مبلغ نهایی: <b>{final_price:,}</b> تومان",
        parse_mode="HTML", reply_markup=kb
    )


# ─── کد تخفیف ───────────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("apply_discount_"))
def handle_discount_prompt(call):
    """ارسال prompt برای دریافت کد تخفیف."""
    uid = call.from_user.id
    # save callback data so we can resume after discount
    state = user_states.get(uid, {})
    state["discount_resume_cb"] = call.data.replace("apply_discount_", "")
    user_states[uid] = state
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ بدون تخفیف", callback_data="skip_discount"))
    bot.send_message(call.message.chat.id,
        "🎟 کد تخفیف خود را ارسال کنید:\n(در صورت نداشتن، گزینه «بدون تخفیف» را انتخاب کنید)",
        reply_markup=kb)
    bot.register_next_step_handler(call.message, _process_discount_code)


def _process_discount_code(message):
    uid = message.from_user.id
    code = (message.text or "").strip()
    state = user_states.get(uid, {})

    pid = state.get("pid", 0)
    category = state.get("category", "")
    eff_price = state.get("eff_price", 0)

    result = validate_discount(code, product_id=pid, amount=eff_price, user_id=uid)
    if not result["valid"]:
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton(
            "❌ بدون تخفیف ← ادامه",
            callback_data=f"discount_skip_{category}_{pid}"
        ))
        bot.send_message(message.chat.id,
            f"❌ {result['error']}",
            reply_markup=kb)
        return

    discount = result["discount_amount"]
    use_discount(result["code_id"], user_id=uid)
    state["applied_discount"] = discount
    user_states[uid] = state

    final_price = max(0, eff_price - discount)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        f"✅ ادامه خرید — {final_price:,} تومان",
        callback_data=f"confirm_wallet_{category}_{pid}"
    ))
    bot.send_message(message.chat.id,
        f"✅ کد تخفیف اعمال شد!\n"
        f"💰 تخفیف: <b>{discount:,}</b> تومان\n"
        f"💳 مبلغ نهایی: <b>{final_price:,}</b> تومان",
        parse_mode="HTML",
        reply_markup=kb
    )


@bot.callback_query_handler(func=lambda c: c.data == "skip_discount")
def handle_skip_discount(call):
    uid = call.from_user.id
    resume_cb = user_states.get(uid, {}).get("discount_resume_cb", "")
    if resume_cb:
        call.data = resume_cb
        if resume_cb.startswith("confirm_wallet_"):
            handle_confirm_wallet(call)
        elif resume_cb.startswith("confirm_full_"):
            handle_confirm_full(call)


@bot.callback_query_handler(func=lambda c: c.data.startswith("resume_buy_"))
def handle_resume_buy(call):
    original_cb = call.data[len("resume_buy_"):]
    call.data = original_cb
    if original_cb.startswith("confirm_wallet_"):
        handle_confirm_wallet(call)
    elif original_cb.startswith("confirm_full_"):
        handle_confirm_full(call)


# ─── اشتراک موجودی ───────────────────────────────────────────────────────────

@bot.callback_query_handler(func=lambda c: c.data.startswith("notify_stock_"))
def handle_notify_stock(call):
    uid = call.from_user.id
    pid = int(call.data.split("_")[-1])
    added = subscribe_stock(uid, pid)
    if added:
        bot.answer_callback_query(call.id, "✅ به‌محض موجود شدن اطلاع داده می‌شود", show_alert=True)
    else:
        bot.answer_callback_query(call.id, "قبلاً ثبت شده‌اید", show_alert=False)


# ─── پشتیبانی محصول پس از خرید ───────────────────────────────────────────────



def send_admin_categories(chat_id):
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "سایر محصولات فروشگاه🛍", callback_data="admin_other_products"
        ),
        types.InlineKeyboardButton(
            "📱 سرویس‌های اپل آیدی", callback_data="admin_products_cat_apple"
        ),
    )
    
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"))
    bot.send_message(chat_id, "یکی از دسته‌بندی‌های محصولات را انتخاب کنید:", reply_markup=kb)


def send_admin_product_detail(call_message, product, edit=False):
    pid = int(product[0])
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        try:
            _row = _conn.execute(
                'SELECT daily_limit_customer, daily_limit_partner FROM products WHERE id=?',
                (pid,)
            ).fetchone()
        finally:
            _conn.close()
        _lim_c = _row[0] if _row else None
        _lim_p = _row[1] if _row else None
    except Exception:
        _lim_c, _lim_p = None, None

    pid, category, title, price, description, is_active = product[0:6]
    partner_price = product[6] if len(product) > 6 else None
    daily_lim_c = product[7] if len(product) > 7 else None
    daily_lim_p = product[8] if len(product) > 8 else None

    status = "✅ فعال" if is_active else "❌ غیرفعال"
    lim_c_show = 'نامحدود' if (_lim_c is None or int(_lim_c) == 0) else str(int(_lim_c))
    lim_p_show = 'نامحدود' if (_lim_p is None or int(_lim_p) == 0) else str(int(_lim_p))

    text = (
        f"مدیریت محصول #{pid}\n\n"
        f"دسته: <b>{category}</b>\n"
        f"عنوان: <b>{title}</b>\n"
        f"قیمت: <b>{price:,}</b> تومان\n"
        f"قیمت همکار: <b>{(partner_price if partner_price is not None else price):,}</b> تومان\n"
        f"حد خرید روزانه مشتری: <b>{lim_c_show}</b>\n"
        f"حد خرید روزانه همکار: <b>{lim_p_show}</b>\n"
        f"وضعیت: {status}\n\n"
        f"توضیحات:\n{description or '---'}"
    )
    total, remaining, delivered = get_feed_stats(pid)
    threshold, _last = get_feed_alert_setting(pid)
    text += (
        "\n\n📦 موجودی خودکار:\n"
        f"کل: <b>{total}</b> | باقی‌مانده: <b>{remaining}</b> | تحویل‌شده: <b>{delivered}</b>\n"
        f"⚠️ آستانه هشدار: <b>{threshold}</b>"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✏️ ویرایش عنوان", callback_data=f"admin_edit_title_{pid}"),
        types.InlineKeyboardButton("✏️ ویرایش قیمت", callback_data=f"admin_edit_price_{pid}"),
    )
    kb.add(
        types.InlineKeyboardButton("🤝 ویرایش قیمت همکار", callback_data=f"admin_edit_partner_price_{pid}"),
        types.InlineKeyboardButton("🧾 ویرایش توضیحات", callback_data=f"admin_edit_desc_{pid}"),
    )
    kb.add(
        types.InlineKeyboardButton("⛔️ حد خرید مشتری", callback_data=f"admin_set_limit_c_{pid}"),
        types.InlineKeyboardButton("⛔️ حد خرید همکار", callback_data=f"admin_set_limit_p_{pid}"),
    )
    kb.add(
        types.InlineKeyboardButton("📦 بارگذار محصول", callback_data=f"admin_feed_bulk_{pid}"),
        types.InlineKeyboardButton("⚠️ تنظیم هشدار موجودی", callback_data=f"admin_feed_alert_{pid}"),
    )
    # product chat toggle
    try:
        _chat_on = _get_product_chat_enabled(pid)
    except Exception:
        _chat_on = 0
    chat_label = ("💬 چت محصول: ✅ روشن" if int(_chat_on)==1 else "💬 چت محصول: ❌ خاموش")
    kb.add(types.InlineKeyboardButton(chat_label, callback_data=f"admin_toggle_chat_{pid}"))
    kb.add(types.InlineKeyboardButton("✏️ تنظیم متن چت", callback_data=f"admin_set_chattext_{pid}"))
    kb.add(
        types.InlineKeyboardButton(
            "🔴 غیرفعال کردن" if is_active else "🟢 فعال کردن",
            callback_data=f"admin_toggle_active_{pid}"
        )
    )
    
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_products_back"))
    # Stack navigation policy: always send a new message; do not edit the previous one.
    bot.send_message(call_message.chat.id, text, reply_markup=kb)


FEED_PAGE_SIZE = 5

def _feed_item_preview(data: str, max_len: int = 80) -> str:
    data = (data or "").strip()
    if not data:
        return "---"
    first_line = data.splitlines()[0].strip()
    if len(first_line) > max_len:
        return first_line[: max_len - 1] + "…"
    return first_line


def send_admin_feed_list(chat_id: int, product_id: int, page: int = 0, mode: int = 0, message_id: int | None = None):
    pid = int(product_id)
    page = max(int(page or 0), 0)
    mode = int(mode or 0)

    delivered_filter = 0 if mode == 0 else None
    total = count_feed_items(pid, delivered_filter)
    pages = max((total + FEED_PAGE_SIZE - 1) // FEED_PAGE_SIZE, 1)
    if page >= pages:
        page = pages - 1

    offset = page * FEED_PAGE_SIZE
    rows = list_feed_items(pid, delivered_filter, limit=FEED_PAGE_SIZE, offset=offset)

    feed_ids = [int(r[0]) for r in rows] if rows else []
    order_map = _get_order_id_map(feed_ids) if feed_ids else {}

    total_all, remaining, delivered = get_feed_stats(pid)
    header_mode = "فقط تحویل‌نشده" if mode == 0 else "همه"

    text = (
        f"📦 مدیریت بارگذاری محصول (Product ID) #{pid}\n"
        f"حالت نمایش: <b>{header_mode}</b>\n"
        f"صفحه: <b>{page+1}</b> / <b>{pages}</b>\n\n"
        f"آمار: کل <b>{total_all}</b> | باقی‌مانده <b>{remaining}</b> | تحویل‌شده <b>{delivered}</b>\n"
        f"نمایش فعلی: <b>{total}</b> آیتم\n"
        f"شناسه‌های داخل لیست: <b>Feed ID</b> (Order ID فقط برای آیتم‌های تحویل‌شده نمایش داده می‌شود)\n\n"
    )

    if not rows:
        text += "فعلاً آیتمی برای این حالت وجود ندارد."
    else:
        for rid, data, is_del, created_at in rows:
            status = "✅" if int(is_del) == 1 else "📦"
            prev = html.escape(_feed_item_preview(data))
            oid = order_map.get(int(rid))
            dn = _display_order_no(oid)
            suffix = f" — <b>Order #{dn}</b>" if dn is not None else ""
            text += f"{status} <b>Feed #{rid}</b>{suffix} — <code>{prev}</code>\n"

    kb = types.InlineKeyboardMarkup(row_width=2)

    if rows:
        for rid, data, is_del, created_at in rows:
            kb.add(
                types.InlineKeyboardButton(f"👁 Feed #{rid}", callback_data=f"admin_feed_view_{rid}_{pid}_{page}_{mode}"),
                types.InlineKeyboardButton(
                    ("✅ موجود" if int(is_del) == 0 else "♻️ برگشت"),
                    callback_data=f"admin_feed_toggle_{rid}_{pid}_{page}_{mode}",
                ),
            )
            kb.add(
                types.InlineKeyboardButton("🗑 حذف", callback_data=f"admin_feed_delete_{rid}_{pid}_{page}_{mode}"),
            )

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("⬅️ قبلی", callback_data=f"admin_feed_list_{pid}_{page-1}_{mode}"))
    if page < pages - 1:
        nav_row.append(types.InlineKeyboardButton("بعدی ➡️", callback_data=f"admin_feed_list_{pid}_{page+1}_{mode}"))
    if nav_row:
        kb.add(*nav_row)

    kb.add(
        types.InlineKeyboardButton("📃 تحویل‌نشده‌ها", callback_data=f"admin_feed_list_{pid}_0_0"),
        types.InlineKeyboardButton("📃 همه", callback_data=f"admin_feed_list_{pid}_0_1"),
    )
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت به محصول", callback_data=f"admin_product_{pid}"))

    if message_id:
        safe_edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")



# ========= FEED MANAGEMENT (GLOBAL PANEL) =========

FEED_GLOBAL_PAGE_SIZE = 10

def admin_feed_panel_menu():
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("📊 آمار دسته‌بندی / موجودی", callback_data="admin_feed_panel_stats"),
        types.InlineKeyboardButton("📃 همه", callback_data="admin_feed_panel_0_0"),
        types.InlineKeyboardButton("✅ محصولات ارسال‌شده", callback_data="admin_feed_panel_1_0"),
        types.InlineKeyboardButton("📦 محصولات ارسال‌نشده", callback_data="admin_feed_panel_2_0"),
        types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"),
    )
    return kb



def count_feed_items_global(delivered_filter: int | None, category_key: str | None = None):
    import sqlite3
    conn = sqlite3.connect(DB_FULL_PATH)
    try:
        cur = conn.cursor()

        where = []
        params = []
        if delivered_filter is not None:
            where.append("pf.delivered=?")
            params.append(int(delivered_filter))
        if category_key:
            where.append("p.category=?")
            params.append(str(category_key))

        if where:
            cur.execute(
                "SELECT COUNT(*) FROM product_feed pf LEFT JOIN products p ON p.id=pf.product_id WHERE " + " AND ".join(where),
                tuple(params),
            )
        else:
            cur.execute("SELECT COUNT(*) FROM product_feed")
        total = cur.fetchone()[0]
        return int(total or 0)
    finally:
        conn.close()


def list_feed_items_global(delivered_filter: int | None, limit: int = 50, offset: int = 0, category_key: str | None = None):
    import sqlite3
    conn = sqlite3.connect(DB_FULL_PATH)
    try:
        cur = conn.cursor()

        where = []
        params = []
        if delivered_filter is not None:
            where.append("pf.delivered=?")
            params.append(int(delivered_filter))
        if category_key:
            where.append("p.category=?")
            params.append(str(category_key))

        base_sql = '''
            SELECT pf.id, pf.product_id, COALESCE(p.category,''), COALESCE(p.title,''), pf.data, pf.delivered, pf.created_at
            FROM product_feed pf
            LEFT JOIN products p ON p.id = pf.product_id
        '''
        if where:
            base_sql += " WHERE " + " AND ".join(where)
        base_sql += " ORDER BY pf.id DESC LIMIT ? OFFSET ?"

        params.extend([int(limit), int(offset)])
        cur.execute(base_sql, tuple(params))

        rows = cur.fetchall()
        return rows
    finally:
        conn.close()


def get_feed_stats_by_category():
    """Return list of dicts: category, total, delivered, undelivered."""
    import sqlite3
    conn = sqlite3.connect(DB_FULL_PATH)
    try:
        cur = conn.cursor()
        cur.execute(
            '''
            SELECT COALESCE(p.category,'') AS category,
                   COUNT(*) AS total,
                   SUM(CASE WHEN pf.delivered=1 THEN 1 ELSE 0 END) AS delivered,
                   SUM(CASE WHEN pf.delivered=0 THEN 1 ELSE 0 END) AS undelivered
            FROM product_feed pf
            LEFT JOIN products p ON p.id = pf.product_id
            GROUP BY COALESCE(p.category,'')
            ORDER BY total DESC
            '''
        )
        rows = cur.fetchall()
    finally:
        conn.close()
    out = []
    for cat, total, deliv, undel in rows:
        out.append(
            {
                "category": str(cat or "").strip() or "uncategorized",
                "total": int(total or 0),
                "delivered": int(deliv or 0),
                "undelivered": int(undel or 0),
            }
        )
    return out


def send_admin_feed_panel_stats(chat_id: int, message_id: int | None = None):
    stats = get_feed_stats_by_category()
    total_all = sum(s["total"] for s in stats)
    delivered_all = sum(s["delivered"] for s in stats)
    undelivered_all = sum(s["undelivered"] for s in stats)

    text = (
        "📊 <b>آمار بارگذاری محصول / موجودی (بر اساس دسته‌بندی)</b>\n\n"
        f"کل آیتم‌ها: <b>{total_all}</b>\n"
        f"ارسال‌شده: <b>{delivered_all}</b>\n"
        f"ارسال‌نشده (موجودی): <b>{undelivered_all}</b>\n\n"
        "—\n"
    )

    if not stats:
        text += "هیچ آیتمی ثبت نشده است."
    else:
        for s in stats:
            text += (
                f"• <b>{html.escape(s['category'])}</b>: "
                f"کل <b>{s['total']}</b> | "
                f"ارسال‌شده <b>{s['delivered']}</b> | "
                f"موجودی <b>{s['undelivered']}</b>\n"
            )

    kb = types.InlineKeyboardMarkup(row_width=2)
    # quick category drill-down buttons (all items for that category)
    if stats:
        for s in stats[:8]:  # avoid huge keyboards
            cat = s["category"]
            # category keys are short (e.g. apple/gmail). if not safe, skip.
            if len(cat) <= 20 and re.fullmatch(r"[A-Za-z0-9_-]+", cat):
                kb.add(types.InlineKeyboardButton(f"📂 {cat}", callback_data=f"admin_feed_panel_cat_{cat}_0_0"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت به مدیریت محصول", callback_data="admin_feed_panel"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"))

    if message_id:
        safe_edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


def send_admin_feed_panel_list_by_category(chat_id: int, category_key: str, page: int = 0, mode: int = 0, message_id: int | None = None):
    # wrapper so callbacks remain distinct
    send_admin_feed_panel_list(chat_id, page=page, mode=mode, message_id=message_id, category_key=category_key)

def _date_key(created_at: str | None) -> str:
    if not created_at:
        return "بدون تاریخ"
    # supports ISO or 'YYYY-MM-DD HH:MM:SS'
    if "T" in created_at:
        return created_at.split("T")[0]
    return created_at.split(" ")[0]


def send_admin_feed_panel_list(chat_id: int, page: int = 0, mode: int = 0, message_id: int | None = None, category_key: str | None = None):
    page = max(int(page or 0), 0)
    mode = int(mode or 0)

    if mode == 1:
        delivered_filter = 1
        header_mode = "محصولات ارسال‌شده"
    elif mode == 2:
        delivered_filter = 0
        header_mode = "محصولات ارسال‌نشده"
    else:
        delivered_filter = None
        header_mode = "همه"

    if category_key:
        header_mode = f"{header_mode} | دسته: {category_key}"

    total = count_feed_items_global(delivered_filter, category_key=category_key)
    pages = max((total + FEED_GLOBAL_PAGE_SIZE - 1) // FEED_GLOBAL_PAGE_SIZE, 1)
    if page >= pages:
        page = pages - 1

    offset = page * FEED_GLOBAL_PAGE_SIZE
    rows = list_feed_items_global(delivered_filter, limit=FEED_GLOBAL_PAGE_SIZE, offset=offset, category_key=category_key)

    feed_ids = [int(r[0]) for r in rows] if rows else []
    order_map = _get_order_id_map(feed_ids) if feed_ids else {}

    text = (
        "📦 مدیریت محصولات (سراسری)\n"
        f"حالت نمایش: <b>{header_mode}</b>\n"
        f"صفحه: <b>{page+1}</b> / <b>{pages}</b>\n"
        f"تعداد آیتم: <b>{total}</b>\n\n"
        "نمایش به‌صورت مرتب‌سازی بر اساس زمان/شناسه بارگذاری (جدیدترین بالا).\n"
        "شناسه: <b>Feed ID</b> و در صورت ارسال‌شده بودن، <b>Order ID</b> همان سفارش است.\n\n"
    )

    if not rows:
        text += "فعلاً آیتمی وجود ندارد."
    else:
        last_day = None
        for rid, pid, cat, title, data, is_del, created_at in rows:
            day = _date_key(created_at)
            if day != last_day:
                text += f"\n🗓 <b>{html.escape(day)}</b>\n"
                last_day = day
            status = "✅" if int(is_del) == 1 else "📦"
            prev = html.escape(_feed_item_preview(data))
            oid = order_map.get(int(rid))
            dn = _display_order_no(oid)
            suffix = f" — <b>Order #{dn}</b>" if dn is not None else ""
            prod = f"محصول #{pid} | {html.escape(title)}"
            if cat:
                prod = f"{html.escape(cat)} | {prod}"
            text += f"{status} <b>Feed #{rid}</b>{suffix} — {prod} — <code>{prev}</code>\n"

    panel_prefix = (f"admin_feed_panel_cat_{category_key}_" if category_key else "admin_feed_panel_")

    kb = types.InlineKeyboardMarkup(row_width=2)

    if rows:
        for rid, pid, cat, title, data, is_del, created_at in rows:
            kb.add(
                types.InlineKeyboardButton(f"👁 Feed #{rid}", callback_data=(f"admin_feed_panel_view_{rid}_{page}_{mode}_{category_key}" if category_key else f"admin_feed_panel_view_{rid}_{page}_{mode}")),
                types.InlineKeyboardButton(
                    ("✅ موجود" if int(is_del) == 0 else "♻️ برگشت"),
                    callback_data=(f"admin_feed_panel_toggle_{rid}_{page}_{mode}_{category_key}" if category_key else f"admin_feed_panel_toggle_{rid}_{page}_{mode}"),
                ),
            )
            kb.add(types.InlineKeyboardButton("🗑 حذف", callback_data=(f"admin_feed_panel_delete_{rid}_{page}_{mode}_{category_key}" if category_key else f"admin_feed_panel_delete_{rid}_{page}_{mode}")))

    nav_row = []
    if page > 0:
        nav_row.append(types.InlineKeyboardButton("⬅️ قبلی", callback_data=f"{panel_prefix}{mode}_{page-1}"))
    if page < pages - 1:
        nav_row.append(types.InlineKeyboardButton("بعدی ➡️", callback_data=f"{panel_prefix}{mode}_{page+1}"))
    if nav_row:
        kb.add(*nav_row)

    kb.add(
        types.InlineKeyboardButton("📃 همه", callback_data=(f"{panel_prefix}0_0")),
        types.InlineKeyboardButton("✅ ارسال‌شده", callback_data=(f"{panel_prefix}1_0")),
        types.InlineKeyboardButton("📦 ارسال‌نشده", callback_data=(f"{panel_prefix}2_0")),
    )
    if category_key:
        kb.add(types.InlineKeyboardButton("🧹 پاک کردن فیلتر دسته", callback_data="admin_feed_panel_0_0"))
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"))

    #if message_id:
        #safe_edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb, parse_mode="HTML")
    #else:
       #bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")
    if message_id:
        try:
            bot.edit_message_text(
                text=text,
                chat_id=chat_id,
                message_id=message_id,
                reply_markup=kb,
                parse_mode="HTML"
            )
        except Exception:
            bot.send_message(
                chat_id,
                text,
                reply_markup=kb,
                parse_mode="HTML"
            )
    else:
        bot.send_message(
            chat_id,
            text,
            reply_markup=kb,
            parse_mode="HTML"
        )

def send_admin_feed_panel_view(chat_id: int, feed_id: int, page: int = 0, mode: int = 0, message_id: int | None = None, category_key: str | None = None):
    import sqlite3
    fid = int(feed_id)
    conn = sqlite3.connect(DB_FULL_PATH)
    try:
        row = conn.execute(
            '''
            SELECT pf.id, pf.product_id, COALESCE(p.category,''), COALESCE(p.title,''), pf.data, pf.delivered, pf.created_at
            FROM product_feed pf
            LEFT JOIN products p ON p.id = pf.product_id
            WHERE pf.id=?
            ''',
            (fid,),
        ).fetchone()
    finally:
        conn.close()

    if not row:
        bot.send_message(chat_id, "این آیتم یافت نشد.")
        return

    rid, pid, cat, title, data, is_del, created_at = row
    # Resolve Order ID (if this feed was delivered). Prefer persistent delivery_messages mapping.
    oid = None
    try:
        _info = _get_delivery_message(int(rid))
        if _info and len(_info) >= 3:
            oid = _info[2]
    except Exception:
        oid = None
    # Backward-compat: if an older helper exists in some versions, try it.
    if oid is None:
        try:
            oid = _get_order_id_by_feed_id(int(rid))  # type: ignore[name-defined]
        except Exception:
            oid = None

    dn = _display_order_no(oid)
    order_line = f"Order ID: <b>{dn}</b>\n" if dn is not None else ""

    text = (
        f"👁 مشاهده محصولات\n\n"
        f"Feed ID: <b>{rid}</b>\n"
        f"Product ID: <b>{pid}</b>\n"
        f"Category: <b>{html.escape(cat)}</b>\n"
        f"Title: <b>{html.escape(title)}</b>\n"
        f"{order_line}"
        f"Status: <b>{('ارسال‌شده ✅' if int(is_del)==1 else 'ارسال‌نشده 📦')}</b>\n"
        f"Created: <b>{html.escape(str(created_at or ''))}</b>\n\n"
        f"<pre>{html.escape(str(data or ''))}</pre>"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton(
            ("✅ تحویل" if int(is_del) == 0 else "♻️ برگشت"),
            callback_data=(f"admin_feed_panel_toggle_{rid}_{page}_{mode}_{category_key}" if category_key else f"admin_feed_panel_toggle_{rid}_{page}_{mode}"),
        ),
        types.InlineKeyboardButton("🗑 حذف", callback_data=(f"admin_feed_panel_delete_{rid}_{page}_{mode}_{category_key}" if category_key else f"admin_feed_panel_delete_{rid}_{page}_{mode}")),
    )
    kb.add(types.InlineKeyboardButton("⬅️ بازگشت به لیست", callback_data=(f"admin_feed_panel_cat_{category_key}_{mode}_{page}" if category_key else f"admin_feed_panel_{mode}_{page}")))

    if message_id:
        safe_edit_message_text(text, chat_id=chat_id, message_id=message_id, reply_markup=kb, parse_mode="HTML")
    else:
        bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


@bot.message_handler(commands=["myid"])
def handle_myid(message):
    bot.send_message(
        message.chat.id, f"آیدی عددی شما: <code>{message.from_user.id}</code>"
    )


@bot.message_handler(commands=["admin"])
def handle_admin_cmd(message):
    if not ensure_admin(message.from_user.id):
        return
    bot.send_message(
        message.chat.id,
        "پنل مدیریت 👇",
        reply_markup=admin_main_inline(),
    )


# ========= TEXT HANDLERS (USER) =========


def _show_category(chat_id: int, cat_id: int, user_id: int = None, msg_id: int = None):
    """نمایش محتوای یک دسته — زیردسته‌ها یا محصولات"""
    cat = get_category(cat_id)
    if not cat:
        bot.send_message(chat_id, "دسته‌بندی یافت نشد.")
        return

    emoji = (cat["emoji"] or "").strip()
    title = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]

    # breadcrumb
    path = get_category_path(cat_id)
    breadcrumb = " › ".join(
        f"{(c['emoji'] or '').strip()} {c['name']}".strip() for c in path
    )

    subcats = get_subcategories(cat_id, active_only=True)
    if subcats:
        text = f"📂 {breadcrumb}\n\nیکی از دسته‌بندی‌های زیر را انتخاب کنید:"
    else:
        prods = get_category_products(cat_id, active_only=True)
        if not prods:
            text = f"📂 {breadcrumb}\n\nدر حال حاضر محصولی در این دسته موجود نیست."
        else:
            text = f"📂 {breadcrumb}\n\nیکی از محصولات زیر را انتخاب کنید:"

    kb = category_inline_keyboard(cat_id, user_id=user_id)

    if msg_id:
        try:
            bot.edit_message_text(text, chat_id, msg_id, reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, reply_markup=kb)


# هندلر داینامیک دسته‌بندی‌ها (Reply Keyboard)
@bot.message_handler(func=lambda m: bool(get_category_by_button_text(m.text or "")))
def handle_category_button(message):
    cat = get_category_by_button_text(message.text)
    if not cat:
        return
    _show_category(message.chat.id, cat["id"], user_id=message.from_user.id)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_WALLET"))
def handle_wallet(message):
    if not is_main_button_enabled("MAIN_BTN_WALLET"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return

    uid = message.from_user.id
    balance = get_wallet_balance(uid)
    text = tf("MSG_WALLET_BALANCE", balance=f"{balance:,}")
    bot.send_message(message.chat.id, text, reply_markup=wallet_inline_keyboard(), parse_mode="HTML")


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_MY_ORDERS"))
def handle_my_orders_menu(message):
    if not is_main_button_enabled("MAIN_BTN_MY_ORDERS"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return
    uid = message.from_user.id
    _show_my_orders(message.chat.id, uid)


def _show_my_orders(chat_id, uid):
    """نمایش ۵ خرید آخر با inline keyboard کشویی."""
    orders = get_recent_orders_by_user(uid, limit=5)
    if not orders:
        bot.send_message(chat_id, t("MSG_NO_ORDERS", "هنوز خریدی انجام نداده‌اید."))
        return

    text = "🛒 <b>خریدهای من</b>\n\nبرای مشاهده محصول روی هر سفارش بزنید:"
    kb = types.InlineKeyboardMarkup(row_width=1)
    for o in orders:
        oid, title, price, created_at = o
        date_str = (created_at or "")[:10]
        kb.add(types.InlineKeyboardButton(
            f"📦 {title[:35]} — {int(price):,} ت | {date_str}",
            callback_data=f"order_detail_{oid}"
        ))
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data.startswith("order_detail_"))
def cb_order_detail(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        oid = int(call.data.split("_")[-1])
    except ValueError:
        return

    import sqlite3 as _sq
    from config import DB_PATH as _DBP
    conn = _sq.connect(_DBP)
    conn.row_factory = _sq.Row
    try:
        order = conn.execute(
            "SELECT * FROM orders WHERE id=? AND CAST(user_id AS INTEGER)=? "
            "AND COALESCE(status,'active') != 'returned';",
            (oid, uid)
        ).fetchone()
        if not order:
            bot.answer_callback_query(call.id, "سفارش یافت نشد", show_alert=True)
            return
        # محتوای محصول از product_feed
        feed = conn.execute(
            "SELECT data FROM product_feed WHERE order_id=? LIMIT 1;",
            (oid,)
        ).fetchone()
    finally:
        conn.close()

    title     = order["title"] or "—"
    price     = int(order["price"] or 0)
    date_str  = (order["created_at"] or "")[:10]
    feed_data = feed["data"] if feed else None

    if feed_data:
        text = (
            f"📦 <b>سفارش #{oid}</b>\n\n"
            f"محصول: {title}\n"
            f"مبلغ: {price:,} تومان\n"
            f"تاریخ: {date_str}\n\n"
            f"━━━━━━━━━━━━━━━\n"
            f"<code>{feed_data}</code>"
        )
    else:
        text = (
            f"📦 <b>سفارش #{oid}</b>\n\n"
            f"محصول: {title}\n"
            f"مبلغ: {price:,} تومان\n"
            f"تاریخ: {date_str}\n\n"
            f"ℹ️ محتوای این سفارش توسط پشتیبانی تحویل داده می‌شود."
        )

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 بازگشت به خریدها", callback_data="my_orders_back"))
    try:
        bot.edit_message_text(
            text, call.message.chat.id, call.message.message_id,
            parse_mode="HTML", reply_markup=kb
        )
    except Exception:
        bot.send_message(call.message.chat.id, text, parse_mode="HTML", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "my_orders_back")
def cb_my_orders_back(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    _show_my_orders(call.message.chat.id, uid)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_SUPPORT"))
def handle_support(message):
    if not is_main_button_enabled("MAIN_BTN_SUPPORT"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return

    uid = message.from_user.id
    text_support = t("SUPPORT_TEXT", DEFAULT_UI_TEXTS.get("SUPPORT_TEXT", ""))
    ticket_ensure_schema()
    existing = ticket_get_open_support(uid)

    kb = types.InlineKeyboardMarkup()
    if existing:
        kb.add(types.InlineKeyboardButton(
            f"💬 ادامه مکالمه (تیکت #{existing['id']})",
            callback_data=f"ticket_v2_continue_{existing['id']}"
        ))
    else:
        kb.add(types.InlineKeyboardButton(
            "📩 ارسال پیام به پشتیبانی",
            callback_data="ticket_v2_new"
        ))

    bot.send_message(message.chat.id, text_support, reply_markup=kb)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_PARTNER_PANEL"))
def handle_partner_panel(message):
    if not is_main_button_enabled("MAIN_BTN_PARTNER_PANEL"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return

    uid = message.from_user.id
    if not is_partner_approved(uid):
        bot.send_message(message.chat.id,
            "🤝 پنل همکار\n\n"
            "شما هنوز به‌عنوان همکار تایید نشده‌اید.\n"
            "برای ثبت درخواست از «📝 درخواست نمایندگی» استفاده کنید.")
        return

    _show_partner_dashboard(message.chat.id, uid)


def _partner_edit(call, text, kb):
    """edit پیام داشبورد همکار — photo یا text."""
    cid, mid = call.message.chat.id, call.message.message_id
    try:
        bot.edit_message_text(text, cid, mid, parse_mode="HTML", reply_markup=kb)
        return
    except Exception:
        pass
    try:
        bot.edit_message_caption(caption=text, chat_id=cid, message_id=mid,
                                 parse_mode="HTML", reply_markup=kb)
        return
    except Exception:
        pass
    try:
        bot.delete_message(cid, mid)
    except Exception:
        pass
    bot.send_message(cid, text, parse_mode="HTML", reply_markup=kb)


def _show_partner_dashboard(chat_id, uid):
    """داشبورد کامل همکار با سطح، آمار و لینک معرفی."""
    from db import (get_partner_order_count, get_partner_tier_for, get_partner_tiers,
                    get_referral_stats_for, ensure_partner_system_schema,
                    ensure_partner_tiers_extended)
    ensure_partner_system_schema()
    ensure_partner_tiers_extended()

    order_count = get_partner_order_count(uid)
    tier        = get_partner_tier_for(order_count)
    all_tiers   = get_partner_tiers()
    ref_stats   = get_referral_stats_for(uid)

    # سطح بعدی و پیشرفت
    next_tier = None
    for t_ in all_tiers:
        if t_["min_orders"] > order_count:
            next_tier = t_
            break

    if next_tier:
        prev_min = tier.get("min_orders", 0)
        span     = next_tier["min_orders"] - prev_min
        done     = order_count - prev_min
        pct      = int((done / span) * 100) if span > 0 else 0
        filled   = int(pct / 10)
        bar      = "▓" * filled + "░" * (10 - filled)
        next_line = (
            f"\n📈 پیشرفت تا {next_tier['icon']} {next_tier['name']}:\n"
            f"<code>{bar}</code> {pct}%\n"
            f"({next_tier['min_orders'] - order_count} خرید دیگر تا ارتقا)"
        )
    else:
        next_line = "\n🎉 شما در بالاترین سطح هستید!"

    conn = None
    partner_total = 0
    try:
        import sqlite3 as _sq
        from config import DB_PATH as _DBP
        conn = _sq.connect(_DBP)
        row = conn.execute(
            "SELECT COALESCE(SUM(price),0) FROM orders WHERE CAST(user_id AS INTEGER)=? AND buyer_type='partner';",
            (uid,)).fetchone()
        partner_total = int(row[0] or 0) if row else 0
    except Exception:
        pass
    finally:
        if conn: conn.close()

    text = (
        f"🤝 <b>داشبورد همکار</b>\n"
        f"━━━━━━━━━━━━━━━\n\n"
        f"سطح فعلی: <b>{tier['icon']} {tier['name']}</b>\n"
        f"🛒 خریدهای همکاری: <b>{order_count}</b>\n"
        f"💰 مجموع خرید: <b>{partner_total:,}</b> تومان"
        f"{next_line}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"👥 <b>دعوت‌شده‌ها</b>\n"
        f"دعوت‌شده‌ها: {ref_stats['total']} | پاداش دریافتی: {ref_stats['total_reward']:,} ت"
    )

    kb = types.InlineKeyboardMarkup(row_width=2)
    from ui_texts import t as _t, DEFAULT_UI_TEXTS as _D
    kb.row(
        types.InlineKeyboardButton(_t("BTN_PARTNER_MY_SELLERS",  _D.get("BTN_PARTNER_MY_SELLERS",  "👥 فروشندگان من")),  callback_data="partner_sub_stats"),
        types.InlineKeyboardButton(_t("BTN_PARTNER_PROFILE",     _D.get("BTN_PARTNER_PROFILE",     "👤 پروفایل")),        callback_data="partner_profile"),
    )
    kb.row(
        types.InlineKeyboardButton(_t("BTN_PARTNER_WALLET",      _D.get("BTN_PARTNER_WALLET",      "💼 کیف‌پول همکاری")), callback_data="partner_wallet"),
        types.InlineKeyboardButton(_t("BTN_PARTNER_REF_LINK",    _D.get("BTN_PARTNER_REF_LINK",    "🔗 لینک معرفی من")),  callback_data="partner_ref_link"),
    )
    kb.row(
        types.InlineKeyboardButton(_t("BTN_PARTNER_CHAT",        _D.get("BTN_PARTNER_CHAT",        "💬 چت با پشتیبان")), callback_data="partner_support"),
    )

    # بنر سطح
    tier_photo = None
    try:
        tier_photo = (tier.get("photo_file_id") or "").strip() or None
    except Exception:
        pass

    if tier_photo:
        try:
            bot.send_photo(chat_id, tier_photo, caption=text, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)


@bot.callback_query_handler(func=lambda c: c.data == "partner_profile")
def cb_partner_profile(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    _show_partner_profile(call.message.chat.id, uid, edit_msg=call.message.message_id)

def _show_partner_profile(chat_id, uid, edit_msg=None):
    from db import get_partner_bank_info, ensure_partner_bank_schema, ensure_partner_bank_address
    ensure_partner_bank_schema(); ensure_partner_bank_address()
    import sqlite3 as _sq4
    from config import DB_PATH as _DBP4
    partner = None
    try:
        _c = _sq4.connect(_DBP4); _c.row_factory = _sq4.Row
        try:
            partner = _c.execute("SELECT * FROM partners WHERE tg_user_id=?;", (uid,)).fetchone()
        finally:
            _c.close()
    except Exception:
        pass
    bank = get_partner_bank_info(uid)
    def _v(val): return val or "—"
    text = (
        f"👤 <b>پروفایل همکار</b>\n{'─'*20}\n\n"
        f"<b>اطلاعات فروشگاه</b>\n"
        f"👤 نام: {_v(partner['full_name'] if partner else None)}\n"
        f"🏪 فروشگاه: {_v(partner['shop_name'] if partner else None)}\n"
        f"🏙 شهر: {_v(partner['city'] if partner else None)}\n"
        f"📍 آدرس: {_v(bank['address'] if bank else None)}\n\n"
        f"<b>اطلاعات بانکی</b>\n"
        f"👤 صاحب حساب: {_v(bank['full_name'] if bank else None)}\n"
        f"💳 کارت: <code>{_v(bank['card_number'] if bank else None)}</code>\n"
        f"🏦 شبا: <code>{_v(bank['iban'] if bank else None)}</code>"
    )
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.row(
        types.InlineKeyboardButton("✏️ نام", callback_data="pedit_name"),
        types.InlineKeyboardButton("✏️ فروشگاه", callback_data="pedit_shop"),
    )
    kb.row(
        types.InlineKeyboardButton("✏️ شهر", callback_data="pedit_city"),
        types.InlineKeyboardButton("✏️ آدرس", callback_data="pedit_address"),
    )
    kb.row(
        types.InlineKeyboardButton("✏️ کارت", callback_data="pedit_card"),
        types.InlineKeyboardButton("✏️ شبا", callback_data="pedit_iban"),
    )
    kb.row(types.InlineKeyboardButton("✏️ نام صاحب حساب", callback_data="pedit_bankname"))
    kb.row(types.InlineKeyboardButton("🔙 بازگشت", callback_data="partner_back"))
    if edit_msg:
        try:
            bot.edit_message_text(text, chat_id, edit_msg, parse_mode="HTML", reply_markup=kb)
            return
        except Exception:
            pass
    bot.send_message(chat_id, text, parse_mode="HTML", reply_markup=kb)

_PEDIT_MAP = {
    "pedit_name":     ("partner_name",    "نام و نام خانوادگی"),
    "pedit_shop":     ("partner_shop",    "نام فروشگاه"),
    "pedit_city":     ("partner_city",    "شهر"),
    "pedit_address":  ("partner_address", "آدرس"),
    "pedit_card":     ("partner_card",    "شماره کارت (۱۶ رقم)"),
    "pedit_iban":     ("partner_iban",    "شماره شبا (با یا بدون IR)"),
    "pedit_bankname": ("partner_bankname","نام صاحب حساب"),
}

@bot.callback_query_handler(func=lambda c: c.data in _PEDIT_MAP)
def cb_pedit(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    mode, label = _PEDIT_MAP[call.data]
    user_states[uid] = {"mode": mode}
    bot.send_message(call.message.chat.id, f"✏️ <b>{label}</b> را وارد کنید:", parse_mode="HTML")

def _pedit_save(uid, chat_id, table, col, val):
    import sqlite3 as _sqe
    from config import DB_PATH as _DBPe
    from db import ensure_partner_bank_schema, ensure_partner_bank_address, get_partner_bank_info
    ensure_partner_bank_schema(); ensure_partner_bank_address()
    conn = _sqe.connect(_DBPe)
    try:
        if table == "partners":
            conn.execute(f"UPDATE partners SET {col}=? WHERE tg_user_id=?;", (val, uid))
        else:
            bank = get_partner_bank_info(uid)
            if bank:
                conn.execute(f"UPDATE partner_bank_info SET {col}=?,updated_at=datetime('now') WHERE user_id=?;", (val, uid))
            else:
                conn.execute(f"INSERT OR REPLACE INTO partner_bank_info (user_id,{col}) VALUES (?,?);", (uid, val))
        conn.commit()
    finally:
        conn.close()
    bot.send_message(chat_id, "✅ ذخیره شد.")
    _show_partner_profile(chat_id, uid)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_name")
def _ph_name(message):
    uid=message.from_user.id; val=(message.text or "").strip()
    if not val: bot.reply_to(message,"نام نمی‌تواند خالی باشد:"); return
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partners","full_name",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_shop")
def _ph_shop(message):
    uid=message.from_user.id; val=(message.text or "").strip()
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partners","shop_name",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_city")
def _ph_city(message):
    uid=message.from_user.id; val=(message.text or "").strip()
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partners","city",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_address")
def _ph_address(message):
    uid=message.from_user.id; val=(message.text or "").strip()
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partner_bank_info","address",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_card")
def _ph_card(message):
    uid=message.from_user.id; val=(message.text or "").replace("-","").replace(" ","").strip()
    if not (val.isdigit() and len(val)==16):
        bot.reply_to(message,"شماره کارت باید ۱۶ رقم باشد:"); return
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partner_bank_info","card_number",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_iban")
def _ph_iban(message):
    uid=message.from_user.id; val=(message.text or "").strip().upper().replace(" ","")
    if not val.startswith("IR"): val="IR"+val
    if len(val)!=26: bot.reply_to(message,"شماره شبا باید ۲۴ رقم (بدون IR) باشد:"); return
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partner_bank_info","iban",val)

@bot.message_handler(func=lambda m: user_states.get(m.from_user.id,{}).get("mode")=="partner_bankname")
def _ph_bankname(message):
    uid=message.from_user.id; val=(message.text or "").strip()
    user_states.pop(uid,None); _pedit_save(uid,message.chat.id,"partner_bank_info","full_name",val)


@bot.callback_query_handler(func=lambda c: c.data == "partner_ref_link")
def cb_partner_ref_link(call):
    """🔗 نمای ادغام‌شده: لینک معرفی + آمار + متن تبلیغاتی آماده + اشتراک یک‌لمسی."""
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    from db import get_referral_stats_for, get_referral_settings, get_promo_settings
    settings = get_referral_settings()
    stats    = get_referral_stats_for(uid)
    bot_username = _bot_username() or "your_bot"
    link = f"https://t.me/{bot_username}?start=ref_{uid}"
    reward = settings.get("reward_amount", 5000)
    promo  = str(get_promo_settings().get("text") or "").format(link=link)

    text = (
        f"🔗 <b>لینک معرفی و ابزار تبلیغ</b>\n\n"
        f"لینک اختصاصی شما:\n<code>{link}</code>\n\n"
        f"💰 پاداش هر عضویت: <b>{reward:,}</b> تومان\n"
        f"💸 + پورسانت از هر خرید دعوت‌شده‌ها (بر اساس سطح شما)\n\n"
        f"📊 آمار تیم فروش شما:\n"
        f"• کل دعوت‌شده‌ها: <b>{stats['total']}</b>\n"
        f"• پاداش دریافتی: <b>{stats['total_reward']:,}</b> تومان\n\n"
        f"📣 <b>متن آماده تبلیغ</b> (کپی یا فوروارد کنید):\n"
        f"➖➖➖➖➖➖➖➖\n"
        f"{promo}\n"
        f"➖➖➖➖➖➖➖➖"
    )
    import urllib.parse as _up
    share_url = "https://t.me/share/url?url=" + _up.quote(link) + "&text=" + _up.quote(promo)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📤 ارسال به دوستان و گروه‌ها", url=share_url))
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="partner_back"))
    _partner_edit(call, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "partner_sub_stats")
def cb_partner_sub_stats(call):
    """نمای تیم فروش — کاربر بالا، دعوت‌شده‌ها با آمار خرید زیرش"""
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    import sqlite3 as _sq
    from config import DB_PATH as _DBP

    my_name = (call.from_user.first_name or "شما").strip()
    subs, total_orders, total_purchase = [], 0, 0
    try:
        conn = _sq.connect(_DBP)
        conn.row_factory = _sq.Row
        # زیرمجموعه‌ها + آمار خرید هرکدام + تعداد زیرمجموعه‌ی خودشان (سطح ۲)
        subs = conn.execute("""
            SELECT r.referred_id AS sid,
                   COALESCE(u.full_name, u.username, 'کاربر ' || r.referred_id) AS name,
                   COALESCE(o.cnt, 0)   AS order_count,
                   COALESCE(o.total, 0) AS total_spent,
                   COALESCE(r2.cnt, 0)  AS own_subs
            FROM referrals r
            LEFT JOIN users u ON CAST(u.user_id AS INTEGER) = r.referred_id
            LEFT JOIN (
                SELECT CAST(user_id AS INTEGER) AS ouid, COUNT(*) AS cnt, SUM(price) AS total
                FROM orders WHERE COALESCE(status,'active') != 'returned'
                GROUP BY CAST(user_id AS INTEGER)
            ) o ON o.ouid = r.referred_id
            LEFT JOIN (
                SELECT referrer_id, COUNT(*) AS cnt FROM referrals GROUP BY referrer_id
            ) r2 ON r2.referrer_id = r.referred_id
            WHERE r.referrer_id = ?
            ORDER BY total_spent DESC, order_count DESC
            LIMIT 30;
        """, (uid,)).fetchall()
        conn.close()
        total_orders   = sum(int(s["order_count"]) for s in subs)
        total_purchase = sum(int(s["total_spent"]) for s in subs)
    except Exception:
        subs = []

    # ─── ساخت درخت شبکه ───
    lines = [
        f"👥 <b>فروشندگان من</b>\n",
        f"👤 <b>{my_name}</b>  (شما)",
    ]
    if not subs:
        lines.append("\n└ هنوز فروشنده‌ای ندارید.\n\n🔗 لینک معرفی خود را به اشتراک بگذارید تا تیم فروش شما رشد کند!")
    else:
        for i, s in enumerate(subs):
            is_last = (i == len(subs) - 1)
            branch  = "└" if is_last else "├"
            medal   = "🥇" if i == 0 and s["order_count"] > 0 else ("🥈" if i == 1 and s["order_count"] > 0 else ("🥉" if i == 2 and s["order_count"] > 0 else "👤"))
            own     = f" | 👥{s['own_subs']}" if s["own_subs"] else ""
            if s["order_count"] > 0:
                lines.append(f"{branch} {medal} {s['name']}\n{'   ' if is_last else '│  '}🛒 {s['order_count']} خرید | 💰 {int(s['total_spent']):,} ت{own}")
            else:
                lines.append(f"{branch} {medal} {s['name']} — بدون خرید{own}")
        lines.append(
            f"\n━━━━━━━━━━━━━━━\n"
            f"📊 جمع تیم: <b>{len(subs)}</b> نفر | "
            f"🛒 <b>{total_orders}</b> خرید | 💰 <b>{total_purchase:,}</b> ت"
        )

    text = "\n".join(lines)
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="partner_back"))
    _partner_edit(call, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "partner_wallet")
def cb_partner_wallet(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    from db import get_partner_wallet_balance, get_partner_transactions, ensure_partner_wallet_schema
    ensure_partner_wallet_schema()
    bal = get_partner_wallet_balance(uid)
    txns = get_partner_transactions(uid, 5)

    type_map = {
        "credit": "💚 واریز پورسانت",
        "transfer_out": "🔄 انتقال به کیف‌پول اصلی",
        "payout_request": "📤 درخواست تسویه",
        "payout_rejected": "↩️ برگشت تسویه",
    }
    txn_lines = "\n".join(
        f"{'+'if tx['type'] in ('credit','payout_rejected') else '-'}"
        f"{int(tx['amount']):,} ت — {type_map.get(tx['type'],tx['type'])} ({(tx['created_at'] or '')[:10]})"
        for tx in txns
    ) if txns else "تراکنشی ثبت نشده"

    text = (
        f"💼 <b>کیف‌پول همکاری</b>\n\n"
        f"موجودی: <b>{bal:,}</b> تومان\n\n"
        f"📋 <b>آخرین تراکنش‌ها:</b>\n{txn_lines}"
    )
    from ui_texts import t as _t, DEFAULT_UI_TEXTS as _D
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton(_t("BTN_WALLET_TRANSFER", _D.get("BTN_WALLET_TRANSFER", "🔄 انتقال به کیف‌پول اصلی")), callback_data="partner_transfer"),
        types.InlineKeyboardButton(_t("BTN_WALLET_PAYOUT",   _D.get("BTN_WALLET_PAYOUT",   "📤 درخواست تسویه")),          callback_data="partner_payout"),
        types.InlineKeyboardButton("🔙 بازگشت", callback_data="partner_back"),
    )
    _partner_edit(call, text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "partner_transfer")
def cb_partner_transfer(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    from db import get_partner_wallet_balance
    bal = get_partner_wallet_balance(uid)
    if bal <= 0:
        bot.answer_callback_query(call.id, "موجودی کیف‌پول همکاری صفر است", show_alert=True)
        return
    user_states[uid] = {"mode": "partner_transfer", "max": bal}
    bot.send_message(call.message.chat.id,
        f"🔄 <b>انتقال به کیف‌پول اصلی</b>\n\n"
        f"موجودی: <b>{bal:,}</b> تومان\n\n"
        "مبلغ مورد نظر را وارد کنید (تومان):\n"
        "(یا «همه» برای انتقال کل موجودی)",
        parse_mode="HTML")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "partner_transfer")
def handle_partner_transfer(message):
    uid = message.from_user.id
    if _exit_chat_if_needed(message):
        return
    st = user_states.pop(uid, {})
    max_bal = st.get("max", 0)
    txt = (message.text or "").strip()
    if txt == "همه":
        amount = max_bal
    elif txt.isdigit():
        amount = int(txt)
    else:
        bot.reply_to(message, "مبلغ نامعتبر. عدد وارد کنید.")
        return
    from db import transfer_partner_to_main
    result = transfer_partner_to_main(uid, amount)
    if result["ok"]:
        bot.send_message(message.chat.id,
            f"✅ <b>{amount:,}</b> تومان به کیف‌پول اصلی منتقل شد.",
            parse_mode="HTML", reply_markup=main_menu(user_id=uid))
    else:
        bot.reply_to(message, f"❌ {result['error']}")


@bot.callback_query_handler(func=lambda c: c.data == "partner_payout")
def cb_partner_payout(call):
    uid = call.from_user.id
    from db import (get_partner_wallet_balance, get_partner_payout_settings,
                    ensure_partner_wallet_schema, get_partner_bank_info,
                    ensure_partner_bank_schema, ensure_partner_bank_address)
    ensure_partner_wallet_schema()
    ensure_partner_bank_schema(); ensure_partner_bank_address()
    settings = get_partner_payout_settings()
    if not settings.get("is_active"):
        bot.answer_callback_query(call.id, "تسویه در حال حاضر غیرفعال است", show_alert=True)
        return
    bal = get_partner_wallet_balance(uid)
    min_a = int(settings.get("min_amount") or 0)
    if min_a and bal < min_a:
        bot.answer_callback_query(call.id,
            f"حداقل موجودی برای تسویه {min_a:,} تومان است.\nموجودی شما: {bal:,} تومان",
            show_alert=True)
        return
    bot.answer_callback_query(call.id)

    # مورد ۴: بررسی اطلاعات بانکی — اگر ناقص است ابتدا جمع‌آوری کن
    bank = get_partner_bank_info(uid)
    if not bank or not (bank.get("iban") or "").strip() or not (bank.get("owner_name") or "").strip():
        user_states[uid] = {"mode": "payout_collect_bank", "step": "owner_name", "bal": bal}
        bot.send_message(call.message.chat.id,
            "🏦 <b>برای ثبت درخواست تسویه، اطلاعات حساب بانکی لازم است.</b>\n\n"
            "لطفاً <b>نام صاحب حساب</b> را وارد کنید:",
            parse_mode="HTML")
        return

    max_a  = int(settings.get("max_amount") or 0)
    max_pm = int(settings.get("max_per_month") or 0)
    user_states[uid] = {"mode": "partner_payout", "bal": bal}
    _iban  = (bank.get("iban") or "").strip()
    _owner = (bank.get("owner_name") or bank.get("iban") or "—").strip()
    text = (
        f"📤 <b>درخواست تسویه</b>\n\n"
        f"موجودی: <b>{bal:,}</b> تومان\n"
        f"{'حداقل: '+format(min_a,',')+' تومان' if min_a else ''}\n"
        f"{'حداکثر: '+format(max_a,',')+' تومان' if max_a else ''}\n"
        f"{'سقف ماهانه: '+str(max_pm)+' درخواست' if max_pm else ''}\n\n"
        f"🏦 پرداخت به: <b>{_owner}</b> — <code>{_iban}</code>\n\n"
        "مبلغ درخواستی را وارد کنید:"
    )
    bot.send_message(call.message.chat.id, text, parse_mode="HTML")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "payout_collect_bank")
def handle_payout_collect_bank(message):
    """جمع‌آوری اطلاعات بانکی قبل از تسویه — مرحله‌ای."""
    uid = message.from_user.id
    state = user_states.get(uid, {})
    step  = state.get("step")
    text  = (message.text or "").strip()
    if not text:
        bot.reply_to(message, "❌ لطفاً متن وارد کنید.")
        return

    from db import ensure_partner_bank_schema, ensure_partner_bank_address
    import sqlite3 as _sq
    from config import DB_PATH as _DBP
    ensure_partner_bank_schema(); ensure_partner_bank_address()

    if step == "owner_name":
        state["owner_name"] = text
        state["step"] = "iban"
        user_states[uid] = state
        bot.reply_to(message,
            "✅ نام ذخیره شد.\n\n"
            "حالا <b>شماره شبا</b> را وارد کنید (با یا بدون IR):",
            parse_mode="HTML")
    elif step == "iban":
        iban = text.upper().replace(" ", "").replace("-", "")
        if not iban.startswith("IR"):
            iban = "IR" + iban
        if len(iban) != 26 or not iban[2:].isdigit():
            bot.reply_to(message,
                "❌ شماره شبا نامعتبر است.\n"
                "شبا باید ۲۴ رقم داشته باشد (IR + ۲۴ رقم).\n"
                "دوباره وارد کنید:")
            return
        owner = state.get("owner_name", "")
        try:
            conn = _sq.connect(_DBP)
            existing = conn.execute(
                "SELECT 1 FROM partner_bank_info WHERE user_id=?;", (uid,)).fetchone()
            if existing:
                conn.execute(
                    "UPDATE partner_bank_info SET owner_name=?,iban=?,updated_at=datetime('now') WHERE user_id=?;",
                    (owner, iban, uid))
            else:
                conn.execute(
                    "INSERT INTO partner_bank_info (user_id,owner_name,iban) VALUES (?,?,?);",
                    (uid, owner, iban))
            conn.commit(); conn.close()
        except Exception as ex:
            bot.reply_to(message, f"❌ خطا در ذخیره: {ex}")
            return

        # ادامه به تسویه
        bal = state.get("bal", 0)
        user_states[uid] = {"mode": "partner_payout", "bal": bal}
        bot.reply_to(message,
            f"✅ اطلاعات بانکی ذخیره شد.\n\n"
            f"🏦 <b>{owner}</b> — <code>{iban}</code>\n\n"
            f"موجودی شما: <b>{bal:,}</b> تومان\n"
            "مبلغ درخواستی را وارد کنید:",
            parse_mode="HTML")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "partner_payout")
def handle_partner_payout(message):
    uid = message.from_user.id
    if _exit_chat_if_needed(message):
        return
    st = user_states.pop(uid, {})
    txt = (message.text or "").strip()
    if not txt.isdigit():
        bot.reply_to(message, "مبلغ نامعتبر. عدد وارد کنید.")
        return
    amount = int(txt)
    from db import request_partner_payout
    result = request_partner_payout(uid, amount)
    if result["ok"]:
        bot.send_message(message.chat.id,
            f"✅ درخواست تسویه <b>{amount:,}</b> تومان ثبت شد.\n"
            "پس از بررسی، نتیجه اعلام می‌شود.",
            parse_mode="HTML", reply_markup=main_menu(user_id=uid))
        try:
            bot.send_message(ADMIN_ID,
                f"📤 <b>درخواست تسویه همکار</b>\n"
                f"کاربر: <code>{uid}</code>\n"
                f"مبلغ: <b>{amount:,}</b> تومان\n\n"
                f"برای بررسی: /admin → همکاران → تسویه‌ها",
                parse_mode="HTML")
        except Exception:
            pass
    else:
        bot.reply_to(message, f"❌ {result['error']}")


@bot.callback_query_handler(func=lambda c: c.data == "partner_guide")
def cb_partner_guide(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    guide_text = t("PARTNER_GUIDE_TEXT",
        "📖 <b>راهنمای همکاری در فروش</b>\n\n"
        "متن راهنما توسط مدیر تنظیم نشده است.\n"
        "لطفاً با پشتیبانی تماس بگیرید.")
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data="partner_back"))
    _partner_edit(call, guide_text, kb)


@bot.callback_query_handler(func=lambda c: c.data == "partner_support")
def cb_partner_support(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    # باز کردن تیکت با نوع «همکاران»
    from db import ticket_create, ticket_ensure_schema, ticket_get_open_support
    ticket_ensure_schema()
    # اگه تیکت همکاری باز داره، ادامه بده
    existing = None
    try:
        import sqlite3 as _sq
        from config import DB_PATH as _DBP
        _c = _sq.connect(_DBP); _c.row_factory = _sq.Row
        try:
            existing = _c.execute(
                "SELECT * FROM tickets WHERE user_id=? AND type='partner_support' AND status!='closed' ORDER BY id DESC LIMIT 1;",
                (uid,)
            ).fetchone()
        finally:
            _c.close()
    except Exception:
        pass

    if existing:
        tid = existing["id"]
        try:
            cur_cnt = int(existing["user_msg_count"] or 0)
        except Exception:
            cur_cnt = 0
        user_states[uid] = {"mode": "ticket_v2", "ticket_id": tid}
        if cur_cnt >= TICKET_MAX_USER_MSGS:
            bot.send_message(call.message.chat.id,
                f"💬 <b>گفتگوی همکاری #{tid}</b>\n\n"
                "🔒 گفتگو در انتظار پاسخ پشتیبانی است.\n"
                "پس از پاسخ، می‌توانید ادامه دهید.",
                parse_mode="HTML")
        else:
            bot.send_message(call.message.chat.id,
                f"💬 <b>ادامه گفتگوی همکاری #{tid}</b>\n\n"
                "پیام خود را ارسال کنید.",
                parse_mode="HTML")
    else:
        tid = ticket_create(uid, type_="partner_support")
        user_states[uid] = {"mode": "ticket_v2", "ticket_id": tid}
        bot.send_message(call.message.chat.id,
            f"💬 <b>چت با پشتیبان همکاران</b> (تیکت #{tid})\n\n"
            "پیام خود را ارسال کنید. تیم پشتیبانی به‌زودی پاسخ می‌دهد.",
            parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data == "partner_back")
def cb_partner_back(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception:
        pass
    _show_partner_dashboard(call.message.chat.id, uid)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_PARTNER_REQUEST"))
def handle_reseller_request(message):
    if not is_main_button_enabled("MAIN_BTN_PARTNER_REQUEST"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return
    uid = message.from_user.id
    ok, msg = can_submit_partner_request(uid)
    if not ok:
        bot.send_message(message.chat.id, msg)
        return

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("📱 ارسال شماره تلفن", request_contact=True))
    kb.add(types.KeyboardButton("❌ انصراف"))
    bot.send_message(
        message.chat.id,
        "🏪 <b>درخواست فروشندگی StockLand</b>\n\n"
        "با ثبت درخواست فروشنده می‌شوید و از مزایا زیر بهره‌مند می‌شوید:\n"
        "• لینک اختصاصی فروش\n"
        "• پورسانت به ازای هر فروش\n"
        "• قیمت ویژه محصولات\n"
        "• پنل اختصاصی آمار\n\n"
        "ابتدا شماره تلفن خود را ارسال کنید:",
        reply_markup=kb, parse_mode="HTML"
    )
    bot.register_next_step_handler(message, process_reseller_contact)


def process_reseller_contact(message):
    uid = message.from_user.id

    if message.text and message.text.strip() == "❌ انصراف":
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu(user_id=uid))
        return
    if message.content_type != "contact" or not message.contact:
        bot.send_message(message.chat.id, "لطفاً شماره را فقط با دکمه «📱 ارسال شماره تلفن» ارسال کنید.",
                         reply_markup=main_menu(user_id=uid))
        return
    if message.contact.user_id and message.contact.user_id != uid:
        bot.send_message(message.chat.id, "شماره ارسالی متعلق به همین اکانت نیست.",
                         reply_markup=main_menu(user_id=uid))
        return

    phone = (message.contact.phone_number or "").strip()
    ok, msg = can_submit_partner_request(uid, phone=phone)
    if not ok:
        bot.send_message(message.chat.id, msg, reply_markup=main_menu(user_id=uid))
        return

    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()
    reseller_signup[uid] = {
        "phone": phone, "username": message.from_user.username or "",
        "full_name": full_name, "city": "", "shop_name": "",
    }

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("❌ انصراف"))
    bot.send_message(message.chat.id, "شهر فعالیت خود را وارد کنید:", reply_markup=kb)
    bot.register_next_step_handler(message, process_reseller_city)


def process_reseller_city(message):
    uid = message.from_user.id
    if message.text and message.text.strip() == "❌ انصراف":
        reseller_signup.pop(uid, None)
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu(user_id=uid))
        return
    city = (message.text or "").strip()
    if not city or len(city) < 2:
        bot.send_message(message.chat.id, "نام شهر نامعتبر است. دوباره ارسال کنید:")
        bot.register_next_step_handler(message, process_reseller_city)
        return
    if uid not in reseller_signup:
        bot.send_message(message.chat.id, "درخواست شما منقضی شد. دوباره شروع کنید.",
                         reply_markup=main_menu(user_id=uid))
        return
    reseller_signup[uid]["city"] = city

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("❌ انصراف"))
    bot.send_message(message.chat.id, "نام فروشگاه / پیج / مجموعه را وارد کنید:", reply_markup=kb)
    bot.register_next_step_handler(message, process_reseller_shop)


def process_reseller_shop(message):
    uid = message.from_user.id
    if message.text and message.text.strip() == "❌ انصراف":
        reseller_signup.pop(uid, None)
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu(user_id=uid))
        return
    shop_name = (message.text or "").strip()
    if not shop_name or len(shop_name) < 2:
        bot.send_message(message.chat.id, "نام فروشگاه نامعتبر است. دوباره ارسال کنید:")
        bot.register_next_step_handler(message, process_reseller_shop)
        return

    data = reseller_signup.pop(uid, None)
    if not data:
        bot.send_message(message.chat.id, "درخواست شما منقضی شد. دوباره شروع کنید.",
                         reply_markup=main_menu(user_id=uid))
        return

    upsert_partner_request(uid, data["phone"], username=data["username"],
                           full_name=data["full_name"], note="",
                           city=data["city"], shop_name=shop_name)

    bot.send_message(message.chat.id,
        "✅ <b>درخواست فروشندگی شما ثبت شد!</b>\n\n"
        "پس از بررسی توسط ادمین، نتیجه به شما اعلام می‌شود.\n"
        "معمولاً در کمتر از ۲۴ ساعت پاسخ داده می‌شود.",
        parse_mode="HTML", reply_markup=main_menu(user_id=uid))

    # نوتیف به ادمین
    try:
        kb_adm = types.InlineKeyboardMarkup()
        kb_adm.add(types.InlineKeyboardButton("🌐 بررسی در پنل", url="https://panel.stland.ir/admin/sellers"))
        bot.send_message(ADMIN_ID,
            f"🔔 <b>درخواست فروشندگی جدید</b>\n"
            f"کاربر: <code>{uid}</code> — {data['full_name']}\n"
            f"شهر: {data['city']} | فروشگاه: {shop_name}",
            reply_markup=kb_adm, parse_mode="HTML")
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == t("BTN_PARTNER_GUIDE") and is_partner_approved(m.from_user.id))
def handle_partner_guide_reply(message):
    """همکار دکمه «راهنما و قوانین» را در Reply Keyboard فشرد"""
    guide_text = t(
        "PARTNER_GUIDE_TEXT",
        "📖 <b>راهنمای همکاری در فروش</b>\n\n"
        "متن راهنما توسط مدیر تنظیم نشده است.\n"
        "برای اطلاعات بیشتر با پشتیبانی در تماس باشید."
    )
    kb = types.InlineKeyboardMarkup()
    bot.send_message(message.chat.id, guide_text, reply_markup=kb, parse_mode="HTML")


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "payout_collect_bank")
def _pre_handle_payout_bank(message):
    return handle_payout_collect_bank(message)


# ── ثبتِ زودهنگام — این‌ها باید قبل از catch-all ادمین (پایین) ثبت شوند
# وگرنه پیام‌های متنیِ ادمین‌ها هرگز به آن‌ها نمی‌رسد.
@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_INVITE"))
def _pre_handle_user_invite(message):
    return handle_user_invite(message)


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "crypto_amount")
def _pre_handle_crypto_amount(message):
    return handle_crypto_amount(message)


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "crypto_txid")
def _pre_handle_crypto_txid(message):
    return handle_crypto_txid(message)


@bot.message_handler(func=lambda m: ensure_admin(m.from_user.id))
def handle_admin_text(message):
    aid = message.from_user.id

    # ─── اگه ادمین در حالت تیکت کاربر (تست) باشه → به handler تیکت برو ──
    user_st = user_states.get(aid, {})
    if user_st.get("mode") == "ticket_support":
        handle_ticket_chat_user(message)
        return

    state = admin_states.get(aid)
    if not state:
        return

    mode = state.get("mode")

    # ─── پاسخ ادمین به تیکت از تلگرام (v2) ──────────────────────────────
    if mode == "ticket_v2_admin_reply":
        tid_val = int(state.get("ticket_id") or 0)
        target_uid = int(state.get("target_uid") or 0)
        if not tid_val or not target_uid:
            clear_admin_state(aid)
            bot.reply_to(message, "تیکت نامعتبر.")
            return

        txt = (message.text or "").strip()
        if txt == "/done":
            clear_admin_state(aid)
            bot.reply_to(message, "پایان حالت پاسخ.")
            return
        if not txt:
            bot.reply_to(message, "پیام خالی — دوباره ارسال کنید:")
            return

        ticket = ticket_get(tid_val)
        if not ticket or ticket["status"] == "closed":
            clear_admin_state(aid)
            bot.reply_to(message, "این تیکت بسته شده است.")
            return

        # ذخیره پاسخ ادمین در DB
        ticket_add_message(tid_val, "admin", txt, source="telegram")
        ticket_admin_replied(tid_val)

        # ارسال به کاربر
        try:
            _tg_send_to_user(
                target_uid,
                f"💬 <b>پاسخ پشتیبانی</b> (تیکت #{tid_val}):\n\n{html.escape(txt)}"
            )
        except Exception:
            pass

        bot.reply_to(message, "✅ پاسخ ارسال شد.")
        return

    if mode == "ticket_reply":  # backward compat
        clear_admin_state(aid)
        bot.reply_to(message, "لطفاً از پنل یا دستور /ticket پاسخ دهید.")
        return

    if mode == "ui_edit":
        k = state.get("ui_key")
        if not k:
            admin_states.pop(aid, None)
            bot.reply_to(message, "خطا در وضعیت. دوباره از تنظیمات اقدام کنید.")
            return
        txt = (message.text or "").strip()
        if not txt:
            bot.reply_to(message, "متن خالی قابل ذخیره نیست. دوباره ارسال کنید:")
            return
        if txt == "/reset":
            try:
                delete_ui_text(k)
                ui_cache_clear()
            except Exception:
                pass
            admin_states.pop(aid, None)
            bot.reply_to(message, f"✅ بازنشانی شد: {t(k, DEFAULT_UI_TEXTS.get(k, k))}")
            return
        try:
            set_ui_text(k, txt)
            ui_cache_clear()
        except Exception as e:
            bot.reply_to(message, f"خطا در ذخیره: {e}")
            return
        admin_states.pop(aid, None)
        bot.reply_to(message, f"✅ ذخیره شد: {t(k, DEFAULT_UI_TEXTS.get(k, k))}")
        return

    if mode == "product_chat_text":
        pid = int(state.get("product_id") or 0)
        txt = (message.text or "").strip()
        if not pid:
            admin_states.pop(aid, None)
            bot.reply_to(message, "خطا در وضعیت. دوباره از پنل محصول اقدام کنید.")
            return
        if not txt:
            bot.reply_to(message, "متن خالی قابل ذخیره نیست. دوباره ارسال کنید:")
            return
        if txt == "/reset":
            _set_product_chat_text(pid, "")
            admin_states.pop(aid, None)
            bot.reply_to(message, "✅ متن چت این محصول پاک شد.")
            try:
                product = get_product_by_id(pid)
                if product:
                    send_admin_product_detail(message, product)
            except Exception:
                pass
            return
        _set_product_chat_text(pid, txt)
        admin_states.pop(aid, None)
        bot.reply_to(message, "✅ متن چت این محصول ذخیره شد.")
        try:
            product = get_product_by_id(pid)
            if product:
                send_admin_product_detail(message, product)
        except Exception:
            pass
        return

    if mode == "partner_search":
        q = (message.text or "").strip()
        if not q:
            bot.reply_to(message, "عبارت جستجو معتبر نیست. دوباره ارسال کنید:")
            return
        admin_states.pop(aid, None)
        send_partner_list(message.chat.id, status=None, query=q)
        return

    if mode == "partner_edit_city":
        new_city = (message.text or "").strip()
        if not new_city:
            bot.reply_to(message, "شهر معتبر نیست. دوباره ارسال کنید (یا - برای عدم تغییر):")
            return
        if new_city in ("-", "—", "_", "ـ"):
            new_city = ""
        state["new_city"] = new_city
        state["mode"] = "partner_edit_shop"
        bot.reply_to(message, "✏️ نام فروشگاه/پیج جدید را وارد کنید (برای عدم تغییر: - ):")
        return

    if mode == "partner_edit_shop":
        new_shop = (message.text or "").strip()
        if not new_shop:
            bot.reply_to(message, "نام فروشگاه معتبر نیست. دوباره ارسال کنید (یا - برای عدم تغییر):")
            return
        if new_shop in ("-", "—", "_", "ـ"):
            new_shop = ""
        target_uid = int(state.get("target_user_id") or 0)
        if not target_uid:
            admin_states.pop(aid, None)
            bot.reply_to(message, "هدف ویرایش نامعتبر است.")
            return
        new_city = state.get("new_city", "")
        admin_states.pop(aid, None)

        update_partner_city_shop(target_uid, city=new_city, shop_name=new_shop)
        bot.send_message(message.chat.id, "✅ اطلاعات همکار بروزرسانی شد.")
        return

    if mode == "wallet_credit_user_id":
        target = safe_int(message.text)
        if not target:
            bot.reply_to(message, "آیدی کاربر باید فقط عدد باشد. دوباره ارسال کنید.")
            return
        admin_states[aid] = {"mode": "wallet_credit_amount", "target_user_id": target}
        bot.reply_to(message, "مبلغ شارژ (تومان) را ارسال کنید:")
        return

    if mode == "wallet_credit_amount":
        amount = safe_int(message.text.replace(",", ""))
        if not amount or amount <= 0:
            bot.reply_to(message, "مبلغ نامعتبر است. فقط عدد مثبت ارسال کنید.")
            return
        target_id = state["target_user_id"]
        new_balance = add_wallet_balance(target_id, amount)
        clear_admin_state(aid)
        bot.reply_to(
            message,
            f"کیف پول کاربر {target_id} به مقدار {amount:,} تومان شارژ شد.\n"
            f"موجودی جدید: {new_balance:,} تومان",
        )
        try:
            bot.send_message(
                target_id,
                f"کیف پول شما توسط ادمین به مقدار <b>{amount:,}</b> تومان شارژ شد.\n"
                f"موجودی فعلی: <b>{new_balance:,}</b> تومان",
            )
        except Exception:
            logger.info("could not notify target user about manual credit")
        return

    if mode == "wallet_debit_user_id":
        target = safe_int(message.text)
        if not target:
            bot.reply_to(message, "آیدی کاربر باید فقط عدد باشد. دوباره ارسال کنید.")
            return
        admin_states[aid] = {"mode": "wallet_debit_amount", "target_user_id": target}
        bot.reply_to(message, "مبلغ کسر (تومان) را ارسال کنید:")
        return

    if mode == "wallet_debit_amount":
        amount = safe_int(message.text.replace(",", ""))
        if not amount or amount <= 0:
            bot.reply_to(message, "مبلغ نامعتبر است. فقط عدد مثبت ارسال کنید.")
            return
        target_id = state["target_user_id"]
        ok = subtract_wallet_balance(target_id, amount)
        if not ok:
            current_balance = get_wallet_balance(target_id)
            bot.reply_to(
                message,
                f"موجودی کاربر برای کسر این مبلغ کافی نیست.\n"
                f"موجودی فعلی: {current_balance:,} تومان",
            )
            return
        new_balance = get_wallet_balance(target_id)
        clear_admin_state(aid)
        bot.reply_to(
            message,
            f"از کیف پول کاربر {target_id} مقدار {amount:,} تومان کسر شد.\n"
            f"موجودی جدید: {new_balance:,} تومان",
        )
        try:
            bot.send_message(
                target_id,
                f"از کیف پول شما توسط ادمین مقدار <b>{amount:,}</b> تومان کسر شد.\n"
                f"موجودی فعلی: <b>{new_balance:,}</b> تومان",
            )
        except Exception:
            logger.info("could not notify target user about manual debit")
        return

    if mode == "wallet_set_user_id":
        target = safe_int(message.text)
        if not target:
            bot.reply_to(message, "آیدی کاربر باید فقط عدد باشد. دوباره ارسال کنید.")
            return
        admin_states[aid] = {"mode": "wallet_set_amount", "target_user_id": target}
        bot.reply_to(message, "موجودی نهایی (تومان) را ارسال کنید:")
        return

    if mode == "wallet_set_amount":
        new_balance_val = safe_int(message.text.replace(",", ""))
        if new_balance_val is None or new_balance_val < 0:
            bot.reply_to(message, "موجودی نامعتبر است. فقط عدد ۰ یا مثبت ارسال کنید.")
            return
        target_id = state["target_user_id"]
        final_balance = set_wallet_balance(target_id, new_balance_val)
        clear_admin_state(aid)
        bot.reply_to(
            message,
            f"موجودی کیف پول کاربر {target_id} روی {final_balance:,} تومان تنظیم شد.",
        )
        try:
            bot.send_message(
                target_id,
                f"موجودی کیف پول شما توسط ادمین روی <b>{final_balance:,}</b> تومان تنظیم شد.",
            )
        except Exception:
            logger.info("could not notify target user about wallet set")
        return

    if mode == "edit_title":
        pid = state["product_id"]
        update_product_field(pid, "title", message.text.strip())
        clear_admin_state(aid)
        bot.reply_to(message, "عنوان محصول به‌روزرسانی شد.")
        return

    if mode == "edit_price":
        pid = state["product_id"]
        amount = safe_int(message.text.replace(",", ""))
        if not amount or amount <= 0:
            bot.reply_to(message, "قیمت نامعتبر است. فقط عدد مثبت ارسال کنید.")
            return
        update_product_field(pid, "price", amount)
        clear_admin_state(aid)
        bot.reply_to(message, "قیمت محصول به‌روزرسانی شد.")
        return

    if mode == "edit_partner_price":
        pid = int(state.get("product_id") or 0)
        amount = safe_int((message.text or "").replace(",", "").strip())

        if amount is None:
            bot.reply_to(message, "عدد ارسال کنید. برای قیمت عادی، 0 بفرستید.")
            return
        if amount < 0:
            bot.reply_to(message, "عدد منفی مجاز نیست. برای قیمت عادی، 0 بفرستید.")
            return

        update_product_field(pid, "partner_price", None if amount == 0 else int(amount))
        clear_admin_state(aid)
        bot.reply_to(message, "✅ قیمت همکار به‌روزرسانی شد.")

        product = get_product_by_id(pid)
        if product:
            send_admin_product_detail(message, product)
        return

    if mode in ("edit_limit_c", "edit_limit_p"):
        raw = (message.text or "").replace(",", "").strip()
        lim = safe_int(raw)
        if lim is None or lim < 0:
            bot.reply_to(message, "عدد نامعتبر است. فقط عدد 0 یا مثبت ارسال کنید.")
            return

        pid = int(state.get("product_id") or 0)
        if not pid:
            clear_admin_state(aid)
            bot.reply_to(message, "محصول نامعتبر است.")
            return

        field = "daily_limit_customer" if mode == "edit_limit_c" else "daily_limit_partner"
        update_product_field(pid, field, int(lim))
        clear_admin_state(aid)
        bot.send_message(message.chat.id, "✅ حد خرید روزانه بروزرسانی شد.")

        product = get_product_by_id(pid)
        if product:
            send_admin_product_detail(message, product)
        return

    if mode == "edit_desc":
        pid = state["product_id"]
        update_product_field(pid, "description", message.text.strip())
        clear_admin_state(aid)
        bot.reply_to(message, "توضیحات محصول به‌روزرسانی شد.")
        return

    if mode == "feed_bulk":
        if message.text and message.text.strip() == "/cancel":
            clear_admin_state(aid)
            bot.reply_to(message, "لغو شد.")
            return
        pid = state["product_id"]
        raw = message.text or ""
        items = parse_feed_bulk_items(raw)
        if not items:
            bot.reply_to(message, "هیچ آیتمی دریافت نشد. هر خط یک آیتم ارسال کنید یا /cancel")
            return
        add_feed_items(pid, items)
        reset_feed_alert_notification(pid)
        dispatched_from_queue = try_dispatch_pending_for_product(pid)
        total, remaining, delivered = get_feed_stats(pid)
        clear_admin_state(aid)
        bot.reply_to(
            message,
            f"✅ {len(items)} آیتم به محصول اضافه شد.\n"
            f"📦 وضعیت فعلی: کل={total} | باقی‌مانده={remaining} | تحویل‌شده={delivered}"
            + (f"\n📤 تحویل خودکار از صف: {dispatched_from_queue}" if dispatched_from_queue else "")
        )
        return

    if mode == "feed_alert":
        if message.text and message.text.strip() == "/cancel":
            clear_admin_state(aid)
            bot.reply_to(message, "لغو شد.")
            return
        pid = state["product_id"]
        th = safe_int((message.text or "").replace(",", "").strip())
        if th is None or th < 0:
            bot.reply_to(message, "عدد نامعتبر است. یک عدد 0 یا بزرگ‌تر ارسال کنید یا /cancel")
            return
        set_feed_alert_threshold(pid, th)
        reset_feed_alert_notification(pid)
        clear_admin_state(aid)
        bot.reply_to(message, f"✅ آستانه هشدار روی {th} تنظیم شد.")
        return

    if mode == "new_other_service_title":
        title = message.text.strip()
        if not title:
            bot.reply_to(message, "عنوان نمی‌تواند خالی باشد. دوباره ارسال کنید.")
            return

        skey = _make_service_key(title)
        ok = add_other_service(skey, title, "")
        if not ok:
            bot.reply_to(message, "این سرویس قبلاً ثبت شده یا کلید تکراری است. یک عنوان دیگر ارسال کنید.")
            return

        clear_admin_state(aid)
        bot.reply_to(message, f"سرویس «{title}» اضافه شد.")
        bot.send_message(message.chat.id, "سایر محصولات (ادمین):", reply_markup=admin_other_products_menu())
        return

    if mode == "new_product_title":
        category = state["category"]
        title = message.text.strip()
        admin_states[aid] = {
            "mode": "new_product_price",
            "category": category,
            "title": title,
        }
        bot.reply_to(message, "قیمت محصول (تومان) را ارسال کنید:")
        return

    if mode == "new_product_price":
        category = state["category"]
        title = state["title"]
        amount = safe_int(message.text.replace(",", ""))
        if not amount or amount <= 0:
            bot.reply_to(message, "قیمت نامعتبر است. فقط عدد مثبت ارسال کنید.")
            return
        admin_states[aid] = {
            "mode": "new_product_partner_price",
            "category": category,
            "title": title,
            "price": amount,
        }
        bot.reply_to(message, "قیمت همکار (تومان) را ارسال کنید. برای استفاده از قیمت عادی، 0 بفرستید:")
        return

    if mode == "new_product_partner_price":
        category = state["category"]
        title = state["title"]
        price = state["price"]
        pp = safe_int(message.text.replace(",", ""))
        if pp is None:
            bot.reply_to(message, "عدد ارسال کنید. برای قیمت عادی، 0 بفرستید.")
            return
        if pp < 0:
            bot.reply_to(message, "عدد منفی مجاز نیست. برای قیمت عادی، 0 بفرستید.")
            return
        partner_price = None if pp == 0 else pp
        admin_states[aid] = {
            "mode": "new_product_desc",
            "category": category,
            "title": title,
            "price": price,
            "partner_price": partner_price,
        }
        bot.reply_to(message, "توضیحات محصول را ارسال کنید (یا خط تیره -):")
        return

    if mode == "new_product_desc":
        category = state["category"]
        title = state["title"]
        price = state["price"]
        partner_price = state.get("partner_price")
        desc = message.text.strip()
        if desc == "-":
            desc = ""
        pid = add_product(category, title, price, desc, is_active=1, partner_price=partner_price)
        clear_admin_state(aid)
        bot.reply_to(
            message,
            f"محصول جدید با شناسه #{pid} اضافه شد.\n"
            f"دسته: {category}\n"
            f"عنوان: {title}\n"
            f"قیمت: {price:,} تومان",
        )
        return

                    # ========= CALLBACKS =========
@bot.callback_query_handler(func=lambda c: bool(getattr(c, "data", None)) and c.data.startswith("admin_toggle_chat_"))
def cb_admin_toggle_chat(call: types.CallbackQuery):
    """Toggle per-product chat flag from admin product detail UI."""
    uid = call.from_user.id
    if not ensure_admin(uid):
        bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
        return
    bot.answer_callback_query(call.id)

    # ensure schema exists even if bot started before migrations ran
    try:
        ticket_ensure_schema()
    except Exception:
        pass

    pid = safe_int(call.data.replace("admin_toggle_chat_", "", 1))
    if not pid:
        bot.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
        return

    cur = _get_product_chat_enabled(int(pid))
    newv = 0 if int(cur) == 1 else 1
    _set_product_chat_enabled(int(pid), int(newv))

    # refresh admin product detail
    product = get_product_by_id(int(pid))
    if product:
        try:
            send_admin_product_detail(call.message, product, edit=True)
        except Exception:
            try:
                send_admin_product_detail(call.message, product)
            except Exception:
                pass



# ══════════════════════════════════════════════════════════════════════════════
# ─── فاز ۱: امتیازدهی ────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _send_rating_request(chat_id: int, uid: int, order_id: int, pid: int, title: str):
    """ارسال درخواست امتیازدهی ۳۰ ثانیه بعد از تحویل."""
    import threading as _th
    def _delayed():
        import time as _t; _t.sleep(30)
        try:
            from db import get_social_settings
            if not int(get_social_settings().get("rating") or 0):
                return
        except Exception:
            pass
        from db import has_rated_order
        if has_rated_order(order_id):
            return
        kb = types.InlineKeyboardMarkup(row_width=5)
        kb.add(*[types.InlineKeyboardButton(
            s, callback_data=f"rate_{order_id}_{pid}_{i}"
        ) for i, s in enumerate(["⭐️1","⭐️2","⭐️3","⭐️4","⭐️5"], 1)])
        kb.add(types.InlineKeyboardButton("بعداً", callback_data=f"rate_skip_{order_id}"))
        try:
            bot.send_message(chat_id,
                f"🌟 <b>نظر شما مهمه!</b>\n\n"
                f"از خرید «{title}» راضی بودید؟\n"
                f"یه امتیاز بدید (چند ثانیه وقت می‌بره):",
                parse_mode="HTML", reply_markup=kb)
        except Exception:
            pass
    _th.Thread(target=_delayed, daemon=True).start()


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_") and not c.data.startswith("rate_skip_"))
def cb_rating(call):
    uid = call.from_user.id
    bot.answer_callback_query(call.id)
    try:
        _, order_id, pid, rating = call.data.split("_")
        order_id = int(order_id); pid = int(pid); rating = int(rating)
    except Exception:
        return
    from db import save_rating, has_rated_order
    if has_rated_order(order_id):
        try: bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception: pass
        return
    stars = "⭐️" * rating
    # ذخیره امتیاز
    if save_rating(uid, order_id, pid, rating):
        if rating >= 4:
            # امتیاز بالا — پیام تشکر
            try:
                bot.edit_message_text(
                    f"✅ ممنون از نظر شما!\n{stars}\n\nخوشحالیم که راضی بودید 🙏",
                    call.message.chat.id, call.message.message_id, parse_mode="HTML"
                )
            except Exception: pass
        else:
            # امتیاز پایین — بپرس چرا
            user_states[uid] = {"mode": "rating_comment", "order_id": order_id, "pid": pid, "rating": rating}
            try:
                bot.edit_message_text(
                    f"{stars} ثبت شد. می‌خوایم بهتر بشیم!\n\n"
                    f"اگه مشکلی داشتید بنویسید (یا /skip بزنید):",
                    call.message.chat.id, call.message.message_id, parse_mode="HTML"
                )
            except Exception: pass


@bot.callback_query_handler(func=lambda c: c.data.startswith("rate_skip_"))
def cb_rating_skip(call):
    bot.answer_callback_query(call.id)
    try: bot.delete_message(call.message.chat.id, call.message.message_id)
    except Exception: pass


@bot.message_handler(func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "rating_comment")
def handle_rating_comment(message):
    uid = message.from_user.id
    st = user_states.pop(uid, {})
    comment = (message.text or "").strip()
    if comment and comment != "/skip":
        from db import save_rating
        # آپدیت کامنت
        try:
            import sqlite3 as _sqr
            from config import DB_PATH as _DBPR
            conn = _sqr.connect(_DBPR)
            conn.execute("UPDATE product_ratings SET comment=? WHERE order_id=?;",
                         (comment, st["order_id"]))
            conn.commit(); conn.close()
        except Exception: pass
        # اطلاع به ادمین
        try:
            bot.send_message(ADMIN_ID,
                f"⭐️ نظر جدید (امتیاز {st['rating']})\n"
                f"Product #{st['pid']}\n"
                f"کامنت: {comment}")
        except Exception: pass
    bot.reply_to(message, "✅ نظر شما ثبت شد. ممنون از بازخوردتون 🙏")


# ─── نمایش FAQ در محصول ──────────────────────────────────────────────────────

def _build_faq_text(pid: int) -> str:
    """ساخت متن FAQ برای محصول."""
    from db import get_product_faqs
    faqs = get_product_faqs(pid)
    if not faqs:
        return ""
    lines = ["\n\n❓ <b>سوالات متداول</b>"]
    for i, f in enumerate(faqs, 1):
        lines.append(f"\n<b>{i}. {f['question']}</b>\n{f['answer']}")
    return "\n".join(lines)


def _build_guarantee_text() -> str:
    """متن ضمانت بازگشت وجه."""
    return t("MSG_GUARANTEE_TEXT",
        "\n\n🛡 <b>ضمانت بازگشت وجه</b>\n"
        "در صورت هرگونه مشکل، ظرف ۲۴ ساعت وجه بازگشت داده می‌شود.")


@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call: types.CallbackQuery):
    data = call.data
    uid = call.from_user.id

    # 🚀 دیسپچ کالبک‌های رشد — هندلرهایشان بعد از این catch-all تعریف شده‌اند
    if data == "partner_promo" or data == "partner_ref_link":
        return cb_partner_ref_link(call)          # نمای ادغام‌شده لینک + ابزار تبلیغ
    if data == "wallet_crypto":
        return cb_wallet_crypto(call)
    if data.startswith("crypto_net_"):
        return cb_crypto_network(call)
    if data == "user_invite":
        return cb_user_invite(call)

    # --- toggle active/inactive for other_services ---
    if data.startswith("toggle_other_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        service_key = data.replace("toggle_other_", "")

        import sqlite3
        with sqlite3.connect(DB_PATH) as conn:
            cur = conn.cursor()
            cur.execute("""
                UPDATE other_services
                SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END
                WHERE service_key = ?
            """, (service_key,))
            conn.commit()

        bot.answer_callback_query(call.id, "وضعیت دسته تغییر کرد")
        return
    # ---------------------------------------------------
    
    # ─── TICKET v2 callbacks ──────────────────────────────────────────────
    if data == "ticket_v2_new":
        bot.answer_callback_query(call.id)
        _support_ticket_start(call.message.chat.id, uid)
        return

    if data.startswith("ticket_v2_open_"):
        # باز کردن تیکت راه‌اندازی — کاربر می‌تونه پیام بفرسته
        bot.answer_callback_query(call.id)
        try:
            tid_val = int(data.split("_")[-1])
        except ValueError:
            return
        ticket = ticket_get(tid_val)
        if not ticket:
            bot.send_message(call.message.chat.id, "❌ تیکت یافت نشد.")
            return
        if ticket["status"] == "closed":
            bot.send_message(call.message.chat.id, "این سفارش قبلاً تکمیل شده است.", reply_markup=main_menu(user_id=uid))
            return
        user_states[uid] = {"mode": "ticket_v2", "ticket_id": tid_val}
        bot.send_message(
            call.message.chat.id,
            f"💬 <b>گفتگوی راه‌اندازی #{tid_val}</b>\n\n"
            "اطلاعات مورد نیاز را ارسال کنید.\n"
            "می‌توانید متن، عکس، فایل یا اسکرین‌شات بفرستید.",
            parse_mode="HTML"
        )
        return

    if data.startswith("ticket_v2_continue_"):
        bot.answer_callback_query(call.id)
        try:
            tid_val = int(data.split("_")[-1])
        except ValueError:
            return
        ticket = ticket_get(tid_val)
        if not ticket:
            bot.send_message(call.message.chat.id, "❌ تیکت یافت نشد.")
            return
        if ticket["status"] == "closed":
            bot.send_message(call.message.chat.id,
                "این گفتگو بسته شده است.", reply_markup=main_menu(user_id=uid))
            return
        # بازگشت به حالت چت تیکت
        user_states[uid] = {"mode": "ticket_v2", "ticket_id": tid_val}
        bot.send_message(
            call.message.chat.id,
            f"💬 <b>گفتگوی #{tid_val} ادامه دارد</b>\n\nپیام خود را ارسال کنید:",
            parse_mode="HTML"
        )
        return

    if data.startswith("ticket_v2_close_"):
        bot.answer_callback_query(call.id)
        try:
            tid_val = int(data.split("_")[-1])
        except ValueError:
            return
        clear_user_state(uid)
        ticket_close(tid_val)
        bot.send_message(call.message.chat.id, "✅ مکالمه پشتیبانی پایان یافت.", reply_markup=main_menu(user_id=uid))
        return

    if data.startswith("ticket_v2_reply_"):
        # ادمین می‌خواد از تلگرام پاسخ بده
        bot.answer_callback_query(call.id)
        if not ensure_admin(uid):
            return
        parts = data.split("_")
        try:
            tid_val = int(parts[3])
            target_uid = int(parts[4])
        except (IndexError, ValueError):
            return
        admin_states[uid] = {"mode": "ticket_v2_admin_reply", "ticket_id": tid_val, "target_uid": target_uid}
        bot.send_message(
            uid,
            f"✏️ پاسخ به تیکت #{tid_val} (کاربر {target_uid}):\n\n"
            "پیام خود را ارسال کنید. برای لغو: /done",
            reply_markup=types.ForceReply(selective=True)
        )
        return

    if data.startswith("ticket_v2_admin_close_"):
        bot.answer_callback_query(call.id, "تیکت بسته شد ✅")
        if not ensure_admin(uid):
            return
        try:
            tid_val = int(data.split("_")[-1])
        except ValueError:
            return
        ticket_close(tid_val)
        ticket_row = ticket_get(tid_val)
        if ticket_row:
            try:
                _tg_send_to_user(
                    ticket_row["user_id"],
                    f"✅ تیکت #{tid_val} توسط پشتیبانی بسته شد."
                )
            except Exception:
                pass
        return

    if data == "create_support_ticket" or data.startswith("continue_support_ticket_"):
        # backward compat — هدایت به سیستم جدید
        bot.answer_callback_query(call.id)
        _support_ticket_start(call.message.chat.id, uid)
        return

    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    if data == "cancel_purchase":
        bot.answer_callback_query(call.id)
        clear_user_state(uid)
        # برگشت به لیست محصولات (نه منوی اصلی)
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        bot.send_message(call.message.chat.id,
            t("MSG_BUY_CANCELLED", "خرید لغو شد."))
        return

    # ─── ناوبری دسته‌بندی داینامیک ────────────────────────────────────────
    if data == "wallet_charge_custom":
        bot.answer_callback_query(call.id)
        user_states[uid] = {"mode": "wallet_charge_amount"}
        bot.send_message(
            call.message.chat.id,
            tf("MSG_WALLET_AMOUNT_REQUEST", min_amount=f"{MIN_TOPUP_AMOUNT:,}"),
            parse_mode="HTML"
        )
        bot.register_next_step_handler(call.message, process_wallet_charge_amount)
        return

    if data.startswith("quick_charge_"):
        bot.answer_callback_query(call.id)
        try:
            amount = int(data.replace("quick_charge_", ""))
        except ValueError:
            return
        if amount < MIN_TOPUP_AMOUNT:
            amount = MIN_TOPUP_AMOUNT
        start_wallet_charge_payment(bot, call.message, uid, amount, clear_user_state)
        return

    if data.startswith("cat_"):
        bot.answer_callback_query(call.id)
        parts = data.split("_")
        # cat_{id}
        if len(parts) == 2:
            cat_id = int(parts[1])
            _show_category(call.message.chat.id, cat_id, user_id=uid, msg_id=call.message.message_id)
            return
        # cat_{cat_id}_p_{pid}  →  نمایش جزئیات محصول
        if len(parts) == 4 and parts[2] == "p":
            cat_id = int(parts[1])
            pid = int(parts[3])
            product = get_product_by_id(pid)
            if not product:
                bot.send_message(call.message.chat.id, "محصول یافت نشد.")
                return
            # نمایش جزئیات با استفاده از تابع موجود — user_id برای قیمت همکار
            send_product_detail(call.message, product, user_id=uid, cat_id=cat_id)
            return
        return

    if data.startswith("ticket_close_"):
        # backward compat → v2
        bot.answer_callback_query(call.id)
        tid = safe_int(data.replace("ticket_close_", "", 1))
        if tid:
            ticket_close(int(tid))
            clear_user_state(uid)
        bot.send_message(call.message.chat.id, "✅ چت بسته شد.", reply_markup=main_menu(user_id=uid))
        return

    if data.startswith("ticket_admin_close_"):
        # backward compat → v2
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        tid = safe_int(data.replace("ticket_admin_close_", "", 1))
        if tid:
            t_row = ticket_get(int(tid))
            ticket_close(int(tid))
            if t_row:
                clear_user_state(int(t_row["user_id"]))
                try:
                    bot.send_message(int(t_row["user_id"]), "⛔️ چت بسته شد.", reply_markup=main_menu(user_id=message.from_user.id if hasattr(message,"from_user") else None))
                except Exception:
                    pass
        return

    if data.startswith("ticket_reply_"):
        # backward compat → v2
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        parts = data.split("_")
        tid = safe_int(parts[2]) if len(parts) >= 3 else None
        target_uid_old = safe_int(parts[3]) if len(parts) >= 4 else None
        if tid and target_uid_old:
            admin_states[uid] = {"mode": "ticket_v2_admin_reply", "ticket_id": int(tid), "target_uid": int(target_uid_old)}
            bot.send_message(uid, f"✏️ پاسخ به تیکت #{tid}: پیام بفرست. /done برای لغو.")
        return
    if data.startswith("admin_toggle_chat_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        pid = safe_int(data.replace("admin_toggle_chat_", "", 1))
        if not pid:
            bot.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
            return
        cur = _get_product_chat_enabled(int(pid))
        newv = 0 if int(cur) == 1 else 1
        _set_product_chat_enabled(int(pid), int(newv))
        # refresh product detail UI
        product = get_product_by_id(int(pid))
        if product:
            try:
                send_admin_product_detail(call.message, product, edit=True)
            except Exception:
                # fallback: send new message if edit fails
                send_admin_product_detail(call.message, product)
        bot.answer_callback_query(call.id, "✅ انجام شد")
        return

    if data.startswith("admin_set_chattext_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        pid = safe_int(data.replace("admin_set_chattext_", "", 1))
        if not pid:
            bot.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        admin_states[uid] = {"mode": "product_chat_text", "product_id": int(pid)}
        current = _get_product_chat_text(int(pid))
        hint = ("(فعلی: " + (current[:80] + ("…" if len(current)>80 else "")) + ")\n\n") if current else ""
        bot.send_message(call.message.chat.id, "✏️ متن چت این محصول را ارسال کنید.\nبرای پاک کردن: /reset\n" + hint)
        return
    if data == "wallet_charge":
        from ui_texts import t as _t, DEFAULT_UI_TEXTS as _D
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                _t("BTN_WALLET_CARD",    _D.get("BTN_WALLET_CARD",    "💳 کارت به کارت")), callback_data="wallet_card2card"
            ),
            types.InlineKeyboardButton(
                _t("BTN_WALLET_GATEWAY", _D.get("BTN_WALLET_GATEWAY", "🌐 درگاه پرداخت")), callback_data="wallet_gateway"
            ),
        )
        try:
            from db import get_crypto_settings
            if int(get_crypto_settings().get("enabled") or 0):
                kb.add(types.InlineKeyboardButton(
                    _t("BTN_WALLET_CRYPTO", _D.get("BTN_WALLET_CRYPTO", "₿ پرداخت رمزارز")),
                    callback_data="wallet_crypto"))
        except Exception:
            pass
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "لطفاً روش پرداخت را انتخاب کنید:",
            reply_markup=kb,
        )
        return

    if data == "wallet_gateway":
        bot.answer_callback_query(call.id)
        start_wallet_charge(call.message)
        return

    if data == "wallet_card2card":
        bot.answer_callback_query(call.id)
        user_states[uid] = {"mode": "card2card_receipt"}
        text_msg = (
            "برای افزایش موجودی کیف پول، مبلغ مورد نظر را به حساب زیر واریز کرده و سپس عکس رسید را در همین چت ارسال کنید:\n\n"
            "💳 شماره کارت:\n"
            "<code>6037701608004393</code>\n"
            "به نام: <b>سید فیروز ایازی</b>\n\n"
            "📍 پس از بررسی، موجودی کیف پول شما شارژ خواهد شد.\n\n"
            "⚠️ فقط عکس واضح از رسید را ارسال کنید.\n"
        )
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "❌ انصراف", callback_data="wallet_cancel_card2card"
            )
        )
        bot.send_message(call.message.chat.id, text_msg, reply_markup=kb)
        return

    if data == "wallet_cancel_card2card":
        bot.answer_callback_query(call.id, "درخواست کارت به کارت لغو شد.")
        clear_user_state(uid)
        try:
            bot.edit_message_reply_markup(
                call.message.chat.id,
                call.message.message_id,
                reply_markup=None,
            )
        except Exception:
            pass
        return

    if data.startswith("other_cat_"):
        bot.answer_callback_query(call.id)
        category = data[len("other_cat_") :]
        send_products_menu(call.message.chat.id, category, user_id=uid)
        return

    if data == "other_categories":
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "لطفا یکی از دسته‌بندی‌های زیر را انتخاب کنید:",
            reply_markup=other_products_menu(),
        )
        return

    if data.startswith("back_list_"):
        bot.answer_callback_query(call.id)
        category = data[len("back_list_") :]
        send_products_menu(call.message.chat.id, category, user_id=uid)
        return

    if data == "back_main":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, t("TXT_MAIN_MENU_TITLE","منوی اصلی"), reply_markup=main_menu(user_id=message.from_user.id if hasattr(message,"from_user") else None))
        return

    if data == "other_back":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, t("TXT_MAIN_MENU_TITLE","منوی اصلی"), reply_markup=main_menu(user_id=message.from_user.id if hasattr(message,"from_user") else None))
        return

    if data == "admin_products_back":
        data = "admin_products"

    if data == "admin_back":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "پنل مدیریت 👇", reply_markup=admin_main_inline())
        return

    if data == "admin_settings":
        bot.answer_callback_query(call.id)
        panel_url = f"https://panel.stland.ir/admin/settings"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌐 باز کردن پنل تنظیمات", url=panel_url))
        bot.send_message(call.message.chat.id, "تنظیمات به پنل وب منتقل شده است:", reply_markup=kb)
        return

    if data in ("admin_main_btn_manage", "admin_ui_main_buttons", "admin_ui_texts",
                "admin_ui_captions", "admin_backup_menu"):
        bot.answer_callback_query(call.id)
        panel_url = f"https://panel.stland.ir/admin/"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌐 باز کردن پنل مدیریت", url=panel_url))
        bot.send_message(call.message.chat.id, "این بخش به پنل وب منتقل شده:", reply_markup=kb)
        return

    if (data.startswith("admin_main_btn_toggle_") or data.startswith("admin_ui_edit_") or
            data in ("admin_export_backup", "admin_import_backup",
                     "admin_full_reset_1", "admin_full_reset_2", "admin_full_reset_do")):
        bot.answer_callback_query(call.id)
        panel_url = "https://panel.stland.ir/admin/"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌐 پنل مدیریت وب", url=panel_url))
        bot.send_message(call.message.chat.id, "این بخش از پنل وب مدیریت می‌شود:", reply_markup=kb)
        return

    if data == "admin_feed_panel":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "مدیریت محصول 👇", reply_markup=admin_feed_panel_menu())
        return

    if data == "admin_feed_panel_stats":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_feed_panel_stats(call.message.chat.id, message_id=call.message.message_id)
        return

    mcat = re.fullmatch(r"admin_feed_panel_cat_([A-Za-z0-9_-]+)_([0-9]+)_([0-9]+)", data)
    if mcat:
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        try:
            cat = str(mcat.group(1))
            mode = int(mcat.group(2))
            page = int(mcat.group(3))
        except Exception:
            bot.answer_callback_query(call.id, "فرمت نامعتبر", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_feed_panel_list(call.message.chat.id, page=page, mode=mode, message_id=call.message.message_id, category_key=cat)
        return

    m = re.fullmatch(r"admin_feed_panel_([0-9]+)_([0-9]+)", data)
    if m:
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        try:
            mode = int(m.group(1))
            page = int(m.group(2))
        except Exception:
            bot.answer_callback_query(call.id, "فرمت نامعتبر", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_feed_panel_list(call.message.chat.id, page=page, mode=mode, message_id=call.message.message_id, category_key=None)
        return

    if data.startswith("admin_feed_panel_view_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        try:
            _parts = data.split("_")
            # admin_feed_panel_view_{feed_id}_{page}_{mode}(_{category_key})?
            fid = int(_parts[4]); page = int(_parts[5]); mode = int(_parts[6])
            category_key = _parts[7] if len(_parts) > 7 else None
        except Exception:
            bot.answer_callback_query(call.id, "فرمت نامعتبر", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_feed_panel_view(call.message.chat.id, fid, page=page, mode=mode, message_id=call.message.message_id, category_key=category_key)
        return

    if data.startswith("admin_feed_panel_toggle_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        try:
            _parts = data.split("_")
            # admin_feed_panel_toggle_{feed_id}_{page}_{mode}(_{category_key})?
            fid = int(_parts[4]); page = int(_parts[5]); mode = int(_parts[6])
            category_key = _parts[7] if len(_parts) > 7 else None
        except Exception:
            bot.answer_callback_query(call.id, "فرمت نامعتبر", show_alert=True)
            return
        # toggle delivered flag only (safely)
        try:
            import sqlite3
            conn = sqlite3.connect(DB_FULL_PATH)
            try:
                cur = conn.cursor()
                cur.execute("SELECT delivered FROM product_feed WHERE id=?", (fid,))
                r = cur.fetchone()
                if not r:
                    bot.answer_callback_query(call.id, "یافت نشد", show_alert=True)
                    return
                new_val = 0 if int(r[0]) == 1 else 1

                # اگر از حالت «ارسال‌شده» به «برگشت/ارسال‌نشده» می‌رویم،
                # پیام تحویل مرتبط با همین Feed را از چت مشتری پاک کن و رکوردش را هم حذف کن.
                if int(r[0]) == 1 and int(new_val) == 0:
                    _info = _get_delivery_message(int(fid))
                    if _info:
                        _chat_id, _msg_id = _info[0], _info[1]
                        try:
                            bot.delete_message(int(_chat_id), int(_msg_id))
                        except Exception:
                            pass
                        _delete_delivery_message_record(int(fid))

                cur.execute("UPDATE product_feed SET delivered=? WHERE id=?", (new_val, fid))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            bot.answer_callback_query(call.id, "خطا در تغییر وضعیت", show_alert=True)
            return

        bot.answer_callback_query(call.id, "انجام شد ✅", show_alert=False)
        # refresh list
        send_admin_feed_panel_list(call.message.chat.id, page=page, mode=mode, message_id=call.message.message_id, category_key=None)
        return

    if data.startswith("admin_feed_panel_delete_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        try:
            _parts = data.split("_")
            # admin_feed_panel_delete_{feed_id}_{page}_{mode}(_{category_key})?
            fid = int(_parts[4]); page = int(_parts[5]); mode = int(_parts[6])
            category_key = _parts[7] if len(_parts) > 7 else None
        except Exception:
            bot.answer_callback_query(call.id, "فرمت نامعتبر", show_alert=True)
            return
        try:
            import sqlite3
            conn = sqlite3.connect(DB_FULL_PATH)
            try:
                # اگر پیام تحویل برای این محصول ذخیره شده، قبل از حذف آیتم تلاش کن آن پیام را پاک کنی
                _info = _get_delivery_message(int(fid))
                if _info:
                    try:
                        bot.delete_message(int(_info[0]), int(_info[1]))
                    except Exception:
                        pass
                    _delete_delivery_message_record(int(fid))
                conn.execute("DELETE FROM product_feed WHERE id=?", (fid,))
                conn.commit()
            finally:
                conn.close()
        except Exception:
            bot.answer_callback_query(call.id, "خطا در حذف", show_alert=True)
            return

        bot.answer_callback_query(call.id, "حذف شد 🗑", show_alert=False)
        send_admin_feed_panel_list(call.message.chat.id, page=page, mode=mode, message_id=call.message.message_id)
        return

    if data == "admin_products":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(" سایر محصولات فروشگاه 🛍", callback_data="admin_other_products"),
            types.InlineKeyboardButton(" سرویس‌های اپل آیدی 📱", callback_data="admin_products_cat_apple"),
        )
        kb.add(types.InlineKeyboardButton("⬅️ بازگشت", callback_data="admin_back"))
        safe_edit_message_text(
            "یکی از دسته‌بندی‌های محصولات را انتخاب کنید:",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb,
        )
        return

    if data == "admin_partner_requests":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "مدیریت درخواست‌های همکار 👇", reply_markup=admin_partner_requests_menu())
        return

    if data.startswith("admin_partner_list_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        suffix = data.replace("admin_partner_list_", "", 1)
        status = None
        if suffix in ("pending", "approved", "rejected"):
            status = suffix
        send_partner_list(call.message.chat.id, status=status, query=None)
        return

    if data == "admin_partner_search":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        admin_states[uid] = {"mode": "partner_search"}
        bot.send_message(call.message.chat.id, "عبارت جستجو را ارسال کنید (شماره/شهر/نام فروشگاه/نام/یوزرنیم):")
        return

    if data == "admin_other_products":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "سایر محصولات (ادمین):",
            reply_markup=admin_other_products_menu(),
        )
        return

    if data == "admin_other_add_service":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        admin_states[uid] = {"mode": "new_other_service_title"}
        bot.send_message(call.message.chat.id, "عنوان سرویس جدید را ارسال کنید:")
        return

    if data == "admin_other_delete_service":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return

        bot.answer_callback_query(call.id)

        services = list_other_services(active_only=False)
        kb = types.InlineKeyboardMarkup(row_width=1)

        has_deletable = False

        for skey, title, emoji, _is_active in services:
            # جلوگیری کامل از نمایش general در لیست حذف
            if skey == "general":
                continue

            has_deletable = True
            label = (
                f"🗑 {emoji.strip()} {title}".strip()
                if (emoji and str(emoji).strip())
                else f"🗑 {str(title).strip()}"
            )

            kb.add(
                types.InlineKeyboardButton(
                    label,
                    callback_data=f"admin_other_del_{skey}"
                )
            )

        if not has_deletable:
            kb.add(
                types.InlineKeyboardButton(
                    "هیچ زیر‌دسته‌ای برای حذف وجود ندارد",
                    callback_data="noop"
                )
            )

        kb.add(
            types.InlineKeyboardButton("🔙 بازگشت", callback_data="admin_other_back")
        )

        bot.send_message(
            call.message.chat.id,
            "کدام زیر‌دسته حذف شود؟",
            reply_markup=kb
        )
        return

    if data.startswith("admin_other_del_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return

        skey = data[len("admin_other_del_"):]

        if skey == "general":
            bot.answer_callback_query(call.id, "امکان حذف این دسته وجود ندارد", show_alert=True)
            return

        delete_other_service(skey)

        bot.answer_callback_query(call.id, "سرویس حذف شد.")
        bot.send_message(
            call.message.chat.id,
            "سایر محصولات (ادمین):",
            reply_markup=admin_other_products_menu()
        )
        return

    if data == "admin_other_back":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_categories(call.message.chat.id)
        return

    if data.startswith("admin_partner_edit_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        target_uid = safe_int(data.replace("admin_partner_edit_", "", 1))
        if not target_uid:
            bot.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        admin_states[uid] = {"mode": "partner_edit_city", "target_user_id": int(target_uid)}
        bot.send_message(call.message.chat.id, "✏️ شهر جدید را وارد کنید (برای عدم تغییر: - )")
        return

    if data.startswith("admin_partner_approve_") or data.startswith("admin_partner_reject_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        parts = data.split("_")
        action = parts[2] if len(parts) >= 3 else ""
        target_uid = safe_int(parts[-1])
        if not target_uid:
            bot.answer_callback_query(call.id, "داده نامعتبر", show_alert=True)
            return
        if action == "approve":
            ok = approve_partner(target_uid)
            bot.answer_callback_query(call.id, "تایید شد" if ok else "یافت نشد", show_alert=True)
            if ok:
                try:
                    # فقط keyboard رو آپدیت کن — دکمه همکاری تبدیل به پنل همکار
                    new_kb = main_menu(user_id=target_uid)
                    bot.send_message(
                        target_uid,
                        t("MSG_PARTNER_APPROVED",
                          "✅ تبریک! درخواست همکاری شما تأیید شد.\n"
                          "قیمت ویژه همکار برای شما فعال است."),
                        reply_markup=new_kb
                    )
                except Exception:
                    pass
        else:
            ok = reject_partner(target_uid)
            bot.answer_callback_query(call.id, "رد شد" if ok else "یافت نشد", show_alert=True)
            if ok:
                try:
                    bot.send_message(target_uid, "❌ درخواست نمایندگی شما رد شد.")
                except Exception:
                    pass
        try:
            bot.edit_message_reply_markup(call.message.chat.id, call.message.message_id, reply_markup=None)
        except Exception:
            pass
        return


    if data.startswith("admin_other_toggle_"):
        if not ensure_admin(uid):
            return

        skey = data.replace("admin_other_toggle_", "")

        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                "SELECT is_active FROM other_services WHERE service_key=?",
                (skey,)
            ).fetchone()

            if row:
                new_status = 0 if int(row[0]) == 1 else 1
                conn.execute(
                    "UPDATE other_services SET is_active=? WHERE service_key=?",
                    (new_status, skey)
                )
                conn.commit()
        finally:
            conn.close()

        bot.answer_callback_query(call.id, "وضعیت تغییر کرد")
        bot.send_message(call.message.chat.id, "سایر محصولات (ادمین):", reply_markup=admin_other_products_menu())
        return


    if data.startswith("admin_products_cat_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        cat_key = data.split("_")[-1]
        if cat_key == "apple":
            category = "apple"
        else:
            keys = {row[0] for row in list_other_services(active_only=True)}
            if cat_key not in keys:
                bot.answer_callback_query(call.id, "دسته‌بندی نامعتبر است.", show_alert=True)
                return
            category = cat_key

        bot.answer_callback_query(call.id)

        products = get_products_by_category(category)
        kb = types.InlineKeyboardMarkup(row_width=2)
        if products:
            for p in products:
                pid, _, title, price, _desc, is_active, _partner_price = p
                status_icon = "✅" if is_active else "❌"
                label = f"{status_icon} {title} | {price:,} تومان"
                kb.add(types.InlineKeyboardButton(label, callback_data=f"admin_product_{pid}"))
            kb.add(types.InlineKeyboardButton("➕ افزودن محصول جدید", callback_data=f"admin_new_product_{category}"))
            kb.add(types.InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="admin_products"))
            text_msg = f"🧾 مدیریت محصولات دسته: {category}\n\nبرای مدیریت، روی هر محصول بزنید."
        else:
            kb.add(types.InlineKeyboardButton("➕ افزودن محصول جدید", callback_data=f"admin_new_product_{category}"))
            kb.add(types.InlineKeyboardButton("🔙 بازگشت به دسته‌ها", callback_data="admin_products"))
            text_msg = f"🧾 مدیریت محصولات دسته: {category}\n\nمحصولی برای این دسته ثبت نشده است."

        safe_edit_message_text(
            text_msg,
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            reply_markup=kb,
        )
        return

    if data.startswith("admin_back_cat_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        category = data.split("_")[-1]
        bot.answer_callback_query(call.id)
        send_products_menu(call.message.chat.id, category, admin_view=True)
        return

    if data.startswith("admin_product_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        send_admin_product_detail(call.message, product)
        return

    if data.startswith("admin_feed_list_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        try:
            _parts = data.split("_")
            pid = safe_int(_parts[3])
            page = safe_int(_parts[4]) or 0
            mode = safe_int(_parts[5]) or 0
        except Exception:
            pid, page, mode = None, 0, 0

        bot.answer_callback_query(call.id)
        send_admin_feed_list(
            chat_id=call.message.chat.id,
            product_id=pid,
            page=page,
            mode=mode,
            message_id=call.message.message_id,
        )
        return

    if data.startswith("admin_feed_view_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        _p = data.split("_")
        feed_id = safe_int(_p[3])
        pid = safe_int(_p[4])
        page = safe_int(_p[5]) or 0
        mode = safe_int(_p[6]) or 0
        bot.answer_callback_query(call.id)
        row = list_feed_items(pid, None, limit=1, offset=0)
        try:
            import sqlite3
            _conn = sqlite3.connect(DB_FULL_PATH)
            try:
                _r = _conn.execute(
                    "SELECT id, data, delivered, created_at FROM product_feed WHERE id=? AND product_id=?;",
                    (int(feed_id), int(pid)),
                ).fetchone()
            finally:
                _conn.close()
        except Exception:
            _r = None
        if not _r:
            bot.send_message(call.message.chat.id, "آیتم مورد نظر پیدا نشد.")
            return
        _id, _data, _del, _created = _r
        status = "✅ تحویل‌شده" if int(_del) == 1 else "📦 تحویل‌نشده"
        _oid = None
        _info = _get_delivery_message(int(_id))
        if _info:
            _oid = _info[2]
        txt = (
            f"📄 آیتم محصول (Feed ID) #{_id}\n"
            f"محصول (Product ID) #{pid}\n"
        )
        if _oid is not None:
            txt += f"Order ID: #{_display_order_no(_oid)}\n"
        txt += (
            f"وضعیت: {status}\n"
            f"تاریخ ثبت: {_created}\n\n"
            f"<code>{html.escape(_data)}</code>"
        )
        kb = types.InlineKeyboardMarkup(row_width=2)
        if int(_del) == 0:
            kb.add(types.InlineKeyboardButton("✅ علامت تحویل", callback_data=f"admin_feed_toggle_{_id}_{pid}_{page}_{mode}"))
        else:
            kb.add(types.InlineKeyboardButton("♻️ برگشت به تحویل‌نشده", callback_data=f"admin_feed_toggle_{_id}_{pid}_{page}_{mode}"))
        kb.add(types.InlineKeyboardButton("🗑 حذف آیتم", callback_data=f"admin_feed_delete_{_id}_{pid}_{page}_{mode}"))
        kb.add(types.InlineKeyboardButton("⬅️ بازگشت به لیست", callback_data=f"admin_feed_list_{pid}_{page}_{mode}"))
        bot.send_message(call.message.chat.id, txt, reply_markup=kb, parse_mode="HTML")
        return

    if data.startswith("admin_feed_toggle_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        _p = data.split("_")
        feed_id = safe_int(_p[3])
        pid = safe_int(_p[4])
        page = safe_int(_p[5]) or 0
        mode = safe_int(_p[6]) or 0
        try:
            import sqlite3
            _conn = sqlite3.connect(DB_FULL_PATH)
            try:
                _r = _conn.execute("SELECT delivered FROM product_feed WHERE id=? AND product_id=?;", (int(feed_id), int(pid))).fetchone()
            finally:
                _conn.close()
            cur_del = int(_r[0]) if _r else 0
        except Exception:
            cur_del = 0
        new_del = 0 if cur_del == 1 else 1
        # اگر از حالت تحویل‌شده به برگشت (تحویل‌نشده) می‌رویم، پیام تحویل را از چت مشتری پاک کن.
        if int(cur_del) == 1 and int(new_del) == 0 and feed_id is not None:
            _info = _get_delivery_message(int(feed_id))
            if _info:
                _chat_id, _msg_id = _info[0], _info[1]
                try:
                    bot.delete_message(int(_chat_id), int(_msg_id))
                except Exception:
                    pass
            _delete_delivery_message_record(int(feed_id))
        set_feed_item_delivered(feed_id, new_del)
        bot.answer_callback_query(call.id, "انجام شد.")
        send_admin_feed_list(
            chat_id=call.message.chat.id,
            product_id=pid,
            page=page,
            mode=mode,
            message_id=call.message.message_id,
        )
        return

    if data.startswith("admin_feed_delete_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        _p = data.split("_")
        feed_id = safe_int(_p[3])
        pid = safe_int(_p[4])
        page = safe_int(_p[5]) or 0
        mode = safe_int(_p[6]) or 0
        delete_feed_item(feed_id)
        bot.answer_callback_query(call.id, "حذف شد.")
        send_admin_feed_list(
            chat_id=call.message.chat.id,
            product_id=pid,
            page=page,
            mode=mode,
            message_id=call.message.message_id,
        )
        return

    if data.startswith("admin_feed_bulk_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "feed_bulk", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            """📦 ارسال موجودی به صورت چندخطی:

    ✅ استاندارد جدید: هر آیتم می‌تواند چندخطی باشد.
    برای جدا کردن آیتم‌ها، یک خط فقط شامل 3 ستاره یا بیشتر بفرستید (*** یا **** و ...).
    اگر ستاره‌ها را نفرستید، حالت قدیمی فعال است: هر خط = یک آیتم.
    برای لغو: /cancel

    نمونه چندخطی:
    <code>Apple Id

    email: testone.com
    pass: 23884890HAd
    date: 1983/02/12

    در حفظ اپل آیدی کوشا باشید

    ***
    Apple Id 2

    email: testone2.com
    pass: 23884890HAd
    date: 1983/02/12

    در حفظ اپل آیدی کوشا باشید</code>""",
            parse_mode="HTML",
        )
        return

    if data.startswith("admin_feed_alert_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "feed_alert", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "⚠️ آستانه هشدار موجودی را ارسال کنید (فقط عدد).\n"
            "مثلاً 5 یعنی وقتی باقی‌مانده ≤ 5 شد به ادمین هشدار بده.\n"
            "برای لغو: /cancel",
        )
        return

    if data.startswith("admin_edit_title_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "edit_title", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "عنوان جدید محصول را ارسال کنید:")
        return

    if data.startswith("admin_edit_price_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "edit_price", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "قیمت جدید (فقط عدد) را ارسال کنید:"
        )
        return

    if data.startswith("admin_set_limit_c_") or data.startswith("admin_set_limit_p_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        is_c = data.startswith("admin_set_limit_c_")
        pid = int(data.split("_")[-1])
        admin_states[uid] = {"mode": ("edit_limit_c" if is_c else "edit_limit_p"), "product_id": pid}
        bot.send_message(call.message.chat.id, "عدد حد خرید روزانه را ارسال کنید (0 یعنی نامحدود):")
        return

    if data.startswith("admin_edit_partner_price_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "edit_partner_price", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "قیمت همکار جدید (فقط عدد) را ارسال کنید. برای استفاده از قیمت عادی، 0 بفرستید:",
        )
        return

    if data.startswith("admin_edit_desc_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        admin_states[uid] = {"mode": "edit_desc", "product_id": pid}
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, "توضیحات جدید محصول را ارسال کنید:")
        return

    if data.startswith("admin_toggle_active_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
            return
        toggle_product_active(pid)
        bot.answer_callback_query(call.id, "وضعیت محصول به‌روزرسانی شد.")
        product = get_product_by_id(pid)
        send_admin_product_detail(call.message, product)
        return

    if data.startswith("admin_delete_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        pid = safe_int(data.split("_")[-1])
        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
            return

        category = product[1]
        delete_product(pid)

        bot.answer_callback_query(call.id, "محصول به‌صورت کامل حذف شد.")
        safe_edit_message_text(
            f"مدیریت محصولات دسته: {category}",
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
        )
        send_products_menu(call.message.chat.id, category, admin_view=True)
        return

    if data.startswith("admin_new_product_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        category = data.split("_")[-1]
        admin_states[uid] = {"mode": "new_product_title", "category": category}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            f"عنوان محصول جدید برای دستهٔ {category} را ارسال کنید:",
        )
        return

    if data == "admin_wallet":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "➕ شارژ کیف پول کاربر", callback_data="admin_wallet_credit"
            ),
        )
        kb.add(
            types.InlineKeyboardButton(
                "➖ کاهش کیف پول کاربر", callback_data="admin_wallet_debit"
            ),
        )
        kb.add(
            types.InlineKeyboardButton(
                "✏️ تنظیم مستقیم موجودی", callback_data="admin_wallet_set"
            ),
        )
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id,
            "یکی از عملیات کیف پول را انتخاب کنید:",
            reply_markup=kb,
        )
        return

    if data == "admin_wallet_credit":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        admin_states[uid] = {"mode": "wallet_credit_user_id"}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "آیدی عددی کاربر برای شارژ کیف پول را ارسال کنید:"
        )
        return

    if data == "admin_wallet_debit":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        admin_states[uid] = {"mode": "wallet_debit_user_id"}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "آیدی عددی کاربر برای کاهش موجودی را ارسال کنید:"
        )
        return

    if data == "admin_wallet_set":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        admin_states[uid] = {"mode": "wallet_set_user_id"}
        bot.answer_callback_query(call.id)
        bot.send_message(
            call.message.chat.id, "آیدی عددی کاربر برای تنظیم موجودی را ارسال کنید:"
        )
        return

    if data == "admin_stats":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        stats = get_stats()
        total_wallets, total_balance, total_orders, total_sales, active_products = stats
        text = (
            "📊 آمار کلی ربات:\n\n"
            f"تعداد کیف پول‌ها: <b>{total_wallets}</b>\n"
            f"مجموع موجودی کیف پول‌ها: <b>{total_balance:,}</b> تومان\n\n"
            f"تعداد سفارش‌ها: <b>{total_orders}</b>\n"
            f"مجموع فروش: <b>{total_sales:,}</b> تومان\n\n"
            f"تعداد محصولات فعال: <b>{active_products}</b>\n"
        )
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text)
        return

    if data == "admin_payments":
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id)
            return
        orders = get_recent_orders_global(limit=15)
        if not orders:
            text = t("MSG_NO_ORDERS")
        else:
            lines = []
            for o in orders:
                oid, user_id, title, amount, created_at = o
                date_str = created_at.split("T")[0] if created_at else ""
                lines.append(
                    f"#{oid} | کاربر {user_id} | {title} | {amount:,} تومان | {date_str}"
                )
            text = "\n".join(lines)
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, text)
        return

    if "_select_" in data:
        _, _, pid_str = data.partition("_select_")
        pid = safe_int(pid_str)
        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد", show_alert=True)
            return
        category = product[1]
        send_product_detail(
            call.message.chat.id,
            product,
            category,
            user_id=uid,
            message=call.message
        )
        bot.answer_callback_query(call.id)
        return
        
# ===== بررسی ادامه خرید بعد از شارژ =====
        import sqlite3

        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()

        cur.execute("""
            SELECT id FROM pending_product_resumes
            WHERE user_id=?
            ORDER BY id DESC
            LIMIT 1
        """, (uid,))

        resume_row = cur.fetchone()

        if resume_row and not data.startswith("confirm_"):
           # حذف رکورد
            cur.execute("DELETE FROM pending_product_resumes WHERE id=?", (resume_row["id"],))
            conn.commit()
            conn.close()

          # اجرای confirm خودکار
            data = f"confirm_{state_category}_{state_pid}"
        else:
            conn.close()
            

    # ===== confirm_full =====
    if data.startswith("confirm_full_"):

        parts = data.split("_")
        if len(parts) < 3:
            bot.answer_callback_query(call.id, "داده نامعتبر است", show_alert=True)
            return

        pid = safe_int(parts[-1])
        category = "_".join(parts[2:-1])

        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد")
            return

        price = product[3]

        start_product_payment(
            bot,
            call.message,
            uid,
            price,
            reserved_wallet_amount=0,
            product_id=pid
        )

        bot.answer_callback_query(call.id)
        return



            # ===== confirm_wallet =====
    if data.startswith("confirm_wallet_"):

        parts = data.split("_")
        pid = safe_int(parts[-1])
        category = "_".join(parts[2:-1])

        product = get_product_by_id(pid)
        if not product:
            bot.answer_callback_query(call.id, "محصول یافت نشد")
            return

        partner_price = product[6] if len(product) > 6 else None
        eff_price = partner_price if (is_partner_approved(uid) and partner_price) else product[3]
        from db import apply_flash_price as _afp
        eff_price, _ = _afp(int(product[0]), int(eff_price))

        wallet_balance = get_wallet_balance(uid)

        if wallet_balance <= 0:
            bot.answer_callback_query(call.id, "موجودی کیف پول صفر است")
            return

        use_wallet = min(wallet_balance, eff_price)

        ok = subtract_wallet_balance(uid, use_wallet)
        if not ok:
            bot.answer_callback_query(call.id, "خطا در برداشت", show_alert=True)
            return

        finalize_product_order(call, uid, product, category, eff_price, wallet_used=use_wallet)

        bot.answer_callback_query(call.id)
        return

        bot.reply_to(
            message,
            "رسید شما ثبت شد ✅\n"
            "پس از تأیید توسط پشتیبانی، کیف پول شما شارژ خواهد شد.",
        )


@bot.message_handler(
    func=lambda m: user_states.get(m.from_user.id, {}).get("mode") == "card2card_receipt",
    content_types=["photo"]
)
def handle_card2card_photo(message):
    uid = message.from_user.id
    st  = user_states.pop(uid, {})
    amount  = int(st.get("amount", 0))
    file_id = message.photo[-1].file_id

    from db import save_card_receipt, ensure_card_receipts_schema
    ensure_card_receipts_schema()
    rid = save_card_receipt(uid, amount, file_id)

    bot.reply_to(message,
        f"رسید شما ثبت شد ✅\n"
        f"شناسه پیگیری: <code>#{rid}</code>\n\n"
        "پس از تأیید توسط پشتیبانی، کیف پول شما شارژ خواهد شد.",
        parse_mode="HTML")
    try:
        import html as _h
        from db import get_user as _gu
        user = _gu(uid)
        name = _h.escape((user["full_name"] if user else None) or str(uid))
        bot.send_photo(ADMIN_ID, file_id,
            caption=(f"💳 <b>رسید کارت‌به‌کارت جدید</b>\n"
                     f"شناسه: #{rid}\n"
                     f"کاربر: {name} (<code>{uid}</code>)\n\n"
                     f"⚠️ مبلغ هنگام تأیید در پنل وارد شود.\n"
                     f"پنل: /admin/receipts/{rid}/view\n"
                     f"تأیید: /approve_receipt_{rid}\n"
                     f"رد: /reject_receipt_{rid}"),
            parse_mode="HTML")
    except Exception:
        pass


@bot.message_handler(func=lambda m: ensure_admin(m.from_user.id) and
                     (m.text or "").startswith("/approve_receipt_"))
def handle_approve_receipt(message):
    rid = int((message.text or "").replace("/approve_receipt_", "").strip())
    from db import update_card_receipt, get_card_receipts
    from db import get_wallet_balance, add_wallet_balance
    receipts = [r for r in get_card_receipts("pending") if r["id"] == rid]
    if not receipts:
        bot.reply_to(message, "رسید یافت نشد یا قبلاً بررسی شده."); return
    r = receipts[0]
    update_card_receipt(rid, "approved", "تأیید توسط ادمین")
    add_wallet_balance(r["user_id"], r["amount"])
    bot.reply_to(message, f"✅ رسید #{rid} تأیید شد. {r['amount']:,} تومان به کیف پول افزوده شد.")
    try:
        bot.send_message(r["user_id"],
            f"✅ پرداخت شما تأیید شد!\n"
            f"مبلغ <b>{r['amount']:,}</b> تومان به کیف پول شما اضافه شد.",
            parse_mode="HTML")
    except Exception: pass


@bot.message_handler(func=lambda m: ensure_admin(m.from_user.id) and
                     (m.text or "").startswith("/reject_receipt_"))
def handle_reject_receipt(message):
    rid = int((message.text or "").replace("/reject_receipt_", "").strip())
    from db import update_card_receipt, get_card_receipts
    receipts = [r for r in get_card_receipts("pending") if r["id"] == rid]
    if not receipts:
        bot.reply_to(message, "رسید یافت نشد یا قبلاً بررسی شده."); return
    r = receipts[0]
    update_card_receipt(rid, "rejected", "رد توسط ادمین")
    bot.reply_to(message, f"❌ رسید #{rid} رد شد.")
    try:
        bot.send_message(r["user_id"],
            "❌ متأسفانه رسید پرداخت شما تأیید نشد.\n"
            "لطفاً با پشتیبانی تماس بگیرید.")
    except Exception: pass


# ========= MAIN =========




@bot.message_handler(content_types=["document"])
def handle_admin_backup_restore_document(message):
    uid = message.from_user.id
    if not ensure_admin(uid):
        return
    st = admin_states.get(uid) or {}
    if st.get("mode") != "await_backup_upload":
        return

    try:
        file_id = message.document.file_id
        file_info = bot.get_file(file_id)
        downloaded = bot.download_file(file_info.file_path)

        _ensure_backup_dir()
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        tmp_path = os.path.join(BACKUP_DIR, f"upload_{uid}_{ts}.sqlite")
        with open(tmp_path, "wb") as f:
            f.write(downloaded)

        ok, msg = validate_backup_db(tmp_path)
        if not ok:
            bot.send_message(message.chat.id, f"فایل بکاپ معتبر نیست: {msg}")
            try: os.remove(tmp_path)
            except: pass
            admin_states.pop(uid, None)
            return

        old_bak = restore_db_from_backup(tmp_path)
        admin_states.pop(uid, None)

        bot.send_message(
            message.chat.id,
            f"بازیابی انجام شد ✅\nنسخه قبلی ذخیره شد: {old_bak}\nربات برای اعمال تغییرات ریستارت می‌شود."
        )

        # Exit so systemd restarts cleanly.
        os._exit(0)

    except Exception as e:
        admin_states.pop(uid, None)
        bot.send_message(message.chat.id, f"خطا در بازیابی بکاپ: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# ─── ₿ شارژ رمزارز + 📣 کیت تبلیغاتی همکار ──────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════

def _send_invite_view(chat_id, uid):
    """🎁 دعوت دوستان — برای همه کاربران: لینک + پاداش + متن آماده + اشتراک."""
    from db import get_referral_settings, get_referral_stats_for, get_promo_settings
    settings = get_referral_settings()
    try:
        stats = get_referral_stats_for(uid)
    except Exception:
        stats = {"total": 0, "total_reward": 0}
    bot_username = _bot_username() or "your_bot"
    link = f"https://t.me/{bot_username}?start=ref_{uid}"
    reward = int(settings.get("reward_amount") or 0)
    promo = str(get_promo_settings().get("text") or "").format(link=link)

    text = (
        "🎁 <b>دعوت دوستان</b>\n\n"
        f"لینک اختصاصی شما:\n<code>{link}</code>\n\n"
    )
    if settings.get("is_active") and reward > 0:
        text += f"💰 با هر عضویت: <b>{reward:,}</b> تومان پاداش\n"
    text += (
        "💸 + پورسانت از هر خرید دعوت‌شده‌ها\n\n"
        f"📊 دعوت‌های شما: <b>{stats['total']}</b> نفر"
        + (f" | پاداش: <b>{stats['total_reward']:,}</b> ت" if stats.get("total_reward") else "")
        + "\n\n📣 متن آماده برای ارسال:\n➖➖➖➖➖➖➖➖\n"
        + promo + "\n➖➖➖➖➖➖➖➖"
    )
    import urllib.parse as _up
    share_url = "https://t.me/share/url?url=" + _up.quote(link) + "&text=" + _up.quote(promo)
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(types.InlineKeyboardButton("📤 ارسال به دوستان و گروه‌ها", url=share_url))
    bot.send_message(chat_id, text, reply_markup=kb, parse_mode="HTML")


def handle_user_invite(message):
    if not is_main_button_enabled("MAIN_BTN_INVITE"):
        bot.reply_to(message, t("MSG_BTN_DISABLED"))
        return
    _send_invite_view(message.chat.id, message.from_user.id)


def cb_user_invite(call):
    bot.answer_callback_query(call.id)
    _send_invite_view(call.message.chat.id, call.from_user.id)


@bot.callback_query_handler(func=lambda c: c.data == "wallet_crypto")
def cb_wallet_crypto(call):
    from db import get_crypto_settings
    cs = get_crypto_settings()
    if not int(cs.get("enabled") or 0):
        bot.answer_callback_query(call.id, "پرداخت رمزارز فعال نیست", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    if (cs.get("usdt_trc20") or "").strip():
        kb.add(types.InlineKeyboardButton("💵 USDT (TRC20)", callback_data="crypto_net_usdt"))
    if (cs.get("trx") or "").strip():
        kb.add(types.InlineKeyboardButton("🔺 TRX (Tron)", callback_data="crypto_net_trx"))
    bot.send_message(call.message.chat.id,
        "₿ <b>شارژ با رمزارز</b>\n\nشبکه مورد نظر را انتخاب کنید:",
        reply_markup=kb, parse_mode="HTML")


@bot.callback_query_handler(func=lambda c: c.data.startswith("crypto_net_"))
def cb_crypto_network(call):
    from db import get_crypto_settings
    cs = get_crypto_settings()
    net = call.data.replace("crypto_net_", "")
    addr = (cs.get("usdt_trc20") if net == "usdt" else cs.get("trx") or "").strip()
    if not addr:
        bot.answer_callback_query(call.id, "آدرس این شبکه تنظیم نشده", show_alert=True)
        return
    bot.answer_callback_query(call.id)
    net_label = "USDT (TRC20)" if net == "usdt" else "TRX"
    user_states[call.from_user.id] = {"mode": "crypto_amount", "net": net}
    bot.send_message(call.message.chat.id,
        f"₿ <b>پرداخت {net_label}</b>\n\n"
        f"آدرس واریز:\n<code>{addr}</code>\n\n"
        f"📌 {cs.get('note','')}\n\n"
        "حالا <b>مبلغ به تومان</b> که می‌خواهید شارژ شود را وارد کنید:",
        parse_mode="HTML")


def handle_crypto_amount(message):
    uid = message.from_user.id
    st = user_states.get(uid, {})
    raw = (message.text or "").strip().translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")).replace(",", "")
    if not raw.isdigit() or int(raw) <= 0:
        bot.reply_to(message, "❌ مبلغ نامعتبر است. یک عدد به تومان وارد کنید:")
        return
    st["amount"] = int(raw)
    st["mode"] = "crypto_txid"
    user_states[uid] = st
    bot.reply_to(message,
        f"مبلغ: <b>{int(raw):,}</b> تومان ✅\n\n"
        "حالا <b>TXID</b> (هش تراکنش) را ارسال کنید:", parse_mode="HTML")


def handle_crypto_txid(message):
    uid = message.from_user.id
    st = user_states.pop(uid, {})
    txid = (message.text or "").strip()
    if len(txid) < 10:
        user_states[uid] = st
        bot.reply_to(message, "❌ TXID معتبر نیست. دوباره ارسال کنید:")
        return
    from db import save_crypto_receipt
    rid = save_crypto_receipt(uid, int(st.get("amount", 0)), st.get("net", "usdt"), txid)
    bot.reply_to(message,
        f"✅ درخواست شارژ رمزارز ثبت شد.\n"
        f"شناسه پیگیری: <code>#{rid}</code>\n\n"
        "پس از تأیید تراکنش، کیف‌پول شما شارژ می‌شود.", parse_mode="HTML")
    try:
        import html as _h
        from db import get_user as _gu
        user = _gu(uid)
        name = _h.escape((user["full_name"] if user else None) or str(uid))
        net_label = "USDT-TRC20" if st.get("net") == "usdt" else "TRX"
        bot.send_message(ADMIN_ID,
            f"₿ <b>رسید رمزارز جدید</b>\n"
            f"شناسه: #{rid}\n"
            f"کاربر: {name} (<code>{uid}</code>)\n"
            f"مبلغ اعلامی: {int(st.get('amount',0)):,} تومان\n"
            f"شبکه: {net_label}\n"
            f"TXID: <code>{_h.escape(txid)}</code>\n\n"
            f"تأیید: /approve_receipt_{rid}\n"
            f"رد: /reject_receipt_{rid}",
            parse_mode="HTML")
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# ─── 🚀 موتور رشد: هوک بعد از خرید + زمان‌بند بازگردانی و لیدربرد ────────────
# ══════════════════════════════════════════════════════════════════════════════

def _after_purchase_extras(uid, chat_id, order_id, pid, cat_id, title):
    """پست کانال + درخواست امتیاز + پیشنهاد Upsell — با تأخیر ۲ ثانیه بعد از تحویل."""
    def _run():
        try:
            from db import get_social_settings, get_upsell_products, apply_flash_price
            soc = get_social_settings()

            # ۶ب) پست خودکار فروش در کانال (ناشناس)
            try:
                ch = str(soc.get("channel_id") or "").strip()
                if ch and int(soc.get("sale_post") or 0):
                    bot.send_message(ch, str(soc.get("sale_post_text") or "").format(title=title),
                                     parse_mode="HTML")
            except Exception:
                pass

            # ۲) پیشنهاد خرید بعدی (Upsell)
            try:
                if int(soc.get("upsell") or 0):
                    ups = get_upsell_products(pid, cat_id, limit=2)
                    if ups:
                        kb = types.InlineKeyboardMarkup(row_width=1)
                        for p in ups:
                            fp, fl = apply_flash_price(p["id"], int(p["price"]))
                            lbl = f"🔥 {p['title']} | {fp:,} تومان" if fl else f"{p['title']} | {fp:,} تومان"
                            kb.add(types.InlineKeyboardButton(
                                lbl, callback_data=f"cat_{p['category_id']}_p_{p['id']}"))
                        bot.send_message(chat_id,
                            "🛍 <b>خریداران این محصول، این‌ها را هم پسندیدند:</b>",
                            reply_markup=kb, parse_mode="HTML")
            except Exception:
                pass
        except Exception:
            pass
    try:
        threading.Timer(2.0, _run).start()
    except Exception:
        pass


def _growth_scheduler():
    """هر ۱۰ دقیقه: بازگردانی روزانه + لیدربرد هفتگی (ضدتکرار با bot_config)."""
    import datetime as _dt
    from db import (get_cfg, set_cfg, get_winback_settings, get_leaderboard_settings,
                    find_winback_candidates, create_winback_code,
                    weekly_top_partners, credit_partner_wallet, ensure_growth_schema)
    ensure_growth_schema()
    while True:
        try:
            now = _dt.datetime.now()
            today = now.strftime("%Y-%m-%d")

            # ── ۱) کمپین بازگردانی — روزی یک‌بار بعد از ساعت تنظیم‌شده ──
            wb = get_winback_settings()
            force_wb = get_cfg("winback_force", "0") == "1"
            if (int(wb.get("enabled") or 0) and now.hour >= int(wb.get("hour") or 11)
                    and get_cfg("winback_last", "") != today) or force_wb:
                if force_wb:
                    set_cfg("winback_force", "0")
                set_cfg("winback_last", today)
                cands = find_winback_candidates(
                    int(wb.get("days_inactive") or 14),
                    int(wb.get("cooldown_days") or 30),
                    int(wb.get("batch") or 30))
                sent = 0
                for c in cands:
                    try:
                        code = create_winback_code(int(c["uid"]),
                                                   int(wb.get("percent") or 15),
                                                   int(wb.get("expire_days") or 3))
                        if not code:
                            continue
                        msg = str(wb.get("message") or "").format(
                            name=(c["name"] or "دوست عزیز"), code=code,
                            percent=wb.get("percent"), days=wb.get("expire_days"))
                        bot.send_message(int(c["uid"]), msg, parse_mode="HTML")
                        sent += 1
                    except Exception:
                        continue
                if sent:
                    logger.info("winback: %s پیام بازگردانی ارسال شد", sent)

            # ── ۴) لیدربرد هفتگی — روز تنظیم‌شده، هفته‌ای یک‌بار ──
            lb = get_leaderboard_settings()
            week_key = now.strftime("%G-W%V")
            force_lb = get_cfg("leaderboard_force", "0") == "1"
            if (int(lb.get("enabled") or 0) and now.weekday() == int(lb.get("weekday") or 4)
                    and get_cfg("leaderboard_last", "") != week_key) or force_lb:
                if force_lb:
                    set_cfg("leaderboard_force", "0")
                set_cfg("leaderboard_last", week_key)
                rewards = []
                for x in str(lb.get("rewards") or "").split(","):
                    try: rewards.append(int(x.strip()))
                    except Exception: pass
                tops = weekly_top_partners(limit=max(1, len(rewards) or 3))
                medals = ["🥇", "🥈", "🥉", "🏅", "🏅"]
                for i, t in enumerate(tops):
                    try:
                        reward = rewards[i] if i < len(rewards) else 0
                        if reward > 0:
                            credit_partner_wallet(int(t["uid"]), reward,
                                                  note=f"جایزه لیدربرد هفته {week_key} — رتبه {i+1}")
                        msg = str(lb.get("message") or "").format(
                            rank=f"{medals[i]} {i+1}", count=t["cnt"], reward=f"{reward:,}")
                        bot.send_message(int(t["uid"]), msg, parse_mode="HTML")
                    except Exception:
                        continue
                if tops:
                    logger.info("leaderboard: جوایز هفته %s پرداخت شد (%s نفر)", week_key, len(tops))
        except Exception as ex:
            logger.exception("growth scheduler error: %s", ex)
        time.sleep(600)


if __name__ == "__main__":
    init_db(DB_PATH)
    ticket_ensure_schema()
    _ensure_delivery_table()
    try:
        from db import ensure_growth_schema as _egs
        _egs()
        threading.Thread(target=_growth_scheduler, daemon=True).start()
        logger.info("🚀 Growth scheduler started")
    except Exception as _gex:
        logger.exception("growth scheduler failed to start: %s", _gex)
    logger.info("Bot started (ticket system v2)...")

    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.exception("Polling crashed, restarting in 5s: %s", e)
            time.sleep(5)
