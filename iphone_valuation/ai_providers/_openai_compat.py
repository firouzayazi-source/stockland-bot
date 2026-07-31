"""کمکی مشترک provider های سازگار با OpenAI Chat Completions API — OpenAI خودش،
OpenRouter، DeepSeek هر سه از پکیج `openai` با یه `base_url` متفاوت استفاده می‌کنن، پس
منطق مشترک این‌جا یه‌بار نوشته می‌شه (نه سه‌بار تکراری). هیچ‌کدوم مستقیم provider ثبت‌شده
در __init__.py نیستن — فقط این تابع رو با پارامترهای خودشون صدا می‌زنن."""
import json

from .base import AIProviderError, SCHEMA, SYSTEM_PROMPT


def analyze_openai_compatible(context: dict, api_key: str, model: str,
                               base_url: str | None, default_model: str) -> dict:
    try:
        import openai
    except ImportError as e:
        raise AIProviderError("پکیج openai نصب نیست") from e

    # timeout صریح — بدونش SDK به پیش‌فرض داخلی خودش وابسته می‌شد؛ این تابع هر سه
    # provider (OpenAI/OpenRouter/DeepSeek) رو سرویس می‌ده، پس این محافظت هر سه رو می‌گیره.
    client = (openai.OpenAI(api_key=api_key, base_url=base_url, timeout=30.0) if base_url
              else openai.OpenAI(api_key=api_key, timeout=30.0))
    max_adjust = context.get("max_adjust_percent", 5)
    user_content = (
        "این اطلاعات کامل کارشناسی رو تحلیل کن و طبق schema زیر، فقط یک شیء JSON خام "
        "(بدون توضیح اضافه، بدون فنس کد) خروجی بده:\n\n"
        f"schema: {json.dumps(SCHEMA, ensure_ascii=False)}\n\n"
        f"داده‌ها:\n{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"حداکثر بازهٔ مجاز adjustment_percent: دقیقاً بین {-max_adjust} تا {max_adjust}."
    )
    try:
        response = client.chat.completions.create(
            model=model or default_model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
    except Exception as e:
        raise AIProviderError(str(e)) from e

    text = ((response.choices[0].message.content or "") if response.choices else "").strip()
    if not text:
        raise AIProviderError("پاسخ متنی خالی بود")
    try:
        return json.loads(text)
    except Exception as e:
        raise AIProviderError(f"پاسخ JSON نامعتبر بود: {e}") from e
