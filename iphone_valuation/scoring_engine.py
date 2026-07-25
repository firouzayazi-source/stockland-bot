"""محاسبهٔ StockLand Score (۰ تا ۱۰۰) و تعیین نتیجهٔ نهایی (🟢/🟡/🔴).

امتیاز بر پایهٔ همون ضرایب قیمتیه (iv_coefficients) به‌علاوه یک وزن جداگانه
برای هر دسته (iv_score_weights) — یعنی یه دسته می‌تونه اثر قیمتی زیاد ولی اثر
کیفیتی کم داشته باشه یا برعکس، کاملاً از پنل قابل تنظیمه.
"""
from . import db as ivdb


def compute_score(selections: dict[str, str], features_ok: bool | None = None) -> dict:
    weights = ivdb.list_score_weights()
    all_coeffs = ivdb.list_coefficients(active_only=True)

    by_category: dict[str, list[dict]] = {}
    for c in all_coeffs:
        by_category.setdefault(c["category"], []).append(c)

    breakdown = []
    total_deduction = 0.0

    for category, weight in weights.items():
        if category == "features":
            continue
        options = by_category.get(category, [])
        if not options:
            continue
        worst = min((o["percent"] for o in options), default=0)
        option_key = (selections or {}).get(category)
        chosen = next((o for o in options if o["option_key"] == option_key), None)
        pct = chosen["percent"] if chosen else 0
        fraction = 0.0 if pct >= 0 or worst >= 0 else min(1.0, pct / worst)
        deduction = fraction * weight
        total_deduction += deduction
        breakdown.append({
            "category": category,
            "label": chosen["option_label"] if chosen else "—",
            "deduction": round(deduction, 1),
        })

    features_weight = weights.get("features", 0)
    if features_ok is False:
        deduction = features_weight * 0.5
        total_deduction += deduction
        breakdown.append({"category": "features", "label": "برخی امکانات مشکل دارند", "deduction": round(deduction, 1)})

    score = max(0, min(100, round(100 - total_deduction)))
    return {"score": score, "breakdown": breakdown}


def compute_verdict(score: int, fair_price: int, seller_price: int | None) -> dict:
    if not seller_price or seller_price <= 0 or fair_price <= 0:
        if score >= 80:
            return {"emoji": "🟢", "text": "خرید عالی", "ratio": None}
        if score >= 50:
            return {"emoji": "🟡", "text": "خرید مناسب با مذاکره", "ratio": None}
        return {"emoji": "🔴", "text": "خرید توصیه نمی‌شود", "ratio": None}

    ratio = seller_price / fair_price
    if score < 40:
        return {"emoji": "🔴", "text": "خرید توصیه نمی‌شود", "ratio": round(ratio, 3)}
    if ratio <= 0.95 and score >= 60:
        return {"emoji": "🟢", "text": "خرید عالی", "ratio": round(ratio, 3)}
    if ratio <= 1.08:
        return {"emoji": "🟡", "text": "خرید مناسب با مذاکره", "ratio": round(ratio, 3)}
    return {"emoji": "🔴", "text": "خرید توصیه نمی‌شود", "ratio": round(ratio, 3)}
