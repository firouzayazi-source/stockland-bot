from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
import sqlite3
import os
import requests
from datetime import datetime

# ================= CONFIG =================

DB_PATH = os.getenv("DB_PATH")
if not DB_PATH:
    raise RuntimeError("DB_PATH environment variable is required")

MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID")
if not MERCHANT_ID:
    raise RuntimeError("ZARINPAL_MERCHANT_ID environment variable is required")

REQUEST_URL = os.getenv(
    "ZARINPAL_REQUEST_URL",
    "https://api.zarinpal.com/pg/v4/payment/request.json"
)

VERIFY_URL = os.getenv(
    "ZARINPAL_VERIFY_URL",
    "https://api.zarinpal.com/pg/v4/payment/verify.json"
)

CALLBACK_URL = os.getenv("BASE_CALLBACK_URL")
if not CALLBACK_URL:
    raise RuntimeError("BASE_CALLBACK_URL environment variable is required")

MIN_AMOUNT = int(os.getenv("MIN_TOPUP_AMOUNT", "10000"))

BOT_TOKEN = os.getenv("BOT_TOKEN")

app = FastAPI()

# ================= DB =================

def get_db():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

def now():
    return datetime.utcnow().isoformat()

# ================= TELEGRAM =================

def send_telegram_message(user_id: int, text: str):
    if not BOT_TOKEN:
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user_id,
                "text": text
            },
            timeout=10
        )
    except Exception:
        pass

# ================= HEALTH =================

@app.get("/health")
def health():
    return {"status": "ok"}

# ================= CREATE PAYMENT =================

@app.post("/payment/create")
def create_payment(payload: dict):

    try:
        user_id = int(payload.get("user_id"))
        amount_toman = int(payload.get("amount", 0))
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid input")

    payment_type = (payload.get("payment_type") or "wallet").lower()
    product_id = payload.get("product_id")
    wallet_reserved = int(payload.get("wallet_reserved", 0) or 0)

    if amount_toman < MIN_AMOUNT:
        raise HTTPException(400, f"Minimum amount is {MIN_AMOUNT}")

    amount_rial = amount_toman * 10

    try:
        response = requests.post(
            REQUEST_URL,
            json={
                "merchant_id": MERCHANT_ID,
                "amount": amount_rial,
                "callback_url": CALLBACK_URL,
                "description": f"{payment_type} payment user {user_id}"
            },
            timeout=15
        )
        result = response.json()
    except Exception:
        raise HTTPException(500, "Zarinpal request failed")

    if result.get("data", {}).get("code") != 100:
        raise HTTPException(400, result)

    authority = result["data"]["authority"]

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO zarinpal_transactions
        (user_id, amount, authority, status, created_at, payment_type, product_id, wallet_reserved)
        VALUES (?, ?, ?, 'pending', ?, ?, ?, ?)
    """, (
        user_id,
        amount_toman,
        authority,
        now(),
        payment_type,
        product_id,
        wallet_reserved
    ))

    conn.commit()
    conn.close()

    return {
        "authority": authority,
        "payment_url": f"https://www.zarinpal.com/pg/StartPay/{authority}"
    }

# ================= CALLBACK =================

@app.get("/payment/callback", response_class=HTMLResponse)
def payment_callback(Authority: str = None, Status: str = None):

    if not Authority:
        return error_page("پارامتر Authority نامعتبر است")

    if Status != "OK":
        return cancel_page()

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT *
        FROM zarinpal_transactions
        WHERE authority=? AND status='pending'
    """, (Authority,))
    tx = cur.fetchone()

    if not tx:
        conn.close()
        return error_page("تراکنش یافت نشد")

    amount_toman = tx["amount"]
    payment_type = (tx["payment_type"] or "wallet").lower()
    wallet_reserved = tx["wallet_reserved"] or 0
    user_id = tx["user_id"]
    product_id = tx["product_id"]

    # -------- VERIFY --------

    try:
        verify_response = requests.post(
            VERIFY_URL,
            json={
                "merchant_id": MERCHANT_ID,
                "amount": amount_toman * 10,
                "authority": Authority
            },
            timeout=15
        )
        verify_data = verify_response.json()
    except Exception:
        conn.close()
        return error_page("خطا در تایید تراکنش")

    if verify_data.get("data", {}).get("code") != 100:
        conn.close()
        return error_page("پرداخت تایید نشد")

    ref_id = verify_data["data"]["ref_id"]

    # -------- MARK PAID --------

    cur.execute("""
        UPDATE zarinpal_transactions
        SET status='paid'
        WHERE authority=?
    """, (Authority,))
    conn.commit()

    # =====================================================
    # PRODUCT PAYMENT
    # =====================================================
    if payment_type == "product":

        # کسر سهم کیف پول
        if wallet_reserved > 0:
            cur.execute("""
                UPDATE wallets
                SET balance = balance - ?, updated_at=?
                WHERE user_id=?
            """, (wallet_reserved, now(), user_id))
            conn.commit()

        # تحویل محصول
        cur.execute("""
            SELECT id, data
            FROM feeds
            WHERE product_id=? AND claimed=0
            ORDER BY id ASC
            LIMIT 1
        """, (product_id,))
        feed = cur.fetchone()

        if feed:
            feed_id = feed["id"]
            feed_data = feed["data"]

            cur.execute("UPDATE feeds SET claimed=1 WHERE id=?", (feed_id,))
            conn.commit()

            send_telegram_message(
                user_id,
                f"سفارش ثبت و تحویل شد ✅\n\n"
                f"مبلغ: {amount_toman:,} تومان\n\n"
                f"{feed_data}"
            )
        else:
            cur.execute("""
                INSERT INTO pending_deliveries
                (user_id, product_id, created_at)
                VALUES (?, ?, ?)
            """, (user_id, product_id, now()))
            conn.commit()

            send_telegram_message(
                user_id,
                "سفارش ثبت شد ✅\n"
                "موجودی فعلاً تکمیل است.\n"
                "در اولین فرصت ارسال خواهد شد."
            )

        conn.close()
        return success_page(amount_toman, ref_id)

    # =====================================================
    # WALLET CHARGE
    # =====================================================

    cur.execute("""
        INSERT INTO wallets (user_id, balance, updated_at)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id)
        DO UPDATE SET
            balance = wallets.balance + excluded.balance,
            updated_at = excluded.updated_at
    """, (user_id, amount_toman, now()))

    conn.commit()
    conn.close()
    return success_page(amount_toman, ref_id)

# ================= HTML PAGES =================

def success_page(amount, ref):
    return f"""
    <html>
    <head><meta charset="utf-8"><title>پرداخت موفق</title></head>
    <body style="text-align:center;font-family:tahoma">
        <h2 style="color:green">پرداخت با موفقیت انجام شد ✅</h2>
        <p>مبلغ: {amount:,} تومان</p>
        <p>شماره پیگیری: {ref}</p>
        <br>
        <a href="https://t.me/stock_land_bot">بازگشت به ربات</a>
    </body>
    </html>
    """

def cancel_page():
    return """
    <html>
    <head><meta charset="utf-8"><title>پرداخت لغو شد</title></head>
    <body style="text-align:center;font-family:tahoma">
        <h2 style="color:red">پرداخت لغو شد ❌</h2>
        <p>تراکنش لغو شد.</p>
        <br>
        <a href="https://t.me/stock_land_bot">بازگشت به ربات</a>
    </body>
    </html>
    """

def error_page(message):
    return f"""
    <html>
    <head><meta charset="utf-8"><title>خطا</title></head>
    <body style="text-align:center;font-family:tahoma">
        <h2 style="color:orange">خطا در پرداخت ⚠️</h2>
        <p>{message}</p>
        <br>
        <a href="https://t.me/stock_land_bot">بازگشت به ربات</a>
    </body>
    </html>
    """