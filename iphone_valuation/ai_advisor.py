"""کارشناس مکمل هوش مصنوعی — بخش ۲۲.۸ CLAUDE.md.

نقش این ماژول کاملاً «مکمل»ه، نه جایگزین: `pricing_engine.price()` همیشه اول اجرا و
مرجع نهایی می‌مونه؛ این تابع فقط (اگه فعال باشه) یه تعدیل محدود روی `fair_price` پیشنهاد
می‌ده. اگه `IV_AI_ENABLED` خاموش باشه یا هر خطایی رخ بده، `analyze()` فقط `None`
برمی‌گردونه و صدازننده (service.valuate) دقیقاً همون رفتار قبلی (بدون AI) رو داره —
هیچ‌وقت جریان قیمت‌گذاری دیتامحور رو مسدود نمی‌کنه یا کند نمی‌کنه با یه خطای غیرمنتظره."""
import datetime
import json


def _safe_int(val, default=0):
    try:
        return int(round(float(val)))
    except (TypeError, ValueError):
        return default


def _safe_float(val, default=0.0):
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def _coeff_label(category, key):
    from . import db as ivdb
    if not key:
        return None
    opts = ivdb.list_coefficients(category=category, active_only=False)
    row = next((o for o in opts if o["option_key"] == key), None)
    return row["option_label"] if row else key


def _coeff_labels(category, keys):
    from . import db as ivdb
    if not keys:
        return []
    opts = ivdb.list_coefficients(category=category, active_only=False)
    by_key = {o["option_key"]: o["option_label"] for o in opts}
    return [by_key.get(k, k) for k in keys]


def _build_context(payload: dict, model: dict, capacity: dict, price_result: dict,
                    score_result: dict, verdict: dict, max_adjust: float) -> dict:
    """همهٔ چیزی که کارشناس AI برای تحلیل نیاز داره — طبق درخواست صریح مالک پروژه، صرفاً
    قیمت موتور رو نمی‌فرستیم؛ نرخ ارز/تاریخ/وضعیت بازار/موجودی/رجیستری/مشخصات دستگاه/
    سلامت باتری/تعویض قطعات/گارانتی/تاریخچهٔ قیمت‌های اخیر همه توی context هستن."""
    from . import db as ivdb

    selections = payload.get("selections") or {}
    fx_mode = "دستی"
    try:
        from db import get_cfg
        fx_mode = "دستی" if get_cfg("IV_FX_MODE", "auto") == "manual" else "آنلاین خودکار"
    except Exception:
        pass

    recent = ivdb.recent_valuations_for_capacity(model["id"], capacity["id"], limit=10)
    recent_fair_prices = [r["fair_price"] for r in recent if r.get("fair_price")]
    trend = "نامشخص (دادهٔ کافی نیست)"
    if len(recent_fair_prices) >= 2:
        newest, oldest = recent_fair_prices[0], recent_fair_prices[-1]
        if oldest:
            delta_pct = ((newest - oldest) / oldest) * 100
            if delta_pct > 2:
                trend = "صعودی"
            elif delta_pct < -2:
                trend = "نزولی"
            else:
                trend = "ثابت"

    try:
        avg_transaction_delta = ivdb.market_data_avg_delta_pct(
            model["id"], capacity["id"], capacity.get("base_price") or 0)
    except Exception:
        avg_transaction_delta = 0.0

    return {
        "timestamp": datetime.datetime.now().isoformat(),
        "fx": {
            "current_rate_toman": price_result.get("current_fx_rate"),
            "source": fx_mode,
        },
        "device": {
            "model": model.get("name"),
            "release_year": model.get("series"),
            "capacity": capacity.get("capacity_label"),
            "color": payload.get("color") or "",
            "part_number": payload.get("part_number") or "",
            "sim_type": payload.get("sim_type") or "",
        },
        "condition": {
            "authenticity_grade": _coeff_label("grade", selections.get("grade")),
            "overall_condition": _coeff_label("condition", selections.get("condition")),
            "battery_health": _coeff_label("battery", selections.get("battery")),
            "replaced_parts": _coeff_labels("replaced", selections.get("replaced")),
            "broken_parts": _coeff_labels("component", selections.get("component")),
            "repair_service_history": _coeff_label("repair", selections.get("repair")),
            "registry_ownership_status": _coeff_label("registry", selections.get("registry")),
            "box_and_accessories": _coeff_label("box", selections.get("box")),
            "cosmetic_condition": _coeff_label("cosmetic", selections.get("cosmetic")),
            "cable_condition": _coeff_label("cable", selections.get("cable")),
            "all_features_working": payload.get("features_ok"),
        },
        "pricing_engine_result": {
            "base_price": capacity.get("base_price"),
            "market_price": price_result.get("market_price"),
            "fair_price": price_result.get("fair_price"),
            "buy_price": price_result.get("buy_price"),
            "sell_price": price_result.get("sell_price"),
            "fx_impact_pct": price_result.get("fx_pct"),
            "market_data_impact_pct": price_result.get("market_pct"),
            "demand_supply_pct": price_result.get("demand_pct"),
            "device_condition_pct": price_result.get("condition_pct"),
            "total_pct": price_result.get("total_pct"),
            "contributions": price_result.get("contributions"),
        },
        "score": {
            "stockland_score_0_100": score_result.get("score"),
            "verdict": verdict.get("text"),
        },
        "market_history": {
            "recent_valuations_fair_price_newest_first": recent_fair_prices,
            "price_trend": trend,
            "avg_recent_transaction_delta_pct": round(avg_transaction_delta, 2),
        },
        "max_adjust_percent": max_adjust,
    }


def _log_analysis(valuation_id, model_id, capacity_id, provider, model_name, context,
                   raw_response, adjustment_percent, confidence, final_price, warnings, error):
    try:
        from . import db as ivdb
        ivdb.create_ai_analysis(
            valuation_id=valuation_id, model_id=model_id, capacity_id=capacity_id,
            provider=provider, model_name=model_name,
            request_context=json.dumps(context, ensure_ascii=False, default=str),
            response_json=json.dumps(raw_response, ensure_ascii=False, default=str),
            adjustment_percent=adjustment_percent, confidence=confidence, final_price=final_price,
            warnings=json.dumps(warnings, ensure_ascii=False), error=error or "")
    except Exception:
        pass  # لاگ‌نشدن یه تحلیل نباید کل جریان رو بشکنه


def analyze(payload: dict, model: dict, capacity: dict, price_result: dict,
            score_result: dict, verdict: dict, valuation_id: int | None = None) -> dict | None:
    """نقطهٔ ورود — service.valuate() این رو بعد از محاسبهٔ قطعی موتور صدا می‌زنه.
    هر مسیر خطا (تنظیم‌نشدن کلید، قطعی provider، پاسخ نامعتبر) فقط None برمی‌گردونه."""
    try:
        from db import get_cfg
        if get_cfg("IV_AI_ENABLED", "0") != "1":
            return None
        enc_key = get_cfg("IV_AI_API_KEY_ENC", "")
        if not enc_key:
            return None
        from . import ai_crypto
        api_key = ai_crypto.decrypt_api_key(enc_key)
        if not api_key:
            return None

        from .ai_providers import AI_PROVIDERS, DEFAULT_PROVIDER
        provider_name = get_cfg("IV_AI_PROVIDER", DEFAULT_PROVIDER) or DEFAULT_PROVIDER
        provider_mod = AI_PROVIDERS.get(provider_name) or AI_PROVIDERS.get(DEFAULT_PROVIDER)
        if not provider_mod:
            return None

        model_name = get_cfg("IV_AI_MODEL", "") or "claude-opus-5"
        max_adjust = abs(_safe_float(get_cfg("IV_AI_MAX_ADJUST_PCT", "5"), 5.0))
        min_confidence = _safe_int(get_cfg("IV_AI_MIN_CONFIDENCE", "60"), 60)

        context = _build_context(payload, model, capacity, price_result, score_result, verdict, max_adjust)
    except Exception:
        return None

    try:
        raw = provider_mod.analyze(context, api_key, model_name)
    except Exception as e:
        _log_analysis(valuation_id, model.get("id"), capacity.get("id"), provider_name, model_name,
                       context, {}, 0.0, 0, None, [], str(e))
        return None

    try:
        confidence = max(0, min(100, _safe_int(raw.get("confidence"), 0)))
        adjustment_percent = _safe_float(raw.get("adjustment_percent"), 0.0)
        # هیچ‌وقت به عدد خودِ مدل اعتماد کور نمی‌شه — حتی اگه سیستم‌پرامپت رو رعایت نکرده
        # باشه، این‌جا دوباره به بازهٔ مجاز clamp می‌شه (نکتهٔ اصلی درخواست مالک پروژه).
        adjustment_percent = max(-max_adjust, min(max_adjust, adjustment_percent))
        # گیت اطمینان: زیر آستانه یعنی هیچ تغییری روی قیمت اعمال نشه (ولی دلیل/هشدارها
        # همچنان نمایش داده می‌شن — طبق درخواست صریح مالک پروژه).
        if confidence < min_confidence:
            adjustment_percent = 0.0

        fair_price = price_result.get("fair_price") or 0
        final_price = int(round(fair_price * (1 + adjustment_percent / 100) / 1000)) * 1000

        warnings = raw.get("warnings") or []
        if not isinstance(warnings, list):
            warnings = [str(warnings)]
        warnings = [str(w) for w in warnings if w]

        result = {
            "provider": provider_name,
            "model_name": model_name,
            "adjustment_percent": round(adjustment_percent, 2),
            "confidence": confidence,
            "below_confidence_threshold": confidence < min_confidence,
            "final_price": final_price,
            "reason": str(raw.get("reason") or "").strip(),
            "market_trend": str(raw.get("market_trend") or ""),
            "risk": str(raw.get("risk") or ""),
            "recommended_buy_price": _safe_int(raw.get("recommended_buy_price"), None) if raw.get("recommended_buy_price") is not None else None,
            "recommended_sell_price": _safe_int(raw.get("recommended_sell_price"), None) if raw.get("recommended_sell_price") is not None else None,
            "warnings": warnings,
        }
    except Exception as e:
        _log_analysis(valuation_id, model.get("id"), capacity.get("id"), provider_name, model_name,
                       context, raw if isinstance(raw, dict) else {}, 0.0, 0, None, [], str(e))
        return None

    _log_analysis(valuation_id, model.get("id"), capacity.get("id"), provider_name, model_name,
                  context, raw, result["adjustment_percent"], confidence, final_price, warnings, "")
    return result
