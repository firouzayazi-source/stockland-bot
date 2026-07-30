"""Provider OpenAI — SDK رسمی openai، طبق قرارداد base.py."""
from ._openai_compat import analyze_openai_compatible


def analyze(context: dict, api_key: str, model: str) -> dict:
    return analyze_openai_compatible(context, api_key, model, base_url=None, default_model="gpt-4o")
