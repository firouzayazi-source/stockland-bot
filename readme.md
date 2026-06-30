# StockLand — مستندات کامل پروژه

> این فایل برای این ساخته شده که اگر پروژه به هوش مصنوعی دیگری سپرده شود یا در نشست جدیدی به Claude داده شود، تمام context لازم در یک‌جا موجود باشد. آخرین به‌روزرسانی: تابستان ۲۰۲۶.

---

## ۱. معرفی کلی

**StockLand** یک فروشگاه دیجیتال مبتنی بر **ربات تلگرام** است که محصولات دیجیتال (مثل اپل آیدی، اکانت و غیره) را با تحویل خودکار از موجودی (Feed) می‌فروشد. ربات سیستم کیف‌پول، همکاری/افیلیت، تیکتینگ، حسابداری سبک و یک پنل مدیریت کامل دارد.

- **مدیر پروژه:** فیروز ایازی — تنها توسعه‌دهنده و مدیر فنی پروژه. فایل‌ها را مستقیماً روی GitHub آپلود و سپس روی سرور Deploy می‌کند (بدون استفاده مستقیم از دستورات git در تعامل با Claude).
- **سرور:** VPS آلمان — مسیر اپلیکیشن: `/opt/stockland/app/`
- **دیتابیس:** SQLite — مسیر: `/opt/stockland/data/stockland.db`
- **Stack:** Python (FastAPI برای پنل + python-telegram-bot/telebot برای ربات) + Uvicorn + systemd
- **دامنه پنل مدیریت:** `https://panel.stland.ir/admin/`
- **GitHub:** `https://github.com/firouzayazi-source/stockland-bot.git`

---

## ۲. فایل‌های اصلی پروژه

| فایل | خطوط تقریبی | مسئولیت |
|---|---|---|
| `bot.py` | ~۵۵۵۰ | منطق کامل ربات تلگرام: منوها، خرید، پرداخت، کیف‌پول، همکاری، تیکت، امتیازدهی |
| `admin_panel.py` | ~۸۵۸۰ | پنل مدیریت تحت وب (FastAPI): همه صفحات، route ها، گزارش‌ها |
| `db.py` | ~۴۳۸۰ | تمام توابع دیتابیس، schema ها، query ها |
| `keyboards.py` | ~۱۷۵ | ساخت کیبورد اصلی ربات (`main_menu`) — داینامیک بر اساس دسته‌بندی و وضعیت همکاری |
| `ui_texts.py` | ~۴۲۰ | مدیریت متمرکز همه متن‌های قابل ویرایش ربات (`DEFAULT_UI_TEXTS`, `TEXT_GROUPS`) |
| `stbak_engine.py` | ~۳۰۰ | موتور بکاپ/ریست/ریستور (فرمت `.stbak`)، شامل تعریف ماژول‌های قابل بکاپ |
| `payment_service.py` | ~۹۸۰ | سرویس مستقل پرداخت (احتمالاً Zarinpal) و webhook handling |
| `payments.py` | ~۱۵۰ | توابع کمکی پرداخت (شارژ کیف‌پول از درگاه) |

### ابزار تست سلامت (Health Check)
مسیر: `/opt/stockland/app/test_health.py`
دستور اجرا (الیاس شده): `health`
بررسی می‌کند: اتصال DB، محصولات، کیف‌پول، کیف‌پول همکاری، claim موجودی، و وجود همه handler های کلیدی.

```bash
alias health='/opt/stockland/venv/bin/python3 /opt/stockland/app/test_health.py'
```

---

## ۳. قوانین ثابت پروژه (الزامی — همیشه رعایت شود)

این قوانین توسط مدیر پروژه تثبیت شده و در همه توسعه‌های آینده باید بدون استثنا رعایت شوند:

1. **ممنوعیت تغییر بدون هماهنگی** — هیچ بخشی (معماری، DB، route، handler، callback، نام‌گذاری) بدون تأیید صریح تغییر نکند؛ ابتدا پیشنهاد داده شود.
2. **تصمیمات تثبیت‌شده** (بخش ۴) قانون ثابت پروژه محسوب می‌شوند و بدون تأیید صریح تغییر نمی‌کنند.
3. **عدم ارائه دستورات Git** — هرگز `git add/commit/push/...` پیشنهاد داده نشود. مدیر فایل را مستقیم آپلود/دیپلوی می‌کند.
4. **ممنوعیت Regression** — رفع یک باگ نباید باعث خرابی بخش دیگری شود؛ همه وابستگی‌ها قبل از پایان توسعه بررسی شوند.
5. **تست اجباری** — هیچ توسعه‌ای کامل تلقی نمی‌شود مگر بخش‌های مرتبط (منوی اصلی، پنل همکار، خرید، پرداخت، مدیریت متن‌ها، بکاپ، ...) تست شده باشند.
6. **حداقل تغییر (Minimal Change)** — فقط فایل/تابع مرتبط مستقیم با اصلاحیه تغییر کند؛ Refactor بخش‌های نامرتبط ممنوع.
7. **گزارش تغییرات** — پس از هر اصلاحیه: فایل‌های تغییریافته + علت + بخش‌های تست‌شده گزارش شود.

---

## ۴. تصمیمات معماری تثبیت‌شده (Locked-In)

این موارد یک‌بار نهایی شده‌اند و **نباید بدون تأیید صریح تغییر کنند**:

- جریان پرداخت از callback های `confirm_wallet_{category}_{pid}` و `confirm_full_{category}_{pid}` استفاده می‌کند (نه `do_pay_`).
- کد تخفیف **فقط یک‌بار** و **قبل از انتخاب روش پرداخت** در `_show_order_summary` جمع‌آوری می‌شود؛ هرگز در `handle_confirm_wallet`/`handle_confirm_full` دوباره پرسیده نمی‌شود.
- `send_product_detail` مستقیماً به `_show_order_summary` می‌رود (بدون صفحه واسط با دکمه‌های confirm جدا).
- منوی همکار تأییدشده: دسته‌بندی‌ها + (خریدهای من | کیف‌پول) + پنل همکار (یک ردیف کامل) + راهنمای همکاری. دکمه پشتیبانی برای همکار حذف است (داخل پنل همکار موجود است).
- کارت‌به‌کارت: مستقیم بعد از کلیک، شماره کارت نمایش داده می‌شود و رسید (عکس) درخواست می‌شود — **بدون مرحله جداگانه دریافت مبلغ از کاربر**. مبلغ توسط ادمین در لحظه تأیید در پنل وارد می‌شود.
- مرکز مالی (کارت‌به‌کارت + تسویه همکار) به‌صورت Embed شده در همان صفحه `/admin/tickets` (پایین لیست تیکت‌ها) نمایش داده می‌شود — نه صفحه جدا. آیکون مستقل navbar برای آن وجود ندارد؛ فقط زنگوله (🔔) که شمارش تیکت+مالی را با هم نشان می‌دهد.
- لیست تیکت‌ها و مرکز مالی هر دو الگوی «۳ مورد آخر نمایان + دکمه نمایش بقیه (toggle با addEventListener، نه inline onclick)» دارند.

---

## ۵. جداول دیتابیس (کامل)

### کاربران و کیف‌پول
- `users` — اطلاعات پایه کاربر
- `wallets` — موجودی کیف‌پول اصلی
- `wallet_orders`, `zarinpal_transactions` — تراکنش‌های شارژ

### محصولات و موجودی
- `categories` — دسته‌بندی محصولات (سلسله‌مراتبی)
- `products` — محصولات (شامل `category_id`, قیمت همکار)
- `product_feed` — موجودی واقعی هر محصول (هر ردیف = یک آیتم قابل تحویل؛ `delivered`, `batch_id`)
- `feed_batches` — اطلاعات مالی هر Batch ورودی موجودی (`purchase_price`, `side_cost`, `item_count`, `notes`) — برای حسابداری
- `feed_alert_settings` — تنظیمات هشدار کمبود موجودی
- `stock_subscriptions` — درخواست اطلاع‌رسانی شارژ مجدد موجودی

### سفارش‌ها
- `orders` — سفارش‌ها (`user_id` به‌صورت TEXT؛ همیشه `CAST(user_id AS INTEGER)` لازم است)
- `delivery_messages`, `other_services`

### همکاری/افیلیت
- `partners` — اطلاعات پایه همکار (وضعیت approved/pending)
- `partner_tiers` — سطوح همکاری (`min_orders`, `icon`, `name`, `photo_file_id` برای بنر)
- `partner_commission` — درصد پورسانت هر سطح
- `partner_wallets`, `partner_transactions` — کیف‌پول همکاری مجزا از کیف‌پول اصلی
- `partner_payouts`, `partner_payout_settings` — درخواست‌های تسویه و تنظیمات (حداقل/حداکثر مبلغ، ساعات بررسی)
- `partner_bank_info` — اطلاعات بانکی همکار (کارت، شبا، نام صاحب حساب، آدرس)
- `referrals`, `referral_settings` — سیستم معرفی کاربر عادی (پاداش معرف)
- `sellers`, `seller_levels`, `seller_commissions`, `seller_payouts` — (ساختار قدیمی/موازی همکاری؛ بررسی نیاز به یکپارچه‌سازی دارد)

### تیکت و پشتیبانی
- `tickets` — تیکت‌ها (`type`: support/product_setup/partner_support؛ `status` چندحالته؛ `archived` برای آرشیو)
- `ticket_messages` — پیام‌های هر تیکت (رسانه، sender، source)

### کارت‌به‌کارت
- `card_receipts` — درخواست‌های شارژ کارت‌به‌کارت (`file_id` تلگرام — تصویر روی سرور ما ذخیره نمی‌شود، فقط رفرنس تلگرام نگه داشته می‌شود و موقع نمایش proxy می‌شود)

### تخفیف
- `discount_codes`, `discount_usage`

### امتیازدهی و FAQ
- `product_ratings` — امتیاز ۱-۵ + کامنت کاربر بعد از خرید
- `product_faqs` — سوالات متداول هر محصول

### حسابداری
- `expenses`, `expense_categories` — هزینه‌های فروشگاه

### تنظیمات و سیستم
- `bot_config` — کلید/مقدار عمومی (شامل `maintenance` برای حالت تعمیرات)
- `panel_theme` — تم پنل (روز/شب/کلاسیک)
- `admin_preferences` — ترجیحات هر مدیر (مثلاً تم انتخابی) به ازای `admin_id`
- `ui_texts` — متن‌های سفارشی‌شده (override روی `DEFAULT_UI_TEXTS`)
- `admin_notes`, `admin_note_replies` — یادداشت‌های داخلی مدیران
- `admin_logs` — لاگ کامل عملیات پنل

---

## ۶. جریان‌های کلیدی (Flows)

### ۶.۱ خرید محصول
```
کاربر روی محصول کلیک می‌کند
  → send_product_detail()
  → مستقیم _show_order_summary() (نمایش قیمت + امتیاز + FAQ + ضمانت + دکمه کد تخفیف)
  → [اختیاری] کاربر کد تخفیف وارد می‌کند → اعمال در user_states[uid]["applied_discount"]
  → کاربر روش پرداخت را انتخاب می‌کند:
      • کیف‌پول کافی  → دکمه «پرداخت با کیف‌پول» (confirm_wallet_) + «پرداخت از درگاه» (confirm_full_)
      • کیف‌پول ناکافی → «پرداخت ترکیبی» (confirm_wallet_، باقیمانده به درگاه) + «پرداخت کامل از درگاه»
      • کیف‌پول صفر    → فقط «پرداخت از درگاه»
  → finalize_product_order() → claim_next_feed_item() → ارسال آیتم به کاربر + order_set_feed_id()
  → ۳۰ ثانیه بعد: درخواست امتیازدهی خودکار ارسال می‌شود
```

### ۶.۲ سیستم همکاری
```
کاربر «درخواست همکاری» می‌زند → تیکت partner_support ایجاد می‌شود
ادمین تأیید می‌کند → approve_partner() → keyboard کاربر فوراً آپدیت می‌شود
  (بدون نیاز به /start مجدد) → دکمه «درخواست همکاری» به «پنل همکار» تبدیل می‌شود
همکار از داشبورد: فروشندگان من / پروفایل / کیف‌پول همکاری / لینک معرفی / پشتیبانی / راهنما
خرید با buyer_type='partner' → قیمت ویژه همکار اعمال می‌شود
پورسانت معرفی به partner_wallets واریز می‌شود
همکار درخواست تسویه می‌زند → ادمین در مرکز مالی تأیید/رد می‌کند
  تأیید → کسر از partner_wallets + پیام به کاربر + لاگ
```

### ۶.۳ کارت‌به‌کارت
```
کاربر «کارت به کارت» می‌زند → state: card2card_receipt
  → شماره کارت نمایش داده می‌شود (مستقیم، بدون پرسیدن مبلغ)
کاربر عکس رسید می‌فرستد → handle_card2card_photo()
  → save_card_receipt(amount=0, file_id) → ثبت در card_receipts
  → پیام به ادمین (با دکمه‌های /approve_receipt_ID و /reject_receipt_ID)
ادمین در مرکز مالی (/admin/tickets#financial) وارد جزئیات رسید می‌شود
  → مبلغ واقعی را وارد می‌کند (چون کاربر مبلغ وارد نکرده) → تأیید
  → update_card_receipt(amount=مبلغ تأییدی) + add_wallet_balance() + اطلاع به کاربر
```

### ۶.۴ مرکز مالی (Financial Queue)
طراحی **Type-based** برای توسعه‌پذیری بدون تغییر معماری:
- تابع مشترک `_financial_section_html(type_filter, q, sort, link_fn)` در `admin_panel.py` هم در صفحه مستقل `/admin/financial` و هم Embed شده در `/admin/tickets` استفاده می‌شود.
- انواع فعلی: `card2card`, `payout`. افزودن نوع جدید (استرداد، مغایرت، ...) فقط با اضافه‌کردن یک بلوک `rows.append(...)` در همان تابع ممکن است.
- جستجو روی نام/آیدی/مبلغ/وضعیت/نوع. مرتب‌سازی روی تاریخ/مبلغ.
- جزئیات هر نوع در صفحه مستقل خودش (`/admin/receipts/{id}/view` یا `/admin/partners/payout/{id}`) رندر می‌شود — مرکز مالی فقط لینک می‌دهد.

### ۶.۵ بکاپ خودکار
- هر شب ساعت ۴ صبح، Thread پس‌زمینه (`_start_auto_backup_thread` در `admin_panel.py`، صدا زده‌شده از `payment_service.py`) بکاپ می‌گیرد.
- مسیر ذخیره: `/tmp/stockland_backups/auto_YYYYMMDD_HHMMSS.stbak`
- فقط ۵ بکاپ آخر نگه داشته می‌شود.
- در پنل، بخش بازیابی یک Dropdown از بکاپ‌های خودکار نشان می‌دهد (`POST /admin/database/restore-auto`) — بدون نیاز به آپلود دستی فایل.

### ۶.۶ Maintenance Mode
- `db.get_maintenance_mode()` / `set_maintenance_mode()` روی جدول `bot_config`.
- در `bot.py`: `maintenance_blocker` (message handler) و `maintenance_blocker_cb` (callback handler) با اولویت بالا ثبت شده‌اند؛ اگر فعال باشد و کاربر ادمین نباشد، پیام ثابت نمایش داده و فرآیند متوقف می‌شود.
- **توجه:** ادمین (`ADMIN_ID`) همیشه از این حالت مستثناست — این By Design است، نه باگ.
- toggle در `/admin/settings/panel`.

---

## ۷. سیستم مدیریت متن‌ها (UI Texts)

تمام متن‌ها و دکمه‌های قابل مشاهده کاربر — به‌جز محتوای اختصاصی ماژول‌ها (توضیح محصول، بنر و ...) — از `ui_texts.py` می‌آیند:

- `DEFAULT_UI_TEXTS` — دیکشنری پیش‌فرض همه کلیدها
- `TEXT_GROUPS` — دسته‌بندی کلیدها برای نمایش در پنل (۱۰+ گروه: دکمه‌های همکار، پروفایل، ناوبری، پیام‌های همکار/تسویه/خریدها/تیکت/عمومی، ...)
- تابع `t(key, default)` در `bot.py` مقدار سفارشی (از جدول `ui_texts`) یا پیش‌فرض را برمی‌گرداند
- ویرایش از پنل: `/admin/settings` (بخش مدیریت متن‌ها)

**نکته فنی مهم:** هرگز از نام متغیر `t` به‌عنوان متغیر حلقه (`for t in ...`) در نزدیکی استفاده از تابع `t()` استفاده نشود — تداخل نام باعث کرش خاموش می‌شود (یک‌بار این باگ رخ داده و رفع شده).

---

## ۸. الگوهای فنی تکرارشونده (برای حفظ ثبات)

### `_partner_edit(call, text, kb)` در `bot.py`
برای ویرایش پیام در callback های پنل همکار — چون داشبورد همکار ممکن است Photo (بنر سطح) باشد و `edit_message_text` روی پیام عکس‌دار Exception می‌دهد:
1. تلاش `edit_message_text`
2. شکست → `edit_message_caption`
3. شکست → `delete_message` + `send_message` جدید

هر callback جدید در پنل همکار **باید** از این تابع به‌جای `bot.edit_message_text` مستقیم استفاده کند.

### Toggle سه‌تایی (پیام‌های تیکت / ردیف‌های لیست)
الگوی استاندارد در `admin_panel.py`:
```python
recent = items[:3]   # یا items[-3:] بسته به ترتیب ASC/DESC
older  = items[3:]
# دکمه با id منحصربه‌فرد + data-older-count
# addEventListener در <script> اصلی صفحه (نه inline onclick چندخطی — این روش قبلاً باعث باگ شد)
```

### حذف کلی (Bulk Delete)
برای کارت‌به‌کارت: `DELETE FROM card_receipts;` — کافی است، چون تصاویر فقط `file_id` تلگرام هستند و فایلی روی سرور ذخیره نمی‌شود.

### Handler Ordering در `bot.py`
- `myord_back` باید قبل از هر `startswith("myord_")` ثبت شود.
- `maintenance_blocker*` باید زودتر از سایر handler ها ثبت شود (اولویت بالا).
- Handler های خاص (`confirm_wallet_`, `confirm_full_`, ...) باید قبل از catch-all (`handle_callbacks` با `func=lambda c: True`) ثبت شوند.
- **هشدار:** قبلاً دو نسخه از `handle_confirm_wallet`/`handle_confirm_full` هم‌زمان در فایل وجود داشت (یکی اشتباه، صفحه را دوباره نشان می‌داد). همیشه قبل از افزودن handler جدید، با `grep -n "def handle_X"` بررسی شود که تکراری نباشد.

### Schema Migration الگو
هر جدول جدید یک `ensure_*_schema()` دارد که idempotent است (با `CREATE TABLE IF NOT EXISTS`) و قبل از هر query مرتبط صدا زده می‌شود — برای جلوگیری از خطای «no such table» روی دیتابیس‌های قدیمی‌تر.

---

## ۹. باگ‌های مهم رفع‌شده (تاریخچه — برای جلوگیری از تکرار)

| باگ | ریشه | درس گرفته‌شده |
|---|---|---|
| دکمه‌های پنل همکار کار نمی‌کرد | `edit_message_text` روی پیام Photo | همیشه از `_partner_edit` استفاده شود |
| پرداخت دو بار صفحه را نشان می‌داد | دو `def handle_confirm_wallet` هم‌زمان در فایل | همیشه قبل از افزودن handler، duplicate چک شود |
| کد تخفیف دوباره پرسیده می‌شد در پرداخت ترکیبی | منطق قدیمی `discount_asked` در confirm handlers باقی مانده بود | تخفیف فقط در `_show_order_summary`، هرگز در confirm handlers |
| حسابداری سود منفی نمایش می‌داد | هزینه کل Batch حساب می‌شد نه فقط آیتم‌های فروخته‌شده | فقط `delivered=1` در محاسبه هزینه |
| `/admin/receipts` کرش می‌کرد (۵۰۰) | بلوک کد تب «مالی» به‌اشتباه داخل تابع `card_receipts_page` چسبیده بود (متغیرهای `type_filter`/`type_tabs` در آن تابع تعریف نشده بودند) | بعد از copy-paste بلوک‌های بزرگ، حتماً syntax + منطق scope بررسی شود |
| Toggle نمایش/مخفی پیام کار نمی‌کرد | `onclick` چندخطی پیچیده inline | جایگزین با `addEventListener` در اسکریپت اصلی صفحه |
| رسید کارت‌به‌کارت مبلغ ۰ ثبت می‌کرد | `update_card_receipt` فقط status/note را آپدیت می‌کرد، نه `amount` | پارامتر `amount` به تابع اضافه شد |
| لینک‌های پنل به Railway اشاره می‌کردند | باقیمانده از دامنه قدیمی هاستینگ | همه به `panel.stland.ir` اصلاح شدند |

---

## ۱۰. نقشه Route های پنل مدیریت (مهم‌ترین‌ها)

```
GET  /admin/                       داشبورد اصلی
GET  /admin/products               لیست محصولات
GET  /admin/feed/{pid}             مدیریت موجودی محصول
POST /admin/feed/{pid}/upload      ثبت موجودی دستی/متنی (+ قیمت خرید Batch)
POST /admin/feed/{pid}/bulk-upload آپلود فایل TXT/CSV (+ قیمت خرید Batch)
GET  /admin/products/{pid}/faqs    مدیریت FAQ و نظرات محصول

GET  /admin/orders                 لیست سفارش‌ها
GET  /admin/orders/{oid}/return    فرم برگشت سفارش
POST /admin/orders/{oid}/return    ثبت برگشت
GET  /admin/orders/{oid}/resend    صفحه ارسال مجدد (معاوضه)
POST /admin/orders/{oid}/resend    ارسال آیتم جدید برای همان سفارش

GET  /admin/tickets                لیست تیکت‌ها + مرکز مالی Embed شده (#financial)
GET  /admin/tickets/{tid}          جزئیات/چت تیکت (۳ پیام آخر + toggle، دکمه آرشیو)
POST /admin/tickets/{tid}/archive | /unarchive | /delete

GET  /admin/financial              نسخه مستقل مرکز مالی (همان محتوای Embed شده)
GET  /admin/receipts/{rid}/view    جزئیات رسید کارت‌به‌کارت + تصویر + تأیید/رد/حذف
POST /admin/receipts/{rid}/approve | /reject | /delete
POST /admin/receipts/delete-all    حذف کلی همه رسیدهای کارت‌به‌کارت

GET  /admin/partners               لیست/تأیید همکاران
GET  /admin/partners/payout/{pid}  جزئیات درخواست تسویه + تأیید/رد

GET  /admin/accounting             داشبورد حسابداری (۱۲+ KPI)
GET  /admin/accounting/expenses    هزینه‌ها
GET  /admin/accounting/cashflow    گردش مالی
GET  /admin/accounting/products    گزارش محصولات
GET  /admin/accounting/partners    گزارش همکاران
GET  /admin/accounting/*/export    خروجی Excel/CSV

GET  /admin/settings               هاب تنظیمات (تم + لینک مدیریت متن)
GET  /admin/settings?group=...     مدیریت متن‌ها (per group)
POST /admin/settings/maintenance   فعال/غیرفعال حالت تعمیرات
POST /admin/settings/save-theme    ذخیره تم انتخابی مدیر (per admin_id)

GET  /admin/notes                  یادداشت‌های داخلی مدیران
GET  /admin/database                بکاپ/ریست/ریستور
POST /admin/database/reset/sync    ریست انتخابی یا کامل (شامل گزینه حسابداری)
POST /admin/database/restore-auto  بازیابی از بکاپ خودکار

GET  /admin/badges.json            شمارش نوتیف‌ها برای navbar (poll هر ۱۲ ثانیه)
```

---

## ۱۱. وضعیت فعلی پروژه (چه چیزهایی کامل و تست‌شده‌اند)

✅ خرید محصول (کیف‌پول / درگاه / ترکیبی) + کد تخفیف
✅ منوی همکار (دسته‌بندی + خرید/کیف‌پول + پنل همکار + راهنما)
✅ داشبورد همکار با بنر سطح، فروشندگان من، لینک معرفی (با دکمه ارسال)، کیف‌پول همکاری، درخواست تسویه
✅ کارت‌به‌کارت (ارسال رسید + تأیید/رد در پنل با مبلغ دستی)
✅ سیستم حسابداری کامل (KPI، گردش مالی، گزارش محصول/همکار، Export)
✅ مرکز مالی یکپارچه (Type-based، قابل توسعه)
✅ بکاپ خودکار شبانه + بازیابی از Dropdown
✅ Maintenance Mode
✅ امتیازدهی محصول + FAQ + ضمانت بازگشت وجه
✅ مدیریت متن‌ها (۴۷+ کلید)
✅ آرشیو/حذف تیکت + Toggle سه‌تایی پیام‌ها و لیست‌ها
✅ برگشت سفارش + ارسال مجدد (معاوضه)

---

## ۱۲. موارد باز / نیازمند توجه آینده

- `sellers`, `seller_levels`, `seller_commissions`, `seller_payouts` در کنار `partners`, `partner_tiers`, ... وجود دارند — به نظر می‌رسد ساختار موازی/قدیمی باشد؛ نیاز به بررسی و احتمالاً یکپارچه‌سازی یا حذف دارد (با احتیاط، چون ممکن است هنوز جایی استفاده شود).
- صفحه مستقل `/admin/receipts` (لیست standalone قدیمی، قبل از ادغام در مرکز مالی) هنوز در کد وجود دارد ولی از هیچ‌جا لینک نمی‌شود — کاندید حذف کامل در آینده (فعلاً برای کاهش ریسک نگه داشته شده).
- بررسی نشده: امنیت کامل (rate limiting، اعتبارسنجی ورودی، session security، SQL injection در query های string-concatenation مثل برخی فیلترها در گزارش‌ها).
- تست بار (Load Test) برای زمانی که تعداد سفارش/تیکت/رسید به شدت بالا برود — `LIMIT` های فعلی (۱۰۰-۲۰۰) برای حجم متوسط مناسب‌اند.

---

## ۱۳. دستورات مفید سرور

```bash
# health check سریع
health

# لاگ زنده
journalctl -u stockland -f --no-pager

# تست import بدون اجرای کامل سرویس
cd /opt/stockland/app && set -a && source .env && set +a && \
  /opt/stockland/venv/bin/python3 -c "import bot; print('OK')"

# بکاپ دستی فوری
cd /opt/stockland/app && set -a && source .env && set +a && \
  /opt/stockland/venv/bin/python3 -c "from admin_panel import _do_auto_backup; _do_auto_backup()"

# بررسی ترتیب handler های ربات (برای دیباگ تداخل)
cd /opt/stockland/app && set -a && source .env && set +a && \
  /opt/stockland/venv/bin/python3 -c "
import bot
for i, h in enumerate(bot.bot.callback_query_handlers):
    print(i, h['function'].__name__)
"
```

---

## ۱۴. نحوه کار با این پروژه (برای دستیار هوش مصنوعی بعدی)

1. **هرگز** دستور git پیشنهاد نده — مدیر فایل را خودش آپلود/دیپلوی می‌کند.
2. قبل از هر تغییر، فایل فعلی را از `/mnt/user-data/outputs/` بخوان (نه از حافظه) — چون نسخه واقعی deploy شده ممکن است با آخرین چیزی که اینجا ساخته شده فرق داشته باشد (مدیر گاهی فایل خودش را آپلود می‌کند).
3. تغییرات را **حداقلی** نگه دار — فقط تابع/route مرتبط را لمس کن.
4. بعد از هر تغییر، خروجی syntax check (`python3 -c "import ast; ast.parse(...)"`) را گزارش بده.
5. در پایان هر اصلاحیه: فایل‌های تغییریافته + علت + بخش‌های تست‌شده را به فارسی و خلاصه گزارش بده.
6. اگر شکی در رفتار فعلی کد داری، **حدس نزن** — از مدیر بخواه یک دستور تشخیصی روی سرور اجرا کند و خروجی را برایت بفرستد (الگوی این پروژه: Claude دستور می‌دهد → مدیر در سرور اجرا می‌کند → خروجی را پیست می‌کند → Claude بر اساس آن تصمیم می‌گیرد).
7. به بخش ۴ (تصمیمات تثبیت‌شده) و بخش ۹ (باگ‌های رفع‌شده) قبل از هر تغییر در `bot.py` یا `admin_panel.py` مراجعه کن تا یک باگ قبلاً رفع‌شده دوباره برنگردد.