"""Client-side payment helper (runs inside the Telegram bot)."""

import os
import logging

import requests
from telebot import types

logger = logging.getLogger("inox_bot")

MIN_TOPUP_AMOUNT = int(os.getenv("MIN_TOPUP_AMOUNT", "10000"))


def _default_payment_base_url() -> str:
    explicit = os.getenv("PAYMENT_API_BASE_URL")
    if explicit:
        return explicit.rstrip("/")
    port = os.getenv("PORT") or "8000"
    return f"http://127.0.0.1:{port}"


PAYMENT_API_BASE_URL = _default_payment_base_url()
PHP_PAYMENT_URL = (os.getenv("PHP_PAYMENT_URL") or "").rstrip("/")
PHP_SECRET      = os.getenv("PHP_SECRET") or ""
PAYMENT_API_TIMEOUT = int(os.getenv("PAYMENT_API_TIMEOUT", "20"))


def _enforce_min_gateway(amount: int, min_amount: int, payment_type: str) -> tuple[int, int]:
    """اعمال حداقل مبلغ درگاه.

    اگه مبلغ درگاه کمتر از MIN_TOPUP_AMOUNT بود:
    - برای wallet: مبلغ به min_amount تبدیل می‌شه (کاربر مطلع می‌شه)
    - برای product: مبلغ کمبود به صورت اضافه دریافت می‌شه و مازاد به کیف‌پول اضافه می‌شه
    Returns: (final_gateway_amount, wallet_bonus)  — wallet_bonus = مازادی که به کیف‌پول می‌ره
    """
    if amount >= min_amount:
        return amount, 0
    bonus = min_amount - amount  # مازاد که به کیف‌پول می‌ره
    return min_amount, bonus


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
    """ایجاد تراکنش پرداخت از درگاه."""
    try:
        amount = int(amount)
        wallet_reserved = int(wallet_reserved or 0)
    except (TypeError, ValueError):
        bot.send_message(message.chat.id, "خطا در مبلغ پرداخت.")
        clear_user_state(uid)
        return

    if amount <= 0:
        bot.send_message(message.chat.id, "مبلغ پرداخت نامعتبر است.")
        clear_user_state(uid)
        return

    # ─── Issue 2: اعمال حداقل مبلغ درگاه ──────────────────────────
    wallet_bonus = 0
    if amount < MIN_TOPUP_AMOUNT:
        final_amount, wallet_bonus = _enforce_min_gateway(amount, MIN_TOPUP_AMOUNT, payment_type)
        if wallet_bonus > 0:
            notice = (
                f"⚠️ حداقل پرداخت از درگاه <b>{MIN_TOPUP_AMOUNT:,}</b> تومان است.\n"
                f"مبلغ {final_amount:,} تومان از درگاه دریافت می‌شود "
                f"و <b>{wallet_bonus:,}</b> تومان مازاد به کیف‌پول شما اضافه خواهد شد."
            )
            bot.send_message(message.chat.id, notice, parse_mode="HTML")
        amount = final_amount

    payload = {
        "user_id": int(uid),
        "amount": amount,
        "payment_type": payment_type,
        "product_id": product_id,
        "wallet_reserved": wallet_reserved,
        "wallet_bonus": wallet_bonus,
        "chat_id": getattr(message.chat, "id", uid),
    }

    logger.info("PAYMENT REQUEST -> %s", payload)

    if PHP_PAYMENT_URL and PHP_SECRET:
        _call_url = PHP_PAYMENT_URL
        _headers  = {"Content-Type": "application/json", "X-Stockland-Secret": PHP_SECRET}
    else:
        _call_url = f"{PAYMENT_API_BASE_URL}/payment/create"
        _headers  = {"Content-Type": "application/json"}

    try:
        resp = requests.post(_call_url, json=payload, headers=_headers, timeout=PAYMENT_API_TIMEOUT)
    except Exception:
        logger.exception("Could not reach payment service")
        bot.send_message(message.chat.id, "خطا در ارتباط با سیستم پرداخت. لطفاً دوباره تلاش کنید.")
        clear_user_state(uid)
        return

    try:
        data = resp.json()
    except Exception:
        bot.send_message(message.chat.id, "خطا در ایجاد تراکنش درگاه.")
        clear_user_state(uid)
        return

    if resp.status_code != 200 or not data.get("payment_url"):
        detail = str(data.get("detail") or data.get("error") or "") if isinstance(data, dict) else ""
        msg = "خطا در ایجاد تراکنش درگاه."
        if "Minimum" in detail:
            msg = "مبلغ کمتر از حداقل مجاز درگاه است."
        bot.send_message(message.chat.id, msg)
        clear_user_state(uid)
        return

    pay_url = data["payment_url"]

    kb = types.InlineKeyboardMarkup()
    kb.add(types.InlineKeyboardButton(
        "ورود به درگاه پرداخت 💳", url=pay_url
    ))

    # پیام #10 - هشدار VPN قبل از درگاه
    warning_text = (
        "⚠️ <b>قبل از پرداخت توجه کنید:</b>\n"
        "🔴 برای انجام پرداخت، لطفاً VPN یا فیلترشکن خود را <b>خاموش</b> کنید.\n\n"
        "برای تکمیل پرداخت روی دکمه زیر بزنید.\n"
        "پس از پرداخت موفق، نتیجه به‌صورت خودکار برای شما ارسال می‌شود."
    )
    bot.send_message(
        message.chat.id,
        warning_text,
        reply_markup=kb,
        parse_mode="HTML"
    )
    clear_user_state(uid)
