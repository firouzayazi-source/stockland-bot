"""سرویس محصولات — منطق خالص."""
from typing import Optional


def list_products(category: str = "", active_only: bool = True, limit: int = 100, q: str = "") -> list:
    """لیست محصولات با قیمت مؤثر (فلش‌سیل اعمال‌شده)."""
    import db
    from db import _get_connection, ensure_product_support_schema
    ensure_product_support_schema()
    conn = _get_connection()
    try:
        where, params = [], []
        if active_only:
            where.append("COALESCE(is_active,1)=1")
        if category:
            where.append("category=?")
            params.append(category)
        if q:
            where.append("(title LIKE ? OR description LIKE ?)")
            like = f"%{q}%"
            params.append(like)
            params.append(like)
        w = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT id, category, title, price, description, is_active, "
            f"COALESCE(partner_price,0) AS partner_price, COALESCE(image_url,'') AS image_url, "
            f"COALESCE(notify_on_restock,0) AS notify_on_restock "
            f"FROM products {w} ORDER BY id DESC LIMIT ?;",
            (*params, limit)).fetchall()
        # سه کوئری batch به‌جای سه کوئری جدا به‌ازای هر محصول (رفع N+1 — بخش ۲۰
        # فاز ۲ ممیزی): قبلاً هر ردیف یعنی یک کانکشن/کوئری جدا برای امتیاز، فروش
        # فوری، و موجودی — با limit=100 یعنی تا ۳۰۰ رفت‌وبرگشت اضافه به دیتابیس.
        ids = [int(r["id"]) for r in rows]
        ratings = db.batch_product_ratings(ids)
        flash_pcts = db.batch_flash_percents(ids)
        stocks = db.batch_available_stock(ids)
        out = []
        for r in rows:
            pid = int(r["id"])
            base = int(r["price"] or 0)
            pct = flash_pcts.get(pid)
            eff = max(0, base - base * pct // 100) if pct is not None else base
            rating = ratings.get(pid, {"count": 0, "avg": 0})
            out.append({
                "id": pid, "category": r["category"],
                "title": r["title"], "price": base,
                "effective_price": int(eff),
                "flash_active": pct is not None,
                "partner_price": int(r["partner_price"] or 0),
                "description": r["description"] or "",
                "image_url": r["image_url"] or "",
                "rating_avg": rating.get("avg", 0),
                "rating_count": rating.get("count", 0),
                "stock": stocks.get(pid, 0),
                "notify_on_restock": bool(r["notify_on_restock"]),
            })
        return out
    finally:
        conn.close()


def get_product(pid: int, uid: int = None) -> Optional[dict]:
    """جزئیات یک محصول + موجودی + امتیاز/نظرات.

    اگه uid داده بشه و کاربر همکارِ تأییدشده باشه، قیمت همکاری هم (طبق همون منطق
    بات — bot.py:_show_order_summary) به‌عنوان یه فیلد جدا برمی‌گرده تا صفحهٔ محصول
    مینی‌اپ بتونه هر دو قیمت رو نشون بده. طی فروش فوری قیمت همکاری نشون داده نمی‌شه
    (دقیقاً مثل بات) چون این دو تخفیف با هم قابل‌جمع نیستن."""
    import db
    p = db.get_product_by_id(pid)
    if not p:
        return None
    from db import apply_flash_price, get_feed_stats, get_product_rating, get_product_ratings_list, is_partner_approved
    base = int(p["price"] or 0)
    eff, flash = apply_flash_price(pid, base)
    partner_price = int(p.get("partner_price") or 0)
    show_partner_price = bool(
        uid and not flash and is_partner_approved(uid)
        and partner_price > 0 and partner_price < base
    )
    try:
        _t, remaining, _d = get_feed_stats(pid)
    except Exception:
        remaining = 0
    try:
        rating = get_product_rating(pid)
    except Exception:
        rating = {"count": 0, "avg": 0}
    try:
        reviews = [{"rating": int(r["rating"]), "comment": r["comment"] or "",
                    "created_at": r["created_at"], "name": (r.get("full_name") or "").strip() or "کاربر استوک‌لند"}
                   for r in get_product_ratings_list(pid, limit=5) if (r.get("comment") or "").strip()]
    except Exception:
        reviews = []
    related = [r for r in list_products(category=p.get("category") or "", limit=7) if r["id"] != pid][:6]
    return {
        "id": int(p["id"]), "category": p.get("category"),
        "title": p["title"], "price": base,
        "effective_price": int(eff), "flash_active": bool(flash),
        "partner_price": partner_price,
        "show_partner_price": show_partner_price,
        "description": p.get("description") or "",
        "is_active": bool(p.get("is_active", 1)),
        "stock": int(remaining),
        "notify_on_restock": bool(p.get("notify_on_restock") or 0),
        "require_terms": bool(p.get("require_terms") or 0),
        "terms_text": db.get_product_terms_text(pid) if p.get("require_terms") else "",
        "image_url": p.get("image_url") or "",
        "rating_avg": rating.get("avg", 0),
        "rating_count": rating.get("count", 0),
        "reviews": reviews,
        "related": related,
    }


def favorite_products(user_id: int, limit: int = 100, offset: int = 0) -> list:
    """محصولات علاقه‌مندی کاربر — فقط فعال‌ها، جدیدترین اول.
    limit/offset برای ثبات با بقیهٔ endpoint های لیستی — فعلاً حجم علاقه‌مندی هر
    کاربر طبیعتاً محدوده، ولی همون الگو رعایت می‌شه."""
    import db
    from db import get_favorite_ids, ensure_product_support_schema
    ids = get_favorite_ids(user_id)
    if not ids:
        return []
    ensure_product_support_schema()
    conn = db._get_connection()
    try:
        # ids از get_favorite_ids یه set بدون ترتیبه — LIMIT/OFFSET باید روی همون
        # کوئری مرتب‌شدهٔ نهایی (id DESC) اعمال بشه، نه با slice کردن خودِ set
        # (که ترتیبش دلخواه/غیرقطعیه و صفحه‌بندی رو خراب می‌کنه).
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, category, title, price, description, is_active, COALESCE(image_url,'') AS image_url "
            f"FROM products WHERE id IN ({placeholders}) AND COALESCE(is_active,1)=1 "
            f"ORDER BY id DESC LIMIT ? OFFSET ?;", tuple(ids) + (limit, offset)).fetchall()
        row_ids = [int(r["id"]) for r in rows]
        ratings = db.batch_product_ratings(row_ids)
        flash_pcts = db.batch_flash_percents(row_ids)
        out = []
        for r in rows:
            pid = int(r["id"])
            base = int(r["price"] or 0)
            pct = flash_pcts.get(pid)
            eff = max(0, base - base * pct // 100) if pct is not None else base
            rating = ratings.get(pid, {"count": 0, "avg": 0})
            out.append({
                "id": pid, "category": r["category"], "title": r["title"],
                "price": base, "effective_price": int(eff), "flash_active": pct is not None,
                "description": r["description"] or "", "image_url": r["image_url"] or "",
                "rating_avg": rating.get("avg", 0), "rating_count": rating.get("count", 0),
            })
        return out
    finally:
        conn.close()
