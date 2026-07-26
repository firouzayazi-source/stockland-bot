# StockLand — AI Project Memory (CLAUDE.md)

> این فایل حافظهٔ دائمی پروژه برای دستیار هوش‌مصنوعیه. **همیشه قبل از شروع هر کار این فایل رو بخون.** کد فعلی مرجع نهایی حقیقته — اگه جایی این سند با رفتار واقعی کد فرق داشت، کد درسته و این فایل باید آپدیت بشه، نه برعکس.
>
> تاریخ آخرین تحلیل کامل: ۲۰۲۶-۰۷-۲۳ — انجام‌شده توسط Claude Code (تحلیل کامل مخزن، بدون تغییر کد، طبق دستور مالک پروژه).
> تاریخ آخرین بروزرسانی افزایشی: ۲۰۲۶-۰۷-۲۶ — بعد از چند راند توسعهٔ مینی‌اپ (بخش ۲۱) + افزودن فیچر مستقل «کارشناس هوشمند قیمت آیفون» (بخش ۲۲، شامل نرمال‌سازی کامل دیتابیس قیمت‌گذاری و بازطراحی پنل به لیست تخت قیمت‌ها) + رفع ریشه‌ای Backup/Restore/Recovery + تکمیل سیستم دسترسی ادمین + منطق خرید ناموجود (بخش ۲۳) — قبل از کار روی هرکدوم، همون بخش رو بخون تا نیازی به خوندن دوبارهٔ کد نباشه.
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
├── iphone_valuation/           پکیج کاملاً مستقل — کارشناس هوشمند قیمت آیفون (بخش ۲۲) — **هم bot.py هم api.py هم admin_panel.py از این استفاده می‌کنن** (برخلاف core/ که فقط api.py استفاده می‌کنه)
│   ├── __init__.py, db.py, fx.py, pricing_engine.py, scoring_engine.py, report.py, service.py, router.py
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
- **محصول/موجودی:** `categories`, `products` (⚠️ ستون `image_url TEXT DEFAULT ''` این نشست اضافه شد — عکس اختصاصی محصول، اختیاری؛ اگه خالی باشه UI آیکون پیش‌فرض دسته را نشون می‌ده)، `product_feed`, `feed_batches`, `feed_alert_settings`, `stock_subscriptions`
- **سفارش:** `orders` (⚠️ `product_id` این جدول `TEXT` است در حالی که `products.id` عدد است — همیشه در JOIN نیاز به `CAST(...AS INTEGER)`)، `delivery_messages`, `other_services`
- **همکاری/افیلیت:** `partners`, `partner_tiers`, `partner_commission`, `partner_wallets`, `partner_transactions`, `partner_payouts`, `partner_payout_settings`, `partner_bank_info`, `referrals`, `referral_settings`
- **سیستم موازی/قدیمی:** `sellers`, `seller_levels`, `seller_commissions`, `seller_payouts` — سیستم افیلیت جداگانه‌ای که با `partners` هم‌پوشانی دارد؛ `seller_apply` عملاً در `partners` هم می‌نویسد. نیاز به بررسی/ادغام دارد (با احتیاط).
- **تیکت:** `tickets` (v2)، `ticket_messages`
- **تخفیف:** `discount_codes`, `discount_usage`
- **امتیاز/FAQ:** `product_ratings`, `product_faqs`
- **حسابداری:** `expenses`, `expense_categories`
- **تنظیمات/سیستم:** `bot_config` (KV عمومی)، `ui_texts`, `admins`, `admin_preferences`, `admin_notes`, `admin_note_replies`, `admin_logs`, `panel_theme`
- **محتوای PWA:** `app_content` (tutorial/news/feature/daily — ⚠️ فقط `daily` واقعاً در مینی‌اپ نمایش داده می‌شود؛ `tutorial`/`feature` یتیم‌اند، بخش ۲۱) — ⚠️ در هیچ ماژول `stbak_engine.py` پوشش داده نمی‌شود (بخش ۱۴)
- **رشد/فروش:** `flash_sales`, `winback_log`
- **مینی‌اپ (این نشست اضافه شد، بخش ۲۱):** `daily_checkins`, `favorites`, `user_notifications` — ⚠️ هیچ‌کدام هنوز در `stbak_engine.py` MODULES ثبت نشده‌اند (بخش ۱۴)
- **کارشناسی آیفون (بخش ۲۲):** `iv_models`, `iv_capacities`, `iv_coefficients`, `iv_score_weights`, `iv_fx_sources`, `iv_transactions`, `iv_valuations` — همه در `iphone_valuation/db.py` نه در `db.py` اصلی؛ ⚠️ این‌ها هم هنوز در `stbak_engine.py` MODULES ثبت نشده‌اند

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
| 5 | `POST /api/v1/checkout` مسیر کیف‌پولی سفارش ثبت و پول کسر می‌کرد ولی محصول را هیچ‌وقت واقعاً تحویل نمی‌داد (نه `claim_next_feed_item`، نه پیام تحویل) | `api.py` — رفع با `_deliver_or_queue_order()` | ✅ **رفع‌شده** (PR #43) — ⚠️ سفارش‌های کیف‌پولی مینی‌اپ *قبل* این رفع ممکنه هیچ‌وقت تحویل نگرفته باشن؛ اگه هنوز چک نشده، دستی بررسی بشه |
| 6 | `db.add_product()` متغیر `cols` تعریف می‌شود ولی هیچ‌جا پر نمی‌شود → `product_key` (NOT NULL) هیچ‌وقت درج نمی‌شود → ویزارد افزودن محصول **خود ربات** (`bot.py:4627`) می‌شکند | `db.py: add_product` | باز — قبلاً به مالک پروژه گزارش شده، هنوز درخواست رفع نشده |
| 7 | دکمهٔ ربات «کارشناسی قیمت آیفون» پیش‌فرض فعاله (مثل بقیهٔ `MAIN_BUTTON_KEYS`) ولی تا مدل/ظرفیتی در `/admin/iphone/models` تعریف نشه، فقط پیام «هنوز مدلی تعریف نشده» می‌ده — نه کرش، ولی UX ناقص تا داده وارد بشه | `bot.py: handle_iphone_valuation_start` | باز — نیاز به پر شدن دستی داده توسط ادمین بعد از دیپلوی، نه باگ |

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
- `daily_checkins`, `favorites`, `user_notifications` (جداول جدید مینی‌اپ، بخش ۲۱) هم مثل `app_content` هنوز به `stbak_engine.py` MODULES اضافه نشده‌اند — همون کلاس مشکل، جدید
- جداول کارشناسی آیفون (`iv_*`، بخش ۲۲) هم به همین دلیل هنوز به `stbak_engine.py` اضافه نشده‌اند
- `iphone_valuation.db.create_transaction()` (یادگیری از معاملات واقعی StockLand برای بهبود قیمت‌گذاری) تابعش آماده‌ست ولی هیچ UI پنلی برای ثبت دستی معامله نداره — فعلاً استفاده نمی‌شه
- نوع `app_content.kind='tutorial'`/`'feature'` دیگه هیچ‌جای مینی‌اپ نمایش داده نمی‌شوند (فقط `'daily'` زنده‌ست) — فرم پنل فقط هشدار می‌ده، داده حذف نشده (بخش ۲۱)
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
- ✅ **رفع‌شده (۲۰۲۶-۰۷-۲۶، بخش ۲۳):** نیازی به افزودن دستی `app_content`, `daily_checkins`, `favorites`, `user_notifications`, `iv_*` به `stbak_engine.py` نیست — بکاپ کامل حالا با `discover_new_tables()` خودش هر جدول پوشش‌نداده رو کشف می‌کنه.
- رفع باگ `db.add_product()` (متغیر `cols` بلااستفاده، `product_key` هیچ‌وقت درج نمی‌شود)
- ساخت UI پنل برای `iphone_valuation.db.create_transaction()` (ثبت دستی معاملات واقعی برای یادگیری بازار)
- انتقال کارشناسی آیفون به مینی‌اپ (فاز بعد، API از الان آماده‌ست)
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

⚠️ **`admin_panel.py` نیازمند Python 3.12+ است، نه پیش‌فرض محیط.** این فایل از یک f-string با نقل‌قول تودرتوی هم‌نوع داخل `{}` استفاده می‌کنه (الگوی `f"""...{"" if x else """...جاوااسکریپت...""" }..."""`) — این نحو فقط با PEP 701 (پایتون ۳.۱۲+) قانونیه. اگه `python3` پیش‌فرض سندباکس/سرور ۳.۱۱ یا قدیمی‌تر باشه، `ast.parse`/`py_compile` روی این فایل با `SyntaxError: invalid decimal literal` (معمولاً حوالی خط ۱۳۰۰، در بلوک `// Idle logout`/`// Badge polling`) شکست می‌خوره — **این یک باگ واقعی در کد نیست**، فقط یعنی مفسر پایتون اشتباه رو داری. قبل از نتیجه‌گیری «admin_panel.py سینتکس‌اش خرابه»، حتماً با `python3.12 -m py_compile admin_panel.py` (اگه نصبه) دوباره چک کن.

```bash
# سینتکس — admin_panel.py را جدا و با پایتون ۳.۱۲+ چک کن
python3 -c "import ast; [ast.parse(open(f).read()) for f in ['bot.py','db.py','api.py','payment_service.py','keyboards.py','ui_texts.py','stbak_engine.py']]"
python3.12 -m py_compile admin_panel.py 2>/dev/null || python3 -m py_compile admin_panel.py

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

### پیکربندی nginx (خارج از این مخزن — فقط روی خود VPS)

فایل: `/etc/nginx/sites-available/stockland` (symlink از `/etc/nginx/sites-enabled/stockland`) — `server_name panel.stland.ir api.stland.ir;`، `proxy_pass http://127.0.0.1:8001;`.

**۲۰۲۶-۰۷-۲۴:** مشخص شد این فایل به‌صورت پیش‌فرض نصب nginx (بدون این خط‌ها) هیچ `client_max_body_size` و مهلت زمانی سفارشی نداشت — یعنی آپلود هر فایلی بزرگ‌تر از ۱ مگابایت (کاور/ویدیو/فایل دانلودی آموزش، رسید کارت‌به‌کارت، پیوست تیکت) با خطای «client intended to send too large body» رد می‌شد، یا برای فایل‌های نزدیک به مرز، بعد از ۶۰ ثانیه (پیش‌فرض `client_body_timeout`) قطع می‌شد. این خط‌ها دستی به بلوک `server { server_name panel.stland.ir ... }` اضافه شدن:
```nginx
client_max_body_size 200m;
proxy_read_timeout 300s;
proxy_send_timeout 300s;
client_body_timeout 300s;
```
بعد از هر تغییر: `nginx -t && systemctl reload nginx`. **این تنظیمات در گیت ثبت نیستن** — اگه سرور از صفر ساخته بشه یا این فایل جایگزین بشه، باید دستی دوباره اضافه بشن.

---

## ۲۱. مینی‌اپ — نقشهٔ کامل قابلیت‌ها و API (تا ۲۰۲۶-۰۷-۲۴)

> این بخش برای این نوشته شده که **دیگه لازم نباشه هر بار `app.js`/`app.css`/`api.py` رو کامل خوند** تا بفهمی مینی‌اپ چی داره. اگه رفتار واقعی کد با این‌جا فرق داشت، کد درسته و این‌جا باید آپدیت بشه.

### معماری
مینی‌اپ (`app/index.html` + `app/app.js` + `app/app.css`، Framework7، تلگرام WebApp) **هیچ منطق قیمت‌گذاری/کسب‌وکاری نداره** — فقط UI. همهٔ منطق در `core/*.py` است و از طریق `api.py` (`/api/v1/*`) صدا زده می‌شود. Auth با `initData` تلگرام (یا `API_KEYS`/`X-User-Id` به‌عنوان روش جایگزین، بخش ۱۳). الگوی معماری استاندارد پروژه برای هر فیچر جدید API-محور همینه: `core/` (منطق خالص) ← `api.py` (روتر نازک، فقط auth+validation+صدازدن core) ← مصرف‌کننده (مینی‌اپ/ربات/پنل).

### فیچرهای مینی‌اپ و API متناظرشون
| فیچر | Endpoint(ها) | جدول(ها) | کنترل ادمین |
|---|---|---|---|
| تحویل درون‌اپی سفارش (کیف‌پول) | `POST /api/v1/checkout` (از `_deliver_or_queue_order`) | `orders`, `product_feed`, `pending_deliveries` | — (همون تنظیمات فروش عادی) |
| نمایش کالای تحویلی در «سفارش‌های من» | `core/orders.py` (JOIN با `product_feed`) | — | — |
| امتیاز/نظر روی کارت و صفحهٔ محصول | `GET /categories`, `GET /products/{id}` (فیلد `rating_avg`/`rating_count`/`reviews`) | `product_ratings` | — |
| ثبت نظر درون‌اپی روی سفارش تحویل‌شده | `POST /orders/{id}/rate` | `product_ratings` | حذف نظر از `/admin/engagement` |
| هماهنگی تم روشن/تاریک با تلگرام | (فقط JS، `tg.colorScheme`+`themeChanged`) | — | — |
| پاداش سرزدن روزانه + بج حساب | `GET/POST /me/checkin` | `daily_checkins` | مبلغ پاداش از `/admin/engagement` (`bot_config.DAILY_CHECKIN_REWARD`) |
| علاقه‌مندی‌ها + محصولات مشابه | `POST/DELETE /favorites/{pid}`, `GET /favorites` | `favorites` | — |
| اطلاع‌رسانی موجودی‌مجدد/تخفیف‌ویژهٔ علاقه‌مندی + تاریخچه اعلان‌ها | `GET /me/notifications`, `POST /me/notifications/read` | `user_notifications` | هوک در `admin_panel.feed_bulk_upload`/`growth_flash_new` (فقط وقتی محصول واقعاً از ۰ موجود به موجود برمی‌گرده) |
| درخواست تسویهٔ همکاری از اپ | `GET /partner/payout-info`, `POST /partner/bank-info`, `POST /partner/payout` | `partner_bank_info`, `partner_payouts` (همون `request_partner_payout()` ربات) | مرکز مالی پنل — بدون تغییر، همون `get_partner_payouts` |
| نوار پیشرفت سطح بعدی همکار | `GET /me/partner` (فیلد `next_tier`) | `partner_tiers` (`core/partners.next_tier_progress`) | مدیریت سطوح همکاری در پنل (`partner_tiers`) |
| اشتراک‌گذاری محصول | (فقط JS، `tg.openTelegramLink('t.me/share/url?...')` با دیپ‌لینک `?start=buy_{id}`) | — | — |
| عکس محصول (با fallback به آیکون دسته) | `GET /categories`, `GET /products/{id}` (فیلد `image_url`) | `products.image_url` | فیلد آپلود در فرم افزودن/ویرایش محصول پنل (`_save_tutorial_file` مسیر `app_media/tutorials/products/...` — نام پوشه ظاهریه، اثر عملکردی نداره) |
| عکس پروفایل کاربر (آپلود خودش، آواتار ۹۶px وسط تب حساب) | `GET /me/profile`, `POST /me/avatar` (روی دیسک `app_media/avatars/{uid}.ext`، نه تلگرام — بدون Pillow، برش دایره‌ای فقط CSS) | `users.avatar_url` | — (کاملاً خودمدیریتی کاربر، بدون نیاز به تأیید ادمین) |

### الگوهای JS قابل‌استفادهٔ مجدد در `app.js`
- `prodImgHtml(p)` — رندر عکس محصول با fallback ایموجی/آیکون؛ همیشه برای هر UI جدید که محصول نشون می‌ده استفاده شود، نه `<img>` مستقیم.
- `starsHtml(avg, count, size)` — رندر ستارهٔ امتیاز.
- `_accPopup(title, html)` / `_accBody()` — الگوی عمومی پاپ‌آپ زیرصفحهٔ تب حساب؛ هر زیرصفحهٔ جدید حساب کاربری (اعلان‌ها، تسویه، …) از همین استفاده می‌کنه، نه پاپ‌آپ دستی جدید.
- `_checkMeBadge()` / `_applyMeBadge()` / `_clearMeBadge()` — بج قرمز آیکون تب «حساب»؛ هر منبع جدید بج (چک‌این، تیکت نخوانده، اعلان نخوانده) باید یک شرط به `_checkMeBadge()` اضافه کنه، نه مکانیزم بج جدا بسازه.
- کلیک‌گیر سراسری روی `a[target="_blank"]` که به `tg.openLink`/`tg.openTelegramLink` مسیر می‌ده — هر لینک خروجی جدید نیازی به کد اضافه نداره، فقط `target="_blank"` بذار.

### دو باگ لایوت رفع‌شدهٔ این دور (کلاس‌بندی برای آینده)
1. **سرریز افقی از عدم `overflow-x:hidden`** روی ظرف تب/پاپ‌آپ + عدم `overflow-wrap:break-word` روی محتوای آزاد (Quill) — می‌تونه با یک لینک/کلمهٔ خیلی بلند رخ بده.
2. **سرریز از `box-sizing:content-box` پیش‌فرض** روی المان `width:100%` دارای padding — در RTL سرریز به چپ می‌ره (نه راست) چون چیدمان از راست شروع می‌شه. هر باکس تازه با `width:100%` + padding باید صریحاً `box-sizing:border-box` بگیره.

هر دو باگ با اندازه‌گیری واقعی `getBoundingClientRect()` در Playwright تشخیص داده شدن، نه با خوندن CSS و حدس زدن — برای باگ لایوت آینده همین روش رو تکرار کن.

### راهنما برای فیچر مینی‌اپ بعدی
1. منطق خالص در `core/<domain>.py` (تابع، بدون FastAPI/HTTP)
2. Endpoint نازک در `api.py` زیر `/api/v1` (فقط auth + صدا زدن core)
3. اگه نیاز به جدول جدید داره: `ensure_*_schema()` با الگوی ALTER+try/except+فلگ گارد (بخش ۷)، و **بلافاصله** به `stbak_engine.py` MODULES هم اضافه کن (فراموش نشه، چون این نشست ۳ بار فراموش شد)
4. UI در `app.js`/`app.css` با استفاده از الگوهای بالا (نه بازسازی از صفر)
5. **هر فیچری که نیاز به مدیریت داره، بخش خودش رو زیر «مدیریت اپ» در پنل ادمین بگیره** (قانون ثابت مالک پروژه — بخش ۱۶ رو هم ببین)
6. تست: سینتکس + FastAPI TestClient با DB موقت واقعی + Playwright با DB موقعیت‌های عادی/لبه (خالی، طولانی، بدون‌مقدار)

---

## ۲۲. کارشناس هوشمند قیمت آیفون — `iphone_valuation/` (از ۲۰۲۶-۰۷-۲۵)

> پکیج مستقل، جدا از `core/`. فرق کلیدی با `core/`: `core/` فقط توسط `api.py` استفاده می‌شه، ولی `iphone_valuation/` رو **هم bot.py هم api.py هم admin_panel.py** مستقیم import می‌کنن — چون این فیچر باید هم‌زمان از ربات (فعلاً) و API (برای مینی‌اپ آینده) و پنل (مدیریت) در دسترس باشه.

### معماری و نقطهٔ ورود مشترک
```
ربات (bot.py) ──┐
API (/api/v1/iphone/valuate) ──┼──> iphone_valuation.service.valuate(payload) ──> نتیجه
مینی‌اپ (فاز بعد) ──┘                    │
                                    ├─ pricing_engine.price()  (فرمول قانون‌محور)
                                    ├─ scoring_engine.compute_score()/compute_verdict()
                                    └─ report.build_report()  (توضیح فارسی، بدون AI خارجی)
```
منطق قیمت‌گذاری **فقط یک‌جا** پیاده‌سازی شده (`service.valuate`) — نه در `bot.py`، نه در `api.py`. اگه فردا مینی‌اپ اضافه شد، فقط UI لازمه، منطق دست‌نخورده می‌مونه.

### فرمول قیمت (pricing_engine.py)
```
ضریب بازار = ۱ + (تاثیر٪ارز + تاثیر٪دادهٔ‌بازار + عرضه/تقاضا٪) ÷ ۱۰۰
ضریب منصفانه = ضریب بازار × (۱ + مجموع‌ضرایب‌شرایط‌دستگاه٪ ÷ ۱۰۰)   [تقریب جمعی، نه ضربی دقیق — کد رو ببین]
قیمت واقعی بازار = قیمت‌پایه × ضریب بازار        (بدون شرایط این دستگاه خاص)
قیمت منصفانه     = قیمت‌پایه × ضریب منصفانه      (با احتساب شرایط واقعی دستگاه)
قیمت پیشنهادی خرید فروشگاه = قیمت‌مرجع‌خرید × ضریب منصفانه
قیمت پیشنهادی فروش فروشگاه = قیمت‌مرجع‌فروش × ضریب منصفانه
```
- **تاثیر ارز:** درصد نوسان نرخ دلار فعلی نسبت به نرخی که موقع تنظیم قیمت پایه در پنل ثبت شده (`iv_capacities.fx_ref_rate`، خودکار ثبت می‌شه)، ضرب در ضریب حساسیت (`IV_FX_SENSITIVITY`، پیش‌فرض ۰.۵، از `/admin/iphone/fx` قابل تغییر). تصمیم عمدی: **نه جمع مستقیم عدد ریالی** با قیمت — چون قیمت آیفون در بازار ایران خطی با دلار حرکت نمی‌کنه.
- **دادهٔ بازار StockLand:** میانگین اختلاف قیمت فروش واقعی (`iv_transactions`) نسبت به قیمت پایه، ضرب در وزن (`IV_MARKET_DATA_WEIGHT`، پیش‌فرض ۰.۱۵). اگه معامله‌ای ثبت نشده باشه (فعلاً همیشه، چون UI ثبتش هنوز نیست)، این عامل صفره.
- **عرضه/تقاضا:** فیلد `demand_percent` روی هر ظرفیت، مستقیم دستی از پنل.
- **شرایط دستگاه:** مجموع `percent` تمام گزینه‌های انتخاب‌شده از `iv_coefficients` (هفت دسته: `condition`, `battery`, `repair`, `registry`, `box`, `cosmetic`, `cable`).
- هیچ عددی هاردکد نیست — فقط مقادیر seed اولیهٔ `iv_coefficients`/`iv_score_weights` (اولین اجرا، بعدش کاملاً از پنل قابل تغییر/حذف/افزودن).

### StockLand Score و نتیجه (scoring_engine.py)
امتیاز ۰-۱۰۰: برای هر دسته، `fraction = پرسنت‌انتخابی ÷ بدترین‌پرسنت‌همون‌دسته` (۰ تا ۱) × وزن دسته (`iv_score_weights`) = کسر امتیاز. دستهٔ هفتم `features` (تست امکانات دستگاه — سؤال بله/خیر ساده در ویزارد ربات، نه هفت تست جدا) نصف وزنش کم می‌شه اگه کاربر «خیر» بزنه.
نتیجه (🟢/🟡/🔴): اگه قیمت پیشنهادی فروشنده داده نشده باشه، فقط بر اساس امتیاز؛ اگه داده شده، بر اساس نسبت قیمت پیشنهادی به قیمت منصفانه + امتیاز با هم.

### جدول‌ها (`iphone_valuation/db.py`، همه با الگوی `ensure_schema` + فلگ گارد استاندارد پروژه)
`iv_models` (مدل+سری+`dual_sim_parts`+`esim_only`+`color_pricing`+`part_pricing`)، `iv_storages` (⚠️ از ۲۰۲۶-۰۷-۲۶ — ظرفیت‌های واقعی هر مدل، `model_id`+`label`+`sort_order`+`active`؛ جایگزین استخراج ظرفیت از متن آزاد قیمت‌ها)، `iv_parts` (⚠️ از ۲۰۲۶-۰۷-۲۶ — پارت‌های **سراسری** قابل‌مدیریت از پنل، `code` یکتا+`label`+`sort_order`+`active`؛ seed اولیه از ثابت قدیمی `PART_OPTIONS` ولی از این به بعد کاملاً دیتابیسیه، ادمین بدون تغییر کد پارت اضافه می‌کنه)، `iv_capacities` (نام فیزیکی جدول عمداً عوض نشد — رکورد قیمت واقعی؛ از ۲۰۲۶-۰۷-۲۶ ستون‌های اصلی `storage_id`/`color_id`/`part_id` هستن نه متن آزاد؛ +قیمت‌پایه+قیمت‌مرجع‌خرید+قیمت‌مرجع‌فروش+نرخ‌ارز‌مرجع+عرضه‌تقاضا — هر ردیف یه ترکیب مدل+ظرفیت+رنگ+پارت)، `iv_colors`، `iv_coefficients` (دسته+کلید+برچسب+درصد، هشت دسته شرایط دستگاه شامل `component`)، `iv_score_weights` (وزن هر دسته برای امتیازدهی)، `iv_fx_sources` (منابع نرخ ارز)، `iv_transactions` (تاریخچهٔ معاملات واقعی — فعلاً بدون UI ثبت)، `iv_valuations` (لاگ کامل هر کارشناسی، برای تاریخچه/آمار پنل).

### نرمال‌سازی کامل دیتابیس قیمت‌گذاری (۲۰۲۶-۰۷-۲۶)
مالک پروژه صریحاً خواست هیچ داده‌ای به‌صورت متن آزاد ذخیره نشه — رکورد قیمت فقط شناسه نگه داره، نه اسم. `iv_capacities` ستون‌های متنی قدیمی (`capacity_label`/`color`/`part_number`) رو برای سازگاری عقب‌رو نگه داشته (بدون `DROP COLUMN` پرریسک) ولی منبع اصلی داده الان `storage_id`/`color_id`/`part_id` (FK به `iv_storages`/`iv_colors`/`iv_parts`) هستن. مهاجرت `_migrate_normalize_pricing_v2` هر ردیف قدیمی رو auto-heal می‌کنه (اگه مقدار متنیش توی جدول lookup تازه پیدا نشه، خودش می‌سازتش، داده حذف نمی‌شه).

**الگوی خواندن سازگار به عقب — چرا `bot.py`/`service.py` تقریباً دست‌نخورده موندن:** `list_capacities`/`get_capacity`/`resolve_capacity` همه از یه JOIN مشترک (`_CAP_SELECT`) استفاده می‌کنن و دیکشنری‌هایی با همون کلیدهای قبلی (`capacity_label`/`color`/`part_number`، این بار **resolve‌شده زنده از جدول‌های lookup**، نه ذخیره‌شده به‌صورت متن) برمی‌گردونن. `resolve_capacity(model_id, capacity_label, part_number='', color='')` امضای رشته‌ای قدیمیش رو حفظ کرده (چون `bot.py` state رو به‌صورت رشته نگه می‌داره) و داخلش رشته‌ها رو با `_find_storage_id`/`_find_color_id`/`_find_part_id` به شناسه resolve می‌کنه؛ `create_capacity`/`update_capacity`/`get_capacity_exact`/`upsert_capacity` (که فرم جدید پنل مستقیم صدا می‌زنه) برعکس، **فقط شناسه** می‌گیرن.

**نصب تازه دیگه رکورد قیمت صفر خودکار نمی‌سازه** — قبلاً برای هر ظرفیت استاندارد هر مدل یه ردیف قیمت=۰ ساخته می‌شد؛ حالا فقط `iv_storages`/`iv_colors` seed می‌شن، سیستم فقط چیزی که ادمین واقعاً از `/admin/iphone/prices` ثبت کرده رو نشون می‌ده. دادهٔ تولید موجود قبل از این تغییر دست‌نخورده می‌مونه (مهاجرت فقط منتقل می‌کنه، چیزی پاک نمی‌کنه).

### قیمت‌گذاری پارت‌محور + رنگ‌محور (از ۲۰۲۶-۰۷-۲۵، رنگ در ۲۰۲۶-۰۷-۲۵ به‌عنوان یک دور دوم اضافه شد)
قیمت هر گوشی بسته به پارت نامبر (LL/A, ZA/A, CH/A) **و** رنگ می‌تونه فرق کنه، پس هر رکورد قیمت یکتا-به-ازای-(مدل+ظرفیت+پارت+رنگ) هست؛ `part_id=NULL`/`color_id=NULL` یعنی «قیمت عمومی بدون پارت/رنگ مشخص». ⚠️ **تصمیم اولیهٔ این نشست این بود که رنگ فقط توصیفیه و روی قیمت اثر نداره — اشتباه بود و مالک پروژه صریحاً تصحیحش کرد؛ رنگ هم دقیقاً مثل پارت یک بعد قیمت‌گذاریه.**

`ivdb.resolve_capacity(model_id, capacity_label, part_number='', color='')` قیمت رو با ۴ سطح fallback به ترتیب دقت پیدا می‌کنه: (پارت دقیق+رنگ دقیق) → (پارت دقیق+رنگ عمومی) → (پارت عمومی+رنگ دقیق) → (پارت عمومی+رنگ عمومی) — یعنی ادمین فقط جایی که قیمت واقعاً فرق داره لازمه پارت/رنگ مشخص وارد کنه، بقیه از قیمت عمومی‌تر استفاده می‌کنن (مقایسه‌ها NULL-safe با `IS ?` هستن، نه `=`، چون `NULL=NULL` توی SQL همیشه false ولی `NULL IS NULL` true است). `ivdb.upsert_capacity(...)` (نه `create_capacity` مستقیم از فرم پنل): اگه ترکیب (مدل+ظرفیت+پارت+رنگ، با شناسه) از قبل ثبت شده باشه آپدیت می‌کنه، وگرنه می‌سازه — **هیچ‌وقت خطای «قبلاً ثبت شده» رد نمی‌شه** (این پیام دقیقاً شبیه باگ قدیمی «ذخیره نمی‌شه» به نظر می‌رسید، پس عمداً حذف شد). `ivdb.get_capacity_exact(model_id, storage_id, part_id, color_id)` تطبیق دقیق شناسه‌ای (نه fallback) رو برمی‌گردونه — پایهٔ upsert. `ivdb.list_capacity_labels(model_id)` از ۲۰۲۶-۰۷-۲۶ مستقیم از `iv_storages` می‌خونه (نه از ردیف‌های قیمت) — یعنی ظرفیت قبل از ثبت هر قیمتی هم توی ویزارد ربات و پنل قابل انتخابه.

**حذف storage/color/part — رفتار متفاوت بر اساس اجباری/اختیاری‌بودن FK:** `delete_storage(storage_id)` چون `storage_id` روی رکورد قیمت اجباریه، **cascade** می‌کنه (رکوردهای قیمت وابسته رو هم پاک می‌کنه — رکورد قیمت بدون ظرفیت بی‌معنیه). `delete_color`/`delete_part` برعکس چون `color_id`/`part_id` اختیاری‌ان، فقط **همون ستون رو NULL می‌کنن** روی رکوردهای وابسته و خودِ قیمت حفظ می‌شه — حذف یه رنگ از کاتالوگ نباید کار قیمت‌گذاری ادمین رو نابود کنه.

**کلید صریح روشن/خاموش برای اثر رنگ/پارت روی قیمت (از ۲۰۲۶-۰۷-۲۵، دور سوم):** مالک پروژه fallback خودکار محض رو کافی ندونست — خواست به‌جای این‌که سیستم حدس بزنه، ادمین صریحاً برای هر مدل تصمیم بگیره. دو ستون جدید روی `iv_models`: `color_pricing`/`part_pricing` (پیش‌فرض ۰/خاموش برای مدل‌های تازه؛ مهاجرت `_migrate_pricing_toggles_v1` برای مدل‌های از‌قبل‌موجود که واقعاً ردیف رنگ/پارت متفاوت داشتن، فلگ رو خودکار روشن نگه می‌داره تا رفتار عوض نشه). **`resolve_capacity` این دو فلگ رو از خودِ مدل می‌خونه و پارامتر رنگ/پارت رو قبل از جست‌وجوی ۴سطحی صفر می‌کنه اگه فلگ مربوطه خاموش باشه** — یعنی الگوریتم fallback خودش دست‌نخورده می‌مونه، فقط ورودی‌هاش از قبل طبق تنظیم ادمین فیلتر می‌شن (اگه هر دو خاموش باشن، عملاً یک لوکاپ تک‌سطحی روی ردیف کاملاً عمومی می‌مونه).

**پارت فقط برای مدل‌های `dual_sim_parts`-دار *پرسیده* می‌شه** (از iPhone XS Max به بعد؛ iPhone XS و پایین‌تر چون `dual_sim_parts` خالیه، اصلاً پرسیده نمی‌شه — همون فلگ سیاست سیم‌کارت موجود `_iv_sim_policy`؛ این سؤال برای تشخیص نوع سیم‌کارت لازمه و **مستقل از فلگ `part_pricing`** همیشه پرسیده می‌شه، حتی اگه پارت روی قیمت اثر نداشته باشه). **رنگ برعکس، همیشه پرسیده می‌شه** (مستقل از `dual_sim_parts` و مستقل از `color_pricing`) — چون رنگ برای همهٔ مدل‌ها به کاربر نمایش داده می‌شه، صرف‌نظر از این‌که روی قیمت اثر داشته باشه یا نه.

**حذف:** `ivdb.delete_capacity(cap_id)` (تک ردیف)، `ivdb.delete_model(model_id)` (کسکید ظرفیت‌ها+رنگ‌های همون مدل؛ تاریخچهٔ `iv_valuations`/`iv_transactions` دست‌نخورده می‌مونه، فقط `model_id` توشون یتیم می‌مونه — دقیقاً مثل رفتار پروژه با محصولات حذف‌شده در سفارش‌های قدیمی).

### نرخ ارز (fx.py)
منابع HTTP نامحدود از پنل (`/admin/iphone/fx`) با `url` + `json_path` (مسیر نقطه‌ای فیلد JSON مثل `usd.sell`) + `priority`. `get_current_rate()`: اگه حالت دستی (`IV_FX_MODE=manual`) → مستقیم `IV_FX_MANUAL_RATE`؛ وگرنه منابع فعال رو به ترتیب اولویت امتحان می‌کنه، اولین موفق رو کش می‌کنه (`IV_FX_LAST_GOOD`) و برمی‌گردونه؛ اگه همه شکست خوردن → آخرین مقدار کش‌شده → نرخ دستی → صفر (هیچ‌وقت استثنا پرتاب نمی‌کنه، قیمت‌گذاری بدون fx ادامه پیدا می‌کنه).

### API (`router.py`، mount در `payment_service.py` مثل `api.py` — try/except، نبودش کل اپ رو نمی‌شکنه)
`GET /api/v1/iphone/models` (مدل+ظرفیت‌ها)، `GET /api/v1/iphone/prices?model_id=`، `GET /api/v1/iphone/options` (گزینه‌های هر دستهٔ ضریب)، `POST /api/v1/iphone/valuate` (بدنه: `model_id`, `capacity_id`, `selections` دیکشنری دسته→کلید، `features_ok`, `sim_type`, `seller_type`, `seller_price`, `city`؛ auth اختیاری با `_auth_optional` از `api.py` — بدون لاگین هم کار می‌کنه، اگه لاگین باشه `user_id` به لاگ کارشناسی وصل می‌شه).

### پنل ادمین (`/admin/iphone`، زیر «مدیریت اپ»)
داشبورد+آمار → `/admin/iphone/models` (کاتالوگ خالص مدل/ظرفیت/رنگ، بدون قیمت) + `/admin/iphone/prices` (⚠️ صفحهٔ تازهٔ ۲۰۲۶-۰۷-۲۶ — همهٔ ثبت/ویرایش/حذف قیمت اینجاست) → `/admin/iphone/coefficients` (CRUD ضرایب هر دسته + وزن امتیازدهی) → `/admin/iphone/fx` (منابع نرخ ارز + حالت دستی/خودکار + حساسیت + وزن دادهٔ بازار) → `/admin/iphone/history` (لاگ کامل کارشناسی‌ها). فعال/غیرفعال‌سازی کل قابلیت با دکمهٔ توگل در داشبورد، که چیزی جز `set_main_button_enabled("MAIN_BTN_IPHONE_VALUATION", ...)` نیست — همون مکانیزم `MAIN_BUTTON_KEYS` استاندارد پروژه (بخش ۱۶، قانون ۴)، نه مکانیزم جدید.

**`/admin/iphone/models` (بازطراحی‌شده و ساده‌شده، ۲۰۲۶-۰۷-۲۶):** مالک پروژه گفت دراپ‌داون رنگ‌های رایج + فرم افزودن رنگ قدیمی «بدردم نمیخوره» — کلاً حذف شد. این صفحه از این به بعد **فقط کاتالوگه، هیچ قیمتی توش ویرایش نمی‌شه** (ثبت قیمت رفته به `/admin/iphone/prices`). هر مدل یه `<details>` جدا: فرم ویرایش نام/سری + دو چک‌باکس «رنگ روی قیمت اثر داره» (همیشه)/«پارت روی قیمت اثر داره» (فقط پارت‌محور) + toggle فعال/غیرفعال + دکمهٔ حذف مدل (`confirm()`)؛ زیرش بخش «ظرفیت‌ها» — چیپ‌های ظرفیت هر کدوم با دکمهٔ × حذف (`POST /iphone/storages/{id}/delete`، تکنیک `form="iv-stor-del-{id}"`) + یه فرم تک‌اینپوتی سادهٔ «+ افزودن ظرفیت» (`POST /iphone/storages/add`)؛ زیرش بخش «رنگ‌ها» — همون الگو با یه فرم تک‌اینپوتی سادهٔ «+ افزودن رنگ» (`POST /iphone/colors/add`، بدون دراپ‌داون رنگ‌های رایج قدیمی).

**`/admin/iphone/prices` (تازه، ۲۰۲۶-۰۷-۲۶) — صفحهٔ اصلی مدیریت قیمت:** طبق درخواست صریح «مشابه لیست پیام‌های بخش تیکت» طراحی شده — دو بخش:
1. **فرم فشردهٔ «📝 ثبت قیمت تازه»** بالای صفحه: دراپ‌داون‌های آبشاری مدل→ظرفیت→رنگ→پارت. یه شیء JSON به اسم `IV_MODEL_DATA` (per-model، شامل storages/colors/parts — colors/parts آرایهٔ خالی می‌مونن اگه `color_pricing`/`part_pricing` اون مدل خاموش باشه) توی `<script>` جاسازی شده؛ یه `onchange` روی دراپ‌داون مدل با JS خام (بدون AJAX) بقیهٔ دراپ‌داون‌ها رو پر/مخفی می‌کنه. ارسال به `POST /iphone/prices/upsert`.
2. **لیست تخت همهٔ رکوردهای قیمت** (`ivdb.list_capacities(active_only=False)`، مرتب بر اساس نام مدل بعد `capacity_sort_key`) — دقیقاً همون ساختار HTML/کلاس‌های Tailwind لیست تیکت‌های پروژه (`card overflow-hidden`→`overflow-x-auto`→`table`). ستون‌ها: مدل | ظرفیت | رنگ | پارت | قیمت پایه/خرید/فروش (هر سه اینپوت ویرایش این‌لاین) | تاریخ بروزرسانی | دکمه‌های 💾ذخیره/🗑حذف. چون `<form>` نمی‌تونه دور `<tr>` بپیچه، هر ردیف از تکنیک `form="iv-pe-{id}"`/`form="iv-pd-{id}"` استفاده می‌کنه که به فرم‌های مخفی جدا بعد از `</table>` اشاره می‌کنن (همون الگوی از قبل جاافتادهٔ پروژه). یه اینپوت جست‌وجوی سمت کلاینت (`#iv-price-search`) روی `data-model` هر `<tr>` فیلتر می‌کنه.

`POST /iphone/prices/upsert` **دفاع در عمق** داره: حتی اگه فرم دستکاری بشه و `color_id`/`part_id` بفرسته، سرور دوباره طبق `color_pricing`/`part_pricing` واقعی مدل این مقادیر رو صفر می‌کنه قبل از upsert — دقیقاً همون منطق `resolve_capacity`، تا هیچ‌وقت رکورد یتیمی که هیچ‌وقت استفاده نمی‌شه ساخته نشه. `POST /iphone/prices/{id}/edit` فقط سه فیلد قیمت رو دست می‌زنه؛ `POST /iphone/prices/{id}/delete` رکورد رو کامل پاک می‌کنه (`ivdb.delete_capacity`). همهٔ فیلدهای قیمت `type="text" inputmode="numeric/decimal"` هستن (نه `type="number"` — بخش ۱۷ رو ببین، دلیلش رو).

### ربات (`bot.py`)
دکمهٔ `MAIN_BTN_IPHONE_VALUATION` در منوی اصلی (`keyboards.main_menu`). ویزارد اینلاین با `user_states[uid]["mode"]="iphone_valuation"` → `"iv_seller_price"` → `"iv_city"` (سه حالت متنی/اینلاین ترکیبی). مراحل (ترتیب از ۲۰۲۶-۰۷-۲۵ چند بار عوض شد): انتخاب مدل → ظرفیت (`ivdb.list_capacity_labels`) → **رنگ** (`ivdb.list_colors(model_id)`، فقط رنگ‌های همین مدل + «سایر») → **[فقط اگه `dual_sim_parts` پر باشه] پارت نامبر** (آخرین مرحله) → `_iv_resolve_and_advance` که `ivdb.resolve_capacity(model_id, label, part_number, color)` قیمتِ درستِ همون ترکیب رو پیدا می‌کنه (`state["capacity_id"]`) → هشت گزینهٔ شرایط دستگاه (از `_IV_COEFF_STEPS`، به ترتیب `iv_coefficients`) → تست امکانات (بله/خیر) → نوع فروشنده → قیمت پیشنهادی (متن آزاد، «ندارم» = رد شدن) → شهر (متن آزاد، «ندارم» = رد شدن) → `_iv_finalize` که `service.valuate()` رو صدا می‌زنه و پیام نهایی رو می‌سازه (برچسب پارت از `ivdb.list_parts()` — ⚠️ از ۲۰۲۶-۰۷-۲۶ دیگه از ثابت هاردکدشدهٔ `PART_OPTIONS` نمی‌خونه، زنده از جدول `iv_parts` می‌خونه تا ادمین بدون تغییر کد پارت جدید اضافه کنه؛ رنگ هم در پیام نهایی نمایش داده می‌شه).

**چرا ترتیب اینه (model → ظرفیت → رنگ → پارت):** کاربر همیشه ظرفیت و رنگ رو انتخاب می‌کنه (این دو همیشه پرسیده می‌شن، صرف‌نظر از این‌که روی قیمت اثر دارن یا نه)؛ پارت آخرین مرحله‌ست چون **فقط برای مدل‌های `dual_sim_parts`-دار پرسیده می‌شه** و صرفاً برای تشخیص نوع سیم‌کارت لازمه، نه انتخاب اولیهٔ دستگاه. قیمت نهایی رو `resolve_capacity` (نه خودِ ویزارد) بر اساس فلگ‌های `color_pricing`/`part_pricing` مدل تعیین می‌کنه — یعنی حتی اگه کاربر رنگ/پارت خاصی رو انتخاب کنه، اگه فلگ مربوطه توی پنل خاموش باشه، قیمت از ردیف عمومی خونده می‌شه.

**⚠️ نکتهٔ مهم Handler Ordering (بخش ۱۶، قانون ۱۶):** کالبک‌های ویزارد (پیشوند `ivw_`) هندلر جدای خودشون رو ندارن — چون کدشون بعد از catch-all اصلی (`handle_callbacks`، `func=lambda c: True`) در فایل قرار می‌گیره و مثل چند مورد دیگهٔ این پروژه (بخش ۱۴) مرده می‌موند. به‌جاش، یه شرط `if data.startswith("ivw_"): return _iv_wizard_callback(call)` **داخل خود catch-all** اضافه شده (دقیقاً مثل الگوی موجود `crypto_net_`/`wallet_crypto`) و منطق واقعی در تابع جدای `_iv_wizard_callback` (تعریف‌شده جای دیگه‌ای از فایل، فراخوانی‌شده از داخل catch-all) پیاده‌سازی شده. **هر فیچر بعدی که کالبک این‌لاین نیاز داره و بعد از `handle_callbacks` در فایل قرار می‌گیره، باید همین الگو رو تکرار کنه.**

**نکتهٔ دیپلوی:** دکمه پیش‌فرض فعاله؛ تا مدل/ظرفیتی در پنل تعریف نشه، کاربر پیام «هنوز مدلی تعریف نشده» می‌بینه (بدون کرش) — بهتره بعد دیپلوی سریع چند مدل وارد بشه یا موقتاً دکمه از تنظیمات غیرفعال بمونه.

---

## ۲۳. Backup/Restore/Recovery، سیستم دسترسی ادمین، منطق خرید ناموجود (از ۲۰۲۶-۰۷-۲۶)

### Backup/Restore/Recovery — `stbak_engine.py` تنها موتور زندهٔ SQLite است

⚠️ **تصحیح مهم نسبت به نسخه‌های قبلی این سند:** تا این نشست، مسیرهای اصلی پنل (دکمهٔ «پشتیبان‌گیری»، همهٔ Restoreها، تردِ بکاپ خودکار روزانه) همه به `pg_backup.py` وصل بودن — ماژولی که فقط با `pg_dump`/`psql` و env var `DATABASE_URL` کار می‌کنه. چون تولید همیشه SQLite است، `DATABASE_URL` هیچ‌وقت ست نمی‌شه، پس بکاپ‌گیری/بازیابی همیشه شکست می‌خورد یا بی‌صدا هیچ کاری نمی‌کرد. این رفع شده: همهٔ این مسیرها الان به `stbak_engine.py` وصلن. `pg_backup.py` حذف نشده (برای احتمال مهاجرت آیندهٔ Postgres) ولی هیچ مسیر زنده‌ای دیگه بهش وصل نیست.

`stbak_engine.py` (v3): بکاپ «کامل» (`modules=None`) خودش با `discover_new_tables()` هر جدولی که در `sqlite_master` هست ولی در دیکشنری `MODULES` پوشش داده نشده رو پیدا و زیر یک بخش خودکار (`_AUTO_MODULE_KEY`) اضافه می‌کنه — یعنی فراموش‌کردن افزودن جدول تازه به `MODULES` (که طبق این سند چندبار اتفاق افتاده بود) دیگه باعث از دست رفتن داده در بکاپ کامل نمی‌شه؛ بکاپ سفارشی/جزئی همچنان دقیقاً به انتخاب صریح ادمین وفادار می‌مونه (کشف خودکار روش اعمال نمی‌شه). فایل‌های `app_media/` هم زیر `media/` داخل همون zip بسته می‌شن. قبل از برگردوندن بکاپ به‌عنوان موفق، `create_stbak` یک dry-run واقعی انجام می‌ده: ساختار جدول‌های دیتابیس فعلی رو در یک دیتابیس آزمایشی در حافظه بازسازی می‌کنه و امکان درج دادهٔ بکاپ رو امتحان می‌کنه؛ هشدارها (نه شکست) توی `manifest.json` ثبت می‌شن.

`restore_stbak`: قبل از دست‌زدن به دادهٔ فعلی یک بکاپ ایمنی خودکار می‌گیره (اگه `safety_backup_dir` داده بشه) — این پایهٔ Recovery است. قبل و بعد از درج داده، تمام مهاجرت‌های Schema شناخته‌شدهٔ پروژه (`db.init_db`, `db.ensure_product_support_schema`, `iphone_valuation.db.ensure_schema`) اجرا می‌شن — یعنی بکاپ‌های قدیمی‌تر از نسخهٔ فعلی کد هم بدون از دست رفتن ستون‌های تازه Restore می‌شن. فایل‌های مدیا هم برمی‌گردن. هر جدول جدا try/except می‌شه (یک جدول ناسازگار کل Restore رو متوقف نمی‌کنه)، خطاها در `result["errors"]` صریح برمی‌گردن (دیگه بی‌صدا قورت داده نمی‌شن).

`save_local_backup(db_path, backup_dir, ...)`/`list_local_backups(backup_dir)`: معادل SQLite-محورِ `pg_backup.create_backup`/`list_local_backups`، برای بکاپ خودکار روزانه (`admin_panel._do_auto_backup`، حالا واقعاً موفق می‌شه) و لیست پنل. مسیر محلی: `admin_panel._BACKUP_DIR` (`/tmp/stockland_backups` پیش‌فرض — قبلاً این ثابت تعریف‌شده بود ولی هیچ‌جا استفاده نمی‌شد، چون `_do_auto_backup` مسیر `pg_backup.BACKUP_DIR` رو صدا می‌زد).

**بازگردانی اضطراری (`POST /admin/database/recover-latest`، دکمهٔ «🆘» در `/admin/database`):** بدون نیاز به انتخاب دستی فایل — بین بکاپ‌های محلی (جدیدترین اول) هرکدوم واقعاً سالم بود (`validate_stbak` پاس بشه) رو پیدا و بازیابی می‌کنه؛ اگه جدیدترین فایل خراب باشه، خودکار سراغ بکاپ قبلی می‌ره (نه اینکه کل عملیات شکست بخوره).

### سیستم دسترسی ادمین — ۲۹ کلید، `PERM_LEGACY` برای سازگاری عقب‌رو

`ALL_PERMISSIONS` (admin_panel.py) از ۱۸ به ۲۹ کلید گسترش یافت. کلیدهای تازه که قبلاً زیر یه کلید عمومی‌تر (معمولاً `settings`/`wallets`) قایم بودن و مالک پروژه صریح خواسته بود جدا بشن: `backup`, `restore`, `recovery` (به‌جای فقط `database`)، `payment` (تأیید رسید کارت‌به‌کارت، `/admin/receipts*`)، `reports` (`/admin/reports`)، `news` (`/admin/app-content*` + `/admin/news-feed*`)، `articles` (`/admin/tutorials*`)، `ai_pricing` (`/admin/iphone*`)، `panel_appearance` (`/admin/settings/theme*` — نه `/admin/settings/save-theme` که ترجیح شخصی هر ادمینه، همیشه آزاد)، `notifications` (`/admin/engagement*`). `mini_app` هم ثبت شده ولی فعلاً به هیچ route‌ای وصل نیست — چون `/admin/shop` عمومیه (auth با initData تلگرام، نه سشن ادمین) و هیچ صفحهٔ تنظیمات اختصاصی مینی‌اپ جدا وجود نداره؛ آمادهٔ اتصال به هر صفحهٔ آیندهٔ مینی‌اپ.

`PERM_LEGACY[new_key] = old_key`: اگه ادمینی `old_key` رو داشته باشه، خودکار به `new_key` هم دسترسی داره — بدون نیاز به تنظیم مجدد دستی بعد از هر آپدیت. مثال: ادمینی که از قبل `wallets` داشته، خودکار `payment` و `reports` رو هم داره.

سه کلید «مرده» (توی `ALL_PERMISSIONS` بودن ولی هیچ‌جا با `_require()` واقعاً چک نمی‌شدن) رفع شدن:
- `categories`: routeهای دسته‌بندی از `products` جدا شدن (۶ route).
- `tickets`: همهٔ ۱۲ route تیکت قبلاً فقط `if not adm` چک می‌کردن (یعنی هر ادمین لاگین‌شده، صرف‌نظر از دسترسی‌های اعطاشده، به همهٔ تیکت‌ها دسترسی داشت) — **این یه گپ امنیتی واقعی بود**، نه فقط یه چک‌باکس بی‌اثر.
- `dashboard`: **عمداً گیت نشد** — کامنت توضیحی بالای تعریفش در `ALL_PERMISSIONS` هست. دلیل: خودِ `/admin/` (dashboard) مقصد استاندارد ریدایرکت هر `_require` دیگه‌ایه (`RedirectResponse("/admin/?err=noperm")`) — گیت‌کردنش یعنی ادمینی که این دسترسی رو نداره وارد یه حلقهٔ ریدایرکت بی‌نهایت به خودِ همین صفحه می‌شه.

`_require_any(admin_info, perms)` (تابع تازه، مکمل `_require`): برای صفحاتی که چند زیردسترسی مجزا رو با هم نشون می‌دن — مثلاً `/admin/database` که دکمه‌های backup/restore/recovery هرکدوم permission جدای خودشون دارن ولی خودِ صفحه باید برای هرکدوم که حداقل یکی از این سه (یا `database` کامل) رو داره باز بشه؛ وگرنه ادمینی که فقط `backup` داره هیچ‌وقت نمی‌تونه به دکمهٔ خودش برسه.

### منطق خرید محصول ناموجود + اطلاع‌رسانی موجود شدن مجدد

**رفتار تازه (قبلاً وجود نداشت):** وقتی موجودی محصول صفره، کاربر اصلاً وارد چرخهٔ خرید نمی‌شه — نه کسر پول، نه ثبت سفارش، نه صف «ارسال بعدی». این گیت در `_show_order_summary` (bot.py) قرار داره — تنها نقطه‌ای که همهٔ مسیرهای ورود به خلاصهٔ سفارش (شروع خرید، اعمال/حذف کد تخفیف) ازش رد می‌شن، پس یک گیت همه‌جا رو پوشش می‌ده. چک دوم (defense in depth) قبل از هر کسر پولی در `finalize_product_order`/`handle_confirm_full`/`handle_confirm_wallet` هم هست — برای race condition نادر بین نمایش خلاصهٔ سفارش و لحظهٔ پرداخت.

`products.notify_on_restock` (ستون تازه، پترن مهاجرت استاندارد در `ensure_product_support_schema`؛ چک‌باکس «اطلاع‌رسانی موجود شدن مجدد» در فرم افزودن/ویرایش محصول پنل): اگه خاموش باشه و موجودی صفر باشه، فقط پیام «موجودی این محصول در حال حاضر به پایان رسیده» با دکمهٔ بازگشت نشون داده می‌شه؛ اگه روشن باشه، دکمهٔ خرید کلاً به «🔔 موجود شد اطلاع بده» تبدیل می‌شه (کال‌بک `notify_stock_{pid}` → `subscribe_stock`). بک‌اند این قابلیت (`subscribe_stock`, `get_stock_subscribers`, هوک اطلاع‌رسانی در `admin_panel.feed_bulk_upload`) از قبل کامل توی کد بود — فقط هیچ‌وقت دکمه‌اش واقعاً ساخته نمی‌شد.

**رفع fallback خطرناک قدیمی:** وقتی موجودی درست بین نمایش خلاصهٔ سفارش و لحظهٔ تأیید پرداخت (race condition) تموم می‌شد، `claim_next_feed_item` شکست می‌خورد و کد قبلاً بی‌صدا `enqueue_pending_delivery` صدا می‌زد (یعنی همون «ارسال بعدی» که باید حذف می‌شد). در هر سه مسیر پرداخت (کیف‌پول در bot.py، PHP bridge و Zarinpal callback در payment_service.py، و مینی‌اپ در api.py) این حالا با بازگشت کامل مبلغ به کیف‌پول کاربر + `status='returned'` (طبق قانون پروژه — بخش ۱۶ قانون ۷ — از دید کاربر کاملاً مخفی) جایگزین شده. `enqueue_pending_delivery`/`pending_deliveries`/`try_dispatch_pending_for_product` حذف نشدن (کد مرده، بی‌خطر) — فقط دیگه از مسیر خرید عادی صدا زده نمی‌شن.

مینی‌اپ (`api.py`): `POST /checkout` سمت سرور موجودی رو چک می‌کنه (هیچ‌وقت به کلاینت اعتماد نمی‌شه)؛ `_deliver_or_queue_order` همون رفتار refund رو داره؛ `POST /products/{id}/notify` معادل دکمهٔ ربات؛ `GET /products` و `/products/{id}` (`core/products.py`) حالا فیلدهای `stock`/`notify_on_restock` رو برمی‌گردونن. `app/app.js`: پاپ‌آپ خرید وقتی ناموجوده اصلاً کیف‌پول/کد تخفیف/دکمه‌های پرداخت نشون نمی‌ده — یا پیام ناموجود، یا دکمهٔ `_notifyStock()`.

### ⚠️ باقی‌مانده: باگ باز شدن اخبار/مقالات در «بخش مرورگر»

طبق درخواست مالک پروژه، برچسب تکراری «📰 اخبار» که روی تک‌تک کارت‌های خبر در `app.js` تکرار می‌شد حذف شد (تب/بخش از قبل عنوان مشابه داره). **ولی خودِ باگ اصلی («باز کردن اخبار/مقالات در بخش مرورگر درست کار نمی‌کنه») هنوز رفع نشده** — تحقیق دو مسیر محتمل پیدا کرد (۱) مینی‌اپ که بیرون از تلگرام در یه مرورگر معمولی باز بشه، (۲) پیش‌نمایش مقاله از خودِ پنل ادمین (`/admin/tutorials/{id}/preview`) — ولی محل دقیق تکرار باگ هنوز از مالک پروژه دریافت نشده. قبل از اقدام روی این مورد، حتماً محل دقیق تکرار رو از مالک پروژه بپرس.
