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
from datetime import datetime, timedelta

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
    "dashboard":  "مشاهده داشبورد",
    "categories": "مدیریت دسته‌بندی‌ها",
    "products":   "مدیریت محصولات",
    "feed":       "مدیریت موجودی",
    "orders":     "مشاهده سفارش‌ها",
    "tickets":    "مدیریت تیکت‌ها",
    "wallets":    "مدیریت کیف‌پول",
    "partners":   "مدیریت همکاران",
    "settings":   "تنظیمات ربات",
    "database":   "بکاپ و دیتابیس",
    "admins":     "مدیریت ادمین‌ها",
    "broadcast":  "پیام همگانی",
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

IDLE_TIMEOUT_SECONDS = 300  # ۵ دقیقه عدم فعالیت → logout

def _make_session(admin_id: str) -> str:
    """session شامل admin_id و timestamp، امضاشده با HMAC."""
    import time as _t
    ts = str(int(_t.time()))
    secret = _env("SESSION_SECRET", "stockland-panel")
    payload = f"{admin_id}|{ts}"
    token = _hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{token}:{admin_id}|{ts}"

def _get_admin(request: Request):
    """Returns (admin_id, is_super, permissions_list) or None. اعتبارسنجی + بررسی idle timeout."""
    import time as _t
    ensure_admins_table()
    cookie = request.cookies.get("adm", "")
    if not cookie or ":" not in cookie:
        return None

    token, payload = cookie.rsplit(":", 1)

    # payload قالب جدید: admin_id|timestamp — سازگاری با قالب قدیمی (فقط admin_id)
    if "|" in payload:
        admin_id, ts_str = payload.rsplit("|", 1)
    else:
        admin_id, ts_str = payload, None

    expected_token = _hmac.new(
        _env("SESSION_SECRET", "stockland-panel").encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()

    if not _hmac.compare_digest(token, expected_token):
        return None

    # بررسی idle timeout (۵ دقیقه)
    if ts_str:
        try:
            age = int(_t.time()) - int(ts_str)
            if age > IDLE_TIMEOUT_SECONDS:
                return None  # منقضی شده → نیاز به ورود مجدد
        except Exception:
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


def _admin_id_of(admin_info) -> str:
    return admin_info[0] if admin_info else ""

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
    try:
        conn = _db()
        n = conn.execute("SELECT COUNT(*) FROM tickets WHERE status='waiting_admin';").fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


def _pending_partner_count() -> int:
    try:
        conn = _db()
        n = conn.execute("SELECT COUNT(*) FROM partners WHERE status='pending';").fetchone()[0]
        conn.close()
        return int(n)
    except Exception:
        return 0


# ─── Theme System ──────────────────────────────────────────────────────────

DEFAULT_THEME = {
    "sidebar_bg":     "#05070A",
    "sidebar_text":   "#9AA7B8",
    "sidebar_active": "#00D7FF",
    "primary":        "#00D7FF",
    "primary_text":   "#ffffff",
    "accent":         "#F59E0B",
    "page_bg":        "#F7F8FA",
    "card_bg":        "#FFFFFF",
    "text_main":      "#111827",
    "text_muted":     "#6B7280",
    "border":         "#E5E7EB",
}

def _get_theme() -> dict:
    theme = dict(DEFAULT_THEME)
    try:
        conn = _db()
        rows = conn.execute("SELECT key, value FROM panel_theme;").fetchall()
        conn.close()
        for r in rows:
            if r["key"] in theme:
                theme[r["key"]] = r["value"]
    except Exception:
        pass
    return theme

def _ensure_theme_table():
    conn = _db()
    try:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS panel_theme (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
        conn.commit()
    finally:
        conn.close()


def _layout(title: str, body: str, admin_info=None,
            flash: str = "", flash_ok: bool = True) -> HTMLResponse:

    theme = _get_theme()

    flash_html = ""
    if flash:
        icon = "circle-check" if flash_ok else "circle-alert"
        flash_html = f"""
        <div class="flash-msg flash-{'ok' if flash_ok else 'err'}">
          <i data-lucide="{icon}"></i><span>{e(flash)}</span>
        </div>"""

    perms = admin_info[2] if admin_info else []
    is_super = admin_info[1] if admin_info else False

    open_tickets    = _open_ticket_count()    if admin_info else 0
    pending_partners = _pending_partner_count() if admin_info else 0

    def has_perm(perm):
        return is_super or perm in perms

    def nav_item(href, icon, label, perm=None, badge=0):
        if perm and not has_perm(perm):
            return ""
        badge_html = f'<span class="nav-badge">{badge}</span>' if badge > 0 else ""
        return f'<a href="{href}" class="nav-item" data-href="{href}"><i data-lucide="{icon}" class="nav-icon"></i><span class="nav-label">{label}</span>{badge_html}</a>'

    sidebar = ""
    if admin_info:
        sidebar = f"""
        <aside id="sidebar" class="sidebar">
          <div class="sidebar-header">
            <a href="/admin/" class="brand-lockup" aria-label="استوک‌لند">
              <span class="brand-mark">
              <svg width="44" height="44" viewBox="0 0 120 120" fill="none" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">
                <!-- گلو پس‌زمینه -->
                <ellipse cx="60" cy="64" rx="42" ry="32" fill="rgba(0,215,255,0.13)" filter="url(#glow)"/>
                <defs>
                  <filter id="glow" x="-50%" y="-50%" width="200%" height="200%">
                    <feGaussianBlur stdDeviation="8" result="blur"/>
                    <feMerge><feMergeNode in="blur"/><feMergeNode in="SourceGraphic"/></feMerge>
                  </filter>
                  <!-- گرادیان نقره‌ای S -->
                  <linearGradient id="sGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#F0F4F8"/>
                    <stop offset="35%" stop-color="#FFFFFF"/>
                    <stop offset="65%" stop-color="#B8C4D0"/>
                    <stop offset="100%" stop-color="#7A8899"/>
                  </linearGradient>
                  <!-- گرادیان نقره‌ای L -->
                  <linearGradient id="lGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#D0D8E4"/>
                    <stop offset="40%" stop-color="#F8FAFC"/>
                    <stop offset="100%" stop-color="#8896A8"/>
                  </linearGradient>
                  <!-- گرادیان فیروزه‌ای -->
                  <linearGradient id="glowGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" stop-color="#00D7FF" stop-opacity="0.6"/>
                    <stop offset="100%" stop-color="#0066AA" stop-opacity="0.2"/>
                  </linearGradient>
                </defs>
                <!-- حرف S -->
                <path d="M28 30 C28 24 34 20 42 20 L66 20 L60 29 L40 29 C37 29 35 31 35 33 C35 35 37 37 42 38 L54 41 C63 43 70 48 70 56 C70 64 63 70 54 70 L28 70 L34 61 L56 61 C60 61 63 59 63 57 C63 55 61 53 56 52 L44 49 C35 47 28 42 28 33 Z" fill="url(#sGrad)"/>
                <!-- حرف L -->
                <path d="M72 20 L82 20 L82 86 L100 86 L94 100 L72 100 Z" fill="url(#lGrad)"/>
                <!-- خط تقاطع نورانی -->
                <path d="M58 38 L78 68" stroke="url(#glowGrad)" stroke-width="2.5" stroke-linecap="round" opacity="0.7"/>
              </svg>
              </span>
              <div class="brand-copy">
                <div class="brand-name">STOCK<span>LAND</span></div>
                <div class="brand-subtitle">مدیریت فروشگاه</div>
              </div>
            </a>
            <button class="icon-button sidebar-close" onclick="toggleSidebar()" aria-label="بستن منو"><i data-lucide="x"></i></button>
          </div>
          <div class="nav-caption">منو اصلی</div>
          <nav class="sidebar-nav">
            {nav_item("/admin/", "layout-dashboard", "داشبورد")}
            <div class="nav-divider"><span>فروشگاه</span></div>
            {nav_item("/admin/categories", "tag", "دسته‌بندی‌ها", "products")}
            {nav_item("/admin/products", "package", "محصولات", "products")}
            {nav_item("/admin/feed", "layers", "موجودی", "feed")}
            <div class="nav-divider"><span>فروش</span></div>
            {nav_item("/admin/orders", "shopping-bag", "سفارش‌ها", "orders")}
            {nav_item("/admin/wallets", "wallet", "کیف‌پول", "wallets")}
            <div class="nav-divider"><span>کاربران</span></div>
            {nav_item("/admin/partners", "handshake", "همکاران", "partners", pending_partners)}
            {nav_item("/admin/tickets", "message-square", "تیکت‌ها", "tickets", open_tickets)}
            {nav_item("/admin/broadcast", "megaphone", "پیام‌رسانی", "broadcast")}
            <div class="nav-divider"><span>سیستم</span></div>
            {nav_item("/admin/settings", "settings", "تنظیمات", "settings")}
            {nav_item("/admin/database", "database", "دیتابیس", "database")}
            {nav_item("/admin/admins", "shield-check", "ادمین‌ها", "admins")}
          </nav>
          <div class="sidebar-footer">
            <div class="sidebar-status"><span class="status-dot"></span><div><strong>سامانه فعال</strong><small>همه سرویس‌ها پایدارند</small></div></div>
            <a href="/admin/logout" class="sidebar-logout"><i data-lucide="log-out"></i><span>خروج از پنل</span></a>
          </div>
        </aside>
        <div id="overlay" class="overlay" onclick="toggleSidebar()"></div>"""

    topbar = ""
    if admin_info:
        admin_label = "مدیر ارشد" if is_super else f"مدیر #{e(admin_info[0])}"
        topbar = f"""
        <header class="topbar">
          <div class="topbar-context">
            <button class="icon-button topbar-menu" onclick="toggleSidebar()" aria-label="بازکردن منو"><i data-lucide="menu"></i></button>
            <div><span class="topbar-eyebrow">STOCKLAND ADMIN</span><h1 class="topbar-title">{e(title)}</h1></div>
          </div>
          <div class="global-search-wrap">
            <i data-lucide="search"></i>
            <input id="globalSearch" class="global-search" type="search" placeholder="جست‌وجو در پنل..." autocomplete="off" aria-label="جست‌وجوی سراسری">
            <kbd>⌘ K</kbd>
            <div id="searchResults" class="search-results"></div>
          </div>
          <div class="topbar-actions">
            <button id="themeToggle" class="icon-button" aria-label="تغییر حالت نمایش"><i data-lucide="moon"></i></button>
            <a class="icon-button notification-button" href="/admin/tickets" aria-label="اعلان‌ها"><i data-lucide="bell"></i><span id="ticket-badge-top" class="notification-count {'hidden' if open_tickets == 0 else ''}">{open_tickets}</span></a>
            <a class="icon-button notification-button" href="/admin/partners" aria-label="همکاران" style="position:relative"><i data-lucide="handshake"></i><span id="partner-badge-top" class="notification-count {'hidden' if pending_partners == 0 else ''}" style="background:#F59E0B">{pending_partners}</span></a>
            <div class="profile-menu">
              <button class="profile-trigger" onclick="toggleProfile()" aria-expanded="false"><span class="profile-avatar"><i data-lucide="user-round"></i></span><span class="profile-copy"><strong>{admin_label}</strong><small>مدیریت فروشگاه</small></span><i data-lucide="chevron-down" class="profile-chevron"></i></button>
              <div id="profileDropdown" class="profile-dropdown"><a href="/admin/settings"><i data-lucide="settings"></i>تنظیمات حساب</a><a href="/admin/logout" class="danger-link"><i data-lucide="log-out"></i>خروج</a></div>
            </div>
          </div>
        </header>"""

    css_vars = ";".join(f"--{k.replace('_','-')}:{v}" for k,v in theme.items())

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{e(title)} — استوک لند</title>
  <link href="https://fonts.googleapis.com/css2?family=Vazirmatn:wght@300;400;500;600;700;800&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script src="https://unpkg.com/lucide@0.468.0/dist/umd/lucide.min.js"></script>
  <style>
    :root {{ {css_vars} }}
    :root {{ --success:#22C55E; --warning:#F59E0B; --danger:#EF4444; --sidebar-secondary:#0B1320; --card-shadow:0 12px 40px rgba(15,23,42,.06); }}
    *, *::before, *::after {{ box-sizing:border-box; font-family:'Vazirmatn',Tahoma,sans-serif !important; }}
    html {{ background:var(--page-bg); scroll-behavior:smooth; }}
    body {{ margin:0; background:var(--page-bg); color:var(--text-main); min-height:100vh; -webkit-font-smoothing:antialiased; }}
    button, input, select, textarea {{ font:inherit; }}
    a {{ color:inherit; }}
    svg {{ flex:0 0 auto; }}
    .hidden {{ display:none !important; }}

    .sidebar {{
      position:fixed; inset:0 0 0 auto; width:280px; height:100vh; z-index:200;
      display:flex; flex-direction:column; color:var(--sidebar-text); overflow:hidden;
      background:linear-gradient(180deg,rgba(11,19,32,.94),rgba(5,7,10,.98) 40%),var(--sidebar-bg);
      border-left:1px solid rgba(255,255,255,.06); box-shadow:-18px 0 50px rgba(2,6,23,.12);
      transition:transform 220ms cubic-bezier(.2,.8,.2,1); backdrop-filter:blur(24px);
    }}
    .sidebar::before {{ content:""; position:absolute; top:-100px; right:-90px; width:280px; height:280px; border-radius:50%; background:rgba(0,215,255,.08); filter:blur(70px); pointer-events:none; }}
    .sidebar-header {{ min-height:104px; display:flex; align-items:center; padding:24px 22px 20px; border-bottom:1px solid rgba(255,255,255,.07); position:relative; }}
    .brand-lockup {{ display:flex; align-items:center; gap:13px; text-decoration:none; position:relative; min-width:0; }}
    .brand-mark {{ width:50px; height:50px; display:grid; place-items:center; border:1px solid rgba(255,255,255,.10); border-radius:17px; background:rgba(255,255,255,.055); box-shadow:0 0 28px rgba(0,215,255,.16),inset 0 1px rgba(255,255,255,.1); }}
    .brand-name {{ font:800 16px/1.1 Inter,Vazirmatn,sans-serif !important; color:#fff; letter-spacing:1.7px; }}
    .brand-name span {{ color:var(--primary); }}
    .brand-subtitle {{ color:#7f8b9e; font-size:11px; margin-top:5px; }}
    .sidebar-close {{ display:none !important; margin-right:auto; color:#9aa7b8 !important; background:rgba(255,255,255,.06) !important; }}
    .nav-caption {{ color:#536075; font-size:10px; font-weight:700; letter-spacing:.08em; padding:20px 26px 8px; }}
    .nav-divider {{ display:flex; align-items:center; gap:8px; padding:14px 16px 5px; }}
    .nav-divider span {{ color:#2D3A4A; font-size:9.5px; font-weight:700; letter-spacing:1.5px; text-transform:uppercase; white-space:nowrap; }}
    .nav-divider::after {{ content:""; flex:1; height:1px; background:rgba(255,255,255,.05); }}
    .sidebar-nav {{ flex:1; overflow-y:auto; padding:0 12px 18px; display:flex; flex-direction:column; gap:4px; scrollbar-width:thin; scrollbar-color:#263244 transparent; }}
    .nav-item {{
      position:relative; display:flex; align-items:center; gap:12px; min-height:44px; padding:0 14px;
      border-radius:13px; text-decoration:none; color:var(--sidebar-text); font-size:13px; font-weight:500;
      transition:background 200ms,color 200ms,transform 200ms,box-shadow 200ms; overflow:hidden;
    }}
    .nav-item::after {{ content:""; position:absolute; right:0; top:8px; bottom:8px; width:4px; border-radius:4px 0 0 4px; background:var(--primary); transform:scaleY(0); transition:transform 200ms; }}
    .nav-item:hover {{ background:rgba(255,255,255,.05); color:#fff; transform:translateX(-2px); }}
    .nav-item.active {{ background:rgba(0,215,255,.08); color:#eafbff; box-shadow:inset 0 0 0 1px rgba(0,215,255,.06),0 8px 28px rgba(0,215,255,.06); }}
    .nav-item.active::after {{ transform:scaleY(1); }}
    .nav-item.active .nav-icon {{ color:var(--primary); filter:drop-shadow(0 0 7px rgba(0,215,255,.45)); }}
    .nav-icon {{ width:19px; height:19px; stroke-width:1.8; }}
    .nav-badge {{ margin-right:auto; min-width:21px; height:21px; padding:0 6px; display:grid; place-items:center; border-radius:999px; background:rgba(0,215,255,.13); color:#66e7ff; border:1px solid rgba(0,215,255,.16); font-size:10px; font-weight:700; }}
    .sidebar-footer {{ border-top:1px solid rgba(255,255,255,.07); padding:14px 16px 16px; }}
    .sidebar-status {{ display:flex; align-items:center; gap:10px; color:#d6dde8; padding:5px 6px 14px; }}
    .sidebar-status strong,.sidebar-status small {{ display:block; }}
    .sidebar-status strong {{ font-size:11px; font-weight:600; }}
    .sidebar-status small {{ font-size:9px; color:#667286; margin-top:2px; }}
    .status-dot {{ width:8px; height:8px; border-radius:50%; background:var(--success); box-shadow:0 0 0 4px rgba(34,197,94,.09),0 0 12px rgba(34,197,94,.55); }}
    .sidebar-logout {{ display:flex; align-items:center; gap:10px; min-height:42px; padding:0 12px; border-radius:12px; color:#f29a9a; text-decoration:none; font-size:12px; transition:200ms; }}
    .sidebar-logout svg {{ width:17px; }} .sidebar-logout:hover {{ color:#fff; background:rgba(239,68,68,.1); }}
    .overlay {{ display:none; position:fixed; inset:0; background:rgba(2,6,23,.54); backdrop-filter:blur(4px); z-index:199; }}

    .topbar {{
      position:fixed; top:0; right:280px; left:0; height:72px; z-index:100; padding:0 28px;
      display:grid; grid-template-columns:1fr minmax(300px,520px) 1fr; align-items:center; gap:24px;
      background:rgba(255,255,255,.88); border-bottom:1px solid rgba(229,231,235,.86); backdrop-filter:blur(20px) saturate(150%);
    }}
    .topbar-context {{ display:flex; align-items:center; gap:12px; min-width:0; }}
    .topbar-eyebrow {{ display:block; color:#9ca3af; font-size:8px; font-weight:800; letter-spacing:.16em; direction:ltr; text-align:right; }}
    .topbar-title {{ margin:2px 0 0; font-size:16px; line-height:1.2; font-weight:750; color:var(--text-main); white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
    .topbar-menu {{ display:none !important; }}
    .global-search-wrap {{ position:relative; display:flex; align-items:center; direction:rtl; }}
    .global-search-wrap>svg {{ position:absolute; right:15px; width:18px; color:#9ca3af; pointer-events:none; }}
    .global-search {{ width:100%; height:42px; padding:0 45px 0 54px !important; border-radius:14px !important; border:1px solid #e6e8ec !important; background:#f8f9fb !important; box-shadow:inset 0 1px 2px rgba(15,23,42,.02); }}
    .global-search:focus {{ background:#fff !important; }}
    .global-search-wrap kbd {{ position:absolute; left:10px; direction:ltr; padding:3px 7px; border:1px solid #e5e7eb; border-bottom-color:#d1d5db; border-radius:7px; background:#fff; color:#9ca3af; font:500 10px/1.3 Inter,sans-serif !important; }}
    .search-results {{ display:none; position:absolute; top:50px; inset-inline:0; padding:7px; border-radius:16px; border:1px solid var(--border); background:var(--card-bg); box-shadow:0 22px 60px rgba(15,23,42,.14); }}
    .search-results.open {{ display:block; }}
    .search-results a {{ display:flex; align-items:center; justify-content:space-between; padding:10px 12px; border-radius:10px; text-decoration:none; font-size:12px; }}
    .search-results a:hover {{ background:var(--page-bg); color:#0891b2; }}
    .search-results small {{ color:var(--text-muted); direction:ltr; }}
    .topbar-actions {{ display:flex; align-items:center; justify-content:flex-end; gap:8px; min-width:0; }}
    .icon-button {{ width:38px; height:38px; display:grid; place-items:center; border:1px solid var(--border); border-radius:12px; background:var(--card-bg); color:#64748b; cursor:pointer; transition:200ms; text-decoration:none; }}
    .icon-button:hover {{ color:var(--text-main); border-color:#cad0d9; transform:translateY(-1px); box-shadow:0 7px 18px rgba(15,23,42,.06); }}
    .icon-button svg {{ width:18px; height:18px; stroke-width:1.8; }}
    .notification-button {{ position:relative; }}
    .notification-count {{ position:absolute; top:-5px; left:-5px; min-width:18px; height:18px; padding:0 4px; display:grid; place-items:center; border:2px solid #fff; border-radius:999px; background:var(--danger); color:#fff; font:700 9px/1 Inter,sans-serif !important; }}
    .profile-menu {{ position:relative; }}
    .profile-trigger {{ height:44px; display:flex; align-items:center; gap:10px; padding:3px 5px 3px 10px; border:0; border-radius:14px; background:transparent; cursor:pointer; color:var(--text-main); transition:200ms; }}
    .profile-trigger:hover {{ background:#f5f6f8; }}
    .profile-avatar {{ width:36px; height:36px; display:grid; place-items:center; border-radius:11px; background:linear-gradient(145deg,#101827,#0b3040); color:#55e5ff; box-shadow:inset 0 0 0 1px rgba(255,255,255,.09); }}
    .profile-avatar svg {{ width:18px; }}
    .profile-copy {{ text-align:right; line-height:1.2; }} .profile-copy strong,.profile-copy small {{ display:block; white-space:nowrap; }}
    .profile-copy strong {{ font-size:11px; }} .profile-copy small {{ font-size:9px; color:var(--text-muted); margin-top:3px; }}
    .profile-chevron {{ width:14px; color:#9ca3af; }}
    .profile-dropdown {{ display:none; position:absolute; left:0; top:52px; min-width:190px; padding:7px; border:1px solid var(--border); border-radius:15px; background:var(--card-bg); box-shadow:0 20px 60px rgba(15,23,42,.14); }}
    .profile-dropdown.open {{ display:block; }}
    .profile-dropdown a {{ display:flex; align-items:center; gap:9px; padding:10px; border-radius:9px; font-size:12px; text-decoration:none; }}
    .profile-dropdown a:hover {{ background:var(--page-bg); }} .profile-dropdown svg {{ width:16px; }} .profile-dropdown .danger-link {{ color:var(--danger); }}

    .main-wrap.with-sidebar {{ margin-right:280px; padding-top:72px; min-height:100vh; width:calc(100% - 280px); }}
    .main-wrap.auth-layout {{ min-height:100vh; width:100%; }}
    .main-content {{ width:100%; max-width:1600px; margin:0 auto; padding:30px 32px 48px; }}
    .auth-layout .main-content {{ max-width:none; padding:0; }}
    .card {{ background:var(--card-bg); border:1px solid rgba(229,231,235,.82); border-radius:24px; box-shadow:var(--card-shadow); transition:transform 200ms ease,box-shadow 200ms ease,border-color 200ms ease; }}
    .card:hover {{ transform:translateY(-2px); box-shadow:0 18px 48px rgba(15,23,42,.085); border-color:rgba(203,213,225,.9); }}
    .flash-msg {{ padding:13px 16px; border-radius:14px; margin-bottom:20px; font-size:13px; display:flex; align-items:center; gap:9px; box-shadow:0 8px 25px rgba(15,23,42,.04); }}
    .flash-msg svg {{ width:18px; }} .flash-ok {{ background:#f0fdf4; border:1px solid #bbf7d0; color:#166534; }} .flash-err {{ background:#fef2f2; border:1px solid #fecaca; color:#991b1b; }}
    .btn {{ display:inline-flex; align-items:center; justify-content:center; gap:7px; min-height:40px; padding:9px 18px; border-radius:12px; font-size:12.5px; font-weight:650; border:1px solid transparent; cursor:pointer; transition:200ms; text-decoration:none; }}
    .btn:hover {{ transform:translateY(-1px); filter:saturate(1.08); }} .btn svg {{ width:16px; height:16px; }}
    .btn-primary {{ background:#07131c; color:#fff; box-shadow:0 8px 18px rgba(2,132,199,.1); }}
    .btn-sm {{ min-height:34px; padding:6px 12px; font-size:11.5px; border-radius:10px; }}
    .btn-slate {{ background:#f8fafc; color:#475569; border-color:var(--border); }} .btn-green {{ background:#ecfdf3; color:#15803d; border-color:#bbf7d0; }} .btn-red {{ background:#fff1f2; color:#be123c; border-color:#fecdd3; }} .btn-indigo {{ background:#ecfeff; color:#0e7490; border-color:#a5f3fc; }}
    input, textarea, select {{
      width:100%; min-height:44px; border:1px solid var(--border); border-radius:14px; padding:10px 13px;
      font-size:13px; background:var(--card-bg); color:var(--text-main); outline:none; transition:border 180ms,box-shadow 180ms,background 180ms;
    }}
    textarea {{ min-height:110px; resize:vertical; }}
    input::placeholder,textarea::placeholder {{ color:#a6adba; }}
    input:focus, textarea:focus, select:focus {{ border-color:var(--primary); box-shadow:0 0 0 4px rgba(0,215,255,.11); }}
    label {{ font-size:12px; color:#4b5563; display:block; margin-bottom:7px; font-weight:600; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; }}
    thead {{ position:sticky; top:72px; z-index:2; }}
    th {{ padding:13px 16px; font-size:11px; color:var(--text-muted); font-weight:700; border-bottom:1px solid var(--border); text-align:right; background:#fafbfc; white-space:nowrap; }}
    td {{ padding:14px 16px; font-size:13px; border-bottom:1px solid #eef0f3; transition:background 160ms; }}
    tbody tr:last-child td {{ border-bottom:0; }} tbody tr:hover td {{ background:#f8fbfc; }}
    .legacy-lucide {{ width:1em; height:1em; display:inline-block; vertical-align:-.16em; margin:0 .12em; stroke-width:1.9; }}

    body.dark-mode {{ --page-bg:#080C12; --card-bg:#101720; --text-main:#F1F5F9; --text-muted:#94A3B8; --border:#273244; --card-shadow:0 12px 40px rgba(0,0,0,.22); background:#080c12; }}
    body.dark-mode .topbar {{ background:rgba(10,15,22,.88); border-bottom-color:#202b39; }}
    body.dark-mode .global-search,body.dark-mode .global-search-wrap kbd {{ background:#111923 !important; border-color:#273244 !important; color:#dbe4ef; }}
    body.dark-mode .profile-trigger:hover,body.dark-mode .profile-dropdown a:hover,body.dark-mode .search-results a:hover {{ background:#18212d; }}
    body.dark-mode th {{ background:#111923; }} body.dark-mode tbody tr:hover td {{ background:#121c27; }} body.dark-mode .notification-count {{ border-color:#101720; }}

    @media (max-width:1100px) {{ .topbar {{ grid-template-columns:auto minmax(240px,1fr) auto; padding:0 20px; gap:16px; }} .profile-copy,.profile-chevron {{ display:none; }} }}
    @media (max-width:820px) {{
      .sidebar {{ transform: translateX(100%); }}
      .sidebar.open {{ transform: translateX(0); }}
      .sidebar-close {{ display:grid !important; }}
      .overlay.open {{ display:block; }}
      .topbar {{ right:0; }}
      .topbar-menu {{ display:grid !important; }}
      .main-wrap.with-sidebar {{ margin-right:0; width:100%; }}
      .main-content {{ padding:24px 18px 36px; }}
    }}
    @media (max-width:640px) {{
      .topbar {{ grid-template-columns:1fr auto; height:64px; padding:0 14px; }}
      .global-search-wrap {{ display:none; }} .topbar-eyebrow {{ display:none; }} .topbar-actions {{ gap:5px; }} .profile-trigger {{ padding:3px; }}
      .main-wrap.with-sidebar {{ padding-top:64px; }} .main-content {{ padding:20px 12px 30px; }} .sidebar {{ width:min(88vw,280px); }}
      .card {{ border-radius:20px; }} thead {{ top:64px; }} th,td {{ padding-inline:12px; }}
    }}
  </style>
</head>
<body>
{sidebar}
{topbar}
<div class="main-wrap {'with-sidebar' if admin_info else 'auth-layout'}">
  <div class="main-content">
    {flash_html}
    {body}
  </div>
</div>

<script>
(function(){{
  function renderIcons(){{ if(window.lucide) lucide.createIcons({{attrs:{{'aria-hidden':'true'}}}}); }}

  // Active nav
  var path = location.pathname;
  document.querySelectorAll('.nav-item[data-href]').forEach(function(el){{
    if(el.dataset.href === path || (path !== '/admin/' && el.dataset.href !== '/admin/' && path.startsWith(el.dataset.href))){{
      el.classList.add('active');
    }}
  }});

  // Toggle sidebar
  window.toggleSidebar = function(){{
    document.getElementById('sidebar')?.classList.toggle('open');
    document.getElementById('overlay')?.classList.toggle('open');
  }};

  window.toggleProfile = function(){{ document.getElementById('profileDropdown')?.classList.toggle('open'); }};
  document.addEventListener('click',function(ev){{
    if(!ev.target.closest('.profile-menu')) document.getElementById('profileDropdown')?.classList.remove('open');
  }});

  var themeToggle=document.getElementById('themeToggle');
  function setTheme(dark){{ document.body.classList.toggle('dark-mode',dark); localStorage.setItem('sl-theme',dark?'dark':'light'); if(themeToggle) themeToggle.innerHTML='<i data-lucide="'+(dark?'sun':'moon')+'"></i>'; renderIcons(); }}
  if(themeToggle){{ setTheme(localStorage.getItem('sl-theme')==='dark'); themeToggle.addEventListener('click',function(){{ setTheme(!document.body.classList.contains('dark-mode')); }}); }}

  var search=document.getElementById('globalSearch'),results=document.getElementById('searchResults');
  function searchPanel(){{
    if(!search||!results)return; var q=search.value.trim().toLowerCase(); results.innerHTML='';
    if(!q){{results.classList.remove('open');return;}}
    Array.from(document.querySelectorAll('.sidebar-nav .nav-item')).filter(function(a){{return a.textContent.trim().toLowerCase().includes(q);}}).slice(0,7).forEach(function(a){{
      var item=document.createElement('a'); item.href=a.href; item.innerHTML='<span>'+a.textContent.trim()+'</span><small>'+new URL(a.href).pathname+'</small>'; results.appendChild(item);
    }});
    if(!results.children.length) results.innerHTML='<span style="display:block;padding:12px;color:var(--text-muted);font-size:12px">نتیجه‌ای پیدا نشد</span>';
    results.classList.add('open');
  }}
  search?.addEventListener('input',searchPanel);
  document.addEventListener('keydown',function(ev){{if((ev.metaKey||ev.ctrlKey)&&ev.key.toLowerCase()==='k'){{ev.preventDefault();search?.focus();}}if(ev.key==='Escape')results?.classList.remove('open');}});

  // Convert legacy decorative emoji in rendered UI to Lucide without touching form data or scripts.
  var emojiIcons={{'✅':'circle-check','❌':'circle-x','⚠️':'triangle-alert','⚠':'triangle-alert','📊':'bar-chart-2','🛒':'shopping-bag','🛍':'shopping-bag','📦':'package','🗂':'folders','🗃':'archive','💼':'briefcase','🧾':'receipt-text','💰':'wallet','💳':'credit-card','👥':'users','🤝':'handshake','🎫':'ticket','📢':'megaphone','⚙️':'settings','⚙':'settings','👤':'user-round','💾':'hard-drive-download','📈':'trending-up','📱':'smartphone','🔑':'key-round','🔴':'circle-alert','🟡':'circle-dot','🟢':'circle-check','🔄':'refresh-cw','👨‍💻':'user-round','🧩':'blocks','←':'arrow-left','↩':'log-out','☰':'menu','✕':'x','▲':'trending-up','▼':'trending-down'}};
  var emojiRe=/(✅|❌|⚠️|⚠|📊|🛒|🛍|📦|🗂|🗃|💼|🧾|💰|💳|👥|🤝|🎫|📢|⚙️|⚙|👤|💾|📈|📱|🔑|🔴|🟡|🟢|🔄|👨‍💻|🧩|←|↩|☰|✕|▲|▼)/g;
  var walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT); var nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode);
  nodes.forEach(function(node){{ var parent=node.parentElement;if(!parent||parent.closest('script,style,input,textarea,select,option,[data-no-icon]')||!emojiRe.test(node.nodeValue)){{emojiRe.lastIndex=0;return;}} emojiRe.lastIndex=0; var frag=document.createDocumentFragment(),last=0,m;while((m=emojiRe.exec(node.nodeValue))){{frag.append(document.createTextNode(node.nodeValue.slice(last,m.index)));var i=document.createElement('i');i.setAttribute('data-lucide',emojiIcons[m[0]]);i.className='legacy-lucide';frag.append(i);last=m.index+m[0].length;}}frag.append(document.createTextNode(node.nodeValue.slice(last)));node.replaceWith(frag);}});

  {"" if not admin_info else """
  // Idle logout
  var IDLE = 300000;
  var timer;
  function reset(){ clearTimeout(timer); timer = setTimeout(function(){ location.href='/admin/login?flash='+encodeURIComponent('به دلیل عدم فعالیت خارج شدید'); }, IDLE); }
  ['mousemove','keydown','click','scroll','touchstart'].forEach(function(ev){ document.addEventListener(ev,reset,true); });
  reset();

  // Badge polling
  function updateBadge(id, count){
    var el = document.getElementById(id);
    if(!el) return;
    if(count>0){ el.textContent=count; el.classList.remove('hidden'); }
    else el.classList.add('hidden');
  }
  setInterval(function(){
    fetch('/admin/badges.json').then(function(r){ return r.json(); }).then(function(d){
      updateBadge('ticket-badge-top', d.tickets||0);
      updateBadge('partner-badge-top', d.partners||0);
    }).catch(function(){});
  }, 15000);
  """}
  renderIcons();
}})();
</script>
</body>
</html>""")

def _card(title, value, sub="", color="indigo"):
    colors = {
        "indigo": "#4f46e5","green":"#16a34a","red":"#dc2626",
        "amber":"#d97706","blue":"#2563eb","slate":"#475569",
    }
    fg = colors.get(color, "#4f46e5")
    return (
        f'<div class="card p-5">'
        f'<div class="text-xs font-semibold mb-1" style="color:{fg}">{e(title)}</div>'
        f'<div class="text-2xl font-bold" style="color:var(--text-main)">{e(str(value))}</div>'
        f'{"<div style=\"font-size:12px;color:var(--text-muted);margin-top:3px\">"+e(sub)+"</div>" if sub else ""}'
        f'</div>'
    )

def _btn(text, href="", color="indigo", small=False, danger=False):
    cls = "btn btn-sm " if small else "btn "
    if danger or color == "red":   cls += "btn-red"
    elif color == "green":         cls += "btn-green"
    elif color == "slate":         cls += "btn-slate"
    else:                          cls += "btn-indigo"
    if href:
        return f'<a href="{e(href)}" class="{cls}">{e(text)}</a>'
    return f'<button type="submit" class="{cls}">{e(text)}</button>'

def _input(name, placeholder="", value="", type_="text", required=False):
    req = "required" if required else ""
    return f'<input type="{type_}" name="{name}" value="{e(value)}" placeholder="{e(placeholder)}" {req}>'

def _textarea(name, placeholder="", value="", rows=4):
    return f'<textarea name="{name}" rows="{rows}" placeholder="{e(placeholder)}">{e(value)}</textarea>'

# ─────────────────────────── Login / Logout ────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, err: str = "", flash: str = ""):
    adm = _get_admin(request)
    if adm:
        return _redir("/admin/")

    err_html = ""
    if err == "1":
        err_html = '<div class="mb-4 text-red-600 text-sm text-center bg-red-50 p-2 rounded-lg">❌ نام کاربری یا رمز اشتباه است</div>'
    if flash:
        err_html += f'<div class="mb-4 text-amber-700 text-sm text-center bg-amber-50 p-2 rounded-lg">⏱ {e(flash)}</div>'

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
        resp.set_cookie("adm", _make_session("super"), max_age=300, httponly=True, samesite="lax")
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
            resp.set_cookie("adm", _make_session(str(row["id"])), max_age=300, httponly=True, samesite="lax")
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
        today = datetime.utcnow().date().isoformat()
        yesterday = (datetime.utcnow().date() - timedelta(days=1)).isoformat()

        today_o   = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at LIKE ?;", (today+"%",)).fetchone()
        yest_o    = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at LIKE ?;", (yesterday+"%",)).fetchone()
        total_o   = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders;").fetchone()
        feed_avail = conn.execute("SELECT COUNT(*) FROM product_feed WHERE delivered=0;").fetchone()[0]
        pending   = conn.execute("SELECT COUNT(*) FROM pending_deliveries WHERE status='pending';").fetchone()[0]
        partners_pend = conn.execute("SELECT COUNT(*) FROM partners WHERE status='pending';").fetchone()[0]
        open_tix  = _open_ticket_count()
        wallets   = conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM wallets;").fetchone()
        products_cnt = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1;").fetchone()[0]

        # نمودار ۳۰ روز اخیر
        chart_data = conn.execute("""
            SELECT substr(created_at,1,10) as day, COALESCE(SUM(price),0) as total
            FROM orders WHERE created_at >= date('now','-30 days')
            GROUP BY day ORDER BY day ASC;
        """).fetchall()

        # محصولات کم موجودی
        low_stock = conn.execute("""
            SELECT p.id, p.title, COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as avail
            FROM products p LEFT JOIN product_feed pf ON pf.product_id=p.id
            WHERE p.is_active=1 GROUP BY p.id HAVING avail<=5 ORDER BY avail ASC LIMIT 5;
        """).fetchall()

        # سفارش‌های اخیر
        recent = conn.execute("""
            SELECT id, user_id, title, price, created_at, COALESCE(status,'active') as status
            FROM orders ORDER BY id DESC LIMIT 8;
        """).fetchall()

        # آخرین بکاپ خودکار
        import glob as _g, os as _o
        auto_backups = sorted(_g.glob("/tmp/stockland_backups/auto_*.sqlite"), reverse=True)
        last_backup = _o.path.basename(auto_backups[0]).replace("auto_","").replace(".sqlite","") if auto_backups else None

    finally:
        conn.close()

    # محاسبه درصد تغییر نسبت به دیروز (فقط برای نمایش KPI)
    rev_change = 0
    if yest_o[1] > 0:
        rev_change = round(((today_o[1] - yest_o[1]) / yest_o[1]) * 100, 1)
    cnt_change = today_o[0] - yest_o[0]

    def pct_badge(value, suffix="%"):
        if value > 0:
            return f'<span class="trend trend-up"><i data-lucide="trending-up"></i>{value}{suffix}</span>'
        if value < 0:
            return f'<span class="trend trend-down"><i data-lucide="trending-down"></i>{abs(value)}{suffix}</span>'
        return '<span class="trend trend-flat"><i data-lucide="minus"></i>بدون تغییر</span>'

    def status_badge(status):
        styles = {
            "active":   ("success", "ارسال شد"),
            "returned": ("danger", "برگشتی"),
            "pending":  ("warning", "در انتظار"),
        }
        tone, label = styles.get(status, ("neutral", status))
        return f'<span class="status-badge status-{tone}"><span></span>{e(label)}</span>'

    chart_labels = json.dumps([r["day"][5:] for r in chart_data], ensure_ascii=False)
    chart_values = json.dumps([int(r["total"]) for r in chart_data])

    low_rows = "".join(f"""
    <a href="/admin/feed/{r['id']}" class="compact-row">
      <span class="row-icon {'danger' if r['avail'] == 0 else 'warning'}"><i data-lucide="package-minus"></i></span>
      <span class="row-copy"><strong>{e(r['title'])}</strong><small>نیازمند تأمین موجودی</small></span>
      <span class="stock-count {'out' if r['avail'] == 0 else ''}">{r['avail']} عدد</span>
    </a>""" for r in low_stock)

    recent_rows = "".join(f"""
    <tr>
      <td><a class="order-id" href="/admin/orders/{o['id']}/edit">#{o['id']}</a></td>
      <td><div class="table-product"><span><i data-lucide="package"></i></span><strong>{e(o['title'][:34])}</strong></div></td>
      <td><span class="muted-cell">{o['user_id']}</span></td>
      <td><strong class="money-cell">{int(o['price']):,}</strong><small class="currency">تومان</small></td>
      <td>{status_badge(o['status'] or 'active')}</td>
      <td><a class="table-action" href="/admin/orders/{o['id']}/edit" aria-label="مشاهده سفارش"><i data-lucide="arrow-up-left"></i></a></td>
    </tr>""" for o in recent)

    # مشتق‌شده از همان سفارش‌های اخیر؛ بدون query یا تغییر منطق داده.
    product_summary = {}
    for order in recent:
        product_title = str(order["title"] or "بدون عنوان")
        if product_title not in product_summary:
            product_summary[product_title] = {"count": 0, "revenue": 0}
        product_summary[product_title]["count"] += 1
        product_summary[product_title]["revenue"] += int(order["price"] or 0)

    top_product_rows = "".join(f"""
      <div class="rank-row"><span class="rank-number">{index}</span><span class="rank-copy"><strong>{e(name[:30])}</strong><small>{data['count']} سفارش اخیر</small></span><strong class="rank-value">{data['revenue']:,}</strong></div>
    """ for index, (name, data) in enumerate(sorted(product_summary.items(), key=lambda item: (item[1]["count"], item[1]["revenue"]), reverse=True)[:5], 1))

    activity_rows = "".join(f"""
      <div class="activity-row"><span class="activity-icon"><i data-lucide="shopping-bag"></i></span><span><strong>سفارش #{o['id']} ثبت شد</strong><small>{e(o['title'][:28])} · {e(str(o['created_at'])[:16])}</small></span></div>
    """ for o in recent[:5])

    def command_item(icon, label, value, meta, tone="cyan", href="#"):
        return f"""
        <a href="{href}" class="command-item command-{tone}">
          <span class="command-icon"><i data-lucide="{icon}"></i></span>
          <span class="command-copy"><small>{label}</small><strong>{value}</strong><em>{meta}</em></span>
          <i data-lucide="arrow-up-left" class="command-arrow"></i>
        </a>"""

    command_items = "".join([
        command_item("clock-3", "سفارش‌های معلق", pending, "نیازمند پیگیری", "warning" if pending else "success", "/admin/orders"),
        command_item("package-search", "کمبود موجودی", len(low_stock), "محصول در آستانه اتمام", "danger" if low_stock else "success", "/admin/feed"),
        command_item("message-square", "تیکت‌های باز", open_tix, "در انتظار پاسخ مدیر", "danger" if open_tix else "success", "/admin/tickets"),
        command_item("handshake", "همکاران معلق", partners_pend, "درخواست بررسی‌نشده", "warning" if partners_pend else "success", "/admin/partners"),
        command_item("database-backup", "آخرین بکاپ", "ثبت شده" if last_backup else "ناموجود", last_backup or "هنوز بکاپی ثبت نشده", "success" if last_backup else "warning", "/admin/database"),
        command_item("activity", "سلامت سیستم", "پایدار", "سرویس پنل در دسترس است", "success", "/admin/database"),
        command_item("bot", "وضعیت ربات", "فعال", "آماده پاسخ‌گویی", "cyan", "/admin/broadcast"),
    ])

    tasks = "".join([
        f'<a href="/admin/feed" class="task-row"><span class="task-status danger"><i data-lucide="package-minus"></i></span><span><strong>تأمین موجودی محصولات</strong><small>{len(low_stock)} محصول نیازمند بررسی</small></span><i data-lucide="chevron-left"></i></a>',
        f'<a href="/admin/tickets" class="task-row"><span class="task-status warning"><i data-lucide="message-circle"></i></span><span><strong>پاسخ به تیکت‌ها</strong><small>{open_tix} تیکت منتظر پاسخ</small></span><i data-lucide="chevron-left"></i></a>',
        f'<a href="/admin/orders" class="task-row"><span class="task-status cyan"><i data-lucide="truck"></i></span><span><strong>تحویل‌های معلق</strong><small>{pending} سفارش در صف ارسال</small></span><i data-lucide="chevron-left"></i></a>',
        '<a href="/admin/database" class="task-row"><span class="task-status success"><i data-lucide="server"></i></span><span><strong>وضعیت سرور</strong><small>سرویس در دسترس است</small></span><i data-lucide="chevron-left"></i></a>',
        ('<a href="/admin/database" class="task-row">'
         f'<span class="task-status {"success" if last_backup else "warning"}">'
         '<i data-lucide="hard-drive-download"></i></span>'
         f'<span><strong>نسخه پشتیبان</strong><small>{e(last_backup or "هنوز ثبت نشده")}</small></span>'
         '<i data-lucide="chevron-left"></i></a>'),
        '<a href="/admin/broadcast" class="task-row"><span class="task-status success"><i data-lucide="bot"></i></span><span><strong>ربات استوک‌لند</strong><small>فعال و آماده پاسخ‌گویی</small></span><i data-lucide="chevron-left"></i></a>',
    ])

    body = f"""
    <style>
      .dashboard {{ display:flex; flex-direction:column; gap:28px; }}
      .dashboard-head {{ display:flex; align-items:flex-end; justify-content:space-between; gap:20px; }}
      .dashboard-head h2 {{ margin:0; color:var(--text-main); font-size:25px; font-weight:800; letter-spacing:-.02em; }}
      .dashboard-head p {{ margin:6px 0 0; color:var(--text-muted); font-size:12px; }}
      .date-chip {{ display:flex; align-items:center; gap:8px; padding:9px 13px; border:1px solid var(--border); border-radius:12px; background:var(--card-bg); color:var(--text-muted); font-size:11px; }}
      .date-chip svg {{ width:16px; color:#0891b2; }}
      .section-heading {{ display:flex; align-items:flex-end; justify-content:space-between; gap:16px; margin-bottom:14px; }}
      .section-heading h3 {{ margin:0; color:var(--text-main); font-size:16px; font-weight:750; }}
      .section-heading p {{ margin:4px 0 0; color:var(--text-muted); font-size:10.5px; }}
      .section-link {{ display:inline-flex; align-items:center; gap:5px; color:#0891b2; font-size:11px; font-weight:650; text-decoration:none; }} .section-link svg {{ width:14px; }}

      .command-center {{ position:relative; overflow:hidden; padding:22px; border-radius:26px; background:linear-gradient(130deg,#07111b 0%,#091827 58%,#0a2631 100%); box-shadow:0 24px 65px rgba(4,12,23,.18); }}
      .command-center::before {{ content:""; position:absolute; top:-130px; left:15%; width:380px; height:280px; border-radius:50%; background:rgba(0,215,255,.10); filter:blur(70px); }}
      .command-head {{ position:relative; display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; color:#fff; }}
      .command-title {{ display:flex; align-items:center; gap:11px; }} .command-title>span {{ width:36px; height:36px; display:grid; place-items:center; border-radius:12px; background:rgba(0,215,255,.1); color:#42e2ff; border:1px solid rgba(0,215,255,.12); }}
      .command-title svg {{ width:18px; }} .command-title h3 {{ margin:0; font-size:15px; }} .command-title p {{ margin:3px 0 0; color:#74849a; font-size:9.5px; }}
      .live-pill {{ display:flex; align-items:center; gap:7px; padding:7px 10px; border-radius:999px; color:#9de9bd; background:rgba(34,197,94,.08); border:1px solid rgba(34,197,94,.12); font-size:9px; }}
      .live-pill span {{ width:6px; height:6px; border-radius:50%; background:#22c55e; box-shadow:0 0 10px #22c55e; }}
      .command-grid {{ position:relative; display:grid; grid-template-columns:repeat(7,minmax(145px,1fr)); gap:9px; overflow-x:auto; padding-bottom:2px; scrollbar-width:thin; }}
      .command-item {{ min-width:145px; min-height:142px; display:flex; flex-direction:column; position:relative; padding:15px; border:1px solid rgba(255,255,255,.07); border-radius:18px; background:rgba(255,255,255,.035); text-decoration:none; transition:200ms; }}
      .command-item:hover {{ background:rgba(255,255,255,.065); border-color:rgba(0,215,255,.18); transform:translateY(-2px); }}
      .command-icon {{ width:33px; height:33px; display:grid; place-items:center; border-radius:11px; background:rgba(0,215,255,.08); color:#42e2ff; }} .command-icon svg {{ width:17px; }}
      .command-warning .command-icon {{ background:rgba(245,158,11,.09); color:#fbbf24; }} .command-danger .command-icon {{ background:rgba(239,68,68,.09); color:#fb7185; }} .command-success .command-icon {{ background:rgba(34,197,94,.09); color:#4ade80; }}
      .command-copy {{ margin-top:auto; }} .command-copy small,.command-copy strong,.command-copy em {{ display:block; font-style:normal; }} .command-copy small {{ color:#8290a3; font-size:9.5px; }} .command-copy strong {{ color:#f8fafc; font-size:17px; margin-top:3px; }} .command-copy em {{ color:#65758a; font-size:8.5px; margin-top:3px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }}
      .command-arrow {{ position:absolute; top:16px; left:14px; width:13px; color:#465568; }}

      .kpi-grid {{ display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:16px; }}
      .kpi-card {{ min-height:188px; padding:20px; overflow:hidden; position:relative; }} .kpi-card::after {{ content:""; position:absolute; top:-55px; left:-45px; width:130px; height:130px; border-radius:50%; background:rgba(0,215,255,.035); }}
      .kpi-top {{ display:flex; align-items:center; justify-content:space-between; }} .kpi-icon {{ width:40px; height:40px; display:grid; place-items:center; border-radius:13px; color:#0891b2; background:#ecfeff; }} .kpi-icon svg {{ width:19px; }}
      .kpi-label {{ color:var(--text-muted); font-size:10.5px; font-weight:600; }} .kpi-value {{ margin:15px 0 3px; color:var(--text-main); font-size:25px; font-weight:800; letter-spacing:-.025em; direction:ltr; text-align:right; }} .kpi-unit {{ color:var(--text-muted); font-size:9px; font-weight:500; margin-right:3px; }}
      .trend {{ display:inline-flex; align-items:center; gap:3px; font-size:9px; font-weight:700; direction:ltr; }} .trend svg {{ width:12px; }} .trend-up {{ color:#16a34a; }} .trend-down {{ color:#e11d48; }} .trend-flat {{ color:#94a3b8; }}
      .sparkline {{ position:absolute; right:15px; left:15px; bottom:11px; height:43px; opacity:.9; }} .sparkline path.line {{ fill:none; stroke:#06b6d4; stroke-width:2.2; stroke-linecap:round; stroke-linejoin:round; }} .sparkline path.area {{ fill:url(#sparkFill); opacity:.55; }}

      .chart-card {{ padding:22px 24px 18px; }} .chart-toolbar {{ display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; }} .chart-legend {{ display:flex; align-items:center; gap:7px; color:var(--text-muted); font-size:10px; }} .chart-legend span {{ width:7px; height:7px; border-radius:50%; background:#00d7ff; box-shadow:0 0 0 4px rgba(0,215,255,.08); }} .chart-period {{ padding:7px 10px; border:1px solid var(--border); border-radius:10px; color:var(--text-muted); font-size:9px; background:var(--card-bg); }}
      .chart-shell {{ position:relative; height:400px; }}
      .two-column {{ display:grid; grid-template-columns:minmax(0,3fr) minmax(320px,2fr); gap:18px; }} .panel-card {{ overflow:hidden; }} .panel-header {{ min-height:68px; display:flex; align-items:center; justify-content:space-between; padding:0 20px; border-bottom:1px solid var(--border); }} .panel-header h3 {{ margin:0; font-size:14px; }} .panel-header p {{ margin:3px 0 0; color:var(--text-muted); font-size:9.5px; }} .table-wrap {{ overflow:auto; max-height:500px; }}
      .order-id {{ color:#0891b2; font:700 11px/1 Inter,sans-serif !important; text-decoration:none; }} .table-product {{ display:flex; align-items:center; gap:9px; min-width:180px; }} .table-product>span {{ width:31px; height:31px; display:grid; place-items:center; border-radius:10px; background:#f1f5f9; color:#64748b; }} .table-product svg {{ width:15px; }} .table-product strong {{ font-size:11px; font-weight:600; }} .muted-cell {{ color:var(--text-muted); font-size:10px; }} .money-cell {{ display:block; font-size:11px; direction:ltr; text-align:right; }} .currency {{ color:var(--text-muted); font-size:8px; }}
      .status-badge {{ display:inline-flex; align-items:center; gap:5px; padding:5px 8px; border-radius:999px; font-size:9px; font-weight:650; white-space:nowrap; }} .status-badge>span {{ width:5px; height:5px; border-radius:50%; }} .status-success {{ color:#15803d; background:#ecfdf3; }} .status-success>span {{ background:#22c55e; }} .status-warning {{ color:#a16207; background:#fffbeb; }} .status-warning>span {{ background:#f59e0b; }} .status-danger {{ color:#be123c; background:#fff1f2; }} .status-danger>span {{ background:#ef4444; }} .status-neutral {{ color:#475569; background:#f1f5f9; }} .status-neutral>span {{ background:#94a3b8; }}
      .table-action {{ width:30px; height:30px; display:grid; place-items:center; border:1px solid var(--border); border-radius:9px; color:#64748b; }} .table-action svg {{ width:14px; }}
      .tasks-list {{ padding:8px 12px 12px; }} .task-row {{ min-height:67px; display:grid; grid-template-columns:38px 1fr 16px; align-items:center; gap:10px; padding:7px 8px; border-bottom:1px solid #eef0f3; text-decoration:none; transition:160ms; }} .task-row:last-child {{ border:0; }} .task-row:hover {{ background:var(--page-bg); border-radius:12px; }} .task-row>svg {{ width:14px; color:#b1b7c2; }} .task-row strong,.task-row small {{ display:block; }} .task-row strong {{ color:var(--text-main); font-size:10.5px; }} .task-row small {{ color:var(--text-muted); font-size:8.5px; margin-top:3px; }}
      .task-status {{ width:36px; height:36px; display:grid; place-items:center; border-radius:11px; }} .task-status svg {{ width:16px; }} .task-status.danger {{ color:#e11d48; background:#fff1f2; }} .task-status.warning {{ color:#d97706; background:#fffbeb; }} .task-status.cyan {{ color:#0891b2; background:#ecfeff; }} .task-status.success {{ color:#16a34a; background:#f0fdf4; }}

      .three-column {{ display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:18px; }} .mini-panel {{ padding-bottom:12px; overflow:hidden; }} .mini-panel .panel-header {{ min-height:64px; }} .rank-row {{ min-height:56px; display:grid; grid-template-columns:28px 1fr auto; align-items:center; gap:9px; padding:7px 18px; }} .rank-number {{ width:25px; height:25px; display:grid; place-items:center; border-radius:8px; background:#f1f5f9; color:#64748b; font:700 9px/1 Inter,sans-serif !important; }} .rank-copy strong,.rank-copy small {{ display:block; }} .rank-copy strong {{ font-size:10px; }} .rank-copy small {{ color:var(--text-muted); font-size:8px; margin-top:3px; }} .rank-value {{ color:#0891b2; font-size:9px; direction:ltr; }}
      .compact-row {{ min-height:58px; display:grid; grid-template-columns:36px 1fr auto; align-items:center; gap:9px; padding:7px 16px; text-decoration:none; }} .row-icon {{ width:34px; height:34px; display:grid; place-items:center; border-radius:10px; }} .row-icon svg {{ width:15px; }} .row-icon.warning {{ color:#d97706; background:#fffbeb; }} .row-icon.danger {{ color:#e11d48; background:#fff1f2; }} .row-copy strong,.row-copy small {{ display:block; }} .row-copy strong {{ font-size:9.5px; }} .row-copy small {{ color:var(--text-muted); font-size:8px; margin-top:3px; }} .stock-count {{ padding:4px 7px; border-radius:999px; color:#a16207; background:#fffbeb; font-size:8px; font-weight:700; }} .stock-count.out {{ color:#be123c; background:#fff1f2; }}
      .activity-row {{ min-height:58px; display:grid; grid-template-columns:35px 1fr; align-items:center; gap:9px; padding:7px 16px; }} .activity-icon {{ width:34px; height:34px; display:grid; place-items:center; border-radius:50%; color:#0891b2; background:#ecfeff; position:relative; }} .activity-icon svg {{ width:15px; }} .activity-row strong,.activity-row small {{ display:block; }} .activity-row strong {{ font-size:9.5px; }} .activity-row small {{ color:var(--text-muted); font-size:8px; margin-top:3px; }} .empty-state {{ padding:38px 18px; color:var(--text-muted); text-align:center; font-size:10px; }}
      body.dark-mode .kpi-icon,body.dark-mode .table-product>span,body.dark-mode .rank-number {{ background:#172330; }} body.dark-mode .task-row,body.dark-mode .panel-header {{ border-color:#273244; }} body.dark-mode .status-success {{ background:rgba(34,197,94,.1); }} body.dark-mode .status-warning {{ background:rgba(245,158,11,.1); }} body.dark-mode .status-danger {{ background:rgba(239,68,68,.1); }}
      @media(max-width:1200px) {{ .kpi-grid {{ grid-template-columns:repeat(2,1fr); }} .three-column {{ grid-template-columns:1fr 1fr; }} .three-column>*:last-child {{ grid-column:1/-1; }} }}
      @media(max-width:940px) {{ .two-column {{ grid-template-columns:1fr; }} .command-grid {{ grid-template-columns:repeat(7,155px); }} }}
      @media(max-width:640px) {{ .dashboard {{ gap:22px; }} .dashboard-head {{ align-items:flex-start; }} .dashboard-head h2 {{ font-size:21px; }} .date-chip {{ display:none; }} .command-center {{ padding:18px 14px; border-radius:22px; }} .command-grid {{ margin-left:-14px; padding-left:14px; }} .kpi-grid,.three-column {{ grid-template-columns:1fr; }} .three-column>*:last-child {{ grid-column:auto; }} .kpi-card {{ min-height:174px; }} .chart-card {{ padding:18px 12px 12px; }} .chart-shell {{ height:320px; }} .panel-header {{ padding:0 14px; }} }}
    </style>

    <main class="dashboard">
      <div class="dashboard-head">
        <div><h2>مرکز مدیریت استوک‌لند</h2><p>نمای یکپارچه فروش، عملیات و سلامت سرویس‌های فروشگاه</p></div>
        <div class="date-chip"><i data-lucide="calendar-days"></i><span>{today}</span></div>
      </div>

      <section class="command-center" aria-labelledby="command-title">
        <div class="command-head"><div class="command-title"><span><i data-lucide="command"></i></span><div><h3 id="command-title">مرکز فرمان</h3><p>مواردی که همین حالا به توجه شما نیاز دارند</p></div></div><div class="live-pill"><span></span>به‌روزرسانی زنده</div></div>
        <div class="command-grid">{command_items}</div>
      </section>

      <section aria-labelledby="kpi-title">
        <div class="section-heading"><div><h3 id="kpi-title">شاخص‌های کلیدی</h3><p>خلاصه عملکرد امروز و وضعیت فروشگاه</p></div></div>
        <div class="kpi-grid">
          <article class="card kpi-card"><div class="kpi-top"><span class="kpi-icon"><i data-lucide="banknote"></i></span>{pct_badge(rev_change)}</div><div class="kpi-value">{int(today_o[1]):,}<span class="kpi-unit">تومان</span></div><div class="kpi-label">درآمد امروز</div><svg class="sparkline" viewBox="0 0 240 45" preserveAspectRatio="none"><defs><linearGradient id="sparkFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#00d7ff" stop-opacity=".24"/><stop offset="1" stop-color="#00d7ff" stop-opacity="0"/></linearGradient></defs><path class="area" d="M0,37 C24,34 35,18 58,24 S93,39 118,23 S154,11 178,18 S210,7 240,10 L240,45 L0,45Z"/><path class="line" d="M0,37 C24,34 35,18 58,24 S93,39 118,23 S154,11 178,18 S210,7 240,10"/></svg></article>
          <article class="card kpi-card"><div class="kpi-top"><span class="kpi-icon"><i data-lucide="shopping-cart"></i></span>{pct_badge(cnt_change, "")}</div><div class="kpi-value">{today_o[0]:,}<span class="kpi-unit">سفارش</span></div><div class="kpi-label">سفارش‌های امروز</div><svg class="sparkline" viewBox="0 0 240 45" preserveAspectRatio="none"><path class="area" d="M0,31 C25,14 48,38 72,26 S112,8 137,20 S175,32 199,17 S223,13 240,7 L240,45 L0,45Z"/><path class="line" d="M0,31 C25,14 48,38 72,26 S112,8 137,20 S175,32 199,17 S223,13 240,7"/></svg></article>
          <article class="card kpi-card"><div class="kpi-top"><span class="kpi-icon"><i data-lucide="boxes"></i></span><span class="trend trend-flat"><i data-lucide="package-check"></i>{products_cnt} محصول فعال</span></div><div class="kpi-value">{feed_avail:,}<span class="kpi-unit">آیتم</span></div><div class="kpi-label">موجودی قابل تحویل</div><svg class="sparkline" viewBox="0 0 240 45" preserveAspectRatio="none"><path class="area" d="M0,28 C22,24 42,27 65,19 S105,30 129,21 S162,12 187,17 S218,10 240,14 L240,45 L0,45Z"/><path class="line" d="M0,28 C22,24 42,27 65,19 S105,30 129,21 S162,12 187,17 S218,10 240,14"/></svg></article>
          <article class="card kpi-card"><div class="kpi-top"><span class="kpi-icon"><i data-lucide="trending-up"></i></span><span class="trend trend-flat"><i data-lucide="receipt-text"></i>{total_o[0]:,} سفارش</span></div><div class="kpi-value">{int(total_o[1]):,}<span class="kpi-unit">تومان</span></div><div class="kpi-label">کل درآمد</div><svg class="sparkline" viewBox="0 0 240 45" preserveAspectRatio="none"><path class="area" d="M0,39 C26,34 38,30 62,31 S101,20 124,23 S160,15 181,16 S216,5 240,9 L240,45 L0,45Z"/><path class="line" d="M0,39 C26,34 38,30 62,31 S101,20 124,23 S160,15 181,16 S216,5 240,9"/></svg></article>
        </div>
      </section>

      <section class="card chart-card" aria-labelledby="sales-title">
        <div class="chart-toolbar"><div class="section-heading" style="margin:0"><div><h3 id="sales-title">تحلیل فروش</h3><p>روند درآمد در ۳۰ روز اخیر</p></div></div><div style="display:flex;align-items:center;gap:14px"><span class="chart-legend"><span></span>فروش روزانه</span><span class="chart-period">۳۰ روز اخیر</span></div></div>
        <div class="chart-shell"><canvas id="salesChart"></canvas></div>
      </section>

      <section class="two-column">
        <article class="card panel-card"><div class="panel-header"><div><h3>سفارش‌های اخیر</h3><p>آخرین تراکنش‌های ثبت‌شده در فروشگاه</p></div><a href="/admin/orders" class="section-link">مشاهده همه<i data-lucide="arrow-left"></i></a></div><div class="table-wrap"><table><thead><tr><th>شناسه</th><th>محصول</th><th>کاربر</th><th>مبلغ</th><th>وضعیت</th><th></th></tr></thead><tbody>{recent_rows or '<tr><td colspan="6" class="empty-state">هنوز سفارشی ثبت نشده است</td></tr>'}</tbody></table></div></article>
        <article class="card panel-card"><div class="panel-header"><div><h3>وظایف مرکز فرمان</h3><p>اولویت‌های عملیاتی امروز</p></div><span class="status-badge status-warning"><span></span>نیازمند توجه</span></div><div class="tasks-list">{tasks}</div></article>
      </section>

      <section class="three-column">
        <article class="card mini-panel"><div class="panel-header"><div><h3>محصولات برتر</h3><p>بر اساس سفارش‌های اخیر</p></div><i data-lucide="trophy" style="width:18px;color:#f59e0b"></i></div>{top_product_rows or '<div class="empty-state">داده‌ای برای نمایش وجود ندارد</div>'}</article>
        <article class="card mini-panel"><div class="panel-header"><div><h3>موجودی رو به اتمام</h3><p>محصولات نیازمند تأمین</p></div><a href="/admin/feed" class="section-link">مدیریت<i data-lucide="arrow-left"></i></a></div>{low_rows or '<div class="empty-state">موجودی همه محصولات کافی است</div>'}</article>
        <article class="card mini-panel"><div class="panel-header"><div><h3>فعالیت‌های اخیر</h3><p>رویدادهای تازه فروشگاه</p></div><i data-lucide="history" style="width:18px;color:#0891b2"></i></div>{activity_rows or '<div class="empty-state">فعالیت تازه‌ای ثبت نشده است</div>'}</article>
      </section>
    </main>

    <script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
    <script>
    (function(){{
      var canvas=document.getElementById('salesChart'); if(!canvas||!window.Chart)return;
      var context=canvas.getContext('2d'); var gradient=context.createLinearGradient(0,0,0,400); gradient.addColorStop(0,'rgba(0,215,255,.22)'); gradient.addColorStop(1,'rgba(0,215,255,0)');
      new Chart(context, {{
        type: 'line',
        data: {{
          labels: {chart_labels},
          datasets: [{{
            label: 'فروش روزانه', data: {chart_values}, borderColor: '#00D7FF',
            backgroundColor: gradient, borderWidth: 2.5, fill: true, tension: .42,
            pointRadius: 0, pointHoverRadius: 5, pointHoverBackgroundColor: '#00D7FF',
            pointHoverBorderColor: '#fff', pointHoverBorderWidth: 3
          }}]
        }},
        options: {{
          responsive: true, maintainAspectRatio: false,
          interaction: {{ intersect: false, mode: 'index' }},
          plugins: {{
            legend: {{ display: false }},
            tooltip: {{
              rtl: true, titleFont: {{ family: 'Vazirmatn', size: 11 }},
              bodyFont: {{ family: 'Vazirmatn', size: 11 }}, backgroundColor: 'rgba(5,7,10,.94)',
              padding: 12, cornerRadius: 12, displayColors: false,
              callbacks: {{ label: function(ctx) {{ return Number(ctx.raw || 0).toLocaleString('fa-IR') + ' تومان'; }} }}
            }}
          }},
          scales: {{
            y: {{
              beginAtZero: true, border: {{ display: false }},
              grid: {{ color: 'rgba(148,163,184,.12)', drawTicks: false }},
              ticks: {{
                padding: 12, color: '#94A3B8', font: {{ family: 'Vazirmatn', size: 9 }},
                callback: function(v) {{ return v >= 1000000 ? (v / 1000000).toLocaleString('fa-IR') + ' م' : v.toLocaleString('fa-IR'); }}
              }}
            }},
            x: {{
              border: {{ display: false }}, grid: {{ display: false }},
              ticks: {{ color: '#94A3B8', font: {{ family: 'Vazirmatn', size: 9 }}, maxRotation: 0, autoSkip: true, maxTicksLimit: 10 }}
            }}
          }}
        }}
      }});
    }})();
    </script>"""

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

    _ensure_theme_table()
    theme = _get_theme()

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

        <!-- Color Theme -->
        <div style="margin-top:20px;border-radius:20px;overflow:hidden;background:linear-gradient(135deg,rgba(5,7,10,.97),rgba(11,19,32,.99));border:1px solid rgba(255,255,255,.08);padding:28px">
          <div style="display:flex;align-items:center;gap:12px;margin-bottom:24px">
            <div style="width:40px;height:40px;border-radius:12px;background:rgba(0,215,255,.1);border:1px solid rgba(0,215,255,.2);display:flex;align-items:center;justify-content:center"><i data-lucide="palette" style="width:18px;color:#00D7FF"></i></div>
            <div>
              <div style="font-size:15px;font-weight:700;color:#fff">تنظیمات رنگ‌بندی پنل</div>
              <div style="font-size:11px;color:#4A5568;margin-top:2px">هر رنگ را با اسلایدر R-G-B تنظیم کنید. تغییرات بلافاصله در پیش‌نمایش اعمال می‌شود.</div>
            </div>
          </div>
          <style>
            .color-grid {{ display:grid; grid-template-columns:repeat(auto-fill,minmax(250px,1fr)); gap:14px; }}
            .color-item {{ background:rgba(255,255,255,.035); border:1px solid rgba(255,255,255,.07); border-radius:16px; padding:15px; transition:.2s; }}
            .color-item:hover {{ background:rgba(0,215,255,.04); border-color:rgba(0,215,255,.12); }}
            .color-header {{ display:flex; align-items:center; gap:11px; margin-bottom:12px; }}
            .color-preview {{ width:42px; height:42px; border-radius:11px; border:1px solid rgba(255,255,255,.12); flex-shrink:0; transition:background .15s; }}
            .color-label {{ font-size:12px; font-weight:600; color:#C5CDD8; }}
            .color-hex {{ font-size:10.5px; color:#3D4D5E; font-family:monospace; margin-top:2px; display:block; }}
            .slider-group {{ display:flex; flex-direction:column; gap:8px; }}
            .slider-row {{ display:grid; grid-template-columns:12px 1fr 22px; align-items:center; gap:8px; }}
            .slider-lbl {{ font-size:9px; font-weight:800; text-align:center; }}
            input[type=range].rgb-slider {{ height:5px; border-radius:5px; outline:none; cursor:pointer; border:none; background:rgba(255,255,255,.08); -webkit-appearance:none; appearance:none; min-height:unset; padding:0; }}
            input[type=range].rgb-slider::-webkit-slider-thumb {{ -webkit-appearance:none; width:13px; height:13px; border-radius:50%; box-shadow:0 2px 6px rgba(0,0,0,.5); cursor:pointer; }}
            .r-slider::-webkit-slider-thumb {{ background:#ef4444; }}
            .g-slider::-webkit-slider-thumb {{ background:#22c55e; }}
            .b-slider::-webkit-slider-thumb {{ background:#3b82f6; }}
            .slider-val {{ font-size:9px; color:#3D4D5E; font-family:monospace; text-align:left; }}
          </style>

          <form method="post" action="/admin/settings/theme" id="themeForm">
            <div class="color-grid">
              {_theme_color_input("sidebar_bg", "پس‌زمینه منو", theme)}
              {_theme_color_input("sidebar_text", "متن منو", theme)}
              {_theme_color_input("sidebar_active", "رنگ آیتم فعال", theme)}
              {_theme_color_input("primary", "رنگ اصلی (Primary)", theme)}
              {_theme_color_input("accent", "رنگ تأکیدی (Accent)", theme)}
              {_theme_color_input("page_bg", "پس‌زمینه صفحه", theme)}
              {_theme_color_input("card_bg", "رنگ کارت‌ها", theme)}
              {_theme_color_input("text_main", "رنگ متن اصلی", theme)}
            </div>
            <div style="display:flex;gap:10px;margin-top:20px;flex-wrap:wrap">
              <button type="submit" style="display:inline-flex;align-items:center;gap:8px;padding:10px 22px;background:#00D7FF;color:#000;font-weight:700;font-size:13px;border:none;border-radius:12px;cursor:pointer;transition:.15s">
                <i data-lucide="save" style="width:15px"></i> ذخیره رنگ‌ها
              </button>
              <a href="/admin/settings/theme/reset" onclick="return confirm('رنگ‌های پیش‌فرض بازگردانده شود؟')"
                 style="display:inline-flex;align-items:center;gap:8px;padding:10px 18px;background:rgba(255,255,255,.06);color:#8896A8;font-size:13px;border-radius:12px;text-decoration:none;border:1px solid rgba(255,255,255,.08);transition:.15s">
                <i data-lucide="rotate-ccw" style="width:14px"></i> پیش‌فرض
              </a>
            </div>
          </form>

          <script>
          (function(){{
            function toHex(n){{ return Math.max(0,Math.min(255,n)).toString(16).padStart(2,'0'); }}
            window.updateColor = function(key){{
              var r = parseInt(document.querySelector('.r-slider[data-key="'+key+'"]').value);
              var g = parseInt(document.querySelector('.g-slider[data-key="'+key+'"]').value);
              var b = parseInt(document.querySelector('.b-slider[data-key="'+key+'"]').value);
              var hex = '#'+toHex(r)+toHex(g)+toHex(b);
              document.getElementById('r_'+key).textContent = r;
              document.getElementById('g_'+key).textContent = g;
              document.getElementById('b_'+key).textContent = b;
              document.getElementById('hex_'+key).textContent = hex;
              document.getElementById('inp_'+key).value = hex;
              document.getElementById('prev_'+key).style.background = hex;
              // پیش‌نمایش فوری روی صفحه
              document.documentElement.style.setProperty('--'+key.replace(/_/g,'-'), hex);
            }};
            if(window.lucide) lucide.createIcons();
          }})();
          </script>
        </div>
      </div>
    </div>"""

    return _layout("تنظیمات", body, adm, flash=flash)


def _theme_color_input(key, label, theme):
    val = theme.get(key, DEFAULT_THEME.get(key, "#000000"))
    # تبدیل hex به RGB
    def hex_to_rgb(h):
        h = h.lstrip('#')
        if len(h) == 3: h = h[0]*2 + h[1]*2 + h[2]*2
        try:
            return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
        except:
            return 100, 100, 100
    r, g, b = hex_to_rgb(val)
    return f"""
    <div class="color-item" data-key="{key}">
      <div class="color-header">
        <div class="color-preview" id="prev_{key}" style="background:{val}"></div>
        <div>
          <div class="color-label">{label}</div>
          <code class="color-hex" id="hex_{key}">{val}</code>
        </div>
      </div>
      <div class="slider-group">
        <div class="slider-row">
          <span class="slider-lbl" style="color:#ef4444">R</span>
          <input type="range" min="0" max="255" value="{r}" class="rgb-slider r-slider" data-key="{key}" oninput="updateColor('{key}')">
          <span class="slider-val" id="r_{key}">{r}</span>
        </div>
        <div class="slider-row">
          <span class="slider-lbl" style="color:#22c55e">G</span>
          <input type="range" min="0" max="255" value="{g}" class="rgb-slider g-slider" data-key="{key}" oninput="updateColor('{key}')">
          <span class="slider-val" id="g_{key}">{g}</span>
        </div>
        <div class="slider-row">
          <span class="slider-lbl" style="color:#3b82f6">B</span>
          <input type="range" min="0" max="255" value="{b}" class="rgb-slider b-slider" data-key="{key}" oninput="updateColor('{key}')">
          <span class="slider-val" id="b_{key}">{b}</span>
        </div>
      </div>
      <input type="hidden" name="{key}" id="inp_{key}" value="{val}">
    </div>"""


@router.post("/settings/theme")
async def settings_theme_save(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard
    _ensure_theme_table()
    form = await request.form()
    conn = _db()
    try:
        for key in DEFAULT_THEME:
            # اول color picker رو چک کن، بعد hex input
            val = str(form.get(key) or form.get(f"{key}_hex") or DEFAULT_THEME[key]).strip()
            if val:
                conn.execute(
                    "INSERT INTO panel_theme (key, value) VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value;",
                    (key, val)
                )
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?flash=رنگ‌بندی+ذخیره+شد")


@router.get("/settings/theme/reset")
async def settings_theme_reset(request: Request):
    adm = _get_admin(request)
    guard = _require(adm, "settings")
    if guard: return guard
    conn = _db()
    try:
        conn.execute("DELETE FROM panel_theme;")
        conn.commit()
    finally:
        conn.close()
    return _redir("/admin/settings?flash=رنگ‌های+پیش‌فرض+بازگردانده+شد")


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

    # لیست بکاپ‌های خودکار
    import glob as _glob, os as _os
    auto_backups = sorted(_glob.glob(f"{_BACKUP_DIR}/auto_*.sqlite"), reverse=True)
    backup_rows = ""
    for bp in auto_backups:
        fname = _os.path.basename(bp)
        size_kb = _os.path.getsize(bp) // 1024
        ts_part = fname.replace("auto_", "").replace(".sqlite", "")
        backup_rows += f"""
        <tr class="border-b hover:bg-gray-50">
          <td class="px-4 py-2 text-sm font-mono">{e(ts_part[:8])} {e(ts_part[9:] if len(ts_part)>8 else "")}</td>
          <td class="px-4 py-2 text-sm text-gray-500">{size_kb} KB</td>
          <td class="px-4 py-2">
            <a href="/admin/database/auto-backup/{e(fname)}"
               class="px-3 py-1 bg-indigo-50 text-indigo-700 rounded text-xs hover:bg-indigo-100">⬇ دانلود</a>
          </td>
        </tr>"""

    auto_backup_section = f"""
    <div class="card p-6 mb-6">
      <div class="flex items-center justify-between mb-3">
        <h2 class="font-bold text-gray-700">🕐 بکاپ‌های خودکار (روزانه)</h2>
        <span class="text-xs text-gray-400">حداکثر ۵ فایل | هر شب یک بکاپ</span>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-2">تاریخ</th><th class="px-4 py-2">حجم</th><th class="px-4 py-2">دانلود</th>
        </tr></thead>
        <tbody>{backup_rows or "<tr><td colspan='3' class='text-center py-4 text-gray-400 text-sm'>هنوز بکاپ خودکاری ایجاد نشده</td></tr>"}</tbody>
      </table>
    </div>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">💾 مدیریت دیتابیس</h1>
    {auto_backup_section}

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

@router.get("/database/auto-backup/{fname}")
async def auto_backup_download(request: Request, fname: str):
    adm = _get_admin(request)
    guard = _require(adm, "database")
    if guard: return guard
    import os, re
    # امنیت: فقط auto_*.sqlite
    if not re.match(r'^auto_\d{8}_\d{6}\.sqlite$', fname):
        return _redir("/admin/database?flash=فایل+نامعتبر")
    path = f"{_BACKUP_DIR}/{fname}"
    if not os.path.exists(path):
        return _redir("/admin/database?flash=فایل+یافت+نشد")
    return FileResponse(path, filename=fname, media_type="application/octet-stream")


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
import threading as _threading
import time as _time

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

    {"" if not adm[1] else f'''
    <!-- Super Admin Settings -->
    <div class="bg-amber-50 border border-amber-200 rounded-xl p-6 mb-6">
      <h2 class="font-bold text-amber-800 mb-4">🔐 تنظیمات سوپرادمین</h2>
      <div class="grid md:grid-cols-2 gap-6">
        <form method="post" action="/admin/admins/super/password" class="space-y-3">
          <label class="text-xs text-gray-600 block">تغییر رمز پنل</label>
          {_input("new_password", "رمز جدید", type_="password", required=True)}
          {_input("confirm_password", "تکرار رمز", type_="password", required=True)}
          <button class="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700">ذخیره رمز</button>
        </form>
        <form method="post" action="/admin/admins/super/telegram_id" class="space-y-3">
          <label class="text-xs text-gray-600 block">تغییر آیدی تلگرام سوپرادمین</label>
          {_input("new_telegram_id", "آیدی عددی تلگرام", type_="number", required=True)}
          <button class="px-4 py-2 bg-amber-600 text-white rounded-lg text-sm hover:bg-amber-700">ذخیره آیدی</button>
        </form>
      </div>
    </div>'''}

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

@router.post("/admins/super/password")
async def super_change_password(request: Request, new_password: str = Form(""), confirm_password: str = Form("")):
    adm = _get_admin(request)
    if not adm or not adm[1]:  # فقط سوپرادمین
        return _redir("/admin/login")
    if not new_password or new_password != confirm_password:
        return _redir("/admin/admins?flash=رمزها+یکسان+نیستند+یا+خالی+است")
    # آپدیت .env
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        lines = open(env_path, encoding="utf-8").readlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("ADMIN_WEB_PASSWORD="):
                new_lines.append(f"ADMIN_WEB_PASSWORD={new_password}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"ADMIN_WEB_PASSWORD={new_password}\n")
        open(env_path, "w", encoding="utf-8").writelines(new_lines)
        os.environ["ADMIN_WEB_PASSWORD"] = new_password
    except Exception as ex:
        return _redir(f"/admin/admins?flash=خطا:+{str(ex)[:40]}")
    return _redir("/admin/admins?flash=رمز+سوپرادمین+تغییر+کرد")


@router.post("/admins/super/telegram_id")
async def super_change_telegram_id(request: Request, new_telegram_id: str = Form("")):
    adm = _get_admin(request)
    if not adm or not adm[1]:
        return _redir("/admin/login")
    try:
        int(new_telegram_id)
    except ValueError:
        return _redir("/admin/admins?flash=آیدی+نامعتبر")
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    try:
        lines = open(env_path, encoding="utf-8").readlines()
        new_lines = []
        found = False
        for line in lines:
            if line.startswith("ADMIN_ID="):
                new_lines.append(f"ADMIN_ID={new_telegram_id}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"ADMIN_ID={new_telegram_id}\n")
        open(env_path, "w", encoding="utf-8").writelines(new_lines)
        os.environ["ADMIN_ID"] = new_telegram_id
    except Exception as ex:
        return _redir(f"/admin/admins?flash=خطا:+{str(ex)[:40]}")
    return _redir("/admin/admins?flash=آیدی+تلگرام+تغییر+کرد+—+ربات+را+ریستارت+کنید")


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
        # تعداد برگشتی این محصول
        try:
            returned_cnt = conn.execute(
                "SELECT COUNT(*) FROM orders WHERE product_id=? AND status='returned';", (str(pid),)
            ).fetchone()[0]
        except Exception:
            returned_cnt = 0
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
    <div class="grid grid-cols-4 gap-4 mb-6">
      {_card("کل آیتم‌ها", str(total), "", "slate")}
      {_card("موجود", str(avail), "", "green")}
      {_card("تحویل‌شده", str(total-avail), "", "indigo")}
      {_card("برگشتی ↩️", str(returned_cnt), "بازگردانده‌شده", "red")}
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
async def orders_list(request: Request, page: int=0, q: str="", flash: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "orders")
    if guard: return guard

    PAGE = 30
    conn = _db()
    try:
        # migration امن
        for col, typedef in [("status", "TEXT DEFAULT 'active'"), ("feed_id", "INTEGER"), ("returned_at", "TEXT")]:
            try:
                conn.execute(f"ALTER TABLE orders ADD COLUMN {col} {typedef};")
            except Exception:
                pass
        where = "WHERE user_id LIKE ?" if q else ""
        params_q = (f"%{q}%",) if q else ()
        total = conn.execute(f"SELECT COUNT(*) FROM orders {where};", params_q).fetchone()[0]
        orders = conn.execute(f"SELECT * FROM orders {where} ORDER BY id DESC LIMIT ? OFFSET ?;",
                              params_q+(PAGE, page*PAGE)).fetchall()
        # آمار برگشتی
        returned_total = conn.execute("SELECT COUNT(*) FROM orders WHERE status='returned';").fetchone()[0]
    finally:
        conn.close()

    pages = max((total+PAGE-1)//PAGE, 1)

    def order_status_badge(st):
        if st == "returned":
            return '<span class="px-2 py-0.5 text-xs rounded-full bg-red-100 text-red-700">برگشتی</span>'
        return '<span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">فعال</span>'

    rows = ""
    for o in orders:
        st = o["status"] if "status" in o.keys() and o["status"] else "active"
        is_returned = st == "returned"
        action_btns = ""
        if not is_returned:
            action_btns = f"""
            <a href="/admin/orders/{o['id']}/edit" class="px-2 py-1 text-xs bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100">✏️ ویرایش</a>
            <form method="post" action="/admin/orders/{o['id']}/return" class="inline" onsubmit="return confirm('محصول برگشت داده شود؟ پیام از چت کاربر حذف و موجودی بازگردانده می‌شود.')">
              <button class="px-2 py-1 text-xs bg-red-50 text-red-700 rounded hover:bg-red-100">↩️ برگشت</button>
            </form>"""
        else:
            action_btns = '<span class="text-xs text-gray-400">برگشت خورده</span>'

        rows += f"""
        <tr class="border-b hover:bg-gray-50 text-sm {'bg-red-50/30' if is_returned else ''}">
          <td class="px-4 py-2 text-gray-400">#{o["id"]}</td>
          <td class="px-4 py-2 font-mono text-xs"><code>{e(o["user_id"])}</code></td>
          <td class="px-4 py-2">{e(o["title"])}</td>
          <td class="px-4 py-2 text-green-700 font-medium">{int(o["price"]):,} ت</td>
          <td class="px-4 py-2">{order_status_badge(st)}</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(o["created_at"] or "")[:16]}</td>
          <td class="px-4 py-2 flex gap-1 items-center">{action_btns}</td>
        </tr>"""

    pager = '<div class="flex gap-2 mt-4 justify-center">' + "".join(
        f'<a href="/admin/orders?page={i}" class="px-3 py-1 rounded border text-sm {"bg-indigo-600 text-white" if i==page else "bg-white"}">{i+1}</a>'
        for i in range(min(pages, 10))
    ) + "</div>" if pages > 1 else ""

    body = f"""
    <div class="flex items-center justify-between mb-6 flex-wrap gap-3">
      <h1 class="text-2xl font-bold text-gray-800">🧾 سفارش‌ها ({total:,})</h1>
      <div class="flex items-center gap-3">
        <span class="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg text-sm">↩️ برگشتی: {returned_total}</span>
        <form method="get" class="flex gap-2">
          {_input("q","جستجو User ID...",q)} {_btn("جستجو","","slate",True)}
        </form>
      </div>
    </div>
    <div class="card overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">#</th><th class="px-4 py-3">User ID</th>
          <th class="px-4 py-3">محصول</th><th class="px-4 py-3">مبلغ</th>
          <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">تاریخ</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='7' class='text-center py-8 text-gray-400'>سفارشی ثبت نشده</td></tr>"}</tbody>
      </table>{pager}
    </div>"""

    return _layout("سفارش‌ها", body, adm, flash=flash)


@router.get("/orders/{oid}/edit", response_class=HTMLResponse)
async def order_edit_get(request: Request, oid: int, flash: str=""):
    adm = _get_admin(request)
    guard = _require(adm, "orders")
    if guard: return guard

    conn = _db()
    try:
        o = conn.execute("SELECT * FROM orders WHERE id=? LIMIT 1;", (oid,)).fetchone()
    finally:
        conn.close()
    if not o:
        return _redir("/admin/orders?flash=سفارش+یافت+نشد")

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/orders", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">✏️ ویرایش سفارش #{oid}</h1>
    </div>
    <div class="card p-6 max-w-xl">
      <form method="post" action="/admin/orders/{oid}/edit" class="space-y-4">
        <div>
          <label class="text-xs text-gray-500 block mb-1">کاربر</label>
          <code class="bg-gray-100 px-2 py-1 rounded text-sm">{e(o["user_id"])}</code>
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">عنوان محصول</label>
          {_input("title", "", str(o["title"] or ""), required=True)}
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">مبلغ (تومان)</label>
          {_input("price", "", str(o["price"] or 0), type_="number", required=True)}
        </div>
        <div class="flex gap-3">
          {_btn("ذخیره تغییرات", color="green")}
          {_btn("انصراف", "/admin/orders", "slate")}
        </div>
      </form>
    </div>"""
    return _layout(f"ویرایش سفارش #{oid}", body, adm, flash=flash)


@router.post("/orders/{oid}/edit")
async def order_edit_post(request: Request, oid: int, title: str=Form(""), price: str=Form("0")):
    adm = _get_admin(request)
    guard = _require(adm, "orders")
    if guard: return guard
    try:
        from db import order_update
        order_update(oid, title=title.strip(), price=int(price or 0))
    except Exception as ex:
        _tg_logger.error("order_edit error: %s", ex)
        return _redir(f"/admin/orders/{oid}/edit?flash=خطا+در+ذخیره")
    return _redir("/admin/orders?flash=سفارش+ویرایش+شد")


@router.post("/orders/{oid}/return")
async def order_return(request: Request, oid: int):
    adm = _get_admin(request)
    guard = _require(adm, "orders")
    if guard: return guard

    try:
        from db import order_mark_returned
        result = order_mark_returned(oid)
    except Exception as ex:
        _tg_logger.error("order_return error: %s", ex)
        return _redir(f"/admin/orders?flash=خطا+در+برگشت:+{str(ex)[:40]}")

    if not result.get("ok"):
        return _redir(f"/admin/orders?flash={result.get('error', 'خطا')}")

    # حذف پیام تحویل از چت کاربر
    if result.get("chat_id") and result.get("message_id"):
        _tg_delete_message(result["chat_id"], result["message_id"])

    # اطلاع به کاربر
    if result.get("user_id"):
        _tg_send(
            int(result["user_id"]),
            f"⚠️ سفارش #{oid} (<b>{html.escape(str(result.get('title') or ''))}</b>) "
            "توسط پشتیبانی برگشت داده شد.\nدر صورت سوال با پشتیبانی در تماس باشید."
        )

    return _redir("/admin/orders?flash=محصول+برگشت+داده+شد+و+موجودی+بازگردانده+شد")


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
          <td class="px-4 py-2">
            <details class="inline-block">
              <summary class="cursor-pointer px-2 py-1 text-xs bg-indigo-50 text-indigo-700 rounded hover:bg-indigo-100 list-none">✏️ ویرایش موجودی</summary>
              <form method="post" action="/admin/wallets/adjust" class="flex gap-2 items-end mt-2 p-2 bg-gray-50 rounded-lg">
                <input type="hidden" name="uid" value="{w["user_id"]}">
                <input type="number" name="amount" placeholder="مبلغ" required class="w-24 border border-gray-300 rounded px-2 py-1 text-xs">
                <select name="op" class="border border-gray-300 rounded px-2 py-1 text-xs">
                  <option value="add">➕ افزودن</option>
                  <option value="sub">➖ کاهش</option>
                  <option value="set">✏️ تنظیم</option>
                </select>
                <button class="px-3 py-1 bg-indigo-600 text-white rounded text-xs">ثبت</button>
              </form>
            </details>
          </td>
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
          <th class="px-4 py-2">User ID</th><th class="px-4 py-2">موجودی</th><th class="px-4 py-2">آپدیت</th><th class="px-4 py-2">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='4' class='text-center py-8 text-gray-400'>کاربری یافت نشد</td></tr>"}</tbody>
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
        # جدول لاگ تراکنش‌های دستی
        conn.execute("""
            CREATE TABLE IF NOT EXISTS wallet_admin_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER, op TEXT, amount INTEGER,
                old_balance INTEGER, new_balance INTEGER,
                admin_id TEXT, created_at TEXT
            );
        """)
        row = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
        cur = int(row["balance"] if row else 0)
        new_bal = cur+amt if op=="add" else max(0,cur-amt) if op=="sub" else amt
        conn.execute("INSERT INTO wallets (user_id,balance,updated_at) VALUES (?,?,?) "
                     "ON CONFLICT(user_id) DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at;",
                     (user_id, new_bal, now))
        # ثبت تراکنش در سوابق
        admin_id = adm[0] if adm else "?"
        conn.execute(
            "INSERT INTO wallet_admin_log (user_id, op, amount, old_balance, new_balance, admin_id, created_at) "
            "VALUES (?,?,?,?,?,?,?);",
            (user_id, op, amt, cur, new_bal, str(admin_id), now)
        )
        conn.commit()
    finally:
        conn.close()

    # اطلاع به کاربر
    op_label = {"add": "افزایش", "sub": "کاهش", "set": "تنظیم"}.get(op, op)
    try:
        _tg_send(
            user_id,
            f"💰 موجودی کیف‌پول شما توسط پشتیبانی {op_label} یافت.\n"
            f"موجودی فعلی: <b>{new_bal:,}</b> تومان"
        )
    except Exception:
        pass

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


def _tg_delete_message(chat_id: int, message_id: int) -> bool:
    """حذف یک پیام از چت کاربر (برای برگشت محصول)."""
    token = _env("BOT_TOKEN")
    if not token or not chat_id or not message_id:
        return False
    try:
        r = _requests.post(
            f"https://api.telegram.org/bot{token}/deleteMessage",
            json={"chat_id": int(chat_id), "message_id": int(message_id)}, timeout=15
        )
        return r.ok
    except Exception as ex:
        _tg_logger.error("_tg_delete_message error: %s", ex)
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
        stats = {s: conn.execute(f"SELECT COUNT(*) FROM tickets WHERE status=?;", (s,)).fetchone()[0]
                 for s in ("waiting_admin", "waiting_user", "closed")}
    finally:
        conn.close()

    def status_badge(s):
        cfg = {
            "waiting_admin": ("منتظر پاسخ ادمین", "danger"),
            "waiting_user":  ("منتظر کاربر", "warning"),
            "closed":        ("بسته", "neutral"),
        }
        lbl, tone = cfg.get(s, (s, "neutral"))
        return f'<span class="status-badge status-{tone}"><span></span>{lbl}</span>'

    total = sum(stats.values())
    tabs_html = '<div style="display:flex;gap:8px;margin-bottom:20px;flex-wrap:wrap">'
    for lbl, val, cnt in [("همه", "", total), ("منتظر ادمین", "waiting_admin", stats["waiting_admin"]),
                           ("منتظر کاربر", "waiting_user", stats["waiting_user"]), ("بسته", "closed", stats["closed"])]:
        is_active = status_filter == val
        style = "background:var(--primary);color:#000;font-weight:700;border-color:var(--primary)" if is_active else "background:#fff;color:var(--text-muted);border-color:var(--border)"
        badge_style = "background:rgba(0,0,0,.15)" if is_active else "background:var(--page-bg)"
        tabs_html += f'<a href="/admin/tickets?status_filter={val}" style="display:inline-flex;align-items:center;gap:7px;padding:8px 16px;border-radius:12px;border:1.5px solid;text-decoration:none;font-size:13px;transition:.15s;{style}">{lbl}<span style="padding:1px 7px;border-radius:20px;font-size:10px;font-weight:700;{badge_style}">{cnt}</span></a>'
    tabs_html += '</div>'

    rows = ""
    for t in tickets:
        rows += f"""<tr>
          <td><a href="/admin/tickets/{t['id']}" style="color:var(--primary);font-weight:700;font-size:12px;text-decoration:none">#{t['id']}</a></td>
          <td><code style="background:var(--page-bg);padding:2px 8px;border-radius:7px;font-size:11px">{e(str(t['user_id']))}</code></td>
          <td><span style="background:var(--page-bg);padding:2px 8px;border-radius:7px;font-size:11.5px">{e(t['type'] or 'support')}</span></td>
          <td>{status_badge(t['status'])}</td>
          <td style="color:var(--text-muted);font-size:12px">{int(t['msg_count'] or 0)} پیام</td>
          <td style="color:var(--text-muted);font-size:11px">{(t['updated_at'] or '')[:16]}</td>
          <td>{_btn("مشاهده", f"/admin/tickets/{t['id']}", "indigo", small=True)}</td>
        </tr>"""

    body = f"""
    <div class="page-header">
      <h1>تیکت‌های پشتیبانی</h1>
      <p>مدیریت و پاسخ به درخواست‌های کاربران</p>
    </div>
    {tabs_html}
    <div class="card" style="overflow:hidden">
      <div style="overflow-x:auto">
        <table style="width:100%;border-collapse:collapse">
          <thead>
            <tr style="background:#F9FAFB;border-bottom:2px solid var(--border)">
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">#</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">User ID</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">نوع</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">وضعیت</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">پیام‌ها</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right">آپدیت</th>
              <th style="padding:12px 16px;font-size:11px;color:var(--text-muted);font-weight:700;text-align:right"></th>
            </tr>
          </thead>
          <tbody>
            {rows or "<tr><td colspan='7' style='text-align:center;padding:40px;color:var(--text-muted);font-size:13px'>تیکتی یافت نشد</td></tr>"}
          </tbody>
        </table>
      </div>
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

    # ── مکالمه با نمایش عکس ─────────────────────────────────────────────────
    bot_token = _env("BOT_TOKEN")
    chat_html = ""
    last_msg_id = 0
    for msg in messages:
        is_adm = msg["sender"] == "admin"
        pos = "items-end" if is_adm else "items-start"
        bubble = "bg-indigo-600 text-white" if is_adm else "bg-white border border-gray-200 text-gray-800"
        lbl = "ادمین 👤" if is_adm else f"کاربر ({user_id_val})"
        src_badge = "" if msg["source"] == "telegram" else ' <span class="text-xs opacity-50">[پنل]</span>'
        last_msg_id = max(last_msg_id, int(msg["id"] or 0))

        content_html = ""
        if msg["media_type"] == "photo" and msg.get("media_file_id") and bot_token:
            # نمایش عکس از Telegram CDN
            file_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={msg['media_file_id']}"
            img_proxy = f"/admin/tickets/media/{e(msg['media_file_id'])}"
            content_html = f'<img src="{img_proxy}" class="rounded-lg max-w-full mt-1" style="max-height:200px" onerror="this.style.display=\'none\'">'
            if msg["text"] and msg["text"] != "[photo]":
                content_html += f'<div class="mt-1">{e(msg["text"])}</div>'
        elif msg["media_type"] and msg["media_type"] not in ("text", None):
            icon = {"document": "📎", "video": "🎥", "audio": "🎵", "voice": "🎤", "sticker": "🎭"}.get(msg["media_type"], "📁")
            content_html = f'{icon} <em class="text-xs opacity-80">[{msg["media_type"]}]</em>'
            if msg["text"] and not msg["text"].startswith("["):
                content_html += f' {e(msg["text"])}'
        else:
            content_html = e(msg["text"] or "")

        chat_html += f"""
        <div class="flex flex-col {pos} mb-3" data-msg-id="{msg['id']}">
          <div class="text-xs text-gray-400 mb-1">{lbl}{src_badge} · {(msg["created_at"] or "")[:16]}</div>
          <div class="{bubble} rounded-2xl px-4 py-2 text-sm" style="max-width:85%;word-break:break-word;white-space:pre-wrap">{content_html}</div>
        </div>"""

    if not chat_html:
        chat_html = '<div class="text-center py-8 text-gray-400 text-sm" id="no-msgs">پیامی ثبت نشده</div>'

    # ── فرم پاسخ ─────────────────────────────────────────────────────────────
    reply_form = ""
    if not is_closed:
        reply_form = f"""
        <div class="card p-4 mt-4">
          <form method="post" action="/admin/tickets/{tid}/reply" id="reply-form">
            <div class="mb-3">
              <label class="text-xs text-gray-500 block mb-1">
                پاسخ به کاربر <code class="bg-gray-100 px-1 rounded">{user_id_val}</code>
              </label>
              <textarea name="text" id="reply-text" rows="3" required
                placeholder="متن پاسخ را بنویسید..."
                class="w-full border border-gray-200 rounded-xl px-3 py-2 text-sm resize-none focus:ring-2 focus:ring-indigo-300"></textarea>
            </div>
            <div class="flex justify-between items-center">
              <span class="text-xs text-gray-300">Ctrl+Enter برای ارسال سریع</span>
              <button type="submit"
                class="bg-indigo-600 hover:bg-indigo-700 text-white px-5 py-2 rounded-xl text-sm font-medium">
                📤 ارسال پاسخ
              </button>
            </div>
          </form>
        </div>"""

    # ── وضعیت دکمه‌ها (با status های جدید v2) ─────────────────────────────
    status_btns = ""
    cur_status = ticket["status"]
    for lbl2, val2, cls2 in [
        ("🔓 بازکردن", "waiting_admin", "bg-green-50 text-green-700 border-green-200"),
        ("🔒 بستن تیکت", "closed", "bg-gray-100 text-gray-600 border-gray-200"),
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
        var b = document.getElementById('chat-box');
        if(b) b.scrollTop = b.scrollHeight;

        // Ctrl+Enter
        var ta = document.getElementById('reply-text');
        if(ta) ta.addEventListener('keydown', function(e){{
          if(e.ctrlKey && e.key === 'Enter') document.getElementById('reply-form') && document.getElementById('reply-form').submit();
        }});

        // Auto-refresh هر ۱۰ ثانیه
        var lastId = {last_msg_id};
        var ticketId = {tid};
        function fetchNew() {{
          fetch('/admin/tickets/' + ticketId + '/messages.json?after=' + lastId)
            .then(function(r){{ return r.json(); }})
            .then(function(data){{
              if(!data.messages || data.messages.length === 0) return;
              var nm = document.getElementById('no-msgs');
              if(nm) nm.remove();
              data.messages.forEach(function(msg){{
                lastId = Math.max(lastId, msg.id);
                var d = document.createElement('div');
                var isA = msg.sender === 'admin';
                d.className = 'flex flex-col ' + (isA ? 'items-end' : 'items-start') + ' mb-3';
                var bbl = isA ? 'bg-indigo-600 text-white' : 'bg-white border border-gray-200 text-gray-800';
                var lbl = isA ? 'ادمین 👤' : 'کاربر';
                var txt = (msg.text || '').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
                if(msg.media_type) txt = '[' + msg.media_type + '] ' + txt;
                d.innerHTML = '<div class="text-xs text-gray-400 mb-1">' + lbl + ' · ' + (msg.created_at||'').slice(0,16) + '</div>' +
                  '<div class="' + bbl + ' rounded-2xl px-4 py-2 text-sm" style="max-width:85%;white-space:pre-wrap">' + txt + '</div>';
                if(b) b.appendChild(d);
              }});
              if(b) b.scrollTop = b.scrollHeight;
            }}).catch(function(){{}});
        }}
        setInterval(fetchNew, 10000);
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

        # ─── migration اطمینان از وجود ستون‌های لازم ─────────────────────
        for col, typedef in [("source", "TEXT"), ("media_file_id", "TEXT"), ("updated_at", "TEXT"), ("user_msg_count", "INTEGER DEFAULT 0")]:
            try:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {col} {typedef};")
            except Exception:
                pass
            try:
                conn.execute(f"ALTER TABLE ticket_messages ADD COLUMN {col} {typedef};")
            except Exception:
                pass

        # ذخیره در ticket_messages
        now = datetime.now().isoformat()
        # بررسی وجود ستون source
        cols = [r[1] for r in conn.execute("PRAGMA table_info(ticket_messages);").fetchall()]
        if "source" in cols:
            conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender, text, source, created_at) VALUES (?,?,?,?,?);",
                (tid, "admin", text, "panel", now)
            )
        else:
            conn.execute(
                "INSERT INTO ticket_messages (ticket_id, sender, text, created_at) VALUES (?,?,?,?);",
                (tid, "admin", text, now)
            )

        # آپدیت وضعیت تیکت
        ticket_cols = [r[1] for r in conn.execute("PRAGMA table_info(tickets);").fetchall()]
        if "user_msg_count" in ticket_cols and "updated_at" in ticket_cols:
            conn.execute(
                "UPDATE tickets SET status='waiting_user', user_msg_count=0, updated_at=? WHERE id=?;",
                (now, tid)
            )
        elif "updated_at" in ticket_cols:
            conn.execute("UPDATE tickets SET status='waiting_user', updated_at=? WHERE id=?;", (now, tid))
        else:
            conn.execute("UPDATE tickets SET status='waiting_user' WHERE id=?;", (tid,))
        conn.commit()
    except Exception as ex:
        _tg_logger.error("ticket_reply DB error: %s", ex)
        return _redir(f"/admin/tickets/{tid}?flash=خطای+پایگاه+داده:+{str(ex)[:50]}")
    finally:
        conn.close()

    # ارسال به کاربر از طریق Telegram API
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


@router.get("/badges.json")
async def badges_json(request: Request):
    """شمارنده‌های real-time برای navbar (تیکت + همکار)."""
    from fastapi.responses import JSONResponse
    adm = _get_admin(request)
    if not adm:
        return JSONResponse({"tickets": 0, "partners": 0}, status_code=401)
    return JSONResponse({
        "tickets": _open_ticket_count(),
        "partners": _pending_partner_count(),
    })


@router.get("/tickets/{tid}/messages.json")
async def ticket_messages_json(request: Request, tid: int, after: int = 0):
    from fastapi.responses import JSONResponse
    adm = _get_admin(request)
    if not adm:
        return JSONResponse({"messages": []}, status_code=401)
    conn = _db()
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT id, sender, text, media_type, media_file_id, source, created_at "
            "FROM ticket_messages WHERE ticket_id=? AND id>? ORDER BY id ASC;",
            (tid, after)
        ).fetchall()
        return JSONResponse({"messages": [dict(r) for r in rows]})
    finally:
        conn.close()


@router.get("/tickets/media/{file_id}")
async def ticket_media(request: Request, file_id: str):
    """Proxy عکس‌های تیکت از Telegram."""
    from fastapi.responses import Response
    adm = _get_admin(request)
    if not adm:
        return Response(status_code=403)
    token = _env("BOT_TOKEN")
    if not token:
        return Response(status_code=404)
    try:
        # گرفتن file_path از Telegram
        r1 = _requests.get(f"https://api.telegram.org/bot{token}/getFile?file_id={file_id}", timeout=10)
        fp = r1.json().get("result", {}).get("file_path", "")
        if not fp:
            return Response(status_code=404)
        r2 = _requests.get(f"https://api.telegram.org/file/bot{token}/{fp}", timeout=15)
        ct = r2.headers.get("content-type", "image/jpeg")
        return Response(content=r2.content, media_type=ct)
    except Exception:
        return Response(status_code=502)


@router.post("/tickets/{tid}/status")
async def ticket_status(request: Request, tid: int, status: str = Form("")):
    adm = _get_admin(request)
    if not adm:
        return _redir("/admin/login")

    valid = {"waiting_admin", "waiting_user", "closed", "open", "in_progress"}
    if status not in valid:
        return _redir(f"/admin/tickets/{tid}?flash=وضعیت+نامعتبر")

    # نرمال‌سازی: اگه status قدیمی بود، به جدید تبدیل کن
    status_map = {"open": "waiting_admin", "in_progress": "waiting_user"}
    status = status_map.get(status, status)

    conn = _db()
    try:
        now = datetime.now().isoformat()
        if status == "closed":
            conn.execute(
                "UPDATE tickets SET status='closed', closed_at=?, updated_at=? WHERE id=?;",
                (now, now, tid)
            )
        else:
            conn.execute("UPDATE tickets SET status=?, updated_at=? WHERE id=?;", (status, now, tid))
        conn.commit()
    except Exception as ex:
        _tg_logger.error("ticket_status error: %s", ex)
        return _redir(f"/admin/tickets/{tid}?flash=خطا+در+تغییر+وضعیت")
    finally:
        conn.close()

    return _redir(f"/admin/tickets/{tid}?flash=وضعیت+تیکت+تغییر+کرد")
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
        # محافظت در برابر جداول ناموجود (علت صفحه سفید)
        try:
            total_users = conn.execute("SELECT COUNT(*) FROM users;").fetchone()[0]
        except Exception:
            total_users = 0
        try:
            total_buyers = conn.execute("SELECT COUNT(DISTINCT user_id) FROM orders;").fetchone()[0]
        except Exception:
            total_buyers = 0
        non_buyers = max(total_users - total_buyers, 0)
        try:
            products = conn.execute("SELECT id, title FROM products WHERE is_active=1 ORDER BY title;").fetchall()
        except Exception:
            products = []
        try:
            categories = conn.execute("SELECT id, name FROM categories WHERE is_active=1 ORDER BY name;").fetchall()
        except Exception:
            categories = []
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
    <h1 class="text-2xl font-bold text-gray-800 mb-6">📢 پیام‌رسان</h1>

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


# ─────────────────────────── Auto Daily Backup ────────────────────────────

_BACKUP_DIR = "/tmp/stockland_backups"
_MAX_BACKUPS = 5
_auto_backup_started = False


def _do_auto_backup() -> None:
    """بکاپ خودکار روزانه — حداکثر ۵ فایل نگه می‌داره."""
    import os, shutil, glob
    db_path = _env("DB_PATH")
    if not db_path or not os.path.exists(db_path):
        return
    os.makedirs(_BACKUP_DIR, exist_ok=True)
    ts = _time.strftime("%Y%m%d_%H%M%S")
    dst = f"{_BACKUP_DIR}/auto_{ts}.sqlite"
    try:
        import sqlite3 as _sq
        src_c = _sq.connect(db_path, timeout=30)
        dst_c = _sq.connect(dst, timeout=30)
        src_c.backup(dst_c)
        dst_c.close()
        src_c.close()
    except Exception as ex:
        _tg_logger.error("Auto-backup failed: %s", ex)
        return

    # حذف بکاپ‌های قدیمی
    all_backups = sorted(glob.glob(f"{_BACKUP_DIR}/auto_*.sqlite"))
    while len(all_backups) > _MAX_BACKUPS:
        try:
            os.remove(all_backups.pop(0))
        except Exception:
            break
    _tg_logger.info("Auto-backup done: %s (total: %d)", dst, len(all_backups))


def _start_auto_backup_thread() -> None:
    global _auto_backup_started
    if _auto_backup_started:
        return
    _auto_backup_started = True

    def _runner():
        while True:
            _time.sleep(86400)  # هر ۲۴ ساعت
            try:
                _do_auto_backup()
            except Exception as ex:
                _tg_logger.error("auto-backup thread error: %s", ex)

    t = _threading.Thread(target=_runner, daemon=True, name="auto-backup")
    t.start()
    _tg_logger.info("Auto-backup scheduler started (every 24h, max %d files)", _MAX_BACKUPS)


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
    # اطلاع به کاربر
    try:
        _tg_send(
            int(uid),
            "✅ <b>درخواست نمایندگی شما تایید شد!</b>\n\n"
            "از این پس قیمت‌های ویژه همکار برای شما فعال است.\n"
            "منوی «پنل همکار» در دسترس شماست. 🤝"
        )
    except Exception:
        pass
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
    # اطلاع به کاربر
    try:
        _tg_send(
            int(uid),
            "❌ متأسفانه درخواست نمایندگی شما در این مرحله تأیید نشد.\n"
            "در صورت سوال با پشتیبانی در تماس باشید."
        )
    except Exception:
        pass
    return _redir("/admin/partners?flash=درخواست+رد+شد")
