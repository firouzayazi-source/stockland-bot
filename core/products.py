"""سرویس محصولات — منطق خالص."""
from typing import Optional


def list_products(category: str = "", active_only: bool = True, limit: int = 100) -> list:
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
        w = ("WHERE " + " AND ".join(where)) if where else ""
        rows = conn.execute(
            f"SELECT id, category, title, price, description, is_active, "
            f"COALESCE(partner_price,0) AS partner_price "
            f"FROM products {w} ORDER BY id DESC LIMIT ?;",
            (*params, limit)).fetchall()
        out = []
        for r in rows:
            base = int(r["price"] or 0)
            eff, flash = apply_flash_price(int(r["id"]), base)
            out.append({
                "id": int(r["id"]), "category": r["category"],
                "title": r["title"], "price": base,
                "effective_price": int(eff),
                "flash_active": bool(flash),
                "partner_price": int(r["partner_price"] or 0),
                "description": r["description"] or "",
            })
        return out
    finally:
        conn.close()


def get_product(pid: int) -> Optional[dict]:
    """جزئیات یک محصول + موجودی."""
    import db
    p = db.get_product_by_id(pid)
    if not p:
        return None
    from db import apply_flash_price, get_feed_stats
    base = int(p["price"] or 0)
    eff, flash = apply_flash_price(pid, base)
    try:
        _t, remaining, _d = get_feed_stats(pid)
    except Exception:
        remaining = 0
    return {
        "id": int(p["id"]), "category": p.get("category"),
        "title": p["title"], "price": base,
        "effective_price": int(eff), "flash_active": bool(flash),
        "partner_price": int(p.get("partner_price") or 0),
        "description": p.get("description") or "",
        "is_active": bool(p.get("is_active", 1)),
        "stock": int(remaining),
    }
