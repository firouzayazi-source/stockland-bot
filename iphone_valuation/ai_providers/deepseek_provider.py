"""Provider DeepSeek — API سازگار با OpenAI، endpoint اختصاصی خودش."""
from ._openai_compat import analyze_openai_compatible


def analyze(context: dict, api_key: str, model: str) -> dict:
    return analyze_openai_compatible(
        context, api_key, model, base_url="https://api.deepseek.com",
        default_model="deepseek-chat")
