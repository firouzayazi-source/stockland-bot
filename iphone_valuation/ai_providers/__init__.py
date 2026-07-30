"""رجیستری provider های هوش مصنوعی کارشناسی — افزودن provider تازه یعنی یه فایل جدید
کنار claude_provider.py با همون قرارداد base.analyze + یه خط این‌جا، بدون تغییر
ai_advisor.py یا هیچ‌جای دیگهٔ پروژه.

هر ماژول فقط داخل خودِ analyze() پکیج SDKاش رو import می‌کنه (نه در سطح ماژول) — یعنی
نصب‌نبودن یه SDK (مثلاً google-generativeai) باعث شکست import کل این پکیج نمی‌شه، فقط
همون provider خاص موقع صدازدن AIProviderError برمی‌گردونه."""
from . import claude_provider
from . import openai_provider
from . import gemini_provider
from . import openrouter_provider
from . import deepseek_provider

AI_PROVIDERS = {
    "claude": claude_provider,
    "openai": openai_provider,
    "gemini": gemini_provider,
    "openrouter": openrouter_provider,
    "deepseek": deepseek_provider,
}

# برچسب نمایشی هر provider در پنل — کلید همون AI_PROVIDERS، مقدار برای UI
PROVIDER_LABELS = {
    "claude": "Claude (Anthropic)",
    "openai": "OpenAI (ChatGPT)",
    "gemini": "Google Gemini",
    "openrouter": "OpenRouter",
    "deepseek": "DeepSeek",
}

DEFAULT_PROVIDER = "claude"
