"""سرویس سفارش‌ها — منطق خالص."""


def user_orders(user_id: int, limit: int = 50) -> list:
    from db import _get_connection
    conn = _get_connection()
    try:
        rows = conn.execute(
            "SELECT id, title, price, status, created_at FROM orders "
            "WHERE user_id=? AND COALESCE(status,'active')!='returned' "
            "ORDER BY id DESC LIMIT ?;",
            (str(user_id), limit)).fetchall()
        return [{"id": int(r["id"]), "title": r["title"],
                 "price": int(r["price"] or 0), "status": r["status"] or "active",
                 "created_at": r["created_at"]} for r in rows]
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
