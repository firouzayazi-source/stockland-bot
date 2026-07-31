"""سرویس سفارش‌ها — منطق خالص."""


def user_orders(user_id: int, limit: int = 50, offset: int = 0) -> list:
    from db import _get_connection, has_rated_order
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT o.id, o.title, o.price, o.status, o.created_at, o.feed_id, o.product_id, pf.data AS feed_data "
            "FROM orders o LEFT JOIN product_feed pf ON pf.id = o.feed_id "
            "WHERE o.user_id=? AND COALESCE(o.status,'active')!='returned' "
            "ORDER BY o.id DESC LIMIT ? OFFSET ?;",
            (str(user_id), limit, offset)).fetchall()
        out = []
        for r in rows:
            try:
                feed_id = int(r["feed_id"]) if r["feed_id"] is not None else None
            except Exception:
                feed_id = None
            try:
                product_id = int(r["product_id"]) if r["product_id"] not in (None, "") else None
            except Exception:
                product_id = None
            try:
                rated = has_rated_order(int(r["id"]))
            except Exception:
                rated = False
            out.append({
                "id": int(r["id"]), "title": r["title"],
                "price": int(r["price"] or 0), "status": r["status"] or "active",
                "created_at": r["created_at"],
                "delivered_data": r["feed_data"] if feed_id else None,
                "product_id": product_id,
                "can_rate": bool(product_id and not rated),
                "has_rated": rated,
            })
        return out
    finally:
        conn.close()


def order_count(user_id: int) -> int:
    from db import _get_connection
    conn = _get_connection()
    try:
        return int(conn.execute(
            "SELECT COUNT(*) FROM orders WHERE user_id=? AND COALESCE(status,'active')='active';",
            (str(user_id),)).fetchone()[0] or 0)
    finally:
        conn.close()
