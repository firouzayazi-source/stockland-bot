import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

DB_PATH = os.getenv("DB_PATH")
if not DB_PATH:
    raise RuntimeError("DB_PATH environment variable is required")
DB_FULL_PATH = DB_PATH

# =====================
# Runtime configuration
# =====================
# NOTE: Secrets / instance-specific values must come from environment variables.

# Telegram bot token
BOT_TOKEN = os.getenv("BOT_TOKEN") or ""

# Webhook configuration
# اگر WEBHOOK_BASE_URL خالی باشد، ربات در حالت polling کار می‌کند (سازگاری با dev)
WEBHOOK_BASE_URL = (os.getenv("WEBHOOK_BASE_URL") or "https://panel.stland.ir").rstrip("/")
# اگر WEBHOOK_SECRET خالی بود، یک مقدار تصادفی در حافظه ساخته می‌شود (هر restart فرق می‌کند)
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET") or ""
if not WEBHOOK_SECRET:
    import secrets as _s
    WEBHOOK_SECRET = _s.token_urlsafe(32)
# فعال‌سازی webhook: اگر USE_WEBHOOK=1 و WEBHOOK_BASE_URL پر باشد
USE_WEBHOOK = (os.getenv("USE_WEBHOOK", "0") == "1") and bool(WEBHOOK_BASE_URL)

# راز داخلی برای محافظت از POST /payment/create (که فقط باید از داخل همین پروسه —
# services/payments.py و api.py — صدا زده بشه، نه مستقیم از اینترنت). دقیقاً همون
# الگوی WEBHOOK_SECRET بالا: اگر ست نشده، یک مقدار تصادفی در حافظه ساخته می‌شود.
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET") or ""
if not INTERNAL_API_SECRET:
    import secrets as _s2
    INTERNAL_API_SECRET = _s2.token_urlsafe(32)

# آدرس داخلی خودِ payment_service.py — services/payments.py قبلاً این fallback رو
# داشت ولی api.py مستقیم "http://127.0.0.1:8001" رو دو جا هاردکد کرده بود؛ حالا
# هردو از همین یک منبع می‌خونن (بخش ۲۴ ممیزی — قابلیت تنظیم پورت/میزبان از env).
PAYMENT_API_BASE_URL = (os.getenv("PAYMENT_API_BASE_URL") or f"http://127.0.0.1:{os.getenv('PORT') or '8001'}").rstrip("/")

# Admin numeric ID
ADMIN_ID = int(os.getenv("ADMIN_ID", "0") or "0")

# Zarinpal settings
# Zarinpal settings
ZARINPAL_MERCHANT_ID = os.getenv("ZARINPAL_MERCHANT_ID") or ""
ZARINPAL_SANDBOX = (os.getenv("ZARINPAL_SANDBOX", "0") == "1")

# 🔴 Callback مستقیم به FastAPI (نسخه نهایی)
#BASE_CALLBACK_URL = "http://82.115.25.45:8000/payment/callback"
BASE_CALLBACK_URL = os.getenv("BASE_CALLBACK_URL") or ""
ZARINPAL_REQUEST_URL = os.getenv(
    "ZARINPAL_REQUEST_URL",
    "https://api.zarinpal.com/pg/v4/payment/request.json",
)

ZARINPAL_STARTPAY_URL = os.getenv(
    "ZARINPAL_STARTPAY_URL",
    "https://www.zarinpal.com/pg/StartPay/",
)
# حداقل مبلغ شارژ کیف پول (تومان)
MIN_TOPUP_AMOUNT = int(os.getenv("MIN_TOPUP_AMOUNT", "10000"))  # تومان

# تابع کمکی برای متغیرهای محیطی (برای سازگاری با کد قدیمی)
def _require_env(key: str) -> str:
    """Get environment variable or raise error."""
    v = os.environ.get(key)
    if not v:
        raise RuntimeError(f"Environment variable {key} is required")
    return v


def validate_config() -> None:
    """Fail fast if critical settings are missing."""
    if not BOT_TOKEN:
        raise RuntimeError("Environment variable BOT_TOKEN is required")
    if not ADMIN_ID:
        raise RuntimeError("Environment variable ADMIN_ID is required")
