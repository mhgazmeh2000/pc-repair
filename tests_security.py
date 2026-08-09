# -*- coding: utf-8 -*-
"""تست واحد ماژول امنیت — قبل از اتصال به سرور"""
import sys
sys.path.insert(0, '/home/user/pc-repair')
import security

P = F = 0
def chk(cond, msg, extra=""):
    global P, F
    if cond:
        P += 1; print(f"  ✅ {msg}")
    else:
        F += 1; print(f"  ❌ {msg}" + (f"  → {extra}" if extra else ""))

PORT = 8080
H = security.TOKEN_HEADER
TOK = security.SESSION_TOKEN

print("═" * 58)
print("۱) توکن نشست")
print("═" * 58)
chk(len(TOK) >= 32, f"توکن به‌قدر کافی بلند است ({len(TOK)} کاراکتر)")
chk(security.check_token(TOK), "توکن درست پذیرفته می‌شود")
chk(not security.check_token("wrong"), "توکن غلط رد می‌شود")
chk(not security.check_token(""), "توکن خالی رد می‌شود")
chk(not security.check_token(None), "توکن None رد می‌شود")
# توکن نباید قابل حدس باشد
import importlib
t1 = security.SESSION_TOKEN
chk(t1 == TOK, "توکن در طول اجرا ثابت می‌ماند")

print()
print("═" * 58)
print("۲) بررسی Host — جلوگیری از DNS rebinding")
print("═" * 58)
for h, want in [("127.0.0.1:8080", True), ("localhost:8080", True),
                ("127.0.0.1", True), ("[::1]:8080", True),
                ("evil.example.com", False), ("evil.example.com:8080", False),
                ("192.168.1.5:8080", False), ("", False)]:
    got = security.check_host(h)
    chk(got == want, f"Host '{h or '(خالی)'}' → {'مجاز' if got else 'رد'}",
        f"انتظار {want}")

print()
print("═" * 58)
print("۳) بررسی Origin")
print("═" * 58)
for o, want in [("", True),
                ("http://127.0.0.1:8080", True),
                ("http://localhost:8080", True),
                ("https://evil.example.com", False),
                ("http://evil.example.com:8080", False),
                ("null", False)]:
    got = security.check_origin(o, PORT)
    chk(got == want, f"Origin '{o or '(خالی)'}' → {'مجاز' if got else 'رد'}")

print()
print("═" * 58)
print("۴) سناریوی حملهٔ واقعی (همان curl که قبلاً موفق بود)")
print("═" * 58)
attack = {"Host": "127.0.0.1:8080", "Origin": "https://evil.example.com"}
ok, err = security.authorize("/api/run_tool", attack, PORT, "POST")
chk(not ok, "حملهٔ CORS مسدود شد", err)
chk("مبدأ" in err, "پیام خطای فارسی و گویا", err)

# مهاجم بدون Origin ولی بدون توکن
attack2 = {"Host": "127.0.0.1:8080"}
ok2, err2 = security.authorize("/api/run_tool", attack2, PORT, "POST")
chk(not ok2, "بدون توکن هم مسدود شد", err2)

# مهاجم با Host جعلی (DNS rebinding)
attack3 = {"Host": "evil.example.com", H: TOK}
ok3, err3 = security.authorize("/api/run_tool", attack3, PORT, "POST")
chk(not ok3, "DNS rebinding مسدود شد", err3)

print()
print("═" * 58)
print("۵) درخواست‌های قانونی نباید بشکنند")
print("═" * 58)
good = {"Host": "127.0.0.1:8080", "Origin": "http://127.0.0.1:8080", H: TOK}
ok, err = security.authorize("/api/run_tool", good, PORT, "POST")
chk(ok, "درخواست معتبر UI پذیرفته شد", err)

# بدون Origin (fetch same-origin اغلب نمی‌فرستد)
good2 = {"Host": "127.0.0.1:8080", H: TOK}
ok, err = security.authorize("/api/ai_chat", good2, PORT, "POST")
chk(ok, "same-origin بدون هدر Origin پذیرفته شد", err)

# صفحهٔ اصلی باید بدون توکن باز شود
for p in ["/", "/index.html", "/pc_toolbox_app.html"]:
    ok, err = security.authorize(p, {"Host": "127.0.0.1:8080"}, PORT, "GET")
    chk(ok, f"صفحهٔ '{p}' بدون توکن قابل بارگذاری است", err)

# OPTIONS
ok, _ = security.authorize("/api/run_tool", attack, PORT, "OPTIONS")
chk(ok, "OPTIONS بدون بررسی رد نمی‌شود (preflight)")

print()
print("═" * 58)
print("۶) تزریق توکن در HTML")
print("═" * 58)
html = "<!DOCTYPE html>\n<html>\n<head>\n<title>x</title>\n</head>\n<body>y</body>\n</html>"
out = security.inject_token(html)
chk(TOK in out, "توکن داخل HTML تزریق شد")
chk("__TOOLBOX_TOKEN__" in out, "نام متغیر درست است")
chk(out.index(TOK) < out.index("<title>"), "توکن بلافاصله بعد از <head> است")
chk(out.count("<head>") == 1, "ساختار HTML خراب نشد")
chk("<body>y</body>" in out, "بقیهٔ محتوا دست‌نخورده")
# بدون head
out2 = security.inject_token("<div>x</div>")
chk(TOK in out2, "بدون <head> هم کار می‌کند")

print()
print("═" * 58)
print("۷) رمزنگاری کلید API")
print("═" * 58)
key = "gsk_ABC123456789XYZ"
enc = security.encrypt_secret(key)
dec = security.decrypt_secret(enc)
if security._dpapi_available():
    chk(enc != key, "کلید رمز شد")
    chk(security.is_encrypted(enc), "پیشوند enc:v1: دارد")
    chk(dec == key, "بازگشایی درست است")
else:
    chk(enc == key, "روی لینوکس بدون DPAPI مقدار دست‌نخورده می‌ماند (رفتار مستند)")
    chk(dec == key, "بازگشایی مقدار خام درست کار می‌کند")

m = security.mask_secret(key)
chk(key not in m, f"ماسک کلید را افشا نمی‌کند: {m}")
chk(m.startswith("gsk_"), "ابتدای کلید برای تشخیص نمایش داده می‌شود")
chk(m.endswith("9XYZ"), "انتهای کلید نمایش داده می‌شود")
chk(security.mask_secret("") == "", "کلید خالی → رشتهٔ خالی")
chk(len(security.mask_secret("ab")) == 2, "کلید خیلی کوتاه هم خطا نمی‌دهد")

print()
print("═" * 58)
print("۸) ناشناس‌سازی داده‌های تشخیصی")
print("═" * 58)
import os, socket
os.environ["USERNAME"] = "m.gazmeh"
txt = r"مسیر C:\Users\m.gazmeh\AppData\Local\Temp و کاربر m.gazmeh با SID S-1-5-21-1234567890-987654321-111"
a = security.anonymize(txt)
chk("m.gazmeh" not in a, "نام کاربری حذف شد", a[:70])
chk("<USER>" in a, "برچسب <USER> جایگزین شد")
chk("S-1-5-21-<SID>" in a, "SID ناشناس شد", a[-40:])
chk("AppData" in a, "بقیهٔ مسیر حفظ شد — برای عیب‌یابی لازم است")

host = socket.gethostname()
a2 = security.anonymize(f"رایانه {host} آماده است")
chk(host not in a2 or len(host) < 3, "نام رایانه حذف شد", a2)

msgs = [{"role": "user", "content": r"خطا در C:\Users\m.gazmeh\test"},
        {"role": "assistant", "content": "بررسی می‌کنم"}]
am = security.anonymize_messages(msgs)
chk("m.gazmeh" not in am[0]["content"], "پیام‌های چت ناشناس شدند")
chk(am[1]["content"] == "بررسی می‌کنم", "پیام بدون داده شخصی تغییر نکرد")
chk(len(am) == 2 and am[0]["role"] == "user", "ساختار پیام‌ها حفظ شد")
chk(security.anonymize("") == "", "متن خالی خطا نمی‌دهد")
chk(security.anonymize(None) is None, "None خطا نمی‌دهد")

print()
print("═" * 58)
print("۱۲) پایداری توکن نشست بین ریاستارت‌ها")
print("═" * 58)
# توکن باید بین دو اجرای ماژول (شبیه‌سازی ریاستارت سرور) ثابت بماند.
# ایزوله‌سازی: ProgramData را به یک پوشهٔ موقت می‌بریم تا فایل‌های توکنِ
# واقعی برنامه (در %ProgramData%\PCRepairToolbox) دست‌نخورده بمانند —
# چون _state_dir از env متغیر ProgramData می‌خواند، reload با این env،
# توکن‌ها را در پوشهٔ موقت می‌سازد/می‌خواند.
import os
import importlib
import tempfile
import shutil
_tmp = tempfile.mkdtemp(prefix="pc_toolbox_sec_test_")
_orig_pd = os.environ.get("ProgramData")
os.environ["ProgramData"] = _tmp
security = importlib.reload(security)
t1 = security.SESSION_TOKEN
p1 = security.PREVIEW_TOKEN
# شبیه‌سازی ریاستارت: دوباره ماژول را بار کن
security = importlib.reload(security)
chk(security.SESSION_TOKEN == t1,
    "توکن نشست بعد از re-import ثابت می‌ماند")
chk(security.PREVIEW_TOKEN == p1,
    "توکن پیش‌نمایش بعد از re-import ثابت می‌ماند")
if _orig_pd is None:
    os.environ.pop("ProgramData", None)
else:
    os.environ["ProgramData"] = _orig_pd
shutil.rmtree(_tmp, ignore_errors=True)

print()
print("─" * 58)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
