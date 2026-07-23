"""
core/ — مغز مرکزی StockLand
سرویس‌های خالص منطق کسب‌وکار — بدون وابستگی به تلگرام، HTML یا FastAPI.
همه کلاینت‌ها (ربات، پنل، API، PWA، اپ‌ها) از این لایه استفاده می‌کنند.
"""
from . import products, orders, wallet, partners, referrals
