# -*- coding: utf-8 -*-
"""تست الف‑۵ (نقطه بازگشت) · الف‑۶ (حافظه) · الف‑۷ (فرهنگ رویداد)"""
import os, sys, tempfile
sys.path.insert(0, '/home/user/pc-repair')

import database
# دیتابیس موقت تا تست‌ها به هم آلوده نشوند
database._DB_PATH = os.path.join(
    tempfile.mkdtemp(prefix='a567_'), 'test.db')
import restore_point as rp
import repair_history as rh
import event_catalog as ec

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

database.init_db()

print("═" * 62)
print("۱) الف‑۵ — نقطهٔ بازگشت (روی لینوکس: رفتار امن)")
print("═" * 62)
chk(not rp.is_admin(), "روی لینوکس ادمین نیست")
st = rp.protection_status()
chk(not st['available'], "در دسترس نبودن گزارش شد")
chk('ویندوز' in st.get('reason', ''), f"دلیل فارسی: {st.get('reason','')[:40]}")

r = rp.create(reason='تست')
chk(not r['success'], "ساخت روی لینوکس ناموفق — بدون ادعای دروغ")
chk(r.get('skipped'), "پرچم skipped")
chk('ویندوز' in r.get('error',''), "پیام واضح")

lp = rp.list_points()
chk(lp['success'] and lp['points'] == [], "فهرست خالی بدون کرش")
r = rp.enable_protection()
chk(not r['success'], "روشن کردن روی لینوکس ناموفق")
r = rp.open_restore_ui()
chk(not r['success'], "باز کردن UI روی لینوکس ناموفق")

print()
print("═" * 62)
print("۲) الف‑۵ — تصمیم‌گیری برای ساخت نقطه")
print("═" * 62)
chk(rp.should_create_for(['winsock']), "winsock نقطه لازم دارد")
chk(rp.should_create_for(['sfc', 'flushdns']), "sfc نقطه لازم دارد")
chk(rp.should_create_for(['dism_restore']), "dism_restore نقطه لازم دارد")
chk(rp.should_create_for(['chkdsk']), "chkdsk نقطه لازم دارد")
chk(not rp.should_create_for(['flushdns']), "flushdns تنها نقطه لازم ندارد")
chk(not rp.should_create_for(['temp_clean']), "temp_clean نقطه لازم ندارد")
chk(not rp.should_create_for([]), "لیست خالی")
chk(rp.should_create_for([], ['caution']), "سطح caution نقطه لازم دارد")
chk(rp.should_create_for([], ['blocked']), "سطح blocked نقطه لازم دارد")
chk(not rp.should_create_for([], ['safe']), "سطح safe نقطه لازم ندارد")

print()
print("═" * 62)
print("۳) الف‑۶ — ثبت و بازیابی نتایج تعمیر")
print("═" * 62)
CMP1 = {"verdict": "no_change", "improved": 0, "worsened": 0, "unchanged": 2,
        "rows": [{"key": "sfc_corrupt", "label_fa": "فساد فایل‌های سیستمی",
                  "before": 1, "after": 1, "status": "unchanged"}]}
r = rh.record_outcome("job_1", ["sfc"], CMP1)
chk(r['success'], "نتیجه ثبت شد")

CMP2 = {"verdict": "resolved", "improved": 2, "worsened": 0, "unchanged": 0,
        "rows": [{"key": "disk_c_free_pct", "label_fa": "فضای آزاد C",
                  "before": 4.2, "after": 31.8, "status": "improved"},
                 {"key": "temp_size_mb", "label_fa": "حجم فایل‌های موقت",
                  "before": 3000, "after": 120, "status": "improved"}]}
rh.record_outcome("job_2", ["temp_clean", "cleanmgr"], CMP2)
rh.record_outcome("job_3", ["sfc"], CMP1)

out = rh.recent_outcomes()
chk(len(out) == 3, f"۳ نتیجه ({len(out)})")
chk(out[0]['job_id'] == 'job_3', "جدیدترین اول")
chk(out[0]['verdict'] == 'no_change', "حکم درست")
chk(len(out[1]['detail']) == 2, "جزئیات سنجه‌های تغییریافته")
chk(all('age_days' in o for o in out), "سن محاسبه شد")

print()
print("═" * 62)
print("۴) الف‑۶ — اثربخشی مراحل (قلب قابلیت)")
print("═" * 62)
eff = rh.step_effectiveness()
chk('sfc' in eff and eff['sfc']['runs'] == 2, f"SFC دو بار اجرا شد")
chk(eff['sfc']['effective'] == 0, "SFC هیچ‌بار مؤثر نبود")
chk(eff['temp_clean']['effective'] == 1, "temp_clean مؤثر بود")

bad = rh.ineffective_steps()
ids = [b['step'] for b in bad]
chk('sfc' in ids, f"SFC در فهرست بی‌اثرها: {ids}")
chk('temp_clean' not in ids, "temp_clean در فهرست بی‌اثرها نیست")
chk(bad[0]['runs'] == 2, "تعداد اجرا درست")

print()
print("═" * 62)
print("۵) الف‑۶ — متن زمینه برای AI")
print("═" * 62)
t = rh.build_context()
chk('تاریخچهٔ تعمیرهای قبلی' in t, "عنوان")
chk('جواب ندادند' in t, "بخش مراحل بی‌اثر")
chk('دوباره پیشنهاد نده' in t, "دستور صریح به AI")
chk('فضای آزاد C' in t, "جزئیات سنجه")
chk('4.2' in t and '31.8' in t, "مقادیر قبل و بعد")
chk(len(t) > 300, f"متن کامل ({len(t)} کاراکتر)")

s = rh.summary()
chk(s['total'] == 3, f"۳ تعمیر ({s['total']})")
chk(s['resolved'] == 1, "۱ مؤثر")
chk(s['no_change'] == 2, "۲ بی‌اثر")
chk('📚' in s['summary_fa'], f"{s['summary_fa']}")

rh.clear_history()
chk(rh.recent_outcomes() == [], "پاک‌سازی تاریخچه")
chk(rh.build_context() == "", "تاریخچهٔ خالی → متن خالی")

print()
print("═" * 62)
print("۶) الف‑۷ — فرهنگ رویداد")
print("═" * 62)
chk(ec.catalog_size() >= 45, f"{ec.catalog_size()} رویداد در فرهنگ")

i = ec.lookup(41, "Microsoft-Windows-Kernel-Power")
chk(i is not None, "Event 41 پیدا شد")
chk('خاموشی ناگهانی' in i['title'], f"عنوان: {i['title']}")
chk(i['severity'] == 'critical', "شدت بحرانی")
chk(len(i['causes']) >= 3, f"{len(i['causes'])} علت محتمل")

i = ec.lookup(4101, "Microsoft-Windows-Display")
chk(i and 'TDR' in i['title'], "Event 4101 (TDR گرافیک)")
chk(47 in i['tool_ids'], "ابزار مرتبط گرافیک")

i = ec.lookup(2004, "Microsoft-Windows-Resource-Exhaustion-Detector")
chk(i and 'حافظه' in i['title'], "Event 2004 (کمبود حافظه)")

# ID یکسان با Provider متفاوت
a = ec.lookup(1001, "BugCheck")
b = ec.lookup(1001, "Windows Error Reporting")
chk(a and b and a['title'] != b['title'],
    f"تفکیک بر اساس Provider: «{a['title'][:20]}» ≠ «{b['title'][:20]}»")

chk(ec.lookup(99999) is None, "رویداد ناشناخته → None")
chk(ec.lookup(None) is None, "None → None")
chk(ec.lookup("متن") is None, "ورودی نامعتبر → None")

print()
print("═" * 62)
print("۷) الف‑۷ — استخراج از متن خام Event Viewer")
print("═" * 62)
RAW = """
TimeCreated  : 1/15/2026 3:22:11 PM
Id           : 41
ProviderName : Microsoft-Windows-Kernel-Power
Msg          : The system has rebooted without cleanly shutting down first.

TimeCreated  : 1/15/2026 2:10:05 PM
Id           : 7031
ProviderName : Service Control Manager
Msg          : The Print Spooler service terminated unexpectedly.

TimeCreated  : 1/14/2026 9:41:00 AM
Id           : 4101
ProviderName : Microsoft-Windows-Display
Msg          : Display driver nvlddmkm stopped responding.

TimeCreated  : 1/14/2026 8:00:00 AM
Id           : 88888
ProviderName : Unknown-Provider
"""
r = ec.explain_text(RAW)
chk(r['success'], "تحلیل انجام شد")
chk(len(r['known']) == 3, f"۳ رویداد شناخته‌شده ({len(r['known'])})")
chk(len(r['unknown']) == 1, "۱ رویداد ناشناخته")
chk(r['known'][0]['severity'] == 'critical', "بحرانی‌ها اول مرتب شدند")
chk(r['counts']['critical'] >= 1, f"شمارش: {r['counts']}")
chk(len(r['suggested_steps']) > 0, f"مراحل پیشنهادی: {r['suggested_steps']}")
chk(len(r['tool_ids']) > 0, f"{len(r['tool_ids'])} ابزار مرتبط")
chk(len(r['tool_ids']) == len(set(r['tool_ids'])), "ابزارها بدون تکرار")
print(f"     {r['summary_fa']}")

# شکل‌های دیگر متن
r2 = ec.explain_text("Event ID: 41\nSource: Kernel-Power")
chk(len(r2['known']) >= 1, "شکل «Event ID:» شناخته شد")
chk(ec.explain_text("")['known'] == [], "متن خالی")
chk(ec.explain_text(None)['known'] == [], "None")
chk(ec.explain_text("بدون هیچ رویدادی")['known'] == [], "متن بدون رویداد")

print()
print("═" * 62)
print("۸) الف‑۷ — متن برای AI")
print("═" * 62)
t = ec.format_for_ai(r)
chk('فرهنگ داخلی' in t, "عنوان")
chk('Event 41' in t, "شمارهٔ رویداد")
chk('علت‌های محتمل' in t, "علت‌ها")
chk('دوباره توضیحشان نده' in t, "دستور صرفه‌جویی توکن")
chk('88888' in t, "رویداد ناشناخته به AI واگذار شد")
chk(len(t) > 400, f"متن کامل ({len(t)} کاراکتر)")
chk(ec.format_for_ai(None) == "", "None → متن خالی")

# رویداد اطلاعی نباید در متن AI بیاید
info_only = ec.explain_text("Id : 6005\nProviderName : EventLog")
t2 = ec.format_for_ai(info_only)
chk('6005' not in t2 or len(t2) < 200, "رویداد اطلاعی به AI فرستاده نمی‌شود")

print()
print("═" * 62)
print("۹) یکپارچگی داده‌های فرهنگ")
print("═" * 62)
bad_sev = [k for k, v in ec.CATALOG.items()
           if v['severity'] not in ('critical', 'warning', 'info')]
chk(not bad_sev, "همه شدت‌ها معتبرند", str(bad_sev))
missing = [k for k, v in ec.CATALOG.items()
           if not v.get('title') or not v.get('meaning')]
chk(not missing, "همه عنوان و توضیح دارند", str(missing[:3]))

try:
    import repair_runner
    valid = set(repair_runner.REPAIR_STEPS.keys())
    bad_steps = set()
    for v in ec.CATALOG.values():
        bad_steps |= (set(v.get('steps', [])) - valid)
    chk(not bad_steps, "همه مراحل پیشنهادی در REPAIR_STEPS هستند", str(bad_steps))
except Exception as e:
    chk(False, "بررسی مراحل", str(e))

import json as _j
_tools_path = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), "tools_data.json")
tools = _j.load(open(_tools_path, encoding='utf-8'))
valid_ids = {t['id'] for t in tools}
bad_tools = set()
for v in ec.CATALOG.values():
    bad_tools |= (set(v.get('tool_ids', [])) - valid_ids)
chk(not bad_tools, "همه شناسه‌های ابزار معتبرند", str(bad_tools))

print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
