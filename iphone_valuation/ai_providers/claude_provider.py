"""Provider Claude — تنها provider پیاده‌سازی‌شده در این نشست. طبق قرارداد base.py."""
import json

from .base import AIProviderError

_SCHEMA = {
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

_SYSTEM_PROMPT = (
    "تو یک کارشناس ارزیابی قیمت آیفون در بازار ایران هستی، مکمل یک موتور قیمت‌گذاری "
    "قانون‌محور که از قبل قیمت پایه رو محاسبه کرده. وظیفهٔ تو اصلاح جزئی و توضیح این "
    "قیمته با توجه به شرایط لحظه‌ای بازار، نه ساختن یه عدد کاملاً تازه بی‌ربط به موتور. "
    "adjustment_percent باید نسبت به fair_price موتور باشه (مثبت=گران‌تر، منفی=ارزان‌تر) "
    "و دقیقاً داخل بازهٔ مجازی که در پیام کاربر اعلام می‌شه بمونه — هیچ‌وقت بیرون این بازه "
    "عدد نده. اگه داده‌های ورودی با هم ناهماهنگ بودن (مثلاً سلامت باتری خیلی پایین ولی "
    "شرایط ظاهری مثل گوشی نو، یا رجیستری نامعتبر ولی گارانتی فعال) حتماً توی warnings "
    "به فارسی و صریح اشاره کن — این مهم‌ترین کمکیه که می‌تونی بکنی. اگه اطلاعات کافی یا "
    "قابل‌اطمینان نبود، confidence رو صادقانه پایین گزارش کن، نه بالا."
)


def analyze(context: dict, api_key: str, model: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise AIProviderError("پکیج anthropic نصب نیست") from e

    client = anthropic.Anthropic(api_key=api_key)
    max_adjust = context.get("max_adjust_percent", 5)
    user_content = (
        "این اطلاعات کامل کارشناسی رو تحلیل کن و طبق schema خروجی بده:\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"حداکثر بازهٔ مجاز adjustment_percent: دقیقاً بین {-max_adjust} تا {max_adjust}."
    )
    try:
        response = client.messages.create(
            model=model or "claude-opus-5",
            max_tokens=2048,
            system=_SYSTEM_PROMPT,
            thinking={"type": "disabled"},
            output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
            messages=[{"role": "user", "content": user_content}],
        )
    except Exception as e:
        raise AIProviderError(str(e)) from e

    if getattr(response, "stop_reason", None) == "refusal":
        raise AIProviderError("مدل درخواست رو رد کرد (refusal)")

    text = next((b.text for b in response.content if b.type == "text"), "")
    if not text:
        raise AIProviderError("پاسخ متنی خالی بود")
    try:
        data = json.loads(text)
    except Exception as e:
        raise AIProviderError(f"پاسخ JSON نامعتبر بود: {e}") from e
    return data
