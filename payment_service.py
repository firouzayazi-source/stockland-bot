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

import html
import logging
import os
import sqlite3
import threading
import time
from datetime import datetime, timezone, date

import requests
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.concurrency import run_in_threadpool


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
from admin_panel import (router as _admin_router, _verify_session_cookie as _panel_verify_cookie,
                          _make_session as _panel_make_session)
app.include_router(_admin_router)

# API رسمی برای PWA/اپ‌ها
try:
    from api import router as _api_router
    app.include_router(_api_router)
    logger.info("✅ API router registered at /api/v1")
except Exception as _ex:
    logger.warning("API router not loaded: %s", _ex)

# کارشناسی هوشمند قیمت آیفون — هستهٔ مستقل، اگه نبود کل اپ کرش نکنه
try:
    from iphone_valuation.router import router as _iv_router
    app.include_router(_iv_router)
    logger.info("✅ iPhone valuation router registered at /api/v1/iphone")
except Exception as _ex:
    logger.warning("iPhone valuation router not loaded: %s", _ex)

# ── PWA استاتیک (/app) + مدیای آپلودی (/app-media) ─────────────────────────
try:
    from fastapi.staticfiles import StaticFiles
    _BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    _PWA_DIR = os.path.join(_BASE_DIR, "app")
    _PWA_MEDIA = os.path.join(_BASE_DIR, "app_media")
    os.makedirs(_PWA_MEDIA, exist_ok=True)
    if os.path.isdir(_PWA_DIR):
        app.mount("/app", StaticFiles(directory=_PWA_DIR, html=True), name="pwa")
        app.mount("/app-media", StaticFiles(directory=_PWA_MEDIA), name="pwa_media")
        logger.info("✅ PWA mounted at /app")
    else:
        logger.warning("PWA dir not found: %s", _PWA_DIR)
except Exception as _ex:
    logger.warning("PWA mount failed: %s", _ex)


_PWA_NO_CACHE_PATHS = {
    "/app/sw.js", "/app/", "/app", "/app/index.html",
    "/app/app.css", "/app/app.js", "/app/manifest.json",
}


@app.middleware("http")
async def _no_cache_pwa_shell(request, call_next):
    """sw.js/index.html/app.css/app.js نباید HTTP-cache بشن — وگرنه مرورگر/تلگرام
    هیچ‌وقت متوجه آپدیت نمی‌شه و کش PWA برای همیشه قدیمی می‌مونه. app.css/app.js
    از قبل با ?v=timestamp نسخه‌بندی می‌شن، ولی این لایهٔ دومه — اگه یه‌جا نسخه‌بندی
    عمل نکنه (باگ دیگه‌ای در sed یا هر چیز دیگه)، مرورگر بازم مجبوره از سرور بپرسه.

    برعکسش: بقیهٔ فایل‌های استاتیک زیر /app و /app-media (vendor، آیکون‌ها، مدیای
    آپلودی) اصلاً Cache-Control نداشتن — یعنی هر بار کامل از سرور دانلود می‌شدن.
    یک روز کش (نه بیشتر — چون app-media شامل فایل‌های قابل‌جایگزینی مثل آواتار
    کاربر با همون URL است، بخش ۲۱ CLAUDE.md) برای این مسیرها اضافه شد."""
    response = await call_next(request)
    try:
        path = request.url.path
        if path in _PWA_NO_CACHE_PATHS:
            response.headers["Cache-Control"] = "no-cache, must-revalidate"
            response.headers["Pragma"] = "no-cache"
        elif path.startswith("/app/") or path.startswith("/app-media/"):
            response.headers.setdefault("Cache-Control", "public, max-age=86400")
    except Exception:
        pass
    return response


@app.middleware("http")
async def _refresh_admin_session(request, call_next):
    """با هر فعالیت ادمین، تایمر idle (۵ دقیقه) را ریست می‌کند.
    ⚠️ عمداً از _verify_session_cookie (بدون کوئری دیتابیس) استفاده می‌کنه، نه
    _get_admin کامل — چون تنها کاری که این میدل‌ور لازمه بکنه تجدید کوکیه، نه
    گرفتن دسترسی‌های واقعی (که خودِ هندلر هر route جداگانه و با دادهٔ تازه چک
    می‌کنه). قبلاً هر درخواست /admin/* دوبار از دیتابیس ادمین می‌خوند — یک‌بار
    اینجا، یک‌بار توی خودِ هندلر — که روی حجم بالای ترافیک پنل قابل‌حس بود."""
    response = await call_next(request)
    try:
        path = request.url.path
        if path.startswith("/admin") and not path.endswith("/logout") and not path.endswith("/login"):
            admin_id = _panel_verify_cookie(request)
            if admin_id:
                fresh = _panel_make_session(admin_id)
                response.set_cookie("adm", fresh, max_age=300, httponly=True, samesite="lax")
    except Exception:
        pass
    return response


@app.middleware("http")
async def _security_headers(request, call_next):
    """هدرهای امنیتی پایه روی همهٔ پاسخ‌ها — بدون CSP (چون admin_panel._layout
    از اسکریپت این‌لاین استفاده می‌کنه و نیاز به یه پاس جدا و دقیق‌تر داره)."""
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "SAMEORIGIN"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.middleware("http")
async def _csrf_guard(request, call_next):
    """محافظت CSRF درجه‌دوم (defense-in-depth) برای فرم‌های پنل ادمین (بخش ۱۳
    آیتم ۶ سند: هیچ فرمی CSRF token ندارد، فقط SameSite=Lax کوکی).

    به‌جای اضافه‌کردن CSRF token به هزاران خط فرم HTML موجود در admin_panel.py
    (تغییری پرریسک و پراکنده روی کل فایل)، همون تکنیک توصیه‌شدهٔ OWASP به‌عنوان
    لایهٔ دوم استفاده شده: برای هر درخواست تغییردهنده‌ی وضعیت (POST/PUT/PATCH/
    DELETE) به /admin/*، هدر Origin (یا در نبودش Referer) باید با Host درخواست
    هم‌خوان باشه. اگه هیچ‌کدوم از این دو هدر نباشه (بعضی کلاینت‌های غیرمرورگری/
    قدیمی)، عمداً رد نمی‌شه — این یه لایهٔ دفاعی اضافه‌ست، نه جایگزین کامل CSRF
    token واقعی."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE") and request.url.path.startswith("/admin"):
        origin = request.headers.get("origin") or request.headers.get("referer") or ""
        host = request.headers.get("host", "")
        if origin and host:
            try:
                origin_host = origin.split("://", 1)[-1].split("/", 1)[0]
                if origin_host.split(":")[0].lower() != host.split(":")[0].lower():
                    return JSONResponse({"detail": "درخواست نامعتبر (CSRF)"}, status_code=403)
            except Exception:
                pass
    return await call_next(request)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def db_connect():
    """اتصال دیتابیس مسیر پرداخت/callback.
    ⚠️ رفع‌شده (ممیزی کامل پروژه): قبلاً همیشه sqlite3.connect خام می‌زد، مستقل
    از DB_DIALECT — یعنی روی سرور Postgres، تأیید پرداخت/تحویل محصول روی یه
    فایل SQLite فانتوم انجام می‌شد. حالا از db_conn.get_connection() استفاده
    می‌کنه (SQLite یا Postgres بر اساس env)."""
    import db_conn
    return db_conn.get_connection(DB_PATH)


def send_telegram_message(user_id: int, text: str, parse_mode: str | None = None) -> None:
    """Send a Telegram message directly via the Bot API (no bot instance needed)."""
    from tg_notify import send_telegram_message as _send
    _send(BOT_TOKEN, user_id, text, parse_mode=parse_mode)


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
            "gateway": "TEXT DEFAULT 'zarinpal'",
            "card_pan": "TEXT",
            "card_hash": "TEXT",
            "fee_type": "TEXT",
            "fee": "INTEGER",
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
        INSERT INTO pending_deliveries
            (order_id, user_id, chat_id, product_id, product_title, price, status, feed_id)
        VALUES (?, ?, ?, ?, ?, ?, 'pending', NULL)
        ON CONFLICT(order_id) DO UPDATE SET
            user_id=excluded.user_id, chat_id=excluded.chat_id, product_id=excluded.product_id,
            product_title=excluded.product_title, price=excluded.price, status=excluded.status,
            feed_id=excluded.feed_id;
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
# چند‌درگاهی (پنل‌محور، با failover خودکار)
# منطق هر درگاه در پکیج payment_gateways/ است (مثل iphone_valuation/ai_providers).
# این‌جا فقط لایهٔ هماهنگی: انتخاب درگاه‌های فعال، ترتیب اولویت، و failover.
# ---------------------------------------------------------------------------
def gateway_callback_url(gateway: str) -> str:
    """آدرس کال‌بک مخصوص هر درگاه: {base}/payment/callback/{gateway}. مسیر شامل نام درگاست
    تا هنگام بازگشت کاربر بدونیم با کدوم درگاه verify کنیم (پارامتر بازگشتی هر درگاه اسم
    متفاوتی داره)."""
    return payment_callback_url().rstrip("/") + "/" + gateway


def _resolve_gateway_config(gateway: str) -> dict | None:
    """config یک درگاه — اول از پنل (جدول payment_gateways)، اگه نبود برای زرین‌پال از env
    قدیمی (سازگاری عقب‌رو: تا وقتی ادمین پنل رو تنظیم نکرده، زرین‌پال از .env کار می‌کنه)."""
    try:
        import db as _db
        row = _db.get_payment_gateway(gateway)
    except Exception:
        row = None
    if row:
        cfg = dict(row.get("credentials") or {})
        # ردیف پنل فقط وقتی «برنده» است که واقعاً اعتبار داشته باشه (کلید غیرخالی یا sandbox
        # روشن)؛ یه ردیف خالی (مثلاً درگاهی که ادمین ذخیره کرده ولی کلید نذاشته) نباید
        # جلوی fallback به env رو بگیره — وگرنه زرین‌پالِ env بی‌دلیل غیرقابل‌استفاده می‌شه.
        has_cred = bool(row.get("sandbox")) or any(str(v).strip() for v in cfg.values())
        if has_cred:
            cfg["sandbox"] = bool(row.get("sandbox"))
            return cfg
    if gateway == "zarinpal" and MERCHANT_ID:
        return {"merchant_id": MERCHANT_ID,
                "sandbox": os.getenv("ZARINPAL_SANDBOX", "") in ("1", "true", "True")}
    return None


def _gateways_for_create() -> list:
    """ترتیب درگاه‌ها برای failover — درگاه‌های فعال پنل به‌ترتیب اولویت؛ اگه پنل خالی بود،
    fallback به زرین‌پالِ env تا چیزی نشکنه (رفتار قبل از این فیچر حفظ می‌شه)."""
    try:
        import db as _db
        active = _db.get_active_payment_gateways()
    except Exception:
        active = []
    if active:
        return [g["gateway"] for g in active]
    return ["zarinpal"] if MERCHANT_ID else []


def _run_gateway_failover(amount_toman: int, description: str):
    """روی درگاه‌های فعال به‌ترتیب اولویت حلقه می‌زنه؛ اولین موفق رو برمی‌گردونه
    (gateway_code, authority, payment_url)، یا None اگه همه شکست خوردن."""
    from payment_gateways import get_gateway_module
    last_error = ""
    for gw in _gateways_for_create():
        mod = get_gateway_module(gw)
        cfg = _resolve_gateway_config(gw)
        if not mod or not cfg:
            continue
        try:
            res = mod.create_payment(amount_toman, gateway_callback_url(gw), description, cfg)
        except Exception as exc:
            last_error = str(exc)
            logger.error("Gateway %s raised on create: %s", gw, exc)
            continue
        if res.get("ok") and res.get("payment_url"):
            logger.info("Gateway %s created payment (authority=%s)", gw, res.get("authority"))
            return (gw, res["authority"], res["payment_url"])
        last_error = res.get("error", "")
        logger.error("Gateway %s create failed: %s", gw, last_error)
    logger.error("All payment gateways failed. last_error=%s", last_error)
    return None


# ---------------------------------------------------------------------------
# App lifecycle: run the Telegram bot in a background thread (single process)
# ---------------------------------------------------------------------------
@app.on_event("startup")
def on_startup() -> None:
    ensure_schema()
    maybe_start_bot_polling()
    try:
        from admin_panel import _start_auto_backup_thread
        _start_auto_backup_thread()
    except Exception:
        pass


_bot_module_ref = None  # برای webhook mode


def maybe_start_bot_polling() -> None:
    """
    نقطه‌ی ورود ربات — بر اساس تنظیم ذخیره‌شده در bot_config شروع می‌کند:
    - bot_run_mode = 'webhook' → webhook ست می‌شود
    - bot_run_mode = 'polling' → thread polling استارت می‌شود
    - bot_run_mode = 'stopped' → ربات متوقف می‌ماند تا از پنل روشن شود
    اگر تنظیم نبود، از env var USE_WEBHOOK استفاده می‌کند (سازگاری قدیم).
    """
    global _bot_thread_started, _bot_module_ref
    if _bot_thread_started or not RUN_BOT_IN_PAYMENT_SERVICE or not BOT_TOKEN:
        return

    import bot as bot_module
    _bot_module_ref = bot_module
    bot_module.init_db(bot_module.DB_PATH)
    bot_module.ensure_pending_schema()
    bot_module._ensure_delivery_table()
    bot_module.ticket_ensure_schema()

    # تصمیم اولیه: از bot_config یا env
    try:
        from db import get_cfg
        mode = (get_cfg("bot_run_mode", "") or "").strip().lower()
    except Exception:
        mode = ""
    if mode not in ("webhook", "polling", "stopped"):
        # سازگاری قدیم: اگه تنظیم نبود، از env
        mode = "webhook" if os.getenv("USE_WEBHOOK", "0") == "1" else "polling"

    # endpoint webhook در هر حالتی روی FastAPI ثبت می‌شود، فقط تلگرام تصمیم می‌گیرد
    # از آن استفاده کند یا نه. این کار سوییچ نرم را ممکن می‌سازد.
    _register_webhook_endpoint(bot_module)

    if mode == "stopped":
        logger.info("Bot run mode: stopped (waiting for panel action)")
        _bot_thread_started = True
        return

    if mode == "webhook":
        if not _activate_webhook(bot_module):
            # اگه webhook شکست بخوره (مثلاً DNS/SSL خراب باشه)، ربات نباید کاملاً
            # بی‌صدا بمونه — فال‌بک خودکار به polling تا وقتی مشکل webhook حل بشه
            logger.warning("Webhook activation failed at startup — falling back to polling so the bot doesn't stay silent")
            _activate_polling(bot_module)
    else:
        _activate_polling(bot_module)

    _bot_thread_started = True


# ── سه تابع کمکی برای مدیریت رانتایم ───────────────────────────────────

_polling_thread = None
_polling_stop_flag = threading.Event()


def _register_webhook_endpoint(bot_module) -> None:
    """endpoint webhook را روی FastAPI ثبت می‌کند (idempotent)."""
    if getattr(app, "_webhook_registered", False):
        return
    from config import WEBHOOK_SECRET
    from fastapi import Request as _Req, HTTPException as _HTTPExc
    from telebot import types as _tg_types

    webhook_path = f"/telegram/webhook/{BOT_TOKEN}"

    @app.post(webhook_path)
    async def _telegram_webhook(request: _Req):
        hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
        if hdr != WEBHOOK_SECRET:
            raise _HTTPExc(status_code=403, detail="invalid secret")
        try:
            payload = await request.json()
            update  = _tg_types.Update.de_json(payload)
            threading.Thread(
                target=lambda: bot_module.bot.process_new_updates([update]),
                name="tg-update-handler",
                daemon=True,
            ).start()
        except Exception as ex:
            logger.exception("webhook processing error: %s", ex)
        return {"ok": True}

    app._webhook_registered = True


def _activate_webhook(bot_module) -> bool:
    """فعال کردن webhook + توقف polling اگر در حال اجراست."""
    from config import WEBHOOK_BASE_URL, WEBHOOK_SECRET
    _stop_polling_thread()
    webhook_url = f"{WEBHOOK_BASE_URL}/telegram/webhook/{BOT_TOKEN}"
    try:
        bot_module.bot.remove_webhook()
        import time as _t; _t.sleep(1)
        bot_module.bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=["message", "callback_query", "inline_query"],
            drop_pending_updates=False,
        )
        logger.info("✅ Webhook activated: %s", webhook_url)
        try:
            from db import set_cfg
            set_cfg("bot_run_mode", "webhook")
        except Exception: pass
        return True
    except Exception as ex:
        logger.error("Webhook activation failed: %s", ex)
        return False


def _activate_polling(bot_module) -> bool:
    """فعال کردن polling در یک thread + حذف webhook از سمت تلگرام."""
    global _polling_thread
    if _polling_thread and _polling_thread.is_alive():
        return True  # از قبل روشنه
    try:
        bot_module.bot.delete_webhook(drop_pending_updates=False)
    except Exception as ex:
        logger.warning("delete_webhook: %s", ex)

    _polling_stop_flag.clear()

    def runner() -> None:
        import time
        logger.info("✅ Polling activated")
        backoff = 5
        while not _polling_stop_flag.is_set():
            try:
                bot_module.bot.infinity_polling(
                    timeout=20,
                    long_polling_timeout=10,
                    allowed_updates=["message", "callback_query"],
                    restart_on_change=False,
                )
                backoff = 5
            except Exception as ex:
                if _polling_stop_flag.is_set():
                    break
                err_str = str(ex)
                if "409" in err_str or "Conflict" in err_str:
                    logger.warning("409 Conflict — waiting %ds", backoff)
                    time.sleep(backoff)
                    backoff = min(backoff * 2, 60)
                    try: bot_module.bot.delete_webhook(drop_pending_updates=True)
                    except Exception: pass
                else:
                    logger.exception("Polling crashed; restarting in 5s")
                    time.sleep(5)
        logger.info("Polling thread exited")

    _polling_thread = threading.Thread(target=runner, name="stockland-polling", daemon=True)
    _polling_thread.start()
    try:
        from db import set_cfg
        set_cfg("bot_run_mode", "polling")
    except Exception: pass
    return True


def _stop_polling_thread() -> None:
    """polling thread را به آرامی متوقف می‌کند."""
    global _polling_thread
    if not _polling_thread or not _polling_thread.is_alive():
        return
    _polling_stop_flag.set()
    try:
        # trick برای بیدار کردن infinity_polling
        import bot as _bm
        _bm.bot.stop_polling()
    except Exception:
        pass
    _polling_thread.join(timeout=3)
    _polling_thread = None


# ── API عمومی برای پنل — سوییچ نرم بدون restart ───────────────────────

def switch_bot_mode(new_mode: str) -> tuple:
    """
    تغییر حالت ربات از پنل. new_mode ∈ {'webhook','polling','stopped'}
    Returns: (ok: bool, message: str)
    """
    global _bot_thread_started
    if new_mode not in ("webhook", "polling", "stopped"):
        return False, "حالت نامعتبر"
    try:
        import bot as bot_module
    except Exception as ex:
        return False, f"خطای import ربات: {ex}"

    _register_webhook_endpoint(bot_module)

    if new_mode == "webhook":
        ok = _activate_webhook(bot_module)
        if ok:
            return True, "Webhook فعال شد"
        # فال‌بک خودکار به polling تا ربات به‌خاطر خطای webhook (مثلاً DNS/SSL) بی‌صدا نمونه
        _activate_polling(bot_module)
        return False, "خطا در فعال‌سازی Webhook — به‌صورت خودکار روی Polling باقی ماند تا مشکل رفع شود"
    if new_mode == "polling":
        try:
            bot_module.bot.remove_webhook()
        except Exception: pass
        ok = _activate_polling(bot_module)
        return (ok, "Polling فعال شد" if ok else "خطا در فعال‌سازی Polling")
    # stopped
    _stop_polling_thread()
    try:
        bot_module.bot.remove_webhook()
        from db import set_cfg
        set_cfg("bot_run_mode", "stopped")
    except Exception: pass
    return True, "ربات متوقف شد"


@app.get("/health")
def health():
    conn = db_connect()
    try:
        conn.execute("SELECT 1;").fetchone()
        return {"ok": True, "bot_polling": _bot_thread_started}
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# 1) Create a payment
# ---------------------------------------------------------------------------
@app.post("/payment/create")
def create_payment(payload: dict, request: Request):
    # این مسیر فقط برای فراخوانی داخلی (services/payments.py و api.py، همون پروسه)
    # طراحی شده — بدون این چک، هرکسی از اینترنت می‌تونه با user_id/wallet_reserved
    # دلخواه یه تراکنش بسازه و بعد از پرداخت مبلغ کوچیک amount، کل wallet_reserved
    # قربانی رو خالی کنه (_finalize_paid_tx). چون uvicorn پشت nginx روی 127.0.0.1
    # گوش می‌ده، چک IP به‌تنهایی این دو حالت رو از هم تشخیص نمی‌ده؛ به‌جاش یه راز
    # داخلی (INTERNAL_API_SECRET، خودکار تولیدشده مثل WEBHOOK_SECRET) استفاده می‌شه.
    import hmac as _hmac
    from config import INTERNAL_API_SECRET
    hdr = request.headers.get("X-Internal-Secret", "")
    if not _hmac.compare_digest(hdr, INTERNAL_API_SECRET):
        raise HTTPException(403, "forbidden")
    ensure_schema()
    if not MERCHANT_ID:
        raise HTTPException(500, "ZARINPAL_MERCHANT_ID is not configured")

    try:
        user_id = int(payload.get("user_id"))
        amount_toman = int(payload.get("amount", 0))
        wallet_reserved = int(payload.get("wallet_reserved", 0) or 0)
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid input")

    # ریت‌لیمیت روی خودِ user_id (نه IP) — چون این مسیر همیشه از داخل همون
    # پروسه (services/payments.py, api.py) صدا زده می‌شه، IP همیشه 127.0.0.1
    # است؛ این لایه محافظت در برابر یه باگ/حلقهٔ تکراری تو یکی از فراخوان‌های
    # داخلیه که بی‌وقفه برای یه کاربر تراکنش می‌سازه، نه محافظت شبکه‌ای.
    from rate_limit import is_rate_limited
    _blocked, _wait = is_rate_limited("payment_create", str(user_id), max_calls=10, window_seconds=60)
    if _blocked:
        raise HTTPException(429, f"تعداد درخواست بیش از حد مجاز است. {_wait} ثانیه دیگر تلاش کنید.")

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

        description = f"Stockland {payment_type} payment {product_title} user {user_id}".strip()
        chosen = _run_gateway_failover(amount_toman, description)
        if not chosen:
            raise HTTPException(400, "ایجاد تراکنش در همهٔ درگاه‌ها ناموفق بود")
        gateway_code, authority, payment_url = chosen

        total_amount = amount_toman + wallet_reserved
        conn.execute(
            """
            INSERT INTO zarinpal_transactions
                (user_id, amount, authority, status, created_at, payment_type,
                 product_id, wallet_reserved, total_amount, buyer_type, chat_id, gateway)
            VALUES (?, ?, ?, 'pending', ?, ?, ?, ?, ?, ?, ?, ?);
            """,
            (user_id, amount_toman, authority, now_iso(), payment_type,
             product_id, wallet_reserved, total_amount, buyer_type, chat_id, gateway_code),
        )
        conn.commit()
    finally:
        conn.close()

    return {"authority": authority, "payment_url": payment_url, "gateway": gateway_code}


# ---------------------------------------------------------------------------
# 2) Payment callback (user returns from the gateway) — چند‌درگاهی
# ---------------------------------------------------------------------------
def _finalize_paid_tx(conn, tx, ref_id, authority, extra: dict | None = None):
    """بخش نهایی‌سازی پرداخت موفق (شارژ کیف‌پول یا تحویل محصول) — مشترک بین کال‌بک همهٔ
    درگاه‌ها. فرض: قفل BEGIN IMMEDIATE از قبل گرفته شده و status هنوز paid نیست. منطق
    این بخش عیناً همون رفتار قبلی زرین‌پاله (شامل بازگشت وجه به کیف‌پول در race condition
    موجودی) — فقط درگاه‌آگاه شده. `extra` فیلدهای اختیاری حسابداری (card_pan/card_hash/
    fee_type/fee) از verify_payment است — هر درگاهی که پشتیبانی نکنه، خالی می‌مونه."""
    extra = extra or {}
    user_id = int(tx["user_id"])
    chat_id = int(tx["chat_id"]) if tx["chat_id"] is not None else user_id
    amount = int(tx["amount"])
    wallet_reserved = int(tx["wallet_reserved"] or 0)
    total_amount = int(tx["total_amount"] or (amount + wallet_reserved))
    payment_type = str(tx["payment_type"] or "wallet").lower()
    buyer_type = str(tx["buyer_type"] or "customer")

    # Mark paid first (the unique pending guard makes this safe)
    conn.execute(
        "UPDATE zarinpal_transactions SET status='paid', ref_id=?, paid_at=?, "
        "card_pan=?, card_hash=?, fee_type=?, fee=? WHERE authority=? AND status='pending';",
        (ref_id, now_iso(), extra.get("card_pan") or "", extra.get("card_hash") or "",
         extra.get("fee_type") or "", extra.get("fee"), authority),
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
        # send_telegram_message_with_id به‌جای wrapper معمولی — message_id لازمه تا
        # ذخیره بشه در delivery_messages؛ بدونش «برگشت» پنل نه می‌تونه این پیام رو از
        # چت کاربر پاک کنه نه (برای این مسیر گیت‌وی) می‌تونست feed رو به موجودی برگردونه
        # (بخش ۴۰ CLAUDE.md).
        from tg_notify import send_telegram_message_with_id
        _ok, _msg_id = send_telegram_message_with_id(
            BOT_TOKEN, chat_id,
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
        try:
            from db import order_set_feed_id
            order_set_feed_id(order_id, feed_id)
            if _msg_id:
                _dc = db_connect()
                try:
                    _dc.execute("""
                        CREATE TABLE IF NOT EXISTS delivery_messages (
                            feed_id INTEGER PRIMARY KEY, order_id INTEGER,
                            chat_id INTEGER NOT NULL, message_id INTEGER NOT NULL, created_at TEXT NOT NULL
                        );
                    """)
                    _dc.execute(
                        "INSERT INTO delivery_messages (feed_id, order_id, chat_id, message_id, created_at) "
                        "VALUES (?,?,?,?,?) ON CONFLICT(feed_id) DO UPDATE SET "
                        "order_id=excluded.order_id, chat_id=excluded.chat_id, "
                        "message_id=excluded.message_id, created_at=excluded.created_at;",
                        (int(feed_id), int(order_id), int(chat_id), int(_msg_id), now_iso())
                    )
                    _dc.commit()
                finally:
                    _dc.close()
        except Exception:
            logger.exception("delivery_messages insert failed (_finalize_paid_tx)")
        if ADMIN_ID:
            send_telegram_message(
                ADMIN_ID,
                f"تحویل خودکار محصول انجام شد.\n\n"
                f"Order ID: #{order_id}\nUser ID: {user_id}\n"
                f"Product: {title} (#{product_id})\nFeed ID: {feed_id}",
            )
    else:
        # موجودی درست همین چند لحظه (بین ساخت لینک پرداخت و بازگشت از درگاه) توسط خریدار
        # دیگری تموم شده — استثنای نادر race condition. طبق سیاست پروژه هیچ محصولی در آینده
        # ارسال نمی‌شه: کل مبلغ (سهم کیف‌پول + سهم درگاه) به کیف‌پول برمی‌گرده، نه صف انتظار.
        conn.execute("UPDATE orders SET status='returned', returned_at=? WHERE id=?;",
                     (now_iso(), order_id))
        mark_wallet_charge(conn, user_id, total_amount)
        conn.commit()
        send_telegram_message(
            chat_id,
            (
                "❌ متأسفانه موجودی این محصول لحظاتی پیش به پایان رسید.\n\n"
                f"مبلغ <b>{total_amount:,}</b> تومان به کیف‌پول شما بازگردانده شد.\n"
                f"کد پیگیری: {ref_id}"
            ),
            parse_mode="HTML",
        )
        if ADMIN_ID:
            send_telegram_message(
                ADMIN_ID,
                f"⚠️ سفارش بدون موجودی — مبلغ به کیف‌پول کاربر بازگشت.\n\n"
                f"Order ID: #{order_id}\nUser ID: {user_id}\n"
                f"Product: {title} (#{product_id})",
            )

    return success_page(total_amount, ref_id or "-")


def _handle_payment_callback(gw: str, query: dict, form: dict):
    """کال‌بک عمومی درگاه‌آگاه — پارامترهای بازگشتی رو با ماژول درگاه parse می‌کنه،
    تراکنش رو پیدا و با همون درگاهی که باهاش ساخته شده verify می‌کنه، بعد نهایی‌سازی."""
    ensure_schema()
    from payment_gateways import get_gateway_module
    mod = get_gateway_module(gw) or get_gateway_module("zarinpal")
    parsed = mod.parse_callback(query or {}, form or {})
    authority = (parsed.get("authority") or "").strip()
    if not authority:
        return error_page("شناسهٔ تراکنش نامعتبر است.")

    conn = db_connect()
    try:
        tx = conn.execute(
            "SELECT * FROM zarinpal_transactions WHERE authority=? LIMIT 1;", (authority,)
        ).fetchone()
        if not tx:
            return error_page("تراکنش پیدا نشد.")

        # Already processed -> show success again (idempotent)
        if str(tx["status"]).lower() == "paid":
            return success_page(int(tx["total_amount"] or tx["amount"]), tx["ref_id"] or "-")

        # کاربر لغو کرد یا درگاه نتیجهٔ ناموفق برگردوند
        if not parsed.get("success"):
            conn.execute(
                "UPDATE zarinpal_transactions SET status='canceled', error=? "
                "WHERE authority=? AND status='pending';",
                ("gateway returned non-success status", authority),
            )
            conn.commit()
            return cancel_page()

        # verify با همون درگاهی که تراکنش باهاش ساخته شده (نه لزوماً gw مسیر)
        tx_gw = str(tx["gateway"] or gw or "zarinpal")
        vmod = get_gateway_module(tx_gw) or mod
        vcfg = _resolve_gateway_config(tx_gw) or {}
        try:
            vres = vmod.verify_payment(authority, int(tx["amount"]), vcfg)
        except Exception as exc:
            vres = {"ok": False, "ref_id": "", "error": str(exc)}
        if not vres.get("ok"):
            conn.execute(
                "UPDATE zarinpal_transactions SET error=? WHERE authority=?;",
                (str(vres.get("error") or "")[:1000], authority),
            )
            conn.commit()
            return error_page("پرداخت تایید نشد.")
        ref_id = vres.get("ref_id", "")

        # Lock and re-check (idempotency under concurrent callbacks)
        conn.execute("BEGIN IMMEDIATE;")
        tx = conn.execute(
            "SELECT * FROM zarinpal_transactions WHERE authority=? LIMIT 1;", (authority,)
        ).fetchone()
        if str(tx["status"]).lower() == "paid":
            conn.commit()
            return success_page(int(tx["total_amount"] or tx["amount"]), ref_id or "-")

        extra = {k: vres.get(k) for k in ("card_pan", "card_hash", "fee_type", "fee")}
        return _finalize_paid_tx(conn, tx, ref_id, authority, extra)

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


@app.get("/payment/callback", response_class=HTMLResponse)
def payment_callback(request: Request):
    """کال‌بک قدیمی بدون /{gateway} — تراکنش‌های زرین‌پالِ در جریان که قبل از فیچر
    چند‌درگاهی ساخته شدن، callback‌شون به این آدرس برمی‌گرده. سازگاری عقب‌رو."""
    return _handle_payment_callback("zarinpal", dict(request.query_params), {})


@app.api_route("/payment/callback/{gw}", methods=["GET", "POST"], response_class=HTMLResponse)
async def payment_callback_gw(gw: str, request: Request):
    """کال‌بک درگاه‌آگاه — نام درگاه در مسیره. هم GET (اکثر درگاه‌ها با ریدایرکت مرورگر)
    هم POST (برخی درگاه‌ها فرم POST می‌فرستن) پشتیبانی می‌شه.
    _handle_payment_callback خودش synchronous است (SQLite خام + requests.post به درگاه
    تا ۱۵ ثانیه + requests.post به تلگرام تا ۱۰ ثانیه) — بدون run_in_threadpool، این
    async def مستقیم event loop مشترک پنل/مینی‌اپ/وبهوک رو تا ~۲۵ ثانیه بلاک می‌کرد."""
    query = dict(request.query_params)
    form = {}
    if request.method == "POST":
        try:
            form = dict(await request.form())
        except Exception:
            form = {}
    return await run_in_threadpool(_handle_payment_callback, gw, query, form)


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
