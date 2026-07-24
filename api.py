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
import logging
import time
from urllib.parse import parse_qsl

from fastapi import APIRouter, Request, HTTPException, Header
from fastapi.responses import JSONResponse, RedirectResponse

router = APIRouter(prefix="/api/v1")
logger = logging.getLogger("stockland.api")


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


_WEB_SESSION_COOKIE = "sl_sess"
_WEB_SESSION_MAX_AGE = 30 * 86400  # ۳۰ روز


def _web_session_key() -> bytes:
    from config import BOT_TOKEN
    return hashlib.sha256((BOT_TOKEN + "|stockland-website-session").encode()).digest()


def _make_web_session(uid: int) -> str:
    """سشن کوکی وب‌سایت — امضاشده با HMAC (کلید مشتق‌شده از BOT_TOKEN، بدون نیاز به env جدید)."""
    payload = f"{int(uid)}|{int(time.time())}"
    token = hmac.new(_web_session_key(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{token}:{payload}"


def _verify_web_session(cookie: str) -> int | None:
    if not cookie or ":" not in cookie:
        return None
    try:
        token, payload = cookie.rsplit(":", 1)
        uid_str, ts_str = payload.rsplit("|", 1)
        expected = hmac.new(_web_session_key(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(token, expected):
            return None
        if (time.time() - int(ts_str)) > _WEB_SESSION_MAX_AGE:
            return None
        return int(uid_str)
    except Exception:
        return None


def _auth(request: Request) -> int:
    """احراز هویت درخواست — user_id یا خطای 401."""
    # روش ۱: initData تلگرام از هدر (مینی‌اپ داخل تلگرام)
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    if init_data:
        uid = _verify_telegram_init_data(init_data)
        if uid:
            return uid
    # روش ۲: کوکی سشن وب‌سایت (لاگین با Telegram Login Widget، خارج از تلگرام)
    web_cookie = request.cookies.get(_WEB_SESSION_COOKIE, "")
    if web_cookie:
        uid = _verify_web_session(web_cookie)
        if uid:
            return uid
    # روش ۳: API key (برای تست/کلاینت‌های داخلی)
    api_key = request.headers.get("X-API-Key", "")
    valid_keys = [k.strip() for k in os.getenv("API_KEYS", "").split(",") if k.strip()]
    if api_key and api_key in valid_keys:
        # user_id از query یا هدر
        uid = request.headers.get("X-User-Id", "")
        return int(uid) if uid.isdigit() else 0
    raise HTTPException(status_code=401, detail="احراز هویت ناموفق")


_WEB_LOGIN_TOKEN_TTL = 300  # ۵ دقیقه — بعدش توکن منقضی حساب می‌شه


@router.post("/auth/start-login")
async def api_auth_start_login():
    """شروع ورود وب‌سایت (PWA خارج از تلگرام) — یک توکن یک‌بارمصرف می‌سازه و
    دیپ‌لینک بازکردن اپ واقعی تلگرام رو برمی‌گردونه (نه ویجت/oauth.telegram.org
    که برای خیلی از کاربرها — به‌خصوص ایران — قابل‌اعتماد نیست).
    فرانت این لینک رو باز می‌کنه و بعد /auth/poll-login رو poll می‌کنه."""
    import secrets
    from db import create_web_login_token
    from bot import _bot_username
    token = secrets.token_urlsafe(16)
    create_web_login_token(token)
    username = _bot_username() or ""
    return {"ok": True, "token": token, "deep_link": f"https://t.me/{username}?start=weblogin_{token}"}


@router.get("/auth/poll-login")
async def api_auth_poll_login(token: str = ""):
    """فرانت هر چند ثانیه صدا می‌زنه تا ببینه کاربر داخل ربات لینک weblogin_TOKEN رو باز کرده یا نه."""
    from db import get_web_login_token, get_user_full_name
    row = get_web_login_token(token) if token else None
    if not row:
        raise HTTPException(404, "توکن نامعتبر")
    status = row["status"]
    if status == "pending" and (time.time() - int(row["created_at"] or 0)) > _WEB_LOGIN_TOKEN_TTL:
        status = "expired"
    if status == "confirmed":
        uid = int(row["user_id"])
        resp = JSONResponse({"ok": True, "status": "confirmed", "full_name": get_user_full_name(uid)})
        resp.set_cookie(
            _WEB_SESSION_COOKIE, _make_web_session(uid),
            max_age=_WEB_SESSION_MAX_AGE, httponly=True, samesite="lax", secure=True, path="/",
        )
        return resp
    return {"ok": True, "status": status}


@router.get("/auth/whoami")
async def api_auth_whoami(request: Request):
    """چک سریع وضعیت لاگین وب‌سایت — برای بارگذاری اولیهٔ صفحه (بدون initData مینی‌اپ)."""
    from db import get_user_full_name
    web_cookie = request.cookies.get(_WEB_SESSION_COOKIE, "")
    uid = _verify_web_session(web_cookie) if web_cookie else None
    if not uid:
        raise HTTPException(401, "لاگین نشده")
    return {"ok": True, "user_id": uid, "full_name": get_user_full_name(uid)}


@router.post("/auth/logout")
async def api_auth_logout():
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(_WEB_SESSION_COOKIE, path="/")
    return resp


# ══════════════════════════════════════════════════════════════════════════
# ─── Endpoints: محصولات ────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

@router.get("/products")
async def api_products(request: Request, category: str = "", limit: int = 60, q: str = ""):
    """لیست محصولات — با q می‌شه در عنوان/توضیح جستجو کرد."""
    from core import products
    try:
        data = products.list_products(category=category, active_only=True, limit=limit, q=q.strip())
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
    is_approved = partners.is_approved(uid)
    tier = partners.current_tier(uid) if is_approved else None
    pending_status = None
    if not is_approved:
        try:
            from db import get_partner_by_user_id
            row = get_partner_by_user_id(uid)
            if row:
                pending_status = (row[3] or "").strip().lower() or None
        except Exception:
            pending_status = None
    return {
        "ok": True,
        "is_partner": is_approved,
        "pending_status": pending_status,  # None | 'pending' | 'rejected'
        "balance": partners.partner_balance(uid),
        "tier": {"name": tier["name"], "icon": tier.get("icon"),
                 "order_count": tier.get("order_count", 0)} if tier else None,
        "referrals": referrals.stats(uid),
    }


@router.post("/partner/apply")
async def api_partner_apply(request: Request):
    """درخواست همکاری از مینی‌اپ — دقیقاً همون تابع/جدولی که ربات (process_reseller_shop)
    استفاده می‌کنه، پس پنل ادمین بدون هیچ تغییری همین درخواست‌ها رو می‌بینه."""
    uid = _auth(request)
    body = await request.json()
    phone = (body.get("phone") or "").strip()
    city = (body.get("city") or "").strip()
    shop_name = (body.get("shop_name") or "").strip()
    full_name = (body.get("full_name") or "").strip()
    username = (body.get("username") or "").strip()

    if not phone or len(phone) < 8:
        raise HTTPException(400, "شماره تماس نامعتبر است")
    if not city or len(city) < 2:
        raise HTTPException(400, "نام شهر نامعتبر است")
    if not shop_name or len(shop_name) < 2:
        raise HTTPException(400, "نام فروشگاه/پیج نامعتبر است")

    from bot import can_submit_partner_request
    ok, msg = can_submit_partner_request(uid, phone=phone)
    if not ok:
        raise HTTPException(400, msg or "امکان ثبت درخواست نیست")

    from db import upsert_partner_request
    upsert_partner_request(uid, phone, username=username, full_name=full_name,
                            note="", city=city, shop_name=shop_name)

    from config import BOT_TOKEN, ADMIN_ID
    import requests
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={"chat_id": ADMIN_ID,
                  "text": (f"🔔 درخواست فروشندگی جدید (از مینی‌اپ)\n"
                           f"کاربر: {uid} — {full_name}\nشهر: {city} | فروشگاه: {shop_name}")},
            timeout=10,
        )
    except Exception:
        pass

    return {"ok": True}


@router.get("/me/invite")
async def api_me_invite(request: Request):
    """لینک دعوت + آمار معرفی کاربر (چه همکار باشد چه کاربر عادی)."""
    uid = _auth(request)
    from core import partners, referrals
    from db import get_referral_settings

    try:
        from bot import _bot_username
        username = _bot_username()
    except Exception:
        username = ""
    username = username or "stock_land_ir"

    settings = get_referral_settings()
    return {
        "ok": True,
        "referral_link": f"https://t.me/{username}?start=ref_{uid}",
        "is_partner": partners.is_approved(uid),
        "reward_amount": int(settings.get("reward_amount") or 0),
        "stats": referrals.stats(uid),
    }


@router.post("/wallet/topup")
async def api_wallet_topup(request: Request):
    """شروع شارژ کیف‌پول از PWA — درخواست پرداخت به زرین‌پال و بازگشت redirect_url."""
    uid = _auth(request)

    body = await request.json()
    try:
        amount = int(body.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0

    from config import MIN_TOPUP_AMOUNT
    if amount < MIN_TOPUP_AMOUNT:
        raise HTTPException(400, f"حداقل مبلغ شارژ {MIN_TOPUP_AMOUNT:,} تومان است")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            r = await client.post(
                "http://127.0.0.1:8001/payment/create",
                json={
                    "user_id": uid,
                    "amount": amount,
                    "payment_type": "wallet",
                    "chat_id": uid,
                })
        data = r.json()
    except Exception as e:
        raise HTTPException(502, f"خطا در اتصال به درگاه: {e}")

    if r.status_code != 200 or not data.get("payment_url"):
        raise HTTPException(502, data.get("detail") or "درگاه پاسخ نداد")

    return {"ok": True, "redirect_url": data["payment_url"]}


# کارت مقصد کارت‌به‌کارت — دقیقاً همون مقداری که ربات هم هاردکد داره (bot.py handle_card2card_amount)
_CARD2CARD_NUMBER = "6037701608004393"
_CARD2CARD_NAME = "سید فیروز ایازی"


async def _upload_photo_to_telegram(photo_bytes: bytes, content_type: str | None, caption: str) -> str:
    """آپلود عکس به چت ادمین در تلگرام برای گرفتن یه file_id واقعی (رسید/تیکت).

    عمداً از requests استفاده می‌کنه، نه httpx: httpx (httpcore) روی این سرور
    مشخص شد که با ConnectTimeout پایدار (نه گاه‌به‌گاه) شکست می‌خوره حتی با
    مهلت ۲۰ ثانیه و retry — که دقیقاً علامت یه محدودیت شناخته‌شدهٔ httpcore
    است: برخلاف requests/urllib3، اگه اولین آدرس resolve‌شده (مثلاً IPv6) روی
    این سرور بلاک/بی‌پاسخ باشه، httpcore به آدرس بعدی (IPv4) fallback نمی‌کنه
    و کل مدت timeout رو منتظر همون آدرس مرده می‌مونه. requests همینجا (در
    _notify_admin_ticket/partner apply) و در کل bot.py (از طریق apihelper)
    برای همین سرور به تلگرام همیشه کار کرده، پس همون رو استفاده می‌کنیم —
    در یه ترد جدا (asyncio.to_thread) که event loop رو بلاک نکنه."""
    from config import BOT_TOKEN, ADMIN_ID
    import asyncio
    import requests

    def _do_upload():
        r = requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendPhoto",
            data={"chat_id": ADMIN_ID, "caption": caption},
            files={"photo": ("photo.jpg", photo_bytes, content_type or "image/jpeg")},
            timeout=(15, 60),  # (connect, read) — همون مقادیر apihelper.CONNECT/READ_TIMEOUT در bot.py
        )
        return r.json()

    last_err = None
    for attempt in range(2):
        try:
            tg_data = await asyncio.to_thread(_do_upload)
            if not tg_data.get("ok"):
                raise RuntimeError(tg_data.get("description") or "خطای نامشخص از تلگرام")
            return tg_data["result"]["photo"][-1]["file_id"]
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
            last_err = e
            logger.warning("تلاش %d/2 آپلود عکس به تلگرام با خطای اتصال شکست خورد: %r", attempt + 1, e)
            if attempt == 0:
                await asyncio.sleep(1.5)
                continue
        except Exception as e:
            last_err = e
            break
    logger.error("خطا در آپلود عکس به تلگرام (caption=%r)", caption, exc_info=last_err)
    why = str(last_err) or f"{type(last_err).__name__} — احتمالاً تایم‌اوت/قطعی اتصال سرور به تلگرام"
    raise HTTPException(502, f"خطا در آپلود عکس — دوباره تلاش کنید ({why})")


@router.get("/payment/methods")
async def api_payment_methods():
    """روش‌های فعال شارژ کیف‌پول — دقیقاً همون تنظیماتی که ربات هم می‌خونه."""
    from db import get_crypto_settings
    cs = get_crypto_settings()
    return {
        "ok": True,
        "gateway": True,
        "card2card": {"card_number": _CARD2CARD_NUMBER, "card_name": _CARD2CARD_NAME},
        "crypto": {
            "enabled": bool(int(cs.get("enabled") or 0)),
            "usdt_trc20": cs.get("usdt_trc20") or "",
            "trx": cs.get("trx") or "",
            "note": cs.get("note") or "",
        },
    }


@router.post("/wallet/card2card")
async def api_wallet_card2card(request: Request):
    """ثبت رسید کارت‌به‌کارت از مینی‌اپ.

    عکس رسید به همون چتِ ادمین در تلگرام آپلود می‌شه تا یه file_id واقعی بگیریم،
    دقیقاً هم‌ساختار با چیزی که ربات از کاربر می‌گیره — چون پنل ادمین
    (admin_panel.py) رسیدها رو با getFile روی همین file_id نمایش می‌ده و
    قرار نیست پنل ادمین دست بخوره، این تنها راهیه که با اون کاملاً سازگار بمونه.
    """
    uid = _auth(request)
    form = await request.form()
    try:
        amount = int(str(form.get("amount", "0")).strip())
    except (TypeError, ValueError):
        amount = 0
    if amount < 1000:
        raise HTTPException(400, "حداقل مبلغ ۱٬۰۰۰ تومان است")
    photo = form.get("photo")
    if not photo or not hasattr(photo, "read"):
        raise HTTPException(400, "عکس رسید ارسال نشده")
    photo_bytes = await photo.read()
    if not photo_bytes:
        raise HTTPException(400, "عکس رسید خالی است")

    file_id = await _upload_photo_to_telegram(
        photo_bytes, photo.content_type,
        f"رسید کارت‌به‌کارت — کاربر {uid} — {amount:,} تومان (از مینی‌اپ)")

    from db import save_card_receipt, ensure_card_receipts_schema
    ensure_card_receipts_schema()
    rid = save_card_receipt(uid, amount, file_id)
    return {"ok": True, "receipt_id": rid}


@router.post("/wallet/crypto")
async def api_wallet_crypto(request: Request):
    """ثبت رسید رمزارز از مینی‌اپ — دقیقاً همون تابعی که ربات استفاده می‌کنه."""
    uid = _auth(request)
    body = await request.json()
    try:
        amount = int(body.get("amount", 0))
    except (TypeError, ValueError):
        amount = 0
    network = (body.get("network") or "").strip().lower()
    txid = (body.get("txid") or "").strip()
    if amount < 1000:
        raise HTTPException(400, "حداقل مبلغ ۱٬۰۰۰ تومان است")
    if network not in ("usdt", "trx"):
        raise HTTPException(400, "شبکه نامعتبر است")
    if not txid:
        raise HTTPException(400, "TXID الزامی است")

    from db import get_crypto_settings, save_crypto_receipt
    cs = get_crypto_settings()
    if not int(cs.get("enabled") or 0):
        raise HTTPException(400, "پرداخت رمزارز غیرفعال است")

    rid = save_crypto_receipt(uid, amount, network, txid)
    return {"ok": True, "receipt_id": rid}


# ══════════════════════════════════════════════════════════════════════════
# ─── پشتیبانی (ticket_v2) — همون جدول/منطق ربات، فقط کلاینت متفاوت ──────────
# ══════════════════════════════════════════════════════════════════════════

TICKET_MAX_USER_MSGS = 3  # همون سقف bot.py


def _ticket_to_dict(t) -> dict:
    return {
        "id": int(t["id"]), "status": t["status"],
        "user_msg_count": int(t["user_msg_count"] or 0),
        "created_at": str(t["created_at"] or ""),
    }


def _support_ticket_type(uid: int) -> str:
    """اگه کاربر همکار تأیید‌شده باشه، تیکتش باید نوع partner_support بگیره
    (دقیقاً مثل دکمهٔ «چت با پشتیبان همکاران» در ربات، cb_partner_support در bot.py)."""
    from core.partners import is_approved
    return "partner_support" if is_approved(uid) else "support"


@router.get("/support/ticket")
async def api_support_ticket_get(request: Request):
    """تیکت پشتیبانی باز فعلی کاربر (اگر باشد) + پیام‌ها."""
    uid = _auth(request)
    from db import ticket_ensure_schema, ticket_get_open_by_type, ticket_get_messages
    ticket_ensure_schema()
    t = ticket_get_open_by_type(uid, _support_ticket_type(uid))
    if not t:
        return {"ok": True, "ticket": None, "messages": []}
    msgs = ticket_get_messages(int(t["id"]))
    return {
        "ok": True,
        "ticket": _ticket_to_dict(t),
        "messages": [
            {"id": int(m["id"]), "sender": m["sender"], "text": m["text"] or "",
             "media_type": m["media_type"] if "media_type" in m.keys() else None,
             "image_url": (f"/api/v1/support/media/{int(m['id'])}"
                            if ("media_type" in m.keys() and m["media_type"] == "photo"
                                and "media_file_id" in m.keys() and m["media_file_id"]) else None),
             "created_at": str(m["created_at"] or "")}
            for m in msgs
        ],
    }


@router.get("/support/media/{message_id}")
async def api_support_media(message_id: int):
    """پراکسی عکس یه پیام تیکت — از همون file_id تلگرام (چه پیام از ربات اومده چه از مینی‌اپ)."""
    from db import ticket_get_messages, _get_connection
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT media_file_id, media_type FROM ticket_messages WHERE id=? LIMIT 1;",
            (message_id,)).fetchone()
    finally:
        conn.close()
    if not row or not row["media_file_id"] or row["media_type"] != "photo":
        raise HTTPException(404, "یافت نشد")
    from config import BOT_TOKEN
    import httpx
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            info = (await client.get(
                f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
                params={"file_id": row["media_file_id"]})).json()
            file_path = info["result"]["file_path"]
            img = await client.get(f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}")
        from fastapi.responses import Response
        return Response(img.content, media_type="image/jpeg")
    except Exception:
        raise HTTPException(502, "خطا در دریافت عکس")


@router.post("/support/ticket")
async def api_support_ticket_create(request: Request):
    """شروع تیکت پشتیبانی جدید — اگر از قبل باز باشه همونو برمی‌گردونه.
    برای همکاران تأییدشده، تیکت با نوع partner_support ساخته می‌شه."""
    uid = _auth(request)
    from db import ticket_ensure_schema, ticket_get_open_by_type, ticket_create
    ticket_ensure_schema()
    ttype = _support_ticket_type(uid)
    t = ticket_get_open_by_type(uid, ttype)
    if not t:
        tid = ticket_create(uid, type_=ttype)
        from db import ticket_get
        t = ticket_get(tid)
    return {"ok": True, "ticket": _ticket_to_dict(t)}


def _notify_admin_ticket(ticket_id: int, uid: int, text: str, ttype: str = "support") -> None:
    from config import BOT_TOKEN, ADMIN_ID
    import requests
    if not BOT_TOKEN or not ADMIN_ID:
        return
    label = "🤝 پیام همکار جدید" if ttype == "partner_support" else "🔵 پیام پشتیبانی جدید"
    try:
        requests.post(
            f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage",
            json={
                "chat_id": ADMIN_ID,
                "text": (f"{label} (از مینی‌اپ)\n"
                         f"تیکت #{ticket_id} — کاربر {uid}\n\n{text[:300]}\n\n"
                         f"https://panel.stland.ir/admin/tickets/{ticket_id}"),
            },
            timeout=10,
        )
    except Exception:
        pass


@router.post("/support/message")
async def api_support_message(request: Request):
    """ارسال پیام کاربر به تیکت باز — دقیقاً هم‌منطق با _ticket_v2_handle_user_message ربات
    (سقف ۳ پیام متوالی تا پاسخ ادمین، نوتیف ادمین فقط روی اولین پیام batch).

    multipart/form-data: text (اختیاری) + photo (اختیاری) — حداقل یکی الزامیه.
    عکس هم مثل کارت‌به‌کارت به تلگرام آپلود می‌شه تا file_id واقعی بگیره، پس پنل ادمین
    (که رسیدها/تیکت‌ها رو با getFile می‌خونه) بدون هیچ تغییری همینو نشون می‌ده."""
    uid = _auth(request)
    form = await request.form()
    text = str(form.get("text") or "").strip()
    photo = form.get("photo")
    has_photo = photo is not None and hasattr(photo, "read")
    if not text and not has_photo:
        raise HTTPException(400, "متن یا عکس ارسال نشده")

    from db import ticket_ensure_schema, ticket_get_open_by_type, ticket_get, \
        ticket_add_message, ticket_user_sent
    ticket_ensure_schema()
    ttype = _support_ticket_type(uid)
    t = ticket_get_open_by_type(uid, ttype)
    if not t or t["status"] == "closed":
        raise HTTPException(400, "تیکت باز یافت نشد — یک تیکت جدید شروع کنید")

    tid = int(t["id"])
    cur_count = int(t["user_msg_count"] or 0)
    if cur_count >= TICKET_MAX_USER_MSGS:
        raise HTTPException(429, "لطفاً منتظر پاسخ پشتیبانی بمانید")

    media_type = None
    media_file_id = None
    if has_photo:
        photo_bytes = await photo.read()
        if photo_bytes:
            media_file_id = await _upload_photo_to_telegram(
                photo_bytes, photo.content_type, f"عکس تیکت #{tid} — کاربر {uid} (از مینی‌اپ)")
            media_type = "photo"

    ticket_add_message(tid, "user", text or None, media_type=media_type,
                        media_file_id=media_file_id, source="miniapp")
    new_count = ticket_user_sent(tid)
    if new_count == 1:
        _notify_admin_ticket(tid, uid, text or "📷 عکس", ttype)

    t2 = ticket_get(tid)
    return {"ok": True, "ticket": _ticket_to_dict(t2), "remaining": max(0, TICKET_MAX_USER_MSGS - new_count)}


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
    """فهرست محتوا برای PWA — kind: tutorial | news | feature (خالی = همه).

    برای kind=news، به‌جای فهرست پست، لینک آرشیو کامل وبلاگ (blog_url) هم
    برگردونده می‌شه — تصمیم مالک پروژه: تب «خبر» اپ فقط به وبلاگ خارجی
    ارجاع بده، محتوای خبر داخل اپ تکرار/مدیریت نشه."""
    from db import get_app_content, get_cfg
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
            "link_url": it.get("link_url") or "",
            "created_at": str(it.get("created_at") or "")[:16],
        })
    return {"ok": True, "items": out, "blog_url": get_cfg("NEWS_BLOG_URL", "")}


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
        "link_url": it.get("link_url") or "",
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

@router.post("/discount/validate")
async def api_discount_validate(request: Request):
    """
    پیش‌نمایش کد تخفیف قبل از خرید — فقط اعتبارسنجی، مصرف نمی‌کند.
    body: { product_id, code }
    """
    uid = _auth(request)
    if not uid:
        raise HTTPException(401, "احراز هویت لازم است")

    body = await request.json()
    pid = int(body.get("product_id", 0))
    code = str(body.get("code", "")).strip()
    if not pid or not code:
        raise HTTPException(400, "product_id و code الزامی هستند")

    from core.products import get_product
    from db import validate_discount, is_partner_approved

    prod = get_product(pid)
    if not prod or not prod.get("is_active"):
        raise HTTPException(404, "محصول یافت نشد")

    is_partner = is_partner_approved(uid)
    partner_price = int(prod.get("partner_price") or 0)
    base_price = int(prod["effective_price"])
    price = (partner_price if is_partner and partner_price > 0 and partner_price < base_price
             else base_price)

    result = validate_discount(code, product_id=pid, amount=price, user_id=uid)
    if not result["valid"]:
        return {"ok": False, "error": result["error"]}
    final_price = max(0, price - int(result["discount_amount"]))
    return {"ok": True, "discount_amount": int(result["discount_amount"]),
            "price": price, "final_price": final_price}


@router.post("/checkout")
async def api_checkout(request: Request):
    """
    شروع خرید از PWA.
    body: { product_id, payment_type: "wallet"|"gateway"|"combined",
            discount_code?, wallet_amount?, initData }
    برای wallet: کسر از کیف‌پول و ثبت سفارش.
    برای gateway/combined: درخواست Zarinpal و بازگشت redirect_url.
    """
    uid = _auth(request)
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
                    create_order, is_partner_approved,
                    validate_discount, use_discount)

    prod = get_product(pid)
    if not prod or not prod.get("is_active"):
        raise HTTPException(404, "محصول یافت نشد")

    # قیمت موثر (همکار یا عادی)
    is_partner = is_partner_approved(uid)
    partner_price = int(prod.get("partner_price") or 0)
    base_price = int(prod["effective_price"])
    final_price = (partner_price if is_partner and partner_price > 0 and partner_price < base_price
                   else base_price)

    # کد تخفیف — اعتبارسنجی مجدد سمت سرور (هرگز به مبلغ کلاینت اعتماد نکن)
    discount_code = str(body.get("discount_code", "")).strip()
    if discount_code:
        d = validate_discount(discount_code, product_id=pid, amount=final_price, user_id=uid)
        if not d["valid"]:
            raise HTTPException(400, d["error"])
        final_price = max(0, final_price - int(d["discount_amount"]))
        use_discount(d["code_id"], user_id=uid)

    wallet_bal = get_wallet_balance(uid)

    if ptype == "wallet":
        if wallet_bal < final_price:
            raise HTTPException(400, f"موجودی کیف‌پول کافی نیست (موجودی: {wallet_bal:,} — نیاز: {final_price:,} تومان)")
        ok = subtract_wallet_balance(uid, final_price)
        if not ok:
            raise HTTPException(400, "کسر از کیف‌پول ناموفق بود")
        oid = create_order(uid, prod.get("category",""), prod["title"],
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
            oid = create_order(uid, prod.get("category",""), prod["title"],
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

    if r.status_code != 200 or not data.get("payment_url"):
        raise HTTPException(502, data.get("detail") or "درگاه پاسخ نداد")

    return {"ok": True, "method": "gateway",
            "redirect_url": data["payment_url"],
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
