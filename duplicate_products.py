"""
ماژول مستقل تشخیص/مدیریت محصولات تکراری (بخش ۸ سند مینی‌اپ).

معیار تطابق: عنوان دقیق محصول (تطابق کامل رشته، بعد از trim فاصله‌های ابتدا/انتها) —
مستقل از دسته‌بندی/انبار/مسیر ثبت. عمداً از هیچ جدول یا ستون تازه‌ای استفاده نمی‌کنه
(بخش ۸.۵: بدون تغییر اساسی در معماری/دیتابیس) — فقط روی products و جدول‌های وابسته‌ی
از قبل موجود کار می‌کنه.

«اصل» گروه = کوچک‌ترین id (چون products هیچ ستون created_at نداره، ولی id در SQLite
AUTOINCREMENT هست، پس ترتیب id دقیقاً ترتیب ثبته). «تکراری» = بقیهٔ اعضای گروه.
"""

from db import _get_connection


def find_duplicate_groups() -> list:
    """گروه‌های محصول تکراری در کل دیتابیس (مستقل از دسته/انبار). هر گروه شامل حداقل
    یک «اصل» (اولین ثبت‌شده) و یک یا چند «تکراری» (بقیه) است."""
    conn = _get_connection()
    try:
        rows = conn.execute("""
            SELECT id, title, category, price,
                   COALESCE(is_active, 1) AS is_active
            FROM products
            ORDER BY id ASC;
        """).fetchall()
        groups = {}
        for r in rows:
            key = (r["title"] or "").strip()
            if not key:
                continue
            groups.setdefault(key, []).append(dict(r))

        out = []
        for title, items in groups.items():
            if len(items) < 2:
                continue
            for i, it in enumerate(items):
                it["is_original"] = (i == 0)
                it["stock"] = _stock_count(conn, it["id"])
                it["feed_batches_count"], it["feed_batches_cost"] = _feed_batches_info(conn, it["id"])
                it["orders_count"] = _orders_count(conn, it["id"])
            out.append({"title": title, "products": items})
        out.sort(key=lambda g: -len(g["products"]))
        return out
    finally:
        conn.close()


def _stock_count(conn, pid: int) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id=? AND delivered=0;", (pid,)
        ).fetchone()
        return int(row[0] or 0)
    except Exception:
        return 0


def _feed_batches_info(conn, pid: int):
    try:
        row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(purchase_price*item_count),0) FROM feed_batches WHERE product_id=?;",
            (pid,)
        ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)
    except Exception:
        return 0, 0


def _orders_count(conn, pid: int) -> int:
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE CAST(product_id AS INTEGER)=?;", (pid,)
        ).fetchone()
        return int(row[0] or 0)
    except Exception:
        return 0


def is_duplicate(pid: int) -> bool:
    """آیا این محصول در حال حاضر واقعاً عضو یک گروه تکراریه؟ (دفاع در برابر حذف یه
    محصول یکتا از طریق یه لینک/وضعیت قدیمی صفحه)."""
    for g in find_duplicate_groups():
        for p in g["products"]:
            if int(p["id"]) == int(pid) and not p["is_original"]:
                return True
    return False


def _ensure_related_schemas():
    """اطمینان از وجود همهٔ جدول‌های وابسته قبل از خوندن/نوشتن روشون — طبق الگوی
    استاندارد پروژه (بخش ۷ CLAUDE.md): بدون این، نصب‌های تازه/قدیمی ممکنه این
    جدول‌ها رو هنوز نساخته باشن."""
    from db import (ensure_feed_batch_schema, ensure_faq_schema, ensure_ratings_schema,
                     ensure_favorites_schema, ensure_subscription_table, ensure_growth_schema,
                     ensure_discount_table)
    for fn in (ensure_feed_batch_schema, ensure_faq_schema, ensure_ratings_schema,
               ensure_favorites_schema, ensure_subscription_table, ensure_growth_schema,
               ensure_discount_table):
        try:
            fn()
        except Exception:
            pass


def delete_duplicate_product(pid: int) -> dict:
    """حذف امن یک محصول «تکراری» + دادهٔ وابسته‌اش — محصول «اصل» و سفارش‌های ثبت‌شده
    (سابقهٔ خرید) هرگز دست‌نخورده نمی‌مونن (بخش ۸.۴). برمی‌گردونه: شمار هر جدول
    پاک‌شده، برای نمایش به ادمین بعد از حذف.

    اگه pid واقعاً عضو یک گروه تکراری نباشه (مثلاً «اصل» گروه یا محصول یکتا)، هیچ‌کاری
    نمی‌کنه و ValueError می‌ده — حذف نهایی همیشه باید فقط روی «تکراری» واقعی اعمال بشه."""
    pid = int(pid)
    if not is_duplicate(pid):
        raise ValueError("این محصول عضو یک گروه تکراری نیست — حذف انجام نشد.")

    _ensure_related_schemas()
    conn = _get_connection()
    result = {"product_id": pid}
    try:
        result["feed_items"] = conn.execute(
            "SELECT COUNT(*) FROM product_feed WHERE product_id=?;", (pid,)
        ).fetchone()[0]
        conn.execute("DELETE FROM product_feed WHERE product_id=?;", (pid,))

        result["feed_batches"] = conn.execute(
            "SELECT COUNT(*) FROM feed_batches WHERE product_id=?;", (pid,)
        ).fetchone()[0]
        conn.execute("DELETE FROM feed_batches WHERE product_id=?;", (pid,))

        conn.execute("DELETE FROM feed_alert_settings WHERE product_id=?;", (pid,))

        result["faqs"] = conn.execute(
            "SELECT COUNT(*) FROM product_faqs WHERE product_id=?;", (pid,)
        ).fetchone()[0]
        conn.execute("DELETE FROM product_faqs WHERE product_id=?;", (pid,))

        result["ratings"] = conn.execute(
            "SELECT COUNT(*) FROM product_ratings WHERE product_id=?;", (pid,)
        ).fetchone()[0]
        conn.execute("DELETE FROM product_ratings WHERE product_id=?;", (pid,))

        conn.execute("DELETE FROM flash_sales WHERE product_id=?;", (pid,))
        conn.execute("DELETE FROM stock_subscriptions WHERE product_id=?;", (pid,))
        conn.execute("DELETE FROM favorites WHERE product_id=?;", (pid,))

        # کد تخفیف اختصاصیِ این محصول حذف نمی‌شه (تاریخچهٔ استفاده‌اش مهمه) —
        # فقط دامنه‌اش به «همه محصولات» برمی‌گرده تا به محصول حذف‌شده اشاره نکنه.
        conn.execute("UPDATE discount_codes SET product_id=NULL WHERE product_id=?;", (pid,))

        # سفارش‌ها (سابقهٔ خرید) عمداً دست‌نخورده می‌مونن — دقیقاً مثل رفتار پروژه
        # با محصولات حذف‌شده در سفارش‌های قدیمی (بخش ۸.۴: تاریخچه نباید پاک بشه)
        result["orders_kept"] = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE CAST(product_id AS INTEGER)=?;", (pid,)
        ).fetchone()[0]

        conn.execute("DELETE FROM products WHERE id=?;", (pid,))
        conn.commit()
        return result
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
