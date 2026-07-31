"""قرارداد مشترک همهٔ درگاه‌های پرداخت — دقیقاً همون الگوی iphone_valuation/ai_providers/base.py.

هر ماژول درگاه سه تابع پیاده‌سازی می‌کنه:

    create_payment(amount_toman, callback_url, description, config) -> dict
        خروجی: {"ok": bool, "authority": str, "payment_url": str, "error": str}
        - authority = شناسهٔ یکتای تراکنش نزد درگاه (Authority زرین‌پال، trackId زیبال، code پی‌پینگ)
          که بعداً برای verify لازمه و روی ردیف تراکنش ذخیره می‌شه.

    parse_callback(query, form) -> dict
        خروجی: {"authority": str, "success": bool}
        - از پارامترهای بازگشتی درگاه (که اسمشون در هر درگاه فرق داره) شناسهٔ تراکنش و
          اینکه کاربر پرداخت رو کامل کرده یا لغو کرده رو استخراج می‌کنه.

    verify_payment(authority, amount_toman, config) -> dict
        خروجی: {"ok": bool, "ref_id": str, "error": str}
        - فیلدهای اختیاری (فقط اگه درگاه پشتیبانی کنه، وگرنه غایب/خالی): "card_pan"
          (شمارهٔ کارت ماسک‌شدهٔ برگشتی از خودِ درگاه، نه خام)، "card_hash", "fee_type",
          "fee" — برای ذخیرهٔ اطلاعات حسابداری/پیگیری تراکنش، نه اجباری برای هر درگاه.

نکتهٔ واحدِ حیاتی (پول): مبلغ داخلی همیشه **تومان** است. هر درگاه خودش می‌دونه واحد
API‌اش چیه و داخل خودش تبدیل می‌کنه (زرین‌پال/زیبال ریال = تومان×۱۰، پی‌پینگ تومان بدون تبدیل).
هیچ تبدیلی بیرون از ماژول درگاه انجام نمی‌شه تا یک‌جا و بدون ابهام بمونه.
"""


class PaymentGatewayError(Exception):
    """خطای عمومی درگاه — create/verify در صورت شکست این رو raise می‌کنن یا در
    خروجی ok=False + error برمی‌گردونن (هر دو مدیریت می‌شن)."""
    pass


RIAL_PER_TOMAN = 10
