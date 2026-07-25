"""نقطهٔ ورود مشترک کارشناسی — هم ربات هم API همین رو صدا می‌زنن.

به همین دلیل منطق قیمت‌گذاری هیچ‌جای دیگه (نه bot.py نه api.py) تکرار نمی‌شه؛
اون‌ها فقط ورودی جمع می‌کنن و خروجی این تابع رو نمایش می‌دن.
"""
import json

from . import db as ivdb
from . import pricing_engine
from . import scoring_engine
from . import report as ivreport


class ValuationError(Exception):
    pass


def valuate(payload: dict) -> dict:
    model_id = payload.get("model_id")
    capacity_id = payload.get("capacity_id")
    if not model_id or not capacity_id:
        raise ValuationError("مدل و ظرفیت دستگاه الزامی است")

    model = ivdb.get_model(int(model_id))
    if not model:
        raise ValuationError("مدل یافت نشد")
    capacity = ivdb.get_capacity(int(capacity_id))
    if not capacity or capacity["model_id"] != int(model_id):
        raise ValuationError("ظرفیت انتخاب‌شده متعلق به این مدل نیست")

    selections = payload.get("selections") or {}
    features_ok = payload.get("features_ok")
    seller_price = payload.get("seller_price")
    try:
        seller_price = int(seller_price) if seller_price not in (None, "") else None
    except (TypeError, ValueError):
        seller_price = None

    price_result = pricing_engine.price(int(model_id), int(capacity_id), selections)
    score_result = scoring_engine.compute_score(selections, features_ok)
    verdict = scoring_engine.compute_verdict(score_result["score"], price_result["fair_price"], seller_price)
    report_text = ivreport.build_report(
        price_result["contributions"], score_result["score"], verdict, price_result["fair_price"])

    result = {
        "model_name": model["name"],
        "capacity_label": capacity["capacity_label"],
        "market_price": price_result["market_price"],
        "fair_price": price_result["fair_price"],
        "buy_price": price_result["buy_price"],
        "sell_price": price_result["sell_price"],
        "score": score_result["score"],
        "score_breakdown": score_result["breakdown"],
        "verdict_emoji": verdict["emoji"],
        "verdict_text": verdict["text"],
        "report_text": report_text,
        "fx_rate": price_result["current_fx_rate"],
        "contributions": price_result["contributions"],
    }

    try:
        vid = ivdb.create_valuation(
            user_id=payload.get("user_id"),
            model_id=int(model_id),
            capacity_id=int(capacity_id),
            color=payload.get("color") or "",
            part_number=payload.get("part_number") or "",
            sim_type=payload.get("sim_type") or "",
            input_json=json.dumps(payload, ensure_ascii=False, default=str),
            market_price=price_result["market_price"],
            fair_price=price_result["fair_price"],
            buy_price=price_result["buy_price"],
            sell_price=price_result["sell_price"],
            score=score_result["score"],
            verdict=f"{verdict['emoji']} {verdict['text']}",
            report_text=report_text,
            seller_price=seller_price,
            city=payload.get("city") or "",
            seller_type=payload.get("seller_type") or "",
        )
        result["valuation_id"] = vid
    except Exception:
        result["valuation_id"] = None

    return result


def list_models_with_capacities() -> list[dict]:
    models = ivdb.list_models(active_only=True)
    out = []
    for m in models:
        caps = ivdb.list_capacities(model_id=m["id"], active_only=True)
        out.append({**m, "capacities": caps})
    return out


def list_selectable_coefficients() -> dict[str, list[dict]]:
    coeffs = ivdb.list_coefficients(active_only=True)
    grouped: dict[str, list[dict]] = {}
    for c in coeffs:
        grouped.setdefault(c["category"], []).append(c)
    return grouped
