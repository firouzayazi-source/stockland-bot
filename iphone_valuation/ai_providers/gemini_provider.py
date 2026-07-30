"""Provider Google Gemini — پکیج تازهٔ `google-genai` (نه `google-generativeai` قدیمی
که رسماً deprecated شده و دیگه بروزرسانی نمی‌گیره)، طبق قرارداد base.py."""
import json

from .base import AIProviderError, SCHEMA, SYSTEM_PROMPT


def analyze(context: dict, api_key: str, model: str) -> dict:
    try:
        from google import genai
        from google.genai import types
    except ImportError as e:
        raise AIProviderError("پکیج google-genai نصب نیست") from e

    max_adjust = context.get("max_adjust_percent", 5)
    user_content = (
        "این اطلاعات کامل کارشناسی رو تحلیل کن و طبق schema خروجی بده:\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2, default=str)}\n\n"
        f"حداکثر بازهٔ مجاز adjustment_percent: دقیقاً بین {-max_adjust} تا {max_adjust}."
    )
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model or "gemini-2.0-flash",
            contents=user_content,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_json_schema=SCHEMA,
            ),
        )
    except Exception as e:
        raise AIProviderError(str(e)) from e

    text = (getattr(response, "text", "") or "").strip()
    if not text:
        raise AIProviderError("پاسخ متنی خالی بود")
    try:
        return json.loads(text)
    except Exception as e:
        raise AIProviderError(f"پاسخ JSON نامعتبر بود: {e}") from e
