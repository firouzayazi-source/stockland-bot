"""
api.py — API رسمی StockLand
──────────────────────────────────────────────────────────────
REST API که سرویس‌های core/ را برای کلاینت‌ها expose می‌کند:
PWA، اپ iOS، اپ Android، و هر کلاینت دیگر.

احراز هویت:
  - کلاینت‌های موبایل: initData تلگرام (همان مکانیزم Mini App)
  - یا API key ساده برای تست (از env: API_KEYS)

همه‌ی endpointها JSON برمی‌گردانند و از core/ استفاده می‌کنند.
منطق تکراری نیست — یک مغز، چند کلاینت.
"""
import os
import hmac
import hashlib
import json
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/v1")


# ══════════════════════════════════════════════════════════════════════════
# ─── احراز هویت ────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _verify_telegram_init_data(init_data: str) -> int | None:
    """
    اعتبارسنجی initData تلگرام (Mini App). user_id برمی‌گرداند یا None.
    امنیت: hash با HMAC-SHA256 بر پایه BOT_TOKEN چک می‌شود.
    """
    from config import BOT_TOKEN
    if not init_data or not BOT_TOKEN:
        return None
    try:
        parsed = dict(parse_qsl(init_data, keep_blank_values=True))
        recv_hash = parsed.pop("hash", "")
        if not recv_hash:
            return None
        # ساخت data_check_string
        pairs = sorted(f"{k}={v}" for k, v in parsed.items())
        data_check = "\n".join(pairs)
        secret = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc = hmac.new(secret, data_check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc, recv_hash):
            return None
        # استخراج user_id
        user_json = parsed.get("user", "")
        if user_json:
            user = json.loads(user_json)
            return int(user.get("id"))
    except Exception:
        return None
    return None


def _auth(request: Request) -> int:
    """احراز هویت درخواست — user_id یا خطای 401."""
    # روش ۱: initData تلگرام از هدر
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        uid = _verify_telegram_init_data(init_data)
        if uid:
            return uid
    # روش ۲: API key (برای تست/کلاینت‌های داخلی)
    api_key = request.headers.get("X-API-Key", "")
    valid_keys = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
    if api_key and api_key in valid_keys:
        # user_id از query یا هدر
        uid = request.headers.get("X-User-Id", "")
        return int(uid) if uid.isdigit() else 0
    raise HTTPException(status_code=401, detail="احراز هویت ناموفق")


# ══════════════════════════════════════════════════════════════════════════
# ─── Endpoints: محصولات ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/products")
async def api_products(request: Request, category: str = "", limit: int = 60):
    """لیست محصولات."""
    from core import products
    try:
        data = products.list_products(category=category, active_only=True, limit=limit)
        return {"ok": True, "products": data}
    except Exception as ex:
        return JSONResponse({"ok": False, "error": str(ex)[:120]}, status_code=500)


@router.get("/products/{pid}")
async def api_product(pid: int):
    """جزئیات یک محصول."""
    from core import products
    p = products.get_product(pid)
    if not p:
        return JSONResponse({"ok": False, "error": "محصول یافت نشد"}, status_code=404)
    return {"ok": True, "product": p}


# ══════════════════════════════════════════════════════════════════════════
# ─── Endpoints: کاربر (نیازمند احراز هویت) ────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/me/wallet")
async def api_wallet(request: Request):
    """موجودی کیف‌پول کاربر."""
    uid = _auth(request)
    from core import wallet
    return {"ok": True, "balance": wallet.get_balance(uid)}


@router.get("/me/orders")
async def api_orders(request: Request, limit: int = 50):
    """سفارش‌های کاربر."""
    uid = _auth(request)
    from core import orders
    return {"ok": True, "orders": orders.user_orders(uid, limit)}


@router.get("/me/partner")
async def api_partner(request: Request):
    """وضعیت همکاری کاربر."""
    uid = _auth(request)
    from core import partners, referrals
    tier = partners.current_tier(uid) if partners.is_approved(uid) else None
    return {
        "ok": True,
        "is_partner": partners.is_approved(uid),
        "balance": partners.partner_balance(uid),
        "tier": {"name": tier["name"], "icon": tier.get("icon"),
                 "order_count": tier.get("order_count", 0)} if tier else None,
        "referrals": referrals.stats(uid),
    }


# ══════════════════════════════════════════════════════════════════════════
# ─── سلامت API ─────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/health")
async def api_health():
    """بررسی سلامت API + dialect جاری."""
    import db_conn
    return {
        "ok": True,
        "service": "stockland-api",
        "version": "1.0",
        "dialect": db_conn.get_dialect(),
        "time": int(time.time()),
    }
