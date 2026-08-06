"""ارسال پیام مستقیم تلگرام بدون نمونهٔ bot (فقط requests.post ساده) — قبلاً این
دقیقاً همین منطق در payment_service.py و ۴ نقطهٔ جدا در api.py تکرار شده بود،
با رفتار خطای کمی متفاوت (بعضی timeout داشتن بعضی نه). این تابع تک‌منبع حقیقتِ
همون فراخوانی، برای هر جایی که نمی‌خواد/نمی‌تونه از نمونهٔ telebot.bot استفاده کنه
(مثل payment_service.py و api.py که در پروسهٔ FastAPI جدا از bot.py اجرا می‌شن)."""
import logging

import requests

logger = logging.getLogger("stockland.tg_notify")


def send_telegram_message(bot_token: str, chat_id: int, text: str,
                           parse_mode: str | None = None, timeout: int = 10) -> bool:
    if not bot_token:
        return False
    payload = {"chat_id": int(chat_id), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=timeout,
        )
        return True
    except Exception:
        logger.exception("Telegram sendMessage failed")
        return False


def send_telegram_message_with_id(bot_token: str, chat_id: int, text: str,
                                   parse_mode: str | None = None, timeout: int = 10) -> tuple[bool, int | None]:
    """مثل send_telegram_message ولی message_id واقعی رو هم برمی‌گردونه — برای پیام‌
    تحویل محصول لازمه، تا بعداً اگه ادمین سفارش رو برگشت زد بشه از چت کاربر حذفش کرد
    (بخش ۴۰ CLAUDE.md). امضای send_telegram_message عمداً دست‌نخورده موند — چند
    caller دیگه فقط bool می‌خوان، تغییرش اونا رو می‌شکست."""
    if not bot_token:
        return False, None
    payload = {"chat_id": int(chat_id), "text": text}
    if parse_mode:
        payload["parse_mode"] = parse_mode
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload,
            timeout=timeout,
        )
        j = r.json()
        if j.get("ok"):
            return True, (j.get("result") or {}).get("message_id")
        return False, None
    except Exception:
        logger.exception("Telegram sendMessage (with_id) failed")
        return False, None
