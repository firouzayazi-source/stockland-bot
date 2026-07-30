"""قرارداد مشترک provider های هوش مصنوعی کارشناسی — بخش ۲۲.۸/۲۲.۹ CLAUDE.md.

هر provider تازه فقط باید یه ماژول با همین یه تابع `analyze(context, api_key, model)`
بسازه و توی `AI_PROVIDERS` در __init__.py همین پکیج ثبت بشه — orchestrator
(`ai_advisor.py`) هیچ‌وقت مستقیم به یه provider خاص وابسته نیست، فقط این قرارداد رو
صدا می‌زنه.

خروجی الزامی analyze(): دیکشنری با کلیدهای
    final_price (int), confidence (int 0-100), adjustment_percent (float),
    reason (str), market_trend ("bullish"/"bearish"/"stable"), risk ("low"/"medium"/"high"),
    recommended_buy_price (int), recommended_sell_price (int), warnings (list[str])
در خطا باید AIProviderError پرتاب بشه — orchestrator خودش می‌گیرتش و هیچ‌وقت جریان
قیمت‌گذاری دیتامحور رو مسدود نمی‌کنه.

SCHEMA/SYSTEM_PROMPT این‌جا مشترکن (نه تکرار در هر provider) تا رفتار خروجی مستقل از
provider انتخابی یکسان بمونه."""

SCHEMA = {
    "type": "object",
    "properties": {
        "final_price": {"type": "integer"},
        "confidence": {"type": "integer"},
        "adjustment_percent": {"type": "number"},
        "reason": {"type": "string"},
        "market_trend": {"type": "string", "enum": ["bullish", "bearish", "stable"]},
        "risk": {"type": "string", "enum": ["low", "medium", "high"]},
        "recommended_buy_price": {"type": "integer"},
        "recommended_sell_price": {"type": "integer"},
        "warnings": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["final_price", "confidence", "adjustment_percent", "reason", "market_trend",
                 "risk", "recommended_buy_price", "recommended_sell_price", "warnings"],
    "additionalProperties": False,
}

SYSTEM_PROMPT = (
    "تو یک کارشناس ارزیابی قیمت آیفون در بازار ایران هستی، مکمل یک موتور قیمت‌گذاری "
    "قانون‌محور که از قبل قیمت پایه رو محاسبه کرده. وظیفهٔ تو اصلاح جزئی و توضیح این "
    "قیمته با توجه به شرایط لحظه‌ای بازار، نه ساختن یه عدد کاملاً تازه بی‌ربط به موتور. "
    "adjustment_percent باید نسبت به fair_price موتور باشه (مثبت=گران‌تر، منفی=ارزان‌تر) "
    "و دقیقاً داخل بازهٔ مجازی که در پیام کاربر اعلام می‌شه بمونه — هیچ‌وقت بیرون این بازه "
    "عدد نده. اگه داده‌های ورودی با هم ناهماهنگ بودن (مثلاً سلامت باتری خیلی پایین ولی "
    "شرایط ظاهری مثل گوشی نو، یا رجیستری نامعتبر ولی گارانتی فعال) حتماً توی warnings "
    "به فارسی و صریح اشاره کن — این مهم‌ترین کمکیه که می‌تونی بکنی. اگه اطلاعات کافی یا "
    "قابل‌اطمینان نبود، confidence رو صادقانه پایین گزارش کن، نه بالا. خروجی باید فقط "
    "و فقط یک شیء JSON خام مطابق schema باشه، بدون هیچ متن اضافه یا فنس کد."
)


class AIProviderError(Exception):
    pass
