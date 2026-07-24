"""سرویس محصولات — منطق خالص."""
from typing import Optional


def list_products(category: str = "", active_only: bool = True, limit: int = 100, q: str = "") -> list:
    """لیست محصولات با قیمت مؤثر (فلش‌سیل اعمال‌شده)."""
    import db
    from db import _get_connection, apply_flash_price
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
            f"COALESCE(partner_price,0) AS partner_price "
            f"FROM products {w} ORDER BY id DESC LIMIT ?;",
            (*params, limit)).fetchall()
        from db import get_product_rating
        out = []
        for r in rows:
            base = int(r["price"] or 0)
            eff, flash = apply_flash_price(int(r["id"]), base)
            try:
                rating = get_product_rating(int(r["id"]))
            except Exception:
                rating = {"count": 0, "avg": 0}
            out.append({
                "id": int(r["id"]), "category": r["category"],
                "title": r["title"], "price": base,
                "effective_price": int(eff),
                "flash_active": bool(flash),
                "partner_price": int(r["partner_price"] or 0),
                "description": r["description"] or "",
                "rating_avg": rating.get("avg", 0),
                "rating_count": rating.get("count", 0),
            })
        return out
    finally:
        conn.close()


def get_product(pid: int) -> Optional[dict]:
    """جزئیات یک محصول + موجودی + امتیاز/نظرات."""
    import db
    p = db.get_product_by_id(pid)
    if not p:
        return None
    from db import apply_flash_price, get_feed_stats, get_product_rating, get_product_ratings_list
    base = int(p["price"] or 0)
    eff, flash = apply_flash_price(pid, base)
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
        "partner_price": int(p.get("partner_price") or 0),
        "description": p.get("description") or "",
        "is_active": bool(p.get("is_active", 1)),
        "stock": int(remaining),
        "rating_avg": rating.get("avg", 0),
        "rating_count": rating.get("count", 0),
        "reviews": reviews,
        "related": related,
    }


def favorite_products(user_id: int) -> list:
    """محصولات علاقه‌مندی کاربر — فقط فعال‌ها، جدیدترین اول."""
    import db
    from db import get_favorite_ids, apply_flash_price, get_product_rating
    ids = get_favorite_ids(user_id)
    if not ids:
        return []
    conn = db._get_connection()
    try:
        placeholders = ",".join("?" * len(ids))
        rows = conn.execute(
            f"SELECT id, category, title, price, description, is_active "
            f"FROM products WHERE id IN ({placeholders}) AND COALESCE(is_active,1)=1 "
            f"ORDER BY id DESC;", tuple(ids)).fetchall()
        out = []
        for r in rows:
            base = int(r["price"] or 0)
            eff, flash = apply_flash_price(int(r["id"]), base)
            try:
                rating = get_product_rating(int(r["id"]))
            except Exception:
                rating = {"count": 0, "avg": 0}
            out.append({
                "id": int(r["id"]), "category": r["category"], "title": r["title"],
                "price": base, "effective_price": int(eff), "flash_active": bool(flash),
                "description": r["description"] or "",
                "rating_avg": rating.get("avg", 0), "rating_count": rating.get("count", 0),
            })
        return out
    finally:
        conn.close()
