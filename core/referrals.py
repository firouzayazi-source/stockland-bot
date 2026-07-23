"""سرویس معرفی‌ها — منطق خالص."""


def stats(user_id: int) -> dict:
    from db import _get_connection
    conn = _get_connection()
    try:
        total = int(conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=?;", (user_id,)).fetchone()[0] or 0)
        rewarded = int(conn.execute(
            "SELECT COUNT(*) FROM referrals WHERE referrer_id=? AND rewarded=1;", (user_id,)).fetchone()[0] or 0)
        earned = int(conn.execute(
            "SELECT COALESCE(SUM(reward_amount),0) FROM referrals WHERE referrer_id=? AND rewarded=1;",
            (user_id,)).fetchone()[0] or 0)
        return {"total": total, "rewarded": rewarded, "earned": earned}
    except Exception:
        return {"total": 0, "rewarded": 0, "earned": 0}
    finally:
        conn.close()
