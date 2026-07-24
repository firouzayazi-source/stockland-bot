"""اخبار تکنولوژی — فچ/کش زندهٔ آخرین پست‌های وردپرس از طریق REST API رسمی
(بدون هیچ محتوای دستی/داخل پنل).

چرا REST API به‌جای RSS: صفحهٔ آرشیو بلاگ معمولاً یک صفحهٔ سفارشی (نه یک
آرشیو واقعی وردپرس) است و /feed/ روش استاندارد فقط برای سایت کامل یا
آرشیو دسته/برچسب واقعی کار می‌کنه، نه برای صفحات سفارشی — یعنی حدس‌زدن
آدرس درست RSS شکننده‌ست. REST API وردپرس (wp-json) همیشه در سطح کل سایت
در دسترسه (صرف‌نظر از این‌که بلاگ در کدوم صفحه نمایش داده می‌شه)، JSON
ساختاریافته برمی‌گردونه (بدون نیاز به scrape کردن HTML برای تصویر شاخص)،
و API رسمی/نگه‌داری‌شدهٔ خود وردپرسه — پایدارتر و حرفه‌ای‌تر از RSS اینجا.

فقط از bot_config (get_cfg/set_cfg) استفاده می‌کنه، جدول جدید لازم نداره:
  NEWS_FEED_URL          دامنهٔ سایت یا آدرس کامل wp-json (تنظیم دستی ادمین)
  NEWS_FEED_CACHE        JSON آخرین ۱۰ آیتم فچ‌شده
  NEWS_FEED_LAST_SYNC    timestamp آخرین فچ موفق
  NEWS_FEED_LAST_STATUS  ok | error
  NEWS_FEED_LAST_ERROR   پیام خطای آخرین تلاش (برای «وضعیت اتصال» تو پنل)
"""
import re
import time
import json
from urllib.parse import urlparse

_CACHE_TTL = 900  # ۱۵ دقیقه — برای کاهش فشار روی سرور وبلاگ/ما
_ITEM_LIMIT = 10


def _strip_html(html_str: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_str or "")
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _normalize_wp_api_url(raw: str) -> str:
    """هرچی ادمین وارد کنه (دامنهٔ ساده، آدرس صفحهٔ بلاگ، یا خود wp-json) رو
    به آدرس استاندارد REST API پست‌های وردپرس تبدیل می‌کنه."""
    raw = (raw or "").strip().rstrip("/")
    if not raw:
        return ""
    if "wp-json" in raw:
        return raw
    parsed = urlparse(raw if "://" in raw else "https://" + raw)
    root = f"{parsed.scheme}://{parsed.netloc}"
    return f"{root}/wp-json/wp/v2/posts"


def _parse_wp_posts(posts: list, limit: int = _ITEM_LIMIT) -> list[dict]:
    out = []
    for p in posts[:limit]:
        if not isinstance(p, dict):
            continue
        title = _strip_html((p.get("title") or {}).get("rendered") or "")
        link = p.get("link") or ""
        if not title or not link:
            continue
        excerpt = _strip_html((p.get("excerpt") or {}).get("rendered") or "")
        image_url = ""
        try:
            media = (p.get("_embedded") or {}).get("wp:featuredmedia") or []
            if media and isinstance(media, list) and media[0].get("source_url"):
                image_url = media[0]["source_url"]
        except Exception:
            pass
        out.append({
            "title": title,
            "link": link,
            "pub_date": (p.get("date") or "")[:10],
            "excerpt": (excerpt[:180] + "…") if len(excerpt) > 180 else excerpt,
            "image_url": image_url,
        })
    return out


def get_feed(force: bool = False) -> dict:
    """برمی‌گردونه {"items", "last_sync", "status": ok|error|unset, "error"}.
    کش‌شده (۱۵ دقیقه) مگر force=True (دکمهٔ «بروزرسانی دستی» پنل)."""
    from db import get_cfg, set_cfg
    raw_url = get_cfg("NEWS_FEED_URL", "").strip()
    if not raw_url:
        return {"items": [], "last_sync": None, "status": "unset", "error": ""}
    api_url = _normalize_wp_api_url(raw_url)

    last_sync = int(get_cfg("NEWS_FEED_LAST_SYNC", "0") or 0)
    cached_raw = get_cfg("NEWS_FEED_CACHE", "[]")
    now = int(time.time())

    if not force and cached_raw and cached_raw != "[]" and (now - last_sync) < _CACHE_TTL:
        try:
            return {
                "items": json.loads(cached_raw), "last_sync": last_sync,
                "status": get_cfg("NEWS_FEED_LAST_STATUS", "ok"), "error": get_cfg("NEWS_FEED_LAST_ERROR", ""),
            }
        except Exception:
            pass  # کش خراب — برو سراغ فچ تازه

    try:
        import requests
        sep = "&" if "?" in api_url else "?"
        fetch_url = f"{api_url}{sep}per_page={_ITEM_LIMIT}&_embed=wp:featuredmedia"
        r = requests.get(fetch_url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; StockLandNewsBot/1.0)"})
        r.raise_for_status()
        posts = r.json()
        if not isinstance(posts, list):
            raise ValueError((posts.get("message") if isinstance(posts, dict) else None) or "پاسخ نامعتبر از REST API وردپرس")
        items = _parse_wp_posts(posts)
        set_cfg("NEWS_FEED_CACHE", json.dumps(items, ensure_ascii=False))
        set_cfg("NEWS_FEED_LAST_SYNC", str(now))
        set_cfg("NEWS_FEED_LAST_STATUS", "ok")
        set_cfg("NEWS_FEED_LAST_ERROR", "")
        return {"items": items, "last_sync": now, "status": "ok", "error": ""}
    except Exception as e:
        err = str(e)[:200]
        set_cfg("NEWS_FEED_LAST_STATUS", "error")
        set_cfg("NEWS_FEED_LAST_ERROR", err)
        try:
            items = json.loads(cached_raw) if cached_raw and cached_raw != "[]" else []
        except Exception:
            items = []
        return {"items": items, "last_sync": (last_sync or None), "status": "error", "error": err}
