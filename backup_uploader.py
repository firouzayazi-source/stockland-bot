# -*- coding: utf-8 -*-
"""
☁️ آپلودر بکاپ ابری — StockLand
سه درایور: کانال خصوصی تلگرام، Google Drive (Service Account)، Microsoft OneDrive.
+ چرخش خودکار (نگه‌داشتن N بکاپ آخر) + نگهبان هشدار.

تنظیمات در bot_config با کلید cloud_backup (JSON) ذخیره می‌شود.
"""
import os
import json
import time
import datetime
import requests

CLOUD_DEFAULTS = {
    "enabled": 0, "hour": 4, "retention": 7,
    "tg_enabled": 0, "tg_channel": "",
    "gd_enabled": 0, "gd_folder": "", "gd_sa_json": "",
    "od_enabled": 0, "od_client_id": "", "od_folder": "StockLand-Backups", "od_refresh": "",
}


def get_cloud_settings() -> dict:
    from db import get_cfg_json
    return get_cfg_json("cloud_backup", CLOUD_DEFAULTS)


def save_cloud_settings(cfg: dict) -> None:
    from db import set_cfg
    merged = dict(CLOUD_DEFAULTS)
    merged.update(cfg or {})
    set_cfg("cloud_backup", json.dumps(merged, ensure_ascii=False))


# ══════════════════════════════════════════════════════════════════════════
# درایور ۱ — کانال خصوصی تلگرام
# ══════════════════════════════════════════════════════════════════════════

def _up_telegram(filepath: str, cfg: dict, retention: int) -> dict:
    from config import BOT_TOKEN
    from db import get_cfg, set_cfg
    channel = str(cfg.get("tg_channel") or "").strip()
    if not channel:
        return {"ok": False, "error": "آیدی کانال تنظیم نشده"}
    fname = os.path.basename(filepath)
    try:
        with open(filepath, "rb") as f:
            r = requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={"chat_id": channel,
                      "caption": f"🗄 بکاپ خودکار — {fname}"},
                files={"document": (fname, f)},
                timeout=120)
        j = r.json()
        if not j.get("ok"):
            return {"ok": False, "error": f"تلگرام: {j.get('description','خطای نامشخص')}"}
        msg_id = j["result"]["message_id"]
    except Exception as ex:
        return {"ok": False, "error": f"تلگرام: {ex}"}

    # چرخش: حذف پیام‌های قدیمی‌تر از N
    try:
        raw = get_cfg("cloudbk_tg_msgs", "[]")
        ids = json.loads(raw) if raw else []
        ids.append(msg_id)
        while len(ids) > int(retention):
            old = ids.pop(0)
            try:
                requests.post(
                    f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage",
                    json={"chat_id": channel, "message_id": old}, timeout=15)
            except Exception:
                pass
        set_cfg("cloudbk_tg_msgs", json.dumps(ids))
    except Exception:
        pass
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# درایور ۲ — Google Drive (Service Account)
# ══════════════════════════════════════════════════════════════════════════

def _gdrive_token(sa_json: str):
    try:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request as _GReq
    except ImportError:
        raise RuntimeError("کتابخانه نصب نیست — روی سرور اجرا کنید: pip install google-auth")
    info = json.loads(sa_json)
    creds = service_account.Credentials.from_service_account_info(
        info, scopes=["https://www.googleapis.com/auth/drive.file",
                      "https://www.googleapis.com/auth/drive"])
    creds.refresh(_GReq())
    return creds.token


def _up_gdrive(filepath: str, cfg: dict, retention: int) -> dict:
    sa_json = str(cfg.get("gd_sa_json") or "").strip()
    folder  = str(cfg.get("gd_folder") or "").strip()
    if not sa_json or not folder:
        return {"ok": False, "error": "Drive: کلید Service Account یا شناسه پوشه تنظیم نشده"}
    try:
        token = _gdrive_token(sa_json)
    except Exception as ex:
        return {"ok": False, "error": f"Drive auth: {ex}"}

    fname = os.path.basename(filepath)
    meta = {"name": fname, "parents": [folder]}
    try:
        with open(filepath, "rb") as f:
            files = {
                "metadata": ("metadata", json.dumps(meta), "application/json; charset=UTF-8"),
                "file": (fname, f, "application/octet-stream"),
            }
            r = requests.post(
                "https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart",
                headers={"Authorization": f"Bearer {token}"},
                files=files, timeout=300)
        if r.status_code not in (200, 201):
            return {"ok": False, "error": f"Drive upload {r.status_code}: {r.text[:180]}"}
    except Exception as ex:
        return {"ok": False, "error": f"Drive: {ex}"}

    # چرخش
    try:
        q = requests.get(
            "https://www.googleapis.com/drive/v3/files",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": f"'{folder}' in parents and trashed=false",
                    "orderBy": "createdTime",
                    "fields": "files(id,name)", "pageSize": 100},
            timeout=60).json()
        files_ls = q.get("files", [])
        while len(files_ls) > int(retention):
            old = files_ls.pop(0)
            requests.delete(
                f"https://www.googleapis.com/drive/v3/files/{old['id']}",
                headers={"Authorization": f"Bearer {token}"}, timeout=30)
    except Exception:
        pass
    return {"ok": True}


# ══════════════════════════════════════════════════════════════════════════
# درایور ۳ — Microsoft OneDrive (Device Code / Refresh Token)
# ══════════════════════════════════════════════════════════════════════════

_MS_TOKEN_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/token"
_MS_DEVICE_URL = "https://login.microsoftonline.com/consumers/oauth2/v2.0/devicecode"
_MS_SCOPE = "Files.ReadWrite offline_access"


def _onedrive_access_token(cfg: dict) -> str:
    client_id = str(cfg.get("od_client_id") or "").strip()
    refresh   = str(cfg.get("od_refresh") or "").strip()
    if not client_id or not refresh:
        raise RuntimeError("OneDrive متصل نیست — از پنل «اتصال» را انجام دهید")
    r = requests.post(_MS_TOKEN_URL, data={
        "client_id": client_id, "grant_type": "refresh_token",
        "refresh_token": refresh, "scope": _MS_SCOPE}, timeout=30)
    j = r.json()
    if "access_token" not in j:
        raise RuntimeError(f"OneDrive token: {j.get('error_description', j)[:180]}")
    # مایکروسافت گاهی refresh_token تازه می‌دهد — ذخیره‌اش کن
    if j.get("refresh_token") and j["refresh_token"] != refresh:
        cfg["od_refresh"] = j["refresh_token"]
        save_cloud_settings(cfg)
    return j["access_token"]


def _up_onedrive(filepath: str, cfg: dict, retention: int) -> dict:
    folder = str(cfg.get("od_folder") or "StockLand-Backups").strip().strip("/")
    try:
        token = _onedrive_access_token(cfg)
    except Exception as ex:
        return {"ok": False, "error": str(ex)}
    H = {"Authorization": f"Bearer {token}"}
    fname = os.path.basename(filepath)

    try:
        # upload session (برای هر حجمی امن است)
        sess = requests.post(
            f"https://graph.microsoft.com/v1.0/me/drive/root:/{folder}/{fname}:/createUploadSession",
            headers=H, json={"item": {"@microsoft.graph.conflictBehavior": "replace"}},
            timeout=30).json()
        up_url = sess.get("uploadUrl")
        if not up_url:
            return {"ok": False, "error": f"OneDrive session: {str(sess)[:180]}"}
        size = os.path.getsize(filepath)
        CH = 5 * 1024 * 1024
        with open(filepath, "rb") as f:
            pos = 0
            while pos < size:
                chunk = f.read(CH)
                end = pos + len(chunk) - 1
                rr = requests.put(up_url, data=chunk, headers={
                    "Content-Length": str(len(chunk)),
                    "Content-Range": f"bytes {pos}-{end}/{size}"}, timeout=300)
                if rr.status_code not in (200, 201, 202):
                    return {"ok": False, "error": f"OneDrive chunk {rr.status_code}: {rr.text[:150]}"}
                pos = end + 1
    except Exception as ex:
        return {"ok": False, "error": f"OneDrive: {ex}"}

    # چرخش
    try:
        ls = requests.get(
            f"https://graph.microsoft.com/v1.0/me/drive/root:/{folder}:/children"
            "?$orderby=lastModifiedDateTime asc&$top=100&$select=id,name",
            headers=H, timeout=60).json()
        items = ls.get("value", [])
        while len(items) > int(retention):
            old = items.pop(0)
            requests.delete(
                f"https://graph.microsoft.com/v1.0/me/drive/items/{old['id']}",
                headers=H, timeout=30)
    except Exception:
        pass
    return {"ok": True}


def onedrive_devicecode_start(client_id: str) -> dict:
    """شروع اتصال OneDrive — کد و لینک برای کاربر."""
    r = requests.post(_MS_DEVICE_URL,
                      data={"client_id": client_id, "scope": _MS_SCOPE}, timeout=30)
    return r.json()


def onedrive_devicecode_poll(client_id: str, device_code: str) -> dict:
    """بررسی تأیید — pending یا ok(+refresh_token)."""
    r = requests.post(_MS_TOKEN_URL, data={
        "client_id": client_id,
        "grant_type": "urn:ietf:params:oauth:grant-type:device_code",
        "device_code": device_code}, timeout=30)
    j = r.json()
    if j.get("refresh_token"):
        return {"status": "ok", "refresh_token": j["refresh_token"]}
    if j.get("error") in ("authorization_pending", "slow_down"):
        return {"status": "pending"}
    return {"status": "error", "error": j.get("error_description", str(j))[:200]}


# ══════════════════════════════════════════════════════════════════════════
# هماهنگ‌کننده + نگهبان
# ══════════════════════════════════════════════════════════════════════════

_DRIVERS = [
    ("tg_enabled", "کانال تلگرام", _up_telegram),
    ("gd_enabled", "Google Drive", _up_gdrive),
    ("od_enabled", "OneDrive",     _up_onedrive),
]


def upload_backup(filepath: str) -> dict:
    """آپلود به همه مقاصد فعال + ثبت وضعیت. {ok, results:[{driver,ok,error}]}"""
    from db import set_cfg
    cfg = get_cloud_settings()
    retention = max(1, int(cfg.get("retention") or 7))
    results, any_ok = [], False
    for flag, label, fn in _DRIVERS:
        if not int(cfg.get(flag) or 0):
            continue
        try:
            res = fn(filepath, cfg, retention)
        except Exception as ex:
            res = {"ok": False, "error": str(ex)}
        res["driver"] = label
        results.append(res)
        any_ok = any_ok or res.get("ok", False)

    now_iso = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    if any_ok:
        set_cfg("cloudbk_last_ok", now_iso)
    set_cfg("cloudbk_last_report", json.dumps(
        {"ts": now_iso, "results": results}, ensure_ascii=False))
    return {"ok": any_ok, "results": results}


def watchdog_check() -> str | None:
    """اگر بکاپ ابری فعال است ولی ۲۶ ساعت آپلود موفقی نبوده → متن هشدار؛ روزی یک‌بار."""
    from db import get_cfg, set_cfg
    cfg = get_cloud_settings()
    if not int(cfg.get("enabled") or 0):
        return None
    if not any(int(cfg.get(flag) or 0) for flag, _, _ in _DRIVERS):
        return None
    today = datetime.date.today().isoformat()
    if get_cfg("cloudbk_alert_last", "") == today:
        return None

    last_ok = get_cfg("cloudbk_last_ok", "")
    stale = True
    if last_ok:
        try:
            dt = datetime.datetime.strptime(last_ok, "%Y-%m-%d %H:%M")
            stale = (datetime.datetime.now() - dt).total_seconds() > 26 * 3600
        except Exception:
            stale = True
    if not stale:
        return None

    set_cfg("cloudbk_alert_last", today)
    lines = ["⚠️ <b>هشدار بکاپ ابری</b>\n",
             f"آخرین آپلود موفق: <b>{last_ok or 'هرگز'}</b>"]
    try:
        rep = json.loads(get_cfg("cloudbk_last_report", "") or "{}")
        errs = [r for r in rep.get("results", []) if not r.get("ok")]
        if errs:
            lines.append("\nخطاهای آخرین تلاش:")
            for r in errs[:4]:
                lines.append(f"• {r.get('driver')}: {str(r.get('error'))[:140]}")
    except Exception:
        pass
    lines.append("\n🔧 پنل ← دیتابیس ← بکاپ ابری را بررسی کنید.")
    return "\n".join(lines)


