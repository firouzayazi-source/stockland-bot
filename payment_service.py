"""Stockland payment service (Zarinpal) — platform independent.

Responsibilities
----------------
1. POST /payment/create  : the bot asks us to start a Zarinpal transaction.
                           We create a pending record and return the gateway URL.
2. GET  /payment/callback : Zarinpal redirects the user back here after payment.
                           We verify, then either top up the wallet or deliver
                           the purchased product, and notify the user on Telegram.

Design notes
------------
* Everything is read from environment variables. Nothing is hard-wired to
  Railway or any specific domain. Move this file to a VPS and only the env
  changes (BASE_CALLBACK_URL, PAYMENT_PUBLIC_BASE_URL, DB_PATH, ...).
* One SQLite database (DB_PATH), shared with the bot. Single source of truth.
* The same `authority` is unique in the DB, so a double callback never
  double-credits (idempotency via `status='pending'` guards).
"""

import hashlib
import hmac
import html
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, date

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse


logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("stockland.payment")

# ---------------------------------------------------------------------------
# Configuration (all from env)
# ---------------------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH")
if not DB_PATH:
    raise RuntimeError("DB_PATH environment variable is required")

MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID") or ""
REQUEST_URL = os.getenv(
    "ZARINPAL_REQUEST_URL", "https://api.zarinpal.com/pg/v4/payment/request.json"
)
VERIFY_URL = os.getenv(
    "ZARINPAL_VERIFY_URL", "https://api.zarinpal.com/pg/v4/payment/verify.json"
)
STARTPAY_URL = os.getenv(
    "ZARINPAL_STARTPAY_URL", "https://www.zarinpal.com/pg/StartPay/"
)
BASE_CALLBACK_URL = os.getenv("BASE_CALLBACK_URL") or ""
MIN_AMOUNT = int(os.getenv("MIN_TOPUP_AMOUNT", "10000"))
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")
BOT_USERNAME = (os.getenv("BOT_USERNAME") or "stock_land_bot").lstrip("@")
RUN_BOT_IN_PAYMENT_SERVICE = os.getenv("RUN_BOT_IN_PAYMENT_SERVICE", "1") != "0"

# Zarinpal works in Rial; our prices are in Toman. 1 Toman = 10 Rial.
RIAL_PER_TOMAN = 10

app = FastAPI(title="Stockland Payment Service")
_bot_thread_started = False

# ── Admin Panel ────────────────────────────────────────────────────────────
from admin_panel import router as _admin_router
app.include_router(_admin_router)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn


def send_telegram_message(user_id: int, text: str, parse_mode: str | None = None) -> None:
    """Send a Telegram message directly via the Bot API (no bot instance needed)."""
    if not BOT_TOKEN:
        return
    payload = {"chat_id": int(user_id), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json=payload,
            timeout=10,
        )
    except Exception:
        logger.exception("Telegram sendMessage failed")


# ---------------------------------------------------------------------------
# Schema (idempotent; matches what the bot expects)
# ---------------------------------------------------------------------------
def ensure_schema() -> None:
    conn = db_connect()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS zarinpal_transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                amount INTEGER NOT NULL,
                authority TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL
            );
            """
        )
        tx_cols = {row["name"] for row in conn.execute("PRAGMA table_info(zarinpal_transactions);")}
        for col, decl in {
            "payment_type": "TEXT DEFAULT 'wallet'",
            "product_id": "INTEGER",
            "wallet_reserved": "INTEGER DEFAULT 0",
            "total_amount": "INTEGER",
            "buyer_type": "TEXT",
            "chat_id": "INTEGER",
            "ref_id": "TEXT",
            "paid_at": "TEXT",
            "error": "TEXT",
        }.items():
            if col not in tx_cols:
                conn.execute(f"ALTER TABLE zarinpal_transactions ADD COLUMN {col} {decl};")
        conn.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_zarinpal_transactions_authority "
            "ON zarinpal_transactions(authority);"
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wallets (
                user_id INTEGER PRIMARY KEY,
                balance INTEGER NOT NULL DEFAULT 0,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                category TEXT NOT NULL,
                product_id TEXT NOT NULL,
                title TEXT NOT NULL,
                price INTEGER NOT NULL,
                created_at TEXT NOT NULL,
                buyer_type TEXT
            );
            """
        )
        order_cols = {row["name"] for row in conn.execute("PRAGMA table_info(orders);")}
        if "buyer_type" not in order_cols:
            conn.execute("ALTER TABLE orders ADD COLUMN buyer_type TEXT;")

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS product_feed (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER NOT NULL,
                data TEXT NOT NULL,
                delivered INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )
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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                web_username TEXT UNIQUE,
                web_password_hash TEXT,
                permissions TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Domain helpers
# ---------------------------------------------------------------------------
def get_product(conn: sqlite3.Connection, product_id: int):
    return conn.execute(
        """
        SELECT id, category, title, price, partner_price,
               COALESCE(daily_limit_customer, 0) AS daily_limit_customer,
               COALESCE(daily_limit_partner, 0)  AS daily_limit_partner
        FROM products WHERE id=? LIMIT 1;
        """,
        (int(product_id),),
    ).fetchone()


def infer_buyer_type(conn: sqlite3.Connection, user_id: int) -> str:
    try:
        row = conn.execute(
            "SELECT status FROM partners WHERE tg_user_id=? LIMIT 1;", (int(user_id),)
        ).fetchone()
        if row and str(row["status"] or "").lower() == "approved":
            return "partner"
    except Exception:
        pass
    return "customer"


def create_order(conn, user_id: int, category: str, product_id: int, title: str, price: int, buyer_type: str) -> int:
    cur = conn.execute(
        """
        INSERT INTO orders (user_id, category, product_id, title, price, created_at, buyer_type)
        VALUES (?, ?, ?, ?, ?, ?, ?);
        """,
        (int(user_id), str(category), str(product_id), str(title), int(price), now_iso(), str(buyer_type)),
    )
    return int(cur.lastrowid)


def claim_feed_item(conn: sqlite3.Connection, product_id: int):
    """Atomically grab the next undelivered feed item for this product."""
    row = conn.execute(
        """
        SELECT id, data FROM product_feed
        WHERE product_id=? AND delivered=0
        ORDER BY id ASC LIMIT 1;
        """,
        (int(product_id),),
    ).fetchone()
    if not row:
        return None
    cur = conn.execute(
        "UPDATE product_feed SET delivered=1 WHERE id=? AND delivered=0;", (int(row["id"]),)
    )
    if cur.rowcount != 1:
        return None
    return int(row["id"]), str(row["data"])


def enqueue_pending_delivery(conn, order_id: int, user_id: int, chat_id: int, product_id: int, title: str, price: int) -> None:
    conn.execute(
        """
        INSERT OR REPLACE INTO pending_deliveries
            (order_id, user_id, chat_id, product_id, product_title, price, status, feed_id)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL);
        """,
        (int(order_id), int(user_id), int(chat_id), int(product_id), str(title), int(price)),
    )


def mark_wallet_charge(conn: sqlite3.Connection, user_id: int, amount: int) -> None:
    conn.execute(
        """
        INSERT INTO wallets (user_id, balance, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET balance = wallets.balance + excluded.balance, updated_at = excluded.updated_at;
        """,
        (int(user_id), int(amount), now_iso()),
    )


def deduct_wallet_reserved(conn: sqlite3.Connection, user_id: int, wallet_reserved: int) -> None:
    wallet_reserved = int(wallet_reserved or 0)
    if wallet_reserved <= 0:
        return
    row = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (int(user_id),)).fetchone()
    current_balance = int(row["balance"] if row else 0)
    new_balance = max(0, current_balance - wallet_reserved)
    conn.execute(
        """
        INSERT INTO wallets (user_id, balance, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at;
        """,
        (int(user_id), int(new_balance), now_iso()),
    )


def count_orders_today(conn: sqlite3.Connection, user_id: int, product_id: int, buyer_type: str) -> int:
    """How many orders this user placed today for this product."""
    try:
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(orders);")}
        if "user_id" not in cols or "created_at" not in cols:
            return 0
        today = date.today().isoformat()
        q = "SELECT COUNT(1) AS c FROM orders WHERE user_id=? AND created_at LIKE ?"
        params: list = [int(user_id), today + "%"]
        if "product_id" in cols:
            q += " AND product_id=?"
            params.append(str(product_id))
        if buyer_type and "buyer_type" in cols:
            q += " AND buyer_type=?"
            params.append(buyer_type)
        r = conn.execute(q, params).fetchone()
        return int(r["c"] if r else 0)
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Zarinpal API
# ---------------------------------------------------------------------------
def zarinpal_create(amount_toman: int, description: str) -> tuple[bool, str, str]:
    """Create a Zarinpal payment. Returns (ok, authority, detail)."""
    try:
        response = requests.post(
            REQUEST_URL,
            json={
                "merchant_id": MERCHANT_ID,
                "amount": int(amount_toman) * RIAL_PER_TOMAN,
                "callback_url": payment_callback_url(),
                "description": description,
            },
            timeout=15,
        )
        result = response.json()
    except Exception as exc:
        logger.exception("Zarinpal create request failed")
        return False, "", str(exc)

    if result.get("data", {}).get("code") == 100:
        return True, str(result["data"]["authority"]), str(result)
    return False, "", str(result)


def verify_zarinpal(authority: str, amount_toman: int) -> tuple[bool, str, str]:
    """Verify a payment. Returns (ok, ref_id, detail)."""
    try:
        response = requests.post(
            VERIFY_URL,
            json={
                "merchant_id": MERCHANT_ID,
                "amount": int(amount_toman) * RIAL_PER_TOMAN,
                "authority": authority,
            },
            timeout=15,
        )
        data = response.json()
    except Exception as exc:
        logger.exception("Zarinpal verify request failed")
        return False, "", str(exc)

    code = data.get("data", {}).get("code")
    # 100 = success, 101 = already verified (still a success for our purposes)
    if code in (100, 101):
        return True, str(data.get("data", {}).get("ref_id") or ""), str(data)
    return False, "", str(data)


def payment_callback_url() -> str:
    """Build the callback URL Zarinpal redirects the user to.

    Priority: explicit BASE_CALLBACK_URL, else a public base + /payment/callback.
    This is the ONLY place the public address is needed -- change env, not code,
    when moving between Railway and a VPS.
    """
    if BASE_CALLBACK_URL:
        return BASE_CALLBACK_URL
    public_base = os.getenv("PAYMENT_PUBLIC_BASE_URL") or os.getenv("RAILWAY_PUBLIC_DOMAIN")
    if public_base:
        if not public_base.startswith(("http://", "https://")):
            public_base = "https://" + public_base
        return public_base.rstrip("/") + "/payment/callback"
    raise HTTPException(500, "BASE_CALLBACK_URL is not configured")


# ---------------------------------------------------------------------------
# App lifecycle: run the Telegram bot in a background thread (single process)
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    ensure_schema()
    maybe_start_bot_polling()


def maybe_start_bot_polling() -> None:
    global _bot_thread_started
    if _bot_thread_started or not RUN_BOT_IN_PAYMENT_SERVICE or not BOT_TOKEN:
        return

    def runner() -> None:
        import bot as bot_module

        bot_module.init_db(bot_module.DB_PATH)
        bot_module.ensure_pending_schema()
        bot_module._ensure_delivery_table()
        bot_module._ensure_ticket_tables()
        logger.info("Bot polling started inside payment service")
        while True:
            try:
                bot_module.bot.infinity_polling(timeout=60, long_polling_timeout=60)
            except Exception:
                logger.exception("Bot polling crashed; restarting in 5 seconds")
                time.sleep(5)

    threading.Thread(target=runner, name="telegram-bot-polling", daemon=True).start()
    _bot_thread_started = True


PHP_SECRET = os.getenv("PHP_SECRET") or ""


@app.get("/health")
def health():
    conn = db_connect()
    try:
        conn.execute("SELECT 1;").fetchone()
        return {"ok": True, "bot_polling": _bot_thread_started, "php_bridge": bool(PHP_SECRET)}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# PHP Bridge: /payment/finalize
# PHP callback روی هاست این endpoint را صدا می‌زند پس از تأیید پرداخت از زرین‌پال
# ---------------------------------------------------------------------------
@app.post("/payment/finalize")
def payment_finalize(payload: dict, request: Request):
    ensure_schema()

    # تأیید secret
    secret = (
        request.headers.get("X-Stockland-Secret")
        or payload.get("secret")
        or ""
    )
    if not PHP_SECRET or not hmac.compare_digest(str(PHP_SECRET), str(secret)):
        raise HTTPException(403, "Unauthorized")

    try:
        user_id        = int(payload["user_id"])
        chat_id        = int(payload.get("chat_id") or user_id)
        amount         = int(payload["amount"])
        payment_type   = str(payload.get("payment_type") or "wallet").lower()
        wallet_reserved= int(payload.get("wallet_reserved") or 0)
        wallet_bonus   = int(payload.get("wallet_bonus") or 0)   # مازاد حداقل درگاه
        ref_id         = str(payload.get("ref_id") or "")
        authority      = str(payload.get("authority") or "")
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(400, f"Invalid payload: {exc}")

    conn = db_connect()
    try:
        # idempotency: اگه قبلاً این authority پردازش شده، دوباره انجام نده
        if authority:
            existing = conn.execute(
                "SELECT status FROM zarinpal_transactions WHERE authority=? LIMIT 1;",
                (authority,)
            ).fetchone()
            if existing and str(existing["status"]) == "paid":
                return {"ok": True, "status": "already_processed"}

        buyer_type = infer_buyer_type(conn, user_id)
        total_amount = amount + wallet_reserved

        # ذخیره تراکنش در دیتابیس
        if authority:
            try:
                conn.execute(
                    """
                    INSERT OR IGNORE INTO zarinpal_transactions
                        (user_id, amount, authority, status, created_at, payment_type,
                         wallet_reserved, total_amount, buyer_type, chat_id, ref_id, paid_at)
                    VALUES (?,?,?,'paid',?,?,?,?,?,?,?,?);
                    """,
                    (user_id, amount, authority, now_iso(), payment_type,
                     wallet_reserved, total_amount, buyer_type, chat_id, ref_id, now_iso()),
                )
            except Exception:
                # ممکنه authority تکراری باشد
                conn.execute(
                    "UPDATE zarinpal_transactions SET status='paid', ref_id=?, paid_at=? "
                    "WHERE authority=? AND status='pending';",
                    (ref_id, now_iso(), authority),
                )

        # ─── شارژ کیف پول ─────────────────────────────────
        if payment_type == "wallet":
            # Issue 2: اضافه کردن wallet_bonus اگه حداقل درگاه اعمال شده بود
            total_wallet = amount + wallet_bonus
            mark_wallet_charge(conn, user_id, total_wallet)
            conn.commit()
            msg = (
                f"✅ کیف پول شما با موفقیت شارژ شد.\n"
                f"مبلغ: <b>{total_wallet:,}</b> تومان\n"
                f"کد پیگیری: {ref_id}"
            )
            if wallet_bonus > 0:
                msg += f"\n\n💡 {wallet_bonus:,} تومان بابت حداقل پرداخت درگاه به کیف‌پول اضافه شد."
            send_telegram_message(chat_id, msg, parse_mode="HTML")
            return {"ok": True, "type": "wallet", "amount": total_wallet}

        # ─── خرید محصول ───────────────────────────────────
        product_id = int(payload.get("product_id") or 0)
        if not product_id:
            raise HTTPException(400, "product_id is required for product payment")

        product = get_product(conn, product_id)
        if not product:
            # Issue 4: محصول پیدا نشد — پول رو به کیف‌پول برگردون
            refund = amount + wallet_bonus
            mark_wallet_charge(conn, user_id, refund)
            conn.commit()
            send_telegram_message(
                chat_id,
                f"⚠️ پرداخت موفق بود ولی محصول یافت نشد.\n"
                f"مبلغ <b>{refund:,}</b> تومان به کیف‌پول شما بازگردانده شد.\n"
                f"کد پیگیری: {ref_id}",
                parse_mode="HTML"
            )
            if ADMIN_ID:
                send_telegram_message(ADMIN_ID, f"⚠️ محصول #{product_id} پیدا نشد — {refund:,}t به کیف‌پول User {user_id} بازگشت")
            return {"ok": True, "type": "refund", "amount": refund}

        title    = str(product["title"])
        category = str(product["category"])

        deduct_wallet_reserved(conn, user_id, wallet_reserved)
        order_id  = create_order(conn, user_id, category, product_id, title, total_amount, buyer_type)
        feed_item = claim_feed_item(conn, product_id)

        if feed_item:
            feed_id, feed_data = feed_item
            conn.commit()
            send_telegram_message(
                chat_id,
                (
                    "✅ سفارش شما ثبت و تحویل شد.\n\n"
                    f"شماره سفارش: #{order_id}\n"
                    f"سرویس: {title}\n"
                    f"مبلغ کل: {total_amount:,} تومان\n"
                    f"کد پیگیری: {ref_id}\n\n"
                    f"<code>{feed_data}</code>"
                ),
                parse_mode="HTML",
            )
            if ADMIN_ID:
                send_telegram_message(
                    ADMIN_ID,
                    f"📦 تحویل خودکار (PHP Bridge)\n\n"
                    f"Order: #{order_id} | User: {user_id}\n"
                    f"Product: {title} (#{product_id})\n"
                    f"Feed: #{feed_id}",
                )
            return {"ok": True, "type": "product", "order_id": order_id, "delivered": True}
        else:
            enqueue_pending_delivery(conn, order_id, user_id, chat_id, product_id, title, total_amount)
            conn.commit()
            send_telegram_message(
                chat_id,
                (
                    "✅ سفارش شما ثبت شد.\n\n"
                    f"شماره سفارش: #{order_id}\n"
                    f"سرویس: {title}\n"
                    f"مبلغ کل: {total_amount:,} تومان\n"
                    "موجودی محصول تکمیل است، به‌محض شارژ ارسال خواهد شد."
                ),
            )
            if ADMIN_ID:
                send_telegram_message(ADMIN_ID, f"⚠️ سفارش بدون موجودی\nOrder: #{order_id} | User: {user_id} | Product: {title}")
            return {"ok": True, "type": "product", "order_id": order_id, "delivered": False}

    except HTTPException:
        raise
    except Exception:
        logger.exception("payment_finalize failed")
        try:
            conn.rollback()
        except Exception:
            pass
        raise HTTPException(500, "Internal error")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1) Create a payment
# ---------------------------------------------------------------------------
@app.post("/payment/create")
def create_payment(payload: dict):
    ensure_schema()
    if not MERCHANT_ID:
        raise HTTPException(500, "ZARINPAL_MERCHANT_ID is not configured")

    try:
        user_id = int(payload.get("user_id"))
        amount_toman = int(payload.get("amount", 0))
        wallet_reserved = int(payload.get("wallet_reserved", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid input")

    chat_id = payload.get("chat_id")
    try:
        chat_id = int(chat_id) if chat_id is not None else user_id
    except (TypeError, ValueError):
        chat_id = user_id

    payment_type = str(payload.get("payment_type") or "wallet").lower().strip()
    if payment_type not in ("wallet", "product"):
        raise HTTPException(400, "Invalid payment_type")
    if amount_toman < MIN_AMOUNT:
        raise HTTPException(400, f"Minimum amount is {MIN_AMOUNT}")
    if wallet_reserved < 0:
        raise HTTPException(400, "wallet_reserved must be positive")

    product_id = payload.get("product_id")
    if payment_type == "product":
        try:
            product_id = int(product_id)
        except (TypeError, ValueError):
            raise HTTPException(400, "product_id is required for product payment")
    else:
        product_id = None
        wallet_reserved = 0

    conn = db_connect()
    try:
        buyer_type = infer_buyer_type(conn, user_id)
        product_title = ""
        if payment_type == "product":
            product = get_product(conn, int(product_id))
            if not product:
                raise HTTPException(404, "Product not found")
            product_title = str(product["title"])

            # سقف خرید روزانه (دفاع لایه‌ی سرور؛ ربات هم قبلش چک می‌کند)
            limit_val = int(
                product["daily_limit_partner"] if buyer_type == "partner"
                else product["daily_limit_customer"]
            )
            if limit_val > 0:
                cnt = count_orders_today(conn, user_id, int(product_id), buyer_type)
                if cnt >= limit_val:
                    raise HTTPException(400, "Daily purchase limit reached")

        ok, authority, detail = zarinpal_create(
            amount_toman,
            f"Stockland {payment_type} payment {product_title} user {user_id}".strip(),
        )
        if not ok:
            logger.error("Zarinpal create failed: %s", detail)
            raise HTTPException(400, "Zarinpal create failed")

        total_amount = amount_toman + wallet_reserved
        conn.execute(
            """
            INSERT INTO zarinpal_transactions
                (user_id, amount, authority, status, created_at, payment_type,
                 product_id, wallet_reserved, total_amount, buyer_type, chat_id)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, amount_toman, authority, now_iso(), payment_type,
             product_id, wallet_reserved, total_amount, buyer_type, chat_id),
        )
        conn.commit()
    finally:
        conn.close()

    return {"authority": authority, "payment_url": STARTPAY_URL.rstrip("/") + "/" + authority}


# ---------------------------------------------------------------------------
# 2) Payment callback (user returns from Zarinpal)
# ---------------------------------------------------------------------------
@app.get("/payment/callback", response_class=HTMLResponse)
def payment_callback(Authority: str | None = None, Status: str | None = None):
    ensure_schema()
    if not Authority:
        return error_page("Authority نامعتبر است.")

    conn = db_connect()
    try:
        tx = conn.execute(
            "SELECT * FROM zarinpal_transactions WHERE authority=? LIMIT 1;", (Authority,)
        ).fetchone()
        if not tx:
            return error_page("تراکنش پیدا نشد.")

        # Already processed -> show success again (idempotent)
        if str(tx["status"]).lower() == "paid":
            return success_page(int(tx["total_amount"] or tx["amount"]), tx["ref_id"] or "-")

        # User canceled or gateway returned non-OK
        if Status != "OK":
            conn.execute(
                "UPDATE zarinpal_transactions SET status='canceled', error=? "
                "WHERE authority=? AND status='pending';",
                ("gateway returned non-OK status", Authority),
            )
            conn.commit()
            return cancel_page()

        # Verify with Zarinpal
        ok, ref_id, verify_detail = verify_zarinpal(Authority, int(tx["amount"]))
        if not ok:
            conn.execute(
                "UPDATE zarinpal_transactions SET error=? WHERE authority=?;",
                (verify_detail[:1000], Authority),
            )
            conn.commit()
            return error_page("پرداخت تایید نشد.")

        # Lock and re-check (idempotency under concurrent callbacks)
        conn.execute("BEGIN IMMEDIATE;")
        tx = conn.execute(
            "SELECT * FROM zarinpal_transactions WHERE authority=? LIMIT 1;", (Authority,)
        ).fetchone()
        if str(tx["status"]).lower() == "paid":
            conn.commit()
            return success_page(int(tx["total_amount"] or tx["amount"]), ref_id or "-")

        user_id = int(tx["user_id"])
        chat_id = int(tx["chat_id"]) if tx["chat_id"] is not None else user_id
        amount = int(tx["amount"])
        wallet_reserved = int(tx["wallet_reserved"] or 0)
        total_amount = int(tx["total_amount"] or (amount + wallet_reserved))
        payment_type = str(tx["payment_type"] or "wallet").lower()
        buyer_type = str(tx["buyer_type"] or "customer")

        # Mark paid first (the unique pending guard makes this safe)
        conn.execute(
            "UPDATE zarinpal_transactions SET status='paid', ref_id=?, paid_at=? "
            "WHERE authority=? AND status='pending';",
            (ref_id, now_iso(), Authority),
        )

        # ---- wallet top-up ----
        if payment_type == "wallet":
            mark_wallet_charge(conn, user_id, amount)
            conn.commit()
            send_telegram_message(
                chat_id,
                f"کیف پول شما با موفقیت شارژ شد.\n"
                f"مبلغ: {amount:,} تومان\n"
                f"کد پیگیری: {ref_id}",
            )
            return success_page(amount, ref_id or "-")

        # ---- product purchase ----
        product_id = int(tx["product_id"])
        product = get_product(conn, product_id)
        if not product:
            conn.rollback()
            return error_page("محصول پیدا نشد. لطفاً با پشتیبانی تماس بگیرید.")

        title = str(product["title"])
        category = str(product["category"])

        # consume the reserved wallet portion (combined payment)
        deduct_wallet_reserved(conn, user_id, wallet_reserved)
        order_id = create_order(conn, user_id, category, product_id, title, total_amount, buyer_type)
        feed_item = claim_feed_item(conn, product_id)

        if feed_item:
            feed_id, feed_data = feed_item
            conn.commit()
            send_telegram_message(
                chat_id,
                (
                    "سفارش شما ثبت و تحویل شد.\n\n"
                    f"شماره سفارش: #{order_id}\n"
                    f"سرویس: {html.escape(title)}\n"
                    f"مبلغ کل: {total_amount:,} تومان\n"
                    f"کد پیگیری: {ref_id}\n\n"
                    f"<code>{html.escape(feed_data)}</code>"
                ),
                parse_mode="HTML",
            )
            if ADMIN_ID:
                send_telegram_message(
                    ADMIN_ID,
                    f"تحویل خودکار محصول انجام شد.\n\n"
                    f"Order ID: #{order_id}\nUser ID: {user_id}\n"
                    f"Product: {title} (#{product_id})\nFeed ID: {feed_id}",
                )
        else:
            # no stock -> queue for auto-delivery when admin refills
            enqueue_pending_delivery(conn, order_id, user_id, chat_id, product_id, title, total_amount)
            conn.commit()
            send_telegram_message(
                chat_id,
                (
                    "سفارش شما ثبت شد.\n\n"
                    f"شماره سفارش: #{order_id}\n"
                    f"سرویس: {title}\n"
                    f"مبلغ کل: {total_amount:,} تومان\n"
                    "موجودی این محصول فعلاً تکمیل است و به‌محض شارژ، خودکار ارسال می‌شود."
                ),
            )
            if ADMIN_ID:
                send_telegram_message(
                    ADMIN_ID,
                    f"سفارش پرداخت‌شده بدون موجودی ثبت شد.\n\n"
                    f"Order ID: #{order_id}\nUser ID: {user_id}\n"
                    f"Product: {title} (#{product_id})",
                )

        return success_page(total_amount, ref_id or "-")

    except HTTPException:
        raise
    except Exception:
        logger.exception("Payment callback failed")
        try:
            conn.rollback()
        except Exception:
            pass
        return error_page("خطای داخلی در پردازش پرداخت. لطفاً با پشتیبانی تماس بگیرید.")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Result pages (kept simple & Persian, as requested)
# ---------------------------------------------------------------------------
def success_page(amount, ref):
    return f"""
    <html dir="rtl"><head><meta charset="utf-8"><title>پرداخت موفق</title></head>
    <body style="text-align:center;font-family:tahoma, sans-serif;padding:32px">
        <h2 style="color:green">پرداخت با موفقیت انجام شد</h2>
        <p>مبلغ: {int(amount):,} تومان</p>
        <p>شماره پیگیری: {html.escape(str(ref))}</p>
        <br><a href="https://t.me/{html.escape(BOT_USERNAME)}">بازگشت به ربات</a>
    </body></html>
    """


def cancel_page():
    return f"""
    <html dir="rtl"><head><meta charset="utf-8"><title>پرداخت لغو شد</title></head>
    <body style="text-align:center;font-family:tahoma, sans-serif;padding:32px">
        <h2 style="color:red">پرداخت لغو شد</h2>
        <p>تراکنش توسط کاربر یا درگاه لغو شد.</p>
        <br><a href="https://t.me/{html.escape(BOT_USERNAME)}">بازگشت به ربات</a>
    </body></html>
    """


def error_page(message):
    return f"""
    <html dir="rtl"><head><meta charset="utf-8"><title>خطا</title></head>
    <body style="text-align:center;font-family:tahoma, sans-serif;padding:32px">
        <h2 style="color:orange">خطا در پرداخت</h2>
        <p>{html.escape(str(message))}</p>
        <br><a href="https://t.me/{html.escape(BOT_USERNAME)}">بازگشت به ربات</a>
    </body></html>
    """
