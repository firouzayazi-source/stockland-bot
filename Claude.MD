# StockLand — راهنمای پروژه برای Claude Code

ربات فروشگاه دیجیتال تلگرام + پنل مدیریت وب. تمام UI به **فارسی** و **RTL** است.

## معماری

| فایل | نقش |
|---|---|
| `bot.py` | ربات تلگرام (pyTelegramBotAPI / telebot، parse_mode=HTML) — همه هندلرها |
| `admin_panel.py` | پنل ادمین (FastAPI router + Tailwind CDN + فونت Vazirmatn، RTL) |
| `db.py` | SQLite — کل اسکیما و کوئری‌ها |
| `keyboards.py` | سازنده‌های Reply/Inline Keyboard |
| `ui_texts.py` | متن‌ها و برچسب دکمه‌ها + تابع `t()` |
| `stbak_engine.py` | موتور بکاپ/ریست ماژول‌محور (`MODULES`) |
| `payment_service.py` | درگاه زرین‌پال |
| `config.py` | تنظیمات — `DB_PATH` اجباری است (بدون آن RuntimeError می‌دهد) |

**متغیرهای محیطی:** `DB_PATH` (اجباری)، `BOT_TOKEN`، `ADMIN_WEB_USERNAME`، `ADMIN_WEB_PASSWORD` (سوپرادمین از env می‌آید؛ جدول admins قابل ریست است).

## قوانین ثابت پروژه — هرگز نقض نشود

1. **اعداد فارسی سراسری.**
   - ربات: پچ سراسری `_fa_digits` روی `send_message` / `edit_message_text` / `reply_to` / کپشن‌ها / `answer_callback_query` در `bot.py` اعمال شده. لینک‌ها، بلوک‌های `<code>`/`<pre>`، یوزرنیم‌ها (`@x`) و دستورات (`/start`) **مستثنا** هستند تا خراب نشوند. پیام جدید ننویس که خودش تبدیل کند — پچ خودکار است.
   - پنل: مبدل JS سراسری (MutationObserver) در `_layout`. عناصر `INPUT/TEXTAREA/SELECT/CODE/PRE` و کلاس `.no-fa` مستثنا هستند.

2. **برچسب دکمه‌ها هرگز هاردکد نمی‌شود.** همیشه:
   ```python
   t("KEY", DEFAULT_UI_TEXTS.get("KEY", "متن پیش‌فرض"))
   ```
   کلید جدید را به `DEFAULT_UI_TEXTS` اضافه کن و اگر ادمین باید ویرایشش کند به `EDITABLE_BUTTON_GROUPS` (+ آیکون در `BUTTON_ICONS`).

3. **آیکون اول رشته** (در RTL سمت راست دیده می‌شود): `"🧾 خریدهای من"` ✅ — `"خریدهای من 🧾"` ❌

4. **دکمه‌های منوی اصلی** با کلیدهای `MAIN_BTN_ENABLED_<KEY>` در جدول `ui_texts` فعال/غیرفعال می‌شوند؛ لیست کلیدها = `MAIN_BUTTON_KEYS`. راهنمای عمومی (`MAIN_BTN_GUIDE`) حذف شده؛ «📖 راهنما و قوانین» (`BTN_PARTNER_GUIDE`) فقط دکمه Reply برای همکاران تأییدشده است (هندلر `handle_partner_guide_reply`) و از داشبورد inline همکار حذف شده.

5. **متن‌های قابل‌ویرایش ادمین فقط:** `WALLET_QUICK_AMOUNTS`، `HELP_TEXT`، `PARTNER_GUIDE_TEXT` (لیست `CRITICAL_TEXT_KEYS`). بقیه متن‌ها پیش‌فرض ثابت‌اند — سیستم «مدیریت متن‌ها» عمداً حذف شده، برنگردان.

6. **دسته‌های ریشه دکمه بازگشت ندارند.** فقط زیردسته‌ها «🔙 بازگشت» به والد دارند.

7. **سفارش برگشتی (`status='returned'`) از دید کاربر کاملاً مخفی است** — هم در `get_user_orders` هم در جزئیات سفارش. ادمین همچنان می‌بیند.

8. **زنجیره پورسانت زیرمجموعه** (روی *هر* خرید، در `process_referral_commission`):
   `commission_fixed` سطح معرف ← اگر ۰ بود `commission_percent` سطح ← اگر ۰ بود درصد عمومی `partner_commission.percent`. سقف `max_payout` و کف `min_order` اعمال می‌شود. پاداش اولین خرید (`process_referral_reward`) جداست و سر جایش می‌ماند.

9. **اعتبارسنجی تخفیف همیشه با `user_id`:** `validate_discount(code, product_id=…, amount=…, user_id=uid)` و `use_discount(code_id, user_id=uid)` — بدون user_id محدودیت‌های هر-کاربر/اولین-خرید/VIP کار نمی‌کنند. تعریف VIP: ستون `users.tags` شامل `vip` (case-insensitive) **یا** همکار `approved`.

10. **آپلود فایل موجودی:** اگر `purchase_price <= 0` بود بعد از درج، ریدایرکت به `/admin/feed/{pid}/batch-pricing` (قیمت خرید اجباری + هزینه جانبی + یادداشت ← `create_feed_batch` + `link_batch_to_feed`). این جریان را دور نزن.

11. **تم پنل:** `admin_preferences` → `dark_mode` ∈ {`'1'`,`'0'`,`'auto'`} و `classic_mode`. حالت `auto` از `prefers-color-scheme` پیروی می‌کند. استایل شب با اوررایدهای کلاس‌های Tailwind پیاده شده — UI جدید را با کلاس‌های استاندارد Tailwind بنویس (`text-gray-700`, `bg-gray-50`, `.card`, …) تا خودکار در حالت شب درست شود.

12. **جدول جدید = ماژول بکاپ.** هر جدول تازه را به ماژول مناسب در `MODULES` داخل `stbak_engine.py` اضافه کن وگرنه بکاپ/ریست ناقص می‌شود.

13. **HTML پنل داخل f-string است:** آکولاد JS/CSS باید `{{ }}` باشد. helperها: `_layout`, `_card`, `_btn`, `_input`, `e()` (escape), `_log(request, action, section, details)`, `_redir`.

## تست قبل از تحویل

```bash
# سینتکس
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['bot.py','admin_panel.py','db.py','keyboards.py','ui_texts.py','stbak_engine.py']]"

# اسموک‌تست با دیتابیس موقت
DB_PATH=/tmp/test.db BOT_TOKEN=123:TEST python3 -c "import db, ui_texts, keyboards"
```

هر تحویل باید **فهرست فایل‌های تغییرکرده** را اعلام کند تا انتخابی کامیت شوند. فایل‌های دست‌نخورده را بازنویسی نکن.

## جداول کلیدی

`users` (tags برای VIP) · `wallets` / `zarinpal_transactions` (status='paid') / `card_receipts` (status='approved') · `orders` (status، buyer_type) · `products` / `product_feed` / `feed_batches` · `partners` / `partner_tiers` (commission_percent, commission_fixed) / `partner_commission` / `partner_wallets` · `referrals` / `referral_settings` · `discount_codes` / `discount_usage` · `expenses` / `expense_categories` · `admins` / `admin_preferences` · `ui_texts`

## سبک کار

- پاسخ‌ها و کامنت‌ها فارسی؛ نام متغیر/تابع انگلیسی.
- تغییرات جراحی و حداقلی — «مابقی کد دستکاری نشه».
- قبل از فیچرهای بزرگ، برداشتت را خلاصه بگو و تأیید بگیر؛ بعد کد بزن.
