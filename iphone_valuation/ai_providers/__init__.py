"""رجیستری provider های هوش مصنوعی کارشناسی — افزودن provider تازه یعنی یه فایل جدید
کنار claude_provider.py با همون قرارداد base.analyze + یه خط این‌جا، بدون تغییر
ai_advisor.py یا هیچ‌جای دیگهٔ پروژه."""
from . import claude_provider

AI_PROVIDERS = {
    "claude": claude_provider,
}

DEFAULT_PROVIDER = "claude"
