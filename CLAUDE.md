# StockLand — AI Project Memory (CLAUDE.md)

> این فایل حافظهٔ دائمی پروژه برای دستیار هوش‌مصنوعیه. **همیشه قبل از شروع هر کار این فایل رو بخون.** کد فعلی مرجع نهایی حقیقته — اگه جایی این سند با رفتار واقعی کد فرق داشت، کد درسته و این فایل باید آپدیت بشه، نه برعکس.
>
> تاریخ آخرین تحلیل کامل: ۲۰۲۶-۰۷-۲۳ — انجام‌شده توسط Claude Code (تحلیل کامل مخزن، بدون تغییر کد، طبق دستور مالک پروژه).
> هر تغییر بعدی باید در `CHANGELOG_AI.md` ثبت بشه.

---

## ۱. معرفی و هدف پروژه

**StockLand** یک فروشگاه دیجیتال است که حول یک **ربات تلگرام** (پایتون، `pyTelegramBotAPI`/telebot) ساخته شده و محصولات دیجیتال (اکانت، آیدی و مشابه) را با **تحویل خودکار از موجودی (Feed)** می‌فروشد. سیستم شامل کیف‌پول داخلی، درگاه پرداخت زرین‌پال، کارت‌به‌کارت دستی، سیستم همکاری/افیلیت چندسطحی، تیکتینگ پشتیبانی، حسابداری سبک، یک **پنل مدیریت وب** (FastAPI + Tailwind، کاملاً فارسی/RTL) و یک **Mini App / PWA** مستقل است.

- **مخزن گیت‌هاب:** `firouzayazi-source/stockland-bot`
- **سرور تولید:** VPS، مسیر اپ: `/opt/stockland/app/` — سرویس systemd: `stockland.service`
- **دامنه پنل/API:** `https://panel.stland.ir`
- **دیتابیس تولید:** SQLite — مسیر از `DB_PATH` env می‌آید (اجباری، بدون آن `RuntimeError`)
- **زبان/جهت رابط کاربری:** فارسی، RTL — همه‌جا

---

## ۲. ساختار دایرکتوری کامل

```
stockland-bot/
├── bot.py                    ~6,627 خط — کل منطق ربات تلگرام (همه handlerها)
├── admin_panel.py             ~11,098 خط — پنل مدیریت وب (FastAPI router، mount شده در payment_service)
├── payment_service.py         ~1,137 خط — اپ اصلی FastAPI/uvicorn؛ درگاه زرین‌پال + استارتِ polling ربات
├── db.py                      ~5,711 خط — کل اسکیمای SQLite و توابع دیتابیس (لایه داده اصلی)
├── db_conn.py                 لایهٔ انتزاعی اتصال (SQLite یا Postgres بر اساس DB_DIALECT)
├── db_dialect.py              مترجم SQL برای حالت Postgres (فقط وقتی DIALECT=postgres فعاله)
├── api.py                     REST API عمومی (/api/v1) برای PWA/موبایل — از core/ استفاده می‌کند
├── config.py                  تنظیمات سراسری از env (DB_PATH اجباری)
├── keyboards.py               سازنده‌های Reply/Inline Keyboard ربات
├── ui_texts.py                متن‌ها/برچسب‌های قابل‌ویرایش + تابع t()
├── state.py                   دیکشنری‌های in-memory وضعیت کاربر/ادمین (user_states, admin_states, reseller_signup)
├── stbak_engine.py            موتور بکاپ/ریست ماژول‌محور فرمت .stbak (SQLite)
├── storage.py                 لایهٔ انتزاعی DB — نوشته شده ولی **در هیچ‌جا import نمی‌شود (کاملاً بلااستفاده)**
├── payments.py                کمکی پرداخت کیف‌پول — **در هیچ‌جا import نمی‌شود (کد مرده)**
├── backup_tools.py             بکاپ/ریست قدیمی (پسوند Robuser) — هنوز در bot.py ایمپورت می‌شود؛ رشته‌های فارسی‌اش mojibake/خراب هستند
├── backup_uploader.py          آپلود بکاپ به کانال تلگرام + Google Drive (async, thread-based)
├── migrate_to_postgres.py      اسکریپت CLI یک‌بارهٔ مهاجرت SQLite→Postgres (دستی، در اپ وایر نشده)
├── pg_backup.py                بکاپ Postgres با pg_dump/psql (سیستم بکاپ جدا از stbak_engine، برای آیندهٔ Postgres)
├── core/                       لایهٔ منطق تازه و نازک — **فقط توسط api.py استفاده می‌شود**، نه bot.py/admin_panel.py
│   ├── __init__.py
│   ├── products.py, orders.py, wallet.py, partners.py, referrals.py
├── services/
│   ├── payments.py             نسخهٔ **فعال** کمکی پرداخت (bot.py همین را import می‌کند)
│   └── internal_api.py         wrapper سازگاری قدیمی؛ فقط `from payment_service import app`
├── app/                        Mini App / PWA — نسخهٔ **زنده** (Framework7، vendor از CDN دانلود می‌شود)
│   ├── index.html, app.js, app.css, manifest.json, sw.js, get_vendor.sh
│   └── icons/
├── app.js, app.css, manifest.json, sw.js  (ریشهٔ پروژه) — **نسخه‌های قدیمی/کپی راکد** app/*، دیگر deploy نمی‌شوند
├── deploy.sh                   اسکریپت دیپلوی فعلی (git pull + کش PWA بست + restart stockland.service)
├── deploy/                     **زیرساخت دیپلوی قدیمیِ نام‌گذاری‌شده «Robuser»** — دو سرویس جدا (bot.py مستقل + internal_api مستقل)؛ جایگزین شده با معماری تک‌سرویسی فعلی، فقط برای مرجع نگه داشته شده
│   ├── install_venv.sh, robuser.env.example
│   └── systemd/robuser-bot.service, robuser-internal-api.service
├── restore.sh                  بازیابی کامل روی سرور فعلی (stockland)
├── restore_backup.sh           اسکریپت بازیابی قدیمی مسیر /opt/Robuser
├── database/bot.db             ⚠️ فایل SQLite باینری کامیت‌شده در گیت (۱۴ جدول، چند ردیف داده) — احتمالاً باقیماندهٔ توسعهٔ اولیه؛ **نباید در گیت باشد**
├── requirements.txt, Procfile, railway.json   وابستگی‌ها و دیپلوی جایگزین (Railway/Heroku-style، فعلاً استفاده نمی‌شود)
├── readme.md                   مستند قدیمی (نوشته‌شده قبل از این نشست) — ورک‌فلوی «هرگز git استفاده نکن» را توصیف می‌کند که دیگر صدق نمی‌کند (بخش ۲۰)
├── Claude.MD                   نسخهٔ قبلی این فایل (حروف کوچک/بزرگ متفاوت) — محتوایش در همین CLAUDE.md ادغام شده
└── CHANGELOG_AI.md             تاریخچهٔ تغییرات این نشست به بعد
```

---

## ۳. نقش فایل‌های کلیدی (خلاصه)

| فایل | نقش |
|---|---|
| `bot.py` | همهٔ handlerهای تلگرام: منو، خرید، تخفیف، کیف‌پول، همکاری، تیکت، امتیازدهی، ادمین این‌لاین |
| `admin_panel.py` | پنل وب کامل: محصولات، موجودی، سفارش‌ها، همکاران، حسابداری، بکاپ، تنظیمات، یک Mini App دوم داخلی (`/admin/shop`) |
| `payment_service.py` | اپ FastAPI اصلی؛ درگاه زرین‌پال؛ **نقطهٔ استارت polling ربات تلگرام در همان پروسه** |
| `db.py` | تک‌منبع حقیقت برای اسکیمای دیتابیس و اکثر کوئری‌ها |
| `api.py` | REST API برای PWA/موبایل، مبتنی بر `core/`، auth با initData تلگرام |
| `config.py` | env vars سراسری |
| `keyboards.py` / `ui_texts.py` / `state.py` | کیبورد، متن قابل‌ویرایش، وضعیت مکالمه |
| `stbak_engine.py` | ماژول‌های بکاپ/ریست SQLite |

---

## ۴. معماری بک‌اند — یک پروسه، چند نقش

**نکتهٔ حیاتی معماری:** تنها یک پروسهٔ uvicorn (`stockland.service` → `uvicorn payment_service:app`) هر سه نقش زیر را همزمان اجرا می‌کند:

1. **FastAPI app اصلی** (`payment_service.py`) — مسیرهای `/payment/*`, `/webhook`, `/telegram/webhook/{BOT_TOKEN}`, `/health`
2. **پنل ادمین** — `admin_panel.py` یک `APIRouter(prefix="/admin")` است که با `app.include_router(_admin_router)` mount می‌شود (payment_service.py:74)
3. **API عمومی** — `api.py` یک `APIRouter(prefix="/api/v1")` است، mount شده در try/except (payment_service.py:78-82 — اگر `core/` نبود، کل اپ کرش نمی‌کند)
4. **ربات تلگرام** — در `@app.on_event("startup")` (`on_startup`، payment_service.py:452-460)، تابع `maybe_start_bot_polling()` (466-509) ماژول `bot.py` را import می‌کند و `bot_module.bot.infinity_polling(...)` را در یک **thread پس‌زمینهٔ daemon جدا** اجرا می‌کند (نه پروسهٔ جدا). حالت webhook هم پشتیبانی می‌شود (`bot_run_mode` از `bot_config` یا env `USE_WEBHOOK`)؛ سوییچ بین حالت‌ها بدون ری‌استارت از طریق `/admin/webhook/switch` ممکن است.
5. Static mounts: `/app` (PWA) و `/app-media` (فایل‌های آپلودی)

**Middleware سراسری:** `_refresh_admin_session` (payment_service.py:101-115) روی هر request اجرا می‌شود و کوکی سشن ادمین را برای مسیرهای `/admin/*` تازه می‌کند (۳۰۰ ثانیه TTL) — همراه با یک مکانیزم مشابه در خود `admin_panel._refresh_session()`، یعنی دو مسیر موازی برای همین کار.

---

## ۵. معماری ربات تلگرام

- کتابخانه: `pyTelegramBotAPI` (telebot)، `parse_mode="HTML"`
- **فقط Polling** فعال است در حالت مستقیم (`bot.infinity_polling`)؛ کد webhook هم در `payment_service.py` وجود دارد و سوییچ‌پذیر است.
- **Exception handler مرکزی**: `_BotExceptionHandler` (bot.py:143-165) — همهٔ خطاهای بدون‌مدیریت هندلرها را می‌گیرد، لاگ کامل + traceback می‌نویسد، و یک هشدار HTML (حداکثر ۱ بار در ۶۰ ثانیه) به `ADMIN_ID` می‌فرستد. متن این هشدار فقط `str(exception)[:300]` است — برای تشخیص دقیق همیشه باید traceback کامل را از `journalctl` گرفت.
- **پچ اعداد فارسی سراسری**: `_fa_digits()` (bot.py:180-229) روی `send_message`/`edit_message_text`/`reply_to`/`send_photo` caption/`answer_callback_query`/`edit_message_caption` مانکی‌پچ شده؛ لینک‌ها، `<code>`/`<pre>`، `@username`، `/command` مستثنا هستند. **پچ نشده:** `send_document`، captionِ `send_animation`/`send_video`.
- **دو سیستم Rate-Limit مستقل و همپوشان** روی هر پیام/کال‌بک اجرا می‌شوند (بی‌ضرر ولی تکراری): یکی در بالای فایل (`_rl_msg_store`/`_rl_cb_store`)، یکی جدا در وسط فایل (`_rate_limits` با `deque`). — نیاز به یکی‌سازی در آینده.
- **Maintenance mode**: `maintenance_blocker`/`maintenance_blocker_cb` با اولویت بالا ثبت شده‌اند؛ `ADMIN_ID` همیشه مستثناست (By Design).
- **`_setup_app_menu_button()`** در **زمان import ماژول** اجرا می‌شود (نه فقط زیر `if __name__=="__main__"`) — یعنی حتی import صرف `bot.py` (مثلاً برای تست/health-check) یک کال واقعی به Telegram API می‌زند.

### وضعیت کاربر (State Machine)

`state.py`: دو دیکشنری تخت `user_states`/`admin_states` (کاملاً in-memory، **بدون persistence** — ری‌استارت ربات همهٔ مکالمات چندمرحله‌ای در حال انجام را پاک می‌کند)، به‌علاوه دیکشنری سوم جدا `reseller_signup` فقط برای مسیر ثبت‌نام همکار.

مقادیر رایج `user_states[uid]["mode"]`: `ticket_v2`, `partner_name/shop/city/address/card/iban/bankname`, `partner_transfer`, `payout_collect_bank`, `partner_payout`, `rating_comment`, `wallet_charge_amount`, `crypto_amount/txid`, `card2card_amount/receipt`.
مقادیر رایج `admin_states[aid]["mode"]`: `ticket_v2_admin_reply`, `ui_edit`, `product_chat_text`, `partner_search`, `wallet_credit/debit/set_*`, `edit_title/price/partner_price/limit_c/limit_p/desc`, `feed_bulk`, `feed_alert`, `new_product_*`, `await_backup_upload`.

مکانیزم مکمل: `bot.register_next_step_handler` (برای ورودی متنی تک‌مرحله‌ای مثل کد تخفیف، مبلغ شارژ).

---

## ۶. هندلرهای تلگرام و جریان‌های کاربر (User Flows)

> فهرست کامل هندلرها (نام تابع + file:line) در گزارش تحلیل نگه‌داری می‌شود؛ اینجا فقط جریان‌های اصلی و نکات ساختاری آمده.

### ۶.۱ خرید محصول (زنده)
```
دکمهٔ دسته/محصول → send_product_detail() [توجه: یک بلوک متن غنی می‌سازد و بعد دور می‌ریزد — پایین را ببینید]
  → _show_order_summary() (قیمت + دکمهٔ کد تخفیف + روش پرداخت)
  → [اختیاری] کد تخفیف: enter_code_* → handle_enter_code → register_next_step_handler → _handle_code_input
  → confirm_wallet_* یا confirm_full_* → handle_confirm_wallet / handle_confirm_full
  → finalize_product_order() → کسر کیف‌پول (SQL خام مستقیم، نه از طریق subtract_wallet_balance!)
    → create_order → process_referral_commission → check_and_notify_tier_up
    → claim_next_feed_item یا enqueue_pending_delivery
  → ۳۰ ثانیه بعد: _send_rating_request (thread)؛ ۲ ثانیه بعد: _after_purchase_extras
```

### ۶.۲ کد تخفیف (زنده در برابر مرده)
مسیر **زنده**: `enter_code_*` → `handle_enter_code`(2022) → `_handle_code_input`(2046) → `validate_discount`/`use_discount`.
مسیر **کاملاً مرده** (~۲۰۰ خط، ۲۱۶۸-۲۴۷۶): `apply_discount_*` → `handle_discount_prompt` → `_process_discount_code` — هیچ دکمه‌ای این callback_data را صادر نمی‌کند. `_process_discount_code` هم **دوبار تعریف شده** (۲۳۴۹ و ۲۴۱۵)؛ نسخهٔ دوم چون بعداً تعریف می‌شود، نامِ سراسری را override می‌کند (ولی چون کل مسیر مرده است، اهمیتی ندارد فعلاً).

### ۶.۳ شارژ کیف‌پول (زرین‌پال)
`MAIN_BTN_WALLET` → `handle_wallet` → دکمهٔ شارژ → مبلغ سریع یا آزاد → `process_wallet_charge_amount` → `services/payments.start_wallet_charge_payment` (نسخهٔ **فعال**؛ نسخهٔ ریشه `payments.py` مرده و import نمی‌شود) → `POST /payment/create` در `payment_service.py` → لینک زرین‌پال → کاربر پرداخت می‌کند → `GET /payment/callback` تأیید و اعتبار کیف‌پول.

### ۶.۴ کارت‌به‌کارت
`wallet_card2card` → `handle_card2card_amount` (مبلغ **از کاربر** پرسیده می‌شود؛ توجه: مستندات قدیمی readme.md می‌گفت مبلغ فقط توسط ادمین وارد می‌شود — رفتار فعلی کد، مبلغ را ابتدا از کاربر می‌گیرد) → `handle_card2card_photo` → `save_card_receipt` → پیام به ادمین با `/approve_receipt_ID` / `/reject_receipt_ID` یا از پنل (`/admin/receipts/{rid}/approve`، امکان override مبلغ در پنل وجود دارد ولی نه در دستورات اسلش ربات).

### ۶.۵ همکاری/افیلیت
درخواست → تیکت `partner_support` یا ویزارد `process_reseller_contact→city→shop` (state در `reseller_signup`، نه `user_states`) → تأیید ادمین (`approve_partner`) → کیبورد کاربر بلافاصله آپدیت می‌شود (بدون نیاز به `/start`) → داشبورد همکار (`_show_partner_dashboard`) → خرید با `buyer_type='partner'` → پورسانت زنجیره‌ای (`process_referral_commission`: `commission_fixed` سطح → `commission_percent` سطح → درصد عمومی؛ سقف `max_payout`/کف `min_order`) → واریز به `partner_wallets` (کیف‌پول جدا از کیف‌پول اصلی) → درخواست تسویه (`request_partner_payout`) → تأیید ادمین در مرکز مالی.

### ۶.۶ تیکت پشتیبانی (v2)
`MAIN_BTN_SUPPORT` → `_support_ticket_start` → `user_states[uid]={"mode":"ticket_v2"}` → پیام‌های بعدی از `_handle_ticket_v2_text/_media` → `_ticket_v2_handle_user_message` (سقف ۳ پیام کاربر، خروج خودکار با زدن دکمهٔ منو) → پاسخ ادمین از پنل یا ربات (`ticket_v2_reply_*`).

---

## ۷. ساختار دیتابیس و روابط

دیتابیس SQLite (پیش‌فرض؛ زیرساخت Postgres آماده ولی غیرفعال — بخش ۹). بیش از ۴۰ جدول در `db.py` تعریف شده‌اند (+ چند جدول در `bot.py`/`admin_panel.py`/`payment_service.py`).

### گروه‌های اصلی جدول
- **کاربر/کیف‌پول:** `users`, `wallets`, `zarinpal_transactions`, `card_receipts`
- **محصول/موجودی:** `categories`, `products`, `product_feed`, `feed_batches`, `feed_alert_settings`, `stock_subscriptions`
- **سفارش:** `orders` (⚠️ `product_id` این جدول `TEXT` است در حالی که `products.id` عدد است — همیشه در JOIN نیاز به `CAST(...AS INTEGER)`)، `delivery_messages`, `other_services`
- **همکاری/افیلیت:** `partners`, `partner_tiers`, `partner_commission`, `partner_wallets`, `partner_transactions`, `partner_payouts`, `partner_payout_settings`, `partner_bank_info`, `referrals`, `referral_settings`
- **سیستم موازی/قدیمی:** `sellers`, `seller_levels`, `seller_commissions`, `seller_payouts` — سیستم افیلیت جداگانه‌ای که با `partners` هم‌پوشانی دارد؛ `seller_apply` عملاً در `partners` هم می‌نویسد. نیاز به بررسی/ادغام دارد (با احتیاط).
- **تیکت:** `tickets` (v2)، `ticket_messages`
- **تخفیف:** `discount_codes`, `discount_usage`
- **امتیاز/FAQ:** `product_ratings`, `product_faqs`
- **حسابداری:** `expenses`, `expense_categories`
- **تنظیمات/سیستم:** `bot_config` (KV عمومی)، `ui_texts`, `admins`, `admin_preferences`, `admin_notes`, `admin_note_replies`, `admin_logs`, `panel_theme`
- **محتوای PWA:** `app_content` (tutorial/news/feature/daily) — ⚠️ در هیچ ماژول `stbak_engine.py` پوشش داده نمی‌شود (بخش ۱۴)
- **رشد/فروش:** `flash_sales`, `winback_log`

### روابط کلیدی
```
users(user_id) ─┬─ wallets(1:1) ─ zarinpal_transactions(1:N) ─ card_receipts(1:N)
                ├─ orders(1:N) ─ product_feed.order_id / delivery_messages / product_ratings(1:1) / discount_usage
                ├─ tickets(1:N)
                ├─ partners.tg_user_id(1:1) ─ partner_wallets/transactions/payouts/bank_info
                ├─ sellers.user_id(1:1, سیستم موازی)
                └─ referrals.referred_id(1:1 UNIQUE) / referrer_id(1:N)

products(id) ─┬─ product_feed(1:N) ─ batch_id → feed_batches
              ├─ categories.id ← category_id
              ├─ product_faqs / product_ratings / flash_sales / discount_codes.product_id / stock_subscriptions
```

### الگوی مهاجرت (Migration) — قانون حیاتی پروژه

`CREATE TABLE IF NOT EXISTS` روی جدول موجود **هیچ کاری نمی‌کند** — ستون تازه به دیتابیس واقعی سرور اضافه نمی‌شود. الگوی درست، همان‌طور که در اکثر `ensure_*` رعایت شده:
```python
try:
    conn.execute("ALTER TABLE X ADD COLUMN Y TYPE DEFAULT ...;")
    conn.commit()
except Exception:
    pass
```
عدم رعایت این الگو باعث `IndexError: No item with that key` (روی `sqlite3.Row`) یا `OperationalError: no such column` می‌شود.

**نمونهٔ رفع‌شده در این نشست:** `discount_codes` — ستون‌هایی مثل `category_id`, `first_buy_only`, `vip_only`, `max_uses_per_user` در دیتابیس‌های قدیمی وجود نداشتند؛ مهاجرت اضافه شد (`ensure_discount_table`, db.py:2569، بلوک مهاجرت ۲۵۹۴-۲۶۴۶).

**🔴 مورد مشابه هنوز رفع‌نشده:** ستون `products.chat_enabled` **در هیچ نسخه‌ای، حتی نصب‌های تازه، ساخته نمی‌شود** (نه در `CREATE TABLE`، نه در هیچ `ALTER TABLE`). تابع `ticket_toggle_product_chat` در db.py (بدون callers) این ستون را می‌خواند بدون `except`. پیاده‌سازی زندهٔ فعلی در `bot.py:701-725` (`_get_product_chat_enabled`/`_set_product_chat_enabled`) کاملاً موازی و مستقل از `db.py` است — با `sqlite3.connect` خام خودش، و خطا را با `try/except: return 0` می‌بلعد. **نتیجه: دکمهٔ ادمین «فعال‌سازی چت محصول» (`admin_toggle_chat_*`) همیشه بی‌اثر است** — چون خطا خاموش گرفته می‌شود، حتی کشف‌شدنش هم سخت است.

### مهاجرت‌های ایگر در برابر Lazy
- جدول‌های هسته (`wallets, products, partners, orders, zarinpal_transactions, product_feed, ...`) در `init_db()` **ایگر** مهاجرت می‌شوند — از `bot.py` هر `/start` و از `payment_service.py` هنگام استارت polling صدا زده می‌شود.
- دستهٔ دوم در **زمان import ماژول `admin_panel.py`** ایگر اجرا می‌شوند (در `try/except: pass` — شکست بی‌صدا می‌بلعد).
- بقیه **Lazy** هستند (فلگ سراسری per-process) — هر مسیر که به این جدول‌ها نیاز دارد باید خودش `ensure_*` مربوطه را صدا بزند؛ فراموشی این کار = همان کلاس باگ بالا.

---

## ۸. جریان سیستم پرداخت (Zarinpal + payment_service)

### تنظیمات
`ZARINPAL_MERCHANT_ID`, `ZARINPAL_SANDBOX`, `ZARINPAL_REQUEST_URL` (پیش‌فرض `https://api.zarinpal.com/pg/v4/payment/request.json`), `ZARINPAL_VERIFY_URL`, `ZARINPAL_STARTPAY_URL`, `BASE_CALLBACK_URL`, `MIN_TOPUP_AMOUNT` (پیش‌فرض ۱۰۰۰۰ تومان). زرین‌پال بر پایهٔ **ریال** است؛ اپ روی **تومان** کار می‌کند — `RIAL_PER_TOMAN=10` در payment_service.py.

### مسیرهای اصلی
| مسیر | نقش |
|---|---|
| `POST /payment/create` | ساخت تراکنش (اعتبارسنجی مبلغ/نوع/محدودیت روزانه) → `zarinpal_create()` → درج ردیف `pending` در `zarinpal_transactions` → برمی‌گرداند `{authority, payment_url}` |
| `GET /payment/callback` | ریدایرکت مرورگر بعد از پرداخت — idempotent (اگر از قبل `paid` بود، دوباره کاری نمی‌کند)؛ زیر `BEGIN IMMEDIATE` قفل می‌شود تا کال‌بک دوبل مشکل نسازد؛ بسته به `payment_type` یا کیف‌پول شارژ می‌شود یا سفارش کامل می‌شود (`create_order` + `claim_feed_item`/صف تحویل) |
| `POST /payment/finalize` | پل PHP خارجی، auth با `X-Stockland-Secret`/`PHP_SECRET` — منطق مشابه callback (کد تکراری) |
| `POST /webhook` | دریافت‌کنندهٔ webhook تلگرام دوم، **بدون auth** — قدیمی/موازی با `/telegram/webhook/{BOT_TOKEN}` که secret-token دارد |
| `GET /health` | سلامت سرویس + وضعیت polling ربات |

### پرداخت ترکیبی (کیف‌پول + درگاه)
مدل‌سازی با `wallet_reserved` (بخش کیف‌پول، فقط بعد از موفقیت درگاه واقعاً کسر می‌شود — `deduct_wallet_reserved`) + `gateway_amount` (باقیمانده برای درگاه).

### توابع کمکی پرداخت
- `services/payments.py` — نسخهٔ **فعال** (bot.py آن را import می‌کند)، ساده‌تر، بدون منطق حداقل مبلغ درگاه.
- `payments.py` (ریشه) — نسخهٔ کامل‌تر با `_enforce_min_gateway`/wallet_bonus ولی **در هیچ‌جا import نمی‌شود؛ کد مرده**.
- `POST /api/v1/checkout` در `api.py` — چک‌اوت از Mini App؛ مسیر کیف‌پول کار می‌کند؛ مسیر درگاه/ترکیبی **تا این نشست خراب بود** (باگ `_get_uid` — رفع‌شده، بخش ۱۴ و CHANGELOG).

---

## ۹. متغیرهای محیطی (Environment Variables)

> فقط نام‌ها — مقادیر واقعی هرگز در گیت/این فایل قرار نمی‌گیرند (در `.env` روی سرور، مسیر `/opt/stockland/app/.env`، untracked).

| متغیر | نقش |
|---|---|
| `DB_PATH` | **اجباری** — مسیر فایل SQLite |
| `BOT_TOKEN` | توکن ربات تلگرام |
| `ADMIN_ID` | آیدی عددی سوپرادمین (مستثنا از rate-limit/maintenance) |
| `BOT_USERNAME` | یوزرنیم ربات برای دیپ‌لینک |
| `WEBHOOK_BASE_URL` | دامنهٔ پایه برای حالت webhook و لینک PWA (پیش‌فرض `https://panel.stland.ir`) |
| `WEBHOOK_SECRET` | اگر خالی باشد، هر ری‌استارت یک مقدار تصادفی تازه تولید می‌شود |
| `USE_WEBHOOK` | `"1"` برای فعال‌سازی حالت webhook |
| `ZARINPAL_MERCHANT_ID`, `ZARINPAL_SANDBOX`, `ZARINPAL_REQUEST_URL`, `ZARINPAL_VERIFY_URL`, `ZARINPAL_STARTPAY_URL` | تنظیمات زرین‌پال |
| `BASE_CALLBACK_URL` | آدرس کال‌بک پرداخت |
| `MIN_TOPUP_AMOUNT` | حداقل مبلغ شارژ کیف‌پول |
| `PAYMENT_API_BASE_URL`, `PAYMENT_API_TIMEOUT`, `PAYMENT_PUBLIC_BASE_URL` | تنظیمات کلاینت داخلی پرداخت (`services/payments.py`) |
| `PHP_PAYMENT_URL`, `PHP_SECRET` | پل پرداخت PHP خارجی (اختیاری) |
| `PORT` | پورت uvicorn (Railway/Heroku-style) |
| `RUN_BOT_IN_PAYMENT_SERVICE` | فعال‌سازی استارت ربات داخل پروسهٔ payment_service |
| `ADMIN_WEB_USERNAME`, `ADMIN_WEB_PASSWORD` | سوپرادمین پنل وب (⚠️ `"admin"`/`"super"` همیشه به‌عنوان یوزرنیم معتبر پذیرفته می‌شوند صرف‌نظر از این env — بخش ۱۳) |
| `SESSION_SECRET` | امضای HMAC سشن پنل ادمین — ⚠️ دو پیش‌فرض هاردکد متفاوت در کد وجود دارد اگر ست نشود (بخش ۱۳) |
| `API_KEYS` | کلیدهای مجاز برای `api.py` (روش دوم auth، جایگزین initData) |
| `DB_DIALECT`, `DATABASE_URL` | سوییچ SQLite↔Postgres (فعلاً همیشه sqlite در تولید) |
| `SQLITE_PATH` | ورودی اسکریپت `migrate_to_postgres.py` |
| `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, `GDRIVE_FOLDER_ID`, `GDRIVE_SA_JSON` | بکاپ ابری Google Drive |
| `ROBUSER_BACKUP_DIR` | مسیر بکاپ محلی سیستم قدیمی `backup_tools.py` |
| `RAILWAY_PUBLIC_DOMAIN` | تشخیص دامنه روی Railway |
| `LOG_LEVEL` | سطح لاگ |
| `SEED_DEFAULT_DATA` | seed دادهٔ اولیه (احتمالاً برای dev) |
| `INTERNAL_API_PORT` | پورت fallback برای `services/internal_api.py` قدیمی |

---

## ۱۰. APIهای خارجی و یکپارچه‌سازی‌ها

- **Telegram Bot API** — از طریق `pyTelegramBotAPI`
- **Zarinpal** — درگاه پرداخت اصلی (`payment_service.py`)
- **Google Drive API** — بکاپ ابری، هم با Service Account JSON و هم با OAuth Device Flow (دو مکانیزم موازی در `backup_uploader.py` — کد فعلی از refresh_token/OAuth استفاده می‌کند، مسیر Service Account هم تعریف شده ولی به نظر استفاده نمی‌شود چون `_up_gdrive` از `_gdrive_access_token`/OAuth استفاده می‌کند نه SA JSON)
- **Telegram Channel** — مقصد دوم بکاپ ابری (ارسال فایل به کانال با `sendDocument`)
- **Framework7 (CDN)** — فریم‌ورک UI موبایل مینی‌اپ؛ در گیت نیست، با `app/get_vendor.sh` روی سرور دانلود می‌شود
- **Vazirmatn font (CDN)** — فونت فارسی، همان‌طور دانلود می‌شود
- **PHP payment bridge** (اختیاری) — `PHP_PAYMENT_URL`/`PHP_SECRET`، مسیر جایگزین پرداخت

---

## ۱۱. ساختار دیپلوی

### معماری فعلی (زنده)
- **یک سرویس systemd:** `stockland.service` → `uvicorn payment_service:app --host 127.0.0.1 --port 8001`
- `WorkingDirectory=/opt/stockland/app`, `.env` در همان مسیر
- دیپلوی با `deploy.sh`: `git pull --ff-only` → نسخهٔ کش PWA در `app/sw.js`/`app/index.html` bump می‌شود (cache-busting) → `systemctl restart stockland.service`
- بازیابی اضطراری: `restore.sh` (git reset --hard origin/main + چک vendor + restart)

### معماری قدیمی (غیرفعال، فقط مرجع)
پوشهٔ `deploy/` — دو سرویس مجزا با نام «Robuser» (`robuser-bot.service` مستقیماً `bot.py` را اجرا می‌کرد، `robuser-internal-api.service` مستقیماً `services/internal_api.py` را) — **جایگزین شده** با معماری تک‌سرویسی فعلی که ربات را داخل همان پروسهٔ FastAPI/uvicorn استارت می‌کند. این فایل‌ها را حذف نکن مگر با تأیید صریح (ممکن است هنوز جایی رفرنس شوند)، ولی برای دیپلوی جدید استفاده نشوند.

### مسیرهای جایگزین تعریف‌شده ولی ظاهراً غیرفعال
- `Procfile` / `railway.json` — هر دو `uvicorn payment_service:app --host 0.0.0.0 --port $PORT` — برای دیپلوی روی Railway/Heroku-style PaaS، مستقل از systemd فعلی

---

## ۱۲. نیازمندی‌های سرور

- Python 3 + venv (`/opt/stockland/venv`)
- `pip install -r requirements.txt`: `pyTelegramBotAPI>=4.14,<5`, `requests`, `Flask>=3.0,<4` (احتمالاً بلااستفاده — کل استک روی FastAPI است، بررسی نشد کجا Flask واقعاً import می‌شود)، `fastapi>=0.110,<1`, `uvicorn[standard]>=0.27,<1`, `python-multipart`, `openpyxl>=3.1` (اکسپورت Excel در پنل حسابداری)
- systemd برای مدیریت سرویس
- برای مینی‌اپ: `app/get_vendor.sh` باید یک‌بار روی سرور اجرا شود (دانلود Framework7 + فونت‌ها به `app/vendor/`)

---

## ۱۳. نقاط حساس امنیتی (Security-Sensitive Areas)

> این‌ها یافته‌های تحلیل کد فعلی‌اند، **هیچ‌کدام در این نشست تغییر داده نشده‌اند** — فقط مستندسازی شده‌اند. قبل از هر اقدام روی این موارد با مالک پروژه هماهنگ شود.

1. **SQL Injection واقعی** — `db.py` تابع `get_card_receipts(status)` مقدار `status` را مستقیم در رشتهٔ SQL درج می‌کند (`f"WHERE r.status='{status}'"`) به‌جای پارامتری‌شده؛ ورودی از query string پنل ادمین می‌آید (`/admin/receipts?status=...`).
2. **رمز سوپرادمین plaintext روی دیسک** — مسیر `POST /admin/admins/super/password` رمز جدید را بدون هش مستقیم داخل فایل `.env` می‌نویسد (و `/admins/super/telegram_id` همین الگو را برای `ADMIN_ID` دارد).
3. **یوزرنیم‌های bypass هاردکد** — لاگین پنل با یوزرنیم `"admin"` یا `"super"` همیشه به‌عنوان سوپرادمین معتبر پذیرفته می‌شود، حتی اگر `ADMIN_WEB_USERNAME` چیز دیگری تنظیم شده باشد.
4. **دو پیش‌فرض متفاوت برای `SESSION_SECRET`** — `_hash_pw` پیش‌فرض `"stockland"` دارد، `_make_session`/`_get_admin` پیش‌فرض `"stockland-panel"` دارند. اگر env ست نشود، سشن‌ها/هش پسورد با این رشته‌های هاردکدشدهٔ ضعیف قابل جعل‌اند.
5. **هش پسورد ادمین‌ها ضعیف** — `SHA256(SESSION_SECRET + password)`، بدون salt، بدون iteration — نه bcrypt/argon2/PBKDF2.
6. **بدون CSRF token** روی هیچ فرم پنل ادمین (فقط `SameSite=Lax` cookie).
7. **دو مسیر webhook تلگرام موازی** — `/telegram/webhook/{BOT_TOKEN}` با secret-token امن است؛ `/webhook` قدیمی‌تر **بدون هیچ auth** است.
8. **`API_KEYS`/`X-User-Id`** در `api.py` — روش دوم auth، بدون امضا؛ هر کسی با کلید معتبر می‌تواند خود را جای هر `user_id` دلخواه جا بزند.
9. **`database/bot.db`** — یک فایل SQLite باینری با داده‌های واقعی‌نما (سفارش، تراکنش زرین‌پال) از ابتدای پروژه در گیت کامیت شده — پیشنهاد: از ردگیری گیت خارج و به `.gitignore` اضافه شود (با تأیید مالک پروژه، چون ممکن است عمداً به‌عنوان seed نگه داشته شده باشد).
10. **بدون رمزهای TODO/FIXME یافت‌شده** در کد — یعنی این موارد خودشان را در کامنت‌ها پرچم نکرده‌اند؛ فقط با خواندن مستقیم کد پیدا شدند.

---

## ۱۴. مشکلات شناخته‌شدهٔ فعلی (Known Issues)

### 🔴 باگ‌های فعال (تأثیرگذار روی کاربر واقعی)

| # | مشکل | محل | وضعیت |
|---|---|---|---|
| 1 | ~~`/api/v1/checkout` با `NameError: _get_uid` کرش می‌کرد~~ | `api.py:286` | ✅ **رفع‌شده در این نشست** — به `_auth` تغییر یافت (کامیت `9760faf`) |
| 2 | مسیر درگاه/ترکیبی `POST /api/v1/checkout` به `http://127.0.0.1:8001/payment/create` هاردکد وصل می‌شود و انتظار کلید `redirect_url` دارد؛ `payment_service.py` واقعاً `{authority, payment_url}` برمی‌گرداند — این mismatch باقی مانده | `api.py:351,364-368` | باز — نیاز به هماهنگی/تصمیم قبل از رفع |
| 3 | دکمهٔ ادمین «فعال‌سازی چت محصول» همیشه بی‌اثر است — `products.chat_enabled` هیچ‌جا ساخته نمی‌شود | `db.py:2320-2332`, `bot.py:701-725,4630-4637` | باز |
| 4 | «کد تخفیف» — خطای `IndexError: No item with that key` روی دیتابیس‌های قدیمی | `db.py: ensure_discount_table` | ✅ **رفع‌شده** (PR #1) |

### 🟡 کد مرده / تکراری (بدون تأثیر کاربر فعلی، ریسک برای توسعهٔ آینده)
- `_process_discount_code` دو تعریف (bot.py:۲۳۴۹ و ۲۴۱۵) — کل مسیر `apply_discount_*` مرده است (هیچ دکمه‌ای صداش نمی‌زند)
- `handle_pay_nodiscount`, `handle_discount_start`, `handle_discount_skip` هرکدام دو بار تعریف/ثبت شده‌اند
- `handle_do_pay` (`do_pay_*`) کاملاً مرده
- داخل catch-all `handle_callbacks`، یک کپی مردهٔ منطق `confirm_wallet_*`/`confirm_full_*` باقی مانده (bot.py:۶۰۶۹-۶۱۳۴) — اگر ترتیب ثبت handlerها روزی تغییر کند، **ریسک کسر دوبرابری کیف‌پول** دارد؛ بلافاصله بعدش هم کد مردهٔ ارجاع به متغیر تعریف‌نشدهٔ `message` (باید `call` باشد)
- `handle_admin_cmd` (bot.py:۳۰۶۳) توسط `handle_admin_command` (۱۰۴۶) سایه می‌شود، هرگز اجرا نمی‌شود
- `handle_admin_text` به تابع تعریف‌نشدهٔ `handle_ticket_chat_user` ارجاع می‌دهد (حالت `ticket_support` که دیگر هیچ‌جا ست نمی‌شود — در حال حاضر بی‌خطر، ولی اگر آن حالت برگردد، `NameError`)
- `payments.py` (ریشه) و `storage.py` کاملاً بلااستفاده‌اند — هیچ فایلی importشان نمی‌کند
- ۷۴ از ۱۳۱ کلید `DEFAULT_UI_TEXTS` (~۵۶٪) هیچ‌جا استفاده نمی‌شوند — پیام‌های واقعی معادل، هاردکد فارسی داخل کدند (نقض قانون خود پروژه دربارهٔ عدم هاردکد متن)
- دو سیستم Rate-Limit موازی در bot.py
- `app_content` در هیچ ماژول `stbak_engine.py` پوشش داده نمی‌شود — بکاپ/ریست کامل این جدول را نادیده می‌گیرد
- دو پیاده‌سازی کامل و مستقل Mini App (پنل `/admin/shop` و PWA مستقل `/app`+`api.py`) با کد initData-verification تکراری در دو فایل جدا
- `db_dialect.py`: ترجمهٔ `INSERT OR REPLACE`→INSERT ساده (معنای upsert را از دست می‌دهد) و `SELECT changes()`→`SELECT 1` (همیشه truthy) — برای Postgres واقعی هنوز درست کار نمی‌کند (فعلاً بی‌خطر چون Postgres در تولید فعال نیست)
- سیستم افیلیت موازی/قدیمی `sellers`/`seller_*` در کنار `partners`/`partner_*` — همپوشانی نامشخص

### 🟠 مغایرت مستندات قدیمی با رفتار واقعی کد (صرفاً برای اطلاع — کد مرجع است)
- `readme.md` می‌گوید کارت‌به‌کارت هرگز مبلغ را از کاربر نمی‌پرسد؛ کد فعلی (`handle_card2card_amount`) صراحتاً از کاربر مبلغ می‌خواهد.

---

## ۱۵. پیشنهادهای بهبود آینده (Pending Improvements — صرفاً پیشنهاد، بدون اقدام خودکار)

- یکی‌سازی دو سیستم Rate-Limit در bot.py
- افزودن مهاجرت `products.chat_enabled`
- تصمیم دربارهٔ حذف کامل مسیر مردهٔ `apply_discount_*`/`_process_discount_code` تکراری
- بررسی و شاید ادغام `sellers`/`seller_*` با `partners`/`partner_*`
- افزودن `app_content` به یک ماژول `stbak_engine.py`
- تصمیم دربارهٔ دو Mini App موازی (`/admin/shop` در برابر `/app`)
- خارج کردن `database/bot.db` از ردگیری گیت
- هش کردن (نه plaintext) هنگام تغییر رمز سوپرادمین؛ یکسان‌سازی پیش‌فرض `SESSION_SECRET`
- افزودن CSRF token به فرم‌های پنل ادمین
- پارامتری‌کردن کوئری `get_card_receipts`

---

## ۱۶. قوانین ثابت پروژه — هرگز نقض نشود

(این بخش از `Claude.MD` قبلی ادغام شده — همچنان معتبر است طبق بررسی کد فعلی)

1. **اعداد فارسی سراسری.** ربات: پچ خودکار روی send/edit/reply/caption/callback در `bot.py` (لینک، `<code>`/`<pre>`، `@user`، `/command` مستثنا). پنل: مبدل JS سراسری (MutationObserver) در `_layout`؛ `INPUT/TEXTAREA/SELECT/CODE/PRE` و کلاس `.no-fa` مستثنا.
2. **برچسب دکمه‌ها هرگز هاردکد نمی‌شود.** همیشه `t("KEY", DEFAULT_UI_TEXTS.get("KEY", "متن پیش‌فرض"))`؛ کلید تازه به `DEFAULT_UI_TEXTS` اضافه شود و اگر ادمین باید ویرایش کند، به `EDITABLE_BUTTON_GROUPS` (+ آیکون در `BUTTON_ICONS`).
3. **آیکون اول رشته** (سمت راست در RTL دیده می‌شود): `"🧾 خریدهای من"` ✅ نه `"خریدهای من 🧾"`.
4. **دکمه‌های منوی اصلی** با `MAIN_BTN_ENABLED_<KEY>` در `ui_texts` فعال/غیرفعال می‌شوند؛ لیست کلیدها = `MAIN_BUTTON_KEYS`.
5. **متن‌های قابل‌ویرایش ادمین فقط:** `WALLET_QUICK_AMOUNTS`, `HELP_TEXT`, `PARTNER_GUIDE_TEXT` (`CRITICAL_TEXT_KEYS`). سیستم عمومی «مدیریت متن‌ها» برای بقیه عمداً حذف شده — برنگردان.
6. **دسته‌های ریشه دکمهٔ بازگشت ندارند.** فقط زیردسته‌ها.
7. **سفارش برگشتی (`status='returned'`) از دید کاربر کاملاً مخفی است** (هم `get_user_orders` هم جزئیات سفارش). ادمین می‌بیند.
8. **زنجیرهٔ پورسانت زیرمجموعه** (روی هر خرید، `process_referral_commission`): `commission_fixed` سطح ← اگر ۰ بود `commission_percent` سطح ← اگر ۰ بود درصد عمومی. سقف `max_payout`، کف `min_order`. پاداش اولین خرید (`process_referral_reward`) جداست.
9. **اعتبارسنجی تخفیف همیشه با `user_id`:** `validate_discount(code, product_id=…, amount=…, user_id=uid)` و `use_discount(code_id, user_id=uid)`. VIP = `users.tags` شامل `vip` یا همکار `approved`.
10. **آپلود فایل موجودی:** اگر `purchase_price<=0`، بعد از درج ریدایرکت به `/admin/feed/{pid}/batch-pricing` (قیمت خرید اجباری). این جریان دور زده نشود.
11. **تم پنل:** `admin_preferences.dark_mode ∈ {'1','0','auto'}` + `classic_mode`. UI جدید با کلاس‌های استاندارد Tailwind بنویس تا خودکار شب/روز درست شود.
12. **جدول جدید = ماژول بکاپ.** هر جدول تازه باید به `MODULES` در `stbak_engine.py` اضافه شود.
13. **ستون جدید = مهاجرت ALTER.** الگوی `PRAGMA table_info` ← `ALTER TABLE ... ADD COLUMN` (در try/except) در `ensure_*` مربوطه — وگرنه «No item with that key» یا `OperationalError`.
14. **HTML پنل داخل f-string است.** آکولاد JS/CSS باید `{{ }}` باشد. helperها: `_layout`, `_card`, `_btn`, `_input`, `e()`, `_log(request, action, section, details)`, `_redir`.
15. **`_partner_edit(call, text, kb)`** برای ویرایش پیام در کال‌بک‌های پنل همکار (چون داشبورد ممکن است Photo باشد): تلاش `edit_message_text` → شکست → `edit_message_caption` → شکست → `delete_message`+`send_message`. هر کال‌بک جدید در پنل همکار باید از این استفاده کند، نه مستقیم `bot.edit_message_text`.
16. **Handler Ordering در `bot.py`:** هندلرهای خاص (`confirm_wallet_`, `confirm_full_`, ...) باید قبل از catch-all (`handle_callbacks`, `func=lambda c: True`) ثبت شوند. قبل از افزودن هندلر جدید، با `grep -n "def handle_X"` چک شود که تکراری نباشد (این پروژه سابقهٔ همین باگ را دارد — بخش ۱۴).

---

## ۱۷. تست قبل از تحویل

```bash
# سینتکس
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['bot.py','admin_panel.py','db.py','api.py','payment_service.py','keyboards.py','ui_texts.py','stbak_engine.py']]"

# اسموک‌تست ایمپورت با دیتابیس موقت
DB_PATH=/tmp/test.db BOT_TOKEN=123:TEST ADMIN_ID=1 python3 -c "import db, ui_texts, keyboards"
DB_PATH=/tmp/test.db BOT_TOKEN=123:TEST ADMIN_ID=1 python3 -c "import api"   # نیازمند fastapi نصب‌شده
```

هر تحویل باید **فهرست فایل‌های تغییرکرده** را اعلام کند تا انتخابی کامیت شوند. فایل‌های دست‌نخورده را بازنویسی نکن.

---

## ۱۸. سبک کار و قواعد توسعه

- پاسخ‌ها و کامنت‌ها فارسی؛ نام متغیر/تابع انگلیسی.
- تغییرات جراحی و حداقلی — «مابقی کد دستکاری نشه».
- قبل از فیچرهای بزرگ، برداشت خلاصه بگو و تأیید بگیر؛ بعد کد بزن.
- **کد فعلی مرجع نهایی است**، نه مستندات قدیمی (`readme.md` قدیمی ممکن است رفتار قدیمی‌تری را توصیف کند — بخش ۱۴).
- وقتی شکی در رفتار سرور واقعی هست (نه چیزی که از کد قابل استنتاج باشد)، حدس نزن — دستور تشخیصی بخواه و خروجی واقعی (journalctl و…) را ببین.

---

## ۱۹. گردش‌کار Git و فرایند دیپلوی (به‌روزشده در این نشست)

⚠️ **تغییر مهم نسبت به `readme.md` قدیمی:** آن سند می‌گفت «هرگز دستور git پیشنهاد نده — مدیر مستقیم آپلود می‌کند». این قانون **دیگر معتبر نیست**. طبق دستور صریح مالک پروژه در این نشست:

- این پروژه به گیت‌هاب وصل است و Claude Code مستقیماً با `git`/GitHub MCP کار می‌کند.
- بعد از هر تغییر تأییدشده: **خودکار commit با پیام واضح** و **push به برنچ فعال**.
- برنچ فعلی کار: `claude/git-connection-issue-cupwr0` — هر تغییر تأییدشده اینجا commit/push می‌شود.
- گیت‌هاب منبع حقیقت است؛ سرور تولید باید با آن هماهنگ نگه داشته شود.
- قبل از push، بررسی شود فقط فایل‌های مدنظر تغییر کرده‌اند (`git status`/`git diff`).
- هرگز کد تست‌نشده/شکسته push نشود — حداقل syntax check (بخش ۱۷) همیشه قبل از commit.
- نیازی به تأیید دستی کاربر برای هر commit/push جدا نیست (طبق دستور صریح مالک) — ولی برای تغییرات پرریسک (حذف/بازنویسی معماری، عملیات مخرب گیت مثل force-push/reset --hard) همچنان تأیید گرفته شود.

### فرایند دیپلوی سرور (جدا از گیت‌هاب — روی خود VPS)
```
cd /opt/stockland/app
git pull origin main
systemctl restart stockland.service
```
یا از اسکریپت آماده: `bash deploy.sh` (همین کار + بامپ نسخهٔ کش PWA). این مرحله **دستی روی سرور** انجام می‌شود؛ Claude Code فقط تا مرحلهٔ push به گیت‌هاب پیش می‌رود مگر صراحتاً خواسته شود دستورهای سروری هم اجرا/راهنمایی شود.

### وضعیت اتصال گیت‌هاب (این نشست)
- مخزن: `firouzayazi-source/stockland-bot`
- PR باز: **#1** (`claude/git-connection-issue-cupwr0` → `main`) — شامل رفع باگ `discount_codes`، `.gitignore`، و رفع `_get_uid`
- سرور در زمان بررسی روی `main@00a61ac`/`5d77803` بود (قبل از merge شدن PR #1) — یعنی رفع‌های این PR تا merge+deploy روی سرور اعمال نمی‌شوند.

---

## ۲۰. دستورات مفید سرور (از readme.md قدیمی، هنوز معتبر)

```bash
# لاگ زنده
journalctl -u stockland -f --no-pager

# traceback کامل یک خطای خاص
journalctl -u stockland.service -n 200 --no-pager | grep -B5 -A 40 "متن خطا"

# ری‌استارت
systemctl restart stockland.service

# وضعیت سرویس‌ها
systemctl list-units --type=service --all | grep -i stockland
```
