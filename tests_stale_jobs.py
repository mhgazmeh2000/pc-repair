# -*- coding: utf-8 -*-
"""
تست تشخیص زنجیره‌های ناتمام (stale jobs)

وقتی پنجرهٔ مدیریتی (UAC) وسط اجرا بسته شود، فرآیند پاورشل می‌میرد و
هیچ‌وقت status نهایی نمی‌نویسد — فایل وضعیت برای همیشه «running» می‌ماند.
این تست مطمئن می‌شود sweep_stale_jobs و get_job_status چنین زنجیره‌هایی
را interrupted می‌کنند.

اجرا:  python tests_stale_jobs.py
"""

import json
import os
import shutil
import sys
import tempfile
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import repair_runner

P = F = 0

# ایزوله‌سازی: همهٔ فایل‌ها در یک پوشهٔ موقت ساخته شوند نه پوشهٔ واقعی
_TMP_STATE = tempfile.mkdtemp(prefix="pc_toolbox_stale_test_")
_ORIG_STATE_DIR = repair_runner._state_dir
repair_runner._state_dir = lambda: _TMP_STATE


def chk(cond, msg, extra=""):
    global P, F
    if cond:
        P += 1
        print(f"  ✅ {msg}")
    else:
        F += 1
        print(f"  ❌ {msg}" + (f"  → {extra}" if extra else ""))


def _fake_job(job_id, status, log_age):
    """فایل وضعیت + فایل لاگ با mtime ساختگی می‌سازد."""
    d = repair_runner._state_dir()
    state = os.path.join(d, f"{job_id}.json")
    log = os.path.join(d, f"{job_id}.log")
    with open(state, "w", encoding="utf-8-sig") as f:
        json.dump({"job": job_id, "status": status, "current": 2,
                   "total": 4, "step": "dism_restore"}, f)
    with open(log, "w", encoding="utf-8") as f:
        f.write("[1/4] sfc\n__STEP_END 1 rc=0\n")
    old = time.time() - log_age
    os.utime(log, (old, old))
    os.utime(state, (old, old))


def _cleanup(job_id):
    d = repair_runner._state_dir()
    for suffix in (".json", ".log"):
        p = os.path.join(d, f"{job_id}{suffix}")
        if os.path.exists(p):
            os.remove(p)


def main():
    print("تست تشخیص زنجیره‌های ناتمام\n" + "─" * 64)

    # ── ۱) لاگ کهنه + وضعیت running → باید interrupted شود ──
    j1 = "test_stale_old"
    _cleanup(j1)
    _fake_job(j1, "running", log_age=3600 * 25)  # ۲۵ ساعت پیش
    try:
        chk(repair_runner._log_stale(j1), "لاگ کهنه تشخیص داده می‌شود")
        cleaned = repair_runner.sweep_stale_jobs()
        chk(j1 in cleaned, "sweep زنجیرهٔ کهنه را پیدا می‌کند",
            f"cleaned={cleaned}")
        st = repair_runner.get_job_status(j1)
        chk(st.get("status") == "interrupted",
            "get_job_status زنجیرهٔ مرده را interrupted گزارش می‌دهد",
            f"status={st.get('status')}")
        with open(os.path.join(repair_runner._state_dir(), f"{j1}.json"),
                  encoding="utf-8-sig") as f:
            raw = json.load(f)
        chk(raw.get("status") == "interrupted",
            "وضعیت interrupted روی دیسک ذخیره شده")
    finally:
        _cleanup(j1)

    # ── ۲) لاگ تازه + running → نباید لمس شود ──
    j2 = "test_stale_fresh"
    _cleanup(j2)
    _fake_job(j2, "running", log_age=30)  # ۳۰ ثانیه پیش
    try:
        chk(not repair_runner._log_stale(j2), "لاگ تازه کهنه محسوب نمی‌شود")
        cleaned = repair_runner.sweep_stale_jobs()
        chk(j2 not in cleaned, "sweep زنجیرهٔ تازه را دست نمی‌زند",
            f"cleaned={cleaned}")
        st = repair_runner.get_job_status(j2)
        chk(st.get("status") == "running",
            "زنجیرهٔ تازه همچنان running است", f"status={st.get('status')}")
    finally:
        _cleanup(j2)

    # ── ۳) وضعیت done → با وجود لاگ کهنه لمس نمی‌شود ──
    j3 = "test_stale_done"
    _cleanup(j3)
    _fake_job(j3, "done", log_age=3600 * 25)
    try:
        cleaned = repair_runner.sweep_stale_jobs()
        chk(j3 not in cleaned, "زنجیرهٔ تمام‌شده دست نمی‌خورد",
            f"cleaned={cleaned}")
    finally:
        _cleanup(j3)

    # ── ۴) BOM در فایل وضعیت (نوشتهٔ PowerShell 5.1) درست خوانده می‌شود ──
    j4 = "test_stale_bom"
    _cleanup(j4)
    d = repair_runner._state_dir()
    with open(os.path.join(d, f"{j4}.json"), "wb") as f:
        f.write(b"\xef\xbb\xbf" + json.dumps(
            {"job": j4, "status": "running", "total": 4}).encode("utf-8"))
    log = os.path.join(d, f"{j4}.log")
    with open(log, "w", encoding="utf-8") as f:
        f.write("x\n")
    os.utime(log, (time.time() - 3600 * 25,) * 2)
    try:
        st = repair_runner.get_job_status(j4)
        chk(st.get("status") == "interrupted",
            "فایل وضعیت با BOM (خروجی PowerShell) درست خوانده می‌شود",
            f"status={st.get('status')}")
    finally:
        _cleanup(j4)

    print()
    print("─" * 64)
    print(f"نتیجه: {P} موفق، {F} ناموفق")
    shutil.rmtree(_TMP_STATE, ignore_errors=True)
    sys.exit(1 if F else 0)


if __name__ == "__main__":
    main()
