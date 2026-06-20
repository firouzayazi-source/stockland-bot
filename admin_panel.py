"""
admin_panel.py — پنل مدیریت وب استوک لند (نسخه کامل)
────────────────────────────────────────────────────
ویژگی‌ها:
  - سیستم ادمین چندنفره با اختیارات مجزا
  - مدیریت کامل تنظیمات ربات
  - بکاپ / بازیابی / ریست دیتابیس
  - مدیریت ادمین‌ها از پنل وب
"""

import hashlib
import hmac as _hmac
import html
import json
import os
import shutil
import sqlite3
from datetime import datetime

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse

router = APIRouter(prefix="/admin")

# ─────────────────────────── Config ────────────────────────────────────────

def _env(k: str, default: str = "") -> str:
    return os.getenv(k) or default

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_env("DB_PATH"), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

# ─────────────────────────── Permissions ───────────────────────────────────

ALL_PERMISSIONS = {
    "products":  "مدیریت محصولات",
    "feed":      "مدیریت موجودی",
    "orders":    "مشاهده سفارش‌ها",
    "wallets":   "مدیریت کیف‌پول",
    "partners":  "مدیریت همکاران",
    "settings":  "تنظیمات ربات",
    "database":  "بکاپ و دیتابیس",
    "admins":    "مدیریت ادمین‌ها",
    "broadcast": "پیام همگانی",
}

# ─────────────────────────── DB Schema for Admins ──────────────────────────

def ensure_admins_table() -> None:
    try:
        conn = _db()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE,
                name TEXT NOT NULL,
                web_username TEXT UNIQUE,
                web_password_hash TEXT,
                permissions TEXT DEFAULT '[]',
                is_active INTEGER DEFAULT 1,
                notes TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass

# ─────────────────────────── Auth & Session ────────────────────────────────

def _hash_pw(password: str) -> str:
    secret = _env("SESSION_SECRET", "stockland")
    return hashlib.sha256((secret + password).encode()).hexdigest()

def _make_session(admin_id: str) -> str:
    secret = _env("SESSION_SECRET", "stockland-panel")
    token = _hmac.new(secret.encode(), admin_id.encode(), hashlib.sha256).hexdigest()
    return f"{token}:{admin_id}"

def _get_admin(request: Request):
    """Returns (admin_id, is_super, permissions_list) or None."""
    ensure_admins_table()
    cookie = request.cookies.get("adm", "")
    if not cookie or ":" not in cookie:
        return None

    token, admin_id = cookie.rsplit(":", 1)
    expected_token = _hmac.new(
        _env("SESSION_SECRET", "stockland-panel").encode(),
        admin_id.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not _hmac.compare_digest(token, expected_token):
        return None

    if admin_id == "super":
        return ("super", True, list(ALL_PERMISSIONS.keys()))

    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, permissions, is_active FROM admins WHERE id=? LIMIT 1;",
            (int(admin_id),),
        ).fetchone()
        conn.close()
        if not row or not row["is_active"]:
            return None
        perms = json.loads(row["permissions"] or "[]")
        return (str(row["id"]), False, perms)
    except Exception:
        return None

def _has(admin_info, perm: str) -> bool:
    if not admin_info:
        return False
    _, is_super, perms = admin_info
    return is_super or perm in perms

def _require(admin_info, perm: str):
    """Returns 403 redirect if admin lacks permission."""
    if not admin_info:
        return RedirectResponse("/admin/login", status_code=303)
    if not _has(admin_info, perm):
        return RedirectResponse("/admin/?err=noperm", status_code=303)
    return None

def _redir(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)

# ─────────────────────────── HTML helpers ──────────────────────────────────

def e(s) -> str:
    return html.escape(str(s or ""))

def _layout(title: str, body: str, admin_info=None,
            flash: str = "", flash_ok: bool = True) -> HTMLResponse:

    flash_html = ""
    if flash:
        color = "green" if flash_ok else "red"
        icon  = "✅" if flash_ok else "❌"
        flash_html = f"""
        <div class="mb-4 px-4 py-3 rounded-lg bg-{color}-50 border border-{color}-200
             text-{color}-800 text-sm flex items-center gap-2">
          <span>{icon}</span> {e(flash)}
        </div>"""

    # Build nav based on permissions
    perms = admin_info[2] if admin_info else []
    is_super = admin_info[1] if admin_info else False

    def nav_link(href, label, perm=None):
        if perm and not is_super and perm not in perms:
            return ""
        return f'<a href="{href}" class="text-indigo-200 hover:text-white text-sm transition">{label}</a>'

    nav = f"""
    <nav class="bg-indigo-900 text-white shadow-xl sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4 flex-wrap text-sm">
        <a href="/admin/" class="font-bold text-lg text-white">🛍 استوک لند</a>
        {nav_link("/admin/", "📊 داشبورد")}
        {nav_link("/admin/products", "📦 محصولات", "products")}
        {nav_link("/admin/feed", "🗃 موجودی", "feed")}
        {nav_link("/admin/orders", "🧾 سفارش‌ها", "orders")}
        {nav_link("/admin/wallets", "💰 کیف‌پول", "wallets")}
        {nav_link("/admin/partners", "🤝 همکاران", "partners")}
        {nav_link("/admin/settings", "⚙️ تنظیمات", "settings")}
        {nav_link("/admin/database", "💾 دیتابیس", "database")}
        {nav_link("/admin/admins", "👥 ادمین‌ها", "admins")}
        <a href="/admin/logout" class="mr-auto text-red-300 hover:text-red-100 transition">خروج ↩</a>
      </div>
    </nav>"""

    if not admin_info:
        nav = ""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{e(title)} — پنل ادمین</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>body{{font-family:Tahoma,sans-serif}}</style>
</head>
<body class="bg-slate-100 min-h-screen">
{nav}
<main class="max-w-7xl mx-auto px-4 py-6">
  {flash_html}
  {body}
</main>
</body>
</html>""")

def _card(title, value, sub="", color="indigo"):
    return f"""
    <div class="bg-white rounded-xl shadow p-5 border-r-4 border-{color}-500">
      <div class="text-xs text-gray-500 mb-1">{e(title)}</div>
      <div class="text-3xl font-bold text-{color}-700">{value}</div>
      {f'<div class="text-xs text-gray-400 mt-1">{e(sub)}</div>' if sub else ""}
    </div>"""

def _btn(text, href="", color="indigo", small=False, danger=False):
    sz = "px-3 py-1.5 text-xs" if small else "px-4 py-2 text-sm"
    c = "red" if danger else color
    if href:
        return f'<a href="{e(href)}" class="{sz} bg-{c}-600 hover:bg-{c}-700 text-white rounded-lg font-medium transition inline-block">{text}</a>'
    return f'<button type="submit" class="{sz} bg-{c}-600 hover:bg-{c}-700 text-white rounded-lg font-medium transition">{text}</button>'

def _input(name, placeholder="", value="", type_="text", required=False):
    req = "required" if required else ""
    return f'<input type="{type_}" name="{name}" value="{e(value)}" placeholder="{e(placeholder)}" {req} class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">'

def _textarea(name, placeholder="", value="", rows=4):
    return f'<textarea name="{name}" rows="{rows}" placeholder="{e(placeholder)}" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">{e(value)}</textarea>'

# ─────────────────────────── Login / Logout ────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, err: str = ""):
    adm = _get_admin(request)
    if adm:
        return _redir("/admin/")

    err_html = ""
    if err == "1":
        err_html = '<div class="mb-4 text-red-600 text-sm text-center bg-red-50 p-2 rounded-lg">❌ نام کاربری یا رمز اشتباه است</div>'

    body = f"""
    <div class="min-h-screen flex items-center justify-center -mt-16">
      <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <div class="text-center mb-6">
          <div class="text-4xl mb-2">🛍</div>
          <h1 class="text-xl font-bold text-gray-800">پنل مدیریت استوک لند</h1>
        </div>
        {err_html}
        <form method="post" action="/admin/login" class="space-y-4">
          <div>
            <label class="text-sm text-gray-600 block mb-1">نام کاربری</label>
            {_input("username", "نام کاربری", required=True)}
          </div>
          <div>
            <label class="text-sm text-gray-600 block mb-1">رمز ورود</label>
            {_input("password", "رمز ورود", type_="password", required=True)}
          </div>
          {_btn("ورود به پنل ←")}
        </form>
      </div>
    </div>"""
    return _layout("ورود", body)

@router.post("/login")
async def login_post(username: str = Form(""), password: str = Form("")):
    ensure_admins_table()
    username = username.strip()
    password = password.strip()

    # سوپرادمین
    super_pw = _env("ADMIN_WEB_PASSWORD")
    if username.lower() in ("admin", "super") and super_pw and _hmac.compare_digest(password, super_pw):
        resp = _redir("/admin/")
        resp.set_cookie("adm", _make_session("super"), max_age=86400 * 7, httponly=True, samesite="lax")
        return resp

    # ادمین از دیتابیس
    try:
        conn = _db()
        row = conn.execute(
            "SELECT id, web_password_hash, is_active FROM admins WHERE web_username=? LIMIT 1;",
            (username,),
        ).fetchone()
        conn.close()
        if row and row["is_active"] and row["web_password_hash"] == _hash_pw(password):
            resp = _redir("/admin/")
            resp.set_cookie("adm", _make_session(str(row["id"])), max_age=86400 * 7, httponly=True, samesite="lax")
            return resp
    except Exception:
        pass

    return _redir("/admin/login?err=1")

@router.get("/logout")
async def logout():
    resp = _redir("/admin/login")
    resp.delete_cookie("adm")
    return resp

# ─────────────────────────── Dashboard ─────────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, err: str = ""):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    flash = "دسترسی کافی ندارید." if err == "noperm" else ""

    conn = _db()
    try:
        wallets  = conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM wallets;").fetchone()
        orders   = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders;").fetchone()
        products = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1;").fetchone()[0]
        feed_avail = conn.execute("SELECT COUNT(*) FROM product_feed WHERE delivered=0;").fetchone()[0]
        pending  = conn.execute("SELECT COUNT(*) FROM pending_deliveries WHERE status='pending';").fetchone()[0]
        today    = datetime.utcnow().date().isoformat()
        today_o  = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at LIKE ?;", (today+"%",)).fetchone()
        partners_pend = conn.execute("SELECT COUNT(*) FROM partners WHERE status='pending';").fetchone()[0]

        low_stock = conn.execute("""
            SELECT p.id, p.title, COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as avail,
                   COALESCE(fas.threshold, 5) as threshold
            FROM products p
            LEFT JOIN product_feed pf ON pf.product_id=p.id
            LEFT JOIN feed_alert_settings fas ON fas.product_id=p.id
            WHERE p.is_active=1 GROUP BY p.id HAVING avail<=threshold ORDER BY avail ASC LIMIT 8;
        """).fetchall()

        recent = conn.execute("""
            SELECT id, user_id, title, price, created_at FROM orders ORDER BY id DESC LIMIT 8;
        """).fetchall()
    finally:
        conn.close()

    low_rows = "".join(f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-2 text-sm">{e(r["title"])}</td>
          <td class="px-4 py-2">
            <span class="px-2 py-0.5 text-xs rounded-full bg-{"red" if r["avail"]==0 else "yellow"}-100 text-{"red" if r["avail"]==0 else "yellow"}-700">{r["avail"]} عدد</span>
          </td>
          <td class="px-4 py-2">{_btn("افزودن موجودی", f"/admin/feed/{r['id']}", "indigo", small=True)}</td>
        </tr>""" for r in low_stock)

    recent_rows = "".join(f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-2 text-gray-400">#{o["id"]}</td>
          <td class="px-4 py-2">{e(o["title"])}</td>
          <td class="px-4 py-2 font-mono text-xs">{o["user_id"]}</td>
          <td class="px-4 py-2 text-green-700 font-medium">{int(o["price"]):,} ت</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(o["created_at"] or "")[:16]}</td>
        </tr>""" for o in recent)

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">📊 داشبورد</h1>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
      {_card("فروش امروز", f'{int(today_o[0]):,}', f'{int(today_o[1]):,} تومان', "green")}
      {_card("کل فروش", f'{int(orders[1]):,}', f'{int(orders[0]):,} سفارش', "indigo")}
      {_card("موجودی فید", str(feed_avail), "در صف تحویل", "blue")}
      {_card("کیف‌پول‌ها", str(int(wallets[0])), f'{int(wallets[1]):,} تومان کل', "purple")}
    </div>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-4 mb-6">
      {_card("محصولات فعال", str(products), "", "teal")}
      {_card("در صف تحویل", str(pending), "منتظر ارسال", "orange")}
      {_card("همکار در انتظار", str(partners_pend), "نیاز به بررسی", "yellow")}
    </div>
    <div class="grid md:grid-cols-2 gap-6">
      <div class="bg-white rounded-xl shadow p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-gray-700">⚠️ کم‌موجودی</h2>
          {_btn("همه موجودی‌ها", "/admin/feed", "indigo", small=True)}
        </div>
        {"<p class='text-sm text-green-600'>✅ همه محصولات موجودی کافی دارند.</p>" if not low_stock else f"<table class='w-full'><tbody>{low_rows}</tbody></table>"}
      </div>
      <div class="bg-white rounded-xl shadow p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-gray-700">🧾 سفارش‌های اخیر</h2>
          {_btn("همه", "/admin/orders", "indigo", small=True)}
        </div>
        <table class="w-full"><tbody>{recent_rows or "<tr><td class='text-center py-4 text-gray-400 text-sm'>سفارشی ثبت نشده</td></tr>"}</tbody></table>
      </div>
    </div>"""

    return _layout("داشبورد", body, adm, flash=flash, flash_ok=False)

# ─────────────────────────── Settings ──────────────────────────────────────

DEFAULT_UI_TEXTS = {
    "MAIN_BTN_OTHER_PRODUCTS": "سایر محصولات فروشگاه 🛍",
    "MAIN_BTN_BUY_APPLE_ID":  "سرویس اپل آیدی 📱",
    "MAIN_BTN_MY_ORDERS":     "خرید های من 🧾",
    "MAIN_BTN_WALLET":        "کیف پول 💰",
    "MAIN_BTN_PARTNER_REQUEST":"درخواست نمایندگی 📝",
    "MAIN_BTN_PARTNER_PANEL": "پنل همکار 🤝",
    "MAIN_BTN_GUIDE":         "راهنما 🔑",
    "MAIN_BTN_SUPPORT":       "پشتیبانی 👨‍💻",
    "SUPPORT_TEXT":           "متن پشتیبانی...",
    "HELP_TEXT":              "متن راهنما...",
    "TXT_MAIN_MENU_TITLE":    "منوی اصلی",
}

MAIN_BUTTONS = [
    "MAIN_BTN_OTHER_PRODUCTS",
    "MAIN_BTN_BUY_APPLE_ID",
    "MAIN_BTN_MY_ORDERS",
    "MAIN_BTN_WALLET",
    "MAIN_BTN_PARTNER_REQUEST",
    "MAIN_BTN_PARTNER_PANEL",
    "MAIN_BTN_GUIDE",
    "MAIN_BTN_SUPPORT",
]

def _get_ui(conn, key: str) -> str:
    try:
        row = conn.execute("SELECT value FROM ui_texts WHERE key=? LIMIT 1;", (key,)).fetchone()
        return row["value"] if row else DEFAULT_UI_TEXTS.get(key, "")
    except Exception:
        return DEFAULT_UI_TEXTS.get(key, "")

def _set_ui(conn, key: str, value: str) -> None:
    now = datetime.utcnow().isoformat()
    conn.execute(
        "INSERT INTO ui_texts(key,value,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
        (key, value, now),
    )

@router.get("/settings", response_class=HTMLResponse)
async def settings_get(request: Request, tab: str = "texts", flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard:
        return guard

    conn = _db()
    try:
        # UI texts
        texts = {k: _get_ui(conn, k) for k in DEFAULT_UI_TEXTS}

        # Button enabled/disabled
        btn_states = {}
        for k in MAIN_BUTTONS:
            flag_key = f"MAIN_BTN_ENABLED_{k}"
            val = _get_ui(conn, flag_key)
            btn_states[k] = val not in ("0", "false", "off", "no")

        # Other services
        services = conn.execute(
            "SELECT service_key, title, emoji, is_active FROM other_services ORDER BY title;"
        ).fetchall()
    finally:
        conn.close()

    # Tab: متن‌ها
    text_fields = ""
    for key, default in DEFAULT_UI_TEXTS.items():
        label = key.replace("MAIN_BTN_", "دکمه: ").replace("TXT_", "عنوان: ").replace("_TEXT", " متن").replace("_", " ")
        is_long = "TEXT" in key or "TITLE" in key
        val = texts.get(key, default)
        text_fields += f"""
        <div class="mb-4">
          <label class="text-xs font-medium text-gray-500 block mb-1">{e(label)}</label>
          {"_textarea(key, default, val, rows=3)" if is_long else f'<input type="text" name="{e(key)}" value="{e(val)}" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">'}
        </div>"""

    # Fix: replace placeholder textarea calls
    for key, default in DEFAULT_UI_TEXTS.items():
        if "TEXT" in key or "TITLE" in key:
            val = texts.get(key, default)
            text_fields = text_fields.replace(
                f'"_textarea(key, default, val, rows=3)"',
                f'<textarea name="{e(key)}" rows="3" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">{e(val)}</textarea>'
            )

    # Rebuild text fields properly
    text_fields = ""
    for key, default in DEFAULT_UI_TEXTS.items():
        label = {
            "MAIN_BTN_OTHER_PRODUCTS": "دکمه: سایر محصولات",
            "MAIN_BTN_BUY_APPLE_ID":  "دکمه: اپل آیدی",
            "MAIN_BTN_MY_ORDERS":     "دکمه: خریدهای من",
            "MAIN_BTN_WALLET":        "دکمه: کیف پول",
            "MAIN_BTN_PARTNER_REQUEST":"دکمه: درخواست نمایندگی",
            "MAIN_BTN_PARTNER_PANEL": "دکمه: پنل همکار",
            "MAIN_BTN_GUIDE":         "دکمه: راهنما",
            "MAIN_BTN_SUPPORT":       "دکمه: پشتیبانی",
            "SUPPORT_TEXT":           "متن پشتیبانی",
            "HELP_TEXT":              "متن راهنما",
            "TXT_MAIN_MENU_TITLE":    "عنوان منوی اصلی",
        }.get(key, key)
        val = texts.get(key, default)
        is_long = key in ("SUPPORT_TEXT", "HELP_TEXT")
        if is_long:
            field = f'<textarea name="{e(key)}" rows="4" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">{e(val)}</textarea>'
        else:
            field = f'<input type="text" name="{e(key)}" value="{e(val)}" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">'
        text_fields += f"""
        <div class="mb-4">
          <label class="text-xs font-medium text-gray-500 block mb-1">{e(label)}</label>
          {field}
        </div>"""

    # Tab: دکمه‌ها
    btn_rows = ""
    btn_labels = {
        "MAIN_BTN_OTHER_PRODUCTS": "سایر محصولات فروشگاه",
        "MAIN_BTN_BUY_APPLE_ID":  "سرویس اپل آیدی",
        "MAIN_BTN_MY_ORDERS":     "خریدهای من",
        "MAIN_BTN_WALLET":        "کیف پول",
        "MAIN_BTN_PARTNER_REQUEST":"درخواست نمایندگی",
        "MAIN_BTN_PARTNER_PANEL": "پنل همکار",
        "MAIN_BTN_GUIDE":         "راهنما",
        "MAIN_BTN_SUPPORT":       "پشتیبانی",
    }
    for k in MAIN_BUTTONS:
        enabled = btn_states.get(k, True)
        badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">فعال</span>' if enabled else '<span class="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700">غیرفعال</span>'
        btn_rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 text-sm">{e(btn_labels.get(k, k))}</td>
          <td class="px-4 py-3">{badge}</td>
          <td class="px-4 py-3">
            <form method="post" action="/admin/settings/toggle-btn">
              <input type="hidden" name="key" value="{e(k)}">
              <button class="px-3 py-1 text-xs rounded border border-gray-300 hover:bg-gray-50">
                {"غیرفعال کن" if enabled else "فعال کن"}
              </button>
            </form>
          </td>
        </tr>"""

    # Tab: دسته‌بندی‌ها
    svc_rows = ""
    for s in services:
        badge = '<span class="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">فعال</span>' if s["is_active"] else '<span class="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">غیرفعال</span>'
        svc_rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 text-sm">{e(s["emoji"] or "")} {e(s["title"])}</td>
          <td class="px-4 py-3 text-xs text-gray-400"><code>{e(s["service_key"])}</code></td>
          <td class="px-4 py-3">{badge}</td>
          <td class="px-4 py-3 flex gap-2">
            <form method="post" action="/admin/settings/toggle-svc">
              <input type="hidden" name="key" value="{e(s['service_key'])}">
              <button class="px-2 py-1 text-xs border rounded hover:bg-gray-50">{"غیرفعال" if s["is_active"] else "فعال"}</button>
            </form>
            {"" if s["service_key"] == "general" else f'''
            <form method="post" action="/admin/settings/delete-svc" onsubmit="return confirm('حذف شود؟')">
              <input type="hidden" name="key" value="{e(s["service_key"])}">
              <button class="px-2 py-1 text-xs border border-red-200 text-red-500 rounded hover:bg-red-50">حذف</button>
            </form>'''}
          </td>
        </tr>"""

    tabs = {
        "texts":    ("📝 متن‌ها", f"""
            <form method="post" action="/admin/settings/save-texts" class="space-y-2">
              {text_fields}
              <div class="pt-4">{_btn("ذخیره همه متن‌ها", color="green")}</div>
            </form>"""),
        "buttons":  ("🔘 دکمه‌های منو", f"""
            <table class="w-full text-right">
              <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
                <th class="px-4 py-3">دکمه</th><th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">عملیات</th>
              </tr></thead>
              <tbody>{btn_rows}</tbody>
            </table>"""),
        "services": ("🗂 دسته‌بندی‌ها", f"""
            <div class="mb-4">
              <form method="post" action="/admin/settings/add-svc" class="flex gap-3 items-end flex-wrap">
                <div><label class="text-xs text-gray-500 block mb-1">عنوان</label>
                  {_input("title", "نام دسته جدید", required=True)}</div>
                <div><label class="text-xs text-gray-500 block mb-1">ایموجی (اختیاری)</label>
                  {_input("emoji", "🧩")}</div>
                {_btn("➕ افزودن", color="green")}
              </form>
            </div>
            <table class="w-full text-right">
              <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
                <th class="px-4 py-3">عنوان</th><th class="px-4 py-3">کلید</th>
                <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">عملیات</th>
              </tr></thead>
              <tbody>{svc_rows or "<tr><td colspan='4' class='text-center py-4 text-gray-400'>دسته‌ای ثبت نشده</td></tr>"}</tbody>
            </table>"""),
    }

    tab_nav = ""
    for tid, (tlabel, _) in tabs.items():
        active = "bg-indigo-600 text-white" if tab == tid else "bg-white text-gray-600 hover:bg-gray-50"
        tab_nav += f'<a href="/admin/settings?tab={tid}" class="px-4 py-2 rounded-lg border text-sm {active} transition">{tlabel}</a>'

    _, (_, tab_content) = [(k, v) for k, v in tabs.items() if k == tab][0], tabs.get(tab, list(tabs.values())[0])

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">⚙️ تنظیمات ربات</h1>
    <div class="flex gap-2 mb-6">{tab_nav}</div>
    <div class="bg-white rounded-xl shadow p-6">{tab_content}</div>"""

    return _layout("تنظیمات", body, adm, flash=flash)

@router.post("/settings/save-texts")
async def settings_save_texts(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    form = await request.form()
    conn = _db()
    try:
        for key in DEFAULT_UI_TEXTS:
            val = (form.get(key) or "").strip()
            if val:
                _set_ui(conn, key, val)
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?tab=texts&flash=متن‌ها+ذخیره+شد")

@router.post("/settings/toggle-btn")
async def settings_toggle_btn(request: Request, key: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    if key not in MAIN_BUTTONS:
        return _redir("/admin/settings?tab=buttons")
    flag_key = f"MAIN_BTN_ENABLED_{key}"
    conn = _db()
    try:
        cur_val = _get_ui(conn, flag_key)
        is_on = cur_val not in ("0", "false", "off", "no")
        # prevent disabling last button
        if is_on:
            enabled_count = sum(
                1 for k in MAIN_BUTTONS
                if _get_ui(conn, f"MAIN_BTN_ENABLED_{k}") not in ("0", "false", "off", "no")
            )
            if enabled_count <= 1:
                conn.close()
                return _redir("/admin/settings?tab=buttons&flash=حداقل+یک+دکمه+باید+فعال+بماند")
        _set_ui(conn, flag_key, "0" if is_on else "1")
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?tab=buttons&flash=وضعیت+دکمه+تغییر+کرد")

@router.post("/settings/add-svc")
async def settings_add_svc(request: Request, title: str = Form(""), emoji: str = Form("🧩")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    title = title.strip()
    if not title:
        return _redir("/admin/settings?tab=services")
    key = title.replace(" ", "_")[:32]
    conn = _db()
    try:
        now = datetime.utcnow().isoformat()
        conn.execute(
            "INSERT OR IGNORE INTO other_services (service_key, title, emoji, is_active, created_at) VALUES (?,?,?,1,?);",
            (key, title, emoji.strip() or "🧩", now),
        )
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?tab=services&flash=دسته+اضافه+شد")

@router.post("/settings/toggle-svc")
async def settings_toggle_svc(request: Request, key: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("UPDATE other_services SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE service_key=?;", (key,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?tab=services&flash=وضعیت+تغییر+کرد")

@router.post("/settings/delete-svc")
async def settings_delete_svc(request: Request, key: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard
    if key == "general":
        return _redir("/admin/settings?tab=services")
    conn = _db()
    try:
        conn.execute("DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category=?);", (key,))
        conn.execute("DELETE FROM products WHERE category=?;", (key,))
        conn.execute("DELETE FROM other_services WHERE service_key=?;", (key,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?tab=services&flash=دسته+حذف+شد")

# ─────────────────────────── Database ──────────────────────────────────────

@router.get("/database", response_class=HTMLResponse)
async def database_page(request: Request, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    db_path = _env("DB_PATH")
    try:
        size_bytes = os.path.getsize(db_path) if os.path.exists(db_path) else 0
        size_str = f"{size_bytes / 1024:.1f} KB"
    except Exception:
        size_str = "نامشخص"

    conn = _db()
    try:
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;"
        ).fetchall()
        table_info = []
        for t in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {t['name']};").fetchone()[0]
            table_info.append((t["name"], count))
    finally:
        conn.close()

    table_rows = "".join(f"""
        <tr class="border-b">
          <td class="px-4 py-2 text-sm font-mono">{e(name)}</td>
          <td class="px-4 py-2 text-sm text-gray-500">{count:,} ردیف</td>
        </tr>""" for name, count in table_info)

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">💾 مدیریت دیتابیس</h1>

    <div class="grid md:grid-cols-3 gap-6 mb-6">
      <!-- Backup -->
      <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-bold text-gray-700 mb-2">📤 بکاپ</h2>
        <p class="text-sm text-gray-500 mb-4">حجم دیتابیس: <strong>{size_str}</strong></p>
        <a href="/admin/database/backup" class="block w-full text-center py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition">دانلود بکاپ</a>
      </div>

      <!-- Restore -->
      <div class="bg-white rounded-xl shadow p-6">
        <h2 class="font-bold text-gray-700 mb-2">📥 بازیابی</h2>
        <p class="text-sm text-gray-500 mb-4">فایل SQLite بارگذاری کنید.</p>
        <form method="post" action="/admin/database/restore" enctype="multipart/form-data">
          <input type="file" name="backup_file" accept=".sqlite,.db" required
            class="w-full text-sm mb-3 file:mr-2 file:py-1 file:px-3 file:rounded file:border-0 file:text-sm file:bg-indigo-50 file:text-indigo-700">
          <button type="submit" onclick="return confirm('آیا مطمئنید؟ دیتابیس فعلی جایگزین می‌شود.')"
            class="w-full py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium">
            بازیابی بکاپ
          </button>
        </form>
      </div>

      <!-- Reset -->
      <div class="bg-white rounded-xl shadow p-6 border-2 border-red-100">
        <h2 class="font-bold text-red-700 mb-2">⚠️ ریست کامل</h2>
        <p class="text-sm text-gray-500 mb-4">همه داده‌ها پاک می‌شود. غیرقابل بازگشت!</p>
        <form method="post" action="/admin/database/reset"
          onsubmit="return confirm('تأیید اول: آیا مطمئنید؟')">
          <input type="text" name="confirm_text" placeholder='بنویسید: RESET' required
            class="w-full border border-red-300 rounded px-3 py-2 text-sm mb-3 focus:ring-2 focus:ring-red-300">
          <button type="submit" class="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">
            ریست کامل
          </button>
        </form>
      </div>
    </div>

    <!-- Table Info -->
    <div class="bg-white rounded-xl shadow p-6">
      <h2 class="font-bold text-gray-700 mb-4">📊 جداول دیتابیس</h2>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-2">جدول</th><th class="px-4 py-2">تعداد ردیف</th>
        </tr></thead>
        <tbody>{table_rows}</tbody>
      </table>
    </div>"""

    return _layout("دیتابیس", body, adm, flash=flash)

@router.get("/database/backup")
async def database_backup(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    db_path = _env("DB_PATH")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp = f"/tmp/stockland_backup_{ts}.sqlite"

    src = sqlite3.connect(db_path, timeout=30)
    try:
        dst = sqlite3.connect(tmp, timeout=30)
        src.backup(dst)
        dst.close()
    finally:
        src.close()

    return FileResponse(tmp, filename=f"stockland_{ts}.sqlite", media_type="application/octet-stream")

@router.post("/database/restore")
async def database_restore(request: Request, backup_file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not backup_file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    db_path = _env("DB_PATH")
    ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    tmp = f"/tmp/restore_{ts}.sqlite"

    content = await backup_file.read()
    with open(tmp, "wb") as f:
        f.write(content)

    # Validate
    try:
        check = sqlite3.connect(tmp)
        tables = {r[0] for r in check.execute("SELECT name FROM sqlite_master WHERE type='table';").fetchall()}
        check.close()
        required = {"wallets", "products", "orders"}
        if not required.issubset(tables):
            os.remove(tmp)
            return _redir("/admin/database?flash=فایل+بکاپ+معتبر+نیست")
    except Exception:
        return _redir("/admin/database?flash=خطا+در+خواندن+فایل+بکاپ")

    # Replace
    bak = f"{db_path}.bak_{ts}"
    if os.path.exists(db_path):
        shutil.copy2(db_path, bak)
    shutil.move(tmp, db_path)

    return _redir("/admin/database?flash=بازیابی+موفق+ربات+ریستارت+می‌شود")

@router.post("/database/reset")
async def database_reset(request: Request, confirm_text: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if confirm_text.strip() != "RESET":
        return _redir("/admin/database?flash=متن+تأیید+اشتباه+است")

    conn = _db()
    try:
        conn.execute("BEGIN IMMEDIATE;")
        for table in ["products", "orders", "wallets", "wallet_orders", "product_feed",
                      "zarinpal_transactions", "pending_deliveries", "tickets",
                      "delivery_messages", "partners"]:
            try:
                conn.execute(f"DELETE FROM {table};")
            except Exception:
                pass
        try:
            conn.execute("DELETE FROM other_services WHERE service_key != 'general';")
        except Exception:
            pass
        conn.execute("DELETE FROM sqlite_sequence;")
        conn.commit()
    finally:
        conn.close()

    return _redir("/admin/database?flash=ریست+کامل+انجام+شد")

# ─────────────────────────── Admins ────────────────────────────────────────

@router.get("/admins", response_class=HTMLResponse)
async def admins_list(request: Request, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard

    ensure_admins_table()
    conn = _db()
    try:
        admins = conn.execute("SELECT * FROM admins ORDER BY id DESC;").fetchall()
    finally:
        conn.close()

    rows = ""
    for a in admins:
        perms = json.loads(a["permissions"] or "[]")
        perm_badges = " ".join(
            f'<span class="px-1.5 py-0.5 text-xs bg-blue-100 text-blue-700 rounded">{ALL_PERMISSIONS.get(p, p)}</span>'
            for p in perms
        ) or '<span class="text-gray-400 text-xs">بدون اختیار</span>'

        status = '<span class="text-xs text-green-600">فعال</span>' if a["is_active"] else '<span class="text-xs text-red-500">غیرفعال</span>'

        rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 font-medium text-sm">{e(a["name"])}</td>
          <td class="px-4 py-3 text-xs font-mono text-gray-500">{e(a["telegram_id"] or "-")}</td>
          <td class="px-4 py-3 text-xs text-gray-500">{e(a["web_username"] or "-")}</td>
          <td class="px-4 py-3">{perm_badges}</td>
          <td class="px-4 py-3">{status}</td>
          <td class="px-4 py-3 flex gap-2">
            {_btn("ویرایش", f"/admin/admins/{a['id']}/edit", "indigo", small=True)}
            <form method="post" action="/admin/admins/{a['id']}/toggle">
              <button class="px-2 py-1 text-xs border rounded hover:bg-gray-50">{"غیرفعال" if a["is_active"] else "فعال"}</button>
            </form>
            <form method="post" action="/admin/admins/{a['id']}/delete" onsubmit="return confirm('حذف شود؟')">
              <button class="px-2 py-1 text-xs border border-red-200 text-red-500 rounded hover:bg-red-50">حذف</button>
            </form>
          </td>
        </tr>"""

    # Permission checkboxes for add form
    perm_checks = ""
    for perm_key, perm_label in ALL_PERMISSIONS.items():
        perm_checks += f"""
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" name="perm_{perm_key}" value="1"
            class="rounded border-gray-300 text-indigo-600">
          {e(perm_label)}
        </label>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">👥 مدیریت ادمین‌ها</h1>

    <!-- Add Form -->
    <div class="bg-white rounded-xl shadow p-6 mb-6">
      <h2 class="font-bold text-gray-700 mb-4">➕ افزودن ادمین جدید</h2>
      <form method="post" action="/admin/admins/add" class="space-y-4">
        <div class="grid md:grid-cols-2 gap-4">
          <div>
            <label class="text-xs text-gray-500 block mb-1">نام نمایشی *</label>
            {_input("name", "مثلاً: پشتیبانی اول", required=True)}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">آیدی تلگرام (برای دسترسی در ربات)</label>
            {_input("telegram_id", "مثلاً: 123456789", type_="number")}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">یوزرنیم پنل وب *</label>
            {_input("web_username", "مثلاً: support1", required=True)}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">رمز پنل وب *</label>
            {_input("web_password", "رمز قوی انتخاب کنید", type_="password", required=True)}
          </div>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-2">اختیارات</label>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-2 p-4 bg-gray-50 rounded-lg">
            {perm_checks}
          </div>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">یادداشت (اختیاری)</label>
          {_input("notes", "توضیح نقش یا مسئولیت")}
        </div>
        {_btn("➕ افزودن ادمین", color="green")}
      </form>
    </div>

    <!-- Admins Table -->
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50">
        <span class="font-medium text-gray-700 text-sm">ادمین‌های فعلی ({len(admins)})</span>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b">
          <th class="px-4 py-3">نام</th><th class="px-4 py-3">تلگرام</th>
          <th class="px-4 py-3">یوزرنیم</th><th class="px-4 py-3">اختیارات</th>
          <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='6' class='text-center py-8 text-gray-400 text-sm'>هنوز ادمینی اضافه نشده</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("ادمین‌ها", body, adm, flash=flash)

@router.post("/admins/add")
async def admins_add(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard

    form = await request.form()
    name         = (form.get("name") or "").strip()
    web_username = (form.get("web_username") or "").strip()
    web_password = (form.get("web_password") or "").strip()
    telegram_id  = form.get("telegram_id") or None
    notes        = (form.get("notes") or "").strip()

    if not name or not web_username or not web_password:
        return _redir("/admin/admins?flash=فیلدهای+اجباری+را+پر+کنید")

    perms = [p.replace("perm_", "") for p in form.keys() if p.startswith("perm_")]

    try:
        tg_id = int(telegram_id) if telegram_id else None
    except ValueError:
        tg_id = None

    ensure_admins_table()
    conn = _db()
    try:
        conn.execute(
            """INSERT INTO admins (telegram_id, name, web_username, web_password_hash, permissions, notes, created_at)
               VALUES (?,?,?,?,?,?,?);""",
            (tg_id, name, web_username, _hash_pw(web_password), json.dumps(perms), notes, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return _redir("/admin/admins?flash=یوزرنیم+یا+تلگرام+تکراری+است")
    finally:
        try: conn.close()
        except: pass

    return _redir("/admin/admins?flash=ادمین+جدید+اضافه+شد")

@router.get("/admins/{aid}/edit", response_class=HTMLResponse)
async def admins_edit_get(request: Request, aid: int, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard

    ensure_admins_table()
    conn = _db()
    try:
        a = conn.execute("SELECT * FROM admins WHERE id=? LIMIT 1;", (aid,)).fetchone()
    finally:
        conn.close()

    if not a:
        return _redir("/admin/admins")

    cur_perms = json.loads(a["permissions"] or "[]")
    perm_checks = ""
    for perm_key, perm_label in ALL_PERMISSIONS.items():
        checked = "checked" if perm_key in cur_perms else ""
        perm_checks += f"""
        <label class="flex items-center gap-2 text-sm cursor-pointer">
          <input type="checkbox" name="perm_{perm_key}" {checked}
            class="rounded border-gray-300 text-indigo-600">
          {e(perm_label)}
        </label>"""

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/admins", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">✏️ ویرایش ادمین: {e(a["name"])}</h1>
    </div>
    <div class="bg-white rounded-xl shadow p-6 max-w-2xl">
      <form method="post" action="/admin/admins/{aid}/edit" class="space-y-4">
        <div class="grid md:grid-cols-2 gap-4">
          <div>
            <label class="text-xs text-gray-500 block mb-1">نام نمایشی</label>
            {_input("name", "", str(a["name"] or ""), required=True)}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">آیدی تلگرام</label>
            {_input("telegram_id", "", str(a["telegram_id"] or ""), type_="number")}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">یوزرنیم پنل</label>
            {_input("web_username", "", str(a["web_username"] or ""))}
          </div>
          <div>
            <label class="text-xs text-gray-500 block mb-1">رمز جدید (خالی = بدون تغییر)</label>
            {_input("web_password", "رمز جدید (اختیاری)", type_="password")}
          </div>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-2">اختیارات</label>
          <div class="grid grid-cols-2 md:grid-cols-3 gap-2 p-4 bg-gray-50 rounded-lg">
            {perm_checks}
          </div>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">یادداشت</label>
          {_input("notes", "", str(a["notes"] or ""))}
        </div>
        {_btn("ذخیره تغییرات", color="green")}
      </form>
    </div>"""

    return _layout(f"ویرایش ادمین #{aid}", body, adm, flash=flash)

@router.post("/admins/{aid}/edit")
async def admins_edit_post(request: Request, aid: int):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard

    form = await request.form()
    name         = (form.get("name") or "").strip()
    web_username = (form.get("web_username") or "").strip()
    web_password = (form.get("web_password") or "").strip()
    telegram_id  = form.get("telegram_id") or None
    notes        = (form.get("notes") or "").strip()
    perms        = [p.replace("perm_", "") for p in form.keys() if p.startswith("perm_")]

    try:
        tg_id = int(telegram_id) if telegram_id else None
    except ValueError:
        tg_id = None

    ensure_admins_table()
    conn = _db()
    try:
        if web_password:
            conn.execute(
                "UPDATE admins SET name=?,telegram_id=?,web_username=?,web_password_hash=?,permissions=?,notes=? WHERE id=?;",
                (name, tg_id, web_username, _hash_pw(web_password), json.dumps(perms), notes, aid),
            )
        else:
            conn.execute(
                "UPDATE admins SET name=?,telegram_id=?,web_username=?,permissions=?,notes=? WHERE id=?;",
                (name, tg_id, web_username, json.dumps(perms), notes, aid),
            )
        conn.commit()
    finally:
        conn.close()

    return _redir(f"/admin/admins/{aid}/edit?flash=ذخیره+شد")

@router.post("/admins/{aid}/toggle")
async def admins_toggle(request: Request, aid: int):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard
    ensure_admins_table()
    conn = _db()
    try:
        conn.execute("UPDATE admins SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (aid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/admins?flash=وضعیت+تغییر+کرد")

@router.post("/admins/{aid}/delete")
async def admins_delete(request: Request, aid: int):
    adm = _get_admin(request)
    guard = _require(adm, "admins")
    if guard: return guard
    ensure_admins_table()
    conn = _db()
    try:
        conn.execute("DELETE FROM admins WHERE id=?;", (aid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/admins?flash=ادمین+حذف+شد")

# ─────────────────────────── Products ──────────────────────────────────────

@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        products = conn.execute("""
            SELECT p.*, COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as feed_avail,
                   COUNT(pf.id) as feed_total
            FROM products p LEFT JOIN product_feed pf ON pf.product_id=p.id
            GROUP BY p.id ORDER BY p.category, p.id;
        """).fetchall()
    finally:
        conn.close()

    rows = ""
    for p in products:
        avail = int(p["feed_avail"] or 0)
        ac = "red" if avail==0 else ("yellow" if avail<5 else "green")
        status = '<span class="text-xs text-green-600">فعال</span>' if p["is_active"] else '<span class="text-xs text-red-500">غیرفعال</span>'
        rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 text-sm font-medium">{e(p["title"])}</td>
          <td class="px-4 py-3 text-xs text-gray-500">{e(p["category"])}</td>
          <td class="px-4 py-3 text-sm font-medium text-indigo-700">{int(p["price"]):,}</td>
          <td class="px-4 py-3">{status}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 text-xs rounded-full bg-{ac}-100 text-{ac}-700">{avail}/{int(p["feed_total"] or 0)}</span>
          </td>
          <td class="px-4 py-3 flex gap-2">
            {_btn("ویرایش", f"/admin/products/{p['id']}", "indigo", small=True)}
            {_btn("موجودی", f"/admin/feed/{p['id']}", "teal", small=True)}
          </td>
        </tr>"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">📦 محصولات</h1>
      {_btn("➕ محصول جدید", "/admin/products/new", "green")}
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">عنوان</th><th class="px-4 py-3">دسته</th>
          <th class="px-4 py-3">قیمت</th><th class="px-4 py-3">وضعیت</th>
          <th class="px-4 py-3">موجودی</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='6' class='text-center py-8 text-gray-400'>محصولی ثبت نشده</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("محصولات", body, adm, flash=flash)

@router.get("/products/new", response_class=HTMLResponse)
async def product_new_get(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        services = conn.execute("SELECT service_key, title FROM other_services ORDER BY title;").fetchall()
    finally:
        conn.close()

    cats = '<option value="apple">سرویس‌های اپل آیدی (apple)</option>'
    for s in services:
        cats += f'<option value="{e(s["service_key"])}">{e(s["title"])} ({e(s["service_key"])})</option>'

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/products", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">➕ محصول جدید</h1>
    </div>
    <form method="post" action="/admin/products/new" class="bg-white rounded-xl shadow p-6 max-w-2xl space-y-4">
      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">دسته‌بندی</label>
        <select name="category" required class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">
          {cats}
        </select>
      </div>
      <div><label class="text-sm font-medium text-gray-700 block mb-1">عنوان محصول</label>
        {_input("title", "عنوان محصول", required=True)}</div>
      <div class="grid grid-cols-2 gap-4">
        <div><label class="text-sm font-medium text-gray-700 block mb-1">قیمت (تومان)</label>
          {_input("price", "250000", type_="number", required=True)}</div>
        <div><label class="text-sm font-medium text-gray-700 block mb-1">قیمت همکار (0=یکسان)</label>
          {_input("partner_price", "0", type_="number")}</div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div><label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه مشتری</label>
          {_input("limit_c", "0", type_="number")}</div>
        <div><label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه همکار</label>
          {_input("limit_p", "0", type_="number")}</div>
      </div>
      <div><label class="text-sm font-medium text-gray-700 block mb-1">توضیحات</label>
        {_textarea("description", "توضیحات محصول...", rows=3)}</div>
      <div class="flex gap-3">{_btn("ذخیره محصول", color="green")} {_btn("انصراف", "/admin/products", "slate")}</div>
    </form>"""

    return _layout("محصول جدید", body, adm)

@router.post("/products/new")
async def product_new_post(request: Request,
    category: str=Form(""), title: str=Form(""), price: str=Form("0"),
    partner_price: str=Form("0"), limit_c: str=Form("0"), limit_p: str=Form("0"),
    description: str=Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    slug = "".join(c if c.isalnum() else "_" for c in title).lower()[:40] or "product"
    pp = int(partner_price or 0)
    conn = _db()
    try:
        conn.execute("""
            INSERT INTO products (category,product_key,title,price,partner_price,
                daily_limit_customer,daily_limit_partner,description,is_active)
            VALUES (?,?,?,?,?,?,?,?,1);""",
            (category, slug, title.strip(), int(price or 0), pp if pp>0 else None,
             int(limit_c or 0), int(limit_p or 0), description.strip()))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/products?flash=محصول+اضافه+شد")

@router.get("/products/{pid}", response_class=HTMLResponse)
async def product_edit_get(request: Request, pid: int, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        p = conn.execute("SELECT * FROM products WHERE id=?;", (pid,)).fetchone()
        services = conn.execute("SELECT service_key, title FROM other_services ORDER BY title;").fetchall()
        feed = conn.execute("SELECT COUNT(*) as t, COUNT(CASE WHEN delivered=0 THEN 1 END) as a FROM product_feed WHERE product_id=?;", (pid,)).fetchone()
    finally:
        conn.close()

    if not p:
        return _redir("/admin/products")

    cats = ""
    for s in [("apple","سرویس‌های اپل آیدی")] + [(r["service_key"],r["title"]) for r in services]:
        sel = "selected" if s[0]==p["category"] else ""
        cats += f'<option value="{e(s[0])}" {sel}>{e(s[1])}</option>'

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/products", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">✏️ ویرایش محصول #{pid}</h1>
    </div>
    <div class="grid md:grid-cols-3 gap-6">
      <div class="md:col-span-2">
        <form method="post" action="/admin/products/{pid}/edit" class="bg-white rounded-xl shadow p-6 space-y-4">
          <div><label class="text-sm font-medium text-gray-700 block mb-1">دسته</label>
            <select name="category" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">{cats}</select></div>
          <div><label class="text-sm font-medium text-gray-700 block mb-1">عنوان</label>
            {_input("title","",str(p["title"] or ""),required=True)}</div>
          <div class="grid grid-cols-2 gap-4">
            <div><label class="text-sm font-medium text-gray-700 block mb-1">قیمت</label>
              {_input("price","",str(p["price"] or 0),"number",True)}</div>
            <div><label class="text-sm font-medium text-gray-700 block mb-1">قیمت همکار</label>
              {_input("partner_price","",str(p["partner_price"] or 0),"number")}</div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div><label class="text-sm font-medium text-gray-700 block mb-1">سقف مشتری</label>
              {_input("limit_c","",str(p["daily_limit_customer"] or 0),"number")}</div>
            <div><label class="text-sm font-medium text-gray-700 block mb-1">سقف همکار</label>
              {_input("limit_p","",str(p["daily_limit_partner"] or 0),"number")}</div>
          </div>
          <div><label class="text-sm font-medium text-gray-700 block mb-1">توضیحات</label>
            {_textarea("description","",str(p["description"] or ""),rows=3)}</div>
          {_btn("ذخیره", color="green")}
        </form>
      </div>
      <div class="space-y-4">
        <div class="bg-white rounded-xl shadow p-5">
          <h3 class="font-bold text-gray-700 mb-2">📦 موجودی</h3>
          <div class="text-3xl font-bold text-indigo-700">{int(feed["a"] or 0)}</div>
          <div class="text-xs text-gray-400 mb-3">از {int(feed["t"] or 0)} کل</div>
          {_btn("مدیریت موجودی →", f"/admin/feed/{pid}", "teal")}
        </div>
        <div class="bg-white rounded-xl shadow p-5 space-y-2">
          <form method="post" action="/admin/products/{pid}/toggle">
            <button type="submit" class="w-full py-2 text-sm rounded-lg border-2 border-{"red" if p["is_active"] else "green"}-300 text-{"red" if p["is_active"] else "green"}-700 hover:bg-{"red" if p["is_active"] else "green"}-50">
              {"🔴 غیرفعال کردن" if p["is_active"] else "🟢 فعال کردن"}
            </button>
          </form>
          <form method="post" action="/admin/products/{pid}/delete" onsubmit="return confirm('حذف شود؟')">
            <button type="submit" class="w-full py-2 text-sm rounded-lg border-2 border-red-200 text-red-600 hover:bg-red-50">🗑 حذف</button>
          </form>
        </div>
      </div>
    </div>"""

    return _layout(f"محصول #{pid}", body, adm, flash=flash)

@router.post("/products/{pid}/edit")
async def product_edit_post(request: Request, pid: int,
    category: str=Form(""), title: str=Form(""), price: str=Form("0"),
    partner_price: str=Form("0"), limit_c: str=Form("0"), limit_p: str=Form("0"),
    description: str=Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard
    pp = int(partner_price or 0)
    conn = _db()
    try:
        conn.execute("""UPDATE products SET category=?,title=?,price=?,partner_price=?,
            daily_limit_customer=?,daily_limit_partner=?,description=? WHERE id=?;""",
            (category,title.strip(),int(price or 0),pp if pp>0 else None,
             int(limit_c or 0),int(limit_p or 0),description.strip(),pid))
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/products/{pid}?flash=ذخیره+شد")

@router.post("/products/{pid}/toggle")
async def product_toggle(request: Request, pid: int):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("UPDATE products SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (pid,))
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/products/{pid}?flash=وضعیت+تغییر+کرد")

@router.post("/products/{pid}/delete")
async def product_delete(request: Request, pid: int):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("DELETE FROM product_feed WHERE product_id=?;", (pid,))
        conn.execute("DELETE FROM products WHERE id=?;", (pid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/products?flash=حذف+شد")

# ─────────────────────────── Feed ──────────────────────────────────────────

@router.get("/feed", response_class=HTMLResponse)
async def feed_overview(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    conn = _db()
    try:
        products = conn.execute("""
            SELECT p.id, p.title, p.category,
                   COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as avail,
                   COUNT(pf.id) as total,
                   COALESCE(fas.threshold, 5) as threshold
            FROM products p
            LEFT JOIN product_feed pf ON pf.product_id=p.id
            LEFT JOIN feed_alert_settings fas ON fas.product_id=p.id
            GROUP BY p.id ORDER BY avail ASC, p.title;
        """).fetchall()
    finally:
        conn.close()

    rows = ""
    for p in products:
        avail = int(p["avail"] or 0)
        total = int(p["total"] or 0)
        pct = int(avail/max(total,1)*100)
        c = "red" if avail==0 else ("yellow" if avail<=int(p["threshold"]) else "green")
        rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 font-medium text-sm">{e(p["title"])}</td>
          <td class="px-4 py-3 text-xs text-gray-400">{e(p["category"])}</td>
          <td class="px-4 py-3">
            <div class="flex items-center gap-2">
              <div class="flex-1 bg-gray-100 rounded-full h-2">
                <div class="bg-{c}-500 h-2 rounded-full" style="width:{pct}%"></div>
              </div>
              <span class="text-sm font-medium text-{c}-700 w-16">{avail}/{total}</span>
            </div>
          </td>
          <td class="px-4 py-3">{_btn("مدیریت →", f"/admin/feed/{p['id']}", "indigo", small=True)}</td>
        </tr>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">🗃 مدیریت موجودی</h1>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">محصول</th><th class="px-4 py-3">دسته</th>
          <th class="px-4 py-3">موجودی</th><th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='4' class='text-center py-8 text-gray-400'>محصولی ثبت نشده</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("موجودی", body, adm)

@router.get("/feed/{pid}", response_class=HTMLResponse)
async def feed_detail(request: Request, pid: int, page: int=0, flash: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    PAGE = 20
    conn = _db()
    try:
        product = conn.execute("SELECT * FROM products WHERE id=?;", (pid,)).fetchone()
        if not product:
            return _redir("/admin/feed")
        total = conn.execute("SELECT COUNT(*) FROM product_feed WHERE product_id=?;", (pid,)).fetchone()[0]
        avail = conn.execute("SELECT COUNT(*) FROM product_feed WHERE product_id=? AND delivered=0;", (pid,)).fetchone()[0]
        items = conn.execute("""
            SELECT id, data, delivered, created_at FROM product_feed
            WHERE product_id=? ORDER BY id DESC LIMIT ? OFFSET ?;
        """, (pid, PAGE, page*PAGE)).fetchall()
    finally:
        conn.close()

    pages = max((total+PAGE-1)//PAGE, 1)
    items_html = ""
    for item in items:
        preview = str(item["data"] or "").splitlines()[0][:80] if item["data"] else "---"
        badge = '<span class="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">تحویل‌شده</span>' if item["delivered"] else '<span class="px-2 py-0.5 text-xs bg-blue-100 text-blue-700 rounded-full">موجود</span>'
        items_html += f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-2 text-gray-400 font-mono">#{item["id"]}</td>
          <td class="px-4 py-2 font-mono text-xs truncate max-w-xs">{e(preview)}</td>
          <td class="px-4 py-2">{badge}</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(item["created_at"] or "")[:10]}</td>
          <td class="px-4 py-2">
            <form method="post" action="/admin/feed/item/{item['id']}/delete" onsubmit="return confirm('حذف شود؟')">
              <button class="text-red-400 hover:text-red-600 text-xs">حذف</button>
            </form>
          </td>
        </tr>"""

    pager = '<div class="flex gap-2 mt-4 justify-center">' + "".join(
        f'<a href="/admin/feed/{pid}?page={i}" class="px-3 py-1 rounded border text-sm {"bg-indigo-600 text-white" if i==page else "bg-white text-gray-600"}">{i+1}</a>'
        for i in range(min(pages, 10))
    ) + "</div>" if pages > 1 else ""

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/feed", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">🗃 موجودی: {e(product["title"])}</h1>
    </div>
    <div class="grid grid-cols-3 gap-4 mb-6">
      {_card("کل آیتم‌ها", str(total), "", "slate")}
      {_card("موجود", str(avail), "", "green")}
      {_card("تحویل‌شده", str(total-avail), "", "indigo")}
    </div>
    <div class="bg-white rounded-xl shadow p-6 mb-6">
      <h2 class="font-bold text-gray-700 mb-3">➕ افزودن موجودی</h2>
      <form method="post" action="/admin/feed/{pid}/upload" class="space-y-3">
        <div class="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">هر خط = یک آیتم | برای چندخطی: <code class="bg-gray-200 px-1 rounded">***</code> بین آیتم‌ها</div>
        {_textarea("items", "آیتم‌ها را اینجا paste کنید...", rows=6)}
        {_btn("افزودن موجودی", color="green")}
      </form>
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50 flex justify-between items-center">
        <span class="text-sm font-medium">لیست آیتم‌ها ({total})</span>
        <form method="post" action="/admin/feed/{pid}/clear-delivered" onsubmit="return confirm('تحویل‌شده‌ها پاک شوند؟')">
          <button class="text-xs text-red-400 hover:text-red-600">🗑 پاک‌سازی تحویل‌شده‌ها</button>
        </form>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b">
          <th class="px-4 py-2">ID</th><th class="px-4 py-2">پیش‌نمایش</th>
          <th class="px-4 py-2">وضعیت</th><th class="px-4 py-2">تاریخ</th><th></th>
        </tr></thead>
        <tbody>{items_html or "<tr><td colspan='5' class='text-center py-8 text-gray-400'>آیتمی ثبت نشده</td></tr>"}</tbody>
      </table>
      {pager}
    </div>"""

    return _layout(f"موجودی #{pid}", body, adm, flash=flash)

@router.post("/feed/{pid}/upload")
async def feed_upload(request: Request, pid: int, items: str=Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    import re as _re
    raw = items.strip()
    if _re.search(r"^\s*\*{3,}\s*$", raw, _re.MULTILINE):
        blocks = [b.strip() for b in _re.split(r"^\s*\*{3,}\s*$", raw, flags=_re.MULTILINE) if b.strip()]
    else:
        blocks = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    if not blocks:
        return _redir(f"/admin/feed/{pid}?flash=آیتمی+یافت+نشد")

    now = datetime.utcnow().isoformat()
    conn = _db()
    try:
        conn.executemany("INSERT INTO product_feed (product_id,data,delivered,created_at) VALUES (?,?,0,?);",
                         [(pid, b, now) for b in blocks])
        conn.execute("INSERT INTO feed_alert_settings (product_id,threshold,last_notified_remaining,updated_at) VALUES (?,5,NULL,?) "
                     "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=NULL, updated_at=excluded.updated_at;", (pid, now))
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/feed/{pid}?flash={len(blocks)}+آیتم+اضافه+شد")

@router.post("/feed/{pid}/clear-delivered")
async def feed_clear(request: Request, pid: int):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard
    conn = _db()
    try:
        r = conn.execute("DELETE FROM product_feed WHERE product_id=? AND delivered=1;", (pid,))
        conn.commit()
        n = r.rowcount
    finally:
        conn.close()
    return _redir(f"/admin/feed/{pid}?flash={n}+آیتم+حذف+شد")

@router.post("/feed/item/{fid}/delete")
async def feed_item_delete(request: Request, fid: int):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard
    conn = _db()
    try:
        row = conn.execute("SELECT product_id FROM product_feed WHERE id=?;", (fid,)).fetchone()
        pid = row["product_id"] if row else 0
        conn.execute("DELETE FROM product_feed WHERE id=?;", (fid,))
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/feed/{pid}?flash=آیتم+حذف+شد")

# ─────────────────────────── Orders ────────────────────────────────────────

@router.get("/orders", response_class=HTMLResponse)
async def orders_list(request: Request, page: int=0, q: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "orders")
    if guard: return guard

    PAGE = 30
    conn = _db()
    try:
        where = "WHERE user_id LIKE ?" if q else ""
        params_q = (f"%{q}%",) if q else ()
        total = conn.execute(f"SELECT COUNT(*) FROM orders {where};", params_q).fetchone()[0]
        orders = conn.execute(f"SELECT * FROM orders {where} ORDER BY id DESC LIMIT ? OFFSET ?;",
                              params_q+(PAGE, page*PAGE)).fetchall()
    finally:
        conn.close()

    pages = max((total+PAGE-1)//PAGE, 1)
    rows = "".join(f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-2 text-gray-400">#{o["id"]}</td>
          <td class="px-4 py-2 font-mono text-xs"><code>{e(o["user_id"])}</code></td>
          <td class="px-4 py-2">{e(o["title"])}</td>
          <td class="px-4 py-2 text-green-700 font-medium">{int(o["price"]):,} ت</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(o["created_at"] or "")[:16]}</td>
        </tr>""" for o in orders)

    pager = '<div class="flex gap-2 mt-4 justify-center">' + "".join(
        f'<a href="/admin/orders?page={i}" class="px-3 py-1 rounded border text-sm {"bg-indigo-600 text-white" if i==page else "bg-white"}">{i+1}</a>'
        for i in range(min(pages, 10))
    ) + "</div>" if pages > 1 else ""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">🧾 سفارش‌ها ({total:,})</h1>
      <form method="get" class="flex gap-2">
        {_input("q","جستجو User ID...",q)} {_btn("جستجو","","slate",True)}
      </form>
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">#</th><th class="px-4 py-3">User ID</th>
          <th class="px-4 py-3">محصول</th><th class="px-4 py-3">مبلغ</th><th class="px-4 py-3">تاریخ</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='5' class='text-center py-8 text-gray-400'>سفارشی ثبت نشده</td></tr>"}</tbody>
      </table>{pager}
    </div>"""

    return _layout("سفارش‌ها", body, adm)

# ─────────────────────────── Wallets ───────────────────────────────────────

@router.get("/wallets", response_class=HTMLResponse)
async def wallets_list(request: Request, q: str="", flash: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "wallets")
    if guard: return guard

    conn = _db()
    try:
        where = "WHERE user_id=?" if (q and q.isdigit()) else ""
        params = (int(q),) if (q and q.isdigit()) else ()
        wallets = conn.execute(f"SELECT * FROM wallets {where} ORDER BY balance DESC LIMIT 50;", params).fetchall()
        totals  = conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM wallets;").fetchone()
    finally:
        conn.close()

    rows = "".join(f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-2 font-mono text-xs"><code>{w["user_id"]}</code></td>
          <td class="px-4 py-2 font-bold text-{"green" if int(w["balance"])>0 else "gray"}-700">{int(w["balance"]):,} ت</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(w["updated_at"] or "")[:16]}</td>
        </tr>""" for w in wallets)

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">💰 کیف‌پول ({int(totals[0])} کاربر | {int(totals[1]):,} ت)</h1>
    </div>
    <div class="bg-white rounded-xl shadow p-5 mb-6">
      <h2 class="font-bold text-gray-700 mb-3">تنظیم موجودی</h2>
      <form method="post" action="/admin/wallets/adjust" class="flex gap-3 flex-wrap items-end">
        <div><label class="text-xs text-gray-500 block mb-1">User ID</label>{_input("uid","",type_="number",required=True)}</div>
        <div><label class="text-xs text-gray-500 block mb-1">مبلغ</label>{_input("amount","",type_="number",required=True)}</div>
        <div><label class="text-xs text-gray-500 block mb-1">عملیات</label>
          <select name="op" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="add">➕ افزودن</option>
            <option value="sub">➖ کاهش</option>
            <option value="set">✏️ تنظیم مستقیم</option>
          </select></div>
        {_btn("اعمال")}
      </form>
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50 flex gap-2">
        <form method="get" class="flex gap-2">
          {_input("q","جستجو User ID...",q)} {_btn("جستجو","","slate",True)}
        </form>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b">
          <th class="px-4 py-2">User ID</th><th class="px-4 py-2">موجودی</th><th class="px-4 py-2">آپدیت</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='3' class='text-center py-8 text-gray-400'>کاربری یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("کیف‌پول‌ها", body, adm, flash=flash)

@router.post("/wallets/adjust")
async def wallet_adjust(request: Request, uid: str=Form(""), amount: str=Form("0"), op: str=Form("add")):
    adm = _get_admin(request)
    guard = _require(adm, "wallets")
    if guard: return guard
    try:
        user_id = int(uid); amt = int(amount)
    except ValueError:
        return _redir("/admin/wallets?flash=مقادیر+نامعتبر")
    now = datetime.utcnow().isoformat()
    conn = _db()
    try:
        row = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
        cur = int(row["balance"] if row else 0)
        new_bal = cur+amt if op=="add" else max(0,cur-amt) if op=="sub" else amt
        conn.execute("INSERT INTO wallets (user_id,balance,updated_at) VALUES (?,?,?) "
                     "ON CONFLICT(user_id) DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at;",
                     (user_id, new_bal, now))
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/wallets?flash=موجودی+{user_id}+به+{new_bal:,}+تومان+تنظیم+شد")

# ─────────────────────────── Partners ──────────────────────────────────────

@router.get("/partners", response_class=HTMLResponse)
async def partners_list(request: Request, status_filter: str="", flash: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "partners")
    if guard: return guard

    conn = _db()
    try:
        where = "WHERE status=?" if status_filter else ""
        partners = conn.execute(f"SELECT * FROM partners {where} ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, id DESC LIMIT 100;",
                                (status_filter,) if status_filter else ()).fetchall()
    finally:
        conn.close()

    tabs = '<div class="flex gap-2 mb-4">' + "".join(
        f'<a href="/admin/partners?status_filter={v}" class="px-4 py-2 rounded-lg border text-sm {"bg-indigo-600 text-white" if status_filter==v else "bg-white text-gray-600"}">{l}</a>'
        for l, v in [("همه",""),("در انتظار","pending"),("تایید شده","approved"),("رد شده","rejected")]
    ) + "</div>"

    rows = ""
    for p in partners:
        st = p["status"] or "pending"
        bc = {"pending":"yellow","approved":"green","rejected":"red"}.get(st,"gray")
        bl = {"pending":"در انتظار","approved":"تایید","rejected":"رد شده"}.get(st,st)
        rows += f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-3 font-mono text-xs"><code>{e(p["tg_user_id"])}</code></td>
          <td class="px-4 py-3">{e(p["full_name"])}</td>
          <td class="px-4 py-3 text-gray-500">{e(p["phone"])}</td>
          <td class="px-4 py-3 text-gray-400 text-xs">{e(p["city"])} | {e(p["shop_name"])}</td>
          <td class="px-4 py-3"><span class="px-2 py-0.5 text-xs rounded-full bg-{bc}-100 text-{bc}-700">{bl}</span></td>
          <td class="px-4 py-3 flex gap-1">
            {f'''<form method="post" action="/admin/partners/{p["tg_user_id"]}/approve">
              <button class="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200">✅</button>
            </form>
            <form method="post" action="/admin/partners/{p["tg_user_id"]}/reject">
              <button class="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200">❌</button>
            </form>''' if st=="pending" else ""}
          </td>
        </tr>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-4">🤝 همکاران</h1>
    {tabs}
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">User ID</th><th class="px-4 py-3">نام</th>
          <th class="px-4 py-3">شماره</th><th class="px-4 py-3">شهر|فروشگاه</th>
          <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='6' class='text-center py-8 text-gray-400'>درخواستی یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("همکاران", body, adm, flash=flash)

@router.post("/partners/{uid}/approve")
async def partner_approve(request: Request, uid: int):
    adm = _get_admin(request)
    guard = _require(adm, "partners")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("UPDATE partners SET status='approved', approved_at=? WHERE tg_user_id=?;", (datetime.utcnow().isoformat(), uid))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/partners?flash=همکار+تایید+شد")

@router.post("/partners/{uid}/reject")
async def partner_reject(request: Request, uid: int):
    adm = _get_admin(request)
    guard = _require(adm, "partners")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("UPDATE partners SET status='rejected' WHERE tg_user_id=?;", (uid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/partners?flash=درخواست+رد+شد")
