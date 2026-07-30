"""درگاه زیبال — API تک‌شناسه‌ای و تمیز، سریع‌ترین درگاه برای شروع در ایران (بدون نیاز
به نماد اعتماد الکترونیکی برای فعال‌سازی اولیه).

زیبال بر پایهٔ ریال کار می‌کنه؛ مبلغ داخلی تومانه، پس ×۱۰ می‌شه.
config: {"merchant": str, "sandbox": bool}
حالت تست زیبال: مرچنت مخصوص رشتهٔ "zibal" (بدون نیاز به کلید واقعی) — پس sandbox=True
یعنی merchant="zibal".

⚠️ این پیاده‌سازی طبق مستندات عمومی زیبال نوشته شده ولی با کلید واقعی تست نشده — قبل از
فعال‌سازی در پنل حتماً با دکمهٔ «تست اتصال» با مرچنت واقعی خودت تأییدش کن.
"""
import requests

from .base import RIAL_PER_TOMAN

_REQUEST_URL = "https://gateway.zibal.ir/v1/request"
_VERIFY_URL = "https://gateway.zibal.ir/v1/verify"
_START_URL = "https://gateway.zibal.ir/start/"


def _merchant(config: dict) -> str:
    if config.get("sandbox"):
        return "zibal"  # مرچنت تست رسمی زیبال
    return (config.get("merchant") or "").strip()


def create_payment(amount_toman: int, callback_url: str, description: str, config: dict) -> dict:
    merchant = _merchant(config)
    if not merchant:
        return {"ok": False, "authority": "", "payment_url": "", "error": "merchant زیبال ثبت نشده"}
    try:
        resp = requests.post(_REQUEST_URL, json={
            "merchant": merchant,
            "amount": int(amount_toman) * RIAL_PER_TOMAN,
            "callbackUrl": callback_url,
            "description": description,
        }, timeout=15)
        data = resp.json()
    except Exception as exc:
        return {"ok": False, "authority": "", "payment_url": "", "error": str(exc)}
    if data.get("result") == 100 and data.get("trackId"):
        track = str(data["trackId"])
        return {"ok": True, "authority": track, "payment_url": _START_URL + track, "error": ""}
    return {"ok": False, "authority": "", "payment_url": "", "error": str(data)}


def parse_callback(query: dict, form: dict) -> dict:
    # زیبال با ?success=1&trackId=...&orderId=...&status=... برمی‌گرده
    return {"authority": (query.get("trackId") or form.get("trackId") or "").strip(),
            "success": str(query.get("success") or form.get("success") or "") in ("1", "true")}


def verify_payment(authority: str, amount_toman: int, config: dict) -> dict:
    merchant = _merchant(config)
    try:
        resp = requests.post(_VERIFY_URL, json={
            "merchant": merchant,
            "trackId": int(authority),
        }, timeout=15)
        data = resp.json()
    except Exception as exc:
        return {"ok": False, "ref_id": "", "error": str(exc)}
    # 100 = موفق، 201 = قبلاً تأیید شده
    if data.get("result") in (100, 201):
        return {"ok": True, "ref_id": str(data.get("refNumber") or authority), "error": ""}
    return {"ok": False, "ref_id": "", "error": str(data)}
