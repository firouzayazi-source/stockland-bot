"""دریافت نرخ دلار — منابع HTTP قابل‌تنظیم از پنل با فچ خودکار.

هیچ منبع خاصی هاردکد نشده؛ ادمین از پنل هر تعداد منبع (URL + مسیر فیلد JSON)
اضافه می‌کنه با اولویت. اگه همهٔ منابع شکست بخورن، آخرین مقدار معتبر (کش‌شده)
یا نرخ دستی برمی‌گرده — کارشناسی هیچ‌وقت به‌خاطر قطعی یک سرویس خارجی نباید
با خطا متوقف بشه.
"""
import requests

from . import db as ivdb


def _extract(data, json_path: str):
    cur = data
    for part in json_path.split("."):
        part = part.strip()
        if not part:
            continue
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            cur = cur[part]
        else:
            raise KeyError(json_path)
    return cur


def fetch_source(source: dict) -> int | None:
    try:
        resp = requests.get(source["url"], timeout=8)
        resp.raise_for_status()
        data = resp.json()
        raw = _extract(data, source.get("json_path") or "price")
        value = int(float(str(raw).replace(",", "").strip()))
        if value <= 0:
            raise ValueError("non-positive fx value")
        ivdb.record_fx_fetch(source["id"], value, None)
        return value
    except Exception as e:
        ivdb.record_fx_fetch(source["id"], None, str(e)[:200])
        return None


def get_current_rate() -> int:
    """نرخ فعلی دلار به تومان — با کش/فال‌بک، هیچ‌وقت استثنا پرتاب نمی‌کنه."""
    from db import get_cfg, set_cfg

    mode = (get_cfg("IV_FX_MODE", "auto") or "auto").strip().lower()
    if mode == "manual":
        try:
            return int(get_cfg("IV_FX_MANUAL_RATE", "0") or "0")
        except Exception:
            return 0

    for source in ivdb.list_fx_sources(active_only=True):
        value = fetch_source(source)
        if value:
            set_cfg("IV_FX_LAST_GOOD", str(value))
            return value

    # همهٔ منابع شکست خوردن — آخرین مقدار معتبر کش‌شده
    try:
        cached = int(get_cfg("IV_FX_LAST_GOOD", "0") or "0")
        if cached:
            return cached
    except Exception:
        pass

    try:
        return int(get_cfg("IV_FX_MANUAL_RATE", "0") or "0")
    except Exception:
        return 0
