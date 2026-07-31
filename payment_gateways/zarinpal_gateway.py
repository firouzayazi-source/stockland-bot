"""درگاه زرین‌پال (v4) — پیاده‌سازی مرجع، دقیقاً همون منطق اثبات‌شدهٔ payment_service.py
که سال‌ها در تولید کار کرده، فقط به شکل ماژول قرارداد base.py درآمده.

زرین‌پال بر پایهٔ ریال کار می‌کنه؛ مبلغ داخلی تومانه، پس ×۱۰ می‌شه.
config: {"merchant_id": str, "sandbox": bool}
"""
import logging

import requests

from .base import RIAL_PER_TOMAN

logger = logging.getLogger("stockland.payment.zarinpal")


def _hosts(sandbox: bool):
    if sandbox:
        return ("https://sandbox.zarinpal.com/pg/v4/payment/request.json",
                "https://sandbox.zarinpal.com/pg/v4/payment/verify.json",
                "https://sandbox.zarinpal.com/pg/StartPay/")
    return ("https://api.zarinpal.com/pg/v4/payment/request.json",
            "https://api.zarinpal.com/pg/v4/payment/verify.json",
            "https://www.zarinpal.com/pg/StartPay/")


def create_payment(amount_toman: int, callback_url: str, description: str, config: dict) -> dict:
    merchant = (config.get("merchant_id") or "").strip()
    if not merchant:
        return {"ok": False, "authority": "", "payment_url": "", "error": "merchant_id ثبت نشده"}
    req_url, _, startpay = _hosts(bool(config.get("sandbox")))
    try:
        resp = requests.post(req_url, json={
            "merchant_id": merchant,
            "amount": int(amount_toman) * RIAL_PER_TOMAN,
            "callback_url": callback_url,
            "description": description,
        }, timeout=15)
        data = resp.json()
    except Exception as exc:
        logger.error("create_payment request failed: %s", exc)
        return {"ok": False, "authority": "", "payment_url": "", "error": str(exc)}
    if data.get("data", {}).get("code") == 100:
        authority = str(data["data"]["authority"])
        # مسیر موفق (اکثریت قریب‌به‌اتفاق تراکنش‌ها) فقط یه خط خلاصه لاگ می‌شه —
        # قبلاً کل پاسخ خام هر تراکنش (فارغ از موفق/ناموفق) در سطح INFO لاگ
        # می‌شد، یعنی حجم لاگ تولید با هر پرداخت رشد می‌کرد. جزئیات کامل فقط
        # وقتی واقعاً لازمه (مسیر شکست، زیر) لاگ می‌شه.
        logger.info("create_payment ok — authority=%s", authority)
        return {"ok": True, "authority": authority, "payment_url": startpay + authority, "error": ""}
    logger.warning("create_payment failed — response: %s", data)
    return {"ok": False, "authority": "", "payment_url": "", "error": str(data)}


def parse_callback(query: dict, form: dict) -> dict:
    return {"authority": (query.get("Authority") or "").strip(),
            "success": (query.get("Status") == "OK")}


def verify_payment(authority: str, amount_toman: int, config: dict) -> dict:
    merchant = (config.get("merchant_id") or "").strip()
    _, verify_url, _ = _hosts(bool(config.get("sandbox")))
    try:
        resp = requests.post(verify_url, json={
            "merchant_id": merchant,
            "amount": int(amount_toman) * RIAL_PER_TOMAN,
            "authority": authority,
        }, timeout=15)
        data = resp.json()
    except Exception as exc:
        logger.error("verify_payment request failed: %s", exc)
        return {"ok": False, "ref_id": "", "error": str(exc)}
    inner = data.get("data", {}) or {}
    code = inner.get("code")
    # 100 = موفق، 101 = قبلاً تأیید شده (باز هم برای ما موفقیته). card_pan از قبل توسط
    # زرین‌پال ماسک‌شده برمی‌گرده (مثل «402360**...**1234»)، پس ذخیره‌اش نقض «کارت ذخیره
    # نشه» نیست — همون فرمتیه که خودِ درگاه رسمی برمی‌گردونه.
    if code in (100, 101):
        # مسیر موفق فقط خلاصه لاگ می‌شه (همون دلیل create_payment بالا)
        logger.info("verify_payment ok — ref_id=%s code=%s", inner.get("ref_id"), code)
        return {
            "ok": True,
            "ref_id": str(inner.get("ref_id") or ""),
            "error": "",
            "card_pan": str(inner.get("card_pan") or ""),
            "card_hash": str(inner.get("card_hash") or ""),
            "fee_type": str(inner.get("fee_type") or ""),
            "fee": inner.get("fee"),
        }
    logger.warning("verify_payment failed — response: %s", data)
    return {"ok": False, "ref_id": "", "error": str(data)}
