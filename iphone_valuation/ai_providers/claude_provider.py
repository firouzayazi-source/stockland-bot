"""Provider Claude — SDK رسمی anthropic، طبق قرارداد base.py."""
import json

from .base import AIProviderError, SCHEMA, SYSTEM_PROMPT


def analyze(context: dict, api_key: str, model: str) -> dict:
    try:
        import anthropic
    except ImportError as e:
        raise AIProviderError("پکیج anthropic نصب نیست") from e

    # timeout صریح — بدونش SDK به پیش‌فرض داخلی خودش (که می‌تونه چند دقیقه باشه) وابسته
    # می‌شد و چون این تابع synchronous از داخل run_in_threadpool صدا زده می‌شه، یه
    # provider آویزان می‌تونست اون ترد رو برای مدت نامعین اشغال کنه.
    client = anthropic.Anthropic(api_key=api_key, timeout=30.0)
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
            system=SYSTEM_PROMPT,
            thinking={"type": "disabled"},
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
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
