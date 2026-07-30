"""قرارداد مشترک provider های هوش مصنوعی کارشناسی — بخش ۲۲.۸ CLAUDE.md.

هر provider تازه (OpenAI/Gemini/OpenRouter/DeepSeek و...) فقط باید یه ماژول با همین یه
تابع `analyze(context, api_key, model)` بسازه و توی `AI_PROVIDERS` در __init__.py همین
پکیج ثبت بشه — orchestrator (`ai_advisor.py`) هیچ‌وقت مستقیم به یه provider خاص وابسته
نیست، فقط این قرارداد رو صدا می‌زنه.

خروجی الزامی analyze(): دیکشنری با کلیدهای
    final_price (int), confidence (int 0-100), adjustment_percent (float),
    reason (str), market_trend ("bullish"/"bearish"/"stable"), risk ("low"/"medium"/"high"),
    recommended_buy_price (int), recommended_sell_price (int), warnings (list[str])
در خطا باید AIProviderError پرتاب بشه — orchestrator خودش می‌گیرتش و هیچ‌وقت جریان
قیمت‌گذاری دیتامحور رو مسدود نمی‌کنه."""


class AIProviderError(Exception):
    pass
