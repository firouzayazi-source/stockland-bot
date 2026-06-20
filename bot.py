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

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
set_ui_cache_clear_callback(ui_cache_clear)




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
    text = (
        f"نام سرویس: <b>{title}</b>\n"
        f"قیمت: <b>{eff_price:,}</b> تومان\n\n"
        f"{description or 'بدون توضیحات'}"
    )

    markup = types.InlineKeyboardMarkup()

    if wallet_balance >= eff_price:
        markup.add(types.InlineKeyboardButton(
            "💳 پرداخت با کیف پول",
            callback_data=f"confirm_wallet_{category}_{pid}"
        ))
    elif 0 < wallet_balance < eff_price:
        markup.add(types.InlineKeyboardButton(
            "💳 پرداخت ترکیبی (کیف پول + درگاه)",
            callback_data=f"confirm_wallet_{category}_{pid}"
        ))
        markup.add(types.InlineKeyboardButton(
            "🌐 پرداخت کامل از درگاه",
            callback_data=f"confirm_full_{category}_{pid}"
        ))
    else:
        markup.add(types.InlineKeyboardButton(
            "🌐 پرداخت از درگاه",
            callback_data=f"confirm_full_{category}_{pid}"
        ))

    markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_purchase"))
    markup.add(types.InlineKeyboardButton("🔙 بازگشت", callback_data=back_cb))

    bot.send_message(chat_id, text, reply_markup=markup, parse_mode="HTML")




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
        conn.execute(
            """
            INSERT OR REPLACE INTO pending_deliveries
                (order_id, user_id, chat_id, product_id, product_title, price, status, feed_id)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL);
            """,
            (int(order_id), int(user_id), int(chat_id), int(product_id), str(title), int(price)),
        )
        conn.commit()
        conn.close()
    except Exception:
        pass

def _mark_pending_delivered(order_id: int, feed_id: int):
    try:
        conn = _db_conn()
        conn.execute(
            "UPDATE pending_deliveries SET status='delivered', feed_id=?, delivered_at=CURRENT_TIMESTAMP WHERE order_id=?;",
            (int(feed_id), int(order_id)),
        )
        conn.commit()
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
        _conn.close()
    except Exception:
        pass



# ================== PRODUCT CHAT (TICKET) ==================
# قابلیت چت برای هر محصول (اختیاری). اگر برای محصول فعال شود، بعد از خرید/تحویل یک تیکت باز می‌شود
# و تا زمانی که کاربر یا ادمین آن را ببندند، پیام‌های کاربر به ادمین و پاسخ ادمین به کاربر ارسال می‌شود.

def _ensure_ticket_tables():
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        # products.chat_enabled
        cols = [r[1] for r in _conn.execute("PRAGMA table_info(products);").fetchall()]
        if "chat_enabled" not in cols:
            _conn.execute("ALTER TABLE products ADD COLUMN chat_enabled INTEGER DEFAULT 0;")
        # products.chat_text
        if "chat_text" not in cols:
            _conn.execute("ALTER TABLE products ADD COLUMN chat_text TEXT;")
        # tickets
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                product_id INTEGER NOT NULL,
                order_no INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'open',
                created_at TEXT NOT NULL,
                closed_at TEXT,
                closed_by TEXT
            );"""
        )
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_user_status ON tickets(user_id, status);")
        _conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_product_status ON tickets(product_id, status);")
        _conn.commit()
        _conn.close()
    except Exception:
        pass


def _get_product_chat_enabled(product_id: int) -> int:
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute("SELECT chat_enabled FROM products WHERE id=?;", (int(product_id),)).fetchone()
        _conn.close()
        return int(row[0] or 0) if row else 0
    except Exception:
        return 0


def _set_product_chat_enabled(product_id: int, enabled: int) -> None:
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute("UPDATE products SET chat_enabled=? WHERE id=?;", (int(enabled), int(product_id)))
        _conn.commit()
        _conn.close()
    except Exception:
        pass


def _get_product_chat_text(product_id: int) -> str:
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute("SELECT chat_text FROM products WHERE id=?;", (int(product_id),)).fetchone()
        _conn.close()
        return (row[0] or "").strip() if row else ""
    except Exception:
        return ""


def _set_product_chat_text(product_id: int, text_val: str | None) -> None:
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute("UPDATE products SET chat_text=? WHERE id=?;", (text_val, int(product_id)))
        _conn.commit()
        _conn.close()
    except Exception:
        pass


def _create_ticket(user_id: int, product_id: int, order_no: int) -> int | None:
    """Create a new ticket; returns ticket_id."""
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        now = datetime.utcnow().isoformat()
        _conn.execute(
            "INSERT INTO tickets(user_id, product_id, order_no, status, created_at) VALUES(?,?,?,?,?);",
            (int(user_id), int(product_id), int(order_no), "open", now),
        )
        tid = _conn.execute("SELECT last_insert_rowid();").fetchone()[0]
        _conn.commit()
        _conn.close()
        return int(tid)
    except Exception:
        return None


def _close_ticket(ticket_id: int, closed_by: str) -> None:
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        now = datetime.utcnow().isoformat()
        _conn.execute(
            "UPDATE tickets SET status='closed', closed_at=?, closed_by=? WHERE id=?;",
            (now, str(closed_by)[:32], int(ticket_id)),
        )
        _conn.commit()
        _conn.close()
    except Exception:
        pass


def _get_open_ticket_for_user(user_id: int) -> tuple[int, int, int] | None:
    """Return (ticket_id, product_id, order_no) for latest open ticket."""
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute(
            "SELECT id, product_id, order_no FROM tickets WHERE user_id=? AND status='open' ORDER BY id DESC LIMIT 1;",
            (int(user_id),),
        ).fetchone()
        _conn.close()
        if not row:
            return None
        return int(row[0]), int(row[1]), int(row[2])
    except Exception:
        return None


def _get_ticket(ticket_id: int) -> tuple[int, int, int, int, str] | None:
    """Return (id, user_id, product_id, order_no, status)."""
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute(
            "SELECT id, user_id, product_id, order_no, status FROM tickets WHERE id=?;",
            (int(ticket_id),),
        ).fetchone()
        _conn.close()
        if not row:
            return None
        return int(row[0]), int(row[1]), int(row[2]), int(row[3]), str(row[4])
    except Exception:
        return None


def _ticket_user_keyboard(ticket_id: int):
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("❌ بستن چت", callback_data=f"ticket_close_{ticket_id}"))
    return kb


def _ticket_admin_keyboard(ticket_id: int, user_id: int):
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("✉️ پاسخ", callback_data=f"ticket_reply_{ticket_id}_{user_id}"),
        types.InlineKeyboardButton("⛔️ بستن", callback_data=f"ticket_admin_close_{ticket_id}"),
    )
    return kb

def _store_delivery_message(feed_id: int, order_id: int | None, chat_id: int, message_id: int):
    _ensure_delivery_table()
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute(
            "INSERT OR REPLACE INTO delivery_messages(feed_id, order_id, chat_id, message_id, created_at) VALUES(?,?,?,?,?);",
            (int(feed_id), (int(order_id) if order_id is not None else None), int(chat_id), int(message_id), datetime.utcnow().isoformat()),
        )
        _conn.commit()
        _conn.close()
    except Exception:
        pass

def _get_delivery_message(feed_id: int):
    """Return (chat_id, message_id, order_id) or None."""
    _ensure_delivery_table()
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute(
            "SELECT chat_id, message_id, order_id FROM delivery_messages WHERE feed_id=?;",
            (int(feed_id),),
        ).fetchone()
        _conn.close()
        if not row:
            return None
        return int(row[0]), int(row[1]), (int(row[2]) if row[2] is not None else None)
    except Exception:
        return None

def _get_order_id_map(feed_ids: list[int]) -> dict[int, int]:
    """Map feed_id -> order_id for rows that have an order_id."""
    _ensure_delivery_table()
    out: dict[int, int] = {}
    try:
        if not feed_ids:
            return out
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        qmarks = ",".join(["?"] * len(feed_ids))
        rows = _conn.execute(
            f"SELECT feed_id, order_id FROM delivery_messages WHERE feed_id IN ({qmarks});",
            tuple(int(x) for x in feed_ids),
        ).fetchall()
        _conn.close()
        for fid, oid in rows or []:
            if oid is None:
                continue
            out[int(fid)] = int(oid)
    except Exception:
        pass
    return out


def _get_feed_id_by_order_id(order_id: int | None) -> int | None:
    """Return feed_id for this order_id if this order was auto-delivered from feed."""
    if order_id is None:
        return None
    _ensure_delivery_table()
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute(
            "SELECT feed_id FROM delivery_messages WHERE order_id=? LIMIT 1;",
            (int(order_id),),
        ).fetchone()
        _conn.close()
        if not row or row[0] is None:
            return None
        return int(row[0])
    except Exception:
        return None

def _delete_delivery_message_record(feed_id: int):
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute("DELETE FROM delivery_messages WHERE feed_id=?;", (int(feed_id),))
        _conn.commit()
        _conn.close()
    except Exception:
        pass



# ================== ORDER DISPLAY NUMBER (HUMAN-FRIENDLY) ==================
# هدف: شماره سفارش قابل نمایش از 1 شروع شود (حتی اگر ID داخلی دیتابیس ادامه‌دار باشد).
# نکته: order_id داخلی برای لینک‌ها/پیگیری داخلی حفظ می‌شود؛ display_no فقط برای نمایش است.
def _ensure_order_display_table():
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute(
            """CREATE TABLE IF NOT EXISTS order_display (
                order_id INTEGER PRIMARY KEY,
                display_no INTEGER UNIQUE NOT NULL,
                created_at TEXT NOT NULL
            );"""
        )

        # Backfill (once): اگر قبلاً سفارش‌ها وجود داشته ولی شمارۀ نمایشی ندارند،
        # از روی سفارش‌های موجود شمارۀ 1..n می‌سازیم. این دقیقاً مشکل ID داخلیِ ادامه‌دار (مثلاً 11) را حل می‌کند.
        cnt = _conn.execute("SELECT COUNT(*) FROM order_display;").fetchone()
        if cnt and int(cnt[0]) == 0:
            rows = _conn.execute("SELECT id, created_at FROM orders ORDER BY id ASC;").fetchall()
            dn = 1
            for oid, _created in rows or []:
                _conn.execute(
                    "INSERT OR IGNORE INTO order_display(order_id, display_no, created_at) VALUES(?,?,?);",
                    (int(oid), int(dn), (_created or datetime.utcnow().isoformat())),
                )
                dn += 1

        _conn.commit()
        _conn.close()
    except Exception:
        pass

def _allocate_order_display_no(order_id: int) -> int:
    """Allocate and persist a sequential display number (1..n) for this order_id."""
    _ensure_order_display_table()
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute("BEGIN IMMEDIATE;")
        # اگر قبلاً تخصیص داده شده
        row = _conn.execute("SELECT display_no FROM order_display WHERE order_id=?;", (int(order_id),)).fetchone()
        if row and row[0] is not None:
            dn = int(row[0])
            _conn.execute("COMMIT;")
            _conn.close()
            return dn
        # تخصیص جدید
        row2 = _conn.execute("SELECT COALESCE(MAX(display_no), 0) + 1 FROM order_display;").fetchone()
        dn = int(row2[0]) if row2 and row2[0] is not None else int(order_id)
        _conn.execute(
            "INSERT INTO order_display(order_id, display_no, created_at) VALUES(?,?,?);",
            (int(order_id), int(dn), datetime.utcnow().isoformat()),
        )
        _conn.execute("COMMIT;")
        _conn.close()
        return dn
    except Exception:
        try:
            _conn.execute("ROLLBACK;")
            _conn.close()
        except Exception:
            pass
        return int(order_id)

def _get_order_display_no(order_id: int | None) -> int | None:
    if order_id is None:
        return None
    _ensure_order_display_table()
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        row = _conn.execute("SELECT display_no FROM order_display WHERE order_id=?;", (int(order_id),)).fetchone()
        _conn.close()
        if not row or row[0] is None:
            return None
        return int(row[0])
    except Exception:
        return None

def _display_order_no(order_id: int | None) -> int | None:
    """Display 'Order ID' that matches what admin sees.

    Rule:
    - اگر این سفارش از محصول تحویل شده باشد: همان Feed ID نمایش داده می‌شود (Order ID == Feed ID).
    - در غیر این صورت: شماره نمایشی 1..n (یا fallback به id داخلی).
    """
    if order_id is None:
        return None
    fid = _get_feed_id_by_order_id(order_id)
    if fid is not None:
        return int(fid)
    dn = _get_order_display_no(order_id)
    return dn if dn is not None else int(order_id)


# ================== SAFE CLAIM FEED ITEM (CONSISTENT ID/DATA) ==================
# هدف: آیتم محصول دقیقا با همان id که تحویل می‌شود در DB تحویل‌شده شود (بدون mismatch).
def safe_claim_next_feed_item(product_id: int):
    try:
        import sqlite3
        _conn = sqlite3.connect(DB_FULL_PATH)
        _conn.execute("BEGIN IMMEDIATE;")
        row = _conn.execute(
            "SELECT id, data FROM product_feed WHERE product_id=? AND delivered=0 ORDER BY id ASC LIMIT 1;",
            (int(product_id),),
        ).fetchone()
        if not row:
            _conn.commit()
            _conn.close()
            return None
        fid, data = int(row[0]), row[1]
        _conn.execute(
            "UPDATE product_feed SET delivered=1 WHERE id=? AND product_id=?;",
            (int(fid), int(product_id)),
        )
        _conn.commit()
        _conn.close()
        return fid, data
    except Exception:
        try:
            _conn.close()
        except Exception:
            pass
        return None


# ensure table on boot (so admin callbacks also work even if nobody ran /start yet)
_ensure_delivery_table()


@bot.message_handler(commands=["admin", "panel"])
def handle_admin_command(message):
    uid = message.from_user.id
    if not ensure_admin(uid):
        return
    panel_url = "https://stockland-bot-production.up.railway.app/admin/"
    kb = types.InlineKeyboardMarkup(row_width=1)
    kb.add(
        types.InlineKeyboardButton("🌐 پنل مدیریت وب", url=panel_url),
        types.InlineKeyboardButton("📦 محصولات", url=panel_url + "products"),
        types.InlineKeyboardButton("🗃 موجودی", url=panel_url + "feed"),
        types.InlineKeyboardButton("⚙️ تنظیمات", url=panel_url + "settings"),
        types.InlineKeyboardButton("👥 ادمین‌ها", url=panel_url + "admins"),
        types.InlineKeyboardButton("💾 دیتابیس", url=panel_url + "database"),
    )
    bot.send_message(uid, "🛍 پنل مدیریت استوک لند:", reply_markup=kb)


@bot.message_handler(commands=["start"])
def handle_start(message):
    init_db(DB_PATH)
    ensure_pending_schema()
    _ensure_delivery_table()
    _ensure_ticket_tables()
    full_name = (message.from_user.first_name or "") + " " + (
        message.from_user.last_name or ""
    )
    text = (
        f"سلام {full_name.strip() or 'دوست عزیز'} 👋\n\n"
        "به ربات فروش سرویس خوش آمدید.\n"
        "از منوی زیر، سرویس مورد نظر خود را انتخاب کنید."
    )
    bot.send_message(message.chat.id, text, reply_markup=main_menu())

def safe_edit_message_text(*args, **kwargs):
    """
    Stack-navigation policy:
    - Never edit an existing message to "open" a new page.
    - Always send a new message instead.

    This function is kept for backward compatibility with old call-sites that were using
    edit_message_text. It will parse the common (text, chat_id, message_id, ...) signature
    and convert it to send_message(chat_id, text, ...).
    """
    # Extract text
    text = None
    if args:
        text = args[0]
    if text is None:
        text = kwargs.get("text")
    # Extract chat_id (accept kwargs or positional arg#1)
    chat_id = kwargs.get("chat_id")
    if chat_id is None and len(args) >= 2:
        chat_id = args[1]

    # If we still can't determine chat_id, do nothing (best-effort).
    if chat_id is None:
        return None

    # Map supported kwargs from edit_* to send_message
    reply_markup = kwargs.get("reply_markup")
    parse_mode = kwargs.get("parse_mode")
    disable_web_page_preview = kwargs.get("disable_web_page_preview")
    entities = kwargs.get("entities")

    try:
        return bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode=parse_mode,
            disable_web_page_preview=disable_web_page_preview,
            entities=entities,
        )
    except Exception:
        return None

# ========= TICKET CHAT (USER) =========
@bot.message_handler(func=lambda m: (not ensure_admin(m.from_user.id)) and (user_states.get(m.from_user.id, {}).get("mode") == "ticket_chat"))
def handle_ticket_chat_user(message):
    uid = message.from_user.id
    st = user_states.get(uid) or {}
    tid = st.get("ticket_id")
    if not tid:
        clear_user_state(uid)
        return
    tk = _get_ticket(int(tid))
    if not tk or tk[4] != "open":
        # اگر تیکت قبلی بسته شده ولی یک تیکت باز جدید داریم (مثلاً خرید جدید)، به جدید سوییچ کن.
        latest = _get_open_ticket_for_user(int(uid))
        if latest:
            new_tid, _pid, _ord = latest
            user_states[uid] = {"mode": "ticket_chat", "ticket_id": int(new_tid)}
            tk = _get_ticket(int(new_tid))
        else:
            clear_user_state(uid)
            bot.send_message(message.chat.id, "این چت بسته شده است.", reply_markup=main_menu())
            return

    # forward to admin with context + reply buttons
    ticket_id, user_id, product_id, order_no, status = tk
    header = f"💬 <b>پیام کاربر</b>\nTicket: <code>{ticket_id}</code>\nOrder: <b>#{order_no}</b>\nProduct ID: <code>{product_id}</code>\nUser ID: <code>{user_id}</code>\n\n"
    txt = (message.text or "").strip()

    if message.content_type == "text" and txt:
        bot.send_message(ADMIN_ID, header + html.escape(txt), reply_markup=_ticket_admin_keyboard(ticket_id, user_id), parse_mode="HTML")
    else:
        # برای انواع غیرمتنی، فوروارد مستقیم + یک پیام زمینه
        try:
            bot.send_message(ADMIN_ID, header + "<i>(فایل/مدیا)</i>", reply_markup=_ticket_admin_keyboard(ticket_id, user_id), parse_mode="HTML")
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
        except Exception:
            pass

    bot.reply_to(message, "✅ ارسال شد.")


@bot.message_handler(func=lambda m: (not ensure_admin(m.from_user.id)) and (user_states.get(m.from_user.id, {}).get("mode") == "ticket_chat"), content_types=["photo","document","video","audio","voice","sticker","animation"])
def handle_ticket_chat_user_media(message):
    handle_ticket_chat_user(message)



# ========= HELPERS =========


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
    bot.send_message(
        message.chat.id,
        f"مقدار شارژ کیف پول را به تومان ارسال کنید.\n"
        f"حداقل مبلغ: <b>{MIN_TOPUP_AMOUNT:,}</b> تومان",
    )
    user_states[uid] = {"mode": "wallet_charge_amount"}
    bot.register_next_step_handler(message, process_wallet_charge_amount)


def process_wallet_charge_amount(message):
    uid = message.from_user.id
    text = message.text.strip().replace(",", "")
    amount = safe_int(text)

    if amount is None:
        bot.reply_to(message, "مبلغ فقط باید شامل عدد باشد. دوباره ارسال کنید.")
        bot.register_next_step_handler(message, process_wallet_charge_amount)
        return

    if amount < MIN_TOPUP_AMOUNT:
        bot.reply_to(
            message,
            f"حداقل مبلغ شارژ <b>{MIN_TOPUP_AMOUNT:,}</b> تومان است. "
            f"لطفا مبلغ بالاتری ارسال کنید.",
        )
        bot.register_next_step_handler(message, process_wallet_charge_amount)
        return

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
    cur = conn.cursor()

    cur.execute("SELECT balance FROM wallets WHERE user_id=?", (uid,))
    row = cur.fetchone()

    if not row:
        conn.close()
        bot.answer_callback_query(call.id, "کیف پول یافت نشد", show_alert=True)
        return

    current_balance = int(row[0])

    if current_balance < eff_price:
        conn.close()
        bot.answer_callback_query(call.id, "موجودی کافی نیست", show_alert=True)
        return

    new_balance = current_balance - eff_price

    cur.execute(
        "UPDATE wallets SET balance=?, updated_at=? WHERE user_id=?",
        (new_balance, datetime.utcnow().isoformat(), uid)
    )

    conn.commit()
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

    # ----------------------------
    # تحویل فوری در صورت وجود موجودی
    # ----------------------------
    feed_item = safe_claim_next_feed_item(pid)

    if feed_item:
        feed_id, feed_data = feed_item

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

        try:
            bot.send_message(
                ADMIN_ID,
                "📦 تحویل فوری محصول\n\n"
                f"Order ID: #{order_id}\n"
                f"User ID: {uid}\n"
                f"محصول: {title} (#{pid})\n"
                f"مبلغ: {eff_price:,} تومان"
            )
        except:
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

#======================= handle_confirm_full ======================

def _daily_limit_exceeded(uid, product, pid):
    """True if the user's daily purchase cap for this product is reached.

    Defense-in-depth: even though send_product_detail already checks this,
    the user might have bought elsewhere between seeing the button and
    pressing it. Returns (exceeded: bool, limit_val: int).
    """
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

    # confirm_full_{category}_{pid} -- pid is last, category may contain "_"
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

    # سقف خرید روزانه
    exceeded, limit_val = _daily_limit_exceeded(uid, product, pid)
    if exceeded:
        bot.answer_callback_query(
            call.id,
            f"سقف خرید روزانه ({limit_val}) تکمیل شده است.",
            show_alert=True,
        )
        return

    price = product[3]
    partner_price = product[6] if len(product) > 6 else None
    partner_ok = is_partner_approved(uid)
    eff_price = partner_price if (partner_ok and partner_price) else price

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

    # confirm_wallet_{category}_{pid} -- pid is last, category may contain "_"
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

    # سقف خرید روزانه
    exceeded, limit_val = _daily_limit_exceeded(uid, product, pid)
    if exceeded:
        bot.answer_callback_query(
            call.id,
            f"سقف خرید روزانه ({limit_val}) تکمیل شده است.",
            show_alert=True,
        )
        return

    title = product[2]
    price = product[3]
    partner_price = product[6] if len(product) > 6 else None

    partner_ok = is_partner_approved(uid)
    eff_price = partner_price if (partner_ok and partner_price) else price

    wallet_balance = get_wallet_balance(uid)

    # 🟢 اگر کیف پول کامل پوشش دهد → مستقیم خرید
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
    
    
# ========= ADMIN PRODUCT UI =========

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
        _row = _conn.execute(
            'SELECT daily_limit_customer, daily_limit_partner FROM products WHERE id=?',
            (pid,)
        ).fetchone()
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
    conn.close()
    return int(total or 0)


def list_feed_items_global(delivered_filter: int | None, limit: int = 50, offset: int = 0, category_key: str | None = None):
    import sqlite3
    conn = sqlite3.connect(DB_FULL_PATH)
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
    conn.close()
    return rows


def get_feed_stats_by_category():
    """Return list of dicts: category, total, delivered, undelivered."""
    import sqlite3
    conn = sqlite3.connect(DB_FULL_PATH)
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
    row = conn.execute(
        '''
        SELECT pf.id, pf.product_id, COALESCE(p.category,''), COALESCE(p.title,''), pf.data, pf.delivered, pf.created_at
        FROM product_feed pf
        LEFT JOIN products p ON p.id = pf.product_id
        WHERE pf.id=?
        ''',
        (fid,),
    ).fetchone()
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
        bot.reply_to(message, "این بخش غیرفعال است.")
        return

    uid = message.from_user.id
    balance = get_wallet_balance(uid)
    text = f"موجودی کیف پول شما: <b>{balance:,}</b> تومان"
    bot.send_message(message.chat.id, text, reply_markup=wallet_inline_keyboard())


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_MY_ORDERS"))
def handle_my_orders_menu(message):
    if not is_main_button_enabled("MAIN_BTN_MY_ORDERS"):
        bot.reply_to(message, "این بخش غیرفعال است.")
        return

    uid = message.from_user.id
    orders = get_recent_orders_by_user(uid, limit=10)
    if not orders:
        bot.send_message(message.chat.id, "هنوز سفارشی ثبت نکرده‌اید.")
        return
    lines = []
    for o in orders:
        oid, title, amount, created_at = o
        date_str = created_at.split("T")[0] if created_at else ""
        dn = _display_order_no(int(oid))
        show_id = dn if dn is not None else oid
        lines.append(f"#{show_id} | {title} | {amount:,} تومان | {date_str}")
    bot.send_message(message.chat.id, "\n".join(lines))


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_SUPPORT"))
def handle_support(message):
    if not is_main_button_enabled("MAIN_BTN_SUPPORT"):
        bot.reply_to(message, "این بخش غیرفعال است.")
        return

    text = t("SUPPORT_TEXT", DEFAULT_UI_TEXTS.get("SUPPORT_TEXT", ""))
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_PARTNER_PANEL"))
def handle_partner_panel(message):
    if not is_main_button_enabled("MAIN_BTN_PARTNER_PANEL"):
        bot.reply_to(message, "این بخش غیرفعال است.")
        return

    uid = message.from_user.id
    if is_partner_approved(uid):
        partner = get_partner_by_user_id(uid)
        phone = partner[2] if partner else "-"
        text = (
            "پنل همکار 🤝\n\n"
            f"وضعیت: ✅ تایید شده\n"
            f"شماره ثبت‌شده: <b>{phone}</b>\n\n"
            "از این لحظه قیمت‌های همکار (در صورت تعریف) برای شما نمایش داده می‌شود."
        )
        bot.send_message(message.chat.id, text)
    else:
        text = (
            "پنل همکار 🤝\n\n"
            "شما هنوز به‌عنوان همکار تایید نشده‌اید.\n"
            "برای ثبت درخواست از «درخواست نمایندگی 📝» استفاده کنید."
        )
        bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_PARTNER_REQUEST"))
def handle_reseller_request(message):
    if not is_main_button_enabled("MAIN_BTN_PARTNER_REQUEST"):
        bot.reply_to(message, "این بخش غیرفعال است.")
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
        "برای ثبت درخواست نمایندگی، شماره تلفن خود را با دکمه زیر ارسال کنید:",
        reply_markup=kb,
    )
    bot.register_next_step_handler(message, process_reseller_contact)


def process_reseller_contact(message):
    uid = message.from_user.id

    if message.text and message.text.strip() == "❌ انصراف":
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu())
        return
    if message.content_type != "contact" or not message.contact:
        bot.send_message(
            message.chat.id,
            "لطفاً شماره را فقط با دکمه «📱 ارسال شماره تلفن» ارسال کنید.",
            reply_markup=main_menu(),
        )
        return
    if message.contact.user_id and message.contact.user_id != uid:
        bot.send_message(message.chat.id, "شماره ارسالی متعلق به همین اکانت نیست. دوباره تلاش کنید.", reply_markup=main_menu())
        return

    phone = (message.contact.phone_number or "").strip()
    ok, msg = can_submit_partner_request(uid, phone=phone)
    if not ok:
        bot.send_message(message.chat.id, msg, reply_markup=main_menu())
        return
    username = message.from_user.username or ""
    full_name = f"{message.from_user.first_name or ''} {message.from_user.last_name or ''}".strip()

    reseller_signup[uid] = {
        "phone": phone,
        "username": username,
        "full_name": full_name,
        "city": "",
        "shop_name": "",
    }

    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=True)
    kb.add(types.KeyboardButton("❌ انصراف"))
    bot.send_message(message.chat.id, "شهر فعالیت خود را وارد کنید:", reply_markup=kb)
    bot.register_next_step_handler(message, process_reseller_city)


def process_reseller_city(message):
    uid = message.from_user.id
    if message.text and message.text.strip() == "❌ انصراف":
        reseller_signup.pop(uid, None)
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu())
        return
    city = (message.text or "").strip()
    if not city or len(city) < 2:
        bot.send_message(message.chat.id, "نام شهر نامعتبر است. دوباره ارسال کنید:")
        bot.register_next_step_handler(message, process_reseller_city)
        return

    if uid not in reseller_signup:
        bot.send_message(message.chat.id, "درخواست شما منقضی شد. دوباره از «درخواست نمایندگی 📝» شروع کنید.", reply_markup=main_menu())
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
        bot.send_message(message.chat.id, "لغو شد.", reply_markup=main_menu())
        return
    shop_name = (message.text or "").strip()
    if not shop_name or len(shop_name) < 2:
        bot.send_message(message.chat.id, "نام فروشگاه نامعتبر است. دوباره ارسال کنید:")
        bot.register_next_step_handler(message, process_reseller_shop)
        return

    data = reseller_signup.pop(uid, None)
    if not data:
        bot.send_message(message.chat.id, "درخواست شما منقضی شد. دوباره از «درخواست نمایندگی 📝» شروع کنید.", reply_markup=main_menu())
        return

    phone = data["phone"]
    username = data["username"]
    full_name = data["full_name"]
    city = data["city"]

    upsert_partner_request(uid, phone, username=username, full_name=full_name, note="", city=city, shop_name=shop_name)

    bot.send_message(
        message.chat.id,
        "درخواست شما ثبت شد ✅\nپس از بررسی، در صورت تایید، قیمت همکار برای شما فعال می‌شود.",
        reply_markup=main_menu(),
    )

    try:
        kb = types.InlineKeyboardMarkup(row_width=2)
        kb.add(
            types.InlineKeyboardButton("✅ تایید", callback_data=f"admin_partner_approve_{uid}"),
            types.InlineKeyboardButton("❌ رد", callback_data=f"admin_partner_reject_{uid}"),
        )
        h = html.escape
        admin_text = (
            "📥 <b>درخواست نمایندگی جدید</b>\n\n"
            f"User ID: <code>{uid}</code>\n"
            f"Username: @{h(username) if username else '-'}\n"
            f"Name: {h(full_name) if full_name else '-'}\n"
            f"Phone: {h(phone)}\n"
            f"City: <b>{h(city) if city else '-'}</b>\n"
            f"Shop: <b>{h(shop_name) if shop_name else '-'}</b>"
        )
        bot.send_message(ADMIN_ID, admin_text, reply_markup=kb, parse_mode="HTML")
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.text == t("MAIN_BTN_GUIDE"))
def handle_help(message):
    if not is_main_button_enabled("MAIN_BTN_GUIDE"):
        bot.reply_to(message, "این بخش غیرفعال است.")
        return

    text = t("HELP_TEXT", DEFAULT_UI_TEXTS.get("HELP_TEXT", ""))
    bot.send_message(message.chat.id, text)


@bot.message_handler(func=lambda m: ensure_admin(m.from_user.id))
def handle_admin_text(message):
    aid = message.from_user.id
    state = admin_states.get(aid)
    if not state:
        return

    mode = state.get("mode")

    if mode == "ticket_reply":
        tid = int(state.get("ticket_id") or 0)
        target_uid = int(state.get("target_user_id") or 0)
        if not tid or not target_uid:
            clear_admin_state(aid)
            bot.reply_to(message, "تیکت نامعتبر است.")
            return
        tk = _get_ticket(tid)
        if not tk or tk[4] != "open":
            clear_admin_state(aid)
            bot.reply_to(message, "این تیکت بسته شده است.")
            return
        txt = (message.text or "").strip()
        if not txt:
            bot.reply_to(message, "پیام خالی است. دوباره ارسال کنید:")
            return
        # send to user
        try:
            bot.send_message(target_uid, f"💬 پاسخ پشتیبانی (Order #{tk[3]}):\n{txt}", reply_markup=_ticket_user_keyboard(tid))
        except Exception:
            pass
        bot.reply_to(message, "✅ ارسال شد.")
        # keep admin in reply mode unless /done
        if txt.strip() == "/done":
            clear_admin_state(aid)
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
        _ensure_ticket_tables()
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


@bot.callback_query_handler(func=lambda c: True)
def handle_callbacks(call: types.CallbackQuery):
    data = call.data
    uid = call.from_user.id
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
    
    if data == "noop":
        bot.answer_callback_query(call.id)
        return

    if data == "cancel_purchase":
        bot.answer_callback_query(call.id)
        clear_user_state(uid)
        bot.send_message(call.message.chat.id, "خرید لغو شد.", reply_markup=main_menu())
        return

    # ─── ناوبری دسته‌بندی داینامیک ────────────────────────────────────────
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
            # نمایش جزئیات با استفاده از تابع موجود
            send_product_detail(call.message, product, cat_id=cat_id)
            return
        return

    if data.startswith("ticket_close_"):
        bot.answer_callback_query(call.id)
        tid = safe_int(data.replace("ticket_close_", "", 1))
        tk = _get_ticket(int(tid)) if tid else None
        if not tk:
            return
        # only owner can close
        if int(tk[1]) != int(uid):
            return
        _close_ticket(int(tid), "user")
        clear_user_state(uid)
        bot.send_message(call.message.chat.id, "✅ چت بسته شد.", reply_markup=main_menu())
        # notify admin
        try:
            bot.send_message(
                ADMIN_ID,
                f"⛔️ چت توسط کاربر بسته شد.\n"
                f"Ticket ID: <code>{int(tid)}</code>\n"
                f"User ID: <code>{int(tk[1])}</code>\n"
                f"Product ID: <code>{int(tk[2])}</code>\n"
                f"Order/Feed ID: <code>{int(tk[3])}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    if data.startswith("ticket_admin_close_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        tid = safe_int(data.replace("ticket_admin_close_", "", 1))
        tk = _get_ticket(int(tid)) if tid else None
        if not tk:
            return
        _close_ticket(int(tid), "admin")
        clear_user_state(int(tk[1]))  # برای خرید/چت بعدی گیر نکند
        try:
            bot.send_message(int(tk[1]), "⛔️ چت توسط پشتیبانی بسته شد.", reply_markup=main_menu())
        except Exception:
            pass
        # notify admin (confirmation)
        try:
            bot.send_message(
                ADMIN_ID,
                f"⛔️ چت توسط ادمین بسته شد.\n"
                f"Ticket ID: <code>{int(tid)}</code>\n"
                f"User ID: <code>{int(tk[1])}</code>\n"
                f"Product ID: <code>{int(tk[2])}</code>\n"
                f"Order/Feed ID: <code>{int(tk[3])}</code>",
                parse_mode="HTML",
            )
        except Exception:
            pass
        return

    if data.startswith("ticket_reply_"):
        if not ensure_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز", show_alert=True)
            return
        bot.answer_callback_query(call.id)
        # ticket_reply_{tid}_{user_id}
        parts = data.split("_")
        tid = safe_int(parts[2]) if len(parts) >= 3 else None
        target_uid = safe_int(parts[3]) if len(parts) >= 4 else None
        if not tid or not target_uid:
            return
        tk = _get_ticket(int(tid))
        if not tk or tk[4] != "open":
            bot.send_message(call.message.chat.id, "این تیکت بسته شده است.")
            return
        admin_states[uid] = {"mode": "ticket_reply", "ticket_id": int(tid), "target_user_id": int(target_uid)}
        bot.send_message(call.message.chat.id, f"✉️ پاسخ خود را برای Order #{tk[3]} ارسال کنید:")
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
        kb = types.InlineKeyboardMarkup()
        kb.add(
            types.InlineKeyboardButton(
                "💳 کارت به کارت", callback_data="wallet_card2card"
            ),
            types.InlineKeyboardButton(
                "🌐 درگاه پرداخت", callback_data="wallet_gateway"
            ),
        )
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
        bot.send_message(call.message.chat.id, t("TXT_MAIN_MENU_TITLE","منوی اصلی"), reply_markup=main_menu())
        return

    if data == "other_back":
        bot.answer_callback_query(call.id)
        bot.send_message(call.message.chat.id, t("TXT_MAIN_MENU_TITLE","منوی اصلی"), reply_markup=main_menu())
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
        panel_url = f"https://stockland-bot-production.up.railway.app/admin/settings"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌐 باز کردن پنل تنظیمات", url=panel_url))
        bot.send_message(call.message.chat.id, "تنظیمات به پنل وب منتقل شده است:", reply_markup=kb)
        return

    if data in ("admin_main_btn_manage", "admin_ui_main_buttons", "admin_ui_texts",
                "admin_ui_captions", "admin_backup_menu"):
        bot.answer_callback_query(call.id)
        panel_url = f"https://stockland-bot-production.up.railway.app/admin/"
        kb = types.InlineKeyboardMarkup()
        kb.add(types.InlineKeyboardButton("🌐 باز کردن پنل مدیریت", url=panel_url))
        bot.send_message(call.message.chat.id, "این بخش به پنل وب منتقل شده:", reply_markup=kb)
        return

    if (data.startswith("admin_main_btn_toggle_") or data.startswith("admin_ui_edit_") or
            data in ("admin_export_backup", "admin_import_backup",
                     "admin_full_reset_1", "admin_full_reset_2", "admin_full_reset_do")):
        bot.answer_callback_query(call.id)
        panel_url = "https://stockland-bot-production.up.railway.app/admin/"
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
            cur = conn.cursor()
            cur.execute("SELECT delivered FROM product_feed WHERE id=?", (fid,))
            r = cur.fetchone()
            if not r:
                conn.close()
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
                    bot.send_message(target_uid, "✅ درخواست نمایندگی شما تایید شد. قیمت همکار برای شما فعال است.")
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
            _r = _conn.execute(
                "SELECT id, data, delivered, created_at FROM product_feed WHERE id=? AND product_id=?;",
                (int(feed_id), int(pid)),
            ).fetchone()
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
            _r = _conn.execute("SELECT delivered FROM product_feed WHERE id=? AND product_id=?;", (int(feed_id), int(pid))).fetchone()
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
            text = "هنوز سفارشی ثبت نشده است."
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
    func=lambda m: user_states.get(m.from_user.id, {}).get("mode")
    == "card2card_receipt",
    content_types=["text"],
)
def handle_card2card_text(message):
    bot.reply_to(
        message,
        "در حال حاضر فقط عکس رسید کارت به کارت را ارسال کنید. برای لغو از دکمه ❌ انصراف استفاده کنید.",
    )


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


if __name__ == "__main__":
    init_db(DB_PATH)
    _ensure_delivery_table()
    _ensure_ticket_tables()
    logger.info("Bot started...")

    import time
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=60)
        except Exception as e:
            logger.exception("Polling crashed, restarting in 5s: %s", e)
            time.sleep(5)
