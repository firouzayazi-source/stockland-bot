"""
backup_uploader.py — آپلود بکاپ ابری (فاز ۶ — بازطراحی)
────────────────────────────────────────────────────────
دو مقصد:
  1) کانال تلگرام (Chat ID قابل تنظیم از پنل — بدون نیاز به باز کردن چت ربات)
  2) Google Drive با Service Account (JSON از env — بدون OAuth و بدون تعامل)

حذف‌شده‌ها: Microsoft OneDrive، Google OAuth Device Flow

تنظیمات env:
  GDRIVE_SA_JSON   — مسیر فایل JSON سرویس‌اکانت (مثلاً /opt/stockland/gdrive-sa.json)
  GDRIVE_FOLDER_ID — آیدی پوشه مقصد در درایو (پوشه باید با ایمیل سرویس‌اکانت share شده باشد)

اصول:
  - آپلود غیرهمزمان (thread) — ربات هرگز متوقف نمی‌شود
  - در صورت خطا فقط log — بدون توقف
  - بکاپ محلی هرگز حذف نمی‌شود (چرخش محلی جدا مدیریت می‌شود)
  - فقط ۳۰ بکاپ آخر در Drive نگه داشته می‌شود
"""
import os
import json
import time
import base64
import logging
import threading

logger = logging.getLogger("backup_uploader")

RETENTION_DRIVE = 30   # فقط ۳۰ بکاپ آخر در Google Drive
RETENTION_TG    = 10   # پیام‌های قدیمی کانال (حذف از سمت ما ممکن نیست، فقط شمارش)


# ══════════════════════════════════════════════════════════════════════════
# ─── تنظیمات (bot_config) ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def get_cloud_settings() -> dict:
    from db import get_cfg_json
    return get_cfg_json("cloud_backup", {
        "tg_enabled": 0, "tg_channel": "",
        "gdrive_enabled": 0,
        "last_upload_at": "", "last_status": "",
    })


def save_cloud_settings(cfg: dict) -> None:
    from db import set_cfg
    import json as _j
    cur = get_cloud_settings()
    cur.update(cfg)
    set_cfg("cloud_backup", _j.dumps(cur, ensure_ascii=False))


# ══════════════════════════════════════════════════════════════════════════
# ─── مقصد ۱: کانال تلگرام ────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def _up_telegram(filepath: str, cfg: dict) -> dict:
    """ارسال فایل بکاپ به کانال تلگرام با Chat ID — بدون نیاز به چت با ربات."""
    import requests
    from config import BOT_TOKEN
    channel = str(cfg.get("tg_channel") or "").strip()
    if not channel:
        return {"ok": False, "error": "کانال تنظیم نشده"}
    if not channel.startswith("@") and not channel.lstrip("-").isdigit():
        channel = "@" + channel
    try:
        fname = os.path.basename(filepath)
        size_mb = os.path.getsize(filepath) / (1024 * 1024)
        with open(filepath, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": channel,
                      "caption": f"💾 بکاپ خودکار\n📅 {time.strftime('%Y-%m-%d %H:%M')}\n📦 {size_mb:.1f} MB"},
                files={"document": (fname, f)},
                timeout=120,
            )
        j = r.json()
        if j.get("ok"):
            return {"ok": True, "message_id": j["result"]["message_id"]}
        return {"ok": False, "error": str(j.get("description", "?"))[:120]}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:120]}


# ══════════════════════════════════════════════════════════════════════════
# ─── مقصد ۲: Google Drive — Service Account (بدون OAuth) ────────────────
# ══════════════════════════════════════════════════════════════════════════

def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _gdrive_sa_token() -> str:
    """
    دریافت access_token با Service Account JWT — بدون هیچ کتابخانه‌ی گوگل.
    JWT با RS256 امضا می‌شود (cryptography که وابستگی requests است).
    """
    import requests
    sa_path = os.getenv("GDRIVE_SA_JSON", "").strip()
    if not sa_path or not os.path.exists(sa_path):
        raise ValueError("GDRIVE_SA_JSON تنظیم نشده یا فایل موجود نیست")
    with open(sa_path) as f:
        sa = json.load(f)

    now = int(time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64url(json.dumps({
        "iss": sa["client_email"],
        "scope": "https://www.googleapis.com/auth/drive.file",
        "aud": "https://oauth2.googleapis.com/token",
        "iat": now, "exp": now + 3600,
    }).encode())
    signing_input = f"{header}.{claims}".encode()

    # امضای RS256 با cryptography
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding
    key = serialization.load_pem_private_key(sa["private_key"].encode(), password=None)
    signature = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    jwt = f"{header}.{claims}.{_b64url(signature)}"

    r = requests.post("https://oauth2.googleapis.com/token", data={
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt,
    }, timeout=30)
    j = r.json()
    if "access_token" not in j:
        raise ValueError(f"token error: {str(j)[:120]}")
    return j["access_token"]


def _up_gdrive(filepath: str) -> dict:
    """آپلود به Google Drive + چرخش (فقط ۳۰ بکاپ آخر)."""
    import requests
    folder_id = os.getenv("GDRIVE_FOLDER_ID", "").strip()
    if not folder_id:
        return {"ok": False, "error": "GDRIVE_FOLDER_ID تنظیم نشده"}
    try:
        token = _gdrive_sa_token()
        headers = {"Authorization": f"Bearer {token}"}
        fname = os.path.basename(filepath)

        # آپلود multipart
        meta = {"name": fname, "parents": [folder_id]}
        with open(filepath, "rb") as f:
            files = {
                "metadata": ("metadata", json.dumps(meta), "application/json"),
                "file": (fname, f, "application/octet-stream"),
            }
            r = requests.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers=headers, files=files, timeout=300)
        j = r.json()
        if "id" not in j:
            return {"ok": False, "error": str(j)[:120]}

        # چرخش: فقط ۳۰ بکاپ آخر
        try:
            lst = requests.get(
                "https://www.googleapis.com/drive/v3/files",
                headers=headers,
                params={"q": f"'{folder_id}' in parents and trashed=false",
                        "orderBy": "createdTime desc",
                        "fields": "files(id,name,createdTime)",
                        "pageSize": 100},
                timeout=30).json()
            files_list = lst.get("files", [])
            for old in files_list[RETENTION_DRIVE:]:
                try:
                    requests.delete(
                        f"https://www.googleapis.com/drive/v3/files/{old['id']}",
                        headers=headers, timeout=30)
                except Exception:
                    pass
        except Exception as ex:
            logger.warning("drive rotation failed: %s", ex)

        return {"ok": True, "file_id": j["id"]}
    except Exception as ex:
        return {"ok": False, "error": str(ex)[:120]}


# ══════════════════════════════════════════════════════════════════════════
# ─── نقطه ورود عمومی — غیرهمزمان ──────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════

def upload_backup(filepath: str) -> dict:
    """
    آپلود فایل .stbak به همه مقاصد فعال — در thread جدا (ربات متوقف نمی‌شود).
    نتیجه بلافاصله برمی‌گردد؛ وضعیت واقعی بعداً در cloud_backup ذخیره می‌شود.
    """
    if not filepath or not os.path.exists(filepath):
        return {"ok": False, "error": "فایل موجود نیست"}

    def _worker():
        cfg = get_cloud_settings()
        results = {}
        if int(cfg.get("tg_enabled") or 0):
            results["telegram"] = _up_telegram(filepath, cfg)
        if int(cfg.get("gdrive_enabled") or 0):
            results["gdrive"] = _up_gdrive(filepath)
        ok_any = any(v.get("ok") for v in results.values()) if results else False
        status = " | ".join(
            f"{k}:{'✅' if v.get('ok') else '❌ '+str(v.get('error',''))[:40]}"
            for k, v in results.items()) or "مقصدی فعال نیست"
        try:
            save_cloud_settings({
                "last_upload_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                "last_status": status,
            })
        except Exception:
            pass
        if results and not ok_any:
            logger.error("cloud backup failed: %s", status)
        else:
            logger.info("cloud backup: %s", status)

    threading.Thread(target=_worker, name="cloud-backup-upload", daemon=True).start()
    return {"ok": True, "async": True}


def watchdog_check() -> str | None:
    """اگر > ۲۶ ساعت از آخرین آپلود موفق گذشته، هشدار (روزی یک‌بار)."""
    from db import get_cfg, set_cfg
    cfg = get_cloud_settings()
    if not (int(cfg.get("tg_enabled") or 0) or int(cfg.get("gdrive_enabled") or 0)):
        return None
    last = cfg.get("last_upload_at", "")
    if not last:
        return None
    try:
        last_ts = time.mktime(time.strptime(last, "%Y-%m-%d %H:%M:%S"))
        if time.time() - last_ts > 26 * 3600:
            today = time.strftime("%Y-%m-%d")
            if get_cfg("backup_alert_day", "") != today:
                set_cfg("backup_alert_day", today)
                return f"⚠️ بیش از ۲۶ ساعت از آخرین بکاپ ابری گذشته (آخرین: {last})"
    except Exception:
        pass
    return None
