#!/usr/bin/env bash
# ─── دانلود یک‌باره‌ی فایل‌های vendor روی سرور ───
# اجرا (فقط یک بار، یا بعد از clone تازه):  bash app/get_vendor.sh
set -e
cd "$(dirname "$0")"
mkdir -p vendor/fonts

F7V="8.3.4"
echo "⬇️  Framework7 $F7V ..."
curl -fL --retry 3 -o vendor/framework7-bundle.min.js \
  "https://cdn.jsdelivr.net/npm/framework7@$F7V/framework7-bundle.min.js"
curl -fL --retry 3 -o vendor/framework7-bundle-rtl.min.css \
  "https://cdn.jsdelivr.net/npm/framework7@$F7V/framework7-bundle-rtl.min.css"

VZ="v33.003"
echo "⬇️  Vazirmatn $VZ ..."
for w in Regular Medium Bold; do
  curl -fL --retry 3 -o "vendor/fonts/Vazirmatn-$w.woff2" \
    "https://cdn.jsdelivr.net/gh/rastikerdar/vazirmatn@$VZ/fonts/webfonts/Vazirmatn-$w.woff2"
done

echo "── فایل‌های دریافت‌شده ──"
ls -lh vendor vendor/fonts
echo "✅ vendor آماده شد — حالا stockland.service را ری‌استارت کنید."
