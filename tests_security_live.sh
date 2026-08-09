#!/bin/bash
# تست امنیتی روی سرور زنده — همان حمله‌ای که قبلاً موفق بود
PORT=8077
B="http://127.0.0.1:$PORT"
P=0; F=0

chk() {  # chk "توضیح" "انتظار" "واقعی"
  if [ "$2" == "$3" ]; then echo "  ✅ $1"; P=$((P+1))
  else echo "  ❌ $1 → انتظار «$2» ولی «$3»"; F=$((F+1)); fi
}

echo "════════════════════════════════════════════════════════"
echo "۱) حملهٔ CORS — دقیقاً همان curl که قبلاً success می‌داد"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /tmp/r1.json -w '%{http_code}' -X POST \
  -H 'Origin: https://evil.example.com' -H 'Content-Type: application/json' \
  -d '{"command":"whoami"}' "$B/api/run_tool")
chk "درخواست مهاجم رد شد (۴۰۳)" "403" "$CODE"
echo "     پاسخ: $(cat /tmp/r1.json)"
grep -q '"blocked": *true' /tmp/r1.json && { echo "  ✅ پرچم blocked در پاسخ"; P=$((P+1)); } || { echo "  ❌ پرچم blocked نیست"; F=$((F+1)); }

echo
echo "════════════════════════════════════════════════════════"
echo "۲) بدون توکن — حتی بدون Origin"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /tmp/r2.json -w '%{http_code}' -X POST \
  -H 'Content-Type: application/json' -d '{"tool_id":1}' "$B/api/run_tool")
chk "بدون توکن رد شد" "403" "$CODE"

CODE=$(curl -s -o /dev/null -w '%{http_code}' "$B/api/settings")
chk "GET حساس بدون توکن رد شد" "403" "$CODE"

echo
echo "════════════════════════════════════════════════════════"
echo "۳) DNS rebinding — Host جعلی"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H 'Host: evil.example.com' -H 'Content-Type: application/json' \
  -d '{"tool_id":1}' "$B/api/run_tool")
chk "Host جعلی رد شد" "403" "$CODE"

echo
echo "════════════════════════════════════════════════════════"
echo "۴) صفحهٔ اصلی باید بدون توکن باز شود"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /tmp/page.html -w '%{http_code}' "$B/")
chk "صفحه بارگذاری شد" "200" "$CODE"
grep -q '__TOOLBOX_TOKEN__' /tmp/page.html && { echo "  ✅ توکن در HTML تزریق شد"; P=$((P+1)); } || { echo "  ❌ توکن تزریق نشد"; F=$((F+1)); }

TOKEN=$(grep -o '__TOOLBOX_TOKEN__ = "[^"]*"' /tmp/page.html | sed 's/.*= "//;s/"//')
if [ -n "$TOKEN" ]; then echo "  ✅ توکن استخراج شد (${#TOKEN} کاراکتر)"; P=$((P+1));
else echo "  ❌ توکن استخراج نشد"; F=$((F+1)); fi

# هدر CORS نباید * باشد
curl -s -D /tmp/h.txt -o /dev/null "$B/"
if grep -qi 'access-control-allow-origin: \*' /tmp/h.txt; then
  echo "  ❌ هنوز Allow-Origin: * می‌فرستد"; F=$((F+1))
else
  echo "  ✅ Allow-Origin دیگر * نیست: $(grep -i 'access-control-allow-origin' /tmp/h.txt | tr -d '\r')"; P=$((P+1))
fi

echo
echo "════════════════════════════════════════════════════════"
echo "۵) درخواست‌های قانونی با توکن باید کار کنند"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /tmp/r5.json -w '%{http_code}' \
  -H "X-Toolbox-Token: $TOKEN" "$B/api/settings")
chk "GET settings با توکن" "200" "$CODE"

CODE=$(curl -s -o /tmp/r6.json -w '%{http_code}' -X POST \
  -H "X-Toolbox-Token: $TOKEN" -H 'Content-Type: application/json' \
  -H "Origin: $B" -d '{"tool_id":1}' "$B/api/run_tool")
chk "run_tool با tool_id معتبر" "200" "$CODE"
echo "     پاسخ: $(cat /tmp/r6.json)"

echo
echo "════════════════════════════════════════════════════════"
echo "۶) whitelist — دستور دلخواه حتی با توکن معتبر"
echo "════════════════════════════════════════════════════════"
CODE=$(curl -s -o /tmp/r7.json -w '%{http_code}' -X POST \
  -H "X-Toolbox-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"command":"calc.exe && del /f /s /q C:\\*"}' "$B/api/run_tool")
chk "دستور دلخواه رد شد (۴۰۰)" "400" "$CODE"
echo "     پاسخ: $(cat /tmp/r7.json)"

CODE=$(curl -s -o /dev/null -w '%{http_code}' -X POST \
  -H "X-Toolbox-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"tool_id":99999}' "$B/api/run_tool")
chk "شناسهٔ ناموجود رد شد" "400" "$CODE"

echo
echo "════════════════════════════════════════════════════════"
echo "۷) کلید API نباید به مرورگر برود"
echo "════════════════════════════════════════════════════════"
curl -s -X POST -H "X-Toolbox-Token: $TOKEN" -H 'Content-Type: application/json' \
  -d '{"api_key":"gsk_SECRET_KEY_123456","model":"llama-3.3-70b-versatile","base_url":"https://api.groq.com/openai/v1"}' \
  "$B/api/settings" > /dev/null
curl -s -H "X-Toolbox-Token: $TOKEN" "$B/api/settings" > /tmp/r8.json
if grep -q 'gsk_SECRET_KEY_123456' /tmp/r8.json; then
  echo "  ❌ کلید کامل در پاسخ افشا شد"; F=$((F+1))
else
  echo "  ✅ کلید کامل در پاسخ نیست"; P=$((P+1))
fi
grep -q 'api_key_masked' /tmp/r8.json && { echo "  ✅ ماسک ارسال شد: $(python3 -c "import json;print(json.load(open('/tmp/r8.json')).get('api_key_masked'))")"; P=$((P+1)); } || { echo "  ❌ ماسک نیست"; F=$((F+1)); }

echo
echo "────────────────────────────────────────────────────────"
echo "نتیجه: $P موفق، $F ناموفق"
[ $F -eq 0 ] || exit 1
