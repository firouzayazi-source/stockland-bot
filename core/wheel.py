"""سرویس گردونهٔ شانس — منطق خالص، تک‌منبع حقیقت برای انتخاب/صدور جایزه.

معماری (طبق CLAUDE.md، بخش «گردونهٔ شانس»):
  wheel_campaigns (فقط یکی هم‌زمان فعال) → wheel_prizes (کاملاً از پنل، بدون Hard
  Code) → این ماژول جایزه رو سمت سرور انتخاب/صادر می‌کنه → wheel_spins (لاگ کامل).
جایزهٔ کیف‌پول از core/wallet.py؛ جایزهٔ کد تخفیف از db.issue_personal_discount_code
(همون موتور discount_codes موجود، نه سیستم موازی). Frontend فقط انیمیشن اجرا
می‌کنه و هیچ کنترلی روی نتیجه نداره — همه‌چیز این‌جا، سمت سرور، تصمیم می‌شه.
"""
import random


# ─── جایزهٔ «بدون برد» پیش‌فرض — وقتی همهٔ جوایز محدود تمام شدن (edge-case
# آماری تقریباً غیرممکن) یا کمپینی هیچ جایزه‌ای تعریف نکرده — تا کاربر هیچ‌وقت
# پاسخ ۵۰۰/خالی نگیره، بلکه یه نتیجهٔ «بدون برد» معتبر می‌بینه. */
_FALLBACK_PRIZE = {
    "id": None, "title": "بدون برد", "icon": "😅", "color": "#6B7280",
    "prize_type": "no_win", "value": 0, "max_discount_value": 0,
    "validity_hours": 0, "total_limit": 0, "description": "",
}


def _effective_usage_date(reset_hour: int) -> str:
    """تاریخ «روز مؤثر» طبق ساعت ریست دلخواه ادمین — پیش‌فرض reset_hour=0 یعنی
    نیمه‌شب معمولی؛ reset_hour=6 یعنی روز از ساعت ۶ صبح شروع می‌شه، نه نیمه‌شب."""
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    shifted = now - timedelta(hours=int(reset_hour or 0))
    return shifted.date().isoformat()


def _weighted_pick(candidates: list) -> dict:
    total = sum(max(0.0, float(c.get("weight") or 0)) for c in candidates)
    if total <= 0:
        return random.choice(candidates)
    r = random.uniform(0, total)
    upto = 0.0
    for c in candidates:
        upto += max(0.0, float(c.get("weight") or 0))
        if upto >= r:
            return c
    return candidates[-1]


def get_state(user_id: int = None) -> dict:
    """وضعیت گردونه برای رندر UI مینی‌اپ — تنظیمات، کمپین فعال، جوایز نمایشی،
    و تعداد چرخش باقیماندهٔ همین کاربر امروز."""
    import db
    settings = db.get_wheel_settings()
    campaign = db.get_active_wheel_campaign()
    result = {
        "enabled": bool(settings.get("enabled")),
        "settings": settings,
        "campaign": None,
        "prizes": [],
        "spins_remaining": 0,
        "can_spin": False,
    }
    if not result["enabled"] or not campaign:
        return result
    prizes = db.list_wheel_prizes(campaign["id"], active_only=True)
    total_weight = sum(max(0.0, float(p.get("weight") or 0)) for p in prizes) or 1
    show_odds = bool(settings.get("show_odds"))
    prize_list = []
    for p in prizes:
        item = {
            "id": p["id"], "title": p["title"], "icon": p["icon"], "color": p["color"],
            "prize_type": p["prize_type"], "sort_order": p["sort_order"],
            "image_url": p.get("image_url") or "",
        }
        if show_odds:
            item["percent"] = round(100 * (float(p.get("weight") or 0) / total_weight), 1)
        prize_list.append(item)
    daily_limit = campaign.get("daily_spin_limit")
    if daily_limit is None:
        daily_limit = int(settings.get("daily_spin_limit") or 1)
    usage_date = _effective_usage_date(settings.get("reset_hour"))
    remaining = -1
    if user_id:
        remaining = db.get_wheel_spins_remaining_today(user_id, campaign["id"], usage_date, daily_limit)
    result.update({
        "campaign": {"id": campaign["id"], "title": campaign["title"],
                     "ends_at": campaign.get("ends_at")},
        "prizes": prize_list,
        "spins_remaining": remaining,
        "can_spin": bool(prize_list) and (remaining != 0),
    })
    return result


def _replay_terminal_spin(row: dict, campaign: dict, daily_limit: int, usage_date: str) -> dict:
    """بازپخش نتیجهٔ یه spin قبلاً تکمیل‌شده (idempotent replay) — برای دبل‌کلیک/
    ریترای شبکه با همون client_request_id. جزئیات نمایشی (آیکون/رنگ/توضیح) از خودِ
    جایزه اگه هنوز موجود باشه؛ چون prize_title/prize_type/amount/discount_code از
    قبل در خودِ ردیف wheel_spins denormalized شدن، حتی اگه جایزه بعداً حذف/ویرایش
    بشه، بازپخش هنوز درست کار می‌کنه."""
    import db
    if row["status"] == "failed":
        return {"ok": False, "error": "صدور این جایزه با خطا مواجه شد — لطفاً دوباره تلاش کنید",
                "duplicate": True}
    prize_row = db.get_wheel_prize(row["prize_id"]) if row.get("prize_id") else None
    icon = (prize_row or {}).get("icon") or ("😅" if row["prize_type"] == "no_win" else "🎁")
    color = (prize_row or {}).get("color") or "#6B7280"
    description = (prize_row or {}).get("description") or ""
    image_url = (prize_row or {}).get("image_url") or ""
    from core import wallet
    remaining = db.get_wheel_spins_remaining_today(row["user_id"], campaign["id"], usage_date, int(daily_limit or 0))
    expires_at = None
    if row.get("discount_code_id"):
        codes = db.list_user_personal_codes(row["user_id"])
        match = next((c for c in codes if c["id"] == row["discount_code_id"]), None)
        if match:
            expires_at = match.get("expires_at")
    return {
        "ok": True,
        "duplicate": True,
        "prize": {
            "id": row.get("prize_id"), "title": row.get("prize_title") or "", "icon": icon,
            "color": color, "prize_type": row["prize_type"], "image_url": image_url,
            "amount": row.get("amount") or 0, "discount_code": row.get("discount_code") or "",
            "expires_at": expires_at, "description": description,
        },
        "wallet_balance": wallet.get_balance(row["user_id"]) if row["prize_type"] == "wallet_credit" else None,
        "spins_remaining": remaining,
    }


def spin(user_id: int, ip: str = "", device_fingerprint: str = "", session_id: str = "",
         client_request_id: str = "") -> dict:
    """چرخش اتمیک — تنها نقطهٔ ورودی که یه جایزه صادر می‌کنه. همیشه سمت سرور تصمیم
    می‌گیره؛ هیچ ورودی کلاینتی روی نتیجه اثر نداره (ip/device/session فقط برای لاگ
    ضدتقلبن، نه ورودی تصمیم‌گیری).

    Idempotency: اگه client_request_id داده بشه (کلاینت یه UUID تازه به‌ازای هر
    کلیک واقعی روی دکمهٔ چرخش می‌سازه)، دبل‌کلیک/ریترای شبکهٔ همون درخواست هیچ‌وقت
    باعث مصرف دوبارهٔ سهمیهٔ روزانه یا صدور دوبارهٔ جایزه نمی‌شه — رزرو اتمیک (یکتای
    user_id+client_request_id در wheel_spins) *قبل* از مصرف سهمیه/انتخاب جایزه
    انجام می‌شه، پس هیچ جایزه‌ای صادر نمی‌شه مگه رزرو موفق شده باشه."""
    import db, time
    settings = db.get_wheel_settings()
    if not settings.get("enabled"):
        return {"ok": False, "error": "گردونهٔ شانس در حال حاضر غیرفعال است"}
    campaign = db.get_active_wheel_campaign()
    if not campaign:
        return {"ok": False, "error": "در حال حاضر کمپین فعالی برای گردونه وجود ندارد"}

    daily_limit = campaign.get("daily_spin_limit")
    if daily_limit is None:
        daily_limit = int(settings.get("daily_spin_limit") or 1)
    usage_date = _effective_usage_date(settings.get("reset_hour"))

    client_request_id = (client_request_id or "").strip()[:120]
    reservation_id = None
    if client_request_id:
        existing = db.get_wheel_spin_by_request_id(user_id, client_request_id)
        if existing is None:
            reserve = db.reserve_wheel_spin(user_id, campaign["id"], client_request_id,
                                             ip, device_fingerprint, session_id)
            if reserve["ok"]:
                reservation_id = reserve["spin_id"]
            else:
                # باخت مسابقهٔ رزرو — یه درخواست هم‌زمان دیگه با همون شناسه زودتر رزرو کرد.
                existing = db.get_wheel_spin_by_request_id(user_id, client_request_id)
        if reservation_id is None:
            # درخواست تکراریه (یا رزرو موجود بود، یا مسابقهٔ رزرو رو باختیم) — اگه
            # هنوز pending (در حال پردازش هم‌زمان توسط یه ریکوئست دیگه)، کمی صبر کن.
            for _ in range(20):
                if existing is None or existing["status"] != "pending":
                    break
                time.sleep(0.1)
                existing = db.get_wheel_spin_by_request_id(user_id, client_request_id)
            if existing is None:
                return {"ok": False, "error": "خطا در ثبت درخواست — دوباره تلاش کنید"}
            if existing["status"] == "pending":
                return {"ok": False, "error": "درخواست قبلی هنوز در حال پردازش است"}
            return _replay_terminal_spin(existing, campaign, int(daily_limit or 0), usage_date)

    consume = db.try_consume_wheel_spin(user_id, campaign["id"], usage_date, int(daily_limit or 0))
    if not consume["ok"]:
        if reservation_id:
            db.finalize_wheel_spin(reservation_id, prize_type="", prize_title="", status="failed")
        return {"ok": False, "error": "چرخش امروز شما تمام شده — فردا دوباره امتحان کنید", "spins_remaining": 0}

    prizes = db.list_wheel_prizes(campaign["id"], active_only=True)
    pool = []
    for p in prizes:
        if p["total_limit"] and p["issued_count"] >= p["total_limit"]:
            continue
        if p["daily_limit"] and db.count_wheel_prize_issued_today(p["id"]) >= p["daily_limit"]:
            continue
        pool.append(p)

    chosen = None
    while pool:
        candidate = _weighted_pick(pool)
        if candidate["total_limit"] and candidate["total_limit"] > 0:
            if not db.try_claim_wheel_prize_slot(candidate["id"]):
                pool = [p for p in pool if p["id"] != candidate["id"]]
                continue
        chosen = candidate
        break
    if chosen is None:
        chosen = _FALLBACK_PRIZE

    # ─ صدور واقعی جایزه — اگه به هر دلیلی (خطای دیتابیس، ...) شکست بخوره، هیچ‌وقت
    # پیام موفقیت کاذب برنمی‌گردونیم؛ spin با status='failed' ثبت می‌شه تا هم در
    # تاریخچه/جوایز من صادقانه دیده بشه، هم قابل بررسی/ریترای دستی بمونه. توجه:
    # سهمیهٔ روزانه/سهم total_limit جایزه تا این نقطه مصرف شده و rollback نمی‌شه —
    # محدودیت شناخته‌شده و مستندشده (شکست واقعی این‌جا فقط با خطای سطح دیتابیس رخ
    # می‌ده، نه سناریوهای عادی دبل‌کلیک/ریترای که idempotency بالا کامل پوشششون می‌ده).
    try:
        issued = _issue_prize(user_id, campaign, chosen, usage_date)
        failed = False
    except Exception:
        import logging
        logging.getLogger("stockland.wheel").exception(
            "صدور جایزهٔ گردونه شکست خورد — user_id=%s prize_id=%s", user_id, chosen.get("id"))
        issued = {"amount": 0, "discount_code": "", "discount_code_id": None, "expires_at": None}
        failed = True

    final_status = "failed" if failed else "issued"
    if reservation_id:
        db.finalize_wheel_spin(
            reservation_id, prize_id=chosen["id"], prize_type=chosen["prize_type"],
            prize_title=chosen["title"], amount=issued.get("amount", 0),
            discount_code=issued.get("discount_code", ""),
            discount_code_id=issued.get("discount_code_id"), status=final_status,
        )
    else:
        db.insert_wheel_spin(
            user_id=user_id, campaign_id=campaign["id"], prize_id=chosen["id"],
            prize_type=chosen["prize_type"], prize_title=chosen["title"],
            amount=issued.get("amount", 0), discount_code=issued.get("discount_code", ""),
            discount_code_id=issued.get("discount_code_id"), status=final_status,
            ip=ip or "", device_fingerprint=device_fingerprint or "", session_id=session_id or "",
        )

    if failed:
        return {"ok": False, "error": "خطا در صدور جایزه — لطفاً با پشتیبانی تماس بگیرید"}

    remaining = db.get_wheel_spins_remaining_today(user_id, campaign["id"], usage_date, int(daily_limit or 0))
    return {
        "ok": True,
        "prize": {
            "id": chosen["id"], "title": chosen["title"], "icon": chosen["icon"],
            "color": chosen["color"], "prize_type": chosen["prize_type"],
            "image_url": chosen.get("image_url") or "",
            "amount": issued.get("amount", 0), "discount_code": issued.get("discount_code", ""),
            "expires_at": issued.get("expires_at"), "description": chosen.get("description") or "",
        },
        "wallet_balance": issued.get("wallet_balance"),
        "spins_remaining": remaining,
    }


def _issue_prize(user_id: int, campaign: dict, prize: dict, usage_date: str) -> dict:
    """صدور واقعی جایزه بر اساس نوعش. برمی‌گردونه اطلاعات لازم برای پاسخ+لاگ."""
    import db
    ptype = prize["prize_type"]
    out = {"amount": 0, "discount_code": "", "discount_code_id": None, "expires_at": None}

    if ptype == "wallet_credit":
        from core import wallet
        amount = int(prize.get("value") or 0)
        if amount > 0:
            wallet.credit(user_id, amount, reason="جایزهٔ گردونهٔ شانس")
        out["amount"] = amount
        out["wallet_balance"] = wallet.get_balance(user_id)

    elif ptype in ("discount_percent", "discount_fixed"):
        disc_type = "percent" if ptype == "discount_percent" else "fixed"
        result = db.issue_personal_discount_code(
            user_id, disc_type, int(prize.get("value") or 0),
            expire_hours=int(prize.get("validity_hours") or 0),
            max_value=int(prize.get("max_discount_value") or 0),
            min_amount=int(prize.get("min_purchase_amount") or 0),
            description=prize.get("description") or prize["title"],
            source="wheel", source_ref_id=campaign["id"],
        )
        out["discount_code"] = result.get("code", "")
        out["discount_code_id"] = result.get("code_id")
        out["expires_at"] = result.get("expires_at")

    elif ptype == "extra_spin":
        extra = int(prize.get("value") or 1)
        db.grant_extra_wheel_spins(user_id, campaign["id"], usage_date, extra)

    # 'no_win' و 'physical_gift' فقط لاگ می‌شن — physical_gift فعلاً جز اطلاع‌رسانی
    # به ادمین (از طریق تاریخچهٔ پنل) هیچ صدور خودکاری نداره؛ پیاده‌سازی کامل
    # (تماس با کاربر برای آدرس/ارسال) فاز توسعهٔ آینده‌ست، عمداً خارج از این نسخه.

    return out
