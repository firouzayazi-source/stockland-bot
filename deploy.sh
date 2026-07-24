#!/usr/bin/env bash
# ── deploy.sh — دیپلوی کامل استوک‌لند (کاملاً خودکار) ──
# استفاده:  bash deploy.sh   (یا با alias:  deploy)
# کارها: git pull → نصب/آپدیت وابستگی‌های پایتون (در صورت تغییر requirements.txt)
#        → چک vendor مینی‌اپ (دانلود در صورت نبود) → پاک‌سازی کش PWA → ری‌استارت سرویس
set -e
APP_DIR="/opt/stockland/app"
cd "$APP_DIR"

echo "══════════════════════════════════════"
echo "  🚀 دیپلوی استوک‌لند"
echo "══════════════════════════════════════"

# ۱. دریافت آخرین تغییرات از گیت (همیشه از main)
echo ""
echo "📥 دریافت تغییرات از گیت..."
git fetch origin main
git checkout main 2>/dev/null || git checkout -b main origin/main
git reset --hard origin/main
echo "✅ کد به‌روز شد (main)"

# ۲. آپدیت وابستگی‌های پایتون (فقط اگر requirements.txt عوض شده باشه — سریع و بی‌خطر در غیر این صورت)
if [ -f venv/bin/pip ]; then
    PIP=venv/bin/pip
elif [ -f "/opt/stockland/venv/bin/pip" ]; then
    PIP=/opt/stockland/venv/bin/pip
else
    PIP=""
fi
if [ -n "$PIP" ] && [ -f requirements.txt ]; then
    echo ""
    echo "📦 بررسی وابستگی‌های پایتون..."
    "$PIP" install -q -r requirements.txt && echo "   ✅ وابستگی‌ها به‌روزند" || echo "   ⚠️  نصب وابستگی‌ها با خطا مواجه شد — بررسی کن"
fi

# ۳. چک vendor مینی‌اپ (Framework7 + فونت — در گیت نیست، فقط یک‌بار لازمه)
if [ ! -f app/vendor/framework7-bundle.min.js ] && [ -f app/get_vendor.sh ]; then
    echo ""
    echo "📦 vendor مینی‌اپ موجود نیست — دانلود..."
    bash app/get_vendor.sh && echo "   ✅ vendor نصب شد" || echo "   ⚠️  دانلود vendor با خطا مواجه شد — بررسی کن"
fi

# ۴. پاک‌سازی کش PWA
V=$(date +%s)
echo ""
echo "🔄 پاک‌سازی کش PWA — نسخه: v${V}"
if [ -f app/sw.js ]; then
    OLD_CACHE=$(grep -o "sl-app-v[^']*" app/sw.js | head -1)
    sed -i -E "s/var CACHE[[:space:]]*=[[:space:]]*'sl-app-v[^']*'/var CACHE='sl-app-v${V}'/" app/sw.js
    NEW_CACHE=$(grep -o "sl-app-v[^']*" app/sw.js | head -1)
    if [ "$OLD_CACHE" != "$NEW_CACHE" ]; then
        echo "   ✅ sw.js → sl-app-v${V}"
    else
        echo "   ⚠️  sw.js CACHE عوض نشد — الگوی sed مطابقت نداشت! دستی چک کن: grep CACHE app/sw.js"
    fi
fi
if [ -f app/index.html ]; then
    sed -i "s/app\.css?v=[^\"']*/app.css?v=${V}/g" app/index.html
    sed -i "s/app\.js?v=[^\"']*/app.js?v=${V}/g" app/index.html
    echo "   ✅ index.html → ?v=${V}"
fi

# ۵. ری‌استارت سرویس
echo ""
echo "♻️  ری‌استارت سرویس..."
sudo systemctl restart stockland.service
sleep 1
STATUS=$(sudo systemctl is-active stockland.service)
if [ "$STATUS" = "active" ]; then
    echo "✅ stockland.service فعال است"
else
    echo "⚠️  وضعیت سرویس: $STATUS"
    echo "   لاگ‌ها:  journalctl -u stockland -n 20 --no-pager"
fi

echo ""
echo "══════════════════════════════════════"
echo "  ✅ دیپلوی کامل شد"
echo "  کش PWA پاک شد — کاربران با اولین"
echo "  بازدید فایل‌های جدید را دریافت می‌کنند."
echo "══════════════════════════════════════"
