"""Provider OpenRouter — دروازهٔ سازگار با OpenAI API که به مدل‌های مختلف (از جمله
غیر-OpenAI مثل Llama/Mixtral/...) وصل می‌شه؛ همون کلاینت openai با base_url اختصاصی."""
from ._openai_compat import analyze_openai_compatible


def analyze(context: dict, api_key: str, model: str) -> dict:
    return analyze_openai_compatible(
        context, api_key, model, base_url="https://openrouter.ai/api/v1",
        default_model="openai/gpt-4o")
