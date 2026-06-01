import os
import requests
import logging
from telebot import types

logger = logging.getLogger("inox_bot")


BOT_TOKEN = os.getenv("BOT_TOKEN")

def send_telegram_message(user_id, text):
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": user_id,
                "text": text
            },
            timeout=10
        )
    except:
        pass


def start_wallet_charge_payment(
    bot,
    message,
    uid,
    amount,
    clear_user_state,
    payment_type="wallet",
    product_id=None,
    wallet_reserved=0
):
    """
    شروع پرداخت از طریق FastAPI داخلی
    amount بر حسب تومان است.
    """

    # ---- validation ----
    try:
        amount = int(amount)
        wallet_reserved = int(wallet_reserved or 0)
    except (TypeError, ValueError):
        logger.error("Invalid amount format")
        bot.reply_to(message, "خطا در مبلغ پرداخت.")
        clear_user_state(uid)
        return

    if amount <= 0:
        logger.error("Amount <= 0")
        bot.reply_to(message, "مبلغ پرداخت نامعتبر است.")
        clear_user_state(uid)
        return

    payload = {
        "user_id": uid,
        "amount": amount,
        "payment_type": payment_type,
        "product_id": product_id,
        "wallet_reserved": wallet_reserved
    }

    logger.info(f"PAYMENT REQUEST → {payload}")

    # ---- call internal API ----
    try:
        resp = requests.post(
            "http://127.0.0.1:8000/payment/create",
            json=payload,
            timeout=15
        )
        logger.info(f"PAYMENT RESPONSE STATUS → {resp.status_code}")
        logger.info(f"PAYMENT RESPONSE BODY → {resp.text}")

        data = resp.json()

    except Exception:
        logger.exception("Internal payment API error")
        bot.reply_to(
            message,
            "خطا در ارتباط با سیستم پرداخت. لطفا بعدا تلاش کنید."
        )
        clear_user_state(uid)
        return

    # ---- validate API response ----
    if resp.status_code != 200 or "payment_url" not in data:
        logger.error(f"Bad response from payment API: {data}")
        bot.reply_to(
            message,
            "خطا در ایجاد تراکنش درگاه."
        )
        clear_user_state(uid)
        return

    pay_url = data["payment_url"]

    # ---- send payment button ----
    kb = types.InlineKeyboardMarkup()
    kb.add(
        types.InlineKeyboardButton(
            "ورود به درگاه پرداخت 💳",
            url=pay_url
        )
    )

    bot.send_message(
        message.chat.id,
        "برای تکمیل پرداخت روی دکمه زیر بزنید.\n"
        "پس از پرداخت موفق، عملیات مربوطه بصورت خودکار انجام خواهد شد.",
        reply_markup=kb,
    )

    clear_user_state(uid)