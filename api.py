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
from fastapi.responses import JSONResponse, RedirectResponse

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


# ══════════════════════════════════════════════════════════════════════════
# ─── محتوای اپ (عمومی — بدون احراز هویت) ──────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/content")
async def api_content_list(kind: str = "", limit: int = 50):
    """فهرست محتوا برای PWA — kind: tutorial | news | feature (خالی = همه)."""
    from db import get_app_content
    kind = kind if kind in ("tutorial", "news", "feature", "daily") else None
    items = get_app_content(kind=kind, active_only=True, limit=min(int(limit or 50), 100))
    out = []
    for it in items:
        body = (it.get("body") or "").strip()
        out.append({
            "id": it["id"],
            "kind": it.get("kind"),
            "title": it.get("title"),
            "excerpt": (body[:160] + "…") if len(body) > 160 else body,
            "image_url": it.get("image_url") or "",
            "created_at": str(it.get("created_at") or "")[:16],
        })
    return {"ok": True, "items": out}


@router.get("/content/{cid}")
async def api_content_item(cid: int):
    """یک آیتم کامل محتوا برای PWA."""
    from db import get_app_content_item
    it = get_app_content_item(cid)
    if not it or not int(it.get("is_active") or 0):
        raise HTTPException(status_code=404, detail="یافت نشد")
    return {"ok": True, "item": {
        "id": it["id"],
        "kind": it.get("kind"),
        "title": it.get("title"),
        "body": it.get("body") or "",
        "image_url": it.get("image_url") or "",
        "created_at": str(it.get("created_at") or "")[:16],
    }}


# ══════════════════════════════════════════════════════════════════════════
# ─── دسته‌بندی‌ها (عمومی) ──────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/categories")
async def api_categories():
    """درخت دسته‌بندی‌ها برای PWA — فعال‌ها، مرتب‌شده."""
    from db import get_root_categories, get_subcategories, get_category_products
    roots = [dict(r) for r in get_root_categories(active_only=True)]
    from db import apply_flash_price
    out = []
    for rc in roots:
        subs = [dict(s) for s in get_subcategories(int(rc["id"]), active_only=True)]
        # محصولات دسته اصلی (بدون زیردسته)
        prods = [dict(p) for p in get_category_products(int(rc["id"]), active_only=True)]
        for sub in subs:
            sub["products"] = []
            for p in get_category_products(int(sub["id"]), active_only=True):
                p = dict(p)
                base = int(p.get("price") or 0)
                eff, fl = apply_flash_price(int(p["id"]), base)
                p["effective_price"] = int(eff)
                p["flash_active"] = bool(fl)
                p["partner_price"] = int(p.get("partner_price") or 0)
                sub["products"].append(p)
        cat_out = {
            "id": int(rc["id"]), "name": rc.get("name"), "emoji": rc.get("emoji") or "",
            "slug": rc.get("slug") or "",
            "subcategories": [{
                "id": int(s["id"]), "name": s.get("name"), "emoji": s.get("emoji") or "",
                "products": s["products"]
            } for s in subs],
        }
        # اگر محصولات مستقیم زیر دسته اصلی هم داشت
        for p in prods:
            p = dict(p)
            base = int(p.get("price") or 0)
            eff, fl = apply_flash_price(int(p["id"]), base)
            p["effective_price"] = int(eff)
            p["flash_active"] = bool(fl)
            p["partner_price"] = int(p.get("partner_price") or 0)
            if not cat_out.get("products"):
                cat_out["products"] = []
            cat_out["products"].append(p)
        out.append(cat_out)
    return {"ok": True, "categories": out}


@router.get("/bot-info")
async def api_bot_info():
    """اطلاعات عمومی ربات — یوزرنیم برای ساخت دیپ‌لینک در PWA."""
    try:
        from bot import _bot_username
        u = _bot_username()
    except Exception:
        u = ""
    return {"ok": True, "username": u or "stock_land_ir"}


@router.get("/content/daily")
async def api_daily_post():
    """آخرین پست روزانه (نوع daily) — برای بخش خانه‌ی PWA."""
    from db import get_app_content
    items = get_app_content(kind="daily", active_only=True, limit=1)
    if not items:
        return {"ok": True, "item": None}
    it = items[0]
    return {"ok": True, "item": {
        "id": it["id"], "kind": "daily", "title": it.get("title"),
        "body": it.get("body") or "",
        "image_url": it.get("image_url") or "",
        "created_at": str(it.get("created_at") or "")[:16],
    }}


# ══════════════════════════════════════════════════════════════════════════
# ─── خرید از اپ ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.post("/checkout")
async def api_checkout(request: Request):
    """
    شروع خرید از PWA.
    body: { product_id, payment_type: "wallet"|"gateway"|"combined",
            wallet_amount?, initData }
    برای wallet: کسر از کیف‌پول و ثبت سفارش.
    برای gateway/combined: درخواست Zarinpal و بازگشت redirect_url.
    """
    uid = _get_uid(request)
    if not uid:
        raise HTTPException(401, "احراز هویت لازم است")

    body = await request.json()
    pid = int(body.get("product_id", 0))
    ptype = str(body.get("payment_type", "wallet")).lower()

    if not pid:
        raise HTTPException(400, "product_id الزامی است")
    if ptype not in ("wallet", "gateway", "combined"):
        raise HTTPException(400, "payment_type نامعتبر")

    from core.products import get_product
    from db import (get_wallet_balance, subtract_wallet_balance,
                    create_order, is_partner_approved)

    prod = get_product(pid)
    if not prod or prod.get("is_active") in (0, False):
        raise HTTPException(404, "محصول یافت نشد")

    # قیمت موثر (همکار یا عادی)
    is_partner = is_partner_approved(uid)
    partner_price = int(prod.get("partner_price") or 0)
    base_price = int(prod.get("effective_price") or prod.get("price") or 0)
    final_price = (partner_price if is_partner and partner_price > 0 and partner_price < base_price
                   else base_price)

    wallet_bal = get_wallet_balance(uid)

    if ptype == "wallet":
        if wallet_bal < final_price:
            raise HTTPException(400, f"موجودی کیف‌پول کافی نیست (موجودی: {wallet_bal:,} — نیاز: {final_price:,} تومان)")
        ok = subtract_wallet_balance(uid, final_price)
        if not ok:
            raise HTTPException(400, "کسر از کیف‌پول ناموفق بود")
        oid = create_order(uid, prod.get("category",""), prod.get("title",""),
                           final_price, product_id=pid,
                           buyer_type="partner" if is_partner else "customer")
        return {"ok": True, "method": "wallet", "order_id": oid,
                "message": f"✅ خرید موفق! سفارش #{oid} ثبت شد."}

    gateway_amount = final_price
    wallet_used = 0
    if ptype == "combined":
        wallet_used = min(wallet_bal, final_price)
        gateway_amount = final_price - wallet_used
        if gateway_amount <= 0:
            # کافیه از کیف‌پول
            ok = subtract_wallet_balance(uid, final_price)
            if not ok:
                raise HTTPException(400, "کسر از کیف‌پول ناموفق بود")
            oid = create_order(uid, prod.get("category",""), prod.get("title",""),
                               final_price, product_id=pid,
                               buyer_type="partner" if is_partner else "customer")
            return {"ok": True, "method": "wallet", "order_id": oid,
                    "message": f"✅ خرید از کیف‌پول موفق! سفارش #{oid}"}

    # درگاه زرین‌پال
    import httpx
    from config import WEBHOOK_BASE_URL
    callback = WEBHOOK_BASE_URL.rstrip("/") + "/api/v1/payment/verify"
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "http://127.0.0.1:8001/payment/create",
                json={
                    "user_id": uid,
                    "amount": gateway_amount,
                    "wallet_reserved": wallet_used,
                    "payment_type": "product",
                    "product_id": pid,
                    "chat_id": uid,
                })
        data = r.json()
    except Exception as e:
        raise HTTPException(502, f"خطا در اتصال به درگاه: {e}")

    pay_url = data.get("payment_url") or data.get("redirect_url")
    if r.status_code != 200 or not pay_url:
        raise HTTPException(502, data.get("detail") or "درگاه پاسخ نداد")

    return {"ok": True, "method": "gateway",
            "redirect_url": pay_url,
            "wallet_used": wallet_used,
            "gateway_amount": gateway_amount}


@router.get("/payment/verify")
async def api_payment_verify(
    request: Request, Authority: str = "", Status: str = ""):
    """
    زرین‌پال بعد از پرداخت به این آدرس redirect می‌کنه.
    چون داخل مینی‌اپ هستیم، کاربر را به صفحه موفقیت در اپ برمی‌گردونیم.
    """
    from config import WEBHOOK_BASE_URL
    base = WEBHOOK_BASE_URL.rstrip("/")
    if Status != "OK" or not Authority:
        return RedirectResponse(url=f"{base}/app/?payment=canceled")
    # تأیید را به روت اصلی واگذار می‌کنیم
    return RedirectResponse(
        url=f"{base}/payment/callback?Authority={Authority}&Status={Status}")


def _get_uid(request: Request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if not init_data:
        return None
    return _verify_telegram_init_data(init_data)
