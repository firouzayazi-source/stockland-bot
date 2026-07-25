"""موتور قیمت‌گذاری قانون‌محور — هیچ عدد مهمی این‌جا هاردکد نیست، همه از DB می‌آد.

فرمول (به‌صورت درصد نسبت به قیمت پایه، چون معنادارترین و قابل‌تنظیم‌ترین حالته):

    ضریب کل = ۱ + (تاثیر نرخ ارز% + تاثیر دادهٔ بازار StockLand% + عرضه/تقاضای مدل% + مجموع ضرایب شرایط دستگاه%) / ۱۰۰
    قیمت واقعی بازار = قیمت پایه × ضریب کل
    قیمت پیشنهادی خرید فروشگاه = قیمت‌مرجع‌خرید × ضریب کل
    قیمت پیشنهادی فروش فروشگاه = قیمت‌مرجع‌فروش × ضریب کل

هوش مصنوعی/AI در این موتور قیمت رو تعیین نمی‌کنه — فقط بعداً روی همین خروجی توضیح می‌سازه (report.py).
"""
from . import db as ivdb
from . import fx as ivfx


def _round1000(x: float) -> int:
    return int(round(x / 1000.0)) * 1000


def price(model_id: int, capacity_id: int, selections: dict[str, str]) -> dict:
    """selections: دیکشنری category -> option_key انتخاب‌شده (مثلاً {'battery':'batt_90_94', ...})"""
    from db import get_cfg

    capacity = ivdb.get_capacity(capacity_id)
    if not capacity or capacity["model_id"] != model_id:
        raise ValueError("ظرفیت/مدل نامعتبر است")

    base_price = capacity["base_price"]
    buy_ref = capacity["buy_price_ref"]
    sell_ref = capacity["sell_price_ref"]
    fx_ref = capacity["fx_ref_rate"] or 0
    demand_pct = capacity["demand_percent"] or 0.0

    current_rate = ivfx.get_current_rate()
    sensitivity = float(get_cfg("IV_FX_SENSITIVITY", "0.5") or "0.5")
    fx_pct = 0.0
    if fx_ref > 0 and current_rate > 0:
        fx_pct = ((current_rate - fx_ref) / fx_ref) * 100 * sensitivity

    market_weight = float(get_cfg("IV_MARKET_DATA_WEIGHT", "0.15") or "0.15")
    market_pct = ivdb.market_data_avg_delta_pct(model_id, capacity_id, base_price) * market_weight

    all_coeffs = ivdb.list_coefficients(active_only=True)
    coeff_by_key = {(c["category"], c["option_key"]): c for c in all_coeffs}

    contributions = [
        {"label": "نرخ ارز", "pct": round(fx_pct, 2), "amount": _round1000(base_price * fx_pct / 100)},
        {"label": "دادهٔ بازار StockLand", "pct": round(market_pct, 2), "amount": _round1000(base_price * market_pct / 100)},
        {"label": "عرضه و تقاضای مدل", "pct": round(demand_pct, 2), "amount": _round1000(base_price * demand_pct / 100)},
    ]

    condition_pct_total = 0.0
    selected_coeffs = {}
    for category, option_key in (selections or {}).items():
        # بعضی دسته‌ها (مثل «component» — کدوم قطعه خرابه) چندانتخابی‌ان: لیست option_key
        option_keys = option_key if isinstance(option_key, (list, tuple)) else [option_key]
        matched = []
        for ok in option_keys:
            c = coeff_by_key.get((category, ok))
            if not c:
                continue
            matched.append(c)
            condition_pct_total += c["percent"]
            contributions.append({
                "label": c["option_label"], "category": category,
                "pct": c["percent"], "amount": _round1000(base_price * c["percent"] / 100),
            })
        if matched:
            selected_coeffs[category] = matched if len(matched) > 1 else matched[0]

    market_wide_pct = fx_pct + market_pct + demand_pct
    total_pct = market_wide_pct + condition_pct_total
    market_factor = 1 + market_wide_pct / 100
    fair_factor = 1 + total_pct / 100

    result = {
        "capacity": capacity,
        "current_fx_rate": current_rate,
        "fx_pct": round(fx_pct, 2),
        "market_pct": round(market_pct, 2),
        "demand_pct": round(demand_pct, 2),
        "condition_pct": round(condition_pct_total, 2),
        "total_pct": round(total_pct, 2),
        "factor": round(fair_factor, 4),
        # قیمت واقعی بازار: فقط عوامل کلان بازار (ارز/دادهٔ بازار/عرضه‌تقاضا)، مستقل از شرایط این دستگاه خاص
        "market_price": max(0, _round1000(base_price * market_factor)),
        # قیمت منصفانه: با احتساب شرایط واقعی همین دستگاه هم
        "fair_price": max(0, _round1000(base_price * fair_factor)),
        "buy_price": max(0, _round1000(buy_ref * fair_factor)),
        "sell_price": max(0, _round1000(sell_ref * fair_factor)),
        "contributions": contributions,
        "selected_coeffs": selected_coeffs,
    }
    return result
