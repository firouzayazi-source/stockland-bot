"""ریت‌لیمیت سبک درون‌حافظه‌ای برای اندپوینت‌های پرهزینهٔ سطح API.

همون الگوی `_login_attempts` در admin_panel.py، ولی عمومی‌شده (چند bucket جدا
با یک دیکشنری مشترک) تا بین payment_service.py / api.py / iphone_valuation/router.py
به‌اشتراک بره — بدون این‌که این سه فایل از هم import کنن.

⚠️ per-process است (نه توزیع‌شده بین چند worker) — دقیقاً مثل بقیهٔ rate-limiterهای
موجود پروژه (bot.py، admin_panel.py)؛ چون کل بک‌اند در یک پروسهٔ uvicorn اجرا می‌شه
(بخش ۴ CLAUDE.md)، این محدودیت در عمل مشکلی ایجاد نمی‌کنه.
"""
import time

_buckets: dict = {}  # (bucket, key) -> [timestamps]


def is_rate_limited(bucket: str, key: str, max_calls: int, window_seconds: int) -> tuple:
    """(is_blocked, remaining_seconds). خودِ این تابع یک تلاش تازه رو ثبت می‌کنه —
    برخلاف الگوی لاگین ادمین (که فقط تلاش‌های *ناموفق* رو می‌شمره)، این‌جا هر
    فراخوانی endpoint حساس — موفق یا ناموفق — جزو سهمیه است."""
    now = time.time()
    k = (bucket, key)
    hits = _buckets.setdefault(k, [])
    hits[:] = [t for t in hits if now - t < window_seconds]
    if len(hits) >= max_calls:
        return True, int(window_seconds - (now - hits[0]))
    hits.append(now)
    return False, 0


def client_ip(request) -> str:
    """استخراج IP واقعی پشت nginx — همون الگوی admin_panel.py/api.py (بخش ۱۳ CLAUDE.md)."""
    xff = request.headers.get("X-Forwarded-For", "")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
