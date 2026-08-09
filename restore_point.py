# -*- coding: utf-8 -*-
"""
نقطهٔ بازگشت سیستم — تور نجات پیش از تعمیرهای پرریسک

چرا لازم است
────────────
دستورهای سطح `caution` مثل پاک‌سازی رجیستری، بازنشانی Winsock یا
غیرفعال کردن سرویس‌ها ممکن است عارضهٔ جانبی داشته باشند. اگر چیزی
خراب شود، کاربر راهی برای برگشت ندارد و باید ویندوز را نصب کند.

System Restore دقیقاً برای همین ساخته شده — ولی کسی یادش نمی‌ماند
قبل از کار دستی بسازد. اینجا خودکار ساخته می‌شود.

سه محدودیت واقعی ویندوز که باید مدیریت شوند
────────────────────────────────────────────
۱. اگر System Protection خاموش باشد، ساخت نقطه بی‌صدا شکست می‌خورد
۲. ویندوز به‌طور پیش‌فرض بیش از یک نقطه در هر ۲۴ ساعت نمی‌سازد
   (کلید رجیستری SystemRestorePointCreationFrequency)
۳. نیاز به دسترسی ادمین دارد

هر سه اینجا بررسی و صادقانه گزارش می‌شوند — نه اینکه وانمود کنیم
نقطه ساخته شده در حالی که نشده.
"""

import os
import re
import subprocess
import time

# ساخت نقطه گاهی طول می‌کشد، مخصوصاً روی دیسک کند
CREATE_TIMEOUT = 180
QUERY_TIMEOUT = 45

# فاصلهٔ حداقلی بین دو نقطهٔ خودکار ما (دقیقه).
# ویندوز خودش ۲۴ ساعت محدودیت دارد ولی ما آن را دور می‌زنیم؛
# این عدد جلوی ساخت بی‌رویه را می‌گیرد.
MIN_INTERVAL_MIN = 30

_LAST_CREATED = {"time": 0.0, "name": ""}


def _ps(script, timeout=QUERY_TIMEOUT, as_admin_check=False):
    """اجرای PowerShell. برگشت (کد خروج، stdout، stderr)."""
    if os.name != "nt":
        return 1, "", "فقط روی ویندوز کار می‌کند"
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        err = r.stderr.decode("utf-8", errors="replace").strip()
        return r.returncode, out, err
    except subprocess.TimeoutExpired:
        return 1, "", "زمان اجرا به پایان رسید"
    except Exception as e:
        return 1, "", str(e)


def is_admin():
    if os.name != "nt":
        return False
    try:
        import ctypes
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def protection_status():
    """
    آیا System Protection روی درایو سیستم روشن است؟

    بدون این، فرمان ساخت نقطه بدون خطا برمی‌گردد ولی هیچ نقطه‌ای
    ساخته نمی‌شود — بدترین حالت ممکن.
    """
    if os.name != "nt":
        return {"available": False, "enabled": False,
                "reason": "فقط روی ویندوز در دسترس است."}

    code, out, err = _ps(
        "try { $d = Get-ComputerRestorePoint -ErrorAction Stop | "
        "Measure-Object; 'OK:' + $d.Count } "
        "catch { 'ERR:' + $_.Exception.Message }"
    )
    if out.startswith("OK:"):
        return {"available": True, "enabled": True,
                "points": int(re.sub(r"\D", "", out) or 0), "reason": ""}

    # روش دوم: مستقیم از WMI
    code2, out2, _ = _ps(
        "try { $s = Get-CimInstance -Namespace root/default "
        "-ClassName SystemRestore -ErrorAction Stop | Measure-Object; "
        "'OK:' + $s.Count } catch { 'ERR' }"
    )
    if out2.startswith("OK:"):
        return {"available": True, "enabled": True,
                "points": int(re.sub(r"\D", "", out2) or 0), "reason": ""}

    return {
        "available": True, "enabled": False, "points": 0,
        "reason": "محافظت سیستم (System Protection) روی درایو C خاموش است. "
                  "بدون آن نقطهٔ بازگشت ساخته نمی‌شود.",
    }


def enable_protection():
    """
    روشن کردن System Protection روی درایو C.
    نیاز به ادمین دارد و ممکن است چند ثانیه طول بکشد.
    """
    if os.name != "nt":
        return {"success": False, "error": "فقط روی ویندوز."}
    if not is_admin():
        return {"success": False,
                "error": "برای روشن کردن محافظت سیستم، برنامه باید با "
                         "دسترسی مدیر اجرا شود."}

    code, out, err = _ps(
        "try { Enable-ComputerRestore -Drive 'C:\\' -ErrorAction Stop; 'OK' } "
        "catch { 'ERR:' + $_.Exception.Message }",
        timeout=90,
    )
    if out.startswith("OK"):
        return {"success": True,
                "message": "محافظت سیستم روی درایو C روشن شد."}
    return {"success": False,
            "error": "روشن کردن ناموفق بود: " + (out or err)[:160]}


def _bypass_frequency_limit():
    """
    ویندوز بیش از یک نقطه در ۲۴ ساعت نمی‌سازد. برای تعمیرهای پیاپی
    این محدودیت مانع است. مقدار صفر یعنی «بدون محدودیت».

    برگشت True اگر تنظیم شد. اگر نشد هم ادامه می‌دهیم — فقط ممکن است
    نقطهٔ جدید ساخته نشود.
    """
    code, out, _ = _ps(
        "try { New-ItemProperty -Path 'HKLM:\\SOFTWARE\\Microsoft\\Windows NT\\"
        "CurrentVersion\\SystemRestore' -Name 'SystemRestorePointCreationFrequency' "
        "-Value 0 -PropertyType DWord -Force -ErrorAction Stop | Out-Null; 'OK' } "
        "catch { 'ERR' }",
        timeout=30,
    )
    return out.startswith("OK")


def create(description=None, reason="پیش از تعمیر خودکار"):
    """
    ساخت نقطهٔ بازگشت.

    خروجی همیشه شامل `success` و در صورت شکست، دلیل قابل فهم فارسی
    است. هرگز وانمود نمی‌کند که ساخته شده.
    """
    if os.name != "nt":
        return {"success": False, "skipped": True,
                "error": "نقطهٔ بازگشت فقط روی ویندوز ساخته می‌شود."}

    # فاصلهٔ خیلی کم = احتمالاً تکراری
    since = time.time() - _LAST_CREATED["time"]
    if _LAST_CREATED["time"] and since < MIN_INTERVAL_MIN * 60:
        return {
            "success": True, "skipped": True,
            "name": _LAST_CREATED["name"],
            "message": f"نقطهٔ بازگشت {int(since / 60)} دقیقه پیش ساخته شده "
                       "و هنوز معتبر است.",
        }

    if not is_admin():
        return {"success": False,
                "error": "ساخت نقطهٔ بازگشت به دسترسی مدیر نیاز دارد. "
                         "برنامه را با «Run as administrator» اجرا کنید."}

    st = protection_status()
    if st.get("available") and not st.get("enabled"):
        return {"success": False, "needs_protection": True,
                "error": st.get("reason", "محافظت سیستم خاموش است.")}

    desc = description or f"PC Repair — {reason} — {time.strftime('%Y/%m/%d %H:%M')}"
    # کوتیشن تکی در PowerShell با دوتا escape می‌شود
    safe_desc = desc.replace("'", "''")

    _bypass_frequency_limit()

    code, out, err = _ps(
        f"try {{ Checkpoint-Computer -Description '{safe_desc}' "
        "-RestorePointType 'MODIFY_SETTINGS' -ErrorAction Stop; 'OK' } "
        "catch { 'ERR:' + $_.Exception.Message }",
        timeout=CREATE_TIMEOUT,
    )

    if out.startswith("OK"):
        _LAST_CREATED["time"] = time.time()
        _LAST_CREATED["name"] = desc
        return {"success": True, "name": desc,
                "message": "نقطهٔ بازگشت ساخته شد. اگر تعمیر مشکلی ایجاد کرد، "
                           "می‌توانید سیستم را به همین لحظه برگردانید."}

    detail = (out or err).replace("ERR:", "").strip()
    return {"success": False,
            "error": "ساخت نقطهٔ بازگشت ناموفق بود: " + (detail[:200] or "دلیل نامشخص")}


def list_points(limit=10):
    """فهرست نقاط بازگشت موجود."""
    if os.name != "nt":
        return {"success": True, "points": [],
                "note": "فقط روی ویندوز در دسترس است."}

    code, out, err = _ps(
        "Get-ComputerRestorePoint -ErrorAction SilentlyContinue | "
        f"Sort-Object CreationTime -Descending | Select-Object -First {int(limit)} "
        "SequenceNumber,Description,"
        "@{N='When';E={$_.ConvertToDateTime($_.CreationTime)}} | "
        "ConvertTo-Json -Compress",
        timeout=60,
    )
    if not out:
        return {"success": True, "points": [],
                "note": "نقطهٔ بازگشتی یافت نشد یا محافظت سیستم خاموش است."}

    import json as _json
    try:
        data = _json.loads(out)
        if isinstance(data, dict):
            data = [data]
        points = []
        for d in data:
            points.append({
                "seq": d.get("SequenceNumber"),
                "desc": d.get("Description", ""),
                "when": str(d.get("When", "")),
            })
        return {"success": True, "points": points}
    except Exception:
        return {"success": True, "points": [], "raw": out[:400]}


def open_restore_ui():
    """
    باز کردن پنجرهٔ بازگردانی ویندوز.

    عمداً خودمان بازگردانی نمی‌کنیم: بازگرداندن سیستم عملیات
    پرمخاطره‌ای است که ری‌استارت می‌خواهد و باید کاربر آگاهانه و در
    محیط رسمی ویندوز انجامش دهد.
    """
    if os.name != "nt":
        return {"success": False, "error": "فقط روی ویندوز."}
    try:
        subprocess.Popen("rstrui.exe", shell=True)
        return {"success": True,
                "message": "پنجرهٔ بازگردانی سیستم باز شد."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def should_create_for(step_keys, risk_levels=None):
    """
    آیا این مجموعه مرحله ارزش ساخت نقطهٔ بازگشت را دارد؟

    ساخت نقطه چند ده ثانیه طول می‌کشد. برای `ipconfig /flushdns`
    ارزشش را ندارد؛ برای بازنشانی Winsock یا رجیستری دارد.
    """
    risky = {
        "winsock",        # پیکربندی شبکه را بازنشانی می‌کند
        "dism_restore",   # اجزای سیستمی را عوض می‌کند
        "chkdsk",         # روی ساختار فایل‌سیستم کار می‌کند
        "sfc",            # فایل‌های سیستمی را جایگزین می‌کند
    }
    for s in (step_keys or []):
        if s in risky:
            return True
    for lvl in (risk_levels or []):
        if lvl in ("caution", "blocked"):
            return True
    return False
