# -*- coding: utf-8 -*-
"""تست الف‑۲ (خط پایه) و الف‑۳ (پرس‌وجوهای جدید)"""
import os
import sys
import tempfile

# دیتابیس موقت تا دادهٔ واقعی کاربر دست نخورد
sys.path.insert(0, '/home/user/pc-repair')

import database
# دیتابیس موقت — روی لینوکس متغیر LOCALAPPDATA نادیده گرفته می‌شود،
# پس مسیر را مستقیم تنظیم می‌کنیم تا تست‌ها به هم آلوده نشوند
database._DB_PATH = os.path.join(
    tempfile.mkdtemp(prefix='bl_test_'), 'test.db')
import baseline as bl
import system_query as sq

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

def mk(key, value, label="x", unit="", higher=True):
    return {"key": key, "label_fa": label, "unit": unit,
            "higher_is_better": higher, "value": value, "error": ""}

database.init_db()

print("═" * 62)
print("۱) الف‑۳ — هشت پرس‌وجوی جدید")
print("═" * 62)
NEW = ['scheduled_tasks', 'smart_attributes', 'pending_reboot',
       'disk_io_latency', 'page_file', 'reliability_index',
       'thermal_throttling', 'firewall_rules']
chk(len(sq.QUERIES) == 29, f"مجموع پرس‌وجوها: {len(sq.QUERIES)} (بود ۲۱)")
for k in NEW:
    chk(k in sq.QUERIES, f"«{k}» ثبت شد")
chk(all(callable(sq.QUERIES[k][1]) for k in NEW), "همه تابع دارند")
chk(all(sq.QUERIES[k][0].strip() for k in NEW), "همه توضیح فارسی دارند")

# اجرای واقعی — روی لینوکس خالی برمی‌گردد ولی نباید کرش کند
crashed = []
for k in NEW:
    r = sq.run_query(k)
    if not r.get('success'):
        crashed.append(k)
chk(not crashed, "اجرای همه بدون کرش (روی لینوکس خروجی خالی طبیعی است)", str(crashed))

r = sq.run_queries(['pending_reboot', 'page_file'])
chk(r['success'] and len(r['requested']) == 2, "run_queries با کلیدهای جدید")
chk('pending_reboot' in r['text'] or r['text'] == '' or 'ری‌استارت' in r['text'],
    "متن خروجی ساخته شد")

print()
print("═" * 62)
print("۲) الف‑۲ — ذخیره و بازیابی خط پایه")
print("═" * 62)
healthy = {
    "disk_c_free_pct": mk("disk_c_free_pct", 55, "فضای آزاد C", "%", True),
    "startup_count":   mk("startup_count", 8, "استارتاپ", "مورد", False),
    "ram_free_pct":    mk("ram_free_pct", 45, "حافظه آزاد", "%", True),
    "boot_time_sec":   mk("boot_time_sec", 22, "زمان بوت", "ثانیه", False),
}
res = bl.save_baseline(label="تست سالم", note="سیستم تازه نصب", snap=healthy)
chk(res['success'], f"ذخیره شد (id={res.get('id')})")
chk(res['metrics_total'] == 4, f"۴ سنجه ثبت شد")
chk(res['metrics_measured'] == 4, "همه اندازه‌گیری شده‌اند")

lst = bl.list_baselines()
chk(lst['success'] and len(lst['baselines']) == 1, "فهرست یک مورد دارد")
chk(lst['baselines'][0]['label'] == "تست سالم", "برچسب درست")
chk(lst['baselines'][0]['note'] == "سیستم تازه نصب", "یادداشت حفظ شد")
chk('snapshot' not in lst['baselines'][0], "فهرست سبک است (بدون اسنپ‌شات)")

got = bl.get_baseline()
chk(got is not None and got['label'] == "تست سالم", "جدیدترین بازیابی شد")
chk(len(got['snapshot']) == 4, "اسنپ‌شات کامل برگشت")

print()
print("═" * 62)
print("۳) تشخیص انحراف — سناریوی «قبلاً خوب بود»")
print("═" * 62)
degraded = {
    "disk_c_free_pct": mk("disk_c_free_pct", 6, "فضای آزاد C", "%", True),
    "startup_count":   mk("startup_count", 31, "استارتاپ", "مورد", False),
    "ram_free_pct":    mk("ram_free_pct", 44, "حافظه آزاد", "%", True),
    "boot_time_sec":   mk("boot_time_sec", 140, "زمان بوت", "ثانیه", False),
}
c = bl.compare_to_baseline(current=degraded)
chk(c['success'], "مقایسه انجام شد")
chk(len(c['worse']) == 3, f"۳ سنجه بدتر شده ({len(c['worse'])})",
    str([r['key'] for r in c['worse']]))
chk(c['stable_count'] == 1, f"حافظه ثابت مانده (نوسان ۱ واحد نویز است)")

worst = c['worse'][0]
chk(worst['key'] in ('startup_count', 'boot_time_sec', 'disk_c_free_pct'),
    f"بدترین انحراف اول: {worst['key']} ({worst.get('pct')}٪)")
chk(all(abs(c['worse'][i].get('pct') or 0) >= abs(c['worse'][i+1].get('pct') or 0)
        for i in range(len(c['worse'])-1)), "مرتب‌سازی نزولی بر اساس شدت")
print(f"     {c['summary_fa']}")
for r in c['worse']:
    print(f"       {r['label_fa']}: {r['baseline']:g} → {r['current']:g} ({r['pct']:+g}٪)")

print()
print("═" * 62)
print("۴) آستانهٔ سخت‌گیرانه‌تر برای بازهٔ بلندمدت")
print("═" * 62)
# disk_c_free_pct آستانهٔ نویز ۰.۵ دارد؛ با ضریب ۱.۵ می‌شود ۰.۷۵
tiny = dict(healthy)
tiny["disk_c_free_pct"] = mk("disk_c_free_pct", 54.4, "فضای آزاد C", "%", True)
c2 = bl.compare_to_baseline(current=tiny)
chk(len(c2['worse']) == 0, "تغییر ۰.۶ واحد انحراف شمرده نمی‌شود (نویز)")

bigger = dict(healthy)
bigger["disk_c_free_pct"] = mk("disk_c_free_pct", 53.0, "فضای آزاد C", "%", True)
c3 = bl.compare_to_baseline(current=bigger)
chk(len(c3['worse']) == 1, "تغییر ۲ واحد انحراف شمرده می‌شود")

print()
print("═" * 62)
print("۵) بهبود هم تشخیص داده می‌شود")
print("═" * 62)
improved = dict(healthy)
improved["startup_count"] = mk("startup_count", 4, "استارتاپ", "مورد", False)
improved["boot_time_sec"] = mk("boot_time_sec", 12, "زمان بوت", "ثانیه", False)
c4 = bl.compare_to_baseline(current=improved)
chk(len(c4['better']) == 2, f"۲ سنجه بهتر شده ({len(c4['better'])})")
chk(len(c4['worse']) == 0, "هیچ سنجه‌ای بدتر نشده")
chk('✅' in c4['summary_fa'], f"خلاصهٔ مثبت: {c4['summary_fa']}")

print()
print("═" * 62)
print("۶) متن خروجی برای AI")
print("═" * 62)
t = bl.format_for_ai(c)
chk("مقایسه با وضعیت سالم" in t, "عنوان دارد")
chk("تست سالم" in t, "برچسب خط پایه")
chk("سیستم تازه نصب" in t, "یادداشت کاربر")
chk("بدتر شده" in t, "بخش سنجه‌های بدتر")
chk("تغییر کرده" in t, "به AI می‌گوید روی تغییرات تمرکز کند")
chk("قبلاً خوب بود" in t, "اشاره به جملهٔ رایج کاربر")
chk(len(t) > 300, f"متن کامل است ({len(t)} کاراکتر)")
chk(bl.format_for_ai(None) == "", "ورودی None → متن خالی")

print()
print("═" * 62)
print("۷) حالت‌های مرزی")
print("═" * 62)
c5 = bl.compare_to_baseline(baseline_id=99999)
chk(not c5['success'], "شناسهٔ ناموجود → خطا")
chk('ثبت وضعیت سالم' in c5['error'], f"راهنمایی در پیام: {c5['error'][:50]}")

partial = {"disk_c_free_pct": mk("disk_c_free_pct", None, "فضا", "%", True)}
c6 = bl.compare_to_baseline(current=partial)
chk(c6['success'], "مقدار None کرش نمی‌کند")
unk = [r for r in c6['rows'] if r['drift'] == 'unknown']
chk(len(unk) >= 1, "سنجهٔ اندازه‌گیری‌نشده unknown می‌شود")

chk(bl.get_baseline(99999) is None, "get_baseline ناموجود → None")

print()
print("═" * 62)
print("۸) سقف تعداد و حذف")
print("═" * 62)
for i in range(12):
    bl.save_baseline(label=f"b{i}", snap=healthy)
lst = bl.list_baselines()
chk(len(lst['baselines']) == bl.MAX_BASELINES,
    f"سقف {bl.MAX_BASELINES} رعایت شد ({len(lst['baselines'])})")
chk(lst['baselines'][0]['label'] == 'b11', "جدیدترین اول است")

did = lst['baselines'][0]['id']
chk(bl.delete_baseline(did)['success'], "حذف موفق")
chk(len(bl.list_baselines()['baselines']) == bl.MAX_BASELINES - 1, "یکی کم شد")

print()
print("═" * 62)
print("۹) ثبت خودکار وقتی سیستم سالم است")
print("═" * 62)
# پاک کردن همه
for b in bl.list_baselines()['baselines']:
    bl.delete_baseline(b['id'])
chk(len(bl.list_baselines()['baselines']) == 0, "همه پاک شدند")

r = bl.auto_baseline_if_healthy({"healthy": True, "snapshot": healthy})
chk(r and r['success'], "سیستم سالم → خط پایه خودکار ثبت شد")
chk('خودکار' in bl.list_baselines()['baselines'][0]['label'], "برچسب «خودکار»")

r2 = bl.auto_baseline_if_healthy({"healthy": True, "snapshot": healthy})
chk(r2 is None, "خط پایهٔ تازه داریم → دوباره ثبت نمی‌شود")

r3 = bl.auto_baseline_if_healthy({"healthy": False, "snapshot": healthy})
chk(r3 is None, "سیستم ناسالم → ثبت نمی‌شود")

print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
