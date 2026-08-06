# StockLand — AI Project Memory (CLAUDE.md)

> این فایل حافظهٔ دائمی پروژه برای دستیار هوش‌مصنوعیه. **همیشه قبل از شروع هر کار این فایل رو بخون.** کد فعلی مرجع نهایی حقیقته — اگه جایی این سند با رفتار واقعی کد فرق داشت، کد درسته و این فایل باید آپدیت بشه، نه برعکس.
>
> تاریخ آخرین تحلیل کامل: ۲۰۲۶-۰۷-۲۳ — انجام‌شده توسط Claude Code (تحلیل کامل مخزن، بدون تغییر کد، طبق دستور مالک پروژه).
> تاریخ آخرین بروزرسانی افزایشی: ۲۰۲۶-۰۸-۰۶ — رفع ۳ باگ محاسباتی حسابداری + ادغام گزارش مالی + چپ‌چین اعداد پنل، رفع باگ سراسری دکمهٔ نامرئی (متغیر CSS `--clr-primary`)، بازطراحی صفحهٔ خلاصهٔ ویزارد کارشناسی آیفون، تکمیل حسابداری با Import عمومی TXT/CSV/Excel + «تعویض کالا» + گزارش‌گیری، رفع نوتیف درخواست فروش + راست‌چین/چپ‌چین ستاره‌ها-نمودارها + کیف‌پول پاداش مینی‌اپ، بازطراحی Premium صفحهٔ «دعوت دوستان» مینی‌اپ، رفع کامل متن/اشتراک‌گذاری دعوت (تگ HTML خام، تکرار لینک، برگشت به الگوی استاندارد `url=+text=` تلگرام)، مسیر اختصاصی آپلود اکسل موجودی محصول چندستونی + چپ‌چین apple id در پنل + توضیحات مشترک اختیاری برای آپلود موجودی، رفع رنگ نامرئی حباب پیام ادمین چت تیکت (تکرار باگ `--clr-primary`) + رفع تغییر نام/پسوند فایل پیوست تیکت پس از انتقال به پنل + امکان ارسال عکس/فایل از پنل به کاربر در چت تیکت + تکمیل سیستم برگشت محصول (رفع باگ نمایش سفارش برگشتی در خریدهای من + بستن خودکار تیکت راه‌اندازی وابسته) + پاکسازی خودکار کش و فایل‌های موقت + یکسان‌سازی پذیرش رقم فارسی/عربی/لاتین در ورودی مبلغ (بات+مینی‌اپ) + تکمیل واقعی سیستم پاداش/چرخهٔ معرفی برای کاربران غیرهمکار (رفع باگی که تحلیل قبلی روی تابع مردهٔ اشتباه انجام داده بود) + رفع ریشه‌ای سیستم برگشت محصول (بازگشت به موجودی بی‌اثر در اکثریت سفارش‌ها + پیام تحویل غیرقابل‌حذف از چت، هر سه مسیر تحویل بات/درگاه/مینی‌اپ) + استاندارد وضعیت پرداخت برای تحویل‌های اصلاحی/تعویضی (بخش ۲۹ تا ۴۱) — قبل از کار روی هرکدوم، همون بخش رو بخون تا نیازی به خوندن دوبارهٔ کد نباشه.
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
├── duplicate_products.py      ماژول مستقل تشخیص/حذف محصولات تکراری (بخش ۸ سند مینی‌اپ، از ۲۰۲۶-۰۷-۳۱) — فقط توسط admin_panel.py استفاده می‌شود
├── rate_limit.py               ریت‌لیمیت سبک درون‌حافظه‌ای مشترک بین payment_service.py/api.py/iphone_valuation (از ۲۰۲۶-۰۷-۳۱، فاز ۱ ممیزی) — الگوی _login_attempts پنل، عمومی‌شده
├── image_utils.py               فشرده‌سازی/resize خودکار عکس آپلودی با Pillow (از ۲۰۲۶-۰۷-۳۱، فاز ۲ ممیزی)
├── html_sanitize.py             sanitizer whitelist-محور HTML برای بدنهٔ آموزش/محتوا (از ۲۰۲۶-۰۷-۳۱، فاز ۲ ممیزی)
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

**Middleware سراسری:** `_refresh_admin_session` (payment_service.py) روی هر request اجرا می‌شود و کوکی سشن ادمین را برای مسیرهای `/admin/*` تازه می‌کند (۳۰۰ ثانیه TTL). ⚠️ تا ۲۰۲۶-۰۷-۲۶ این میدل‌ور تابع کامل `_get_admin` (که یک کوئری دیتابیس داره) رو صدا می‌زد — دقیقاً همون کاری که خودِ هر route handler چند خط پایین‌تر دوباره انجام می‌داد؛ یعنی هر درخواست `/admin/*` دوبار از دیتابیس ادمین می‌خوند. رفع شد: میدل‌ور الان از `admin_panel._verify_session_cookie` (فقط HMAC+idle-timeout، بدون دیتابیس) استفاده می‌کنه؛ `_get_admin` هم بازنویسی شد تا خودش از همین تابع به‌عنوان جزء اول منطقش استفاده کنه (بدون تغییر رفتار بیرونی). `_layout()` هم جدا خودش `admin_panel._refresh_session()` (ارزون، بدون کوئری) رو برای صفحات HTML صدا می‌زنه — این دوتا دیگه کار تکراری نمی‌کنن، هرکدوم نقش مکملِ خودشون رو دارن (میدل‌ور برای مسیرهای غیر-HTML مثل JSON/redirect، `_layout` برای صفحات رندرشده).

---

## ۵. معماری ربات تلگرام

- کتابخانه: `pyTelegramBotAPI` (telebot)، `parse_mode="HTML"`
- **فقط Polling** فعال است در حالت مستقیم (`bot.infinity_polling`)؛ کد webhook هم در `payment_service.py` وجود دارد و سوییچ‌پذیر است.
- **Exception handler مرکزی**: `_BotExceptionHandler` (bot.py:143-165) — همهٔ خطاهای بدون‌مدیریت هندلرها را می‌گیرد، لاگ کامل + traceback می‌نویسد، و یک هشدار HTML (حداکثر ۱ بار در ۶۰ ثانیه) به `ADMIN_ID` می‌فرستد. متن این هشدار فقط `str(exception)[:300]` است — برای تشخیص دقیق همیشه باید traceback کامل را از `journalctl` گرفت.
- **پچ اعداد فارسی سراسری**: `_fa_digits()` (bot.py:180-229) روی `send_message`/`edit_message_text`/`reply_to`/`send_photo` caption/`answer_callback_query`/`edit_message_caption` مانکی‌پچ شده؛ لینک‌ها، `<code>`/`<pre>`، `@username`، `/command` مستثنا هستند. **پچ نشده:** `send_document`، captionِ `send_animation`/`send_video`.
- ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، فاز ۳ ممیزی)** — ~~دو سیستم Rate-Limit مستقل و همپوشان~~ — سیستم دوم (`_rate_limits`/`_is_rate_limited`، وسط فایل) حذف شد؛ چون آستانهٔ سیستم اول (`_rl_msg_store`/`_rl_cb_store`، بالای فایل، registered زودتر) همیشه سخت‌گیرانه‌تر بود و طبق قانون single-dispatch تلگرام‌بات، همیشه اول تصمیم می‌گرفت — سیستم دوم برای پیام‌ها عملاً هیچ‌وقت واقعاً تصمیم‌گیرنده نبود.
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
  → finalize_product_order() → کسر کیف‌پول (✅ از ۲۰۲۶-۰۷-۳۱ از طریق subtract_wallet_balance — قبلاً SQL خام مستقیم بود، بخش ۲۳ رو ببین)
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
| `POST /payment/create` | ساخت تراکنش (اعتبارسنجی مبلغ/نوع/محدودیت روزانه) → **`_run_gateway_failover()`** (سیستم چند‌درگاهی، بخش ۲۵) → درج ردیف `pending` در `zarinpal_transactions` (با ستون `gateway`) → برمی‌گرداند `{authority, payment_url, gateway}` |
| `GET /payment/callback` و `GET|POST /payment/callback/{gw}` | ریدایرکت مرورگر بعد از پرداخت — درگاه‌آگاه (بخش ۲۵)؛ idempotent (اگر از قبل `paid` بود، دوباره کاری نمی‌کند)؛ زیر `BEGIN IMMEDIATE` قفل می‌شود تا کال‌بک دوبل مشکل نسازد؛ بسته به `payment_type` یا کیف‌پول شارژ می‌شود یا سفارش کامل می‌شود (`create_order` + `claim_feed_item`/بازگشت وجه). مسیر بدون `/{gw}` برای سازگاری عقب‌رو (تراکنش‌های زرین‌پالِ در جریان قبل از فیچر چند‌درگاهی) نگه داشته شده |
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
| `INTERNAL_API_SECRET` | راز محافظت‌کنندهٔ `POST /payment/create` از فراخوانی مستقیم اینترنت (بخش ۱۳ آیتم ۱۱) — دقیقاً همون الگوی `WEBHOOK_SECRET`، اگر خالی باشد خودکار تولید می‌شود |
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
| `DB_CONNECTION_POOL` | `"1"` برای فعال‌سازی connection pooling سبک SQLite (پیش‌فرض خاموش — بخش ۲۸، فاز C) |
| `SQLITE_PATH` | ورودی اسکریپت `migrate_to_postgres.py` |
| `GDRIVE_CLIENT_ID`, `GDRIVE_CLIENT_SECRET`, `GDRIVE_FOLDER_ID`, `GDRIVE_SA_JSON` | بکاپ ابری Google Drive |
| `IV_AI_ENC_KEY` | کلید رمزنگاری Fernet برای ذخیرهٔ کلید API کارشناس مکمل هوش مصنوعی (بخش ۲۲.۹) — بدون این، کل قابلیت AI از پنل قابل‌فعال‌شدن نیست (fail closed، `iphone_valuation/ai_crypto.py`) |
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
- `pip install -r requirements.txt`: `pyTelegramBotAPI>=4.14,<5`, `requests`, `Flask>=3.0,<4` (احتمالاً بلااستفاده — کل استک روی FastAPI است، بررسی نشد کجا Flask واقعاً import می‌شود)، `fastapi>=0.110,<1`، `uvicorn[standard]>=0.27,<1`، `python-multipart`، `openpyxl>=3.1` (اکسپورت Excel در پنل حسابداری)، `cryptography>=41.0,<43` (رمزنگاری کلید API کارشناس AI، بخش ۲۲.۹)، `anthropic>=0.120,<1` (SDK رسمی Claude، provider فعلاً یگانهٔ کارشناس مکمل هوش مصنوعی)، `Pillow>=10.0,<12` (فشرده‌سازی/resize خودکار عکس آپلودی — `image_utils.py`، از فاز ۲ ممیزی)
- systemd برای مدیریت سرویس
- برای مینی‌اپ: `app/get_vendor.sh` باید یک‌بار روی سرور اجرا شود (دانلود Framework7 + فونت‌ها به `app/vendor/`)

---

## ۱۳. نقاط حساس امنیتی (Security-Sensitive Areas)

> این‌ها یافته‌های تحلیل کد فعلی‌اند، **هیچ‌کدام در این نشست تغییر داده نشده‌اند** — فقط مستندسازی شده‌اند. قبل از هر اقدام روی این موارد با مالک پروژه هماهنگ شود.

1. ✅ **رفع‌شده (۲۰۲۶-۰۷-۲۶، PR #86)** — ~~SQL Injection واقعی~~ — `db.py` تابع `get_card_receipts(status)` مقدار `status` را مستقیم در رشتهٔ SQL درج می‌کرد؛ حالا پارامتری‌شده (`WHERE r.status=?`). تابع تازهٔ `count_card_receipts(status)` هم برای شمارش سبک (بدون fetch کامل) اضافه شد.
1b. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، ضمن کار روی بخش ۹ حسابداری)** — ~~SQL Injection دوم، سه‌جا~~ — `get_accounting_kpis`, `get_cashflow`, `get_expenses` مقادیر `date_from`/`date_to` (و `category` در `get_expenses`) رو مستقیم با f-string داخل SQL درج می‌کردن؛ این پارامترها از query string پنل (`/admin/accounting?df=...&dt=...`) میان — یعنی چون از طریق GET بدون نیاز به CSRF token قابل تزریقن (پنل CSRF protection نداره، بخش ۱۳ آیتم ۶)، یه ادمین لاگین‌شده می‌تونست صرفاً با کلیک روی یه لینک ساخته‌شده قربانی این حمله بشه. `get_expenses` حتی یه «ساده‌سازی» ناقص داشت (`category.replace(chr(39),'')`) که نشون می‌داد نویسنده از خطر آگاه بوده ولی راه‌حل اشتباه انتخاب کرده. هر سه تابع حالا کاملاً پارامتری‌شدن. تست: هارنس مستقیم با payload شامل `'; DROP TABLE orders; --` — بدون خطای دیتابیس، بدون تغییر داده (اثبات این‌که دیگه به‌عنوان SQL تفسیر نمی‌شه).
2. **رمز سوپرادمین plaintext روی دیسک** — مسیر `POST /admin/admins/super/password` رمز جدید را بدون هش مستقیم داخل فایل `.env` می‌نویسد (و `/admins/super/telegram_id` همین الگو را برای `ADMIN_ID` دارد).
3. **یوزرنیم‌های bypass هاردکد** — لاگین پنل با یوزرنیم `"admin"` یا `"super"` همیشه به‌عنوان سوپرادمین معتبر پذیرفته می‌شود، حتی اگر `ADMIN_WEB_USERNAME` چیز دیگری تنظیم شده باشد.
4. **دو پیش‌فرض متفاوت برای `SESSION_SECRET`** — `_hash_pw` پیش‌فرض `"stockland"` دارد، `_make_session`/`_get_admin` پیش‌فرض `"stockland-panel"` دارند. اگر env ست نشود، سشن‌ها/هش پسورد با این رشته‌های هاردکدشدهٔ ضعیف قابل جعل‌اند.
5. **هش پسورد ادمین‌ها ضعیف** — `SHA256(SESSION_SECRET + password)`، بدون salt، بدون iteration — نه bcrypt/argon2/PBKDF2.
6. **بدون CSRF token** روی هیچ فرم پنل ادمین (فقط `SameSite=Lax` cookie).
7. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، فاز ۰ ممیزی کامل)** — ~~دو مسیر webhook تلگرام موازی~~ — مسیر ناامن `/webhook` (بدون auth، امکان جعل کامل هویت `ADMIN_ID` با یک Update جعلی) کاملاً حذف شد؛ تأیید شد که این مسیر هیچ‌وقت به‌عنوان webhook واقعی تلگرام ثبت نمی‌شد (`_activate_webhook` همیشه فقط مسیر امن `/telegram/webhook/{BOT_TOKEN}` با `secret_token=WEBHOOK_SECRET` رو فعال می‌کنه)، پس حذفش کد مرده رو هم پاک کرد هم یه حفرهٔ امنیتی رو بست.
8. **`API_KEYS`/`X-User-Id`** در `api.py` — روش دوم auth، بدون امضا؛ هر کسی با کلید معتبر می‌تواند خود را جای هر `user_id` دلخواه جا بزند.
9. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، تأیید صریح مالک پروژه)** — ~~`database/bot.db` یک فایل SQLite باینری با داده‌های واقعی‌نما از ابتدای پروژه در گیت کامیت شده~~ — کاملاً از **تمام تاریخچهٔ گیت** حذف شد (`git-filter-repo --path database/bot.db --invert-paths`)، نه فقط از HEAD. همهٔ برنچ‌ها (`main`, `claude/git-connection-issue-cupwr0`, `server-backup-2026-07-23`) بازنویسی و force-push شدن. **⚠️ این یعنی تمام commit hashها عوض شدن** — سرور تولید (یا هر clone دیگه‌ای) دیگه نمی‌تونه `git pull` ساده بزنه؛ باید کامل دوباره clone بشه یا با `git fetch origin && git reset --hard origin/main` ریست بشه (بخش ۱۹/۲۰ همین سند رو برای دستورهای دقیق ببین).
10. **بدون رمزهای TODO/FIXME یافت‌شده** در کد — یعنی این موارد خودشان را در کامنت‌ها پرچم نکرده‌اند؛ فقط با خواندن مستقیم کد پیدا شدند.
11. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، فاز ۰ ممیزی کامل)** — ~~`POST /payment/create` بدون احراز هویت~~ — چون uvicorn پشت nginx روی `127.0.0.1` گوش می‌ده، این مسیر داخلی (که فقط باید از `services/payments.py`/`api.py` صدا زده بشه) از اینترنت هم قابل‌دسترس بود و بدنهٔ کاملاً کلاینت‌کنترل (`user_id`, `wallet_reserved`, `chat_id`) امکان سرقت مستقیم موجودی کیف‌پول هر کاربری رو می‌داد (پرداخت مبلغ کوچیک `amount` توسط مهاجم + کسر کامل `wallet_reserved` قربانی). رفع با راز داخلی `config.INTERNAL_API_SECRET` (الگوی `WEBHOOK_SECRET`، خودکار تولیدشده اگه env ست نشه) چک‌شده با `hmac.compare_digest` روی هدر `X-Internal-Secret`.
12. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، فاز ۰ ممیزی کامل)** — ~~کوکی سشن ادمین بدون Secure~~ — هر ۳ محل صدور کوکی `adm` حالا `secure=True` دارن (تولید همیشه HTTPS است).
13. ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱، فاز ۰ ممیزی کامل)** — ~~rate-limit ورود پنل روی IP اشتباه~~ — `login_post` حالا مثل `_log()` از `X-Forwarded-For` می‌خونه؛ قبلاً `request.client.host` پشت nginx همیشه یکسان بود، یعنی هرکسی می‌تونست با ۵ تلاش ناموفق، ورود پنل رو برای مدیر واقعی هم قفل کنه (DoS رایگان).

---

## ۱۴. مشکلات شناخته‌شدهٔ فعلی (Known Issues)

### 🔴 باگ‌های فعال (تأثیرگذار روی کاربر واقعی)

| # | مشکل | محل | وضعیت |
|---|---|---|---|
| 1 | ~~`/api/v1/checkout` با `NameError: _get_uid` کرش می‌کرد~~ | `api.py:286` | ✅ **رفع‌شده در این نشست** — به `_auth` تغییر یافت (کامیت `9760faf`) |
| 2 | ~~مسیر درگاه/ترکیبی `POST /api/v1/checkout` به `http://127.0.0.1:8001/payment/create` هاردکد وصل می‌شود و انتظار کلید `redirect_url` دارد؛ `payment_service.py` واقعاً `{authority, payment_url}` برمی‌گرداند~~ | `api.py` | ✅ **رفع‌شده** — هاردکد URL در فاز ۲ ممیزی (بخش ۲۴) با `PAYMENT_API_BASE_URL` جایگزین شد. دربارهٔ خودِ «mismatch»: تأیید مجدد کد فعلی (۲۰۲۶-۰۷-۳۱) نشون داد اصلاً mismatch نبوده — هر دو نقطهٔ فراخوانی (`api.py:747,1467`) صریحاً `data["payment_url"]` رو می‌خونن و به‌عنوان `redirect_url` برمی‌گردونن؛ این ردیف صرفاً یه توصیف نادرست قدیمی بوده. |
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
- ✅ **رفع‌شده (۲۰۲۶-۰۷-۳۱)** — ~~`payments.py` (ریشه) و `storage.py` کاملاً بلااستفاده‌اند~~ — هر دو حذف شدن (+ نسخه‌های راکد ریشهٔ `app.js`/`app.css`/`manifest.json`/`sw.js`)، طبق تأیید صریح مالک پروژه.
- ۷۴ از ۱۳۱ کلید `DEFAULT_UI_TEXTS` (~۵۶٪) هیچ‌جا استفاده نمی‌شوند — پیام‌های واقعی معادل، هاردکد فارسی داخل کدند (نقض قانون خود پروژه دربارهٔ عدم هاردکد متن)
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
- ✅ **رفع‌شده (۲۰۲۶-۰۷-۲۶):** پارامتری‌کردن کوئری `get_card_receipts`

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
| تأیید قوانین خرید قبل از پرداخت (بخش ۷، از ۲۰۲۶-۰۷-۳۱؛ متن per-product از ۲۰۲۶-۰۷-۳۱ دور بعد) | `GET /products/{id}` (فیلدهای `require_terms` + `terms_text` — همون متن resolve‌شده، دیگه نیازی به فراخوانی جدای `/purchase-terms` در چک‌اوت نیست؛ endpoint `GET /purchase-terms` هنوز برای سازگاری/مصرف بیرونی وجود داره، فقط `openCheckout` دیگه صداش نمی‌زنه)، `POST /checkout` (بدنه‌اش `agreed_terms` می‌گیره، بدونش ۴۰۰ برمی‌گردونه) | `products.require_terms` (per-product toggle) + `products.terms_text` (متن اختصاصی هر محصول، مثل الگوی `setup_message`) + `bot_config.PURCHASE_TERMS_TEXT` (فقط fallback سراسری وقتی `terms_text` محصول خالیه — `db.get_product_terms_text()`) | `/admin/settings/purchase-terms` (ویرایش متن پیش‌فرض عمومی/fallback) + چک‌باکس «نیاز به تأیید قوانین خرید» + تکست‌اریای «متن قوانین اختصاصی این محصول» در فرم افزودن/ویرایش محصول (پیش‌فرض خاموش، متن اختصاصی اختیاری) |
| تب «ابزار مفید» — هاب موزاییکی جایگزین تب مستقل «آموزش» (بخش ۶، از ۲۰۲۶-۰۷-۳۱) | (فقط JS/HTML، بدون API تازه — `#tab-tools` صرفاً کارت‌های ناوبری داره) | — | — (کارت‌های «کارشناسی قیمت آیفون»/«سلامت آیفون» فعلاً placeholder با برچسب «به‌زودی»‌ان، بدون لینک واقعی — طبق تصمیم موجود پروژه که انتقال کارشناسی آیفون به مینی‌اپ فاز بعده) |
| دو قیمت (اصلی + همکاری) در صفحهٔ محصول (بخش ۲، از ۲۰۲۶-۰۷-۳۱) | `GET /products/{id}` (فیلدهای `show_partner_price`/`partner_price`، حالا با auth اختیاری چون قیمت همکاری وابسته به uid‌ه) | — (فقط منطق، دیتا از `products.partner_price` موجود) | — (همون فرم قیمت همکاری محصول در پنل — چیزی جدید نیست) |
| پنل همکاری — بازطراحی کامل چندبخشی (از ۲۰۲۶-۰۷-۳۱، دور دوم) — طبق دستور صریح مالک پروژه: تمام قابلیت‌های داشبورد همکار بات (به‌جز «چت با پشتیبان»، چون اپ پشتیبانی مستقل خودش رو داره) به پنل همکاری مینی‌اپ منتقل شد؛ ردیف مستقل «دعوت دوستان» از تب حساب حذف شد، لینک دعوت فقط از داخل همین پنل در دسترسه. ساختار: `openPartner()` یه داشبورد اصلی (سطح+پیشرفت+۴ ردیف ناوبری) رندر می‌کنه؛ هر بخش صفحهٔ خودش رو با یه لینک «‹ بازگشت» همون داخل popup رندر می‌کنه (بدون بستن/بازکردن) | `GET /partner/team` (تیم فروش دوسطحی)، `GET/POST /partner/profile` (نام/فروشگاه/شهر/آدرس+بانکی، partial-update)، `GET /partner/wallet` (موجودی+تراکنش‌ها)، `POST /partner/wallet/transfer` (انتقال به کیف‌پول اصلی)، `GET /me/invite` (حالا شامل `promo_text` هم برای دعوت‌و‌تبلیغ)، `GET /me/partner` (بدون تغییر) | — (همه از جدول‌های موجود می‌خونن/می‌نویسن: `partners`, `partner_bank_info`, `partner_wallets`, `partner_transactions`, `referrals`, `orders`) | — |
| عکس پروفایل کاربر (آپلود خودش، آواتار ۹۶px وسط تب حساب) | `GET /me/profile`, `POST /me/avatar` (روی دیسک `app_media/avatars/{uid}.ext`، نه تلگرام — بدون Pillow، برش دایره‌ای فقط CSS) | `users.avatar_url` | — (کاملاً خودمدیریتی کاربر، بدون نیاز به تأیید ادمین) |

### الگوهای JS قابل‌استفادهٔ مجدد در `app.js`
- `prodImgHtml(p)` — رندر عکس محصول با fallback ایموجی/آیکون؛ همیشه برای هر UI جدید که محصول نشون می‌ده استفاده شود، نه `<img>` مستقیم.
- `starsHtml(avg, count, size)` — رندر ستارهٔ امتیاز.
- `_accPopup(title, html)` / `_accBody()` — الگوی عمومی پاپ‌آپ زیرصفحهٔ تب حساب؛ هر زیرصفحهٔ جدید حساب کاربری (اعلان‌ها، تسویه، …) از همین استفاده می‌کنه، نه پاپ‌آپ دستی جدید.
- `_checkMeBadge()` / `_applyMeBadge()` / `_clearMeBadge()` — بج قرمز آیکون تب «حساب»؛ هر منبع جدید بج (چک‌این، تیکت نخوانده، اعلان نخوانده) باید یک شرط به `_checkMeBadge()` اضافه کنه، نه مکانیزم بج جدا بسازه.
- کلیک‌گیر سراسری روی `a[target="_blank"]` که به `tg.openLink`/`tg.openTelegramLink` مسیر می‌ده — هر لینک خروجی جدید نیازی به کد اضافه نداره، فقط `target="_blank"` بذار.

### سه باگ لایوت رفع‌شده (کلاس‌بندی برای آینده)
1. **سرریز افقی از عدم `overflow-x:hidden`** روی ظرف تب/پاپ‌آپ + عدم `overflow-wrap:break-word` روی محتوای آزاد (Quill) — می‌تونه با یک لینک/کلمهٔ خیلی بلند رخ بده.
2. **سرریز از `box-sizing:content-box` پیش‌فرض** روی المان `width:100%` دارای padding — در RTL سرریز به چپ می‌ره (نه راست) چون چیدمان از راست شروع می‌شه. هر باکس تازه با `width:100%` + padding باید صریحاً `box-sizing:border-box` بگیره. ⚠️ استثنا: خودِ `<button>`/`<input>` نیازی به این ندارن چون Framework7 قانون سراسری `button{box-sizing:border-box}` داره — قبل از «رفع» این الگو روی button، با `getComputedStyle` تأیید کن که واقعاً مشکلی هست، وگرنه یه تغییر بی‌اثر/تکراری می‌زنی.
3. **`align-self:flex-end`/`flex-start` داخل یک ظرف `flex-direction:column` که در `dir="rtl"` قرار داره، فیزیکی برعکسِ تصور طبیعیه** — `flex-end` سمت **چپ** می‌شینه، `flex-start` سمت **راست** (نه برعکس، هرچقدر هم منطقی به‌نظر برسه). پیدا شده در `app.css` (بخش «چت پشتیبانی» — `.sl-sp-mine`/`.sl-sp-theirs`، ۲۰۲۶-۰۷-۳۱): حباب پیام خودِ کاربر با `flex-end` سمت چپ می‌نشست، برخلاف قرارداد استاندارد چت‌های فارسی (پیام خودم = راست). رفع با سواپ کردن `flex-end`↔`flex-start` (+ سواپ متقارن `border-radius` دم حباب). قبل از هر ادعای درست/غلط بودن سمت یه المان RTL-flex-column، با یه تست ایزوله (یا مستقیم `getBoundingClientRect()` روی صفحهٔ واقعی) اندازه بگیر — این‌جا هم یه تست مینیمال جدا قبل از تغییر کد واقعی اجرا شد تا خودِ برداشت اولیه از رفتار مرورگر تأیید بشه.

هر سه باگ با اندازه‌گیری واقعی `getBoundingClientRect()` در Playwright تشخیص داده شدن، نه با خوندن CSS و حدس زدن — برای باگ لایوت آینده همین روش رو تکرار کن.

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
- **شرایط دستگاه:** مجموع `percent` تمام گزینه‌های انتخاب‌شده از `iv_coefficients` (`COEFFICIENT_CATEGORIES` در `iphone_valuation/db.py`: `condition`, `battery`, `repair`, `registry`, `box`, `cosmetic`, `cable`, `component`، به‌علاوهٔ `replaced` از ۲۰۲۶-۰۷-۲۶ — بخش «بازطراحی ویزارد» پایین‌تر). هیچ عددی هاردکد نیست — فقط مقادیر seed اولیهٔ `iv_coefficients`/`iv_score_weights` (اولین اجرا، بعدش کاملاً از پنل قابل تغییر/حذف/افزودن).
- ⚠️ **نکتهٔ معماری مهم (تأییدشده ۲۰۲۶-۰۷-۲۶):** حلقهٔ اصلی `pricing_engine.price()` کاملاً category-agnostic و list-aware است — روی `selections.items()` پیمایش می‌کنه و هر `(category, option_key)` رو مستقیم توی `iv_coefficients` جست‌وجو می‌کنه، بدون هیچ if/switch خاصِ نام دسته. یعنی افزودن یه دستهٔ ضریب کاملاً تازه (مثل `replaced`) هیچ تغییری توی `pricing_engine.py`/`scoring_engine.py` لازم نداره — فقط داده (ردیف‌های `iv_coefficients`/`iv_score_weights`). قبل از فکر کردن به «نیاز به تغییر موتور قیمت‌گذاری» برای هر فیچر تازهٔ مبتنی بر دسته، این نکته رو یادت باشه.

### StockLand Score و نتیجه (scoring_engine.py)
امتیاز ۰-۱۰۰: برای هر دسته، `fraction = پرسنت‌انتخابی ÷ بدترین‌پرسنت‌همون‌دسته` (۰ تا ۱) × وزن دسته (`iv_score_weights`) = کسر امتیاز. دستهٔ هفتم `features` (تست امکانات دستگاه — سؤال بله/خیر ساده در ویزارد ربات، نه هفت تست جدا) نصف وزنش کم می‌شه اگه کاربر «خیر» بزنه.
نتیجه (🟢/🟡/🔴): اگه قیمت پیشنهادی فروشنده داده نشده باشه، فقط بر اساس امتیاز؛ اگه داده شده، بر اساس نسبت قیمت پیشنهادی به قیمت منصفانه + امتیاز با هم.

### جدول‌ها (`iphone_valuation/db.py`، همه با الگوی `ensure_schema` + فلگ گارد استاندارد پروژه)
`iv_models` (مدل+سری+`series_id`⚠️از۲۰۲۶-۰۷-۲۶ (پایین‌تر ببین)+`dual_sim_parts`+`esim_only`+`color_pricing`+`part_pricing`)، `iv_storages` (ظرفیت‌های واقعی هر مدل، `model_id`+`label`+`sort_order`+`active`)، `iv_colors`، `iv_parts` (پارت‌های **سراسری** قابل‌مدیریت از پنل، `code` یکتا+`label`+`sort_order`+`active`)، `iv_capacities` (رکورد قیمت واقعی؛ ستون‌های اصلی `storage_id`/`color_id`/`part_id` — نه متن آزاد؛ +قیمت‌پایه+قیمت‌مرجع‌خرید+قیمت‌مرجع‌فروش+نرخ‌ارز‌مرجع+عرضه‌تقاضا — هر ردیف یه ترکیب مدل+ظرفیت+رنگ+پارت)، `iv_coefficients` (دسته+کلید+برچسب+درصد؛ `COEFFICIENT_CATEGORIES` = `condition`,`battery`,`repair`,`registry`,`box`,`cosmetic`,`cable`,`component`,`replaced`)، `iv_score_weights` (وزن هر دسته برای امتیازدهی)، `iv_fx_sources` (منابع نرخ ارز)، `iv_transactions` (تاریخچهٔ معاملات واقعی — فعلاً بدون UI ثبت)، `iv_valuations` (لاگ کامل هر کارشناسی، برای تاریخچه/آمار پنل) — به‌علاوهٔ دو جدول تازهٔ ۲۰۲۶-۰۷-۲۶: `iv_series` (گروه‌بندی نسل/سری مدل‌ها) و `iv_repair_parts` (کاتالوگ مشترک قطعات برای دو دستهٔ موازی `component`/`replaced` — بخش «بازطراحی ویزارد» پایین‌تر).

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
داشبورد+آمار → `/admin/iphone/prices` (همهٔ ثبت/ویرایش/حذف قیمت) → `/admin/iphone/coefficients` (CRUD ضرایب هر دسته + وزن امتیازدهی — ⚠️ از ۲۰۲۶-۰۷-۲۶ دیگه `component`/`replaced` رو نشون نمی‌ده، اون دو رفتن به `/admin/iphone/repairs`) → `/admin/iphone/repairs` (⚠️ تازهٔ ۲۰۲۶-۰۷-۲۶ — «مدیریت تعمیرات»، بخش «بازطراحی ویزارد» پایین‌تر) → `/admin/iphone/series` (⚠️ تازهٔ ۲۰۲۶-۰۷-۲۶ — گروه‌بندی نسل‌ها) → `/admin/iphone/fx` (منابع نرخ ارز + حالت دستی/خودکار + حساسیت + وزن دادهٔ بازار) → `/admin/iphone/history` (لاگ کامل کارشناسی‌ها). فعال/غیرفعال‌سازی کل قابلیت با دکمهٔ توگل در داشبورد، که چیزی جز `set_main_button_enabled("MAIN_BTN_IPHONE_VALUATION", ...)` نیست — همون مکانیزم `MAIN_BUTTON_KEYS` استاندارد پروژه (بخش ۱۶، قانون ۴)، نه مکانیزم جدید. **⚠️ صفحهٔ کامل CRUD مدل‌ها (`/admin/iphone/models`) عمداً حذف شده (۲۰۲۶-۰۷-۲۶) و برنگشته — کاتالوگ مدل/ظرفیت/رنگ فقط از طریق seed اولیه + `/admin/iphone/series` (تخصیص سری) مدیریت می‌شه؛ قبل از بازسازی این صفحه با مالک پروژه هماهنگ کن.**

**`/admin/iphone/prices` — صفحهٔ اصلی مدیریت قیمت:** طبق درخواست صریح «مشابه لیست پیام‌های بخش تیکت» طراحی شده — دو بخش:
1. **فرم فشردهٔ «📝 ثبت قیمت تازه»** بالای صفحه: دراپ‌داون‌های آبشاری مدل→ظرفیت→رنگ→پارت. یه شیء JSON به اسم `IV_MODEL_DATA` (per-model، شامل storages/colors/parts — colors/parts آرایهٔ خالی می‌مونن اگه `color_pricing`/`part_pricing` اون مدل خاموش باشه) توی `<script>` جاسازی شده؛ یه `onchange` روی دراپ‌داون مدل با JS خام (بدون AJAX) بقیهٔ دراپ‌داون‌ها رو پر/مخفی می‌کنه. ارسال به `POST /iphone/prices/upsert`.
2. **لیست تخت همهٔ رکوردهای قیمت** (`ivdb.list_capacities(active_only=False)`، مرتب بر اساس نام مدل بعد `capacity_sort_key`) — دقیقاً همون ساختار HTML/کلاس‌های Tailwind لیست تیکت‌های پروژه (`card overflow-hidden`→`overflow-x-auto`→`table`). ستون‌ها: مدل | ظرفیت | رنگ | پارت | قیمت پایه/خرید/فروش (هر سه اینپوت ویرایش این‌لاین) | تاریخ بروزرسانی | دکمه‌های 💾ذخیره/🗑حذف. چون `<form>` نمی‌تونه دور `<tr>` بپیچه، هر ردیف از تکنیک `form="iv-pe-{id}"`/`form="iv-pd-{id}"` استفاده می‌کنه که به فرم‌های مخفی جدا بعد از `</table>` اشاره می‌کنن (همون الگوی از قبل جاافتادهٔ پروژه). یه اینپوت جست‌وجوی سمت کلاینت (`#iv-price-search`) روی `data-model` هر `<tr>` فیلتر می‌کنه.

`POST /iphone/prices/upsert` **دفاع در عمق** داره: حتی اگه فرم دستکاری بشه و `color_id`/`part_id` بفرسته، سرور دوباره طبق `color_pricing`/`part_pricing` واقعی مدل این مقادیر رو صفر می‌کنه قبل از upsert — دقیقاً همون منطق `resolve_capacity`، تا هیچ‌وقت رکورد یتیمی که هیچ‌وقت استفاده نمی‌شه ساخته نشه. `POST /iphone/prices/{id}/edit` فقط سه فیلد قیمت رو دست می‌زنه؛ `POST /iphone/prices/{id}/delete` رکورد رو کامل پاک می‌کنه (`ivdb.delete_capacity`). همهٔ فیلدهای قیمت `type="text" inputmode="numeric/decimal"` هستن (نه `type="number"` — بخش ۱۷ رو ببین، دلیلش رو).

### ربات (`bot.py`) — موتور مرحله‌ای شرطی (بازطراحی کامل ۲۰۲۶-۰۷-۲۶)

⚠️ **این زیربخش کاملاً بازنویسی شد — نسخهٔ قبلی (زنجیرهٔ هاردکدِ «تابع → صدا زدن مستقیم تابع بعدی» با `_IV_COEFF_STEPS`/`_iv_advance_coeff`/`_iv_resolve_and_advance`) دیگه در کد وجود نداره.** توضیح کامل معماری تازه در «بازطراحی ساختاری ویزارد» (زیربخش بعدی همین بخش ۲۲). خلاصهٔ خیلی کوتاه برای کسی که فقط می‌خواد بدونه از کجا شروع کنه: `handle_iphone_valuation_start` → `_iv_goto(chat_id, uid, "series")`؛ همه‌چیز بعدش از `_IV_STEP_ORDER` + `_iv_step_skip` + `_iv_goto`/`_iv_step_done` تغذیه می‌شه.

**⚠️ نکتهٔ مهم Handler Ordering (بخش ۱۶، قانون ۱۶) — همچنان برقرار:** کالبک‌های ویزارد (پیشوند `ivw_`) هندلر جدای خودشون رو ندارن — چون کدشون بعد از catch-all اصلی (`handle_callbacks`، `func=lambda c: True`) در فایل قرار می‌گیره. به‌جاش، `if data.startswith("ivw_"): return _iv_wizard_callback(call)` **داخل خود catch-all** اضافه شده و منطق واقعی در `_iv_wizard_callback` پیاده‌سازی شده. **هر فیچر بعدی که کالبک این‌لاین نیاز داره و بعد از `handle_callbacks` در فایل قرار می‌گیره، باید همین الگو رو تکرار کنه.**

**نکتهٔ دیپلوی:** دکمه پیش‌فرض فعاله؛ تا سری/مدل/ظرفیت/قیمتی در پنل تعریف نشه، کاربر پیام واضح می‌بینه (بدون کرش) — بهتره بعد دیپلوی سریع چند مدل+قیمت وارد بشه یا موقتاً دکمه از تنظیمات غیرفعال بمونه.

### بازطراحی ساختاری ویزارد (از ۲۰۲۶-۰۷-۲۶) — گروه‌بندی نسل، موتور مرحله‌ای شرطی، تفکیک قطعات

مالک پروژه صریحاً خواست **ساختار** ویزارد بازطراحی بشه (نه منطق قیمت‌گذاری) — حرفه‌ای‌تر، هوشمندتر، UX خلوت‌تر. جزئیات کامل در `CHANGELOG_AI.md` (entry «بازطراحی کامل ویزارد کارشناسی قیمت آیفون»)؛ خلاصهٔ چیزی که برای کار روی این بخش لازمه بدونی:

**۱) گروه‌بندی سری/نسل:** جدول تازهٔ `iv_series` (id, name, sort_order, active) + ستون `iv_models.series_id` (FK نال‌پذیر) — **کاملاً جدا** از ستون قدیمی `iv_models.series` (که فقط سال انتشار متنیه و برای نمایش «(سال)» در `/admin/iphone/prices` استفاده می‌شه، دست‌نخورده مونده). مهاجرت یک‌بارهٔ `_migrate_iv_series_v1` با `_iv_series_for_model_name(name)` (رگولار اکسپرشن روی اسم مدل، الگوی مشابه `_iv_sim_policy` موجود) همهٔ مدل‌های seed‌شده رو به سری‌های منطقی (iPhone SE، iPhone X، iPhone 3 تا iPhone 17، ...) تخصیص داد — بعدش کاملاً از `/admin/iphone/series` قابل‌ویرایش/جابه‌جاست، هیچ قانون هاردکد دائمی نیست. توابع: `list_series`/`create_series`/`update_series`/`delete_series` (soft — مدل‌های وابسته فقط `series_id=NULL` می‌شن، مثل `delete_color`)، + دو کوئری مخصوص ربات `list_bot_visible_series()`/`list_bot_visible_models(series_id)` که فقط سری/مدلی با حداقل یه قیمت فعال نشون می‌دن (بدون گزینهٔ بن‌بست در ویزارد). ویزارد ربات حالا یه مرحلهٔ اول تازه داره: انتخاب سری، بعد فقط مدل‌های همون سری.

**۲) موتور مرحله‌ای شرطی (Conditional Step Engine، `bot.py`):** جایگزین زنجیرهٔ قدیمی. سه جزء کلیدی:
- `_IV_STEP_ORDER` — ترتیب ثابت همهٔ مراحل: `series, model, capacity, color, part, cond, defms, batt, repms, repair, reg, box, cos, cable, feat, stype, price, city, summary`.
- `_iv_step_skip(step_id, state)` — تک‌منبع حقیقت برای «این مرحله باید رد بشه یا نه» (رنگ/پارت بدون داده، دستهٔ ضریب بدون گزینهٔ فعال، `defms` وقتی `condition != cond_needs_repair`). افزودن شرط شرطی تازه = یه branch این‌جا، نه بازنویسی زنجیره.
- `_iv_goto(chat_id, uid, step_id)`/`_iv_step_done(chat_id, uid)` — دو تابع پیمایش عمومی. `_iv_goto` هر مرحلهٔ رد-شونده رو با یه حلقه دور می‌زنه و همین که از فاز انتخاب دستگاه (`_IV_DEVICE_STEPS = {series,model,capacity,color,part}`) خارج بشه، یه‌بار `ivdb.resolve_capacity(...)` رو صدا می‌زنه (`_iv_try_resolve_capacity` — اگه قیمتی برای این ترکیب نبود، همین‌جا با پیام واضح ویزارد رو متوقف می‌کنه، نه بعد از هفت سؤال ضریب).
- `_iv_peek_next(step_id, state)` — نسخهٔ بدون-side-effect حلقهٔ رد-شدن `_iv_goto`، برای تشخیص «مرحلهٔ واقعی بعدی» در `_iv_step_done`. ⚠️ **باگ واقعی که فقط با تست پیدا شد:** اگه `_iv_step_done` به‌جای این تابع، فقط همسایهٔ *ثابتِ* `_IV_STEP_ORDER` رو چک می‌کرد، تشخیص «کی از فاز دستگاه خارج شدیم» (برای صفحهٔ خلاصه/ویرایش، پایین‌تر) روی مدل‌هایی که مرحلهٔ بعدی‌شون (مثلاً `part`) رد می‌شه، اشتباه می‌رفت. برای هر تغییر آینده روی این دو تابع، حتماً با یه هارنس شبیه‌ساز (بدون تلگرام واقعی — `bot.bot.send_message`/`edit_message_text` رو monkey-patch کن، `bot._iv_wizard_callback(fake_call)` رو مستقیم صدا بزن) تست کن، نه فقط با خوندن کد.

**۳) قطعات تعویض‌شده در برابر معیوب — دو بعد مستقل:** جدول کاتالوگ مشترک تازهٔ `iv_repair_parts` (کدها = `option_key` دستهٔ `component`) + دستهٔ تازهٔ `"replaced"` در `COEFFICIENT_CATEGORIES`. برای هر قطعه دو ردیف `iv_coefficients` موازی (`component`=معیوب، `replaced`=تعویض‌شده، درصد پیش‌فرض replaced تقریباً نصف component) + وزن امتیازدهی جدا. دو گزینهٔ قدیمی `repair_screen`/`repair_battery` توی دستهٔ `repair` (که قبلاً جایگزین خام «تعویض‌شده» بودن) soft-deactivate شدن (`_migrate_repair_vs_replaced_v1`) تا با مولتی‌سلکت granular تازه دوبل‌شمارش نشن — `repair` از این به بعد فقط توصیف‌کنندهٔ شدت/تاریخچهٔ سرویسه (باز شدن/تعمیر برد/آب‌خوردگی)، نه قطعهٔ خاص. توی ویزارد، تابع تک قدیمی `_iv_ask_broken_parts` به `_iv_ask_multiselect(chat_id, uid, step_id)` عمومی تعمیم یافت (پارامتری با `_IV_MULTISELECT_STEP_MAP`، یه دیکشنری `{step_id: (category, title)}`) و دو بار استفاده می‌شه: `defms` (فقط وقتی `condition=cond_needs_repair`) و `repms` (همیشه، مستقل از condition — چون قطعهٔ تعویض‌شدهٔ سالم یه سیگنال قیمتی جداست، صرف‌نظر از وضعیت کلی). مکانیزم toggle-and-re-render همون پیام (از قبل موجود در نسخهٔ تک-منظورهٔ قدیمی) کاملاً حفظ شده.

**۴) حذف «سایر» برای رنگ (پارت‌نامبر استثناست):** دکمهٔ `ivw_color_OTHER` حذف شد؛ مرحلهٔ `color` وقتی مدلی صفر رنگ ثبت‌شده داره، از قبل توسط `_iv_step_skip` رد می‌شه (پرسیده نمی‌شه، نه اینکه گزینهٔ «سایر» بده). حافظه از قبل هیچ‌وقت «سایر» نداشت.

**۵) صفحهٔ خلاصه/ویرایش:** مرحلهٔ آخر قبل از `_iv_finalize`. `_iv_ask_summary` همهٔ پاسخ‌ها رو با یه دکمهٔ ✏️ به‌ازای هر بخش (`ivw_edit_{step_id}`) نشون می‌ده. زدن ✏️ یعنی `state["editing"]=step_id` و `_iv_goto(chat_id, uid, step_id)`. ⚠️ از ۲۰۲۶-۰۷-۳۰ منطق «کی برگردیم به خلاصه» دیگه بر اساس همسایگی مرحلهٔ فعلی نیست — `_iv_edit_group_for(root_step)` بر اساس مرحله‌ای که واقعاً کلیک شده (نه مرحلهٔ فعلی وسط cascade) گروه رو تعیین می‌کنه: دستگاه (`series..part`)، تعمیرات (`repair/defms/repms`)، یا `cond` (که خودش گروه بزرگ‌تری تا `repms` داره چون تغییرش می‌تونه کل ارزیابی کیفیت رو باز/بسته کنه) — بقیهٔ مراحل هرکدوم گروه تک‌عضوی خودشونن (پایین‌تر، بخش ۲۲.۷ رو ببین). `ivw_summary_confirm`→`_iv_finalize`، `ivw_summary_cancel`→پاک‌کردن state.

**۶) پنل ادمین:** صفحات تازه زیر همون permission `ai_pricing`: `/admin/iphone/series`، `/admin/iphone/repairs`، و از ۲۰۲۶-۰۷-۳۰ هم `/admin/iphone/colors` (بخش ۲۲.۷). صفحهٔ عمومی `/iphone/coefficients` دیگه `component`/`replaced` رو نشون نمی‌ده (`grade` از ۲۰۲۶-۰۷-۳۰ اضافه شد، بخش ۲۲.۷).

**تصمیم معماری کلیدی که کل بازطراحی رو کم‌ریسک کرد:** `pricing_engine.py`/`scoring_engine.py`/`service.py` **صفر خط تغییر کردن** — چون از قبل کاملاً category-agnostic و list-aware بودن (بالاتر، بخش «فرمول قیمت» رو ببین). دستهٔ تازهٔ `replaced` صرفاً داده‌ست، نه کد تازه در موتور قیمت‌گذاری.

### ۷) سری اصالت دستگاه + رنگ درصدی + بازطراحی دوم پنل/ویزارد (از ۲۰۲۶-۰۷-۳۰)

جزئیات کامل در `CHANGELOG_AI.md` (entry «اصلاحیهٔ بزرگ بخش قیمت‌گذاری آیفون»)؛ خلاصهٔ چیزی که لازمه بدونی:

- **`grade`** — دستهٔ ضریب تازه (مثل `replaced`، صفر تغییر در pricing/scoring_engine): ۷ گزینهٔ ثابت `grade_m/n/f/p/3/4/5` (M=اصلی=۰٪ پیش‌فرض). `ivdb.GRADE_STOP_CALC_KEYS = {grade_p, grade_3, grade_4}` — انتخاب هرکدوم توی ویزارد ربات (`_iv_grade_stop`) محاسبهٔ قیمت رو کلاً متوقف می‌کنه، پیام «قیمت توافقی» مخصوص می‌ده، مستقیم می‌ره سراغ دکمه‌های نهایی.
- **رنگ درصدی** — ستون تازهٔ `iv_colors.price_percent`، اعمال‌شده در `pricing_engine.price()` به‌عنوان یه `contribution` اضافی (تنها نقطه‌ای که مستقیم از `iv_colors` می‌خونه، نه `iv_coefficients` عمومی، چون رنگ per-model هست نه سراسری). ⚠️ **این جایگزین مکانیزم قدیمی «ردیف قیمت اختصاصی هر رنگ» (`iv_capacities.color_id`) نیست — کاملاً موازی و اضافیه**، چون دادهٔ تولید ممکنه از قبل قیمت دقیق جداگانه به‌ازای رنگ داشته باشه (`_migrate_pricing_toggles_v1` قدیمی دقیقاً برای همین سناریو نوشته شده بود). مدیریت از `/admin/iphone/colors` (صفحهٔ تازه — همون‌جا هم می‌شه اسم پیش‌فرض رنگ رو به معادل بازار ایران تغییر داد، مثلاً «نور ستاره‌ای»→«سفید»؛ تا این نشست هیچ UI ای برای rename/ویرایش رنگ وجود نداشت، فقط seed اولیه).
- **موتور مرحله‌ای ربات** (`_IV_STEP_ORDER` و بقیهٔ اجزای بخش ۲۲.۲ بالا) دست‌نخورده مونده، فقط ترتیب/شرط‌ها عوض شدن: `grade` بعد از `part`؛ «نو»+«پلمپ» ادغام به `cond_new_sealed` (short-circuit مستقیم به `reg`)؛ مسیر تعمیرات حالا وابسته به `features_ok` (نه `condition` مستقیم) — `repair` فقط اگه `features_ok=False`؛ جواب `repair_none`→`defms`، `repair_opened`/`repair_board`→`repms`، `repair_water`→هیچ‌کدوم. سؤال‌های «قیمت پیشنهادی»/«فروشگاه یا شخصی» کامل حذف شدن.
- **`_iv_active_selections(state)`** (تازه) — قبل از `_iv_finalize`، `selections` رو فقط به دسته‌های واقعاً غیر-رد-شونده فیلتر می‌کنه؛ بدونش، ویرایش یه پاسخ بالادستی (مثلاً «امکانات» از خیر به بله) جواب‌های قدیمیِ مراحل حالا-مخفی رو توی state باقی می‌ذاشت و بی‌جا روی قیمت اثر می‌ذاشت — این باگ فقط با تست مستقیم پیدا شد، نه با خوندن کد.
- **بعد از نتیجهٔ نهایی** (چه محاسبه‌شده چه توقف‌محاسبهٔ P/۳/۴)، state به یه حالت سبک `iv_post_result` می‌ره (نه پاک‌شدن کامل) با ۳ دکمه: «🤝 می‌خوام بفروشم» (جدول تازهٔ `iv_sell_requests` + پیام به `ADMIN_ID`؛ مدیریت از پنل توی `/admin/receipts` زیر لیست کارت‌به‌کارت، `_iv_sell_requests_section_html`)، «💾 ذخیره» (فقط تأیید — از قبل توی `iv_valuations` ذخیره می‌شه)، «🔗 اشتراک‌گذاری» (لینک `t.me/share/url`).
- برندینگ «StockLand»→«استوک‌لند» همه‌جا (پیام نهایی، `report.py`, `pricing_engine.py` labels، پنل)؛ لیبل‌های فرم نهایی هم عوض شدن («ارزش فروش کالا»/«قیمت منصفانه کالا»/«قیمت خرید فروشگاه از شما»، بدون خط «پیشنهاد فروش فروشگاه»).
- **⚠️ باقی‌مانده، فاز بعد:** اتصال AI به کارشناسی (provider abstraction + کلید رمزنگاری‌شده + دکمهٔ «تحلیل با AI» + JSON contract + لاگ مدیریتی) — مشخصات کامل از مالک پروژه گرفته شده ولی پیاده‌سازی نشده، عمداً به‌عنوان یک فاز افزونه‌ای جدا موکول شد.

**۸) سری اصالت به‌عنوان بعد سوم ردیف قیمت دقیق (دور دوم همون روز، ۲۰۲۶-۰۷-۳۰):** مالک پروژه بعد از تأیید توگل رنگ/پارت خواست `grade` هم دقیقاً همون رفتار رو داشته باشه — نه فقط دستهٔ ضریب درصدی سراسری (بالا، بند ۱)، بلکه یه بعد سوم مستقل روی خود ردیف قیمت (مثل رنگ/پارت). `iv_models.grade_pricing` + `iv_capacities.grade_id` اضافه شد (همون الگوی `color_pricing`/`part_pricing`)؛ `resolve_capacity` از fallback هاردکد دوبعدی (پارت×رنگ) به یه الگوریتم عمومی Cartesian-product روی هر تعداد بعد (حالا ۳تا) بازنویسی شد — مرتب‌شده بر اساس «تعداد `None` کمتر = دقیق‌تر». `/admin/iphone/prices` دراپ‌داون grade کنار رنگ + توگل «🏷 اثر سری اصالت روی قیمت این مدل» گرفت (`POST /iphone/prices/grade-pricing`، دقیقاً الگوی رنگ/پارت). در `bot.py`، چون `grade` یه مرحلهٔ *بعد* از فاز دستگاهه ولی می‌تونه ردیف قیمت رو عوض کنه، `_IV_PRE_RESOLVE_STEPS = _IV_DEVICE_STEPS | {"grade"}` جایگزین چک قبلی شد تا resolve تا بعد جواب grade صبر کنه. برچسب‌های نهایی هفت‌گانه دقیق شدن (`grade_m`="سری اصلی M" ... `grade_5`="سری 5 اپل بدون گارانتی") — **ارقام ۳/۴/۵ باید لاتین بمونن**؛ چون این پچ سراسری اعداد فارسی فقط روی `text`/`caption` اثر می‌ذاره نه `reply_markup`، دکمه‌های این‌لاین خودشون همیشه امن بودن، فقط خط grade توی صفحهٔ خلاصه با `<code>` دور رقم‌ها محافظت شد. جزئیات کامل: `CHANGELOG_AI.md` entry «سری اصالت به‌عنوان بعد سوم ردیف قیمت دقیق».

### ۹) کارشناس مکمل هوش مصنوعی (از ۲۰۲۶-۰۷-۳۰) — پکیج `iphone_valuation/ai_advisor.py` + `ai_providers/`

آیتم ۷ (که تا این نشست موکول شده بود) پیاده‌سازی شد. نکتهٔ کلیدی معماری: AI **جایگزین** موتور دیتامحور (`pricing_engine.price()`) نیست — همیشه اول موتور اجرا و مرجع می‌مونه؛ AI فقط (اگه فعال باشه) یه تعدیل محدود روی `fair_price` پیشنهاد می‌ده + توضیح/هشدار. اگه `IV_AI_ENABLED` خاموش باشه، سیستم قیمت‌گذاری دستی دقیقاً همون رفتار قبلی رو داره — صفر تغییر مسیر.

- **نقطهٔ ورود:** `ai_advisor.analyze(payload, model, capacity, price_result, score_result, verdict, valuation_id)` — فقط از `iphone_valuation/service.py:valuate()` صدا زده می‌شه (بعد از محاسبهٔ قطعی موتور)، تا هم ربات هم API آیندهٔ مینی‌اپ بدون تکرار کد ازش بهره‌مند بشن. خروجی روی `result["ai"]` سوار می‌شه (`None` اگه غیرفعال/خطا).
- **کلید طراحی — clamp همیشه سمت سرور، نه سمت مدل:** درخواست صریح مالک پروژه بود که بازهٔ مجاز تعدیل ثابت ±۵٪ نباشه — `IV_AI_MAX_ADJUST_PCT` از پنل قابل تنظیمه (پیش‌فرض ۵، می‌تونه تا هر عددی بره، مثلاً ۲۰). مهم‌تر: حتی اگه مدل یه عدد بیرون بازه برگردونه (چون سیستم‌پرامپت رو رعایت نکرده)، `ai_advisor.analyze()` دوباره با `max(-max_adjust, min(max_adjust, ...))` clamp می‌کنه — هیچ‌وقت به عدد خام مدل اعتماد کور نمی‌شه.
- **گیت اطمینان:** `IV_AI_MIN_CONFIDENCE` (پیش‌فرض ۶۰). اگه `confidence` زیر این آستانه باشه، `adjustment_percent` به‌زور صفر می‌شه (یعنی `final_price == fair_price` موتور) — ولی `reason`/`warnings` مدل همچنان توی پیام نهایی نشون داده می‌شن، چون طبق درخواست صریح «این ارزش واقعی AI است» حتی وقتی قیمت رو عوض نمی‌کنه.
- **Context کامل، نه فقط خروجی موتور:** `_build_context()` در `ai_advisor.py` نرخ ارز+منبع، تاریخ/ساعت، مدل/ظرفیت/رنگ/پارت‌نامبر، همهٔ انتخاب‌های ویزارد (باتری/تعویض‌قطعات/قطعات‌معیوب/تعمیرات/رجیستری/جعبه/ظاهر/کابل/سری‌اصالت، با برچسب فارسی خوانا نه فقط `option_key` خام)، کل خروجی `pricing_engine.price()` (contributions، fx_pct، market_pct، demand_pct، condition_pct)، و تاریخچهٔ قیمت (`ivdb.recent_valuations_for_capacity` + `ivdb.market_data_avg_delta_pct` برای تشخیص روند صعودی/نزولی/ثابت) رو می‌سازه. مدل مأموره اگه داده‌ها ناهماهنگ بودن (مثلاً باتری ضعیف ولی قیمت مثل نو) توی `warnings` صریح بگه.
- **خروجی ساختاریافته (نه فقط عدد):** provider باید `{final_price, confidence, adjustment_percent, reason, market_trend, risk, recommended_buy_price, recommended_sell_price, warnings}` برگردونه — با `output_config.format` (JSON Schema، نه prefill) از Claude API گرفته می‌شه.
- **provider abstraction:** `iphone_valuation/ai_providers/base.py` قرارداد رو مستند می‌کنه (تابع `analyze(context, api_key, model) -> dict`، خطا = `AIProviderError`)؛ `ai_providers/__init__.py` یه رجیستری سادهٔ `AI_PROVIDERS = {"claude": claude_provider}` نگه می‌داره. طبق تصمیم صریح مالک پروژه، فعلاً فقط `claude_provider.py` (SDK رسمی `anthropic`، مدل پیش‌فرض `claude-opus-5`، `thinking` عمداً `disabled` چون این یه استخراج ساختاریافتهٔ محدوده نه استدلال عمیق و کاربر تلگرام منتظر پاسخ سریعه) پیاده‌سازی شده — بقیه (OpenAI/Gemini/OpenRouter/DeepSeek) فقط با افزودن یه فایل مشابه + یه خط توی رجیستری اضافه می‌شن، بدون تغییر `ai_advisor.py`.
- **رمزنگاری کلید API:** `iphone_valuation/ai_crypto.py` (Fernet از پکیج `cryptography`) با کلید مشتق‌شده از env var اختصاصی `IV_AI_ENC_KEY` (نه `SESSION_SECRET` — اون یکی از قبل پیش‌فرض هاردکد ضعیف داره، بخش ۱۳). **Fail closed:** بدون `IV_AI_ENC_KEY` روی سرور، نه رمزنگاری کلید ممکنه نه اصلاً توگل فعال‌سازی AI از پنل قابل روشن‌شدنه (`admin_panel.iphone_ai_toggle`/`iphone_ai_api_key` هر دو چک می‌کنن).
- **لاگ کامل برای ممیزی:** هر فراخوانی (موفق یا ناموفق) توی جدول تازهٔ `iv_ai_analyses` (`iphone_valuation/db.py`) ثبت می‌شه — `request_context`/`response_json`/`adjustment_percent`/`confidence`/`warnings`/`error`، با `valuation_id` وصل به `iv_valuations`. پنل `/admin/iphone/ai` این لاگ رو نشون می‌ده.
- **پنل ادمین `/admin/iphone/ai`** (permission `ai_pricing`، بدون permission تازه): توگل روشن/خاموش، انتخاب provider (دراپ‌داون از `AI_PROVIDERS.keys()`)، فیلد مدل، فیلد بازهٔ مجاز تعدیل، فیلد آستانهٔ اطمینان، فرم کلید API (`type="password"`, فقط نوشتنی — مقدار رمزگشایی‌شده هیچ‌وقت به HTML برنمی‌گرده، فقط وضعیت «ثبت شده/نشده»)، و جدول لاگ.
- **ربات:** `bot.py:_iv_finalize` بعد از نمایش نتیجهٔ دیتامحور، اگه `result["ai"]` غیر-`None` باشه، یه بلوک اضافه با «🤖 تحلیل هوش مصنوعی» (قیمت اصلاح‌شده، روند بازار، ریسک، دلیل، هشدارها) زیر همون پیام اضافه می‌کنه — پیام دیتامحور بالا هیچ تغییری نمی‌کنه.
- **تست انجام‌شده:** هارنس مستقیم `ai_advisor.analyze()` با provider جعلی (۶ سناریو: غیرفعال، بدون کلید، حالت عادی، clamp روی مقدار بیرون‌بازه، گیت اطمینان زیر آستانه، خطای provider)، تست end-to-end `service.valuate()` (هم حالت خاموش هم روشن)، رندر پیام نهایی ربات با `_iv_finalize` (مانیتور مستقیم `bot.send_message` جعلی)، و همهٔ روت‌های پنل (`/admin/iphone/ai` GET/toggle/settings/api-key/api-key/clear، شامل تست fail-closed وقتی `IV_AI_ENC_KEY` ست نشده).

### ۱۰) چند-Provider (از ۲۰۲۶-۰۷-۳۰، دور دوم همون روز) — OpenAI/Gemini/OpenRouter/DeepSeek

طبق درخواست صریح مالک پروژه («امکان استفاده سایر هوش مصنوعی‌ها هم اضافه کن»)، ۴ provider دیگه به `iphone_valuation/ai_providers/` اضافه شد — همه از همون قرارداد `base.py` (`analyze(context, api_key, model) -> dict`) پیروی می‌کنن، بدون هیچ تغییری در `ai_advisor.py`:

- **`SCHEMA`/`SYSTEM_PROMPT` مشترک** از `claude_provider.py` به خودِ `base.py` منتقل شد (یک منبع حقیقت، نه تکرار در هر provider) — رفتار خروجی مستقل از provider انتخابی یکسان می‌مونه.
- **`_openai_compat.py`** (ماژول خصوصی، خودش provider ثبت‌شده نیست) — منطق مشترک سه provider سازگار با OpenAI Chat Completions API (`response_format={"type":"json_object"}`): `openai_provider.py` (پکیج `openai`، بدون `base_url`، پیش‌فرض `gpt-4o`)، `openrouter_provider.py` (`base_url="https://openrouter.ai/api/v1"`، پیش‌فرض `openai/gpt-4o`)، `deepseek_provider.py` (`base_url="https://api.deepseek.com"`، پیش‌فرض `deepseek-chat`).
- **`gemini_provider.py`** — پکیج **`google-genai`** (نه `google-generativeai` قدیمی که در حین توسعه معلوم شد رسماً deprecated شده و دیگه بروزرسانی نمی‌گیره؛ تعویض شد قبل از merge). از `response_json_schema` (نه فقط `response_mime_type`) استفاده می‌کنه — یعنی خروجی Gemini هم مثل Claude با یه JSON Schema واقعی محدود می‌شه، نه فقط با پرامپت.
- **import لeazی درون خودِ `analyze()`** (نه سطح ماژول) در همهٔ ۵ provider — یعنی نصب‌نبودن SDK یه provider (مثلاً `google-genai` روی سروری که فقط Claude استفاده می‌کنه) باعث شکست `import` کل پکیج `ai_providers` نمی‌شه؛ فقط همون provider خاص موقع صدازدن `AIProviderError` برمی‌گردونه (تست شده مستقیم).
- **`PROVIDER_LABELS`** (دیکشنری تازه در `__init__.py`) — برچسب نمایشی خواناتر برای دراپ‌داون پنل (`Claude (Anthropic)`, `OpenAI (ChatGPT)`, `Google Gemini`, `OpenRouter`, `DeepSeek`) به‌جای `.capitalize()` خام.
- **مدل پیش‌فرض دیگه سراسری نیست:** `ai_advisor.py` و روت‌های پنل دیگه fallback هاردکد `"claude-opus-5"` رو به فیلد خالی `IV_AI_MODEL` تحمیل نمی‌کنن — خالی‌بودن یعنی هر provider از پیش‌فرض خودش استفاده کنه (`model or default_model` داخل خودِ هر provider)، چون یه پیش‌فرض ثابت وابسته به Claude برای بقیه provider ها بی‌معنی بود.
- **`requirements.txt`:** `openai>=1.30,<2` و `google-genai>=0.3,<1` اضافه شد.
- **تست انجام‌شده:** هر ۵ provider مستقیم با client جعلی (نه API واقعی) — بررسی صحت پارامترهای ارسالی (`response_format`/`base_url`/`response_json_schema`/`system_instruction`) و parse صحیح خروجی؛ تست fail-safe نصب‌نبودن SDK.

### ۱۱) بازطراحی UX صفحات مدیریت آیفون — «یک دکمهٔ ذخیره» به‌جای دکمهٔ جداگانه هر ردیف (از ۲۰۲۶-۰۷-۳۰)

مالک پروژه گزارش داد داشتن یک دکمهٔ «ذخیره» جداگانه روی هر ردیف (هر رنگ، هر قطعهٔ تعمیر، هر ضریب، هر منبع نرخ ارز، هر سری) خستگی‌آوره. پنج صفحه بازطراحی شدن — همه با یک الگوی یکسان: **تمام ردیف‌های قابل‌ویرایش داخل یک `<form>` واحد**، فیلدهای هر ردیف با نام‌گذاری `{field}_{id}` (نه `Form(...)` استاتیک، چون تعداد ردیف پویاست — روت با `await request.form()` خام پردازش می‌شه)، و **یک دکمهٔ «💾 ذخیرهٔ همهٔ تغییرات» فقط یک‌بار پایین صفحه**. دکمه‌های حذف (destructive، باید فوری بمونن) با همون الگوی قدیمی «فرم مخفی + `form="id"` روی دکمه» جدا می‌مونن — چون `<form>` تو در تو در HTML معتبر نیست، این تکنیک (که از قبل توی پروژه برای صفحهٔ قیمت‌ها جاافتاده بود) رعایت شد.

| صفحه | روت جدید bulk-save | روت‌های حذف‌شده |
|---|---|---|
| `/admin/iphone/series` | `POST /iphone/series/bulk-save` | `{sid}/edit`, `series/assign` |
| `/admin/iphone/repairs` | `POST /iphone/repairs/bulk-save` | `{pid}/edit` (+ وزن‌های component/replaced از `/iphone/weights/save` مشترک جدا شدن، حالا بخشی از همین بولک‌سیو) |
| `/admin/iphone/colors` | `POST /iphone/colors/bulk-save` | `{cid}/edit` |
| `/admin/iphone/coefficients` | `POST /iphone/coefficients/bulk-save` | `{cid}/edit` + `/iphone/weights/save` (کاملاً حذف شد، چون فقط از دو صفحهٔ بالا صدا زده می‌شد) |
| `/admin/iphone/fx` | `POST /iphone/fx/bulk-save` | `{sid}/edit` |

استثناها که عمداً دست‌نخورده موندن: فرم‌های «افزودن آیتم تازه» (create یه اکشن جداست)، دکمه‌های حذف (destructive، فوری)، دکمهٔ «تست فچ» در صفحهٔ fx (فقط fetch زندهٔ نمایشی، چیزی رو persist نمی‌کنه)، و فرم تنظیمات نرخ ارز در همون صفحه (از قبل هم صفحه‌ای/تک‌دکمه بود، نه per-row).

**دکمهٔ بازگشت یکسان‌سازی شد:** همون `<a href="/admin/iphone" class="text-indigo-600 text-sm mb-4 inline-block">← بازگشت به کارشناسی آیفون</a>` (الگوی از قبل موجود در صفحات prices/colors/ai) به صفحات series، repairs، coefficients، fx، و history هم اضافه شد — الان همهٔ ۸ زیرصفحهٔ `/admin/iphone/*` این لینک رو دارن (فقط داشبورد اصلی `/admin/iphone` که خودش صفحهٔ ریشه‌ست، نداره).

**تست انجام‌شده:** رندر مستقیم هر ۵ صفحه (بررسی وجود دکمهٔ ذخیرهٔ واحد + نبود دکمه‌های جداگانهٔ قدیمی)، فراخوانی مستقیم هر ۵ روت bulk-save با دادهٔ چندردیفی و تأیید ذخیرهٔ صحیح همهٔ فیلدها، و تأیید سالم‌ماندن روت‌های add/delete (بدون تغییر رفتار).

### ۱۲) چند‌انتخابی رنگ/سری اصالت در ثبت قیمت + فیلتر سری‌های توقف‌محاسبه + ظرفیت به‌عنوان بعد اختیاری (از ۲۰۲۶-۰۷-۳۰، دور سوم)

سه اصلاحیهٔ مرتبط با فرم «📝 ثبت قیمت تازه» در `/admin/iphone/prices` (`admin_panel.py`)، طبق درخواست صریح مالک پروژه:

- **چند‌انتخابی رنگ و سری اصالت:** دراپ‌داون تک‌تایی قدیمی رنگ/سری اصالت با چک‌باکس چندتایی (`color_ids[]`/`grade_ids[]`) جایگزین شد. روت `POST /iphone/prices/upsert` دیگه پارامترهای Form استاتیک نداره (چون تعداد چک‌باکس‌ها پویاست) — از `await request.form()` خام با `getlist()` استفاده می‌کنه، دقیقاً الگوی صفحات bulk-save (بخش ۲۲.۱۱). روی **کارتزین رنگ×سری اصالت انتخابی** حلقه می‌زنه و به‌ازای هر ترکیب یک `ivdb.upsert_capacity(...)` صدا می‌زنه — یعنی «۱۳ نرمال، همهٔ رنگ‌ها یک قیمت، فقط آبی جدا» با یک بار ثبت (بدون تیک زدن آبی) + یک ثبت جدا برای آبی ممکنه، بدون تغییر در `resolve_capacity`/`pricing_engine` (چون هر ترکیب صرفاً یک ردیف `iv_capacities` عادیه، دقیقاً مثل قبل). خالی‌بودن هر دو چک‌باکس‌گروه یعنی `[None]` (ردیف عمومی)، دقیقاً مثل رفتار قبلی دراپ‌داون خالی.
- **فیلتر سری‌های توقف‌محاسبه از چک‌باکس:** `grade_p`/`grade_3`/`grade_4` (`ivdb.GRADE_STOP_CALC_KEYS`، بخش ۲۲.۷) دیگه اصلاً توی این فرم نشون داده نمی‌شن — چون این سه مسیر محاسبهٔ کاملاً جدا دارن (توقف قیمت‌گذاری، پیام «توافقی»)، تعریف ردیف قیمت دقیق براشون بی‌معنیه. فیلتر هم توی `iphone_prices_page` (لیست گزینه‌ها) هم توی `iphone_prices_edit_page` (با یک استثنا: اگه رکورد از قبل با یکی از این سه ثبت شده، همچنان توی گزینه‌های همون رکورد می‌مونه که ادمین گیر نکنه) اعمال شده، به‌علاوهٔ دفاع در عمق سمت سرور در `iphone_prices_upsert` (حتی اگه فرم دستکاری بشه و id یکی از این سه رو بفرسته، سرور دوباره فیلترش می‌کنه).
- **ظرفیت/حافظه به‌عنوان بعد چهارم اختیاری قیمت:** دقیقاً همون الگوی توگل رنگ/پارت/سری اصالت (`iv_models.color_pricing`/`part_pricing`/`grade_pricing`) برای ظرفیت هم تکرار شد — ستون تازهٔ `iv_models.capacity_pricing`، **با تفاوت کلیدی نسبت به سه توگل قبلی: پیش‌فرضش روشنه (۱)**، نه خاموش — چون معمولاً ظرفیت واقعاً روی قیمت اثر داره؛ بی‌اثر بودنش (مدل‌های خیلی قدیمی/ارزون که یه قیمت برای همهٔ ظرفیت‌هاشون کافیه) استثناست، نه قاعده. `iv_capacities.storage_id` از قبل نال‌پذیر بود (نیازی به تغییر schema نداشت، فقط `get_capacity_exact` که تا این نشست `storage_id=?` (تطبیق دقیق، با NULL همیشه false) به‌جای `storage_id IS ?` (NULL-safe) استفاده می‌کرد اصلاح شد — وگرنه هر upsert روی مدلی با ظرفیت خاموش، به‌جای آپدیت ردیف عمومی موجود، هر بار یه ردیف تکراری تازه می‌ساخت). `resolve_capacity()` از fallback سه‌بعدی (پارت×رنگ×سری اصالت) به **چهاربعدی** (+ظرفیت) بازنویسی شد — همون الگوریتم Cartesian-product موجود، فقط یه بعد اضافه؛ وقتی `capacity_pricing` خاموشه، `storage_id` قبل از جست‌وجو به `None` صفر می‌شه (دقیقاً مثل رفتار رنگ/پارت/سری اصالت)، یعنی صرف‌نظر از ظرفیتی که کاربر توی ویزارد انتخاب کرده، قیمت از ردیف عمومی (بدون ظرفیت خاص) خونده می‌شه. **سؤال ظرفیت در ویزارد ربات دست‌نخورده موند و همیشه پرسیده می‌شه** (برای شناسایی دستگاه) — فقط *محاسبهٔ قیمت* هست که طبق این توگل ممکنه ظرفیت رو نادیده بگیره؛ `bot.py` هیچ تغییری نخواست چون از قبل `resolve_capacity()` رو به‌صورت generic صدا می‌زنه (بخش ۲۲.۷). در فرم پنل، دراپ‌داون ظرفیت وقتی توگل خاموشه کلاً مخفی/غیرالزامی می‌شه (شبیه رفتار مخفی‌شدن رنگ/پارت/سری اصالت وقتی خاموشن، فقط پیش‌فرض معکوس).
- **تصمیم عمدی خارج از scope این دور:** ظرفیت **چند‌انتخابی نشد** (برخلاف رنگ/سری اصالت) — درخواست صریح مالک پروژه فقط «همون کاری که برای رنگ/سری کردی» یعنی الگوی توگل‌پذیر/اختیاری بود، نه چک‌باکس چندتایی؛ چون معنای «چند ظرفیت با هم یک قیمت» با toggle خاموش از قبل پوشش داده می‌شه (هر ظرفیتی، یک قیمت مشترک)، نیازی به چک‌باکس جدا نبود.
- **تست انجام‌شده:** هارنس مستقیم (نه از طریق تلگرام/HTTP واقعی) روی `iphone_prices_upsert` با چک‌باکس چندتایی رنگ×سری (تأیید تعداد صحیح ردیف = حاصل‌ضرب انتخاب‌ها، idempotency روی ارسال دوباره، ردیف عمومی وقتی هیچ‌کدوم تیک نخورده)، تست دفاع در عمق سری توقف‌محاسبه (id تزریق‌شده هیچ‌وقت ذخیره نمی‌شه)، و مجموعه‌ای جدا برای ظرفیت: توگل روشن پیش‌فرض، resolve دقیق وقتی روشنه (ظرفیت بدون قیمت ثبت‌شده = None، نه fallback اشتباه)، resolve مشترک وقتی خاموشه (دو ظرفیت متفاوت به یک ردیف قیمت می‌رسن)، برگشت به رفتار دقیق بعد از روشن‌کردن دوباره (بدون از دست رفتن دادهٔ قدیمی)، و دفاع در عمق سمت سرور (فرم دستکاری‌شده که سعی می‌کنه storage_id رو وقتی توگل خاموشه تزریق کنه، نادیده گرفته می‌شه). رندر هر دو صفحهٔ `/admin/iphone/prices` و صفحهٔ ادیت هم مستقیم بررسی شد (وجود عناصر تازه، نبود دراپ‌داون‌های قدیمی تک‌تایی).

### ۱۳) چند‌انتخابی پارت + یکی‌سازی ادیت با فرم ثبت + جلوگیری از تعریف تکراری (از ۲۰۲۶-۰۷-۳۰، دور چهارم)

سه اصلاحیهٔ دیگه روی همون صفحهٔ `/admin/iphone/prices`، طبق درخواست صریح مالک پروژه:

- **چند‌انتخابی پارت:** دراپ‌داون تک‌تایی `part_id` هم مثل رنگ/سری اصالت به چک‌باکس چندتایی (`part_ids[]`) تبدیل شد — مثلاً ZA/A و CH/A با هم قابل انتخاب برای یک قیمت مشترک. `iphone_prices_upsert` حالا روی **کارتزین کامل سه بعد** (پارت×رنگ×سری اصالت) حلقه می‌زنه، نه فقط رنگ×سری.
- **حذف کامل «صفحهٔ ادیت» جدا:** روت‌های `GET /iphone/prices/{cid}/edit-page` و `POST /iphone/prices/{cid}/edit` کاملاً حذف شدن. دکمهٔ «✏️ ادیت» حالا به `/admin/iphone/prices?edit={cid}#iv-p-editform` می‌ره — همون فرم «ثبت قیمت تازه» بالای صفحه با query param `edit` باز می‌شه؛ `iphone_prices_page` رکورد رو می‌خونه (`ivdb.get_capacity`) و از طریق یه متغیر JS تازه (`IV_EDIT_CAP`) به فرم پاس می‌ده. جاوااسکریپت مدل رو انتخاب می‌کنه (رویداد `change` رو دستی صدا می‌زنه تا ظرفیت/رنگ/پارت/سری بسازه)، بعد چک‌باکس‌های دقیق همون ردیف رو تیک می‌زنه، قیمت‌ها رو پر می‌کنه، یه بنر زرد «در حال ویرایش» نشون می‌ده، و فرم رو با `scrollIntoView` جلوی چشم ادمین می‌بره — دقیقاً همون تجربهٔ زمان تعریف اولیه، با همون قابلیت چند‌انتخابی (یعنی ادمین می‌تونه هنگام ادیت هم رنگ/پارت/سری بیشتری اضافه کنه، نه فقط قیمت رو عوض کنه).
- **جلوگیری از تعریف تکراری:** رفتار قدیمی upsert («همیشه بی‌صدا آپدیت کن») برای فرم چند‌انتخابی به یه رفتار محافظه‌کارانه‌تر تغییر کرد — قبل از ساخت هر ترکیب (پارت×رنگ×سری)، `ivdb.get_capacity_exact(...)` چک می‌شه: اگه از قبل یه ردیف *دیگه* (نه ردیفی که با `edit_cap_id` مشخصاً داریم ویرایشش می‌کنیم) دقیقاً همون ترکیب رو داره، اون ترکیب **رد می‌شه** (نه upsert)، و در پیام نهایی («⚠️ N ترکیب قبلاً ثبت شده بود و رد شد: …») به ادمین گزارش می‌شه. اگه ادمین واقعاً بخواد قیمت یه ترکیب موجود رو عوض کنه، باید از دکمهٔ ✏️ همون ردیف وارد بشه (که `edit_cap_id` رو ست می‌کنه و دقیقاً همون یه ترکیب رو مجاز به آپدیت می‌کنه، بقیهٔ ترکیب‌های تکراری همچنان رد می‌شن). سمت کلاینت هم یه کمک بصری اضافه شد: تابع JS `recomputeDuplicates()` با دادهٔ `existing_combos` (لیست ترکیب‌های موجود، جاسازی‌شده در `IV_MODEL_DATA` هر مدل) هر چک‌باکسی که با *اولین گزینهٔ تیک‌خوردهٔ دو بعد دیگه* دقیقاً یه ترکیب تکراری بسازه رو خاکستری/خط‌خورده و غیرقابل‌تیک می‌کنه (⚠️ این فقط یه راهنمای کلاینتیه، نه بلاک واقعی — برای حالت رایج «یه پارت/سری ثابت + چند رنگ متغیر» دقیقه، برای ترکیب‌های خیلی چندبعدی‌تر فقط تقریبیه؛ بلاک قطعی همیشه سمت سرور اتفاق می‌افته). چک‌باکس‌های از قبل تیک‌خورده (مثلاً موقع پیش‌پرشدن حالت ادیت) هیچ‌وقت غیرفعال نمی‌شن.
- **تست انجام‌شده:** هارنس مستقیم — ثبت چندپارت×چندرنگ×یه‌سری (تأیید تعداد ردیف = حاصل‌ضرب کامل سه بعد)، ارسال ترکیب هم‌پوشان با یه رنگ تازه (تأیید فقط ترکیب تازه ذخیره می‌شه، پیام حاوی گزارش رد‌شدن)، ادیت دقیقاً همون ترکیب با `edit_cap_id` (تأیید آپدیت قیمت به‌جای رد‌شدن/ساخت ردیف تازه)، و رندر مستقیم صفحه هم بدون `edit` هم با `edit={id}` (وجود `IV_EDIT_CAP` درست، نبود دراپ‌داون تک‌تایی پارت قدیمی، نبود مسیر `edit-page`).

### ۱۴) بازنویسی لیبل «ارزش فروش کالا» → «ارزش نسخهٔ اصلی» (از ۲۰۲۶-۰۸-۰۲)

مالک پروژه گزارش داد گاهی فاصلهٔ زیادی بین «ارزش فروش کالا» (اولین عدد نتیجهٔ نهایی، مثلاً ۱۸ میلیون) و «قیمت منصفانه کالا» (عدد واقعی متناسب با شرایط دستگاه کاربر، مثلاً ۱۰ میلیون) می‌افته و کاربر رو گیج می‌کنه. علت فنی: `market_price` (`pricing_engine.py`) عمداً فقط عوامل کلان بازار (نرخ ارز/دادهٔ بازار/عرضه‌تقاضا) رو حساب می‌کنه، بدون احتساب ضرایب شرایط خودِ دستگاه — یعنی همیشه معادل `base_price` خامه، مستقل از باتری/ظاهر/قطعات واقعی دستگاه کاربر.

**تأیید فنی برداشت مالک پروژه:** بررسی دقیق `iv_coefficients` نشون داد دقیقاً همون گزینه‌هایی که روشون صفر درصد تعریف شده («بدون افت») منطبقن با «در حد نو» (`condition`)، «باتری ۹۵ تا ۱۰۰٪» (`battery`)، و «سری اصلی» (`grade`) — یعنی `base_price` واقعاً معادل دقیق یه دستگاه در حد آک با باتری سالم و قطعات اصلیه، پس لیبل پیشنهادی («ارزش نسخهٔ اصلی، آک، باتری ۹۵ تا ۱۰۰٪») از نظر داده‌ای هم دقیقاً درسته، نه فقط یه رفع سردرگمی سطحی.

رفع: در `bot.py:_iv_finalize` (پیام نهایی ویزارد)، لیبل به «💵 ارزش نسخهٔ اصلی (در حد آک، باتری ۱۰۰٪)» تغییر کرد (نسخهٔ نهایی متن، بعد از یک اصلاح ظریف بعدی — مالک پروژه ترجیح داد «۱۰۰٪» ساده بگه، نه بازهٔ «۹۵ تا ۱۰۰٪» فنی) — این عدد رو به‌عنوان یه مرجع/بنچمارک معرفی می‌کنه، نه پیشنهاد قیمت واقعی دستگاه کاربر. خط بعدی هم برای کنتراست بیشتر به «⚖️ قیمت منصفانه با شرایط دستگاه شما» اصلاح شد. فقط تغییر متن نمایشی — `pricing_engine.py`/`market_price` (نام فیلد داخلی/دیتابیس) و منطق قیمت‌گذاری صفر خط تغییر کرد، عمداً (این لیبل فقط همین یک‌جا در `bot.py` استفاده می‌شه؛ نه در `/admin/iphone/*` نه در `report.py`).

### ۱۵) بازطراحی چیدمان پیام نهایی — «منبع استعلام قیمت» به‌جای لیست تنزلی قیمت‌ها (دور بعد، همون روز)

مالک پروژه هدف بزرگ‌تری برای این بخش مطرح کرد: می‌خواد کل خروجی کارشناسی حس یک «منبع استعلام قیمت آیفون» هیجان‌انگیز بده، نه چیزی که کاربر حس کنه طراحی شده تا گوشیش رو ارزون بخره (مشکل اصلی: سه قیمت پشت سر هم با فاصلهٔ زیاد، مثل تنزل تدریجی از یه عدد بزرگ به یه عدد کوچیک می‌خوند).

**محدودیت پلتفرم که باید صادقانه اعلام شد:** HTML محدود تلگرام (`parse_mode="HTML"`) هیچ پشتیبانی‌ای از `font-size` یا `text-align` نداره — «بزرگ‌تر» و «وسط‌چین» به‌معنای واقعی کلمه ممکن نیست؛ فقط `<b>`/فاصله‌گذاری/خط جدید در دسترسه.

**رفع نهایی (تأییدشده):** چیدمان به الگوی «گزینهٔ ۱» تغییر کرد — جداسازی کامل «قیمت مرجع بازار» (بی‌طرف/اطلاعاتی) از «برای دستگاه شما» (شخصی‌سازی‌شده)، با یه جداکنندهٔ بصری (`➖➖➖➖➖➖➖➖`) بین این دو بخش. هر سه قیمت به الگوی «لیبل در یک خط، قیمت بولد با ایموجی 💰 در خط بعدی» تبدیل شدن — نزدیک‌ترین معادل ممکن به «بزرگ‌تر و برجسته‌تر» در چارچوب محدودیت تلگرام.

**اصلاح جملهٔ توضیحی قیمت مرجع:** به‌جای «باتری ۱۰۰٪» (که برای مدل‌های قدیمی‌تر که هیچ‌وقت باتری ۱۰۰٪ نداشتن گمراه‌کننده بود)، جملهٔ دقیق‌تر مالک پروژه استفاده شد: «دستگاه مشابه، موجود در بازار ایران، بدون باز شدگی، در حد نو و با بالاترین باتری نسبت به این مدل». تأیید فنی: بررسی `iv_coefficients` نشون داد baseline صفرِ دستهٔ `repair` دقیقاً `repair_none` («باز نشده») است — یعنی «بدون باز شدگی» هم مثل «در حد نو»/«بالاترین باتری» واقعاً بخشی از تعریف فنی `base_price`ه، نه فقط توصیف بازاریابی.

**لحن «پیشنهاد» به‌جای «ارزیابی یک‌طرفه»:** «قیمت خرید فروشگاه از شما» به «🏬 پیشنهاد نقدی استوک‌لند» تغییر کرد.

`_iv_enter_post_result` (دکمهٔ اشتراک‌گذاری نتیجه) از همون `txt` به‌روزشده استفاده می‌کنه (`summary_text=txt`) — پس متن اشتراک‌گذاری هم خودکار با چیدمان تازه هماهنگه، بدون نیاز به تغییر جدا. فقط `bot.py:_iv_finalize` تغییر کرد — منطق قیمت‌گذاری/امتیازدهی صفر خط تغییر کرد.

فایل‌های تغییرکرده: `bot.py`.

فایل‌های تغییرکرده: `bot.py`.

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

⚠️ **باگ رفع‌شده (۲۰۲۶-۰۷-۳۱):** پاپ‌آپ **جزئیات محصول** مینی‌اپ (`openP()` در `app.js`، جدا از پاپ‌آپ چک‌اوت که از قبل درست بود) این منطق `notify_on_restock` رو رعایت نمی‌کرد — دکمهٔ محصول ناموجود همیشه بدون قید و شرط با لینک `t.me/...` کاربر رو به ربات می‌فرستاد. رفع شد؛ الان دقیقاً همون رفتار پاپ‌آپ چک‌اوت رو داره.

**پنل مدیریت درخواست‌ها (`/admin/stock-requests`، زیر «مدیریت اپ»، permission `settings`/route-level `notifications`):** لیست همهٔ ردیف‌های `stock_subscriptions` گروه‌بندی‌شده بر اساس محصول (نام کاربر، تاریخ درخواست، وضعیت در‌انتظار/اطلاع‌داده‌شده) + دکمهٔ حذف تک‌ردیف (`db.delete_stock_request`) + دکمهٔ «🔔 اطلاع‌رسانی الان» که مستقل از آپلود موجودی، همون `admin_panel._notify_restock_subscribers` رو به‌عنوان `BackgroundTask` صدا می‌زنه (برای وقتی ادمین می‌خواد بدون آپلود فید جدید، همین الان به مشترکان منتظر خبر بده). `db.list_stock_requests()` تابع تازه — JOIN با `products`/`users`، موجودی هر محصول رو زنده از `product_feed` محاسبه می‌کنه (نه ستون ذخیره‌شده، چون `products` اصلاً چنین ستونی نداره).

### ✅ رفع‌شده (۲۰۲۶-۰۷-۳۱، دور دوازدهم): باگ باز نشدن اخبار/مقالات در PWA نصب‌شده

مالک پروژه محل دقیق تکرار رو مشخص کرد: مینی‌اپ در حالت PWA نصب‌شده (`display:standalone`، بیرون از تلگرام) — کلیک روی خبر هیچ اتفاقی نمی‌افتاد. علت: interceptor سراسری کلیک روی `a[target="_blank"]` در `app/app.js` فقط داخل `if(inTG){...}` ثبت می‌شد؛ بیرون از تلگرام اصلاً وجود نداشت، پس رفتار پیش‌فرض مرورگر (که در حالت standalone خیلی از مرورگرها ساکت شکست می‌خوره چون مفهوم «تب جدید» ندارن) اجرا می‌شد. رفع: ثبت listener دیگه شرطی به `inTG` نیست؛ شاخهٔ غیر-تلگرام اول `window.open` رو امتحان می‌کنه، اگه `null` برگردوند (بلاک‌شده/پشتیبانی‌نشده) به `location.href` (ناوبری همون تب) سقوط می‌کنه. جزئیات کامل تست در `CHANGELOG_AI.md`.

---

## ۲۴. دور دوم رفع کندی — CDN خارجی در پنل + مهاجرت اسکیمای تکراری در ربات (از ۲۰۲۶-۰۷-۲۶)

بعد از PR #86 (رفع ۵ مورد کندی سمت پنل — entry جدا در `CHANGELOG_AI.md`، نه بخش ۲۳ که مربوط به Backup/Restore/دسترسی ادمین/خرید ناموجوده)، مالک پروژه گزارش داد هنوز کنده و خواست **هم پنل هم ربات** بررسی بشن. جزئیات کامل در `CHANGELOG_AI.md` (entry «دور دوم رفع کندی») — خلاصهٔ چیزی که برای کار روی این بخش‌ها لازمه بدونی:

- **`_layout()` (admin_panel.py) دیگه مستقیم به `cdn.tailwindcss.com`/`unpkg.com`/`fonts.googleapis.com` وصل نمی‌شه** — از `/app/vendor/admin-tailwind.js`, `/app/vendor/admin-lucide.min.js`, و `@font-face` محلی به `/app/vendor/fonts/Vazirmatn-*.woff2` (۶ وزن) استفاده می‌کنه (همون مسیر `/app` که از قبل برای مینی‌اپ mount شده — بدون mount جدید). اگه این فایل‌ها روی سرور موجود نباشن، یک fallback synchronous (`document.write`) خودکار به همون CDNهای قبلی برمی‌گرده — یعنی پنل هیچ‌وقت به‌خاطر نبود vendor خراب نمی‌شه. **`app/get_vendor.sh` باید بعد از دیپلوی این نسخه یک‌بار دیگه روی سرور اجرا بشه** تا این فایل‌های تازه دانلود بشن؛ تا اون موقع فقط fallback (رفتار قبلی، نه بدتر) فعاله.
- `db.py`: `init_db()` حالا یک فلگ per-process (`_DB_INIT_DONE_PATH`) داره — دیگه هر `/start` ربات کل ۳۱ دستور DDL رو دوباره اجرا نمی‌کنه. `ensure_indexes()` هم یک فلگ per-index-name (`_INDEXES_DONE`) داره — self-healing (ایندکسی که به‌خاطر نبودن جدولش شکست بخوره، دفعهٔ بعد دوباره امتحان می‌شه). **اگه تابع مهاجرت جدیدی (`ensure_*_schema`) اضافه می‌کنی که ممکنه از چند نقطهٔ hot-path (نه فقط استارتاپ) صدا زده بشه، همین الگوی فلگ per-process رو رعایت کن — وگرنه دقیقاً همین کلاس باگ تکرار می‌شه.**
- `idx_orders_created_at` اضافه شد (داشبورد پنل ۳ کوئری روی این ستون می‌زنه، بدون ایندکس اسکن کامل جدول).
- `dashboard()` (admin_panel.py) کوئری‌هاش رو به تابع sync جدا (`_dashboard_fetch`) استخراج کرده و با `run_in_threadpool` صدا می‌زنه — همون الگویی که PR #86 فقط برای تماس‌های تلگرام رعایت کرده بود، حالا برای سنگین‌ترین route هم اعمال شده. **بقیهٔ routeهای سنگین پنل (لیست سفارش‌ها، گزارش‌ها، ...) هنوز همین رفتار رو ندارن — کاندید فاز بعد اگه باز گزارش کندی اومد.**
- ✅ **تکمیل‌شده (۲۰۲۶-۰۷-۳۱، فاز ۰ ممیزی کامل):** این الگو به `payment_service.py` (`payment_callback_gw` — مسیر فعال تأیید پرداخت) و `iphone_valuation/router.py` (`POST /valuate`) هم تعمیم یافت؛ تا قبل از این، فقط `admin_panel.py` این محافظت رو داشت، در حالی که این دو مسیر هم I/O بلاکینگ سنگین (SQLite خام + `requests.post` به درگاه/تلگرام، یا فچ نرخ ارز + provider هوش مصنوعی) رو مستقیم روی event loop مشترک اجرا می‌کردن.

---

## ۲۵. سیستم چند‌درگاهی پرداخت — `payment_gateways/` (از ۲۰۲۶-۰۷-۳۰)

> مالک پروژه بعد از مهاجرت هاست وردپرسی، پرداخت از کار افتاد (خطای «خطا در ایجاد تراکنش درگاه»). تشخیص: `.env` آدرس API زرین‌پال (`ZARINPAL_REQUEST_URL`) رو به یه دامنهٔ واسطهٔ خودی `pay.stland.ir` وصل کرده بود که بعد از مهاجرت گواهی SSL نامعتبر داشت؛ به‌علاوه پل PHP واسط (`stland.ir/payment/stockland-pay.php`) هم بعد از مهاجرت ۵۰۲ می‌داد. ثابت شد VPS (با IP خارجی آلمان) **مستقیم** به `api.zarinpal.com` می‌رسه — پس واسطه اصلاً لازم نبود. رفع فوری با اصلاح `.env` انجام شد؛ بعد مالک پروژه خواست کل مسیر به یه سیستم چند‌درگاهی حرفه‌ای بازطراحی بشه.

### معماری — دقیقاً همون الگوی `iphone_valuation/ai_providers/`
```
bot / mini-app → POST /payment/create → payment_service._run_gateway_failover()
                   → درگاه‌های فعال به‌ترتیب اولویت: اولی خطا داد → بعدی (failover خودکار)
                   → درج tx با ستون gateway → {authority, payment_url, gateway}
بازگشت کاربر → /payment/callback/{gw} → parse_callback درگاه → verify_payment همون درگاه
             → _finalize_paid_tx() (شارژ کیف‌پول/تحویل محصول، مشترک بین همهٔ درگاه‌ها)
```

### پکیج `payment_gateways/`
- `base.py` — قرارداد مشترک (`PaymentGatewayError`, `RIAL_PER_TOMAN=10`) + مستند سه‌تابعیِ هر درگاه: `create_payment(amount_toman, callback_url, description, config) -> {ok, authority, payment_url, error}`، `parse_callback(query, form) -> {authority, success}`، `verify_payment(authority, amount_toman, config) -> {ok, ref_id, error}`.
- **⚠️ واحد پول:** مبلغ داخلی همیشه **تومان**. هر درگاه خودش داخل ماژولش تبدیل می‌کنه — زرین‌پال/زیبال ریال (×۱۰)، **پی‌پینگ تومان (بدون تبدیل)**. هیچ تبدیلی بیرون از ماژول درگاه نیست.
- `zarinpal_gateway.py` — پیاده‌سازی مرجع (منطق اثبات‌شدهٔ قبلی، فقط ماژولار شده). `sandbox` → `sandbox.zarinpal.com`.
- `zibal_gateway.py` — تک‌شناسه (trackId)، ریال. `sandbox` → مرچنت رشتهٔ `"zibal"`.
- `payping_gateway.py` — تک‌شناسه (code)، **تومان**، auth با Bearer token.
- `__init__.py` — رجیستری `PAYMENT_GATEWAYS = {code: {module, label, fields, supports_sandbox}}` + `DEFAULT_GATEWAY="zarinpal"`. **افزودن درگاه تازه = یک فایل ماژول + یک خط این‌جا، بدون تغییر در payment_service.py یا admin_panel.py.** `fields` (لیست `(cred_key, label)`) فرم پنل رو خودکار می‌سازه.
- **⚠️ فقط زرین‌پال با کلید واقعی تولید تست شده. زیبال/پی‌پینگ طبق مستندات عمومی نوشته شدن ولی با کلید واقعی تست نشدن — قبل از فعال‌سازی باید با دکمهٔ «تست اتصال» تأیید بشن. طراحی امنه: درگاه غیرفعال تا وقتی ادمین صریحاً فعالش نکنه در failover استفاده نمی‌شه، و اگه create_payment یکی خطا بده failover می‌ره بعدی.**

### دیتابیس (`db.py`)
- جدول تازهٔ `payment_gateways` (`gateway PK, enabled, priority, credentials JSON, sandbox, updated_at`) + توابع `ensure_payment_gateways_schema`/`list_payment_gateways`/`get_payment_gateway`/`save_payment_gateway`/`get_active_payment_gateways` (فعال‌ها مرتب بر اساس priority صعودی). **⚠️ credentials به‌صورت JSON متن ساده (بدون رمزنگاری) ذخیره می‌شه** — عمداً، چون در دسترس‌بودن پرداخت > رمزنگاری‌در‌سکون مرچنت‌آیدی (که به‌تنهایی امکان برداشت نمی‌ده)؛ همون سطح امنیتی رازهای موجود در `.env` (بخش ۱۳). کلید هیچ‌وقت به HTML پنل برنمی‌گرده (فقط وضعیت «ثبت‌شده/نشده»).
- ستون تازهٔ `gateway TEXT DEFAULT 'zarinpal'` روی `zarinpal_transactions` (مهاجرت ALTER در **هردو** `db.py:init_db` و `payment_service.ensure_schema`) — تا کال‌بک بدونه با کدوم درگاه verify کنه.

### `payment_service.py`
- `_run_gateway_failover(amount_toman, description)` — حلقه روی `_gateways_for_create()` (فعال‌های پنل، یا fallback به زرین‌پالِ env اگه پنل خالیه)، اولین موفق رو برمی‌گردونه.
- `_resolve_gateway_config(gateway)` — config از پنل، **یا** برای زرین‌پال از env (`ZARINPAL_MERCHANT_ID`) اگه پنل نداره یا ردیفش خالیه. **⚠️ نکتهٔ ظریفی که فقط با تست پیدا شد:** یه ردیف پنلِ خالی (درگاهی که ادمین ذخیره کرده ولی کلید نذاشته) نباید جلوی fallback به env رو بگیره — پس چک `has_cred` قبل از «برنده‌شدن» ردیف پنل هست.
- `gateway_callback_url(gw)` = `{BASE_CALLBACK_URL}/{gw}` — نام درگاه در مسیر کال‌بکه.
- `_finalize_paid_tx(conn, tx, ref_id, authority)` — بخش نهایی‌سازی (شارژ کیف‌پول/تحویل/بازگشت وجه در race موجودی) که از کال‌بک قدیمی استخراج و مشترک شد؛ منطقش **عیناً** رفتار قبلی زرین‌پاله.
- `_handle_payment_callback(gw, query, form)` — کال‌بک عمومی درگاه‌آگاه؛ دو route نازک روش سوارن: `GET /payment/callback` (سازگاری عقب‌رو، gw=zarinpal) و `GET|POST /payment/callback/{gw}`.
- توابع قدیمی `zarinpal_create`/`verify_zarinpal` هنوز در فایل هستن ولی **دیگه صدا زده نمی‌شن** (کد مرده بی‌خطر، عمداً حذف نشدن تا دیف کوچیک بمونه).

### پنل ادمین `/admin/payment-gateways`
- زیر گروه «فروش» سایدبار، permission تازهٔ `payment_gateways` (با `PERM_LEGACY → settings`). یک فرم واحد با یک کارت به‌ازای هر درگاه: توگل فعال، اولویت، فیلد(های) کلید (`type=password`، فقط‌نوشتنی — خالی‌گذاشتن یعنی «کلید قبلی حفظ بشه»، نه پاک‌شدن)، توگل sandbox (اگه درگاه پشتیبانی کنه)، دکمهٔ «تست اتصال» (فرم مخفی + `form=` مثل الگوی حذف صفحهٔ قیمت‌ها)، و یک دکمهٔ «💾 ذخیرهٔ همهٔ تغییرات» پایین. روت‌ها: `payment_gateways_page`/`payment_gateways_save`/`payment_gateways_test`.
- «تست اتصال» یه `create_payment(10000, ...)` واقعی به درگاه می‌زنه (تراکنش در دیتابیس ما ثبت نمی‌شه، فقط چک اتصال+کلید) و نتیجه رو flash می‌کنه.

### ربات (`services/payments.py`)
- **شاخهٔ PHP کاملاً حذف شد** — همیشه مستقیم `{PAYMENT_API_BASE_URL}/payment/create` رو صدا می‌زنه (که خودش چند‌درگاهیه). ⚠️ **`PAYMENT_API_BASE_URL` باید در `.env` روی `http://127.0.0.1:8001` باشه** (سرویس روی ۸۰۰۱ گوش می‌ده؛ `PORT=5001` در env قدیمی اشتباه بود و اگه `PAYMENT_API_BASE_URL` خالی باشه، fallback به پورت غلط می‌ره).

### `.env` (تغییرات لازم روی سرور — نه در گیت)
- `ZARINPAL_REQUEST_URL`/`VERIFY_URL`/`STARTPAY_URL` → آدرس واقعی زرین‌پال (نه `pay.stland.ir`) یا اصلاً حذف بشن (کد پیش‌فرض درست داره).
- `PHP_PAYMENT_URL=`/`PHP_SECRET=` خالی.
- `PAYMENT_API_BASE_URL=http://127.0.0.1:8001`.
- زرین‌پال از همین env کار می‌کنه تا وقتی ادمین از پنل درگاه‌ها رو تنظیم کنه؛ بعدش تنظیمات پنل اولویت داره.

### تست انجام‌شده
هارنس مستقیم (بدون تلگرام/HTTP/API واقعی، با `requests.post` جعلی و monkeypatch ماژول درگاه‌ها): توابع DB (ذخیره/لیست/فعال‌های مرتب)، هر سه ماژول درگاه (صحت تبدیل واحد ریال/تومان، parse_callback، verify)، failover (اولی خطا→دومی، ترتیب اولویت، همه‌خطا→None)، fallback به env وقتی پنل خالیه (+ اصلاح باگ ردیف خالی)، کال‌بک کامل (verify→نهایی‌سازی کیف‌پول، idempotency بدون کسر دوبل، مسیر لغو)، و هر سه روت پنل (رندر، ذخیره با حفظ کلید روی فیلد خالی، تست اتصال).

### دور دوم — فیلدهای تکمیلی Verify (`card_pan`/`card_hash`/`fee_type`/`fee`) از ۲۰۲۶-۰۷-۳۰

مالک پروژه یه سند («معماری استاندارد پرداخت») از یه دستیار هوش مصنوعی گرفته بود که ادعا می‌کرد فلوی فعلی رو مطابق مستند رسمی زرین‌پال اصلاح کنیم. تحلیل نشون داد **فلوی اصلی (مراحل ۱ تا ۴) از قبل کاملاً همون چیزیه که سند خواسته** — فقط دو مورد در اون سند اشتباه بودن (نباید اعمال می‌شدن): (۱) `payment.zarinpal.com` به‌جای `api.zarinpal.com` (بدون مدرک معتبر، در حالی که `api.zarinpal.com` روی سرور واقعی تست و تأیید شده بود)، (۲) `ZARINPAL_CALLBACK_URL=https://stland.ir/payment/callback` بدون `panel.` — دقیقاً همون دامنهٔ اشتباهی که باعث خرابی اولیهٔ این نشست شده بود (`stland.ir` سایت وردپرسیه، نه جایی که `payment_service.py` اجرا می‌شه). این دو تغییر رد شدن. یه تناقض هم بین سند («merchant_id فقط env») و تصمیم صریح مالک پروژه (مدیریت چند‌درگاهی از پنل) بود — با سکوت/عدم اعتراض مالک پروژه به این ادامه‌داد.

تنها بخش واقعاً مفید سند: ذخیرهٔ `card_pan`/`card_hash`/`fee_type`/`fee` از پاسخ `verify.json`. این با **افزودن ۴ ستون** (ALTER، نه بازسازی جدول) به `zarinpal_transactions` پیاده‌سازی شد — نه یه جدول تازهٔ `payments` که سند پیشنهاد داده بود (بدون دلیل واقعی، چون جدول فعلی همین ستون‌ها رو تقریباً کامل داره و `bot.py`/`admin_panel.py` جاهای زیادی بهش وابسته‌ان).

- `zarinpal_gateway.verify_payment()` این ۴ فیلد رو از `data.card_pan`/`data.card_hash`/`data.fee_type`/`data.fee` استخراج و در خروجی برمی‌گردونه (⚠️ `card_pan` از قبل توسط خودِ زرین‌پال ماسک‌شده برمی‌گرده، پس ذخیره‌اش نقض «کارت ذخیره نشه» نیست). دو درگاه دیگه (زیبال/پی‌پینگ) این فیلدها رو ندارن — `base.py` مستند کرده که این‌ها اختیاریَن، نه اجباری برای هر درگاه.
- `payment_service._finalize_paid_tx()` پارامتر تازهٔ `extra: dict` گرفت (پیش‌فرض `{}`) و این ۴ فیلد رو توی همون `UPDATE ... status='paid'` ذخیره می‌کنه — برای درگاه‌هایی که این فیلدها رو ندارن، مقدار خالی/`None` ذخیره می‌شه (بدون کرش).
- لاگ کامل‌تر: `create_payment`/`verify_payment` زرین‌پال حالا کل پاسخ خام رو با `logger.info` هم ثبت می‌کنن (قبلاً فقط خطاها لاگ می‌شدن).
- **تست انجام‌شده:** استخراج صحیح ۴ فیلد در `verify_payment`، مهاجرت ستون‌ها (هم `db.py` هم `payment_service.py`)، ذخیرهٔ کامل end-to-end در کال‌بک، و مهم‌تر — تأیید که درگاه‌های **بدون** این فیلدها (زیبال) کرش نمی‌کنن و مقدار خالی ذخیره می‌کنن.

### دور سوم — پاک‌سازی کامل بقایای مسیر PHP قدیمی (از ۲۰۲۶-۰۷-۳۱)

بعد از تأیید کامل کارکرد سیستم چند‌درگاهی (رفع مشکل زیردامنهٔ اختصاصی `pay.stland.ir` — CNAME باید به `zpc.zarinpal.com` اشاره کنه، نه IP خودِ VPS؛ این یه ویژگی رسمی زرین‌پال برای white-label checkout است، مستقل از این پروژه)، مالک پروژه صریح خواست بقایای کاملاً مردهٔ مسیر PHP حذف بشه (نه فقط بی‌اثر بمونه). حذف شد:
- `payment_service.zarinpal_create()`/`verify_zarinpal()` — جایگزین‌شده با `payment_gateways/zarinpal_gateway.py`.
- `payment_service.REQUEST_URL`/`VERIFY_URL`/`STARTPAY_URL` (مقادیر خونده‌شده از `ZARINPAL_REQUEST_URL`/`ZARINPAL_VERIFY_URL`/`ZARINPAL_STARTPAY_URL` در `.env`) — دیگه هیچ‌جا خونده نمی‌شن؛ `zarinpal_gateway.py` این آدرس‌ها رو خودش هاردکد داره (نه از env). یعنی این سه env var دیگه **کاملاً بی‌اثرن** حتی اگه در `.env` باقی بمونن — پاک‌کردنشون از `.env` اختیاریه (بی‌خطر چه بمونن چه نمونن).
- `POST /payment/finalize` endpoint کامل (پل PHP خارجی) + متغیر `PHP_SECRET` + فیلد `php_bridge` در `/health`.
- ایمپورت‌های بلااستفادهٔ `hashlib`/`hmac` (که فقط همین endpoint استفاده می‌کرد).

فایل PHP خودِ `public_html/payment/stockland-pay.php` روی هاست وردپرسی (بیرون از این مخزن) هم توسط مالک پروژه حذف شد — چون از قبل هیچ مسیری در کد بهش وصل نبود، حذفش بی‌خطر بود.

**تست انجام‌شده:** سینتکس کامل + هارنس رگرسیون کامل (failover، callback→finalize با فیلدهای card_pan/fee، `/health` بدون فیلد مرده) بعد از حذف — همه سالم.

---

## ۲۶. یکپارچه‌سازی کیف‌پول‌ها — ممیزی + رفع ریشه‌ای (بخش ۱ سند مینی‌اپ، از ۲۰۲۶-۰۷-۳۱)

مالک پروژه گزارش «ناهماهنگی کیف‌پول بین بات و مینی‌اپ» داد و خواست ساختار یکی بشه. **نتیجهٔ ممیزی کامل کد:** یک منبع دادهٔ جدا برای مینی‌اپ وجود نداشت — `core/wallet.py` (که فقط `api.py` استفاده می‌کنه) از قبل از همون `db.get_wallet_balance`/`db.add_wallet_balance` استفاده می‌کرد که بات هم می‌کنه؛ کیف‌پول همکاری (ثانویه) هم همینطور — هم بات (`get_partner_wallet_balance`) هم مینی‌اپ (`core/partners.partner_balance` → همون تابع) دقیقاً یک جدول (`partner_wallets`) می‌خونن. یعنی «دو دیتابیس جدا» وجود نداشت.

**چیزی که واقعاً پیدا شد و رفع شد:** تنها مسیر خرید کیف‌پولیِ **بات** (`bot.py:finalize_product_order`) کسر موجودی رو با یک `sqlite3.connect` خام و `SELECT`+`UPDATE` جدا (بدون قفل تراکنشی) روی جدول `wallets` انجام می‌داد — نه با فراخوانی `db.subtract_wallet_balance` که همه‌جای دیگهٔ پروژه (پنل، `api.py`، بقیهٔ بات) ازش استفاده می‌کنن. این خودش باعث «دیتای متفاوت» نمی‌شد (جدول یکیه)، ولی دو مشکل واقعی داشت:
1. **بدون قفل atomic** — یعنی دو کسر همزمان (دبل‌تپ دکمهٔ خرید، یا خرید همزمان از بات و مینی‌اپ برای همون کاربر) می‌تونستن هر دو همون موجودی قدیمی رو بخونن و هر دو موفق بشن → کسر دوبل / موجودی منفی. این محتمل‌ترین توضیح فنی برای حس «دیسینک» کاربره: بعد از یه خرید همزمان یا دبل‌تپ، عدد نهایی با انتظار کاربر جور درنمی‌اومد.
2. مسیر جدا از تک‌نقطهٔ رسمی کسر کیف‌پول بود — یعنی هر تغییر آیندهٔ منطق کسر (لاگ، محدودیت، ولیدیشن) باید دستی توی دو جا اعمال می‌شد.

**رفع:**
- `db.subtract_wallet_balance` حالا با `BEGIN IMMEDIATE` قفل می‌شه (دقیقاً همون الگوی `claim_next_feed_item`) — دو کسر همزمان دیگه نمی‌تونن هر دو موفق بشن اگه موجودی کافی برای هردو نباشه.
- `bot.py:finalize_product_order` بلوک SQL خام حذف شد، جایگزین با یک فراخوانی `subtract_wallet_balance(uid, eff_price)`. **نکتهٔ ظریفی که فقط تست پیدا کرد:** بعد از این جایگزینی، متغیر `new_balance` (که پایین‌تر توی همون تابع برای پیام «موجودی فعلی» و محاسبهٔ بازگشت وجه در سناریوی race-condition موجودی استفاده می‌شه) دیگه تعریف نمی‌شد — باعث `NameError` توی مسیر موفق خرید می‌شد. رفع شد با یک خط `new_balance = get_wallet_balance(uid)` بلافاصله بعد از کسر موفق.

**تست:** هارنس مستقیم — کسر موفق، رد شدن کسر با موجودی ناکافی (بدون تغییر موجودی)، کسر روی کاربر بدون ردیف کیف‌پول، و مهم‌ترین تست: **۲۰ ترد هم‌زمان** هرکدوم سعی در کسر ۱۰٬۰۰۰ از موجودی ۱۰۰٬۰۰۰ — دقیقاً ۱۰تا موفق شدن، موجودی نهایی صفر (نه منفی)، بدون کسر دوبل. `finalize_product_order` هم با هارنس مستقیم تست شد (مسیر رد با موجودی ناکافی، و مسیر موفق با تأیید مقدار صحیح موجودی نهایی).

---

## ۲۷. حذف `database/bot.db` از کل تاریخچهٔ گیت (۲۰۲۶-۰۷-۳۱) — ⚠️ عملیات بازنویسی تاریخچه

طبق تأیید صریح مالک پروژه (در ادامهٔ گزارش ممیزی کامل، بخش ۱۳ آیتم ۹)، فایل باینری SQLite کامیت‌شدهٔ `database/bot.db` **از تمام تاریخچهٔ گیت** حذف شد — نه فقط از HEAD با یه commit جدید (که فایل رو در commitهای قدیمی همچنان قابل‌بازیابی نگه می‌داشت)، بلکه با بازنویسی کامل تاریخچه.

### چیکار شد
- ابزار: `git-filter-repo --path database/bot.db --invert-paths --force`.
- قبل از اجرا: بکاپ کامل تمام refها با `git bundle create ... --all`.
- بعد از اجرا: تأیید با `git rev-list --objects --all | grep bot.db` (بدون نتیجه) + یه clone تازه از remote برای تأیید نهایی.
- هر سه برنچ محلی/ریموت (`main`, `claude/git-connection-issue-cupwr0`, `server-backup-2026-07-23`) بازنویسی و با `git push --force` جایگزین شدن.
- فقط **یک** commit تاریخی (`bc8c9b9 Update stbak_engine.py`) این فایل رو اضافه کرده بود؛ از همون commit به بعد همهٔ commitهای بعدی هم بازنویسی شدن (چون tree هرکدوم به بلاب bot.db رفرنس داشت) — یعنی **همهٔ commit hashهای پروژه از اون نقطه به بعد عوض شدن**.

### ⚠️ اقدام لازم روی سرور تولید و هر clone دیگه (حتماً بخون قبل از هر git عملیات بعدی)
چون تاریخچه بازنویسی شده، `git pull` معمولی روی سرور یا هر clone قدیمی **کار نمی‌کنه** (تاریخچهٔ محلی و ریموت دیگه common ancestor مشترکی که git انتظارش رو داره ندارن — واقعاً دارن ولی hashها فرق دارن، پس git این‌طور می‌بینه که انگار دو تاریخچهٔ کاملاً جدا هستن). راه درست — یکی از این دو:

**روش ۱ (ساده‌تر، توصیه‌شده): clone تازه**
```bash
cd /opt/stockland
mv app app.old-history-$(date +%Y%m%d)   # نه rm — برای احتیاط نگه دار
git clone https://github.com/firouzayazi-source/stockland-bot.git app
cd app
# .env از app.old-history-... کپی کن (untracked بود، توی clone تازه نیست)
cp ../app.old-history-*/.env .env
# vendor رو هم دوباره لازمه (untracked/gitignored)
bash app/get_vendor.sh
systemctl restart stockland.service
```

**روش ۲ (بدون clone مجدد، اگه فضای دیسک محدوده):**
```bash
cd /opt/stockland/app
git fetch origin main
git reset --hard origin/main   # ⚠️ مخرب — هر تغییر لوکال commit‌نشده از بین می‌ره
git clean -fd                  # فایل‌های untracked اضافه (غیر از .env که gitignore شده) رو هم پاک می‌کنه — با احتیاط
systemctl restart stockland.service
```
در هر دو حالت، `.env` (که هیچ‌وقت commit نشده) و `app/vendor/` (که gitignored هستن) باید دست‌نخورده بمونن یا دوباره ساخته بشن — چک کن قبل از ری‌استارت سرویس.

### چرا این کار درست بود (نه فقط حذف از HEAD)
یه `git rm database/bot.db && git commit` معمولی فقط فایل رو از ورژن *جدید* پروژه حذف می‌کنه — هر کسی که کل تاریخچه رو clone کنه (`git clone` بدون `--depth`) همچنان می‌تونه با `git show bc8c9b9:database/bot.db` محتوای اون فایل (داده‌های واقعی‌نمای سفارش/تراکنش) رو استخراج کنه. بازنویسی کامل تاریخچه تنها راه واقعی حذفشه.

### تست انجام‌شده
- `git rev-list --objects --all | grep -i bot.db` روی هم repo لوکال هم یه clone تازهٔ remote → بدون نتیجه، هر دو.
- سایز `.git` بعد از `git gc --prune=now --aggressive` بررسی شد (کاهش یافت).
- تأیید سلامت کامل تاریخچه: `git log --oneline` روی هر سه برنچ، commitهای اخیر (فاز ۰ تا ۳ ممیزی) دست‌نخورده و به ترتیب صحیح باقی موندن.
- تأیید محتوای فایل‌های فعلی پروژه (بعد از rewrite) با اسموک‌تست import کامل (`bot.py`, `api.py`, `admin_panel.py`) — بدون خطا.

---

## ۲۸. تکمیل موارد باقی‌ماندهٔ ممیزی فنی — فاز R + P (از ۲۰۲۶-۰۷-۳۱)

بعد از تحویل کامل آرتیفکت ممیزی فنی (بخش‌های ۱ تا ۲۰ همون گزارش)، تمام موارد Medium/Low باقی‌مانده (که در فازهای ۰-۳ قبلی پوشش داده نشده بودن) به دو زیرفاز تقسیم و کامل شدن — طبق تأیید مالک پروژه («همه رو فازبندی و انجام بده»).

### فاز R — تصحیح ۳ مورد که قبلاً «انجام‌شده» گزارش شده بود ولی چک مستقیم کد ناقص بودنشون رو نشون داد
1. **نشتی حافظهٔ rate-limit واقعاً باز بود** — یکی‌سازی فاز ۳ (بخش ۵ همین سند) سیستمی با پاک‌سازی دوره‌ای (`_rate_limits`) رو حذف کرد و سیستم بدون پاک‌سازی (`_rl_msg_store`/`_rl_cb_store`) رو نگه داشت. رفع: `_rl_cleanup_loop()` در `bot.py` — هر ۳۰ دقیقه، کلیدهای بی‌فعالیت بیش از ۲۴ ساعت حذف می‌شن.
2. **یکی‌سازی partner-price ناقص بود** — فقط `bot.py` اصلاح شده بود؛ `api.py` (چک‌اوت مینی‌اپ + پیش‌نمایش کد تخفیف) هنوز شرط تکراری داشت. هر دو حالا از `db.partner_price_applies()` استفاده می‌کنن.
3. **دکوراتور مردهٔ callback کریپتو هنوز موجود بود** — `cb_wallet_crypto`/`cb_crypto_network` هنوز `@bot.callback_query_handler` جدا داشتن که هیچ‌وقت واقعاً trigger نمی‌شد (catch-all زودتر ثبت شده). حذف شد؛ فقط دیسپچ دستی داخل catch-all باقی موند.

### فاز P — موارد Medium/Low که اصلاً کار نشده بودن
- کش `admin_preferences` در `_layout()` (per-admin، ۳۰ ثانیه، الگوی `_get_theme`).
- صفحه‌بندی واقعی `/admin/tickets` (به‌جای سقف ثابت ۲۰۰).
- `PRAGMA synchronous=NORMAL` روی هر ۴ نقطهٔ اتصال SQLite + ANALYZE هفتگی (دوشنبه‌ها، همراه بکاپ خودکار).
- سقف `limit` در `GET /api/v1/products`؛ `limit`/`offset` در `GET /api/v1/favorites` (⚠️ `get_favorite_ids` یه `set` بدون‌ترتیبه — LIMIT/OFFSET باید سطح SQL روی `ORDER BY id DESC` اعمال بشه، نه با slice کردن خودِ set؛ این باگ فقط با تست مستقیم کشف شد).
- لوگوی هیرو (قبلاً فشرده‌شده به ۲۶KB) به precache سرویس‌ورکر اضافه شد.
- `loading="lazy"` به هر ۱۱ نقطهٔ باقی‌ماندهٔ `<img>` در `app.js`.
- فیلد `id` به `manifest.json` (⚠️ `screenshots` عمداً اضافه نشد — نیاز به عکس واقعی از اپ داره، نه placeholder جعلی؛ خودِ گزارش هم بلندمدت/اختیاری علامت زده بود).
- تأیید شد timeout صریح روی هر ۵ provider هوش مصنوعی از قبل موجوده (بخش ۲۲.۹/۲۲.۱۰) — بدون نیاز به تغییر.
- `TeleBot(..., num_threads=8)` صریح.
- `get_vendor.sh`: تأیید صریح دانلود موفق هر ۶ وزن فونت + دو فایل framework7 (قبلاً شکست نصفه‌کاره بی‌صدا بود)؛ حذف فایل زبالهٔ `app/icons/1`.
- preload فونت `Vazirmatn-Regular` در `app/index.html` و پنل ادمین.
- `deploy.sh`: مرحلهٔ minify اختیاری با esbuild (فقط اگه نصب باشه، بدون وابستگی جدید اجباری).
- `core/__init__.py`: اصلاح docstring اشتباه (ادعا می‌کرد «همه کلاینت‌ها استفاده می‌کنن» — دقیقاً برعکس واقعیت؛ فقط `api.py` استفاده می‌کنه، بقیه مستقیم از `db.py`).
- ماژول تازهٔ `tg_notify.py` — `send_telegram_message()` مشترک، یکی‌سازی ۵ نقطهٔ تکراری `requests.post` به تلگرام در `payment_service.py`/`api.py`. `payment_service.send_telegram_message` موجود حالا فقط delegate می‌کنه.
- بخش ۱۴ آیتم ۲ این سند (mismatch `redirect_url`/`payment_url`) تأیید و به «رفع‌شده» به‌روزرسانی شد — چک مستقیم کد نشون داد اصلاً mismatch نبوده.

### فاز C — Connection Pooling سبک SQLite (opt-in، پیش‌فرض خاموش)

پرریسک‌ترین آیتم کل گزارش ممیزی («ریسک اجرا متوسط تا بالا — نیاز به تست دقیق تراکنش‌های `BEGIN IMMEDIATE`»). پیاده‌سازی شد ولی **عمداً پیش‌فرض غیرفعال** — فقط با `DB_CONNECTION_POOL=1` در `.env` فعال می‌شه؛ رفتار پیش‌فرض فعلی (اتصال SQLite تازه به‌ازای هر فراخوانی) دست‌نخورده می‌مونه مگه صراحتاً روشن بشه.

**طراحی (`db_conn.py`):** یک اتصال SQLite به‌ازای هر ترد (`threading.local`)، reuse می‌شه به‌جای باز/بسته‌شدن مکرر. `_PooledSqliteConnection` یه رَپِر نازکه که `close()` روش عمداً no-op است (برمی‌گردونه به pool، نه می‌بنده). **مکانیزم fail-safe:** قبل از تحویل یه اتصال cache‌شده به فراخوان تازه، اگه `conn.in_transaction` باشه (یعنی یه transaction باز جامونده — نشونهٔ باگ commit/rollback جای دیگه)، به‌جای merge بی‌صدا با کوئری بعدی، صریحاً `rollback()` + لاگ هشدار می‌شه.

**باگ واقعی که فقط با تست concurrent کشف شد:** فعال‌سازی pooling، یه race condition پیش‌موجود در `claim_next_feed_item` رو آشکار کرد — مهاجرت `product_feed.order_id`/`delivered_at` قبلاً فقط لیزی (داخل خودِ تابع، هر فراخوانی) با دو `ALTER TABLE` توی یه `try` مشترک انجام می‌شد؛ بدون pooling این race تقریباً هیچ‌وقت trigger نمی‌شد (باز/بستن اتصال هر بار یه فاصلهٔ زمانی طبیعی بین تردها می‌نداخت)، ولی با pooling (بدون اون فاصله) روی یه دیتابیس کاملاً تازه با ۱۵ ترد هم‌زمان، اگه ترد اول فقط `order_id` رو اضافه می‌کرد، ALTER اول تردهای بعدی فوراً fail می‌شد و ALTER دوم (`delivered_at`) هیچ‌وقت اجرا نمی‌شد → `OperationalError: no such column: delivered_at`. رفع ریشه‌ای: این مهاجرت به `init_db()` منتقل شد (ایگر، مطابق قاعدهٔ استاندارد پروژه برای جدول‌های هسته — بخش ۷)، هر `ALTER` هم `try/except` جدا گرفت (هم توی `init_db` هم توی fallback باقی‌ماندهٔ داخل خودِ تابع). **این یافته نشون می‌ده pooling می‌تونه race conditionهای نهفتهٔ قبلی رو با کم‌کردن jitter زمانی بین تردها آشکار کنه — دلیل دیگه‌ای برای پیش‌فرض خاموش بودن.**

**تست انجام‌شده:** پیش‌فرض خاموش (رفتار قبلی دست‌نخورده)، reuse درست اتصال در همون ترد + ایزولاسیون کامل بین تردها، rollback دفاعی روی transaction باز جامونده (با لاگ هشدار)، تست استرس ۲۰ ترد هم‌زمان روی `subtract_wallet_balance` واقعی (دقیقاً ۱۰ کسر موفق از موجودی ۱۰۰٬۰۰۰ با کسر ۱۰٬۰۰۰، موجودی نهایی صفر، بدون کسر دوبل)، تست استرس ۱۵ ترد هم‌زمان روی `claim_next_feed_item` واقعی (۱۰ آیتم، بدون تحویل دوبل، بدون خطا) — هم با pooling هم بدونش.

**توصیه برای فعال‌سازی روی تولید:** اول روی یه محیط staging/کپی از دیتابیس واقعی با بار همزمان واقعی تست بشه؛ بعد با `DB_CONNECTION_POOL=1` در `.env` + ری‌استارت سرویس فعال بشه؛ لاگ‌های `stockland.db_conn` (هشدار transaction باز جامونده) چند روز اول رصد بشن.

### موارد پایین‌اولویتی که عمداً skip شدن (نه فراموش‌شده)
- `screenshots` در `manifest.json` — نیاز به عکس واقعی، نه placeholder.
- WebP/AVIF + `srcset` — بخشی از همون کار Pillow که قبلاً انجام شده، ولی تولید هم‌زمان فرمت جایگزین کار جداییه؛ فرصت از دست‌رفته‌ست نه باگ، اولویت پایین.
- Virtualization لیست محصولات/سفارش‌های مینی‌اپ — عمداً معلق («فقط اگه کاتالوگ رشد کرد»، طبق خودِ گزارش).

---

## ۲۹. دور بزرگ حسابداری (۲۰۲۶-۰۸-۰۱) — رفع باگ‌های محاسباتی + رفع باگ سراسری CSS + Import/تعویض کالا

جزئیات کامل در `CHANGELOG_AI.md` (سه entry جدا). خلاصهٔ چیزی که برای کار روی این بخش‌ها لازمه بدونی:

### ۲۹.۱ سه باگ محاسباتی حسابداری (رفع‌شده) — `get_accounting_kpis` (db.py)
- **پورسانت پرداختی دست‌کم محاسبه می‌شد:** قبلاً فقط `referrals.reward_amount` (پاداش یک‌بارهٔ اولین خرید) رو می‌شمرد؛ پورسانت مستمر هر خرید بعدی (`partner_transactions WHERE type='credit'`) اصلاً لحاظ نمی‌شد. رفع شد — حالا از `partner_transactions` می‌خونه (هر دو نوع پورسانت رو پوشش می‌ده).
- **«مانده صندوق» همیشه اشتباه بود:** `total_payouts` دنبال `status='paid'` می‌گشت که هیچ‌وقت نوشته نمی‌شه (`process_partner_payout` فقط `'approved'`/`'rejected'` می‌نویسه). رفع شد — از `payout_total` (status='approved') استفاده می‌کنه.
- **`feed_upload` (مسیر «افزودن متنی» موجودی) بدون اجبار قیمت خرید بود:** برخلاف مسیر آپلود فایل، اجازه می‌داد کالا بدون `purchase_price` ثبت بشه. رفع شد — حالا مثل مسیر فایل، به `batch-pricing` ریدایرکت اجباری می‌شه.
- «گزارش‌های مالی» (`/admin/reports`، صفحهٔ مستقل قدیمی) حذف و به `/admin/accounting` ریدایرکت شد؛ `get_financial_report()` (محاسبات ناقص‌تر، COGS رو بدون فیلتر `delivered=1` می‌شمرد) از `db.py` حذف شد.
- تمام اعداد پنل (KPIهای داشبورد، ستون مبلغ جدول سفارش‌ها، خلاصهٔ حسابداری) چپ‌چین شدن (`text-align` راست→چپ روی `.kpi-value`/`.money-cell`/`.ltr-num` + کلاس‌های `no-fa ltr-left`).

### ۲۹.۲ باگ سراسری «دکمهٔ نامرئی» — متغیر CSS `--clr-primary` (رفع‌شده، سپس بخشاً برگردونده‌شده)
`_layout()` (admin_panel.py) توکن‌های تم (`css_vars`، تزریق‌شده توی بلوک `:root{}`) رو با `";".join(...)` بدون سمی‌کالن پایانی می‌ساخت. آخرین متغیرش (`--border`) بدون `;` قبل از ادامهٔ بلوک اصلی (`--clr-primary` و بقیه) می‌اومد — طبق قواعد parse مقدار custom property در CSS، هرچی تا اولین سمی‌کالن بعدی بیاد جزو مقدار همون متغیر قبلی (`--border`) حساب می‌شه، نه یک property جدا. نتیجه: `--clr-primary` **در کل پنل** (نه فقط لاگین) هیچ‌وقت واقعاً تعریف نمی‌شد؛ هرجا `background:var(--clr-primary)` بود (از جمله دکمهٔ «ورود به پنل») پس‌زمینه transparent می‌شد.

⚠️ **تصمیم نهایی (طبق نظر صریح مالک پروژه):** این باگ **عمداً به‌طور کامل رفع نشد** — چون رفعش (اضافه‌کردن سمی‌کالن) باعث شد لهجهٔ رنگ teal یهو توی خیلی جاهای دیگهٔ پنل (دکمه‌ها/بج‌ها/حالت فعال سایدبار) هم ظاهر بشه که مالک پروژه ترکیب رنگ قبلی (بدون این لهجه) رو بیشتر می‌پسندید. راه‌حل نهایی: سمی‌کالن اضافه‌شده به `css_vars` **برداشته شد** (یعنی `--clr-primary` دوباره مثل قبل در بقیهٔ پنل تعریف نمی‌شه — ترکیب رنگ کلی پنل به حالت قدیمی برگشت)، ولی فقط `.login-submit` به‌جای `var(--clr-primary)` از `var(--primary)` استفاده می‌کنه — متغیر legacy جداگانه‌ای که هیچ‌وقت این باگ رو نداشت و همون رنگ teal (`#2EC4B6`) رو داره. یعنی **فقط دکمهٔ ورود** مستقل از این باگ درست/قابل‌مشاهده می‌مونه؛ بقیهٔ پنل عمداً با باگ (رفتار قبلی) باقی مونده. اگه در آینده جای دیگه‌ای از پنل هم دکمه/رنگ نامرئی گزارش شد، همین الگو (استفاده از `var(--primary)` به‌جای `var(--clr-primary)`، نه رفع خودِ `css_vars`) رو تکرار کن — مگه اینکه مالک پروژه صریحاً بخواد لهجهٔ رنگ teal همه‌جا برگرده.

### ۲۹.۳ بازطراحی صفحهٔ خلاصهٔ ویزارد کارشناسی آیفون (bot.py)
صفحهٔ «خلاصهٔ کارشناسی» (قبل از محاسبهٔ قیمت نهایی، بخش ۲۲.۲) دیگه هیچ‌کدوم از گزینه‌های انتخاب‌شده رو نشون نمی‌ده و دکمهٔ ✏️ جدا به‌ازای هر بخش نداره (طبق تصمیم صریح مالک پروژه، صرفاً UX). فقط ۳ دکمه: راست «✅ تایید و محاسبهٔ قیمت»، چپ «✏️ اصلاح گزینه‌ها»، زیرشون «❌ انصراف». ⚠️ **نکتهٔ فنی مهم دربارهٔ ترتیب دکمه‌ها در Telegram:** `InlineKeyboardMarkup.row(a, b)` همیشه `a` رو **چپ** و `b` رو **راست** رندر می‌کنه (چیدمان inline keyboard در تلگرام مستقل از جهت متن پیامه، همیشه بر اساس ترتیب آرایه از چپ‌به‌راست) — برای این‌که «تأیید» راست بشینه، باید *دومین* عنصر آرایه باشه: `kb.row(edit_button, confirm_button)`.

«اصلاح گزینه‌ها» کل ویزارد رو از مرحلهٔ اول (`series`) با حفظ کامل مقادیر قبلی در `state` دوباره باز می‌کنه — نه فقط یه بخش. پیاده‌سازی: سنتینل تازهٔ `_IV_EDIT_ALL_SENTINEL = "__editall__"` که با `state["editing"]=...` روی همون مکانیزم موجود (`_iv_edit_group_for`/`_iv_step_done`، قبلاً فقط برای ویرایش تک‌بخشی از داخل خلاصه استفاده می‌شد) سوار می‌شه؛ `_iv_edit_group_for` وقتی این سنتینل رو ببینه، گروه ویرایش رو `set(_IV_STEP_ORDER)` (یعنی همهٔ مراحل) برمی‌گردونه، پس درایور موجود خودش کل زنجیره رو تا آخر (شهر) طی می‌کنه و فقط اونجا خودکار به خلاصه برمی‌گرده. دکمه‌های `ivw_edit_{step_id}` قدیمی (تک‌بخشی) دیگه از هیچ‌جا emit نمی‌شن، ولی handlerشون عمداً حذف نشد (کد مرده بی‌خطر، دیف کوچیک‌تر). منطق `pricing_engine.py`/`scoring_engine.py`/`service.py` صفر خط تغییر کرد.

### ۲۹.۴ تکمیل حسابداری — Import عمومی + «تعویض کالا» + گزارش‌گیری
طبق درخواست «سیستم حسابداری باید هستهٔ مالی جامع/دقیق/سبک بشه»، بدون بازنویسی معماری موجود (جدول‌های تخصصی فعلی از قبل تک‌منبع درست بودن):

**ماژول تازهٔ `import_utils.py`:** `parse_uploaded_rows(filename, raw_bytes)` — بر اساس پسوند (`.xlsx`/`.xlsm` با openpyxl، `.csv` با `csv.DictReader`، بقیه TXT خطی **بدون هدر**) به لیست dict تبدیل می‌کنه؛ `pick(row, *keys)` اولین ستون غیرخالی از چند اسم رایج (فارسی/انگلیسی) رو برمی‌گردونه. ⚠️ **عمداً هیچ حدسی برای «TXT شاید CSV با هدر باشه» زده نمی‌شه** — چون فرمت خطی موجود (هر خط یک آیتم) می‌تونه خودش کاما داشته باشه بدون این‌که خط اول واقعاً هدر باشه؛ نسخهٔ اولیهٔ این تابع این حدس رو داشت و با تست مستقیم معلوم شد باعث حذف بی‌صدای اولین ردیف واقعی می‌شه — رفع شد. مصرف‌کننده‌ها:
- `feed_bulk_upload` (آپلود موجودی محصول، admin_panel.py): برای `.csv`/`.xlsx` از این پارسر استفاده می‌کنه (ستون `data`/`item`/`account`/...)؛ مسیر `.txt` قدیمی (`***` یا خط‌به‌خط، `line.split(",")[0]`) کاملاً دست‌نخورده موند.
- `/admin/accounting/expenses`: کارت تازهٔ «وارد کردن دسته‌ای از فایل» (`POST /accounting/expenses/import`) — عنوان/مبلغ اجباری، بقیه اختیاری با پیش‌فرض؛ ردیف ناقص بی‌صدا رد می‌شه، تعدادش توی پیام نهایی گزارش می‌شه.

**تعویض کالا (`db.exchange_order`) — قابلیتی که قبلاً کاملاً غایب بود** (فقط «برگشت» + «ارسال مجدد همون محصول» بود، نه تعویض به محصول/قیمت متفاوت). ⚠️ **تصمیم معماری کلیدی:** به‌جای وضعیت تازهٔ `orders.status` (که نیاز به ویرایش ~۱۰ جای کد داشت که از قبل دقیقاً `!= 'returned'` رو چک می‌کردن تا سفارش برگشتی از دید کاربر/گزارش مخفی بمونه — قانون ۷ پروژه)، سفارش قدیم دقیقاً با همون `status='returned'` موجود بسته می‌شه؛ یعنی همهٔ اون ~۱۰ جای کد بدون هیچ تغییری برای تعویض هم درست کار می‌کنن. یه ستون نال‌پذیر تازهٔ `orders.exchange_pair_id` (مهاجرت ایگر در `init_db`، مثل `feed_id`/`returned_at`) سفارش قدیم و جدید رو دوطرفه لینک می‌کنه. `exchange_order(old_order_id, new_product_id, old_product_action, wallet_delta)` اتمیک (`BEGIN IMMEDIATE`، دقیقاً الگوی `claim_next_feed_item`) این کارها رو با هم انجام می‌ده:
1. اول یه آیتم تازه از محصول مقصد claim می‌کنه — **قبل از هر تغییری روی سفارش قدیم** (اگه موجودی نبود، سفارش قدیم دست‌نخورده می‌مونه، خطای واضح).
2. تکلیف آیتم قدیم (بازگشت به موجودی/حذف دائم) — دقیقاً همون منطق `order_mark_returned_advanced`.
3. سفارش کاملاً جدید می‌سازه (خودش با `status='active'` عادی وارد فروش/COGS می‌شه — پس کوئری‌های `status='active'` مثل `get_accounting_kpis` خودشون درست کار می‌کنن، بدون نیاز به هیچ تغییری).
4. اختلاف قیمت (`wallet_delta`) رو مستقیم روی کیف‌پول کاربر اعمال می‌کنه (همون الگوی مقداردهی مستقیم `order_mark_returned_advanced`، نه `subtract_wallet_balance`، چون این یه override دستی ادمینه نه خرید خودکار).

کیف‌پول/پورسانت: `exchange_order` عمداً `process_referral_commission` رو دوباره صدا نمی‌زنه — پورسانت قبلاً روی خرید اصلی پرداخت شده، دوباره‌محاسبه یعنی پرداخت دوبل.

پنل: `GET/POST /admin/orders/{oid}/exchange` (فرم انتخاب محصول جایگزین از بین محصولات فعال با موجودی + تسویهٔ خودکار یا دستی اختلاف قیمت) + دکمهٔ «🔄 تعویض» کنار «↩️ برگشت»/«✏️ ویرایش» در لیست سفارش‌ها — عمداً **کنار** فرم برگشت/ارسال مجدد موجود اضافه شد، نه جایگزینش (اون‌ها برای همون-محصول/همون-قیمت هنوز کاربردی‌ان). `get_exchange_pair(order_id)`/`list_exchanges(limit)` برای گزارش‌گیری؛ صفحهٔ `/admin/accounting/exchanges` (لیست + Excel، الگوی گزارش‌های محصولات/همکاران موجود) با لینک از داشبورد حسابداری.

**تست انجام‌شده:** هارنس مستقیم `db.exchange_order` (فروش کل/COGS قبل و بعد درست، بدون شمارش دوبل؛ آیتم قدیم واقعاً `delivered=0` می‌شه؛ کیف‌پول با `max(0,...)` درست تسویه می‌شه؛ لینک دوطرفه صحیح؛ جلوگیری از تعویض دوبارهٔ سفارش قبلاً برگشتی؛ شکست تمیز بدون تغییر جزئی وقتی موجودی مقصد خالیه)، تست پارسر `import_utils` روی هر ۳ فرمت + کیس منفی (TXT با کاما که نباید هدر تلقی بشه)، تست end-to-end Playwright (ایمپورت CSV هزینه با یک ردیف ناقصِ درست رد‌شده، آپلود CSV موجودی محصول با اجبار صحیح batch-pricing، فرم کامل تعویض، صفحهٔ گزارش) — بدون خطای صفحه.

فایل‌های تغییرکرده این دور: `import_utils.py` (تازه)، `db.py`، `admin_panel.py`، `bot.py`.

---

## ۳۰. رفع نوتیف درخواست فروش + جهت‌دهی چپ‌چین ستاره‌ها/نمودارها + کیف‌پول پاداش مینی‌اپ (۲۰۲۶-۰۸-۰۱، دور دوم)

### ۳۰.۱ باگ نوتیف «می‌خوام بفروشم» (رفع‌شده) — `_pending_sell_requests_count` (admin_panel.py)
`iv_sell_requests.status` پیش‌فرضش `'new'`ه (هم ستون جدول `DEFAULT 'new'`، هم `bot.py` صریحاً `status="new"` می‌فرسته؛ تأیید ادمین هم به `'contacted'` تغییرش می‌ده) — ولی `_pending_sell_requests_count()` دنبال `status='pending'` می‌گشت که هیچ‌وقت مقداردهی نمی‌شد. یعنی درخواست تازهٔ «می‌خوام بفروشم» هیچ‌وقت نوتیف بالای «خرید و بخش مالی» رو فعال نمی‌کرد (خودِ لیست توی `/admin/receipts` درست نشون داده می‌شد چون `list_sell_requests()` بدون فیلتر status صدا زده می‌شه — فقط بج/نوتیف بود که خراب بود، پس ادمین اصلاً متوجه نمی‌شد باید اون صفحه رو چک کنه). رفع: چک به `count_sell_requests("new")` اصلاح شد.

### ۳۰.۲ جهت چپ‌چین برای ستاره‌های امتیاز/نمودارها (رفع‌شده)
طبق درخواست صریح مالک پروژه («فقط نوشته‌های فارسی راست‌چین باشن، مابقی چپ‌چین»)، با تست واقعی Playwright (نه حدس) تأیید شد رشتهٔ ترکیبی `★★★☆☆` داخل یک container با `dir="rtl"` توسط الگوریتم bidi یونیکد کاملاً بهم‌ریخته نمایش داده می‌شه (چون `★`/`☆` کاراکترهای neutral هستن) — رفع با `direction:ltr` روی container، دقیقاً همون الگوی از قبل موجود در `.sl-tier-progress-bar` (نوار پیشرفت پنل همکار، که از قبل عمداً `direction:ltr` داشت).
- `app/app.css`: `.sl-stars`/`.sl-stars-ico` (امتیاز محصول)، `.sl-review-st` (ستارهٔ نظرات خریداران)، `.sl-rate-stars` (ورودی امتیازدهی کاربر به سفارش تحویل‌شده) — همه `direction:ltr` گرفتن.
- `admin_panel.py`: `.chart-shell` (نمودار Chart.js فروش داشبورد) `direction:ltr` گرفت — Chart.js جهت صفحه رو از CSS تشخیص می‌ده و بدون این override محور افقی (تاریخ‌ها) رو معکوس رسم می‌کنه. نوار پیشرفت broadcast (ارسال همگانی، `admin_panel.py`) هم کلاس `ltr-num` (از قبل موجود، تعریف‌شده در بخش حسابداری امروز) گرفت — قبلاً فراموش شده بود.
- ⚠️ **بررسی شد و تغییری لازم نبود:** ستاره‌های ادمین پنل (`"⭐️"*rating`، تکرار یک گلیف یکسان) بصری تفاوتی با/بدون معکوس‌شدن نداره (همه گلیف‌ها یکی‌ان) — نیازی به فیکس نداشت. نوار پیشرفت `_bar()` صفحهٔ حسابداری و `.sl-tier-progress-bar` پنل همکار مینی‌اپ از قبل درست بودن (همین امروز/قبلاً `direction:ltr`/`ltr-num` گرفته بودن). نوار پیشرفت سطح همکار در `bot.py` (پیام تلگرام، با کاراکتر `▓`/`░`) داخل `<code>` رنداپ شده — تگ `<code>` در تلگرام از قبل از بازآرایی bidi در امانه (همون الگوی محافظتی که ارقام لاتین سری‌های ۳/۴/۵ رو هم امروز صبح محافظت می‌کرد)، نیازی به تغییر نداشت.

### ۳۰.۳ کیف‌پول پاداش (دوم) روی صفحهٔ اصلی حساب کاربری مینی‌اپ (تازه)
طبق درخواست صریح مالک پروژه: کیف‌پول همکاری (`partner_wallets`، «کیف‌پول دوم») که قبلاً فقط داخل پنل همکاری دیده می‌شد، حالا **علاوه بر آن** بالای کیف‌پول اصلی در تب «حساب» هم نشون داده می‌شه — داخل همون کادر آبی کیف‌پول اصلی (نه کادر جدا)، با جداکنندهٔ کم‌رنگ، عدد کوچک‌تر و **سبز رنگ** تا با کیف‌پول اصلی قاطی نشه. فقط برای همکاران تأییدشده فعاله (`is_partner`)؛ برای کاربر عادی کلاً مخفیه.
- **بدون API تازه** — `GET /me/partner` از قبل فیلد `balance` (همون `partners.partner_balance(uid)`) رو برمی‌گردوند (برای پنل همکاری استفاده می‌شد)؛ همین مقدار حالا برای رندر کیف‌پول پاداش هم استفاده می‌شه.
- `app/app.js` (`loadMe()`): بلوک `.sl-wallet-reward` (پیش‌فرض `display:none`) به HTML اضافه شد؛ داخل `.then()` پاسخ `/me/partner`، اگه `is_partner` بود نمایش داده و پر می‌شه.
- `app/app.css`: `.sl-wallet-reward`/`.sl-wallet-reward-l`/`.sl-wallet-reward-b` (سبز، `direction:ltr`) تازه اضافه شد؛ `.sl-wallet-b` (عدد کیف‌پول اصلی) هم `direction:ltr;text-align:left` گرفت — قبلاً هیچ‌کدوم از دو عدد کیف‌پول توی مینی‌اپ چپ‌چین نبودن.

### ۳۰.۴ مسیر پول پاداش/پورسانت — بررسی شد، نیازی به تغییر نبود
مالک پروژه خواسته بود «تمام پول‌های پاداش/پورسانت/جایزهٔ معرفی دقیق در کیف‌پول دوم بیاد، برای کاربر عادی غیرفعال، با همکار شدن فعال بشه». بررسی کامل کد قبل از هر تغییر:
- `process_referral_reward` (پاداش یک‌بارهٔ اولین خرید معرفی‌شده) → مستقیم `credit_partner_wallet` صدا می‌زنه (کیف‌پول دوم) — درست بود از قبل.
- `process_referral_commission` (پورسانت مستمر هر خرید بعدی) → قبل از هر پرداختی `_is_approved_partner(referrer_id)` رو چک می‌کنه؛ اگه معرف همکار تأییدشده نباشه، اصلاً چیزی پرداخت نمی‌شه (`{"paid": False}`) — یعنی این پورسانت **فقط** به همکاران تأییدشده تعلق می‌گیره، و توسط `credit_referrer` هم همیشه به کیف‌پول دوم واریز می‌شه (`credit_referrer` یه شاخهٔ fallback برای کاربر غیرهمکار داره که به کیف‌پول اصلی واریز کنه، ولی چون هر دو caller از قبل با `_is_approved_partner` فیلتر شدن، این شاخه در عمل هیچ‌وقت اجرا نمی‌شه — کد مرده بی‌خطر، عمداً دست‌نخورده موند تا دیف اضافه/پرریسک نشه).
- `pay_signup_referral_reward` هم همین‌طور، صراحتاً `if not _is_approved_partner(referrer_id): return {"paid": False}` داره.
- نتیجه: **هیچ تغییر بک‌اندی لازم نبود** — مسیر پول از قبل کاملاً درست بود؛ مشکل واقعی صرفاً UI بود (کاربر جایی نمی‌دید این پول کجا رفته) که با بخش ۳۰.۳ حل شد.
- ⚠️ **عمداً خارج از این تغییر:** پاداش سرزدن روزانه (`claim_daily_checkin`) کماکان به کیف‌پول **اصلی** واریز می‌شه (`add_wallet_balance`) — این یه مکانیزم انگیجمنت عمومیه برای همهٔ کاربرها (نه مخصوص معرفی/همکاری)، نه یه «پورسانت»، پس داخل تعریف «پاداش‌ها/پورسانت‌های معرفی» درخواست مالک پروژه قرار نمی‌گیره. اگه بعداً خلاف این تأیید شد، همینجا مستندش کن.

فایل‌های تغییرکرده این دور: `admin_panel.py`، `app/app.css`، `app/app.js`.

---

## ۳۱. بازطراحی Premium صفحهٔ «دعوت دوستان» مینی‌اپ (۲۰۲۶-۰۸-۰۲، دور سوم)

طبق دستور صریح مالک پروژه: **فقط UI/UX** تابع `_ptInvite()` (`app/app.js`، دسترسی از داخل پنل همکاری مینی‌اپ، ردیف «دعوت و تبلیغ») ارتقا یافت — هیچ تغییری در Backend/DB/API/تنظیمات پنل. همون endpoint موجود `GET /me/invite` (`api.py`) و همون فیلدهای پاسخ (`referral_link`, `promo_text`, `is_partner`, `reward_amount`, `stats.rewarded`, `stats.earned`, `stats.total` — این آخری از `core/referrals.stats()`) با مارک‌آپ/CSS تازه مصرف می‌شن؛ متن آماده تبلیغ قابل‌ویرایش ادمین (`get_promo_settings`/`bot_config`) دست‌نخورده و همچنان در پایین صفحه نمایش داده می‌شه، فقط با ظاهر تازه.

**طراحی (کلاس‌های تازهٔ `.sl-ref-*` در `app.css`، الهام از Telegram Premium/Apple Wallet):**
- `.sl-ref-hero` — آیکون هدیهٔ گرادیانی (آبی→بنفش) + عنوان «دعوت دوستان» + زیرعنوان انگیزشی.
- `.sl-ref-card` — کارت گرادیانی «شیشه‌ای» (سرمه‌ای→بنفش، دو گلوی شعاعی تزئینی با `::before`/`::after`، انیمیشن ورود ملایم `slRefIn`) شامل جعبهٔ لینک دعوت (`.sl-ref-link-box`، `backdrop-filter:blur`) + دکمهٔ اصلی سفید «🚀 اشتراک‌گذاری لینک دعوت» (`.sl-ref-btn-primary`، `<a>` به `t.me/share/url` مثل قبل) + دکمهٔ ثانویهٔ شیشه‌ای «📋 کپی لینک» (`.sl-ref-btn-secondary`، همون منطق کلیپ‌بورد قبلی).
- `.sl-ref-stats` — سه کارت کوچک (دعوت موفق/پاداش دریافتی/دعوت‌شده) از همون `stats` موجود، بدون هیچ کوئری/فیلد تازه.
- `.sl-ref-how` — بخش «💡 چطور کار می‌کند؟» با سه مرحلهٔ شماره‌دار (`.sl-ref-step`).
- `.sl-ref-promo-title`/`.sl-ref-promo-box` — همون متن تبلیغ قدیمی، فقط بازطراحی بصری.

قبل از شروع، کامپوننت‌ها/توکن‌های طراحی موجود پروژه بررسی و بازاستفاده شدن تا صفحه با بقیهٔ مینی‌اپ یکپارچه بمونه: الگوی گرادیان `.sl-wallet` (بخش ۲۱/۳۰)، توکن‌های `:root` (`--br`, `--dp`, `--lv`, `--card`, `--rd`, `--sh`)، الگوی ناوبری `_ptBackHtml`/`_ptWireBack`/`_accBody`/`skel`/`err`/`nl2br`. رفتار JS موجود عیناً حفظ شد (کپی کلیپ‌بورد با پیام «✅ کپی شد»، اشتراک‌گذاری تلگرام، بازگشت به پنل همکاری).

⚠️ **نکتهٔ تست (نه یک باگ واقعی):** اولین اسکرین‌شات Playwright از حالت تاریک، کارت گرادیانی رو تقریباً سیاه نشون داد. بررسی با مقایسهٔ pixel + تست ایزوله (بدون بقیهٔ app.css) + تست با تأخیر ثابت کرد این صرفاً مسابقهٔ زمانی خودِ اسکرین‌شات با انیمیشن CSS ورود کارت (`slRefIn`, ۴۵۰ میلی‌ثانیه) بوده — کارت واقعی (`.sl-wallet` موجود هم با همین متد تست شد و مشکلی نداشت) در هر دو تم، بعد از اتمام انیمیشن، کاملاً درست و واضح رندر می‌شه. هیچ تغییری در `color-scheme`/رندر سراسری لازم نبود.

فایل‌های تغییرکرده این دور: `app/app.js`، `app/app.css`.

### ۳۱.۱ رفع باگ تگ HTML خام در متن دعوت + بازنویسی متن پیش‌فرض (دور چهارم، همون روز)

مالک پروژه اسکرین‌شات پیام واقعی اشتراک‌گذاری‌شده رو فرستاد که توش `<b>`/`</b>` خام دیده می‌شد. علت: متن پیش‌فرض دعوت (`bot_config.promo`، `db.py:PROMO_DEFAULTS`) با تگ HTML تلگرام ذخیره می‌شد — درست فقط وقتی ربات با `parse_mode=HTML` داخل چت می‌فرستادش (`bot.py:cb_partner_ref_link`/`_send_invite_view`)، ولی همین متن خام مستقیم توی `t.me/share/url?text=...` هم می‌رفت (هم دکمهٔ ربات هم دکمهٔ اشتراک‌گذاری مینی‌اپ، از `GET /me/invite`) — اون سطح متن سادست، تگ‌ها تفسیر نمی‌شن. اسکرین‌شات تکرار لینک رو هم نشون داد (یک‌بار از `url=` شیت اشتراک‌گذاری، یک‌بار از داخل متن).

رفع (فقط `db.py`+`admin_panel.py`؛ `bot.py`/`api.py`/`app.js` بدون تغییر چون همه از همین متن مرکزی می‌خونن): `PROMO_DEFAULTS` بازنویسی شد (بدون تگ HTML، بدون خط تکراری لینک، لحن کوتاه‌تر/دعوت‌محور). `get_promo_settings()` یک خودترمیمی گرفت — اگه ردیف ذخیره‌شده در `bot_config` هنوز امضای خراب (`<b>`/`</b>`) رو داره، به‌جای بازتولید باگ به پیش‌فرض تازه برمی‌گرده؛ متن سفارشی مشروع ادمین (بدون تگ) دست‌نخورده می‌مونه. ⚠️ این self-heal برای پوشش دادن دیتای احتمالی سرور تولیده — چون `get_cfg_json` مقدار پیش‌فرض پایتون رو موقع خوندن هیچ‌وقت خودکار به دیتابیس نمی‌نویسه (فقط وقتی صریح `set_cfg` صدا زده بشه)، اگه ادمین قبلاً یه‌بار فرم `/admin/growth` رو ذخیره کرده باشه، متن قدیمی خراب توی `bot_config` گیر مونده بود و صرفاً عوض‌کردن ثابت پایتون کافی نبود.

فایل‌های تغییرکرده: `db.py`، `admin_panel.py`.

### ۳۱.۲ حذف تکرار لینک دعوت در پیام اشتراک‌گذاری (دور پنجم، همون روز)

بعد از رفع ۳۱.۱، لینک هنوز توی پیام نهایی دو بار دیده می‌شد — چون سه نقطهٔ ساخت لینک اشتراک‌گذاری (`bot.py:cb_partner_ref_link`، `bot.py:_send_invite_view`، `app/app.js:_ptInvite`) الگوی `https://t.me/share/url?url=<link>&text=<promo>` رو می‌ساختن: تلگرام خودش مقدار `url=` رو جدا بالای پیام اضافه می‌کنه، و چون `promo` هم از قبل خودِ لینک رو (از طریق `{link}`) داخلش جاسازی داره، نتیجه دو بار تکرار بود. رفع: هر سه نقطه فقط با `?text=<promo>` می‌سازن (بدون `url=`) — چون لینک از قبل داخل `promo` هست، نیازی به پارامتر جدا نیست. مسیر «کاربر عادی» (بدون لینک همکاری، `bot.py:_send_invite_view` شاخهٔ `else`) و مسیر اشتراک‌گذاری نتیجهٔ کارشناسی آیفون (`bot.py:_iv_enter_post_result`) دست‌نخورده موندن — اون‌ها اصلاً `promo`/لینک تکراری ندارن.

فایل‌های تغییرکرده: `bot.py`، `app/app.js`.

### ۳۱.۳ رفع اشتراک‌گذاری داخل تلگرام + شخصی‌سازی متن دعوت با نام فرستنده (دور ششم، همون روز)

مالک پروژه گزارش داد اشتراک‌گذاری لینک دعوت به‌جای شیت بومی تلگرام، به یه صفحهٔ دیگه هدایت می‌کنه — «مثل قبل می‌خوام داخل خود تلگرام شیر بشه». علت: رفع ۳۱.۲ پارامتر `url=` رو کاملاً از `t.me/share/url` حذف کرده بود؛ ولی این پارامتر دقیقاً همونیه که کلاینت‌های تلگرام باهاش این لینک رو به‌عنوان «شیت اشتراک‌گذاری بومی» تشخیص می‌دن — بدونش بعضی کلاینت‌ها (خصوصاً از داخل webview مینی‌اپ) اون رو مثل یه صفحهٔ وب معمولی باز می‌کنن.

**رفع درست‌تر (بدون برگشت به تکرار لینک):** `url=` برگردونده شد، ولی متن `promo` دیگه خودش `{link}` رو جاسازی نمی‌کنه (بند بعدی) — پس ترکیب `url=link` + `text=promo` دقیقاً یک‌بار لینک نشون می‌ده (بالای پیام، از پارامتر `url=`، دقیقاً همونی که تلگرام خودش رسم می‌کنه). برای مسیر «کپی دستی برای پیام‌رسان‌های دیگه» (بلوک متنی داخل چت ربات با برچسب «کپی یا فوروارد کنید» + جعبهٔ «متن آماده تبلیغ» در مینی‌اپ) که به شیت اشتراک‌گذاری تلگرام وابسته نیست، لینک صریح و جدا بعد از `promo` اضافه می‌شه (`promo + "\n" + link`) — پس اونجا هم دقیقاً یک‌بار دیده می‌شه، فقط این‌بار توسط خودمون کنترل می‌شه نه تلگرام.

**شخصی‌سازی متن دعوت:** طبق درخواست صریح («اول متن باید اطلاعات فرستنده بیاد برای حس بهتر») متن پیش‌فرض (`PROMO_DEFAULTS`) با نام دعوت‌کننده شروع می‌شه: `"🎁 {name} شما را به استوک‌لند دعوت کرد!\n..."`. نام از `db.get_user_full_name(uid)` خونده می‌شه — همون ستون `users.full_name` که هر بار `/start` پر می‌شه (`upsert_user`، `bot.py:1163`)، پس برای هر کاربر واقعی که قبلاً با ربات تعامل داشته قابل‌اعتماده؛ fallback نهایی «یک دوست» برای حالت خیلی نادر خالی‌بودن. سه نقطهٔ مصرف (`bot.py:cb_partner_ref_link`، `bot.py:_send_invite_view`، `api.py:GET /me/invite`) همه از همین تابع استفاده می‌کنن. `{link}` هم به‌صورت **اختیاری** توی متغیرهای در دسترس ادمین می‌مونه (متن‌های سفارشی قدیمی که فقط `{link}` داشتن، بدون `{name}`، بدون کرش کار می‌کنن — چون kwarg اضافه در `str.format()` نادیده گرفته می‌شه، نه خطا).

فایل‌های تغییرکرده: `db.py` (`PROMO_DEFAULTS` + راهنمای self-heal)، `bot.py` (هر دو مسیر)، `api.py`، `app/app.js`، `admin_panel.py` (راهنمای فیلد).

### ۳۱.۴ حذف شخصی‌سازی نام + برگردوندن لینک به پایین متن (دور هفتم، همون روز — نسخهٔ نهایی)

مالک پروژه صریح خواست: (۱) شخصی‌سازی نام (`{name}`) حذف بشه — باعث بهم‌ریختگی فرم پیام می‌شد؛ (۲) لینک همیشه **پایین** متن دیده بشه، نه بالا. این با نکتهٔ فنی ۳۱.۳ در تناقض بود: تا وقتی `url=` استفاده بشه (برای شیت اشتراک‌گذاری بومی تلگرام)، تلگرام **همیشه** مقدار `url=` رو بالای پیام می‌ذاره — امکان «هم اشتراک‌گذاری بومی هم لینک پایین» با این مکانیزم وجود نداره. طبق اولویت صریح و تکرارشدهٔ مالک پروژه («دفعه دهم هست که میگم»)، تصمیم نهایی: **موقعیت لینک بر شیت اشتراک‌گذاری بومی اولویت داره.**

رفع نهایی: `{name}` کاملاً حذف شد (از `PROMO_DEFAULTS` و هر سه نقطهٔ مصرف). `{link}` دوباره داخل خود متن (`PROMO_DEFAULTS`) در انتها قرار گرفت. `share_url` در هر سه نقطه (`bot.py:cb_partner_ref_link`، `bot.py:_send_invite_view`، `app/app.js:_ptInvite`) دوباره فقط با `?text=<promo>` ساخته می‌شه — بدون `url=`. نتیجه: لینک همیشه دقیقاً همون‌جایی که ادمین توی متن قرارش داده (پیش‌فرض: انتها) دیده می‌شه؛ اگه بعضی کلاینت‌های تلگرام (خصوصاً از داخل webview مینی‌اپ) این لینک رو مثل صفحهٔ وب معمولی باز کنن نه شیت اشتراک‌گذاری، این یه ترید‌آف شناخته‌شده و پذیرفته‌شده‌ست، نه باگ.

⚠️ **اگه در آینده دوباره تصمیم به اولویت‌دادن به شیت اشتراک‌گذاری بومی گرفته شد**، راه‌حل درست «دکمهٔ دوم» است، نه برگشت به `url=`: یه دکمهٔ «🚀 اشتراک‌گذاری سریع» با `url=link&text=promo-بدون-لینک` (لینک بالا، تضمین شیت بومی) **در کنار** دکمهٔ فعلی «📋 کپی متن دعوت» (که متن کامل با لینک پایین رو کپی می‌کنه، برای واتساپ/اینستاگرام/فوروارد دستی). این ترکیب هر دو نیاز رو بدون تناقض پوشش می‌ده — ولی پیاده‌سازیش منوط به تأیید صریح مالک پروژه‌ست، چون فعلاً اولویت روشن اعلام شده (لینک پایین > شیت بومی).

**راهنمای فیلد پنل** (`/admin/growth`) هم اصلاح شد: فقط متغیر `{link}` (نه `{name}`)، با تأکید صریح که باید جایی توی متن قرار بگیره (پیشنهاد: انتها) — چون دیگه به‌صورت جدا/خودکار فرستاده نمی‌شه؛ فراموش‌کردنش یعنی دعوت‌شده اصلاً لینک عضویت رو نمی‌بینه.

**پرسش تکرارشونده — کجای پنل متن حالت «همکار» و «کاربر عادی» مدیریت می‌شه:** فقط **یک** فیلد ادمین‌ادیت‌پذیر وجود داره — «📣 کیت تبلیغاتی همکار» در `/admin/growth` (همون `bot_config.promo`) — که **فقط برای کاربران همکار تأییدشده** استفاده می‌شه (`bot.py:_send_invite_view` شاخهٔ `is_partner`، و `cb_partner_ref_link`). متن حالت «کاربر عادی» (`_send_invite_view` شاخهٔ `else` — بدون لینک شخصی، فقط معرفی ربات + دعوت به ثبت‌نام همکاری) **کاملاً هاردکد در `bot.py`** و از پنل قابل‌ویرایش نیست. اگه لازم شد این هم ادمین‌ادیت‌پذیر بشه، باید فیلد تازه (مثلاً `bot_config.promo_normal`) + بخش تازه در فرم `/admin/growth` اضافه بشه — فعلاً فقط مستندسازی شده، اقدامی نشده.

فایل‌های تغییرکرده: `db.py`، `bot.py`، `api.py`، `app/app.js`، `admin_panel.py`.

### ۳۱.۵ برگشت به الگوی استاندارد اشتراک‌گذاری تلگرام (دور هشتم، همون روز — نسخهٔ واقعاً نهایی)

بعد از ۳۱.۴، مالک پروژه گزارش داد بازم لینک به‌جای شیت بومی تلگرام، صفحهٔ دیگه‌ای باز می‌کنه؛ این‌بار صراحتاً گفت «هر حالت استانداردی که می‌دونی بساز، فقط دو تا لینک نباشه» — یعنی اولویت رو کاملاً به من واگذار کرد، فقط با قید «بدون تکرار لینک» و «متن دوستانه/جذاب».

**تشخیص نهایی و قطعی:** الگوی رسمی/تنها-مستندِ دکمهٔ اشتراک‌گذاری تلگرام `t.me/share/url?url=X&text=Y` است — `url=` **اجباریه** (این پارامتریه که به تلگرام می‌گه «این یه عملیات اشتراک‌گذاریه»، نه یه لینک معمولی)؛ `text=` فقط کپشن اختیاریه. تلاش‌های ۳۱.۲ تا ۳۱.۴ (حذف `url=` برای کنترل موقعیت لینک) دقیقاً همون چیزی بود که در بعضی کلاینت‌ها باعث می‌شد این لینک به‌جای شیت اشتراک‌گذاری، مثل یه صفحهٔ وب معمولی باز بشه — یه ترید‌آف واقعی و اجتناب‌ناپذیر بین «کنترل کامل موقعیت لینک» و «تضمین شیت بومی».

**رفع نهایی:** `url=link` دوباره برگشت (تضمین شیت بومی در همهٔ کلاینت‌ها) + `text=promo`. برای این‌که این ترکیب هیچ‌وقت تکراری نشه، `promo` (فیلد ادمین‌ادیت‌پذیر «📣 کیت تبلیغاتی همکار») دیگه اصلاً `{link}` رو در خودش جاسازی نمی‌کنه — پس همیشه دقیقاً **یک** لینک (بالای پیام، از `url=`) دیده می‌شه. متن پیش‌فرض هم با همین چیدمان طبیعی می‌خونه: «همین الان با لینک بالا عضو شو...».

برای مسیر «دیدن/کپی دستی لینک» داخل خودِ چت ربات (نه چیزی که فرستاده می‌شه)، یه خط مستقل «🔗 لینک اختصاصی شما» با `<code>{link}</code>` جدا از بلوک «متن آماده تبلیغ» اضافه شد — این دو تا کاملاً جدان (یکی برای دیدن/کپی لینک خام، یکی برای متن تبلیغ)، پس اونجا هم هیچ‌وقت دو لینک کنار هم دیده نمی‌شه.

`{link}` به‌عنوان متغیر **کاملاً اختیاری** برای ادمین باقی می‌مونه (اگه صراحتاً بخواد لینک رو هم داخل متن بیاره، مثلاً برای پلتفرم‌هایی که `url=` جدا معنی نداره) — راهنمای فیلد در `/admin/growth` این رو توضیح می‌ده.

**درس این ۵ دور رفت‌وبرگشت:** موقعیت دقیق لینک در پیام نهایی و تضمین شیت اشتراک‌گذاری بومی تلگرام دو نیاز واقعاً در تناقضن وقتی از یک دکمهٔ واحد استفاده می‌شه — راه‌حل درست (اگه بعداً موقعیت دقیق دوباره اهمیت پیدا کرد) «دکمهٔ دوم» موازیه (مستند در ۳۱.۴)، نه دستکاری بیشتر همین یک دکمه.

فایل‌های تغییرکرده: `db.py`، `bot.py` (هر دو مسیر)، `app/app.js`، `admin_panel.py`.

---

## ۳۲. مسیر اختصاصی آپلود اکسل موجودی محصول — هر ردیف = یک محصول چندستونی (۲۰۲۶-۰۸-۰۲)

طبق مثال دقیق مالک پروژه: ساختار فایل اکسل موجودی محصول با TXT/CSV فرق داره — اطلاعات هر محصول توی **یک ستون** نیست، توی **چند ستون** (چپ به راست) پخش شده، و ردیف اول عنوان همون ستون‌هاست (مثال واقعی: `apple id | pass | pet | city | meet … | code | FREE` در ردیف ۱، بعدش هر ردیف یک اکانت کامل). مسیر قبلی اکسل (`parse_uploaded_rows` + `pick`، مشترک با CSV) فقط **یک** ستون رو (اولین ستون تطبیق‌یافته با نام‌های `data`/`item`/`account`/...، وگرنه اولین ستون موجود) به‌عنوان کل محصول برمی‌داشت — بقیهٔ ستون‌ها (رمز، پاسخ سؤالات امنیتی، کد، توضیحات) بی‌صدا دور ریخته می‌شدن.

**رفع:** `import_utils.parse_xlsx_labeled_items(raw)` — تابع تازه، جدا از `parse_uploaded_rows`. ردیف اول رو عیناً (بدون lower/تغییر حروف — چون این متن مستقیم داخل `<code>` به خریدار تحویل داده می‌شه) به‌عنوان برچسب ستون‌ها می‌خونه؛ هر ردیف بعدی رو با پیمایش تمام ستون‌ها به یک آیتم **چندخطی** به فرم `"{برچسب}: {مقدار}"` (یک فیلد در هر خط) تبدیل می‌کنه — دقیقاً همون فرمتی که ورودی متنی `***`-جداشده (بخش ۶.۱ جدول‌های موجود) از قبل ازش پشتیبانی می‌کنه؛ یعنی `product_feed.data` هر ردیف یه بلوک چندخطیه، دقیقاً مثل این‌که ادمین دستی همون متن رو با فرمت TXT وارد کرده بود. اعداد صحیح (مثل کد ۲۳۴۳۴) بدون `.0` اضافه رندر می‌شن (`isinstance(v, float) and v.is_integer()`).

`admin_panel.feed_bulk_upload` حالا سه شاخهٔ کاملاً جدا داره: `.xlsx`/`.xlsm` ← `parse_xlsx_labeled_items` (تازه)، `.csv` ← همون منطق قبلی `pick()` تک‌ستونی (**بدون تغییر**، طبق درخواست صریح که فقط اکسل جدا بشه، نه CSV)، بقیه (TXT) ← منطق قدیمی دوفرمتی (`***` یا خط‌به‌خط) دست‌نخورده. راهنمای متن زیر دراپ‌زون آپلود هم به‌روز شد تا این تفاوت رو توضیح بده.

⚠️ **محدودیت شناخته‌شده، عمداً مستندشده نه رفع‌شده:** اگه هدر یه ستون خالی باشه، اون ستون از خط حذف می‌شه (نه با برچسب مبهم مثل `col3:`). یه فایل نمونهٔ اولیه‌تر که مالک پروژه فرستاد (قبل از نمونهٔ دقیق‌تر نهایی) این الگو رو داشت: ستون‌های جواب سؤال امنیتی (`best friend?` → جواب) با هدر خالی زیر ستون سؤال بودن — با پیاده‌سازی فعلی، اون جواب‌ها (دادهٔ واقعاً حساس) حذف می‌شن، فقط متن خودِ سؤال می‌مونه. چون نمونهٔ نهایی/دقیق مالک پروژه (که تأیید صریح شد) این مشکل رو نداشت، این ادج‌کیس عمداً حل نشد — اگه فایل واقعی تولید همچین ستون‌های بی‌هدری داره، باید یا عنوان هر ستون توی خودِ فایل اکسل پر بشه (راه‌حل ساده‌تر و مطمئن‌تر)، یا این تابع برای «هدر خالی = ادامهٔ ستون قبلی» گسترش پیدا کنه — منوط به تأیید صریح.

**تست:** هارنس مستقیم روی هر دو فایل نمونهٔ ارسالی (یکی با ستون‌های کامل، یکی با هدر خالی) — خروجی فایل کامل دقیقاً با فرمت درخواستی مطابقت داشت؛ end-to-end با درج واقعی در `product_feed` و بررسی هم preview لیست پنل (`splitlines()[0][:80]`) هم رندر نهایی `<code>` تحویل به خریدار.

فایل‌های تغییرکرده: `import_utils.py`، `admin_panel.py`.

### ۳۲.۱ چپ‌چین apple id در پنل + توضیحات مشترک اختیاری برای آپلود موجودی (دور دوم، همون روز)

مالک پروژه تأیید کرد منطق بخش ۳۲ درسته، فقط دو مورد اضافه خواست:

**۱) چپ‌چین:** چون خط اول محتوای فید (مثل `apple id: ...`) کاملاً لاتینه ولی صفحهٔ پنل راست‌چینه، بدون تنظیم صریح راست‌چین نمایش داده می‌شد. رفع در دو نقطه‌ای که این محتوا دیده می‌شه: پیش‌نمایش لیست فید (`feed_detail`، `<td dir="ltr" style="text-align:left">`) و تکست‌اریای صفحهٔ ویرایش آیتم (`feed_item_edit_get`). `_textarea()` یک پارامتر اختیاری تازه `ltr=False` گرفت — فقط همین یک فراخوانی (`data` در ویرایش آیتم) ازش `True` می‌ده، بقیهٔ ۱۵ فراخوانی قبلی (فیلدهای فارسی مثل توضیحات محصول) بدون تغییر رفتار.

**۲) توضیحات مشترک اختیاری:** طبق درخواست («برای انتهای هر اپل آیدی توضیحات مشترک دارم، مثلاً خاموش کردن Find My») یک تکست‌اریای تازه (`common_suffix`) به فرم «آپلود فایل» اضافه شد. هر متنی ادمین توش بنویسه، بعد از پارس‌شدن فایل (مستقل از فرمت — هر سه شاخهٔ xlsx/csv/txt)، به انتهای **همهٔ** آیتم‌های همون آپلود اضافه می‌شه: `item = f"{item}\n{common_suffix}"`. این یک فیلد per-upload‌ه (فقط برای همون یک آپلود)، جایی ذخیره نمی‌شه — اگه بعداً نیاز به یادآوریِ دائمی/پیش‌فرض شد (مثلاً per-product)، باید فیلد تازه‌ای طراحی بشه (خارج از اسکوپ این درخواست).

فایل‌های تغییرکرده: `admin_panel.py`.

---

## ۳۳. رفع رنگ نامرئی متن حباب پیام ادمین در چت تیکت (۲۰۲۶-۰۸-۰۶)

مالک پروژه گزارش داد داخل چت تیکت، نوشته‌های حباب پیام ادمین با پس‌زمینهٔ حباب یک‌رنگ شدن و دیده نمی‌شن. علت: تکرار همون باگ سراسری `--clr-primary` (بخش ۲۹.۲) — `.chat-bubble--admin` هم مثل دکمهٔ ورود قدیمی از `background:var(--clr-primary)` استفاده می‌کرد؛ این متغیر به‌خاطر سمی‌کالن جاافتاده در تولید `css_vars` هیچ‌وقت واقعاً تعریف نمی‌شه (transparent می‌مونه)، پس پس‌زمینهٔ حباب ادمین transparent و متن سفید روش عملاً نامرئی بود.

رفع: دقیقاً همون الگوی تثبیت‌شدهٔ بخش ۲۹.۲ (نه رفع ریشه‌ای `css_vars`، که عمداً دست‌نخورده می‌مونه) — `.chat-bubble--admin` از `var(--clr-primary)` به `var(--primary)` (متغیر legacy همیشه‌تعریف‌شده، رنگ teal `#2EC4B6`، هم در بلوک روشن هم تاریک یکسان) تغییر کرد. **الگوی تکرارپذیر برای آینده:** هر جای دیگهٔ پنل که رنگ/دکمه نامرئی گزارش شد، همین جایگزینی نقطه‌ای رو بکن، نه دست‌کاری `css_vars`.

فایل‌های تغییرکرده: `admin_panel.py`.

---

## ۳۴. رفع تغییر نام/پسوند فایل پیوست تیکت پس از انتقال به پنل (۲۰۲۶-۰۸-۰۶)

مالک پروژه گزارش داد فایل‌های پیوست‌شده به تیکت، بعد از دانلود از پنل ادمین، نام/پسوند اصلی‌شون رو از دست می‌دن. سه لایهٔ علت:
1. `bot.py:_ticket_v2_handle_user_message` برای پیام نوع `document` فقط `file_id` رو می‌خوند، هیچ‌وقت `message.document.file_name` (تنها نوع محتوایی که تلگرام واقعاً نام اصلی فایل رو نگه می‌داره) رو نمی‌خوند.
2. `ticket_messages` (db.py) اصلاً ستونی برای نام فایل نداشت.
3. روت پروکسی `/admin/tickets/media/{file_id}` (admin_panel.py) هیچ‌وقت هدر `Content-Disposition` ست نمی‌کرد — مرورگر موقع دانلود از هش داخلی `file_path` تلگرام به‌جای نام واقعی استفاده می‌کرد.

**رفع (سه فایل، هر لایه یک فایل):**
- `db.py`: ستون تازهٔ `file_name TEXT` به `ticket_messages` (مهاجرت استاندارد ALTER در `ticket_ensure_schema`). `ticket_add_message()` پارامتر اختیاری `file_name` گرفت. تابع موازی/قدیمی `save_ticket_message` چک شد — بدون هیچ caller زنده‌ای، دست‌نخورده موند (کد مرده).
- `bot.py`: `_ticket_v2_handle_user_message` حالا `message.document.file_name` رو هم می‌خونه و پاس می‌ده. دو caller دیگهٔ `ticket_add_message` (پیام راه‌اندازی محصول، پاسخ متنی ادمین از داخل ربات) صرفاً متنی‌ان، بدون رسانه — دست‌نخورده موندن.
- `admin_panel.py`: `_render_media()` نام فایل رو به URL پروکسی به‌صورت `?fn=<urlencoded>` اضافه می‌کنه (`urllib.parse.quote(fname, safe='')`، نه `e()` که فقط HTML-escape است). روت `GET /tickets/media/{file_id}` پارامتر `fn` رو می‌گیره، پاک‌سازی می‌کنه (حذف `"`/`\`/CRLF برای جلوگیری از header injection) و `Content-Disposition: inline; filename="..."` رو ست می‌کنه.

**تست انجام‌شده:** هارنس مستقیم `db.ticket_add_message` با نام فایل فارسی+پسوند — ذخیره/بازخوانی دقیق تأیید شد. تست جدا برای roundtrip صحیح `urllib.parse.quote`/`unquote` روی رشتهٔ فارسی، و برای پاک‌سازی هدر (تلاش تزریق `"; filename="x.exe` به‌عنوان نام فایل — کاراکترهای خطرناک حذف می‌شن). سینتکس کامل هر سه فایل چک شد.

فایل‌های تغییرکرده: `db.py`، `bot.py`، `admin_panel.py`.

---

## ۳۵. امکان ارسال عکس/فایل از پنل ادمین به کاربر در چت تیکت (۲۰۲۶-۰۸-۰۶)

مالک پروژه گزارش داد فرم پاسخ تیکت در پنل فقط متن می‌فرسته، نه عکس/فایل. علت: فرم `<form>` بدون `enctype="multipart/form-data"` بود، روت `POST /admin/tickets/{tid}/reply` فقط `text: str = Form("")` می‌گرفت، و تنها راه ارسال رسانه به کاربر (`_tg_send_photo`) فقط از روی **URL از قبل میزبانی‌شده** کار می‌کرد (برای بنر تبلیغاتی/محتوای اپ)، نه آپلود مستقیم بایت‌های فایل از کامپیوتر ادمین.

**رفع:**
- فرم پاسخ (`ticket_detail`): `enctype="multipart/form-data"` گرفت + `<input type="file" name="attachment">` اضافه شد؛ `required` روی تکست‌اریا حذف شد (چون حالا پیوست‌تنها هم مجازه).
- تابع تازهٔ `_tg_send_document(chat_id, file_bytes, filename, caption, as_photo, reply_markup)` — آپلود مستقیم بایت خام به `sendDocument`/`sendPhoto` تلگرام (`files={field: (filename, file_bytes)}`، نه `json=` مثل `_tg_send_photo` موجود که فقط URL می‌فرسته)؛ `file_id` واقعی تلگرام رو از پاسخ استخراج و برمی‌گردونه (برای عکس، بزرگ‌ترین سایز — آخرین آیتم آرایهٔ `photo`).
- `POST /tickets/{tid}/reply`: پارامتر تازهٔ `attachment: UploadFile = None` (همون الگوی `feed_bulk_upload`/`restore_sync` موجود در فایل، بدون نیاز به import `File`). اعتبارسنجی از «متن اجباری» به «متن یا پیوست، حداقل یکی» تغییر کرد. اگه پیوست باشه، به‌جای `sendMessage`، از `_tg_send_document` استفاده می‌شه (با همون دکمهٔ این‌لاین «ادامه گفتگو» که قبلاً فقط رو پیام متنی بود). رکورد `ticket_messages` با `media_type`/`media_file_id`/`file_name` واقعی (بعد از موفقیت ارسال تلگرام، نه قبلش) ذخیره می‌شه — `_render_media()` (بخش ۳۴) از قبل مستقل از `sender` کار می‌کنه، پس رندر پیام‌های ادمین با رسانه بدون هیچ تغییر اضافه‌ای در `_render_media` درست نمایش داده می‌شه.

⚠️ **باگی که فقط با تست پیدا شد و قبل از commit رفع شد:** نسخهٔ اولیهٔ رفع، `try/except` مربوط به لوکاپ+مهاجرت تیکت رو از بلوک INSERT نهایی جدا کرد، ولی مسیرهای بازگشت زودهنگام («تیکت یافت نشد»/«تیکت بسته است») دیگه به `finally: conn.close()` بلوک دوم نمی‌رسیدن — یعنی نشتی اتصال SQLite در دو مسیر خطای رایج. رفع با `conn.close()` صریح قبل از هر `return` زودهنگام در بلوک اول.

**تست انجام‌شده:** هارنس مستقیم `admin_panel.ticket_reply()` (نه از طریق HTTP واقعی — `_get_admin` و `_requests.post` مانکی‌پچ شدن) با ۴ سناریو: پاسخ فقط‌متنی (رگرسیون، بدون تغییر رفتار)، پاسخ سند+متن (`media_type='document'`, نام فایل فارسی+پسوند حفظ‌شده)، پاسخ فقط‌عکس بدون متن (placeholder `[photo]`، `file_id` بزرگ‌ترین سایز)، و رد پاسخ کاملاً خالی (نه متن نه پیوست). جدا: تیکت یافت‌نشد + تیکت بسته (تأیید عدم نشتی اتصال بعد از رفع باگ بالا).

فایل‌های تغییرکرده: `admin_panel.py`.

---

## ۳۶. تکمیل سیستم برگشت محصول — پاک‌سازی از «خریدهای من» و بستن تیکت مرتبط (۲۰۲۶-۰۸-۰۶)

مالک پروژه خواست وقتی ادمین محصولی رو عودت می‌زنه، اون سفارش «انگار اصلاً خریده نشده» — هم از خریدهای من هم از چت — ناپدید بشه. بررسی کد نشون داد این تصمیم قبلاً *تقریباً* درست پیاده شده بود (قانون ۷ پروژه: `status='returned'` از دید کاربر مخفیه)، ولی دو رخنهٔ واقعی داشت:

1. **باگ واقعی در «🛒 خریدهای من»:** `bot.py:_show_my_orders` (دکمهٔ اصلی منو) از `db.get_recent_orders_by_user` استفاده می‌کنه — برخلاف تقریباً هر تابع مشابه دیگهٔ پروژه (`get_user_orders`، جزئیات سفارش در `cb_order_detail`)، این تابع هیچ فیلتر `status != 'returned'` نداشت. یعنی سفارش برگشت‌خورده توی لیست «خریدهای من» می‌موند، فقط با کلیک روش («جزئیات») درست مخفی می‌شد (پیام «سفارش یافت نشد»، چون `cb_order_detail` فیلترش داشت). رفع: فیلتر استاندارد `AND COALESCE(status,'active') != 'returned'` اضافه شد.
2. **قطعهٔ کاملاً غایب — بستن تیکت راه‌اندازی محصول:** برای محصولاتی که از مسیر «راه‌اندازی» (`type_="product_setup"`، بخش ۲۳ همین سند) عبور می‌کنن، اطلاعات تحویلی (مثلاً apple id/pass) داخل یک گفتگوی تیکت رد و بدل می‌شه، نه یک پیام تحویل مستقیم قابل‌ردیابی در `delivery_messages` (که از قبل موقع برگشت حذف می‌شد). `order_mark_returned_advanced`/`exchange_order` هیچ‌وقت این تیکت‌ها رو لمس نمی‌کردن — یعنی دکمهٔ قدیمی «💬 ادامه گفتگو»/«ارسال اطلاعات» (اگه توی چت کاربر باقی مونده باشه) بعد از برگشت محصول هنوز کار می‌کرد و کاربر می‌تونست به همون مکالمهٔ حاوی اطلاعات اکانتِ برگشت‌خورده وصل بشه.

رفع (هر دو تابع، همون الگوی دقیقاً یکسان که کامنت‌های خودِ `exchange_order` هم بهش اشاره می‌کنن — «دقیقاً همون منطق»): بعد از `UPDATE orders SET status='returned'`، یک `UPDATE tickets SET status='closed', closed_at=?, updated_at=? WHERE order_id=? AND status != 'closed';` هم روی همون اتصال/تراکنش اجرا می‌شه. نتیجه: هر دو نقطهٔ ورود موجود به گفتگوی تیکت (`ticket_v2_open_*`, `ticket_v2_continue_*` در bot.py) از قبل برای تیکت بسته پیام واضح «این گفتگو بسته شده است.» نشون می‌دن — این رفتار از قبل درست بود، فقط تیکت هیچ‌وقت واقعاً بسته نمی‌شد.

⚠️ **محدودیت شناخته‌شده، عمداً مستندشده نه رفع‌شده:** این رفع مکالمهٔ تیکت رو *غیرقابل‌ادامه* می‌کنه و از لیست‌های آیندهٔ فعال مخفیش می‌کنه، ولی **پیام‌های خام قبلی که تلگرام از قبل توی چت کاربر نشون داده رو پاک نمی‌کنه** — چون Telegram Bot API فقط اجازهٔ حذف پیام‌های خودِ ربات تا ۴۸ ساعت بعد از ارسال رو می‌ده، و مهم‌تر، این پروژه هیچ‌جا `message_id` پیام‌های ارسالی داخل تیکت (چه از بات چه از پنل) رو ذخیره نمی‌کنه تا بشه بعداً برای حذف بهش رفرنس داد (فقط `delivery_messages`، مسیر تحویل مستقیم غیرتیکتی، این رفرنس رو داره). اگه بعداً نیاز به حذف واقعی پیام‌های تاریخی شد، باید یه ستون `telegram_message_id` به `ticket_messages` اضافه بشه (هم برای پیام‌های ادمین هم پیام‌های ارسالی خودکار) — خارج از اسکوپ این رفع.

**تست انجام‌شده:** هارنس مستقیم — سناریوی کامل «سفارش با تیکت راه‌اندازی → برگشت با `order_mark_returned_advanced`» (تأیید `orders.status='returned'`، `tickets.status='closed'`، ناپدیدی از `get_recent_orders_by_user` و `get_user_orders`)؛ سناریوی مشابه برای `exchange_order` (تأیید بستن تیکت سفارش قدیم + سفارش جدید فعال و در لیست باقی می‌مونه).

فایل‌های تغییرکرده: `db.py`.

---

## ۳۷. پاکسازی خودکار کش و فایل‌های موقت — `/admin/system-cache` (۲۰۲۶-۰۸-۰۶)

مالک پروژه یه بخش کامل توی پنل خواست: زمان‌بندی دلخواه (روزانه/هفتگی/بازهٔ سفارشی)، دکمهٔ «پاکسازی فوری»، نمایش فضای آزادشده + گزارش آخرین اجرا — با تأکید صریح که **هرگز** دیتابیس/بکاپ/تنظیمات/اطلاعات کاربران نباید حذف/تغییر پیدا کنه.

**بررسی صادقانهٔ اسکوپ قبل از کدنویسی:** خوندن مستقیم کد نشون داد این پروژه در عمل تقریباً هیچ کش/فایل‌موقت واقعی تولید نمی‌کنه — نه پوشهٔ staging برای آپلود در حین پردازش، نه فایل لاگ روی دیسک (لاگ‌ها فقط از طریق `logging` استاندارد پایتون، معمولاً به journalctl سرور می‌رن نه فایل)، حتی `tempfile` وارد‌شده در بالای `admin_panel.py` (`import ... tempfile as _tempfile`) هیچ‌جای فایل واقعاً استفاده نمی‌شه. پس دو هدف واقعاً امن و معنادار انتخاب شد، نه یه فیچر «پر و خالی»:
1. **`__pycache__`** — کش بایت‌کد پایتون؛ پایتون خودش دوباره می‌سازتش، صفر ریسک از هر جهت.
2. **آواتار یتیم (`app_media/avatars/`)** — بررسی `POST /me/avatar` (api.py) نشون داد آپلود آواتار خودش موقع جایگزینی، فایل قدیمی با پسوند دیگه رو از قبل پاک می‌کنه (`for old_ext in _AVATAR_EXTS: os.remove(...)`) — پس در عمل این سناریو نادره (فقط اگه رایت فایل موفق بشه ولی `UPDATE users SET avatar_url` بعدش شکست بخوره). همچنان به‌عنوان شبکهٔ ایمنی نگه داشته شد، با انتظار واقع‌بینانه که معمولاً ۰ فایل پیدا کنه.

⚠️ **عمداً خارج از اسکوپ:** بقیهٔ زیرپوشه‌های `app_media` (تصویر محصول/کاور آموزش/گالری/ویدیو — همه از `_save_tutorial_file` عبور می‌کنن) اسکن نمی‌شن؛ چون رفرنس دیتابیسشون شکل‌های متفاوت داره (بعضی ستون ساده، بعضی احتمالاً JSON) و ریسک حذف اشتباه یک فایل زندهٔ نمایش‌داده‌شده به کاربر واقعی، از فایدهٔ آزادسازی چند مگابایت بیشتره. اگه لازم شد، باید با بررسی دقیق‌تر جدا طراحی بشه.

**پیاده‌سازی:**
- `run_cache_cleanup() -> dict`: هدف ۱ با `os.walk` + `shutil.rmtree` (حجم/تعداد قبل از حذف اندازه‌گیری می‌شه). هدف ۲: `SELECT avatar_url FROM users` مجموعهٔ «نگه‌داشتنی»‌ها رو می‌سازه (basename هر URL، بدون query string)؛ هر فایل داخل `avatars/` که در این مجموعه نیست **و** قدیمی‌تر از ۴۸ ساعته (حاشیهٔ ایمنی در برابر race با آپلود تازه) حذف می‌شه. نتیجه در `bot_config` (`CACHE_CLEANUP_LAST_RUN`/`CACHE_CLEANUP_LAST_REPORT` JSON) ذخیره می‌شه.
- زمان‌بندی: `_start_cache_cleanup_thread()` — دقیقاً همون الگوی `_start_auto_backup_thread` (بخش ۱۱ سند اصلی/CLAUDE.md قدیمی، `_time.sleep` تا هدف بعدی، نه cron/APScheduler)؛ از داخل خودِ `_start_auto_backup_thread()` صدا زده می‌شه (یه نقطهٔ استارت مشترک برای همهٔ تردهای پس‌زمینه). سه حالت: `daily`/`weekly`/`interval` (ساعت به ساعت). **پیش‌فرض کاملاً خاموش** (`CACHE_CLEANUP_ENABLED=0`) — الگوی محافظه‌کارانهٔ استاندارد پروژه برای هر رفتار خودکار تازه (مثل `DB_CONNECTION_POOL`، بخش ۲۸ فاز C)؛ حتی وقتی خاموشه، ترد هر ساعت یه‌بار چک می‌کنه که از پنل فعال شده یا نه (بدون نیاز به ری‌استارت سرویس).
- صفحهٔ `/admin/system-cache` (permission تازهٔ `cache_cleanup`، `PERM_LEGACY → database`؛ آیتم سایدبار زیر بخش «سیستم»، کنار «پشتیبان‌گیری»): کارت گزارش آخرین اجرا + دکمهٔ «🧹 پاکسازی فوری کش» (`POST /system-cache/run-now`، همزمان با `run_in_threadpool` تا صفحه بعد از تکمیل واقعی ریدایرکت بشه و گزارش تازه نشون بده)، و فرم تنظیمات زمان‌بندی (`POST /system-cache/save-settings`).

**تست انجام‌شده:** هارنس مستقیم `run_cache_cleanup()` با سه سناریوی آواتار (فایل نگه‌داشتنی چون در `avatar_url` واقعیه، فایل یتیم قدیمی‌تر از ۴۸ ساعت که باید حذف بشه، فایل یتیم تازه که باید فقط به‌خاطر حاشیهٔ سنی رد بشه) — هر سه دقیق مطابق انتظار. تست مستقیم هر سه روت پنل (رندر صفحه، ذخیرهٔ تنظیمات با تأیید persist در `bot_config`، اجرای فوری با تأیید `CACHE_CLEANUP_LAST_RUN`/گزارش صحیح) — سه بار تکرار برای رد کردن flakiness محیط تست.

فایل‌های تغییرکرده: `admin_panel.py`.

---

## ۳۸. یکسان‌سازی جداکنندهٔ هزارگان نمایش + پذیرش رقم فارسی/عربی/لاتین در ورودی مبلغ (۲۰۲۶-۰۸-۰۶)

مالک پروژه خواست همه‌جای پروژه (ربات/پنل/مینی‌اپ) دو چیز یکسان بشه: (۱) نمایش مبلغ همیشه با جداکنندهٔ هزارگان (۱۰۰,۰۰۰ نه ۱۰۰۰۰۰)، (۲) ورودی عددی کاربر/ادمین چه با کیبورد فارسی چه لاتین تفاوتی برای محاسبه نداشته باشه.

**بررسی موضوع ۱ (نمایش):** بررسی مستقیم کد نشون داد این از قبل به‌طور گسترده رعایت شده — همه‌جای `admin_panel.py` که مبلغ نمایش داده می‌شه از format spec پایتون `:,}` استفاده می‌کنه (مثلاً `{int(o['price']):,}`)، و پچ سراسری اعداد فارسی (بخش ۱۶ قانون ۱) این جداکننده رو هم به رقم فارسی تبدیل می‌کنه. نیازی به تغییر نبود.

**رفع موضوع ۲ (پذیرش ورودی) — دو باگ واقعی پیدا و رفع شد:**
- **مینی‌اپ (`app/app.js`):** ۴ نقطهٔ ورودی مبلغ/شماره‌کارت (شارژ کیف‌پول، انتقال به کیف‌پول اصلی، شمارهٔ کارت بانکی همکار، مبلغ درخواست تسویه) مقدار ورودی رو با `.replace(/[^0-9]/g,'')` می‌خوندن — این رجکس فقط ارقام اسکی ۰-۹ رو نگه می‌داره؛ ارقام فارسی/عربی (که یونیکد جدایی دارن، خارج از بازهٔ `0-9`) به‌جای تبدیل، **کاملاً حذف** می‌شدن — یعنی کاربری که با کیبورد فارسی «۱۰۰۰۰» تایپ می‌کرد، مقدار خونده‌شده خالی/صفر می‌شد. رفع: تابع تازهٔ `digitsOnly(s)` (تبدیل ارقام فارسی ۰۶F0-۰۶F9 و عربی ۰۶۶۰-۰۶69 به لاتین، بعد حذف هر کاراکتر غیرعددی باقی‌مونده) — هر ۴ نقطه از این استفاده می‌کنن.
- **ربات (`bot.py`):** سه هندلر مبلغ (`process_wallet_charge_amount`, `handle_card2card_amount`, `handle_crypto_amount`) هرکدوم یه زیرمجموعهٔ ناقص و متفاوت از سه جداکنندهٔ رایج هزارگان (`,` لاتین، `،` کاما عربی U+060C، `٬` جداکنندهٔ هزارگان عربی U+066C) رو دستی strip می‌کردن — مثلاً یکی `,`+`،` می‌گرفت ولی `٬` نه، یکی دیگه `,`+`٬` می‌گرفت ولی `،` نه. تابع مشترک تازهٔ `parse_amount(text)` (کنار `safe_int` موجود) هر سه جداکننده رو یکسان حذف می‌کنه؛ برای خودِ رقم فارسی/عربی نیازی به تبدیل دستی نبود — `int()` پایتون خودش از هر رقم دستهٔ یونیکد Nd (هم فارسی هم عربی) پشتیبانی می‌کنه (تأیید مستقیم: `int('۱۴۵')==145` و `int('١٤٥')==145`)، فقط جداکننده باید حذف بشه. هر سه هندلر حالا از `parse_amount` استفاده می‌کنن؛ منطق/پیام‌های خطای موجود هرکدوم دست‌نخورده موند.

⚠️ **اسکوپ‌بندی صریح — بخش سوم که عمداً در این دور دست نخورد:** ۵۱ فیلد `<input type="number">` مبلغ در `admin_panel.py` (قیمت محصول، اعتبار/بدهی کیف‌پول، تنظیمات کمیسیون، ...) هنوز به الگوی `type="text" inputmode="decimal"` تبدیل نشدن — همون الگویی که قبلاً فقط برای بخش کارشناسی آیفون پیاده شده بود (بخش ۲۲.۷) چون `type="number"` روی کیبورد فارسی اصلاً اجازهٔ تایپ رقم فارسی رو نمی‌ده (محدودیت سطح مرورگر، نه چیزی که سمت سرور قابل جبران باشه). **نکتهٔ فنی مهم برای اجرای این کار در آینده:** خودِ backend این ۵۱ فیلد نیازی به تغییر نداره — چون `int()`/Pydantic (که `Form(...): int` رو باهاش می‌خونه) از قبل رقم فارسی/عربی رو می‌پذیره؛ تنها مشکل واقعی، فیلتر کردن کیبورد در سطح خودِ `<input type="number">` مرورگره. دلیل عدم اقدام در همین دور: این ۵۱ مورد پراکنده‌ان روی فرم‌های کاملاً متفاوت، خیلی‌هاشون attribute های `min`/`max`/`step` دارن که با `type="number"` معنای اعتبارسنجی مرورگری دارن (مثلاً `max="90"` برای درصد تخفیف) و با تبدیل ساده به `type="text"` این اعتبارسنجی بومی از دست می‌ره مگه با JS جایگزین بشه — یعنی یه sed خام روی هر ۵۱ خط، ریسک شکستن اعتبارسنجی فرم‌های مالی حساس (کیف‌پول، قیمت‌گذاری) رو داره، بدون تست جدا برای هرکدوم. اگه در آینده خواسته شد، باید فرم‌به‌فرم (نه یکجا) با تست مستقیم هر روت انجام بشه.

**تست انجام‌شده:** تست مستقیم Node.js روی `digitsOnly()` (۹ سناریو: رقم فارسی خالص، لاتین خالص، عربی خالص، رقم فارسی+کاما، رقم+حروف/فاصلهٔ مخلوط، ورودی خالی/null) — همه مطابق انتظار. تست مستقیم پایتون روی `parse_amount()` (۱۳ سناریو شامل هر سه نوع جداکننده با رقم فارسی، ورودی نامعتبر، منفی، صفر) — همه مطابق انتظار. سینتکس کامل `bot.py` (`ast.parse`) و `app/app.js` (`node -c`).

فایل‌های تغییرکرده: `bot.py`، `app/app.js`.

---

## ۳۹. تکمیل واقعیِ درخواست «کاربر غیرهمکار در چرخهٔ معرفی/پاداش باشه، فقط پول نگیره» (۲۰۲۶-۰۸-۰۶)

این ادامهٔ همون درخواستی‌ست که در بخش ۳۰.۴ یه‌بار «بررسی شد، نیازی به تغییر نبود» نتیجه‌گیری شده بود — ولی اون بررسی روی تابع اشتباه (`process_referral_reward`، که معلوم شد **هیچ caller‌ی در کل پروژه نداره، کد کاملاً مرده‌ست**) انجام شده بود، نه تابع واقعاً زندهٔ پاداش عضویت (`pay_signup_referral_reward`، صدا زده‌شده از `bot.py`/`admin_panel.py`). با خوندن مستقیم کد (نه اعتماد به تحلیل قبلی)، دو باگ واقعی پیدا شد که دقیقاً توضیح می‌دن چرا مالک پروژه گزارش داد «کاربر غیرهمکار در چرخه دیده نمی‌شه»:

1. **`bot.py:_send_invite_view` — کاربر عادی اصلاً لینک شخصیِ قابل‌ردیابی نمی‌گرفت.** حالت غیرهمکار فقط لینک عمومی ربات (`https://t.me/{bot}`، بدون `?start=ref_...`) رو نشون می‌داد. چون ثبت هر معرفی (`register_referral`) فقط از مسیر `/start ref_{referrer_id}` اتفاق می‌افته، کاربر عادی که این لینک رو نداشت، هیچ‌وقت هیچ ردیف `referrals` براش ساخته نمی‌شد — یعنی دعوت‌هاش از همون ابتدا **اصلاً وارد چرخه نمی‌شدن**، نه این‌که «توی چرخه بودن ولی پول نمی‌گرفتن». ⚠️ نکتهٔ مهم: مینی‌اپ (`GET /me/invite`، api.py) از قبل این باگ رو نداشت — همیشه برای «چه همکار باشد چه کاربر عادی» لینک واقعی می‌ده؛ یعنی این یه ناهماهنگی بین بات و مینی‌اپ بود، نه یه محدودیت طراحی‌شده در کل پروژه.
2. **`db.py:pay_signup_referral_reward` — پرچم `rewarded=1` حتی وقتی پولی واریز نمی‌شد ست می‌شد.** چک `_is_approved_partner(referrer_id)` *بعد* از `UPDATE referrals SET rewarded=1...` بود؛ یعنی وقتی معرف همکار نبود، تابع پولی نمی‌داد ولی همون ردیف رو برای همیشه «قبلاً جایزه گرفته» علامت می‌زد. نتیجه: حتی اگه اون کاربر بعداً همکار می‌شد، دیگه هیچ‌وقت واجد شرایط این پاداش نمی‌شد (چون شرط `WHERE rewarded=0` دیگه true نبود) — دقیقاً **برعکس** خواستهٔ مالک پروژه («وقتی همکار شد... پاداش براش محاسبه بشه»).

**رفع:**
- `_send_invite_view`: هر دو حالت (همکار/کاربر عادی) حالا لینک شخصی واقعی می‌گیرن — دقیقاً هماهنگ با `GET /me/invite`. تنها فرق باقی‌مونده بین دو حالت، فقط متنه: کاربر عادی پیام «برای دریافت پاداش/پورسانت این دعوت‌ها، درخواست همکاری ثبت کنید — بعد از تأیید، حتی دعوت‌های همین الان هم محاسبه می‌شود» می‌بینه.
- `pay_signup_referral_reward`: چک `_is_approved_partner` به **اول** تابع منتقل شد (قبل از هر `UPDATE`ای) — اگه معرف همکار نباشه، هیچ تغییری روی ردیف `referrals` اعمال نمی‌شه (نه `rewarded`، نه `reward_amount`)، پس ردیف همچنان واجد شرایط ارزیابی آینده می‌مونه.
- تابع تازهٔ `db.py:_pay_pending_referral_rewards_for(referrer_id)` — **مکانیزم جبرانی**: بعد از `approve_partner()`، خودکار همهٔ ردیف‌های `referrals WHERE referrer_id=X AND rewarded=0` رو دوباره از `pay_signup_referral_reward` رد می‌کنه؛ یعنی معرفی‌هایی که قبل از همکار شدن ثبت شده بودن (طبق رفع بند ۱، حالا واقعاً ثبت می‌شن)، دقیقاً همون لحظهٔ تأیید همکاری، پاداششون محاسبه/واریز می‌شه. این دقیقاً «وقتی که درخواست همکاری داد و همکار شد بیاد تو چرخه و پاداش... براش محاسبه بشه» رو پیاده می‌کنه.
- `admin_panel.py:/partners/{uid}/approve` — قبلاً `UPDATE partners SET status='approved'...` رو مستقیم/جدا اجرا می‌کرد (بدون این کچ‌آپ). حالا از `db.approve_partner()` استفاده می‌کنه — یعنی هر دو مسیر تأیید همکار (این‌لاین بات + پنل وب) دقیقاً یک منطق دارن، بدون نیاز به دوبار پیاده‌سازی کچ‌آپ.

**بررسی شد، نیازی به تغییر نبود:** `process_referral_commission` (پورسانت مستمر هر خرید بعدی، نه پاداش یک‌بارهٔ عضویت) از قبل کاملاً درست بود — چون ارزیابیش **در لحظهٔ هر خرید** انجام می‌شه (نه یه پرچم یک‌بارمصرف)، به‌محض این‌که معرف همکار بشه، خریدهای *بعدیِ* زیرمجموعه‌اش خودکار پورسانت تولید می‌کنن، بدون نیاز به هیچ کچ‌آپی. آمار/نمودار درختی ادمین (`_build_partner_tree`، `/admin/partners` تب «🌳 درخت همکاران») و تیم فروش همکار (`get_partner_team_stats`) هم از قبل کاربران غیرهمکار رو درست نشون می‌دادن (بدون فیلتر روی جدول `partners`) — این دو مصرف‌کننده هیچ‌وقت باگ نداشتن، فقط چون خودِ ردیف `referrals` (به‌خاطر بند ۱) هیچ‌وقت ساخته نمی‌شد، چیزی برای نشون‌دادن نبود.

**تست انجام‌شده:** هارنس مستقیم — سناریوی کامل «معرفی توسط کاربر غیرهمکار → تلاش پرداخت پاداش (رد می‌شه، `rewarded` دست‌نخورده می‌مونه) → تأیید همکاری → کچ‌آپ خودکار (پاداش واریز می‌شه، `rewarded=1`) → تلاش دوبارهٔ پرداخت (idempotent، بدون پرداخت مضاعف)»؛ تست مستقل `_send_invite_view` (مانیتور مستقیم `bot.send_message`) برای هر دو حالت همکار/غیرهمکار — تأیید لینک واقعی در هر دو، تأیید تفاوت فقط در متن؛ تست کامل روت پنل `/partners/{uid}/approve` (تأیید کچ‌آپ از طریق مسیر پنل هم کار می‌کنه).

فایل‌های تغییرکرده: `bot.py`، `db.py`، `admin_panel.py`.

---

## ۴۰. رفع ریشه‌ای سیستم برگشت محصول — «بازگشت به موجودی» بی‌اثر + پیام تحویل غیرقابل‌حذف از چت (۲۰۲۶-۰۸-۰۶)

مالک پروژه گزارش داد بعد از این‌که در بخش ۳۶ بستن تیکت راه‌اندازی رو رفع کردیم، هنوز پیام تحویل از چت کاربر پاک نمی‌شه؛ و مهم‌تر، یک محصول واقعی رو با گزینهٔ «بازگشت به موجودی» برگشت زده و به فید فروش برنگشته. خواست از صفر تا صد این بخش (همهٔ گزینه‌های تعریف‌شده در فرم برگشت/تعویض) بررسی و درست بشه، بدون بازطراحی UI، به‌علاوهٔ تضمین این‌که هر اتفاقی برای کاربر پیش میاد (برگشت پول، کسر پول، تعویض) اطلاع‌رسانی بشه.

### ریشهٔ واقعی مشکل — پیدا شد با خوندن مستقیم هر سه مسیر تحویل، نه با حدس

`order_mark_returned_advanced`/`exchange_order` برای پیدا کردن `feed_id` سفارش، فقط دو منبع رو چک می‌کردن: ستون `orders.feed_id` (که فقط با فراخوانی صریح `order_set_feed_id()` پر می‌شه) و جدول `delivery_messages` (که فقط با یه INSERT دستی پر می‌شه). بررسی هر سه مسیر واقعی تحویل نشون داد **هیچ‌کدوم این دو رو به‌طور کامل پر نمی‌کردن**:

| مسیر تحویل | `order_set_feed_id` | `delivery_messages` INSERT |
|---|---|---|
| `bot.py:finalize_product_order` (خرید مستقیم کیف‌پولی از بات — پرمصرف‌ترین مسیر) | ❌ اصلاً صدا زده نمی‌شد | ❌ اصلاً درج نمی‌شد |
| `payment_service.py:_finalize_paid_tx` (پرداخت درگاه/ترکیبی) | ❌ اصلاً صدا زده نمی‌شد | ❌ اصلاً درج نمی‌شد |
| `api.py:_deliver_or_queue_order` (چک‌اوت مینی‌اپ) | ✅ صدا زده می‌شد | ❌ درج نمی‌شد |

(تابع `_send_delivery_to_user` در `bot.py` هر دو کار رو درست انجام می‌داد، ولی معلوم شد **کد کاملاً مرده‌ست** — تنها caller‌اش `try_dispatch_pending_for_product` هست که خودش از مسیر خرید عادی دیگه صدا زده نمی‌شه، بخش ۲۳.)

نتیجه: برای اکثریت قریب‌به‌اتفاق سفارش‌ها (خرید مستقیم کیف‌پولی، پرتکرارترین مسیر)، `feed_id` هیچ‌وقت قابل‌کشف نبود — یعنی بلوک «بازگشت به موجودی» تو در `order_mark_returned_advanced` بی‌صدا skip می‌شد (نه خطا، نه لاگ)، و `chat_id`/`message_id` همیشه `None` بودن یعنی `_tg_delete_message` هیچ‌وقت واقعاً صدا زده نمی‌شد.

### رفع

**۱) Reverse lookup مستقیم روی `product_feed.order_id` — رفع فوری، بدون نیاز به تغییر مسیرهای تحویل:** `claim_next_feed_item` (db.py) از قبل و همیشه `product_feed.order_id` رو در لحظهٔ claim ست می‌کنه (`UPDATE product_feed SET delivered=1, order_id=?, ... WHERE id=?`) — این تنها منبعیه که **بدون استثنا** برای هر سه مسیر همیشه درست پر می‌شه. `order_mark_returned_advanced`/`exchange_order` حالا اول `SELECT id FROM product_feed WHERE order_id=?` رو چک می‌کنن (اولویت اول)، بعد `orders.feed_id`، بعد `delivery_messages` (fallback). این یه تغییر جبراً هم برای سفارش‌های **جدید** هم **قدیمی** (از قبل ثبت‌شده در دیتابیس) کار می‌کنه — نیازی به مهاجرت دیتا نیست.

**۲) هر سه مسیر تحویل حالا `orders.feed_id` + `delivery_messages` رو کامل ثبت می‌کنن (برای این‌که «حذف پیام از چت» هم واقعاً کار کنه، نه فقط بازگشت به موجودی):**
- `bot.py:finalize_product_order` — بعد از `bot.send_message(...)`، مقدار برگشتی (شیء Message، شامل `message_id`) گرفته می‌شه، `order_set_feed_id()` صدا زده می‌شه، و ردیف `delivery_messages` درج می‌شه.
- `payment_service.py:_finalize_paid_tx` — چون wrapper محلی `send_telegram_message()` فقط `bool` برمی‌گردوند (نه `message_id`)، تابع تازهٔ `tg_notify.send_telegram_message_with_id()` اضافه شد (امضای `send_telegram_message` اصلی دست‌نخورده موند تا caller های دیگه‌اش نشکنن) و همین‌جا استفاده می‌شه.
- `api.py:_deliver_or_queue_order` — از همون `send_telegram_message_with_id` تازه استفاده می‌کنه (قبلاً فقط `order_set_feed_id` رو صدا می‌زد، `delivery_messages` رو نه).
- `admin_panel.py:order_resend_post` («ارسال مجدد» بعد از یه برگشت قبلی) هم همین الگو رو گرفت — قبلاً با `_tg_send` (بدون message_id) می‌فرستاد، یعنی اگه همین سفارش دوباره برگشت می‌خورد، پیام تازه قابل حذف نبود.

**۳) `delivery_messages` از جدول لیزی (فقط داخل خودِ `order_mark_returned_advanced` ساخته می‌شد) به جدول هستهٔ ایگر در `init_db()` منتقل شد** — طبق قاعدهٔ استاندارد پروژه (بخش ۷). قبلاً روی یه دیتابیس کاملاً تازه، اگه اولین خرید قبل از اولین «برگشت» ادمین اتفاق می‌افتاد، INSERT مسیرهای تحویل با «no such table» بی‌صدا شکست می‌خورد.

**۴) تکمیل نوتیف کاربر:** حالت `wallet_action=custom_deduct` در فرم برگشت هیچ پیامی به کاربر نمی‌فرستاد (فقط `full`/`custom_add` پیام داشتن). رفع شد — حالا از `result["wallet_delta"]` واقعی (نه بازسازی از فیلدهای فرم) استفاده می‌کنه، دقیقاً همون الگوی از قبل درستِ روت `exchange`. روت `exchange` از قبل کامل بود (حذف پیام قدیم + نوتیف با اختلاف قیمت + تحویل محصول جدید) — نیازی به تغییر نداشت.

⚠️ **محدودیت باقی‌مانده، عمداً مستندشده:** پیام‌های تحویلی که **قبل از این رفع** ارسال شدن، `message_id`شون هیچ‌جا ثبت نشده و قابل‌بازیابی نیست — برای سفارش‌های *قدیمی*، حذف خودکار از چت هنوز ممکن نیست (فقط بازگشت به موجودی، که reverse lookup جدید حلش کرده، چون اون به `product_feed.order_id` وابسته‌ست نه به پیام تلگرام). برای سفارش‌های *از این به بعد*، هر دو قابلیت کامل کار می‌کنن.

**تست انجام‌شده:** هارنس مستقیم — بازتولید دقیق باگ گزارش‌شده (claim بدون ثبت `orders.feed_id`/`delivery_messages`، دقیقاً مثل مسیر قدیمی بات) و تأیید رفع؛ تست end-to-end هر سه مسیر تحویل (بات/درگاه/مینی‌اپ) از تحویل تا برگشت با تأیید بازگشت موجودی + `chat_id`/`message_id` صحیح؛ تست کامل روت پنل `order_return` با ۳ سناریو (restore+custom_deduct با تأیید نوتیف تازه، delete permanent با تأیید حذف واقعی از فید بدون اثر روی آیتم‌های دیگه، ری‌فاند کامل)؛ تست `order_resend_post` با تأیید ثبت `delivery_messages`. سینتکس کامل هر ۶ فایل تغییرکرده.

فایل‌های تغییرکرده: `db.py`، `bot.py`، `payment_service.py`، `api.py`، `tg_notify.py`، `admin_panel.py`.

---

## ۴۱. استاندارد وضعیت پرداخت برای تحویل‌های اصلاحی/تعویضی + تکمیل نوتیف صفحهٔ «ارسال مجدد» (۲۰۲۶-۰۸-۰۶)

مالک پروژه بعد از تأیید رفع بخش ۴۰ (بازگشت به موجودی درست کار می‌کنه) گزارش داد وقتی از صفحهٔ «ارسال مجدد» یه آیتم جایگزین فرستاده، هیچ‌جا ازش پرسیده/تأیید نشده که این آیتم از موجودی کم بشه یا نه — و خواست یه «استاندارد» تعریف بشه که همیشه روشن باشه آیا کاربر بابت کالایی که الان دریافت می‌کنه پرداخت اضافی کرده یا نه.

**تأیید فنی قبل از هر تغییر:** بررسی مستقیم `order_resend_post` (و `exchange_order`) نشون داد **کسر موجودی از قبل درست انجام می‌شد** (`UPDATE product_feed SET delivered=1 ...`، تست مستقیم با هارنس تأیید کرد stock واقعاً کم می‌شه) — این یه باگ واقعی نبود، بلکه یه **رخنهٔ دید (visibility gap)**: نه دیالوگ تأییدی وجود داشت، نه هیچ ردی در لیست سفارش‌ها از این‌که یه سفارش خاص «اصلاح‌شده» (بدون پرداخت اضافی) بوده یا «طرف جدید یک تعویض» (با تسویهٔ اختلاف قیمت مستقل).

**رفع:**
- ستون تازهٔ `orders.resent_at` (مهاجرت استاندارد ALTER، کنار `exchange_pair_id`) — وقتی ادمین از «ارسال مجدد» استفاده می‌کنه، این ستون ست می‌شه.
- `order_resend_post`: پیام flash حالا صریحاً تأیید می‌کنه «آیتم از موجودی کم شد، بدون پرداخت اضافی از کاربر» — پاسخ مستقیم به «از من نپرسید».
- لیست سفارش‌ها (`/admin/orders`): تابع تازهٔ `payment_note(o)` زیر بج وضعیت (فعال/برگشتی) یه بج کوچیک دوم اضافه می‌کنه:
  - سفارشی که `resent_at` داره → «♻️ اصلاح‌شده — بدون پرداخت اضافی»
  - سفارشی که طرف جدید یک تعویضه (`exchange_pair_id` ست و `status != returned`) → «🔁 از تعویض سفارش #X» (قیمتش با `wallet_delta` موقع تعویض تسویه شده، مستقل قابل‌ردیابیه)
  - سفارش عادی → بدون بج اضافه (خودِ ستون «مبلغ» دقیقاً چیزیه که پرداخت شده)

این سه حالت با هم دقیقاً همون «استاندارد» درخواستی رو تشکیل می‌دن — با نگاه به لیست سفارش‌ها، همیشه روشنه این تحویل مستقل/پرداخت‌شده بوده، اصلاحیهٔ رایگان بوده، یا نتیجهٔ یه تعویض با تسویهٔ جدا.

**تست انجام‌شده:** هارنس مستقیم — سناریوی کامل «ارسال مجدد → تأیید `resent_at` ست شده → رندر واقعی صفحهٔ `/admin/orders` → تأیید نمایش بج "اصلاح‌شده"» + «تعویض → تأیید سفارش جدید `exchange_pair_id` درست → تأیید نمایش بج "از تعویض سفارش #X"» — هر دو در HTML واقعی رندرشده تأیید شدن، نه فقط دیتابیس.

فایل‌های تغییرکرده: `db.py`، `admin_panel.py`.
