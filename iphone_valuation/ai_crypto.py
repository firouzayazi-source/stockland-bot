"""رمزنگاری کلید API هوش مصنوعی — Fernet (متقارن)، کلید از env var اختصاصی.

عمداً از SESSION_SECRET استفاده نمی‌کنیم (بخش ۱۳ CLAUDE.md: SESSION_SECRET دو پیش‌فرض
هاردکد ضعیف داره) — این‌جا اگه IV_AI_ENC_KEY ست نشده باشه، رمزنگاری/رمزگشایی صریحاً
شکست می‌خوره (fail closed) نه اینکه با یه کلید پیش‌فرض ضعیف کار کنه؛ یعنی بدون این env
var، قابلیت AI اصلاً قابل‌فعال‌شدن نیست."""
import base64
import hashlib
import os


class AICryptoError(Exception):
    pass


def _fernet():
    from cryptography.fernet import Fernet
    raw = os.getenv("IV_AI_ENC_KEY") or ""
    if not raw:
        raise AICryptoError("IV_AI_ENC_KEY تنظیم نشده — رمزنگاری کلید AI ممکن نیست")
    # هر رشتهٔ دلخواه رو به یه کلید ۳۲بایتی Fernet-سازگار تبدیل می‌کنه
    digest = hashlib.sha256(raw.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_api_key(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("utf-8")


def decrypt_api_key(token: str) -> str:
    if not token:
        return ""
    try:
        return _fernet().decrypt(token.encode("utf-8")).decode("utf-8")
    except Exception:
        return ""


def crypto_available() -> bool:
    return bool(os.getenv("IV_AI_ENC_KEY"))
