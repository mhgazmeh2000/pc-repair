# -*- coding: utf-8 -*-
"""
اجرای همهٔ تست‌های پروژه

    python run_tests.py            همهٔ تست‌ها
    python run_tests.py --quick    فقط تست‌های واحد (بدون سرور)

تست‌های «زنده» خودشان سرور را روی پورت آزاد بالا می‌آورند، پس
لازم نیست چیزی از قبل در حال اجرا باشد.
"""

import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))

UNIT = [
    ("tests_build.py",     "پیکربندی ساخت"),
    ("tests_security.py",  "امنیت — توکن، رمزنگاری، ناشناس‌سازی"),
    ("tests_metrics.py",   "سنجه‌های عددی + تشخیص محلی"),
    ("tests_baseline.py",  "خط پایه + پرس‌وجوهای جدید"),
    ("tests_workspace.py", "پوشهٔ پروژه"),
    ("tests_changes.py",   "استخراج و اعمال diff"),
    ("tests_a567.py",      "نقطهٔ بازگشت، حافظه، فرهنگ رویداد"),
]

LIVE = [
    ("tests_step2_live.py",   "سرور — حلقهٔ بسته و تشخیص محلی"),
    ("tests_step3_live.py",   "سرور — خط پایه"),
    ("tests_dev_live.py",     "سرور — تب توسعه"),
    ("tests_changes_live.py", "سرور — تب Changes"),
    ("tests_a567_live.py",    "سرور — الف‑۵ تا الف‑۷"),
]


def run(script, desc):
    path = os.path.join(HERE, script)
    if not os.path.exists(path):
        return None, f"فایل یافت نشد: {script}"
    t0 = time.time()
    try:
        r = subprocess.run([sys.executable, path], cwd=HERE,
                           capture_output=True, timeout=600)
        out = r.stdout.decode("utf-8", "replace")
        last = [l for l in out.strip().split("\n") if "نتیجه:" in l]
        summary = last[-1].replace("نتیجه:", "").strip() if last else "بدون خلاصه"
        return r.returncode == 0, f"{summary}  ({time.time() - t0:.1f}s)"
    except subprocess.TimeoutExpired:
        return False, "زمان اجرا تمام شد"
    except Exception as e:
        return False, str(e)[:60]


def main():
    quick = "--quick" in sys.argv
    groups = [("تست‌های واحد", UNIT)]
    if not quick:
        groups.append(("تست‌های سرور زنده", LIVE))

    total_ok = total_fail = 0
    failed = []

    for title, items in groups:
        print()
        print("═" * 68)
        print(title)
        print("═" * 68)
        for script, desc in items:
            ok, summary = run(script, desc)
            if ok is None:
                print(f"  ⏭  {desc:<38} {summary}")
                continue
            icon = "✅" if ok else "❌"
            print(f"  {icon} {desc:<38} {summary}")
            if ok:
                total_ok += 1
            else:
                total_fail += 1
                failed.append(script)

    print()
    print("─" * 68)
    if total_fail:
        print(f"❌ {total_ok} مجموعه موفق، {total_fail} ناموفق")
        print("   ناموفق: " + "، ".join(failed))
    else:
        print(f"✅ هر {total_ok} مجموعه موفق")
    return 1 if total_fail else 0


if __name__ == "__main__":
    sys.exit(main())
