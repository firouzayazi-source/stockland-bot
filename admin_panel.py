"""
admin_panel.py — پنل مدیریت وب استوک لند
────────────────────────────────────────
mount شده در /admin روی همان FastAPI که payment_service.py اجرا می‌کند.
هیچ وابستگی جدیدی ندارد — فقط python-multipart برای آپلود فایل.

متغیرهای محیطی لازم:
  ADMIN_WEB_PASSWORD  رمز ورود پنل
  SESSION_SECRET      کلید امنیتی (هر رشته تصادفی)
  DB_PATH             مسیر دیتابیس (از قبل ست شده)
"""

import hashlib
import hmac
import html
import os
import sqlite3
from datetime import date, datetime

from fastapi import APIRouter, Form, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse

router = APIRouter(prefix="/admin")

# ──────────────────────────────── config ────────────────────────────────────

def _env(k: str, default: str = "") -> str:
    return os.getenv(k) or default

def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(_env("DB_PATH"), timeout=30, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA busy_timeout=30000;")
    return conn

def _session_token() -> str:
    pw = _env("ADMIN_WEB_PASSWORD")
    secret = _env("SESSION_SECRET", "stockland-panel-secret")
    return hmac.new(secret.encode(), pw.encode(), hashlib.sha256).hexdigest()

def _is_auth(request: Request) -> bool:
    if not _env("ADMIN_WEB_PASSWORD"):
        return False
    return hmac.compare_digest(request.cookies.get("adm", ""), _session_token())

def _login_redirect() -> RedirectResponse:
    return RedirectResponse("/admin/login", status_code=303)

def _ok_redirect(path: str) -> RedirectResponse:
    return RedirectResponse(path, status_code=303)

# ──────────────────────────────── HTML core ──────────────────────────────────

def e(s) -> str:
    return html.escape(str(s or ""))

def _layout(title: str, body: str, flash: str = "", flash_ok: bool = True) -> HTMLResponse:
    flash_html = ""
    if flash:
        color = "green" if flash_ok else "red"
        flash_html = f"""
        <div class="mb-4 px-4 py-3 rounded-lg bg-{color}-50 border border-{color}-200 text-{color}-800 text-sm flex items-center gap-2">
          <span>{"✅" if flash_ok else "❌"}</span> {e(flash)}
        </div>"""

    return HTMLResponse(f"""<!DOCTYPE html>
<html lang="fa" dir="rtl">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{e(title)} — پنل ادمین استوک لند</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body {{ font-family: Tahoma, sans-serif; }}
    .table-auto th {{ background: #f1f5f9; }}
    input,textarea,select {{ outline: none; }}
    .nav-link {{ @apply text-indigo-200 hover:text-white text-sm transition; }}
  </style>
</head>
<body class="bg-slate-100 min-h-screen">

<!-- Navigation -->
<nav class="bg-indigo-900 text-white shadow-xl sticky top-0 z-50">
  <div class="max-w-7xl mx-auto px-4 py-3 flex items-center gap-5 flex-wrap text-sm">
    <a href="/admin/" class="font-bold text-lg text-white">🛍 استوک لند</a>
    <a href="/admin/" class="text-indigo-200 hover:text-white transition">📊 داشبورد</a>
    <a href="/admin/products" class="text-indigo-200 hover:text-white transition">📦 محصولات</a>
    <a href="/admin/feed" class="text-indigo-200 hover:text-white transition">🗃 موجودی</a>
    <a href="/admin/orders" class="text-indigo-200 hover:text-white transition">🧾 سفارش‌ها</a>
    <a href="/admin/wallets" class="text-indigo-200 hover:text-white transition">💰 کیف‌پول</a>
    <a href="/admin/partners" class="text-indigo-200 hover:text-white transition">🤝 همکاران</a>
    <a href="/admin/logout" class="mr-auto text-red-300 hover:text-red-100 transition">خروج ↩</a>
  </div>
</nav>

<!-- Main -->
<main class="max-w-7xl mx-auto px-4 py-6">
  {flash_html}
  {body}
</main>
</body>
</html>""")

def _card(title: str, value: str, sub: str = "", color: str = "indigo") -> str:
    return f"""
    <div class="bg-white rounded-xl shadow p-5 border-r-4 border-{color}-500">
      <div class="text-xs text-gray-500 mb-1">{e(title)}</div>
      <div class="text-3xl font-bold text-{color}-700">{value}</div>
      {f'<div class="text-xs text-gray-400 mt-1">{e(sub)}</div>' if sub else ""}
    </div>"""

def _btn(text: str, href: str = "", color: str = "indigo", small: bool = False) -> str:
    sz = "px-3 py-1.5 text-xs" if small else "px-4 py-2 text-sm"
    if href:
        return f'<a href="{e(href)}" class="{sz} bg-{color}-600 hover:bg-{color}-700 text-white rounded-lg font-medium transition inline-block">{text}</a>'
    return f'<button type="submit" class="{sz} bg-{color}-600 hover:bg-{color}-700 text-white rounded-lg font-medium transition">{text}</button>'

def _input(name: str, placeholder: str = "", value: str = "", type_: str = "text", required: bool = False) -> str:
    req = "required" if required else ""
    return f'<input type="{type_}" name="{name}" value="{e(value)}" placeholder="{e(placeholder)}" {req} class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">'

def _textarea(name: str, placeholder: str = "", value: str = "", rows: int = 6) -> str:
    return f'<textarea name="{name}" rows="{rows}" placeholder="{e(placeholder)}" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300 font-mono">{e(value)}</textarea>'

# ──────────────────────────────── LOGIN ─────────────────────────────────────

@router.get("/login", response_class=HTMLResponse)
async def login_get(request: Request, err: str = ""):
    if _is_auth(request):
        return _ok_redirect("/admin/")
    body = f"""
    <div class="min-h-screen flex items-center justify-center -mt-16">
      <div class="bg-white rounded-2xl shadow-xl p-8 w-full max-w-sm">
        <div class="text-center mb-6">
          <div class="text-4xl mb-2">🛍</div>
          <h1 class="text-xl font-bold text-gray-800">پنل مدیریت استوک لند</h1>
        </div>
        {f'<div class="mb-4 text-red-600 text-sm text-center bg-red-50 p-2 rounded-lg">❌ رمز اشتباه است</div>' if err else ""}
        <form method="post" action="/admin/login" class="space-y-4">
          <div>
            <label class="text-sm text-gray-600 block mb-1">رمز ورود</label>
            {_input("password", "رمز ورود پنل ادمین", type_="password", required=True)}
          </div>
          {_btn("ورود به پنل ←", color="indigo")}
        </form>
      </div>
    </div>"""
    return _layout("ورود", body)

@router.post("/login")
async def login_post(request: Request, password: str = Form(...)):
    expected = _env("ADMIN_WEB_PASSWORD")
    if not expected or not hmac.compare_digest(password.strip(), expected):
        return _ok_redirect("/admin/login?err=1")
    resp = _ok_redirect("/admin/")
    resp.set_cookie("adm", _session_token(), max_age=86400 * 7, httponly=True, samesite="lax")
    return resp

@router.get("/logout")
async def logout():
    resp = _ok_redirect("/admin/login")
    resp.delete_cookie("adm")
    return resp

# ──────────────────────────────── DASHBOARD ──────────────────────────────────

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        wallets = conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM wallets;").fetchone()
        orders = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders;").fetchone()
        products_active = conn.execute("SELECT COUNT(*) FROM products WHERE is_active=1;").fetchone()[0]
        feed_total = conn.execute("SELECT COUNT(*) FROM product_feed;").fetchone()[0]
        feed_avail = conn.execute("SELECT COUNT(*) FROM product_feed WHERE delivered=0;").fetchone()[0]
        pending = conn.execute("SELECT COUNT(*) FROM pending_deliveries WHERE status='pending';").fetchone()[0]
        partners_pending = conn.execute("SELECT COUNT(*) FROM partners WHERE status='pending';").fetchone()[0]
        today = date.today().isoformat()
        orders_today = conn.execute("SELECT COUNT(*), COALESCE(SUM(price),0) FROM orders WHERE created_at LIKE ?;", (today + "%",)).fetchone()

        # Low stock products
        low_stock = conn.execute("""
            SELECT p.id, p.title, p.category,
                   COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as avail,
                   COALESCE(fas.threshold, 5) as threshold
            FROM products p
            LEFT JOIN product_feed pf ON pf.product_id = p.id
            LEFT JOIN feed_alert_settings fas ON fas.product_id = p.id
            WHERE p.is_active = 1
            GROUP BY p.id
            HAVING avail <= threshold
            ORDER BY avail ASC
            LIMIT 10;
        """).fetchall()

        # Recent orders
        recent_orders = conn.execute("""
            SELECT o.id, o.user_id, o.title, o.price, o.created_at
            FROM orders o ORDER BY o.id DESC LIMIT 8;
        """).fetchall()
    finally:
        conn.close()

    low_rows = ""
    for r in low_stock:
        badge_color = "red" if int(r["avail"]) == 0 else "yellow"
        low_rows += f"""
        <tr class="hover:bg-gray-50 border-b">
          <td class="px-4 py-2 text-sm">{e(r["title"])}</td>
          <td class="px-4 py-2 text-sm text-gray-500">{e(r["category"])}</td>
          <td class="px-4 py-2">
            <span class="px-2 py-0.5 rounded-full text-xs font-medium bg-{badge_color}-100 text-{badge_color}-700">{r["avail"]} عدد</span>
          </td>
          <td class="px-4 py-2">{_btn("افزودن موجودی", f"/admin/feed/{r['id']}", "indigo", small=True)}</td>
        </tr>"""

    recent_rows = ""
    for o in recent_orders:
        recent_rows += f"""
        <tr class="hover:bg-gray-50 border-b text-sm">
          <td class="px-4 py-2 text-gray-400">#{o["id"]}</td>
          <td class="px-4 py-2">{e(o["title"])}</td>
          <td class="px-4 py-2 text-gray-500 text-xs"><code>{o["user_id"]}</code></td>
          <td class="px-4 py-2 font-medium text-green-700">{int(o["price"]):,} ت</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(o["created_at"] or "")[:16]}</td>
        </tr>"""

    body = f"""
    <h1 class="text-2xl font-bold text-gray-800 mb-6">📊 داشبورد</h1>

    <!-- Stats Cards -->
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {_card("سفارش‌های امروز", f'{int(orders_today[0]):,}', f'{int(orders_today[1]):,} تومان', "green")}
      {_card("کل فروش", f'{int(orders[1]):,}', f'{int(orders[0]):,} سفارش', "indigo")}
      {_card("موجودی فید", f'{feed_avail:,}', f'از {feed_total:,} کل', "blue")}
      {_card("کیف‌پول‌ها", f'{int(wallets[0]):,}', f'{int(wallets[1]):,} تومان کل', "purple")}
    </div>
    <div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
      {_card("محصولات فعال", str(products_active), "", "teal")}
      {_card("در صف تحویل", str(pending), "منتظر ارسال", "orange")}
      {_card("همکار در انتظار", str(partners_pending), "نیاز به بررسی", "yellow")}
      {_card("کاربران", str(int(wallets[0])), "با کیف‌پول", "slate")}
    </div>

    <div class="grid md:grid-cols-2 gap-6">
      <!-- Low Stock -->
      <div class="bg-white rounded-xl shadow p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-gray-700">⚠️ محصولات کم‌موجودی</h2>
          {_btn("مدیریت موجودی", "/admin/feed", "indigo", small=True)}
        </div>
        {"<p class='text-sm text-green-600'>✅ همه محصولات موجودی کافی دارند.</p>" if not low_stock else f"""
        <table class="w-full text-right">
          <thead><tr class="text-xs text-gray-500 border-b">
            <th class="px-4 py-2 text-right">محصول</th><th class="px-4 py-2 text-right">دسته</th>
            <th class="px-4 py-2 text-right">موجودی</th><th></th>
          </tr></thead>
          <tbody>{low_rows}</tbody>
        </table>"""}
      </div>

      <!-- Recent Orders -->
      <div class="bg-white rounded-xl shadow p-5">
        <div class="flex items-center justify-between mb-4">
          <h2 class="font-bold text-gray-700">🧾 آخرین سفارش‌ها</h2>
          {_btn("همه سفارش‌ها", "/admin/orders", "indigo", small=True)}
        </div>
        <table class="w-full text-right">
          <thead><tr class="text-xs text-gray-500 border-b">
            <th class="px-4 py-2">#</th><th class="px-4 py-2">محصول</th>
            <th class="px-4 py-2">کاربر</th><th class="px-4 py-2">مبلغ</th><th class="px-4 py-2">تاریخ</th>
          </tr></thead>
          <tbody>{"<tr><td colspan='5' class='text-center text-gray-400 py-4 text-sm'>سفارشی ثبت نشده</td></tr>" if not recent_orders else recent_rows}</tbody>
        </table>
      </div>
    </div>"""

    return _layout("داشبورد", body)

# ──────────────────────────────── PRODUCTS ───────────────────────────────────

@router.get("/products", response_class=HTMLResponse)
async def products_list(request: Request, flash: str = "", flash_ok: str = "1"):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        products = conn.execute("""
            SELECT p.*,
                   COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as feed_avail,
                   COUNT(pf.id) as feed_total
            FROM products p
            LEFT JOIN product_feed pf ON pf.product_id = p.id
            GROUP BY p.id ORDER BY p.category, p.id;
        """).fetchall()
    finally:
        conn.close()

    rows = ""
    for p in products:
        status_badge = '<span class="px-2 py-0.5 rounded-full text-xs bg-green-100 text-green-700">فعال</span>' if p["is_active"] else '<span class="px-2 py-0.5 rounded-full text-xs bg-red-100 text-red-700">غیرفعال</span>'
        avail = int(p["feed_avail"] or 0)
        avail_color = "red" if avail == 0 else ("yellow" if avail < 5 else "green")
        rows += f"""
        <tr class="hover:bg-gray-50 border-b">
          <td class="px-4 py-3 text-sm font-medium">{e(p["title"])}</td>
          <td class="px-4 py-3 text-sm text-gray-500">{e(p["category"])}</td>
          <td class="px-4 py-3 text-sm font-medium text-indigo-700">{int(p["price"]):,}</td>
          <td class="px-4 py-3">{status_badge}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded-full text-xs bg-{avail_color}-100 text-{avail_color}-700">{avail} / {int(p["feed_total"] or 0)}</span>
          </td>
          <td class="px-4 py-3 flex gap-2">
            {_btn("ویرایش", f"/admin/products/{p['id']}", "indigo", small=True)}
            {_btn("موجودی", f"/admin/feed/{p['id']}", "teal", small=True)}
          </td>
        </tr>"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">📦 مدیریت محصولات</h1>
      {_btn("➕ محصول جدید", "/admin/products/new", "green")}
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">عنوان</th><th class="px-4 py-3">دسته</th>
          <th class="px-4 py-3">قیمت (ت)</th><th class="px-4 py-3">وضعیت</th>
          <th class="px-4 py-3">موجودی</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{"<tr><td colspan='6' class='text-center text-gray-400 py-8'>محصولی ثبت نشده</td></tr>" if not products else rows}</tbody>
      </table>
    </div>"""

    return _layout("محصولات", body, flash=flash, flash_ok=flash == "" or flash_ok == "1")

@router.get("/products/new", response_class=HTMLResponse)
async def product_new_get(request: Request):
    if not _is_auth(request):
        return _login_redirect()

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
      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">عنوان محصول</label>
        {_input("title", "مثال: اپل آیدی آماده ریجن آمریکا", required=True)}
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">قیمت (تومان)</label>
          {_input("price", "مثال: 250000", type_="number", required=True)}
        </div>
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">قیمت همکار (0 = یکسان)</label>
          {_input("partner_price", "0", type_="number")}
        </div>
      </div>
      <div class="grid grid-cols-2 gap-4">
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه مشتری (0 = نامحدود)</label>
          {_input("limit_c", "0", type_="number")}
        </div>
        <div>
          <label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه همکار (0 = نامحدود)</label>
          {_input("limit_p", "0", type_="number")}
        </div>
      </div>
      <div>
        <label class="text-sm font-medium text-gray-700 block mb-1">توضیحات</label>
        {_textarea("description", "توضیحات محصول...", rows=3)}
      </div>
      <div class="flex gap-3 pt-2">
        {_btn("ذخیره محصول", color="green")}
        {_btn("انصراف", "/admin/products", "slate")}
      </div>
    </form>"""

    return _layout("محصول جدید", body)

@router.post("/products/new")
async def product_new_post(request: Request,
    category: str = Form(""), title: str = Form(""), price: str = Form("0"),
    partner_price: str = Form("0"), limit_c: str = Form("0"), limit_p: str = Form("0"),
    description: str = Form("")):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        slug = "".join(c if c.isalnum() else "_" for c in title).lower()[:40] or "product"
        pp = int(partner_price or 0)
        conn.execute("""
            INSERT INTO products (category, product_key, title, price, partner_price,
                daily_limit_customer, daily_limit_partner, description, is_active)
            VALUES (?,?,?,?,?,?,?,?,1);
        """, (category.strip(), slug, title.strip(), int(price or 0),
              pp if pp > 0 else None, int(limit_c or 0), int(limit_p or 0), description.strip()))
        conn.commit()
    finally:
        conn.close()

    return _ok_redirect("/admin/products?flash=محصول+جدید+اضافه+شد")

@router.get("/products/{pid}", response_class=HTMLResponse)
async def product_edit_get(request: Request, pid: int, flash: str = ""):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        p = conn.execute("SELECT * FROM products WHERE id=?;", (pid,)).fetchone()
        services = conn.execute("SELECT service_key, title FROM other_services ORDER BY title;").fetchall()
        feed_stats = conn.execute("""
            SELECT COUNT(*) as total,
                   COUNT(CASE WHEN delivered=0 THEN 1 END) as avail
            FROM product_feed WHERE product_id=?;
        """, (pid,)).fetchone()
    finally:
        conn.close()

    if not p:
        return _ok_redirect("/admin/products?flash=محصول+یافت+نشد&flash_ok=0")

    cats = ""
    for s in [("apple", "سرویس‌های اپل آیدی")] + [(r["service_key"], r["title"]) for r in services]:
        sel = "selected" if s[0] == p["category"] else ""
        cats += f'<option value="{e(s[0])}" {sel}>{e(s[1])} ({e(s[0])})</option>'

    status_label = "فعال ✅" if p["is_active"] else "غیرفعال ❌"

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/products", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">✏️ ویرایش محصول #{pid}</h1>
      <span class="text-sm text-gray-400">({status_label})</span>
    </div>

    <div class="grid md:grid-cols-3 gap-6">
      <!-- Edit Form -->
      <div class="md:col-span-2">
        <form method="post" action="/admin/products/{pid}/edit" class="bg-white rounded-xl shadow p-6 space-y-4">
          <div>
            <label class="text-sm font-medium text-gray-700 block mb-1">دسته‌بندی</label>
            <select name="category" class="w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:ring-2 focus:ring-indigo-300">
              {cats}
            </select>
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700 block mb-1">عنوان</label>
            {_input("title", "", str(p["title"] or ""), required=True)}
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-gray-700 block mb-1">قیمت (تومان)</label>
              {_input("price", "", str(p["price"] or 0), "number", required=True)}
            </div>
            <div>
              <label class="text-sm font-medium text-gray-700 block mb-1">قیمت همکار (0 = یکسان)</label>
              {_input("partner_price", "0", str(p["partner_price"] or 0), "number")}
            </div>
          </div>
          <div class="grid grid-cols-2 gap-4">
            <div>
              <label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه مشتری</label>
              {_input("limit_c", "0", str(p["daily_limit_customer"] or 0), "number")}
            </div>
            <div>
              <label class="text-sm font-medium text-gray-700 block mb-1">سقف روزانه همکار</label>
              {_input("limit_p", "0", str(p["daily_limit_partner"] or 0), "number")}
            </div>
          </div>
          <div>
            <label class="text-sm font-medium text-gray-700 block mb-1">توضیحات</label>
            {_textarea("description", "", str(p["description"] or ""), rows=3)}
          </div>
          <div class="flex gap-3 pt-2">
            {_btn("ذخیره تغییرات", color="green")}
          </div>
        </form>
      </div>

      <!-- Sidebar Actions -->
      <div class="space-y-4">
        <div class="bg-white rounded-xl shadow p-5">
          <h3 class="font-bold text-gray-700 mb-3">📦 موجودی</h3>
          <div class="text-3xl font-bold text-indigo-700 mb-1">{int(feed_stats["avail"] or 0)}</div>
          <div class="text-xs text-gray-400 mb-3">از {int(feed_stats["total"] or 0)} آیتم کل</div>
          {_btn("مدیریت موجودی →", f"/admin/feed/{pid}", "teal")}
        </div>

        <div class="bg-white rounded-xl shadow p-5 space-y-3">
          <h3 class="font-bold text-gray-700 mb-3">⚡️ عملیات سریع</h3>
          <form method="post" action="/admin/products/{pid}/toggle">
            <button type="submit" class="w-full py-2 text-sm rounded-lg border-2 border-{"red" if p["is_active"] else "green"}-300 text-{"red" if p["is_active"] else "green"}-700 hover:bg-{"red" if p["is_active"] else "green"}-50 transition font-medium">
              {"🔴 غیرفعال کردن" if p["is_active"] else "🟢 فعال کردن"}
            </button>
          </form>
          <form method="post" action="/admin/products/{pid}/delete"
            onsubmit="return confirm('آیا از حذف این محصول مطمئنید؟ موجودی‌ها هم پاک می‌شوند.');">
            <button type="submit" class="w-full py-2 text-sm rounded-lg border-2 border-red-200 text-red-600 hover:bg-red-50 transition">
              🗑 حذف محصول
            </button>
          </form>
        </div>
      </div>
    </div>"""

    return _layout(f"ویرایش محصول #{pid}", body, flash=flash)

@router.post("/products/{pid}/edit")
async def product_edit_post(request: Request, pid: int,
    category: str = Form(""), title: str = Form(""), price: str = Form("0"),
    partner_price: str = Form("0"), limit_c: str = Form("0"), limit_p: str = Form("0"),
    description: str = Form("")):
    if not _is_auth(request):
        return _login_redirect()
    pp = int(partner_price or 0)
    conn = _db()
    try:
        conn.execute("""
            UPDATE products SET category=?, title=?, price=?, partner_price=?,
                daily_limit_customer=?, daily_limit_partner=?, description=?
            WHERE id=?;
        """, (category, title.strip(), int(price or 0), pp if pp > 0 else None,
              int(limit_c or 0), int(limit_p or 0), description.strip(), pid))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect(f"/admin/products/{pid}?flash=تغییرات+ذخیره+شد")

@router.post("/products/{pid}/toggle")
async def product_toggle(request: Request, pid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        conn.execute("UPDATE products SET is_active = CASE WHEN is_active=1 THEN 0 ELSE 1 END WHERE id=?;", (pid,))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect(f"/admin/products/{pid}?flash=وضعیت+تغییر+کرد")

@router.post("/products/{pid}/delete")
async def product_delete(request: Request, pid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        conn.execute("DELETE FROM product_feed WHERE product_id=?;", (pid,))
        conn.execute("DELETE FROM products WHERE id=?;", (pid,))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect("/admin/products?flash=محصول+حذف+شد")

# ──────────────────────────────── FEED ───────────────────────────────────────

@router.get("/feed", response_class=HTMLResponse)
async def feed_overview(request: Request):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        products = conn.execute("""
            SELECT p.id, p.title, p.category, p.is_active,
                   COUNT(pf.id) as total,
                   COUNT(CASE WHEN pf.delivered=0 THEN 1 END) as avail,
                   COALESCE(fas.threshold, 5) as threshold
            FROM products p
            LEFT JOIN product_feed pf ON pf.product_id = p.id
            LEFT JOIN feed_alert_settings fas ON fas.product_id = p.id
            GROUP BY p.id
            ORDER BY avail ASC, p.category, p.title;
        """).fetchall()
    finally:
        conn.close()

    rows = ""
    for p in products:
        avail = int(p["avail"] or 0)
        total = int(p["total"] or 0)
        pct = int(avail / max(total, 1) * 100)
        bar_color = "red" if avail == 0 else ("yellow" if avail <= int(p["threshold"]) else "green")
        rows += f"""
        <tr class="hover:bg-gray-50 border-b">
          <td class="px-4 py-3 font-medium text-sm">{e(p["title"])}</td>
          <td class="px-4 py-3 text-sm text-gray-400">{e(p["category"])}</td>
          <td class="px-4 py-3">
            <div class="flex items-center gap-2">
              <div class="flex-1 bg-gray-100 rounded-full h-2">
                <div class="bg-{bar_color}-500 h-2 rounded-full" style="width:{pct}%"></div>
              </div>
              <span class="text-sm font-medium w-16 text-{bar_color}-700">{avail} / {total}</span>
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

    return _layout("مدیریت موجودی", body)

@router.get("/feed/{pid}", response_class=HTMLResponse)
async def feed_detail(request: Request, pid: int, page: int = 0, flash: str = ""):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        product = conn.execute("SELECT * FROM products WHERE id=?;", (pid,)).fetchone()
        if not product:
            return _ok_redirect("/admin/feed")

        PAGE = 20
        total = conn.execute("SELECT COUNT(*) FROM product_feed WHERE product_id=?;", (pid,)).fetchone()[0]
        avail = conn.execute("SELECT COUNT(*) FROM product_feed WHERE product_id=? AND delivered=0;", (pid,)).fetchone()[0]
        items = conn.execute("""
            SELECT id, data, delivered, created_at FROM product_feed
            WHERE product_id=? ORDER BY id DESC LIMIT ? OFFSET ?;
        """, (pid, PAGE, page * PAGE)).fetchall()
    finally:
        conn.close()

    pages = max((total + PAGE - 1) // PAGE, 1)

    items_html = ""
    for item in items:
        preview = str(item["data"] or "")
        first_line = preview.splitlines()[0][:80] if preview else "---"
        badge = '<span class="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-700">تحویل‌شده</span>' if item["delivered"] else '<span class="px-2 py-0.5 text-xs rounded-full bg-blue-100 text-blue-700">موجود</span>'
        items_html += f"""
        <tr class="hover:bg-gray-50 border-b text-sm">
          <td class="px-4 py-2 text-gray-400 font-mono">#{item["id"]}</td>
          <td class="px-4 py-2 font-mono text-xs text-gray-700 max-w-xs truncate">{e(first_line)}</td>
          <td class="px-4 py-2">{badge}</td>
          <td class="px-4 py-2 text-gray-400 text-xs">{(item["created_at"] or "")[:10]}</td>
          <td class="px-4 py-2">
            <form method="post" action="/admin/feed/item/{item['id']}/delete" onsubmit="return confirm('حذف شود؟')">
              <button class="text-red-400 hover:text-red-600 text-xs">حذف</button>
            </form>
          </td>
        </tr>"""

    pager = ""
    if pages > 1:
        pager = '<div class="flex gap-2 mt-4 justify-center">'
        for i in range(pages):
            active = "bg-indigo-600 text-white" if i == page else "bg-white text-gray-600 hover:bg-gray-50"
            pager += f'<a href="/admin/feed/{pid}?page={i}" class="px-3 py-1 rounded border text-sm {active}">{i+1}</a>'
        pager += '</div>'

    body = f"""
    <div class="flex items-center gap-3 mb-6">
      {_btn("← بازگشت", "/admin/feed", "slate", small=True)}
      <h1 class="text-2xl font-bold text-gray-800">🗃 موجودی: {e(product["title"])}</h1>
    </div>

    <div class="grid grid-cols-3 gap-4 mb-6">
      {_card("کل آیتم‌ها", str(total), "", "slate")}
      {_card("موجود", str(avail), "در صف تحویل", "green")}
      {_card("تحویل‌شده", str(total - avail), "", "indigo")}
    </div>

    <!-- Upload Form -->
    <div class="bg-white rounded-xl shadow p-6 mb-6">
      <h2 class="font-bold text-gray-700 mb-4">➕ افزودن موجودی جدید</h2>
      <form method="post" action="/admin/feed/{pid}/upload" class="space-y-3">
        <div class="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
          هر خط = یک آیتم | برای آیتم چندخطی، بین هر آیتم <code class="bg-gray-200 px-1 rounded">***</code> بزنید
        </div>
        {_textarea("items", "آیتم‌ها را اینجا paste کنید...", rows=8)}
        {_btn("افزودن موجودی", color="green")}
      </form>
    </div>

    <!-- Items Table -->
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50 flex items-center justify-between">
        <span class="text-sm font-medium text-gray-700">لیست آیتم‌ها ({total} عدد)</span>
        <form method="post" action="/admin/feed/{pid}/clear-delivered"
          onsubmit="return confirm('تمام آیتم‌های تحویل‌شده حذف شوند؟')">
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

    return _layout(f"موجودی #{pid}", body, flash=flash)

@router.post("/feed/{pid}/upload")
async def feed_upload(request: Request, pid: int, items: str = Form("")):
    if not _is_auth(request):
        return _login_redirect()

    import re
    raw = items.strip()
    delim_re = re.compile(r"^\s*\*{3,}\s*$", re.MULTILINE)

    if re.search(delim_re, raw):
        blocks = [b.strip() for b in delim_re.split(raw) if b.strip()]
    else:
        blocks = [ln.strip() for ln in raw.splitlines() if ln.strip()]

    if not blocks:
        return _ok_redirect(f"/admin/feed/{pid}?flash=آیتمی+یافت+نشد&flash_ok=0")

    now = datetime.utcnow().isoformat()
    conn = _db()
    try:
        conn.executemany(
            "INSERT INTO product_feed (product_id, data, delivered, created_at) VALUES (?,?,0,?);",
            [(pid, b, now) for b in blocks]
        )
        # Reset alert
        conn.execute(
            "INSERT INTO feed_alert_settings (product_id, threshold, last_notified_remaining, updated_at) VALUES (?,5,NULL,?) "
            "ON CONFLICT(product_id) DO UPDATE SET last_notified_remaining=NULL, updated_at=excluded.updated_at;",
            (pid, now)
        )
        conn.commit()
    finally:
        conn.close()

    return _ok_redirect(f"/admin/feed/{pid}?flash={len(blocks)}+آیتم+اضافه+شد")

@router.post("/feed/{pid}/clear-delivered")
async def feed_clear_delivered(request: Request, pid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        r = conn.execute("DELETE FROM product_feed WHERE product_id=? AND delivered=1;", (pid,))
        conn.commit()
        n = r.rowcount
    finally:
        conn.close()
    return _ok_redirect(f"/admin/feed/{pid}?flash={n}+آیتم+حذف+شد")

@router.post("/feed/item/{fid}/delete")
async def feed_item_delete(request: Request, fid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        row = conn.execute("SELECT product_id FROM product_feed WHERE id=?;", (fid,)).fetchone()
        pid = row["product_id"] if row else 0
        conn.execute("DELETE FROM product_feed WHERE id=?;", (fid,))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect(f"/admin/feed/{pid}?flash=آیتم+حذف+شد")

# ──────────────────────────────── ORDERS ─────────────────────────────────────

@router.get("/orders", response_class=HTMLResponse)
async def orders_list(request: Request, page: int = 0, q: str = ""):
    if not _is_auth(request):
        return _login_redirect()

    PAGE = 30
    conn = _db()
    try:
        where = "WHERE o.user_id LIKE ?" if q else ""
        params_q = (f"%{q}%",) if q else ()
        total = conn.execute(f"SELECT COUNT(*) FROM orders o {where};", params_q).fetchone()[0]
        orders = conn.execute(f"""
            SELECT o.id, o.user_id, o.title, o.price, o.created_at, o.buyer_type
            FROM orders o {where}
            ORDER BY o.id DESC LIMIT ? OFFSET ?;
        """, params_q + (PAGE, page * PAGE)).fetchall()
    finally:
        conn.close()

    pages = max((total + PAGE - 1) // PAGE, 1)

    rows = ""
    for o in orders:
        badge = '<span class="px-1.5 py-0.5 text-xs rounded bg-purple-100 text-purple-700">همکار</span>' if o["buyer_type"] == "partner" else ""
        rows += f"""
        <tr class="hover:bg-gray-50 border-b text-sm">
          <td class="px-4 py-2.5 text-gray-400">#{o["id"]}</td>
          <td class="px-4 py-2.5 font-mono text-xs"><code>{e(o["user_id"])}</code></td>
          <td class="px-4 py-2.5">{e(o["title"])} {badge}</td>
          <td class="px-4 py-2.5 font-medium text-green-700">{int(o["price"]):,} ت</td>
          <td class="px-4 py-2.5 text-gray-400 text-xs">{(o["created_at"] or "")[:16]}</td>
        </tr>"""

    pager = '<div class="flex gap-2 mt-4 justify-center">' + "".join(
        f'<a href="/admin/orders?page={i}" class="px-3 py-1 rounded border text-sm {"bg-indigo-600 text-white" if i==page else "bg-white text-gray-600"}">{i+1}</a>'
        for i in range(min(pages, 10))
    ) + "</div>" if pages > 1 else ""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">🧾 سفارش‌ها ({total:,})</h1>
      <form method="get" action="/admin/orders" class="flex gap-2">
        {_input("q", "جستجو User ID...", q)}
        {_btn("جستجو", color="slate", small=True)}
      </form>
    </div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">#</th><th class="px-4 py-3">User ID</th>
          <th class="px-4 py-3">محصول</th><th class="px-4 py-3">مبلغ</th><th class="px-4 py-3">تاریخ</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='5' class='text-center py-8 text-gray-400'>سفارشی ثبت نشده</td></tr>"}</tbody>
      </table>
      {pager}
    </div>"""

    return _layout("سفارش‌ها", body)

# ──────────────────────────────── WALLETS ────────────────────────────────────

@router.get("/wallets", response_class=HTMLResponse)
async def wallets_list(request: Request, q: str = "", flash: str = ""):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        where = "WHERE user_id = ?" if q else ""
        params = (int(q),) if q and q.isdigit() else ()
        wallets = conn.execute(f"""
            SELECT user_id, balance, updated_at FROM wallets {where}
            ORDER BY balance DESC LIMIT 50;
        """, params).fetchall()
        totals = conn.execute("SELECT COUNT(*), COALESCE(SUM(balance),0) FROM wallets;").fetchone()
    finally:
        conn.close()

    rows = ""
    for w in wallets:
        rows += f"""
        <tr class="hover:bg-gray-50 border-b text-sm">
          <td class="px-4 py-2.5 font-mono"><code>{e(w["user_id"])}</code></td>
          <td class="px-4 py-2.5 font-bold text-{"red" if int(w["balance"])==0 else "green"}-700">{int(w["balance"]):,} ت</td>
          <td class="px-4 py-2.5 text-gray-400 text-xs">{(w["updated_at"] or "")[:16]}</td>
          <td class="px-4 py-2.5">
            <a href="/admin/wallets/adjust?uid={w['user_id']}" class="text-indigo-500 hover:text-indigo-700 text-xs">تنظیم</a>
          </td>
        </tr>"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">💰 کیف‌پول‌ها</h1>
      <div class="text-sm text-gray-500">{int(totals[0])} کاربر | جمع: {int(totals[1]):,} تومان</div>
    </div>

    <div class="bg-white rounded-xl shadow p-5 mb-6">
      <h2 class="font-bold text-gray-700 mb-3">تنظیم کیف‌پول کاربر</h2>
      <form method="post" action="/admin/wallets/adjust" class="flex gap-3 items-end flex-wrap">
        <div>
          <label class="text-xs text-gray-500 block mb-1">User ID</label>
          {_input("uid", "آیدی عددی کاربر", type_="number", required=True)}
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">مبلغ (تومان)</label>
          {_input("amount", "مثال: 50000", type_="number", required=True)}
        </div>
        <div>
          <label class="text-xs text-gray-500 block mb-1">عملیات</label>
          <select name="op" class="border border-gray-300 rounded-lg px-3 py-2 text-sm">
            <option value="add">افزودن ➕</option>
            <option value="sub">کاهش ➖</option>
            <option value="set">تنظیم مستقیم ✏️</option>
          </select>
        </div>
        {_btn("اعمال", color="indigo")}
      </form>
    </div>

    <div class="bg-white rounded-xl shadow overflow-hidden">
      <div class="px-5 py-3 border-b bg-gray-50 flex items-center gap-3">
        <span class="font-medium text-gray-700 text-sm">کاربران</span>
        <form method="get" action="/admin/wallets" class="flex gap-2">
          {_input("q", "جستجو User ID...", q)}
          {_btn("جستجو", color="slate", small=True)}
        </form>
      </div>
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b">
          <th class="px-4 py-2">User ID</th><th class="px-4 py-2">موجودی</th>
          <th class="px-4 py-2">آخرین آپدیت</th><th></th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='4' class='text-center py-8 text-gray-400'>کاربری یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("کیف‌پول‌ها", body, flash=flash)

@router.post("/wallets/adjust")
async def wallet_adjust(request: Request, uid: str = Form(""), amount: str = Form("0"), op: str = Form("add")):
    if not _is_auth(request):
        return _login_redirect()
    try:
        user_id = int(uid)
        amt = int(amount)
    except ValueError:
        return _ok_redirect("/admin/wallets?flash=مقادیر+نامعتبر&flash_ok=0")

    conn = _db()
    try:
        now = datetime.utcnow().isoformat()
        row = conn.execute("SELECT balance FROM wallets WHERE user_id=?;", (user_id,)).fetchone()
        cur = int(row["balance"] if row else 0)

        if op == "add":
            new_bal = cur + amt
        elif op == "sub":
            new_bal = max(0, cur - amt)
        else:
            new_bal = amt

        conn.execute("""
            INSERT INTO wallets (user_id, balance, updated_at) VALUES (?,?,?)
            ON CONFLICT(user_id) DO UPDATE SET balance=excluded.balance, updated_at=excluded.updated_at;
        """, (user_id, new_bal, now))
        conn.commit()
    finally:
        conn.close()

    return _ok_redirect(f"/admin/wallets?flash=موجودی+{user_id}+به+{new_bal:,}+تومان+تنظیم+شد")

# ──────────────────────────────── PARTNERS ───────────────────────────────────

@router.get("/partners", response_class=HTMLResponse)
async def partners_list(request: Request, status_filter: str = "", flash: str = ""):
    if not _is_auth(request):
        return _login_redirect()

    conn = _db()
    try:
        where = "WHERE status=?" if status_filter else ""
        partners = conn.execute(f"""
            SELECT * FROM partners {where} ORDER BY
            CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END,
            id DESC LIMIT 100;
        """, (status_filter,) if status_filter else ()).fetchall()
    finally:
        conn.close()

    tabs = ""
    for label, val in [("همه", ""), ("در انتظار", "pending"), ("تایید شده", "approved"), ("رد شده", "rejected")]:
        active = "bg-indigo-600 text-white" if status_filter == val else "bg-white text-gray-600 hover:bg-gray-50"
        tabs += f'<a href="/admin/partners?status_filter={val}" class="px-4 py-2 rounded-lg border text-sm {active} transition">{label}</a>'

    rows = ""
    for p in partners:
        st = p["status"] or "pending"
        badge_colors = {"pending": "yellow", "approved": "green", "rejected": "red"}
        badge_labels = {"pending": "در انتظار", "approved": "تایید", "rejected": "رد شده"}
        bc = badge_colors.get(st, "gray")
        bl = badge_labels.get(st, st)
        rows += f"""
        <tr class="hover:bg-gray-50 border-b text-sm">
          <td class="px-4 py-3 font-mono text-xs"><code>{e(p["tg_user_id"])}</code></td>
          <td class="px-4 py-3">{e(p["full_name"])}</td>
          <td class="px-4 py-3 text-gray-500">{e(p["phone"])}</td>
          <td class="px-4 py-3 text-gray-400 text-xs">{e(p["city"])} | {e(p["shop_name"])}</td>
          <td class="px-4 py-3">
            <span class="px-2 py-0.5 rounded-full text-xs bg-{bc}-100 text-{bc}-700">{bl}</span>
          </td>
          <td class="px-4 py-3 flex gap-2">
            {f'''
            <form method="post" action="/admin/partners/{p["tg_user_id"]}/approve">
              <button class="px-2 py-1 text-xs bg-green-100 text-green-700 rounded hover:bg-green-200">✅ تایید</button>
            </form>
            <form method="post" action="/admin/partners/{p["tg_user_id"]}/reject">
              <button class="px-2 py-1 text-xs bg-red-100 text-red-700 rounded hover:bg-red-200">❌ رد</button>
            </form>''' if st == "pending" else ""}
          </td>
        </tr>"""

    body = f"""
    <div class="flex items-center justify-between mb-6">
      <h1 class="text-2xl font-bold text-gray-800">🤝 درخواست‌های همکار</h1>
    </div>
    <div class="flex gap-2 mb-4">{tabs}</div>
    <div class="bg-white rounded-xl shadow overflow-hidden">
      <table class="w-full text-right">
        <thead><tr class="text-xs text-gray-500 border-b bg-gray-50">
          <th class="px-4 py-3">User ID</th><th class="px-4 py-3">نام</th>
          <th class="px-4 py-3">شماره</th><th class="px-4 py-3">شهر | فروشگاه</th>
          <th class="px-4 py-3">وضعیت</th><th class="px-4 py-3">عملیات</th>
        </tr></thead>
        <tbody>{rows or "<tr><td colspan='6' class='text-center py-8 text-gray-400'>درخواستی یافت نشد</td></tr>"}</tbody>
      </table>
    </div>"""

    return _layout("همکاران", body, flash=flash)

@router.post("/partners/{uid}/approve")
async def partner_approve(request: Request, uid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        conn.execute("UPDATE partners SET status='approved', approved_at=? WHERE tg_user_id=?;",
                     (datetime.utcnow().isoformat(), uid))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect("/admin/partners?flash=همکار+تایید+شد")

@router.post("/partners/{uid}/reject")
async def partner_reject(request: Request, uid: int):
    if not _is_auth(request):
        return _login_redirect()
    conn = _db()
    try:
        conn.execute("UPDATE partners SET status='rejected' WHERE tg_user_id=?;", (uid,))
        conn.commit()
    finally:
        conn.close()
    return _ok_redirect("/admin/partners?flash=درخواست+رد+شد")
