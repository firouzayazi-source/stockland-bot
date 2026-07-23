#!/bin/bash
# بازیابی کامل استوک‌لند — برگشت به نسخه سالم
set -e
cd /opt/stockland/app

echo "🔄 بازیابی کامل..."

# ۱. گیت ریست کامل
git checkout main 2>/dev/null || true
git reset --hard origin/main 2>/dev/null || git reset --hard HEAD

# ۲. گیت pull
git config pull.rebase false
git pull --no-edit 2>/dev/null || true

# ۳. vendor چک
if [ ! -f app/vendor/framework7-bundle.min.js ]; then
    echo "📦 نصب vendor..."
    bash app/get_vendor.sh
fi

# ۴. ری‌استارت
systemctl restart stockland
sleep 2

STATUS=$(systemctl is-active stockland 2>/dev/null || echo "unknown")
echo ""
echo "✅ بازیابی کامل شد"
echo "   سرویس: $STATUS"
echo "   تست: مینی‌اپ رو ببند و دوباره باز کن"
