"""رجیستری درگاه‌های پرداخت — دقیقاً همون الگوی iphone_valuation/ai_providers/__init__.py.

افزودن یک درگاه تازه = یک فایل ماژول جدید (مطابق قرارداد base.py) + یک خط این‌جا.
هیچ تغییری در payment_service.py یا admin_panel.py برای درگاه تازه لازم نیست.

هر ورودی: کلید = code یکتای درگاه، مقدار = (ماژول، برچسب فارسی، لیست فیلدهای اعتبار).
`fields` برای ساختن خودکار فرم پنل استفاده می‌شه (بدون هاردکد فرم per-درگاه):
هر فیلد = (نام_کلید_داخل_credentials، برچسب_فارسی).
"""
from . import zarinpal_gateway, zibal_gateway, payping_gateway
from .base import PaymentGatewayError  # noqa: F401 (re-export برای مصرف‌کننده‌ها)

PAYMENT_GATEWAYS = {
    "zarinpal": {
        "module": zarinpal_gateway,
        "label": "زرین‌پال",
        "fields": [("merchant_id", "مرچنت‌آیدی (Merchant ID)")],
        "supports_sandbox": True,
    },
    "zibal": {
        "module": zibal_gateway,
        "label": "زیبال",
        "fields": [("merchant", "مرچنت (Merchant)")],
        "supports_sandbox": True,
    },
    "payping": {
        "module": payping_gateway,
        "label": "پی‌پینگ (PayPing)",
        "fields": [("token", "توکن API")],
        "supports_sandbox": False,
    },
}

# درگاه پیش‌فرض که اگه هیچ‌چیز در پنل تنظیم نشده باشه، سیستم ازش (با env قدیمی) استفاده می‌کنه.
DEFAULT_GATEWAY = "zarinpal"


def get_gateway_module(code: str):
    entry = PAYMENT_GATEWAYS.get(code)
    return entry["module"] if entry else None


def gateway_label(code: str) -> str:
    entry = PAYMENT_GATEWAYS.get(code)
    return entry["label"] if entry else code
