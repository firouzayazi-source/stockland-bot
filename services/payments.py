"""Client-side payment helper (runs inside the Telegram bot).

This module is the ONLY bridge between the bot and the payment service.
It does not talk to Zarinpal directly; it asks the payment service
(``payment_service.py``) to create a transaction and returns the gateway
URL to the user.

Platform independence:
    The payment service location is read from ``PAYMENT_API_BASE_URL``.
    Today the bot and payment service run in one process on Railway, so the
    default ``http://127.0.0.1:8000`` works. Tomorrow, if the payment service
    moves to a VPS, only this env var changes -- no code edits.
"""

import os
import logging

import requests
from telebot import types

logger = logging.getLogger("inox_bot")


def _default_payment_base_url() -> str:
    """Resolve where the payment service lives.

    Priority:
      1. PAYMENT_API_BASE_URL  (explicit override -- use this for a VPS later)
      2. http://127.0.0.1:$PORT  (same process on Railway; PORT is always set)
      3. http://127.0.0.1:8000  (local fallback)
    """
    explicit = os.getenv("PAYMENT_API_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    port = os.getenv("PORT") or "8000"
    return f"http://127.0.0.1:{port}"


# Where the payment service lives. Same machine/process by default.
PAYMENT_API_BASE_URL = _default_payment_base_url()

# اگه PHP_PAYMENT_URL ست شده، پرداخت از طریق PHP هاست انجام می‌شه
PHP_PAYMENT_URL = (os.getenv("PHP_PAYMENT_URL") or "").rstrip("/")
PHP_SECRET      = os.getenv("PHP_SECRET") or ""

# How long to wait for the payment service before giving up.
PAYMENT_API_TIMEOUT = int(os.getenv("PAYMENT_API_TIMEOUT", "20"))


def start_wallet_charge_payment(
    bot,
    message,
    uid,
    amount,
    clear_user_state,
    payment_type="wallet",
    product_id=None,
    wallet_reserved=0,
):
    """Ask the payment service to create a Zarinpal transaction.

    amount: gateway amount in Toman (what the user pays at the gateway).
    payment_type: "wallet" (top-up) or "product" (buy a product).
    product_id: required when payment_type == "product".
    wallet_reserved: Toman already covered by the wallet (combined payment).
    """

    # ---- validate inputs ----
    try:
        amount = int(amount)
        wallet_reserved = int(wallet_reserved or 0)
    except (TypeError, ValueError):
        logger.error("Invalid amount/wallet_reserved format")
        bot.send_message(message.chat.id, "خطا در مبلغ پرداخت.")
        clear_user_state(uid)
        return

    if amount <= 0:
        logger.error("Payment amount <= 0")
        bot.send_message(message.chat.id, "مبلغ پرداخت نامعتبر است.")
        clear_user_state(uid)
        return

    payload = {
        "user_id": int(uid),
        "amount": amount,
        "payment_type": payment_type,
        "product_id": product_id,
        "wallet_reserved": wallet_reserved,
        "chat_id": getattr(message.chat, "id", uid),
    }

    logger.info("PAYMENT REQUEST -> %s", payload)

    # ─── اگه PHP_PAYMENT_URL ست شده: از PHP هاست استفاده کن ──────────────
    if PHP_PAYMENT_URL and PHP_SECRET:
        _call_url = PHP_PAYMENT_URL
        _headers  = {
            "Content-Type": "application/json",
            "X-Stockland-Secret": PHP_SECRET,
        }
        logger.info("Using PHP bridge: %s", _call_url)
    else:
        _call_url = f"{PAYMENT_API_BASE_URL}/payment/create"
        _headers  = {"Content-Type": "application/json"}
        logger.info("Using Railway payment service: %s", _call_url)

    # ---- call the payment service ----
    try:
        resp = requests.post(
            _call_url,
            json=payload,
            headers=_headers,
            timeout=PAYMENT_API_TIMEOUT,
        )
        logger.info("PAYMENT RESPONSE STATUS -> %s", resp.status_code)
        logger.info("PAYMENT RESPONSE BODY -> %s", resp.text[:500])
    except Exception:
        logger.exception("Could not reach payment service")
        bot.send_message(
            message.chat.id,
            "خطا در ارتباط با سیستم پرداخت. لطفاً چند لحظه بعد دوباره تلاش کنید.",
        )
        clear_user_state(uid)
        return

    # ---- parse response ----
    try:
        data = resp.json()
    except Exception:
        logger.error("Payment service returned non-JSON: %s", resp.text[:500])
        bot.send_message(message.chat.id, "خطا در ایجاد تراکنش درگاه.")
        clear_user_state(uid)
        return

    if resp.status_code != 200 or not data.get("payment_url"):
        # surface a friendly reason when the service provides one
        detail = ""
        if isinstance(data, dict):
            detail = str(data.get("detail") or data.get("error") or "")
        logger.error("Bad response from payment service: %s", data)
        msg = "خطا در ایجاد تراکنش درگاه."
        if detail and "Minimum amount" in detail:
            msg = "مبلغ کمتر از حداقل مجاز درگاه است."
        bot.send_message(message.chat.id, msg)
        clear_user_state(uid)
        return

    pay_url = data["payment_url"]

    # ---- send the gateway button ----
    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton("ورود به درگاه پرداخت 💳", url=pay_url))

    bot.send_message(
        message.chat.id,
        "برای تکمیل پرداخت روی دکمه زیر بزنید.\n"
        "پس از پرداخت موفق، نتیجه به‌صورت خودکار برای شما ارسال می‌شود.",
        reply_markup=kb,
    )

    clear_user_state(uid)
