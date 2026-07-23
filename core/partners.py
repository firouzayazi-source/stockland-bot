"""سرویس همکاران — منطق خالص."""


def is_approved(user_id: int) -> bool:
    from db import _get_connection
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT 1 FROM partners WHERE CAST(tg_user_id AS INTEGER)=? AND status='approved' LIMIT 1;",
            (int(user_id),)).fetchone()
        return row is not None
    except Exception:
        return False
    finally:
        conn.close()


def partner_balance(user_id: int) -> int:
    import db
    try:
        return int(db.get_partner_wallet_balance(user_id) or 0)
    except Exception:
        return 0


def current_tier(user_id: int) -> dict | None:
    """سطح فعلی همکار بر اساس تعداد فروش."""
    from db import _get_connection, ensure_partner_tiers_extended
    ensure_partner_tiers_extended()
    from core.orders import order_count
    cnt = order_count(user_id)
    conn = _get_connection()
    try:
        row = conn.execute(
            "SELECT * FROM partner_tiers WHERE min_orders<=? ORDER BY min_orders DESC LIMIT 1;",
            (cnt,)).fetchone()
        if not row:
            row = conn.execute(
                "SELECT * FROM partner_tiers ORDER BY min_orders ASC LIMIT 1;").fetchone()
        if not row:
            return None
        d = dict(row)
        d["order_count"] = cnt
        return d
    finally:
        conn.close()
