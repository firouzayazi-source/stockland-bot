"""درگاه پی‌پینگ (PayPing) — API تک‌شناسه‌ای، auth با Bearer token.

⚠️ نکتهٔ حیاتی واحد پول: پی‌پینگ بر پایهٔ **تومان** کار می‌کنه (برخلاف زرین‌پال/زیبال که
ریالن) — پس مبلغ داخلی (که تومانه) بدون هیچ تبدیلی پاس داده می‌شه.
config: {"token": str}   (توکن API از پنل پی‌پینگ)

⚠️ این پیاده‌سازی طبق مستندات عمومی پی‌پینگ نوشته شده ولی با توکن واقعی تست نشده — قبل
از فعال‌سازی در پنل با دکمهٔ «تست اتصال» تأییدش کن.
"""
import requests

_CREATE_URL = "https://api.payping.ir/v2/pay"
_VERIFY_URL = "https://api.payping.ir/v2/pay/verify"
_START_URL = "https://api.payping.ir/v2/pay/gotoipg/"


def _headers(config: dict) -> dict:
    return {"Authorization": "Bearer " + (config.get("token") or "").strip(),
            "Content-Type": "application/json"}


def create_payment(amount_toman: int, callback_url: str, description: str, config: dict) -> dict:
    if not (config.get("token") or "").strip():
        return {"ok": False, "authority": "", "payment_url": "", "error": "token پی‌پینگ ثبت نشده"}
    try:
        resp = requests.post(_CREATE_URL, headers=_headers(config), json={
            "amount": int(amount_toman),   # پی‌پینگ تومانه، بدون ×۱۰
            "returnUrl": callback_url,
            "description": description[:150],
        }, timeout=15)
        try:
            data = resp.json()
        except Exception:
            data = {}
    except Exception as exc:
        return {"ok": False, "authority": "", "payment_url": "", "error": str(exc)}
    code = data.get("code") if isinstance(data, dict) else None
    if resp.status_code == 200 and code:
        return {"ok": True, "authority": str(code), "payment_url": _START_URL + str(code), "error": ""}
    return {"ok": False, "authority": "", "payment_url": "", "error": str(data) or f"HTTP {resp.status_code}"}


def parse_callback(query: dict, form: dict) -> dict:
    # پی‌پینگ با ?refid=...&clientrefid=... برمی‌گرده (refid همون code ساخت پرداخته)
    refid = (query.get("refid") or query.get("refId") or form.get("refid") or form.get("refId") or "").strip()
    return {"authority": refid, "success": bool(refid)}


def verify_payment(authority: str, amount_toman: int, config: dict) -> dict:
    try:
        resp = requests.post(_VERIFY_URL, headers=_headers(config), json={
            "refId": str(authority),
            "amount": int(amount_toman),
        }, timeout=15)
    except Exception as exc:
        return {"ok": False, "ref_id": "", "error": str(exc)}
    if resp.status_code == 200:
        ref = ""
        try:
            ref = str((resp.json() or {}).get("cardNumber") or authority)
        except Exception:
            ref = str(authority)
        return {"ok": True, "ref_id": ref, "error": ""}
    txt = ""
    try:
        txt = str(resp.json())
    except Exception:
        txt = f"HTTP {resp.status_code}"
    return {"ok": False, "ref_id": "", "error": txt}
