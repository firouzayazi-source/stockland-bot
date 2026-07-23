#!/usr/bin/env bash
# ── deploy.sh — دیپلوی کامل استوک‌لند ──
# استفاده:  bash deploy.sh
# کارها: git pull → کش PWA پاک → سرویس ری‌استارت
set -e
APP_DIR="/opt/stockland/app"
cd "$APP_DIR"

echo "══════════════════════════════════════"
echo "  🚀 دیپلوی استوک‌لند"
echo "══════════════════════════════════════"

# ۱. دریافت آخرین تغییرات از گیت
echo ""
echo "📥 دریافت تغییرات از گیت..."
git pull --ff-only 2>&1 || git pull 2>&1
echo "✅ کد به‌روز شد"

# ۲. پاک‌سازی کش PWA
V=$(date +%s)
echo ""
echo "🔄 پاک‌سازی کش PWA — نسخه: v${V}"
if [ -f app/sw.js ]; then
    sed -i "s/var CACHE = 'sl-app-v[^']*'/var CACHE = 'sl-app-v${V}'/" app/sw.js
    echo "   ✅ sw.js → sl-app-v${V}"
fi
if [ -f app/index.html ]; then
    sed -i "s/app\.css?v=[^\"']*/app.css?v=${V}/g" app/index.html
    sed -i "s/app\.js?v=[^\"']*/app.js?v=${V}/g" app/index.html
    echo "   ✅ index.html → ?v=${V}"
fi

# ۳. ری‌استارت سرویس
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
