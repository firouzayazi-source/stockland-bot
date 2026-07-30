"""درگاه زرین‌پال (v4) — پیاده‌سازی مرجع، دقیقاً همون منطق اثبات‌شدهٔ payment_service.py
که سال‌ها در تولید کار کرده، فقط به شکل ماژول قرارداد base.py درآمده.

زرین‌پال بر پایهٔ ریال کار می‌کنه؛ مبلغ داخلی تومانه، پس ×۱۰ می‌شه.
config: {"merchant_id": str, "sandbox": bool}
"""
import requests

from .base import RIAL_PER_TOMAN


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
        return {"ok": False, "authority": "", "payment_url": "", "error": str(exc)}
    if data.get("data", {}).get("code") == 100:
        authority = str(data["data"]["authority"])
        return {"ok": True, "authority": authority, "payment_url": startpay + authority, "error": ""}
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
        return {"ok": False, "ref_id": "", "error": str(exc)}
    code = data.get("data", {}).get("code")
    # 100 = موفق، 101 = قبلاً تأیید شده (باز هم برای ما موفقیته)
    if code in (100, 101):
        return {"ok": True, "ref_id": str(data.get("data", {}).get("ref_id") or ""), "error": ""}
    return {"ok": False, "ref_id": "", "error": str(data)}
