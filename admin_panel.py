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
import threading
import time
from datetime import datetime

import requests as _requests
from fastapi import APIRouter, BackgroundTasks, Form, Request, UploadFile
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

def _open_ticket_count() -> int:
    """تعداد تیکت‌هایی که منتظر پاسخ ادمین هستند."""
    try:
        conn = _db()
        n = conn.execute(
            "SELECT COUNT(*) FROM tickets WHERE status='waiting_admin';"
        ).fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


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

    perms = admin_info[2] if admin_info else []
    is_super = admin_info[1] if admin_info else False

    # نوتیف تیکت‌های باز
    open_tickets = _open_ticket_count() if admin_info else 0
    ticket_badge = (
        f'<span class="bg-red-500 text-white text-xs rounded-full px-1.5 py-0.5 mr-0.5 font-bold">{open_tickets}</span>'
        if open_tickets > 0 else ""
    )

    def nav_link(href, label, perm=None, badge=""):
        if perm and not is_super and perm not in perms:
            return ""
        return f'<a href="{href}" class="text-indigo-200 hover:text-white text-sm transition flex items-center gap-1">{badge}{label}</a>'

    nav = f"""
    <nav class="bg-indigo-900 text-white shadow-xl sticky top-0 z-50">
      <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-4 flex-wrap text-sm">
        <a href="/admin/" class="font-bold text-lg text-white">🛍 استوک لند</a>
        {nav_link("/admin/", "📊 داشبورد")}
        {nav_link("/admin/categories", "🗂 دسته‌بندی‌ها", "products")}
        {nav_link("/admin/products", "📦 محصولات", "products")}
        {nav_link("/admin/feed", "🗃 موجودی", "feed")}
        {nav_link("/admin/orders", "🧾 سفارش‌ها", "orders")}
        {nav_link("/admin/wallets", "💰 کیف‌پول", "wallets")}
        {nav_link("/admin/partners", "🤝 همکاران", "partners")}
        {nav_link("/admin/tickets", "🎫 تیکت‌ها", "orders", badge=ticket_badge)}
        {nav_link("/admin/broadcast", "📢 پیام‌رسانی", "broadcast")}
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    * {{ font-family: 'Vazirmatn', Tahoma, sans-serif !important; }}
    body {{ background: #f1f5f9; }}
    .card {{ background: white; border-radius: 12px; box-shadow: 0 1px 3px rgba(0,0,0,.08); }}
    .btn-primary {{ background: #4f46e5; color: white; padding: 8px 16px; border-radius: 8px; font-size: 14px; font-weight: 500; border: none; cursor: pointer; transition: .15s; }}
    .btn-primary:hover {{ background: #4338ca; }}
    .btn-sm {{ padding: 4px 10px; font-size: 12px; border-radius: 6px; font-weight: 500; cursor: pointer; border: none; }}
    input, textarea, select {{ font-family: 'Vazirmatn', Tahoma, sans-serif !important; }}
  </style>
</head>
<body class="min-h-screen">
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
async def settings_get(request: Request, group: str = "", flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    try:
        from ui_texts import (DEFAULT_UI_TEXTS as _DEFAULTS, TEXT_GROUPS as _GROUPS,
                              TEXT_DESCRIPTIONS as _DESCS, MAIN_BUTTON_KEYS as _BTN_KEYS)
    except ImportError:
        _DEFAULTS = {}; _GROUPS = {}; _DESCS = {}; _BTN_KEYS = []

    conn = _db()
    try:
        db_texts = {r["key"]: r["value"] for r in conn.execute("SELECT key, value FROM ui_texts;").fetchall()}
        btn_states = {k: db_texts.get(f"MAIN_BTN_ENABLED_{k}", "1") not in ("0","false","off","no") for k in _BTN_KEYS}
    finally:
        conn.close()

    def get_val(k): return db_texts.get(k, _DEFAULTS.get(k, ""))

    # انتخاب گروه فعال
    group_names = list(_GROUPS.keys()) + ["🔘 دکمه‌های منو"]
    active_group = group or (group_names[0] if group_names else "")

    # ─── Sidebar ناوبری گروه‌ها ──────────────────────────────────────────
    group_icons = {
        "دکمه‌های منو": "🔘",
        "پیام‌های اصلی": "💬",
        "کیف پول": "💰",
        "جریان خرید": "🛒",
        "سفارش‌ها": "🧾",
        "پشتیبانی و راهنما": "📖",
        "همکاران": "🤝",
        "🔘 دکمه‌های منو": "🔘",
    }
    sidebar = ""
    for gname in group_names:
        icon = group_icons.get(gname, "📝")
        is_active = gname == active_group
        bg = "bg-indigo-50 text-indigo-700 font-semibold border-r-2 border-indigo-600" if is_active else "text-gray-600 hover:bg-gray-50"
        sidebar += f'<a href="/admin/settings?group={e(gname)}" class="flex items-center gap-2 px-4 py-2.5 text-sm rounded-lg transition {bg}">{icon} {e(gname)}</a>'

    # ─── محتوای گروه فعال ────────────────────────────────────────────────
    content = ""

    if active_group == "🔘 دکمه‌های منو":
        # فعال/غیرفعال کردن دکمه‌های سیستمی
        btn_label_map = {
            "MAIN_BTN_MY_ORDERS": "خریدهای من 🧾",
            "MAIN_BTN_WALLET": "کیف پول 💰",
            "MAIN_BTN_PARTNER_REQUEST": "درخواست نمایندگی 📝",
            "MAIN_BTN_PARTNER_PANEL": "پنل همکار 🤝",
            "MAIN_BTN_GUIDE": "راهنما 🔑",
            "MAIN_BTN_SUPPORT": "پشتیبانی 👨‍💻",
        }
        rows = ""
        for k in _BTN_KEYS:
            en = btn_states.get(k, True)
            badge = '<span class="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">فعال</span>' if en else '<span class="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">غیرفعال</span>'
            rows += f"""<tr class="border-b hover:bg-gray-50">
              <td class="px-4 py-3 text-sm font-medium">{e(btn_label_map.get(k,k))}</td>
              <td class="px-4 py-3">{badge}</td>
              <td class="px-4 py-3 text-xs text-gray-400">منوی اصلی ربات</td>
              <td class="px-4 py-3"><form method="post" action="/admin/settings/toggle-btn">
                <input type="hidden" name="key" value="{e(k)}">
                <button class="btn-sm border rounded hover:bg-gray-50">{"غیرفعال کن" if en else "فعال کن"}</button>
              </form></td>
            </tr>"""
        content = f"""<div class="overflow-x-auto"><table class="w-full text-right">
          <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
            <th class="px-4 py-3">دکمه</th><th class="px-4 py-3">وضعیت</th>
            <th class="px-4 py-3">محل نمایش</th><th class="px-4 py-3">عملیات</th>
          </tr></thead><tbody>{rows}</tbody></table></div>"""

    else:
        # متن‌های گروه انتخاب‌شده
        keys = _GROUPS.get(active_group, [])
        fields_html = ""
        for key in keys:
            val = get_val(key)
            default = _DEFAULTS.get(key, "")
            desc = _DESCS.get(key, "")
            is_long = len(default) > 80 or "\n" in default
            is_modified = key in db_texts

            modified_badge = '<span class="text-xs text-blue-600 bg-blue-50 px-1.5 py-0.5 rounded mr-1">ویرایش‌شده</span>' if is_modified else ''
            desc_html = f'<span class="text-gray-400 font-normal">← {e(desc)}</span>' if desc else ""

            if is_long:
                field_input = f'<textarea id="f_{e(key)}" name="value" rows="3" class="w-full border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300 font-mono bg-white">{e(val)}</textarea>'
            else:
                field_input = f'<input type="text" id="f_{e(key)}" name="value" value="{e(val)}" class="flex-1 border border-gray-200 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300 bg-white">'

            fields_html += f"""
            <div class="p-4 border border-gray-100 rounded-xl bg-gray-50 hover:bg-white transition mb-3">
              <div class="flex items-start justify-between mb-2">
                <div>
                  <code class="text-xs text-indigo-600 bg-indigo-50 px-2 py-0.5 rounded">{e(key)}</code>
                  {modified_badge}
                  <div class="text-xs text-gray-400 mt-1">{desc_html}</div>
                </div>
                <form method="post" action="/admin/settings/reset-field" class="mr-2">
                  <input type="hidden" name="key" value="{e(key)}">
                  <input type="hidden" name="group" value="{e(active_group)}">
                  <button title="بازگشت به پیش‌فرض"
                    class="text-xs text-gray-400 hover:text-red-500 transition px-2 py-1 rounded hover:bg-red-50">
                    🔄 پیش‌فرض
                  </button>
                </form>
              </div>
              <form method="post" action="/admin/settings/save-field" class="{"space-y-1" if is_long else "flex gap-2 items-end"}">
                <input type="hidden" name="key" value="{e(key)}">
                <input type="hidden" name="group" value="{e(active_group)}">
                {field_input}
                <button class="btn-sm bg-indigo-600 text-white rounded-lg px-3 py-2 hover:bg-indigo-700 whitespace-nowrap {"mt-2" if is_long else ""}">
                  💾 ذخیره
                </button>
              </form>
              {"" if not default else f'<div class="mt-2 text-xs text-gray-300">پیش‌فرض: {e(default[:120])}{"..." if len(default)>120 else ""}</div>'}
            </div>"""

        # دکمه ذخیره همه گروه
        content = f"""
        <form method="post" action="/admin/settings/save-group">
          <input type="hidden" name="group" value="{e(active_group)}">
          <div class="flex items-center justify-between mb-4">
            <span class="text-sm text-gray-500">{len(keys)} فیلد</span>
            <button class="px-4 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg text-sm font-medium">
              💾 ذخیره همه این بخش
            </button>
          </div>
        </form>
        {fields_html}"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">⚙️ مدیریت متن‌ها و تنظیمات</h1>
    </div>

    <!-- موبایل: نوار بالا | دسکتاپ: sidebar -->
    <div class="mb-4 lg:hidden overflow-x-auto">
      <div class="flex gap-2 pb-2 min-w-max">
        {" ".join(f'<a href="/admin/settings?group={e(g)}" class="px-3 py-2 rounded-lg border text-sm whitespace-nowrap {"bg-indigo-600 text-white" if g == active_group else "bg-white text-gray-600"}">{group_icons.get(g,"📝")} {e(g)}</a>' for g in group_names)}
      </div>
    </div>

    <div class="flex gap-6">
      <!-- Sidebar فقط دسکتاپ -->
      <div class="hidden lg:block w-52 shrink-0">
        <div class="card p-2 space-y-0.5 sticky top-20">
          {sidebar}
        </div>
      </div>
      <!-- Content -->
      <div class="flex-1 min-w-0">
        <div class="card p-4 md:p-6">
          <h2 class="font-bold text-gray-700 text-lg mb-4">{e(active_group)}</h2>
          {content}
        </div>
      </div>
    </div>"""

    return _layout("تنظیمات", body, adm, flash=flash)


@router.post("/settings/save-field")
async def settings_save_field(request: Request, key: str = Form(""), value: str = Form(""),
                               group: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    if key:
        conn = _db()
        try:
            now = datetime.now().isoformat()
            conn.execute("INSERT INTO ui_texts(key,value,updated_at) VALUES(?,?,?) "
                        "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at;",
                        (key, value.strip(), now))
            conn.commit()
        finally:
            conn.close()
        try:
            from ui_texts import ui_cache_clear; ui_cache_clear()
        except Exception: pass

    return _redir(f"/admin/settings?group={e(group)}&flash=ذخیره+شد")


@router.post("/settings/save-group")
async def settings_save_group(request: Request, group: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    try:
        from ui_texts import TEXT_GROUPS as _GROUPS
    except ImportError:
        _GROUPS = {}

    form = await request.form()
    keys = _GROUPS.get(group, [])
    conn = _db()
    try:
        now = datetime.now().isoformat()
        for key in keys:
            val = (form.get(key) or "").strip()
            if val:
                conn.execute("INSERT INTO ui_texts(key,value,updated_at) VALUES(?,?,?) "
                            "ON CONFLICT(key) DO UPDATE SET value=excluded.value,updated_at=excluded.updated_at;",
                            (key, val, now))
        conn.commit()
    finally:
        conn.close()
    try:
        from ui_texts import ui_cache_clear; ui_cache_clear()
    except Exception: pass
    return _redir(f"/admin/settings?group={e(group)}&flash=همه+فیلدهای+این+بخش+ذخیره+شدند")


@router.post("/settings/reset-field")
async def settings_reset_field(request: Request, key: str = Form(""), group: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard

    if key:
        conn = _db()
        try:
            conn.execute("DELETE FROM ui_texts WHERE key=?;", (key,))
            conn.commit()
        finally:
            conn.close()
        try:
            from ui_texts import ui_cache_clear; ui_cache_clear()
        except Exception: pass

    return _redir(f"/admin/settings?group={e(group)}&flash={e(key)}+به+پیش‌فرض+بازگشت")


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
        tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name;").fetchall()
        table_info = []
        for t in tables:
            count = conn.execute(f"SELECT COUNT(*) FROM {t['name']};").fetchone()[0]
            table_info.append((t["name"], count))

        counts = {name: cnt for name, cnt in table_info}
    finally:
        conn.close()

    table_rows = "".join(f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-2 text-sm font-mono">{e(name)}</td>
          <td class="px-4 py-2 text-sm text-gray-500">{count:,} ردیف</td>
        </tr>""" for name, count in table_info)

    def section_card(icon, title, desc, count_key, export_url, import_url=None,
                     import_note=None, color="indigo"):
        cnt = counts.get(count_key, 0)
        import_html = ""
        if import_url:
            import_html = f"""
            <form method="post" action="{import_url}" enctype="multipart/form-data" class="mt-3 pt-3 border-t">
              <p class="text-xs text-gray-400 mb-2">{import_note or "فایل JSON آپلود کنید"}</p>
              <input type="file" name="file" accept=".json,.csv" required
                class="w-full text-xs mb-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-{color}-50 file:text-{color}-700">
              <button type="submit" onclick="return confirm('داده‌های موجود با این فایل ادغام/جایگزین می‌شوند. ادامه دهید؟')"
                class="w-full py-1.5 bg-{color}-100 text-{color}-700 rounded text-xs font-medium hover:bg-{color}-200">
                📥 بازیابی
              </button>
            </form>"""
        return f"""
        <div class="card p-5">
          <div class="flex items-center gap-2 mb-1">
            <span class="text-xl">{icon}</span>
            <h3 class="font-bold text-gray-700">{title}</h3>
          </div>
          <p class="text-xs text-gray-400 mb-3">{desc}<br>
            <span class="text-{color}-600 font-medium">{cnt:,} ردیف</span>
          </p>
          <div class="space-y-1">
            <a href="{export_url}?fmt=json"
               class="flex items-center justify-between px-3 py-2 bg-{color}-50 hover:bg-{color}-100 text-{color}-700 rounded text-xs font-medium transition">
              <span>📤 دانلود JSON</span> <span>←</span>
            </a>
            <a href="{export_url}?fmt=csv"
               class="flex items-center justify-between px-3 py-2 bg-gray-50 hover:bg-gray-100 text-gray-700 rounded text-xs font-medium transition">
              <span>📊 دانلود CSV</span> <span>←</span>
            </a>
          </div>
          {import_html}
        </div>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">💾 مدیریت دیتابیس</h1>

    <!-- بکاپ کامل / بازیابی / ریست -->
    <div class="grid md:grid-cols-3 gap-4 mb-8">
      <div class="card p-5">
        <h2 class="font-bold text-gray-700 mb-1">🗄 بکاپ کامل</h2>
        <p class="text-xs text-gray-400 mb-3">حجم: <strong>{size_str}</strong> — همه جداول</p>
        <a href="/admin/database/backup"
           class="block w-full text-center py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-sm font-medium transition">
          📤 دانلود SQLite
        </a>
      </div>

      <div class="card p-5">
        <h2 class="font-bold text-gray-700 mb-1">📥 بازیابی کامل</h2>
        <p class="text-xs text-gray-400 mb-3">فایل SQLite — کل دیتابیس جایگزین می‌شود</p>
        <form method="post" action="/admin/database/restore" enctype="multipart/form-data">
          <input type="file" name="backup_file" accept=".sqlite,.db" required
            class="w-full text-xs mb-2 file:py-1 file:px-2 file:rounded file:border-0 file:text-xs file:bg-orange-50 file:text-orange-700">
          <button type="submit" onclick="return confirm('دیتابیس کاملاً جایگزین می‌شود!')"
            class="w-full py-2 bg-orange-500 hover:bg-orange-600 text-white rounded-lg text-sm font-medium">
            بازیابی
          </button>
        </form>
      </div>

      <div class="card p-5 border-2 border-red-100">
        <h2 class="font-bold text-red-700 mb-1">⚠️ ریست کامل</h2>
        <p class="text-xs text-gray-400 mb-3">همه داده‌ها پاک — غیرقابل بازگشت!</p>
        <form method="post" action="/admin/database/reset"
          onsubmit="return confirm('آخرین تأیید: همه داده‌ها حذف می‌شوند!')">
          <input type="text" name="confirm_text" placeholder='بنویسید: RESET' required
            class="w-full border border-red-300 rounded px-3 py-2 text-xs mb-2">
          <button type="submit"
            class="w-full py-2 bg-red-600 hover:bg-red-700 text-white rounded-lg text-sm font-medium">
            ریست
          </button>
        </form>
      </div>
    </div>

    <!-- بکاپ بخش‌بندی‌شده -->
    <h2 class="text-lg font-bold text-gray-700 mb-4">📦 بکاپ بخش‌بندی‌شده</h2>
    <div class="grid md:grid-cols-2 lg:grid-cols-3 gap-4 mb-8">

      {section_card("👥", "کاربران", "همه کاربران ربات",
        "users", "/admin/database/export/users", "/admin/database/import/users",
        "JSON کاربران — ادغام با موجودین", "blue")}

      {section_card("📦", "محصولات", "محصولات + دسته‌بندی‌ها",
        "products", "/admin/database/export/products", "/admin/database/import/products",
        "JSON محصولات — جایگزین می‌شوند", "teal")}

      {section_card("🗂", "دسته‌بندی‌ها", "ساختار درختی دسته‌ها",
        "categories", "/admin/database/export/categories", "/admin/database/import/categories",
        "JSON دسته‌بندی‌ها", "purple")}

      {section_card("🧾", "سفارش‌ها", "تاریخچه خریدها",
        "orders", "/admin/database/export/orders", color="green")}

      {section_card("💰", "کیف‌پول‌ها", "موجودی همه کاربران",
        "wallets", "/admin/database/export/wallets", "/admin/database/import/wallets",
        "JSON کیف‌پول — موجودی‌ها آپدیت می‌شوند", "yellow")}

      {section_card("⚙️", "تنظیمات", "همه متن‌های ربات + تنظیمات",
        "ui_texts", "/admin/database/export/settings", "/admin/database/import/settings",
        "JSON تنظیمات — جایگزین می‌شوند", "indigo")}

    </div>

    <!-- اطلاعات جداول -->
    <div class="card p-6">
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


# ─────────────────────────── Section Export ────────────────────────────────

import csv
import io

_SECTION_MAP = {
    "users":      ("users",      ["user_id", "username", "full_name", "first_seen", "last_seen"]),
    "products":   ("products",   ["id", "category", "category_id", "product_key", "title", "price",
                                  "partner_price", "daily_limit_customer", "daily_limit_partner",
                                  "description", "is_active"]),
    "categories": ("categories", ["id", "name", "slug", "parent_id", "emoji", "sort_order", "is_active"]),
    "orders":     ("orders",     ["id", "user_id", "category", "product_id", "title", "price",
                                  "created_at", "buyer_type"]),
    "wallets":    ("wallets",    ["user_id", "balance", "updated_at"]),
    "settings":   ("ui_texts",   ["key", "value", "updated_at"]),
}


@router.get("/database/export/{section}")
async def section_export(request: Request, section: str, fmt: str = "json"):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if section not in _SECTION_MAP:
        return _redir("/admin/database?flash=بخش+نامعتبر")

    table, cols = _SECTION_MAP[section]
    conn = _db()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(f"SELECT * FROM {table};").fetchall()
        data = [dict(r) for r in rows]
    finally:
        conn.close()

    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if fmt == "csv":
        output = io.StringIO()
        if data:
            writer = csv.DictWriter(output, fieldnames=data[0].keys())
            writer.writeheader()
            writer.writerows(data)
        content = output.getvalue().encode("utf-8-sig")
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type="text/csv; charset=utf-8-sig",
            headers={"Content-Disposition": f'attachment; filename="stockland_{section}_{ts}.csv"'}
        )
    else:
        from fastapi.responses import Response
        content = json.dumps(data, ensure_ascii=False, indent=2, default=str).encode("utf-8")
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="stockland_{section}_{ts}.json"'}
        )


# ─────────────────────────── Section Import ────────────────────────────────

@router.post("/database/import/users")
async def import_users(request: Request, file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    content = await file.read()
    try:
        data = json.loads(content)
    except Exception:
        return _redir("/admin/database?flash=فرمت+فایل+نامعتبر")

    conn = _db()
    try:
        inserted = 0
        for row in data:
            try:
                conn.execute(
                    "INSERT INTO users (user_id, username, full_name, first_seen, last_seen) "
                    "VALUES (?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET "
                    "username=excluded.username, full_name=excluded.full_name, last_seen=excluded.last_seen;",
                    (row.get("user_id"), row.get("username"), row.get("full_name"),
                     row.get("first_seen"), row.get("last_seen"))
                )
                inserted += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/database?flash={inserted}+کاربر+بازیابی+شد")


@router.post("/database/import/products")
async def import_products(request: Request, file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    content = await file.read()
    try:
        data = json.loads(content)
    except Exception:
        return _redir("/admin/database?flash=فرمت+فایل+نامعتبر")

    conn = _db()
    try:
        inserted = 0
        for row in data:
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO products
                       (id, category, category_id, product_key, title, price, partner_price,
                        daily_limit_customer, daily_limit_partner, description, is_active)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?);""",
                    (row.get("id"), row.get("category"), row.get("category_id"),
                     row.get("product_key"), row.get("title"), row.get("price"),
                     row.get("partner_price"), row.get("daily_limit_customer"),
                     row.get("daily_limit_partner"), row.get("description"),
                     row.get("is_active", 1))
                )
                inserted += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/database?flash={inserted}+محصول+بازیابی+شد")


@router.post("/database/import/categories")
async def import_categories(request: Request, file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    content = await file.read()
    try:
        data = json.loads(content)
    except Exception:
        return _redir("/admin/database?flash=فرمت+فایل+نامعتبر")

    conn = _db()
    try:
        inserted = 0
        # اول ریشه‌ها، بعد فرزندان
        for parent_pass in [True, False]:
            for row in data:
                is_root = row.get("parent_id") is None
                if is_root != parent_pass:
                    continue
                try:
                    conn.execute(
                        """INSERT OR REPLACE INTO categories
                           (id, name, slug, parent_id, emoji, sort_order, is_active)
                           VALUES (?,?,?,?,?,?,?);""",
                        (row.get("id"), row.get("name"), row.get("slug"),
                         row.get("parent_id"), row.get("emoji", ""),
                         row.get("sort_order", 0), row.get("is_active", 1))
                    )
                    inserted += 1
                except Exception:
                    pass
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/database?flash={inserted}+دسته+بازیابی+شد")


@router.post("/database/import/wallets")
async def import_wallets(request: Request, file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    content = await file.read()
    try:
        data = json.loads(content)
    except Exception:
        return _redir("/admin/database?flash=فرمت+فایل+نامعتبر")

    conn = _db()
    try:
        updated = 0
        now = datetime.now().isoformat()
        for row in data:
            try:
                conn.execute(
                    "INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(user_id) DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at;",
                    (row.get("user_id"), row.get("balance", 0), row.get("updated_at", now))
                )
                updated += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/database?flash={updated}+کیف‌پول+بازیابی+شد")


@router.post("/database/import/settings")
async def import_settings(request: Request, file: UploadFile = None):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard

    if not file:
        return _redir("/admin/database?flash=فایل+انتخاب+نشده")

    content = await file.read()
    try:
        data = json.loads(content)
    except Exception:
        return _redir("/admin/database?flash=فرمت+فایل+نامعتبر")

    conn = _db()
    try:
        imported = 0
        now = datetime.now().isoformat()
        for row in data:
            try:
                conn.execute(
                    "INSERT INTO ui_texts (key, value, updated_at) VALUES (?,?,?) "
                    "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at;",
                    (row.get("key"), row.get("value"), row.get("updated_at", now))
                )
                imported += 1
            except Exception:
                pass
        conn.commit()
    finally:
        conn.close()

    # پاک کردن cache متن‌ها
    try:
        from ui_texts import ui_cache_clear
        ui_cache_clear()
    except Exception:
        pass

    return _redir(f"/admin/database?flash={imported}+تنظیمات+بازیابی+شد")

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

# ─────────────────────────── Categories ────────────────────────────────────

def _render_cat_tree(cats_all: list, parent_id=None, depth=0) -> str:
    """رندر درختی دسته‌بندی‌ها"""
    rows = ""
    children = [c for c in cats_all if c["parent_id"] == parent_id]
    for cat in children:
        indent = "　" * depth
        emoji = (cat["emoji"] or "").strip()
        label = f"{emoji} {cat['name']}".strip() if emoji else cat["name"]
        active_badge = '<span class="text-xs text-green-600">فعال</span>' if cat["is_active"] else '<span class="text-xs text-red-500">غیرفعال</span>'
        rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-2 text-sm">{indent}{'└ ' if depth else ''}{e(label)}</td>
          <td class="px-4 py-2">{active_badge}</td>
          <td class="px-4 py-2 text-xs text-gray-400">{cat['sort_order']}</td>
          <td class="px-4 py-2 flex gap-1 flex-wrap">
            {_btn("ویرایش", f"/admin/categories/{cat['id']}/edit", "indigo", small=True)}
            <form method="post" action="/admin/categories/{cat['id']}/toggle" class="inline">
              <button class="btn-sm {"bg-red-100 text-red-700" if cat["is_active"] else "bg-green-100 text-green-700"} rounded">{"غیرفعال" if cat["is_active"] else "فعال"}</button>
            </form>
            <form method="post" action="/admin/categories/{cat['id']}/delete" onsubmit="return confirm('حذف شود؟ همه زیردسته‌ها و محصولات هم حذف می‌شوند.')" class="inline">
              <button class="btn-sm bg-red-100 text-red-700 rounded">حذف</button>
            </form>
          </td>
        </tr>"""
        rows += _render_cat_tree(cats_all, parent_id=cat["id"], depth=depth + 1)
    return rows


def _cat_select_options(cats_all: list, selected_id=None, exclude_id=None, parent_id=None, depth=0) -> str:
    opts = ""
    children = [c for c in cats_all if c["parent_id"] == parent_id]
    for cat in children:
        if cat["id"] == exclude_id:
            continue
        indent = "── " * depth
        sel = "selected" if cat["id"] == selected_id else ""
        opts += f'<option value="{cat["id"]}" {sel}>{indent}{e(cat["name"])}</option>'
        opts += _cat_select_options(cats_all, selected_id, exclude_id, parent_id=cat["id"], depth=depth + 1)
    return opts


@router.get("/categories", response_class=HTMLResponse)
async def categories_list(request: Request, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        cats = conn.execute("SELECT * FROM categories ORDER BY parent_id NULLS FIRST, sort_order, name;").fetchall()
    finally:
        conn.close()

    tree_rows = _render_cat_tree(cats)
    cat_opts = '<option value="">— بدون والد (دسته ریشه) —</option>' + _cat_select_options(cats)

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">🗂 دسته‌بندی‌ها</h1>
    </div>

    <div class="card p-6 mb-6">
      <h2 class="font-bold text-gray-700 mb-4">➕ افزودن دسته جدید</h2>
      <form method="post" action="/admin/categories/add" class="grid md:grid-cols-4 gap-4 items-end">
        <div>
          <label class="text-xs text-gray-500 block mb-1">نام دسته *</label>
          {_input("name", "مثلاً: هوش مصنوعی", required=True)}
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">ایموجی</label>
          {_input("emoji", "🧩")}
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">والد (زیردسته‌ی چه چیزی؟)</label>
          <select name="parent_id" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
            {cat_opts}
          </select>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">ترتیب نمایش</label>
          {_input("sort_order", "0", "0", "number")}
        </div>
        <div class="md:col-span-4">{_btn("➕ افزودن دسته", color="green")}</div>
      </form>
    </div>

    <div class="card overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50 text-sm font-medium text-gray-700">
        ساختار دسته‌بندی‌ها ({len(cats)} دسته)
        <span class="text-xs text-gray-400 mr-2">دسته‌های ریشه در منوی اصلی ربات نمایش داده می‌شوند</span>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-2">نام</th><th class="px-4 py-2">وضعیت</th>
          <th class="px-4 py-2">ترتیب</th><th class="px-4 py-2">عملیات</th>
        </tr></thead>
        <tbody>{tree_rows or "<tr><td colspan='4' class='text-center py-8 text-gray-400'>هنوز دسته‌ای اضافه نشده</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("دسته‌بندی‌ها", body, adm, flash=flash)


@router.post("/categories/add")
async def categories_add(request: Request, name: str = Form(""), emoji: str = Form(""),
                          parent_id: str = Form(""), sort_order: str = Form("0")):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    name = name.strip()
    if not name:
        return _redir("/admin/categories?flash=نام+دسته+الزامی+است")

    pid = int(parent_id) if parent_id.strip().isdigit() else None
    slug = "".join(c if c.isalnum() else "_" for c in name).lower()[:40]
    now = datetime.now().isoformat()

    conn = _db()
    try:
        conn.execute(
            "INSERT INTO categories (name, slug, parent_id, emoji, sort_order, is_active, created_at) VALUES (?,?,?,?,?,1,?);",
            (name, slug, pid, emoji.strip() or "", int(sort_order or 0), now)
        )
        conn.commit()
    except Exception as ex:
        return _redir(f"/admin/categories?flash=خطا: {str(ex)[:50]}")
    finally:
        conn.close()
    return _redir("/admin/categories?flash=دسته+اضافه+شد")


@router.get("/categories/{cid}/edit", response_class=HTMLResponse)
async def categories_edit_get(request: Request, cid: int, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        cat = conn.execute("SELECT * FROM categories WHERE id=? LIMIT 1;", (cid,)).fetchone()
        cats_all = conn.execute("SELECT * FROM categories ORDER BY parent_id NULLS FIRST, sort_order, name;").fetchall()
    finally:
        conn.close()

    if not cat:
        return _redir("/admin/categories")

    cat_opts = '<option value="">— بدون والد (دسته ریشه) —</option>' + _cat_select_options(
        cats_all, selected_id=cat["parent_id"], exclude_id=cid
    )

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/categories", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">✏️ ویرایش: {e(cat["name"])}</h1>
    </div>
    <div class="card p-6 max-w-xl">
      <form method="post" action="/admin/categories/{cid}/edit" class="space-y-4">
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">نام دسته</label>
          {_input("name", "", str(cat["name"]), required=True)}
        </div>
        <div class="grid grid-cols-2 gap-4">
          <div>
            <label class="text-sm font-medium text-gray-700 block mb-1">ایموجی</label>
            {_input("emoji", "🧩", str(cat["emoji"] or ""))}
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700 block mb-1">ترتیب نمایش</label>
            {_input("sort_order", "0", str(cat["sort_order"] or 0), "number")}
          </div>
        </div>
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">والد</label>
          <select name="parent_id" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">{cat_opts}</select>
        </div>
        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-gray-700">فعال</label>
          <input type="checkbox" name="is_active" value="1" {"checked" if cat["is_active"] else ""} class="rounded">
        </div>
        {_btn("ذخیره تغییرات", color="green")}
      </form>
    </div>"""

    return _layout(f"ویرایش دسته #{cid}", body, adm, flash=flash)


@router.post("/categories/{cid}/edit")
async def categories_edit_post(request: Request, cid: int,
    name: str = Form(""), emoji: str = Form(""), parent_id: str = Form(""),
    sort_order: str = Form("0"), is_active: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    pid = int(parent_id) if parent_id.strip().isdigit() else None
    active = 1 if is_active == "1" else 0

    conn = _db()
    try:
        conn.execute(
            "UPDATE categories SET name=?, emoji=?, parent_id=?, sort_order=?, is_active=? WHERE id=?;",
            (name.strip(), emoji.strip(), pid, int(sort_order or 0), active, cid)
        )
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/categories/{cid}/edit?flash=ذخیره+شد")


@router.post("/categories/{cid}/toggle")
async def categories_toggle(request: Request, cid: int):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("UPDATE categories SET is_active=CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (cid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/categories?flash=وضعیت+تغییر+کرد")


@router.post("/categories/{cid}/delete")
async def categories_delete(request: Request, cid: int):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    def collect_ids(conn, cat_id):
        ids = [cat_id]
        children = conn.execute("SELECT id FROM categories WHERE parent_id=?;", (cat_id,)).fetchall()
        for ch in children:
            ids.extend(collect_ids(conn, ch[0]))
        return ids

    conn = _db()
    try:
        all_ids = collect_ids(conn, cid)
        placeholders = ",".join("?" * len(all_ids))
        conn.execute(f"DELETE FROM product_feed WHERE product_id IN (SELECT id FROM products WHERE category_id IN ({placeholders}));", all_ids)
        conn.execute(f"DELETE FROM products WHERE category_id IN ({placeholders});", all_ids)
        conn.execute(f"DELETE FROM categories WHERE id IN ({placeholders});", all_ids)
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/categories?flash=دسته+و+زیردسته‌ها+حذف+شدند")


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
        status_badge = '<span class="px-2 py-0.5 text-xs bg-green-100 text-green-700 rounded-full">فعال</span>' if p["is_active"] else '<span class="px-2 py-0.5 text-xs bg-red-100 text-red-700 rounded-full">غیرفعال</span>'
        rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-3 text-sm font-medium text-gray-800">{e(p["title"])}</td>
          <td class="px-4 py-3 text-xs text-gray-400">{e(p["category"])}</td>
          <td class="px-4 py-3 text-sm font-medium text-indigo-700">{int(p["price"]):,}</td>
          <td class="px-4 py-3">{status_badge}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 text-xs rounded-full bg-{ac}-100 text-{ac}-700">{avail}/{int(p["feed_total"] or 0)}</span>
          </td>
          <td class="px-4 py-3">
            <div class="flex gap-1">
              <a href="/admin/products/{p['id']}" class="btn-sm bg-indigo-50 text-indigo-700 border border-indigo-200 rounded px-2 py-1 text-xs">✏️</a>
              <a href="/admin/feed/{p['id']}" class="btn-sm bg-teal-50 text-teal-700 border border-teal-200 rounded px-2 py-1 text-xs">📦</a>
              <form method="post" action="/admin/products/{p['id']}/toggle" class="inline">
                <button class="btn-sm {"bg-red-50 text-red-600 border border-red-200" if p["is_active"] else "bg-green-50 text-green-600 border border-green-200"} rounded px-2 py-1 text-xs">
                  {"⊘" if p["is_active"] else "✓"}
                </button>
              </form>
              <form method="post" action="/admin/products/{p['id']}/delete" class="inline"
                onsubmit="return confirm('حذف شود؟')">
                <button class="btn-sm bg-red-50 text-red-600 border border-red-200 rounded px-2 py-1 text-xs">🗑</button>
              </form>
            </div>
          </td>
        </tr>"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">📦 محصولات</h1>
      {_btn("➕ محصول جدید", "/admin/products/new", "green")}
    </div>
    <div class="card overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-right min-w-max">
          <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
            <th class="px-4 py-3">عنوان</th><th class="px-4 py-3">دسته</th>
            <th class="px-4 py-3">قیمت</th><th class="px-4 py-3">وضعیت</th>
            <th class="px-4 py-3">موجودی</th><th class="px-4 py-3">عملیات</th>
          </tr></thead>
          <tbody>{rows or "<tr><td colspan='6' class='text-center py-8 text-gray-400'>محصولی ثبت نشده</td></tr>"}</tbody>
        </table>
      </div>
    </div>"""

    return _layout("محصولات", body, adm, flash=flash)

@router.get("/products/new", response_class=HTMLResponse)
async def product_new_get(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    conn = _db()
    try:
        cats_all = conn.execute("SELECT * FROM categories WHERE is_active=1 ORDER BY parent_id NULLS FIRST, sort_order, name;").fetchall()
    finally:
        conn.close()

    if not cats_all:
        body = f"""
        <div class="flex items-center gap-3 mb-6">
          {_btn("← بازگشت", "/admin/products", "slate", small=True)}
          <h1 class="text-2xl font-bold text-gray-800">➕ محصول جدید</h1>
        </div>
        <div class="card p-6">
          <p class="text-amber-600">⚠️ ابتدا باید دسته‌بندی بسازید.</p>
          <div class="mt-4">{_btn("← ساخت دسته‌بندی", "/admin/categories", "indigo")}</div>
        </div>"""
        return _layout("محصول جدید", body, adm)

    cat_opts = _cat_select_options(cats_all)

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/products", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">➕ محصول جدید</h1>
    </div>
    <form method="post" action="/admin/products/new" class="card p-6 max-w-2xl space-y-4">
      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">دسته‌بندی *</label>
        <select name="category_id" required class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">
          <option value="">انتخاب کنید...</option>
          {cat_opts}
        </select>
      </div>
      <div><label class="text-sm font-medium text-gray-700 block mb-1">عنوان محصول *</label>
        {_input("title", "عنوان محصول", required=True)}</div>
      <div class="grid grid-cols-2 gap-4">
        <div><label class="text-sm font-medium text-gray-700 block mb-1">قیمت (تومان) *</label>
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
    category_id: str=Form(""), title: str=Form(""), price: str=Form("0"),
    partner_price: str=Form("0"), limit_c: str=Form("0"), limit_p: str=Form("0"),
    description: str=Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "products")
    if guard: return guard

    if not category_id.strip().isdigit():
        return _redir("/admin/products/new?flash=دسته‌بندی+انتخاب+کنید")

    cat_id = int(category_id)
    pp = int(partner_price or 0)
    slug = "".join(c if c.isalnum() else "_" for c in title).lower()[:40] or "product"

    conn = _db()
    try:
        cat = conn.execute("SELECT slug, name FROM categories WHERE id=?;", (cat_id,)).fetchone()
        cat_slug = cat["slug"] if cat else str(cat_id)
        conn.execute("""
            INSERT INTO products (category, category_id, product_key, title, price, partner_price,
                daily_limit_customer, daily_limit_partner, description, is_active)
            VALUES (?,?,?,?,?,?,?,?,?,1);""",
            (cat_slug, cat_id, slug, title.strip(), int(price or 0), pp if pp > 0 else None,
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
        # چک feed — اگه موجودی داشت اجازه حذف نده
        avail = conn.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id=? AND delivered=0;", (pid,)
        ).fetchone()[0]
        if avail > 0:
            conn.close()
            return _redir(f"/admin/products/{pid}?flash=⚠️+محصول+{avail}+موجودی+دارد.+ابتدا+موجودی+را+از+بخش+فید+پاک+کنید")

        conn.execute("DELETE FROM product_feed WHERE product_id=?;", (pid,))
        conn.execute("DELETE FROM products WHERE id=?;", (pid,))
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/products?flash=محصول+حذف+شد")

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
          <td class="px-4 py-2 flex gap-1">
            {_btn("ویرایش", f"/admin/feed/item/{item['id']}/edit", "indigo", small=True)}
            <form method="post" action="/admin/feed/item/{item['id']}/delete" onsubmit="return confirm('حذف شود؟')" class="inline">
              <button class="btn-sm bg-red-100 text-red-600 rounded">حذف</button>
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
async def feed_clear(request: Request, pid: int, background_tasks: BackgroundTasks):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    def _do_clear(product_id: int):
        conn = _db()
        try:
            # حذف دسته‌ای با LIMIT برای جلوگیری از قفل شدن DB
            while True:
                r = conn.execute(
                    "DELETE FROM product_feed WHERE rowid IN "
                    "(SELECT rowid FROM product_feed WHERE product_id=? AND delivered=1 LIMIT 500);",
                    (product_id,)
                )
                conn.commit()
                if r.rowcount == 0:
                    break
        finally:
            conn.close()

    # شمارش قبل از حذف
    conn = _db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM product_feed WHERE product_id=? AND delivered=1;", (pid,)).fetchone()[0]
    finally:
        conn.close()

    background_tasks.add_task(_do_clear, pid)
    return _redir(f"/admin/feed/{pid}?flash={n}+آیتم+در+حال+پاکسازی+است")

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


@router.get("/feed/item/{fid}/edit", response_class=HTMLResponse)
async def feed_item_edit_get(request: Request, fid: int, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    conn = _db()
    try:
        item = conn.execute("SELECT * FROM product_feed WHERE id=? LIMIT 1;", (fid,)).fetchone()
        if not item:
            return _redir("/admin/feed")
        product = conn.execute("SELECT title FROM products WHERE id=? LIMIT 1;", (item["product_id"],)).fetchone()
        product_title = product["title"] if product else f"#{item['product_id']}"
    finally:
        conn.close()

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", f"/admin/feed/{item['product_id']}", "slate", small=True)}
      <h1 class="text-xl font-bold text-gray-800">✏️ ویرایش آیتم فید #{fid}</h1>
      <span class="text-sm text-gray-400">{e(product_title)}</span>
    </div>
    <div class="card p-6 max-w-2xl">
      <form method="post" action="/admin/feed/item/{fid}/edit" class="space-y-4">
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">محتوای آیتم</label>
          <div class="text-xs text-gray-400 mb-2">برای چندخطی: هر خط محتوا است</div>
          {_textarea("data", "", str(item["data"] or ""), rows=6)}
        </div>
        <div class="flex items-center gap-3">
          <label class="text-sm font-medium text-gray-700">تحویل داده شده</label>
          <input type="checkbox" name="delivered" value="1" {"checked" if item["delivered"] else ""}>
        </div>
        <div class="flex gap-3">
          {_btn("ذخیره", color="green")}
          {_btn("انصراف", f"/admin/feed/{item['product_id']}", "slate")}
        </div>
      </form>
    </div>"""

    return _layout(f"ویرایش فید #{fid}", body, adm, flash=flash)


@router.post("/feed/item/{fid}/edit")
async def feed_item_edit_post(request: Request, fid: int,
                               data: str = Form(""), delivered: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "feed")
    if guard: return guard

    conn = _db()
    try:
        row = conn.execute("SELECT product_id FROM product_feed WHERE id=?;", (fid,)).fetchone()
        pid = row["product_id"] if row else 0
        delivered_val = 1 if delivered == "1" else 0
        conn.execute(
            "UPDATE product_feed SET data=?, delivered=? WHERE id=?;",
            (data.strip(), delivered_val, fid)
        )
        conn.commit()
    finally:
        conn.close()
    return _redir(f"/admin/feed/{pid}?flash=آیتم+ویرایش+شد")

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

# ─────────────────────────── Telegram Helper ───────────────────────────────

import logging as _logging
_tg_logger = _logging.getLogger("admin_panel.tg")


def _tg_send(chat_id: int, text: str, parse_mode: str = "HTML",
              reply_markup: dict | None = None) -> bool:
    token = _env("BOT_TOKEN")
    if not token:
        _tg_logger.error("BOT_TOKEN not set — cannot send Telegram message")
        return False
    try:
        data: dict = {"chat_id": int(chat_id), "text": text, "parse_mode": parse_mode}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json=data, timeout=15
        )
        if not r.ok:
            _tg_logger.error("Telegram sendMessage failed: %s %s", r.status_code, r.text[:200])
        return r.ok
    except Exception as ex:
        _tg_logger.exception("_tg_send error: %s", ex)
        return False


def _tg_send_photo(chat_id: int, photo_url: str, caption: str = "",
                    reply_markup: dict | None = None) -> bool:
    token = _env("BOT_TOKEN")
    if not token:
        return False
    try:
        data: dict = {"chat_id": chat_id, "photo": photo_url, "caption": caption, "parse_mode": "HTML"}
        if reply_markup:
            data["reply_markup"] = json.dumps(reply_markup)
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/sendPhoto",
            json=data, timeout=15
        )
        return r.ok
    except Exception:
        return False


# ─────────────────────────── Tickets ───────────────────────────────────────

def _ticket_status_badge(status: str) -> str:
    colors = {
        "waiting_admin": "red",
        "waiting_user":  "yellow",
        "closed":        "gray",
        # backward compat
        "open": "green", "in_progress": "yellow",
    }
    labels = {
        "waiting_admin": "منتظر ادمین",
        "waiting_user":  "منتظر کاربر",
        "closed":        "بسته",
        "open": "باز", "in_progress": "در بررسی",
    }
    c = colors.get(status, "slate")
    l = labels.get(status, status)
    return f'<span class="px-2 py-0.5 text-xs rounded-full bg-{c}-100 text-{c}-700">{l}</span>'


@router.get("/tickets", response_class=HTMLResponse)
async def tickets_list(request: Request, status_filter: str = "", flash: str = ""):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    conn = _db()
    try:
        where = "WHERE t.status=?" if status_filter else ""
        params = (status_filter, 100) if status_filter else (100,)
        tickets = conn.execute(f"""
            SELECT t.*,
                   (SELECT COUNT(*) FROM ticket_messages m WHERE m.ticket_id=t.id) AS msg_count
            FROM tickets t {where}
            ORDER BY CASE t.status WHEN 'waiting_admin' THEN 0 WHEN 'waiting_user' THEN 1 ELSE 2 END,
                     t.updated_at DESC LIMIT ?;
        """, params).fetchall()
        stats = {s: conn.execute(f"SELECT COUNT(*) FROM tickets WHERE status='{s}';").fetchone()[0]
                 for s in ("waiting_admin", "waiting_user", "closed")}
    finally:
        conn.close()

    def status_badge(s):
        cfg = {
            "waiting_admin": ("🔴 منتظر پاسخ ادمین", "red"),
            "waiting_user":  ("🟡 منتظر کاربر", "yellow"),
            "closed":        ("⚫ بسته", "gray"),
        }
        lbl, color = cfg.get(s, (s, "slate"))
        return f'<span class="px-2 py-0.5 text-xs rounded-full bg-{color}-100 text-{color}-700">{lbl}</span>'

    tabs = [
        ("همه", "", sum(stats.values())),
        ("منتظر ادمین 🔴", "waiting_admin", stats["waiting_admin"]),
        ("منتظر کاربر 🟡", "waiting_user",  stats["waiting_user"]),
        ("بسته", "closed", stats["closed"]),
    ]
    tab_nav = '<div class="flex gap-2 mb-4 flex-wrap">'
    for lbl, val, cnt in tabs:
        active = "bg-indigo-600 text-white" if status_filter == val else "bg-white text-gray-600"
        tab_nav += f'<a href="/admin/tickets?status_filter={val}" class="px-3 py-1.5 rounded-lg border text-sm {active}">{lbl} ({cnt})</a>'
    tab_nav += "</div>"

    rows = ""
    for t in tickets:
        rows += f"""
        <tr class="border-b hover:bg-gray-50 text-sm cursor-pointer" onclick="location.href='/admin/tickets/{t['id']}'">
          <td class="px-4 py-3 text-gray-400">#{t["id"]}</td>
          <td class="px-4 py-3 font-mono text-xs"><code>{t["user_id"]}</code></td>
          <td class="px-4 py-3"><span class="text-xs bg-gray-100 px-1.5 rounded">{t["type"]}</span></td>
          <td class="px-4 py-3">{status_badge(t["status"])}</td>
          <td class="px-4 py-3 text-gray-400 text-xs">{int(t["msg_count"] or 0)} پیام</td>
          <td class="px-4 py-3 text-gray-400 text-xs">{(t["updated_at"] or "")[:16]}</td>
          <td class="px-4 py-3">{_btn("مشاهده", f"/admin/tickets/{t['id']}", "indigo", small=True)}</td>
        </tr>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-4">🎫 تیکت‌های پشتیبانی</h1>
    {tab_nav}
    <div class="card overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">#</th><th class="px-4 py-3">User ID</th>
          <th class="px-4 py-3">نوع</th><th class="px-4 py-3">وضعیت</th>
          <th class="px-4 py-3">پیام‌ها</th><th class="px-4 py-3">آپدیت</th><th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='7' class='text-center py-8 text-gray-400'>تیکتی یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("تیکت‌ها", body, adm, flash=flash)
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    conn = _db()
    try:
        where = "WHERE t.status=?" if status_filter else ""
        params = (status_filter, 100) if status_filter else (100,)
        tickets = conn.execute(f"""
            SELECT t.*, p.title as product_title,
                   (SELECT COUNT(*) FROM ticket_messages tm WHERE tm.ticket_id=t.id) as msg_count
            FROM tickets t
            LEFT JOIN products p ON t.product_id=p.id
            {where} ORDER BY
              CASE t.status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END,
              t.id DESC LIMIT ?;
        """, params).fetchall()
        stats = {
            "open": conn.execute("SELECT COUNT(*) FROM tickets WHERE status='open';").fetchone()[0],
            "in_progress": conn.execute("SELECT COUNT(*) FROM tickets WHERE status='in_progress';").fetchone()[0],
            "closed": conn.execute("SELECT COUNT(*) FROM tickets WHERE status='closed';").fetchone()[0],
        }
    finally:
        conn.close()

    tab_nav = '<div class="flex gap-2 mb-4">'
    for lbl, val, count in [
        ("همه", "", stats["open"] + stats["in_progress"] + stats["closed"]),
        (f"باز ({stats['open']})", "open", stats["open"]),
        (f"در بررسی ({stats['in_progress']})", "in_progress", stats["in_progress"]),
        (f"بسته ({stats['closed']})", "closed", stats["closed"]),
    ]:
        active = "bg-indigo-600 text-white" if status_filter == val else "bg-white text-gray-600 hover:bg-gray-50"
        tab_nav += f'<a href="/admin/tickets?status_filter={val}" class="px-4 py-2 rounded-lg border text-sm {active}">{lbl}</a>'
    tab_nav += "</div>"

    rows = ""
    for t in tickets:
        rows += f"""
        <tr class="border-b hover:bg-gray-50 text-sm">
          <td class="px-4 py-3 text-gray-400">#{t["id"]}</td>
          <td class="px-4 py-3 font-mono text-xs"><code>{t["user_id"]}</code></td>
          <td class="px-4 py-3">{e(t["product_title"] or "-")}</td>
          <td class="px-4 py-3 text-gray-400">#{t["order_no"]}</td>
          <td class="px-4 py-3">{_ticket_status_badge(t["status"])}</td>
          <td class="px-4 py-3 text-xs text-gray-400">{int(t["msg_count"] or 0)} پیام</td>
          <td class="px-4 py-3">{(t["created_at"] or "")[:10]}</td>
          <td class="px-4 py-3">{_btn("مشاهده", f"/admin/tickets/{t['id']}", "indigo", small=True)}</td>
        </tr>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-4">🎫 تیکت‌های پشتیبانی</h1>
    {tab_nav}
    <div class="card overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">#</th><th class="px-4 py-3">User ID</th>
          <th class="px-4 py-3">محصول</th><th class="px-4 py-3">سفارش</th>
          <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">پیام‌ها</th>
          <th class="px-4 py-3">تاریخ</th><th class="px-4 py-3"></th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='8' class='text-center py-8 text-gray-400'>تیکتی یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("تیکت‌ها", body, adm, flash=flash)


@router.get("/tickets/{tid}", response_class=HTMLResponse)
async def ticket_detail(request: Request, tid: int, flash: str = ""):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    conn = _db()
    try:
        ticket = conn.execute("""
            SELECT t.*, p.title as product_title
            FROM tickets t LEFT JOIN products p ON t.product_id=p.id
            WHERE t.id=? LIMIT 1;
        """, (tid,)).fetchone()

        if not ticket:
            return _redir("/admin/tickets")

        messages = conn.execute(
            "SELECT * FROM ticket_messages WHERE ticket_id=? ORDER BY id ASC;", (tid,)
        ).fetchall()

        # وقتی ادمین تیکت رو باز می‌کنه → status به in_progress تغییر کنه (badge پاک بشه)
        if ticket["status"] == "open":
            conn.execute("UPDATE tickets SET status='in_progress' WHERE id=?;", (tid,))
            conn.commit()

    finally:
        conn.close()

    is_general = (not ticket["product_id"] or int(ticket["product_id"] or 0) == 0)
    is_closed = (ticket["status"] == "closed")
    user_id_val = int(ticket["user_id"])

    # ── مکالمه ──────────────────────────────────────────────────────────────
    chat_html = ""
    for msg in messages:
        is_adm = msg["sender"] == "admin"
        pos = "items-end" if is_adm else "items-start"
        bubble = "bg-indigo-600 text-white" if is_adm else "bg-white border border-gray-200 text-gray-800"
        lbl = "ادمین 👤" if is_adm else f"کاربر ({user_id_val})"
        txt_safe = e(msg["text"] or "")
        if msg["media_type"]:
            txt_safe += f' <em class="text-xs opacity-60">[{e(msg["media_type"])}]</em>'
        chat_html += f"""
        <div class="flex flex-col {pos} mb-3">
          <div class="text-xs text-gray-400 mb-1">{lbl} · {(msg["created_at"] or "")[:16]}</div>
          <div class="{bubble} rounded-2xl px-4 py-2 text-sm max-w-xs" style="white-space:pre-wrap">{txt_safe}</div>
        </div>"""

    if not chat_html:
        chat_html = '<div class="text-center py-8 text-gray-400 text-sm">پیامی ثبت نشده</div>'

    # ── فرم پاسخ ─────────────────────────────────────────────────────────────
    reply_form = ""
    if not is_closed:
        reply_form = f"""
        <div class="card p-4 mt-4">
          <form method="post" action="/admin/tickets/{tid}/reply">
            <div class="mb-3">
              <label class="text-xs text-gray-500 block mb-1">
                پاسخ به کاربر <code class="bg-gray-100 px-1 rounded">{user_id_val}</code>
              </label>
              <textarea name="text" rows="3" required
                placeholder="متن پاسخ را بنویسید..."
                class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-indigo-300"></textarea>
            </div>
            <div class="flex justify-end">
              <button type="submit"
                class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-xl text-sm font-medium">
                📤 ارسال پاسخ
              </button>
            </div>
          </form>
        </div>"""

    # ── وضعیت دکمه‌ها ────────────────────────────────────────────────────────
    status_btns = ""
    cur_status = ticket["status"]
    for lbl2, val2, cls2 in [
        ("🔓 بازکردن", "open", "bg-green-50 text-green-700 border-green-200"),
        ("⏳ در بررسی", "in_progress", "bg-yellow-50 text-yellow-700 border-yellow-200"),
        ("🔒 بستن", "closed", "bg-gray-100 text-gray-600 border-gray-200"),
    ]:
        if val2 != cur_status:
            status_btns += f"""
            <form method="post" action="/admin/tickets/{tid}/status" class="inline-block mr-1 mb-1">
              <input type="hidden" name="status" value="{val2}">
              <button class="btn-sm border rounded-lg px-3 py-1.5 text-xs {cls2}">{lbl2}</button>
            </form>"""

    # ── ساختار صفحه ─────────────────────────────────────────────────────────
    ticket_type = "پشتیبانی عمومی" if is_general else e(ticket["product_title"] or "-")

    body = f"""
    <div class="flex items-center gap-3 mb-4 flex-wrap">
      {_btn("← تیکت‌ها", "/admin/tickets", "slate", small=True)}
      <h1 class="text-xl font-bold text-gray-800">🎫 تیکت #{tid}</h1>
      {_ticket_status_badge(ticket["status"])}
      <span class="text-sm text-gray-400">{ticket_type}</span>
    </div>

    <div class="grid lg:grid-cols-3 gap-4">
      <!-- مکالمه + فرم پاسخ -->
      <div class="lg:col-span-2">
        <div class="card p-4 overflow-y-auto" style="min-height:280px;max-height:450px;" id="chat-box">
          {chat_html}
        </div>
        {reply_form}
        {"" if is_closed else f'''
        <div class="card p-4 mt-3 border-dashed border-2 border-gray-200 bg-gray-50">
          <p class="text-xs text-gray-400 mb-2">📩 پیام مستقیم (بدون ثبت در تاریخچه)</p>
          <form method="post" action="/admin/tickets/{tid}/direct" class="flex gap-2">
            <textarea name="direct_msg" rows="2" placeholder="پیام آزاد..."
              class="flex-1 border border-gray-200 rounded-lg px-3 py-1.5 text-sm resize-none"></textarea>
            <button type="submit" class="bg-gray-500 hover:bg-gray-600 text-white rounded-lg px-3 py-2 text-xs self-end">ارسال</button>
          </form>
        </div>'''}
      </div>

      <!-- اطلاعات -->
      <div class="space-y-3">
        <div class="card p-4">
          <h3 class="font-bold text-gray-700 mb-3 text-sm">اطلاعات تیکت</h3>
          <dl class="space-y-2 text-sm">
            <div class="flex justify-between"><dt class="text-gray-400">User ID</dt>
              <dd><code class="text-xs bg-gray-100 px-1 rounded">{user_id_val}</code></dd></div>
            <div class="flex justify-between"><dt class="text-gray-400">نوع</dt><dd class="text-gray-700 text-xs">{ticket_type}</dd></div>
            <div class="flex justify-between"><dt class="text-gray-400">پیام‌ها</dt>
              <dd class="font-bold text-indigo-600">{len(messages)}</dd></div>
            <div class="flex justify-between"><dt class="text-gray-400">تاریخ</dt>
              <dd class="text-xs text-gray-400">{(ticket["created_at"] or "")[:16]}</dd></div>
          </dl>
        </div>
        <div class="card p-4">
          <h3 class="font-bold text-gray-700 mb-2 text-sm">تغییر وضعیت</h3>
          <div>{status_btns}</div>
        </div>
      </div>
    </div>
    <script>
      (function(){{
        var b=document.getElementById('chat-box');
        if(b) b.scrollTop=b.scrollHeight;
      }})();
    </script>"""

    return _layout(f"تیکت #{tid}", body, adm, flash=flash)


@router.post("/tickets/{tid}/reply")
async def ticket_reply(request: Request, tid: int, text: str = Form("")):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    text = text.strip()
    if not text:
        return _redir(f"/admin/tickets/{tid}?flash=متن+خالی+است")

    conn = _db()
    try:
        ticket = conn.execute(
            "SELECT user_id, status FROM tickets WHERE id=? LIMIT 1;", (tid,)
        ).fetchone()
        if not ticket:
            return _redir("/admin/tickets?flash=تیکت+یافت+نشد")
        if ticket["status"] == "closed":
            return _redir(f"/admin/tickets/{tid}?flash=تیکت+بسته+است")
        user_id = int(ticket["user_id"])
    finally:
        conn.close()

    # ─── ذخیره پاسخ در DB ─────────────────────────────────────────────────
    now = datetime.now().isoformat()
    conn2 = _db()
    try:
        conn2.execute(
            "INSERT INTO ticket_messages (ticket_id, sender, text, source, created_at) VALUES (?,?,?,?,?);",
            (tid, "admin", text, "panel", now)
        )
        # status → waiting_user، counter reset
        conn2.execute(
            "UPDATE tickets SET status='waiting_user', user_msg_count=0, updated_at=? WHERE id=?;",
            (now, tid)
        )
        conn2.commit()
    finally:
        conn2.close()

    # ─── ارسال به کاربر از طریق Telegram API ─────────────────────────────
    msg_text = f"💬 <b>پاسخ پشتیبانی</b> (تیکت #{tid}):\n\n{html.escape(text)}"
    ok = _tg_send(user_id, msg_text)

    if ok:
        return _redir(f"/admin/tickets/{tid}?flash=پاسخ+ارسال+شد")
    else:
        return _redir(f"/admin/tickets/{tid}?flash=ذخیره+شد+اما+ارسال+تلگرام+ناموفق")


@router.post("/tickets/{tid}/direct")
async def ticket_direct(request: Request, tid: int, direct_msg: str = Form("")):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    direct_msg = direct_msg.strip()
    if not direct_msg:
        return _redir(f"/admin/tickets/{tid}")

    conn = _db()
    try:
        ticket = conn.execute("SELECT user_id FROM tickets WHERE id=? LIMIT 1;", (tid,)).fetchone()
        user_id = ticket["user_id"] if ticket else None
    finally:
        conn.close()

    if user_id:
        _tg_send(user_id, f"📩 <b>پیام مستقیم از پشتیبانی:</b>\n\n{html.escape(direct_msg)}")

    return _redir(f"/admin/tickets/{tid}?flash=پیام+مستقیم+ارسال+شد")


@router.post("/tickets/{tid}/status")
async def ticket_status(request: Request, tid: int, status: str = Form("")):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    valid = {"open", "in_progress", "closed"}
    if status not in valid:
        return _redir(f"/admin/tickets/{tid}")

    conn = _db()
    try:
        now = datetime.now().isoformat()
        if status == "closed":
            conn.execute("UPDATE tickets SET status=?, closed_at=?, closed_by='admin' WHERE id=?;", (status, now, tid))
        else:
            conn.execute("UPDATE tickets SET status=? WHERE id=?;", (status, tid))
        conn.commit()
    finally:
        conn.close()

    return _redir(f"/admin/tickets/{tid}?flash=وضعیت+تغییر+کرد")


# ─────────────────────────── Broadcast ─────────────────────────────────────

# وضعیت broadcast جاری
_broadcast_state: dict = {"running": False, "total": 0, "sent": 0, "failed": 0, "done": False}
_broadcast_lock = threading.Lock()


def _do_broadcast(user_ids: list[int], text: str, photo_url: str,
                   inline_buttons: list[dict], token: str) -> None:
    global _broadcast_state
    with _broadcast_lock:
        _broadcast_state.update({"running": True, "total": len(user_ids), "sent": 0, "failed": 0, "done": False})

    markup = None
    if inline_buttons:
        markup = {"inline_keyboard": [inline_buttons]}

    for uid in user_ids:
        try:
            if photo_url:
                _tg_send_photo(uid, photo_url, caption=text, reply_markup=markup)
            else:
                _tg_send(uid, text, reply_markup=markup)
            with _broadcast_lock:
                _broadcast_state["sent"] += 1
        except Exception:
            with _broadcast_lock:
                _broadcast_state["failed"] += 1
        time.sleep(0.05)  # rate limit safety

    with _broadcast_lock:
        _broadcast_state["running"] = False
        _broadcast_state["done"] = True


@router.get("/broadcast", response_class=HTMLResponse)
async def broadcast_page(request: Request, flash: str = ""):
    adm = _get_admin(request)
    guard = _require(adm, "broadcast")
    if guard: return guard

    conn = _db()
    try:
        total_users = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        total_buyers = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders;").fetchone()[0]
        non_buyers = total_users - total_buyers
        products = conn.execute("SELECT id, title FROM products WHERE is_active=1 ORDER BY title;").fetchall()
        categories = conn.execute("SELECT id, name FROM categories WHERE is_active=1 ORDER BY name;").fetchall()
    finally:
        conn.close()

    prod_opts = "".join(f'<option value="{p["id"]}">{e(p["title"])}</option>' for p in products)
    cat_opts = "".join(f'<option value="{c["id"]}">{e(c["name"])}</option>' for c in categories)

    # وضعیت broadcast جاری
    status_html = ""
    with _broadcast_lock:
        st = dict(_broadcast_state)
    if st["total"] > 0:
        pct = int(st["sent"] / max(st["total"], 1) * 100)
        status_color = "green" if st["done"] else "indigo"
        status_html = f"""
        <div class="card p-5 mb-6 border-r-4 border-{status_color}-500">
          <h3 class="font-bold text-{status_color}-700 mb-2">{"✅ ارسال تمام شد" if st["done"] else "🔄 در حال ارسال..."}</h3>
          <div class="bg-gray-100 rounded-full h-3 mb-2">
            <div class="bg-{status_color}-500 h-3 rounded-full" style="width:{pct}%"></div>
          </div>
          <div class="text-sm text-gray-600">
            ارسال‌شده: {st["sent"]} | ناموفق: {st["failed"]} | کل: {st["total"]}
          </div>
        </div>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">📢 پیام‌رسانی و Broadcast</h1>

    {status_html}

    <div class="grid md:grid-cols-3 gap-4 mb-6">
      {_card("کل کاربران", str(total_users), "در سیستم", "indigo")}
      {_card("خریداران", str(total_buyers), "حداقل یک خرید", "green")}
      {_card("بدون خرید", str(non_buyers), "عضو بدون خرید", "orange")}
    </div>

    <div class="card p-6">
      <h2 class="font-bold text-gray-700 mb-4">ارسال پیام جدید</h2>
      <form method="post" action="/admin/broadcast/send" class="space-y-4">

        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">مخاطبان *</label>
          <select name="target" id="target-select" onchange="toggleTargetOptions(this.value)"
            class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="all">همه کاربران ({total_users} نفر)</option>
            <option value="buyers">خریداران ({total_buyers} نفر)</option>
            <option value="non_buyers">بدون خرید ({non_buyers} نفر)</option>
            <option value="product">خریداران یک محصول خاص</option>
            <option value="category">خریداران یک دسته خاص</option>
          </select>
        </div>

        <div id="product-select" style="display:none">
          <label class="text-sm font-medium text-gray-700 block mb-1">محصول</label>
          <select name="product_id" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
            {prod_opts}
          </select>
        </div>

        <div id="category-select" style="display:none">
          <label class="text-sm font-medium text-gray-700 block mb-1">دسته‌بندی</label>
          <select name="category_id" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm">
            {cat_opts}
          </select>
        </div>

        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">متن پیام * (HTML پشتیبانی می‌شود)</label>
          {_textarea("text", "متن پیام را بنویسید...\n<b>بولد</b> و <i>ایتالیک</i> پشتیبانی می‌شود.", rows=5)}
        </div>

        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">آدرس عکس (اختیاری)</label>
          {_input("photo_url", "https://example.com/image.jpg")}
        </div>

        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">دکمه‌های Inline (اختیاری)</label>
          <div class="text-xs text-gray-400 mb-1">فرمت: متن|لینک — هر دکمه در یک خط</div>
          {_textarea("buttons", "دکمه اول|https://t.me/yourbot\nدکمه دوم|https://site.com", rows=3)}
        </div>

        <div class="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-700">
          ⚠️ بعد از ارسال، عملیات در پس‌زمینه انجام می‌شود. صفحه را ببندید و بعداً وضعیت را چک کنید.
        </div>

        {_btn("📢 شروع ارسال", color="green")}
      </form>
    </div>

    <script>
    function toggleTargetOptions(val) {{
      document.getElementById('product-select').style.display = val === 'product' ? '' : 'none';
      document.getElementById('category-select').style.display = val === 'category' ? '' : 'none';
    }}
    </script>"""

    return _layout("پیام‌رسانی", body, adm, flash=flash)


@router.post("/broadcast/send")
async def broadcast_send(request: Request, background_tasks: BackgroundTasks,
    target: str = Form("all"), text: str = Form(""), photo_url: str = Form(""),
    buttons: str = Form(""), product_id: str = Form(""), category_id: str = Form("")):
    adm = _get_admin(request)
    guard = _require(adm, "broadcast")
    if guard: return guard

    with _broadcast_lock:
        if _broadcast_state["running"]:
            return _redir("/admin/broadcast?flash=یک+broadcast+در+حال+اجرا+است")

    text = text.strip()
    if not text:
        return _redir("/admin/broadcast?flash=متن+پیام+الزامی+است")

    # parse inline buttons
    inline_buttons = []
    for line in (buttons or "").strip().splitlines():
        line = line.strip()
        if "|" in line:
            parts = line.split("|", 1)
            if len(parts) == 2 and parts[1].strip().startswith("http"):
                inline_buttons.append({"text": parts[0].strip(), "url": parts[1].strip()})

    # get target users
    pid = int(product_id) if product_id.strip().isdigit() else None
    cid = int(category_id) if category_id.strip().isdigit() else None

    conn = _db()
    try:
        if target == "all":
            rows = conn.execute("SELECT user_id FROM users;").fetchall()
        elif target == "buyers":
            rows = conn.execute("SELECT DISTINCT user_id FROM orders;").fetchall()
        elif target == "non_buyers":
            rows = conn.execute("""
                SELECT u.user_id FROM users u
                LEFT JOIN orders o ON u.user_id=o.user_id WHERE o.user_id IS NULL;
            """).fetchall()
        elif target == "product" and pid:
            rows = conn.execute("SELECT DISTINCT user_id FROM orders WHERE product_id=?;", (str(pid),)).fetchall()
        elif target == "category" and cid:
            rows = conn.execute("""
                SELECT DISTINCT o.user_id FROM orders o
                JOIN products p ON CAST(o.product_id AS INTEGER)=p.id WHERE p.category_id=?;
            """, (cid,)).fetchall()
        else:
            rows = []
        user_ids = [int(r[0]) for r in rows]
    finally:
        conn.close()

    if not user_ids:
        return _redir("/admin/broadcast?flash=هیچ+کاربری+یافت+نشد")

    token = _env("BOT_TOKEN")
    background_tasks.add_task(_do_broadcast, user_ids, text, photo_url.strip(), inline_buttons, token)

    return _redir(f"/admin/broadcast?flash=ارسال+به+{len(user_ids)}+کاربر+آغاز+شد")


@router.get("/broadcast/status")
async def broadcast_status(request: Request):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")
    with _broadcast_lock:
        st = dict(_broadcast_state)
    from fastapi.responses import JSONResponse
    return JSONResponse(st)


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
