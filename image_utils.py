"""فشرده‌سازی/resize خودکار تصاویر آپلودی (Pillow) — یک منبع مشترک بین
admin_panel.py (کاور/گالری آموزش، عکس محصول) و api.py (آواتار مینی‌اپ)،
تا مشکل کلاس لوگوی هیرو (بخش ۱۵ فاز ۱ ممیزی — ۱.۴۲MB برای نمایش ۷۶px)
دیگه برای آپلودهای آینده تکرار نشه.

fail-open عمدی: اگه Pillow نصب نباشه، عکس خراب/غیرقابل‌پردازش باشه، یا فشرده‌سازی
عملاً حجم رو بزرگ‌تر کنه، بایت‌های خام دست‌نخورده برمی‌گردن — در دسترس‌بودن آپلود
مهم‌تر از فشرده‌سازیه، هیچ‌وقت آپلود کاربر رو به‌خاطر این لایه نباید رد کرد.
"""

MAX_DIMENSION = 1600  # طولانی‌ترین ضلع؛ فراتر از این برای عکس محصول/کاور/آواتار بی‌فایده‌ست
JPEG_QUALITY = 85
WEBP_QUALITY = 85

# فقط این پسوندها fشرده می‌شن — gif عمداً مستثناست چون Pillow انیمیشن گیف رو
# موقع resize/save از دست می‌ده (فقط فریم اول باقی می‌مونه)
COMPRESSIBLE_EXTS = (".jpg", ".jpeg", ".png", ".webp")


def compress_image_bytes(data: bytes, ext: str) -> bytes:
    ext = (ext or "").lower()
    if ext not in COMPRESSIBLE_EXTS or not data:
        return data
    try:
        import io
        from PIL import Image

        im = Image.open(io.BytesIO(data))
        im.load()
        fmt = (im.format or "").upper()
        w, h = im.size
        if max(w, h) > MAX_DIMENSION:
            ratio = MAX_DIMENSION / max(w, h)
            im = im.resize((max(1, int(w * ratio)), max(1, int(h * ratio))), Image.LANCZOS)

        buf = io.BytesIO()
        if ext in (".jpg", ".jpeg") or fmt == "JPEG":
            if im.mode in ("RGBA", "P", "LA"):
                im = im.convert("RGB")
            im.save(buf, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        elif ext == ".webp" or fmt == "WEBP":
            im.save(buf, format="WEBP", quality=WEBP_QUALITY)
        else:  # .png یا هر فرمت دیگهٔ ناشناخته
            im.save(buf, format="PNG", optimize=True)

        out = buf.getvalue()
        return out if 0 < len(out) < len(data) else data
    except Exception:
        return data
