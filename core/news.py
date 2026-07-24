"""اخبار تکنولوژی — فچ/پارس/کش فید RSS بیرونی (بدون هیچ محتوای داخلی).

فقط از bot_config (get_cfg/set_cfg) استفاده می‌کنه، جدول جدید لازم نداره:
  NEWS_FEED_URL          آدرس فید RSS (تنظیم دستی ادمین)
  NEWS_FEED_CACHE        JSON آخرین ۱۰ آیتم فچ‌شده
  NEWS_FEED_LAST_SYNC    timestamp آخرین فچ موفق
  NEWS_FEED_LAST_STATUS  ok | error
  NEWS_FEED_LAST_ERROR   پیام خطای آخرین تلاش (برای «وضعیت اتصال» تو پنل)
"""
import re
import time
import json
import xml.etree.ElementTree as ET

_NS = {
    "content": "http://purl.org/rss/1.0/modules/content/",
    "media": "http://search.yahoo.com/mrss/",
}
_CACHE_TTL = 900  # ۱۵ دقیقه — برای کاهش فشار روی سرور وبلاگ/ما
_ITEM_LIMIT = 10


def _strip_html(html_str: str) -> str:
    text = re.sub(r"<[^>]+>", " ", html_str or "")
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _extract_image(item) -> str:
    media = item.find("media:content", _NS)
    if media is None:
        media = item.find("media:thumbnail", _NS)
    if media is not None and media.get("url"):
        return media.get("url")
    enclosure = item.find("enclosure")
    if enclosure is not None and (enclosure.get("type") or "").startswith("image") and enclosure.get("url"):
        return enclosure.get("url")
    content_encoded = item.find("content:encoded", _NS)
    html_blob = (content_encoded.text if content_encoded is not None else "") or (item.findtext("description") or "")
    m = re.search(r'<img[^>]+src=["\']([^"\']+)["\']', html_blob or "")
    return m.group(1) if m else ""


def _parse_rss(xml_bytes: bytes, limit: int = _ITEM_LIMIT) -> list[dict]:
    root = ET.fromstring(xml_bytes)
    channel = root.find("channel")
    items = channel.findall("item") if channel is not None else root.findall(".//item")
    out = []
    for it in items[:limit]:
        title = (it.findtext("title") or "").strip()
        link = (it.findtext("link") or "").strip()
        if not title or not link:
            continue
        desc = _strip_html(it.findtext("description") or "")
        out.append({
            "title": title,
            "link": link,
            "pub_date": (it.findtext("pubDate") or "").strip(),
            "excerpt": (desc[:180] + "…") if len(desc) > 180 else desc,
            "image_url": _extract_image(it),
        })
    return out


def get_feed(force: bool = False) -> dict:
    """برمی‌گردونه {"items", "last_sync", "status": ok|error|unset, "error"}.
    کش‌شده (۱۵ دقیقه) مگر force=True (دکمهٔ «بروزرسانی دستی» پنل)."""
    from db import get_cfg, set_cfg
    url = get_cfg("NEWS_FEED_URL", "").strip()
    if not url:
        return {"items": [], "last_sync": None, "status": "unset", "error": ""}

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
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (compatible; StockLandNewsBot/1.0)"})
        r.raise_for_status()
        items = _parse_rss(r.content)
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
