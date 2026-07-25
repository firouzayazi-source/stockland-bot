"""تولید گزارش فارسی — قالب هوشمند قانون‌محور، بدون اتصال به هیچ سرویس AI خارجی.

طبق تصمیم مالک پروژه: این بخش «چرا این قیمت» رو توضیح می‌ده، نه اینکه خودش
قیمت تعیین کنه (قیمت از pricing_engine میاد). کاملاً قطعی و بدون وابستگی/هزینهٔ
API خارجیه؛ اگه بعداً خواستن به یه مدل زبانی واقعی وصل بشه، فقط باید همین تابع
جایگزین بشه — بقیهٔ سیستم به همون ورودی/خروجی وابسته‌ست.
"""


def _fmt(n: int) -> str:
    return f"{n:,}".replace(",", "٬")


def build_report(contributions: list[dict], score: int, verdict: dict, fair_price: int) -> str:
    negatives = sorted(
        [c for c in contributions if c["amount"] < 0], key=lambda c: c["amount"])[:3]
    positives = sorted(
        [c for c in contributions if c["amount"] > 0], key=lambda c: -c["amount"])[:2]

    lines = []
    if negatives:
        parts = "، ".join(c["label"] for c in negatives)
        total = sum(c["amount"] for c in negatives)
        lines.append(f"این دستگاه به دلیل {parts} حدود {_fmt(abs(total))} تومان کمتر از یک نمونهٔ کامل ارزش دارد.")
    if positives:
        parts = "، ".join(c["label"] for c in positives)
        total = sum(c["amount"] for c in positives)
        lines.append(f"از طرفی به دلیل {parts} حدود {_fmt(total)} تومان به ارزش دستگاه اضافه شده.")
    if not negatives and not positives:
        lines.append("این دستگاه در شرایط استاندارد بازار قرار داره، بدون افت یا افزایش قابل‌توجه.")

    lines.append(f"امتیاز StockLand این دستگاه {score} از ۱۰۰ است.")
    if verdict.get("ratio") is not None:
        if verdict["ratio"] < 1:
            lines.append(f"قیمت پیشنهادی فروشنده حدود {round((1-verdict['ratio'])*100)}٪ پایین‌تر از ارزش واقعی بازاره.")
        elif verdict["ratio"] > 1:
            lines.append(f"قیمت پیشنهادی فروشنده حدود {round((verdict['ratio']-1)*100)}٪ بالاتر از ارزش واقعی بازاره.")

    return " ".join(lines)
