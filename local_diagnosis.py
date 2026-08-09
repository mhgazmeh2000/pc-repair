# -*- coding: utf-8 -*-
"""
تشخیص محلی بدون هوش مصنوعی — قواعد قطعی برای مشکلات شناخته‌شده

چرا؟
────
خیلی از مشکلات ویندوز الگوی کاملاً مشخصی دارند. برای فهمیدن اینکه
«درایو C فقط ۳٪ آزاد دارد پس سیستم کند است» نیازی به مدل زبانی نیست.

مزیت‌ها نسبت به فرستادن همه‌چیز به AI:
  • صفر توکن مصرف می‌کند — با مدل رایگان محدود، این مهم است
  • آفلاین کار می‌کند
  • قطعی و تکرارپذیر است، نه احتمالی
  • فوری است، نه چند ثانیه انتظار

AI برای موارد مبهم و تحلیل عمیق باقی می‌ماند. نتیجهٔ این ماژول هم
به‌عنوان زمینه به AI داده می‌شود تا دوباره کشفش نکند.

هر قاعده:
    id          شناسه
    severity    critical | warning | info
    title_fa    عنوان
    detail_fa   توضیح با مقدار واقعی
    steps       کلیدهای REPAIR_STEPS برای رفع
    tool_ids    شناسهٔ ابزارهای مرتبط در tools_data.json
"""

import health_metrics

CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {CRITICAL: 0, WARNING: 1, INFO: 2}
_SEVERITY_FA = {
    CRITICAL: "بحرانی",
    WARNING: "هشدار",
    INFO: "اطلاع",
}


def _val(snap, key):
    """مقدار عددی یک سنجه، یا None."""
    m = (snap or {}).get(key) or {}
    return m.get("value")


# ═══════════════════════════ قواعد ═══════════════════════════
#
# هر قاعده تابعی است که snapshot می‌گیرد و یا None برمی‌گرداند
# (یعنی مشکلی نیست) یا یک dict یافته.


def _r_disk_critical(s):
    v = _val(s, "disk_c_free_pct")
    gb = _val(s, "disk_c_free_gb")
    if v is None or v >= 10:
        return None
    sev = CRITICAL if v < 5 else WARNING
    gb_txt = f" (حدود {gb:g} گیگابایت)" if gb is not None else ""
    return {
        "id": "disk_low",
        "severity": sev,
        "title_fa": "فضای درایو C بحرانی است" if sev == CRITICAL
                    else "فضای درایو C رو به اتمام است",
        "detail_fa": (
            f"فقط {v:g}٪ از درایو C آزاد است{gb_txt}. "
            "ویندوز برای فایل موقت، حافظهٔ مجازی و به‌روزرسانی به فضای "
            "آزاد نیاز دارد؛ زیر ۱۰٪ باعث کندی محسوس و خطاهای عجیب می‌شود."
        ),
        "steps": ["temp_clean", "cleanmgr"],
        "tool_ids": [38, 39, 41, 42],
    }


def _r_temp_bloat(s):
    v = _val(s, "temp_size_mb")
    if v is None or v < 1024:
        return None
    return {
        "id": "temp_bloat",
        "severity": WARNING if v < 5120 else CRITICAL,
        "title_fa": "حجم فایل‌های موقت زیاد است",
        "detail_fa": (
            f"پوشهٔ Temp حدود {v/1024:.1f} گیگابایت فضا گرفته است. "
            "این فایل‌ها بی‌خطر پاک می‌شوند و فضای قابل توجهی آزاد می‌کنند."
        ),
        "steps": ["temp_clean"],
        "tool_ids": [37, 41],
    }


def _r_pending_reboot(s):
    if _val(s, "pending_reboot") != 1:
        return None
    return {
        "id": "pending_reboot",
        "severity": WARNING,
        "title_fa": "ری‌استارت معلق دارید",
        "detail_fa": (
            "ویندوز منتظر یک ری‌استارت است تا تغییرات نصب‌شده کامل شود. "
            "تا وقتی ری‌استارت نکنید، بسیاری از تعمیرها اثر نمی‌کنند و "
            "ممکن است خطاهای تکراری ببینید. این را قبل از هر کار دیگری "
            "انجام دهید."
        ),
        "steps": [],
        "tool_ids": [],
    }


def _r_sfc_corrupt(s):
    if _val(s, "sfc_corrupt") != 1:
        return None
    return {
        "id": "sfc_corrupt",
        "severity": CRITICAL,
        "title_fa": "فایل‌های سیستمی آسیب دیده‌اند",
        "detail_fa": (
            "لاگ CBS نشان می‌دهد SFC نتوانسته برخی فایل‌ها را تعمیر کند. "
            "معمولاً باید اول DISM اجرا شود تا منبع سالم بازیابی شود، "
            "سپس دوباره SFC."
        ),
        "steps": ["dism_restore", "sfc"],
        "tool_ids": [],
    }


def _r_dism_health(s):
    v = _val(s, "dism_health")
    if v is None or v == 0:
        return None
    if v == 1:
        return {
            "id": "dism_repairable",
            "severity": WARNING,
            "title_fa": "ایمیج ویندوز قابل تعمیر است",
            "detail_fa": "DISM فساد قابل تعمیر گزارش کرده. اجرای RestoreHealth رفعش می‌کند.",
            "steps": ["dism_restore"],
            "tool_ids": [],
        }
    return {
        "id": "dism_unrepairable",
        "severity": CRITICAL,
        "title_fa": "ایمیج ویندوز به‌صورت معمول قابل تعمیر نیست",
        "detail_fa": (
            "DISM فساد غیرقابل تعمیر گزارش کرده. ممکن است به منبع نصب "
            "(فایل ISO یا install.wim) نیاز باشد یا در نهایت نصب مجدد."
        ),
        "steps": ["dism_restore"],
        "tool_ids": [],
    }


def _r_startup_bloat(s):
    v = _val(s, "startup_count")
    if v is None or v <= 15:
        return None
    return {
        "id": "startup_bloat",
        "severity": WARNING if v <= 25 else CRITICAL,
        "title_fa": "برنامه‌های استارتاپ زیاد است",
        "detail_fa": (
            f"{int(v)} برنامه هنگام روشن شدن ویندوز اجرا می‌شوند. "
            "هر کدام چند ثانیه به زمان بوت اضافه می‌کند و در پس‌زمینه "
            "حافظه مصرف می‌کند. غیرفعال کردن موارد غیرضروری بیشترین "
            "تأثیر را روی سرعت بالا آمدن دارد."
        ),
        "steps": [],
        "tool_ids": [24],
    }


def _r_ram_pressure(s):
    v = _val(s, "ram_free_pct")
    if v is None or v >= 10:
        return None
    return {
        "id": "ram_pressure",
        "severity": CRITICAL if v < 5 else WARNING,
        "title_fa": "حافظهٔ سیستم تقریباً پر است",
        "detail_fa": (
            f"فقط {v:g}٪ از حافظه آزاد است. ویندوز مجبور می‌شود از دیسک "
            "به‌عنوان حافظهٔ مجازی استفاده کند که ده‌ها برابر کندتر است. "
            "برنامه‌های پرمصرف را ببندید یا به فکر ارتقای رم باشید."
        ),
        "steps": [],
        "tool_ids": [23, 25],
    }


def _r_dns_broken(s):
    if _val(s, "dns_ok") != 0:
        return None
    return {
        "id": "dns_broken",
        "severity": CRITICAL,
        "title_fa": "DNS کار نمی‌کند",
        "detail_fa": (
            "تبدیل نام دامنه به آدرس IP ناموفق بود. یعنی حتی اگر اینترنت "
            "وصل باشد، سایت‌ها باز نمی‌شوند. پاک‌سازی کش DNS و بازنشانی "
            "Winsock معمولاً رفعش می‌کند."
        ),
        "steps": ["flushdns", "winsock"],
        "tool_ids": [30, 31, 35],
    }


def _r_net_slow(s):
    v = _val(s, "net_latency_ms")
    if v is None or v < 200:
        return None
    return {
        "id": "net_slow",
        "severity": WARNING,
        "title_fa": "تأخیر شبکه بالاست",
        "detail_fa": (
            f"میانگین تأخیر {v:g} میلی‌ثانیه است. برای کار عادی قابل تحمل "
            "ولی برای تماس تصویری و بازی مشکل‌ساز است. اگر از پروکسی یا "
            "VPN استفاده می‌کنید، بخشی از تأخیر طبیعی است."
        ),
        "steps": ["flushdns", "renew_ip"],
        "tool_ids": [29, 30, 33],
    }


def _r_problem_drivers(s):
    v = _val(s, "problem_drivers")
    if v is None or v == 0:
        return None
    return {
        "id": "problem_drivers",
        "severity": WARNING,
        "title_fa": "درایور مشکل‌دار دارید",
        "detail_fa": (
            f"{int(v)} دستگاه با کد خطا در Device Manager دیده می‌شود "
            "(علامت تعجب زرد). این می‌تواند باعث کار نکردن سخت‌افزار، "
            "کندی یا صفحهٔ آبی شود."
        ),
        "steps": [],
        "tool_ids": [12, 44],
    }


def _r_defender_off(s):
    if _val(s, "defender_realtime") != 0:
        return None
    return {
        "id": "defender_off",
        "severity": CRITICAL,
        "title_fa": "محافظت زندهٔ Defender خاموش است",
        "detail_fa": (
            "آنتی‌ویروس ویندوز در حالت محافظت زنده نیست. اگر آنتی‌ویروس "
            "دیگری نصب نکرده‌اید، سیستم شما در معرض بدافزار است — که خودش "
            "یکی از دلایل رایج کندی و رفتار عجیب است."
        ),
        "steps": [],
        "tool_ids": [8],
    }


def _r_many_errors(s):
    v = _val(s, "error_events_24h")
    if v is None or v < 20:
        return None
    return {
        "id": "many_errors",
        "severity": WARNING if v < 50 else CRITICAL,
        "title_fa": "خطاهای سیستمی زیادی ثبت شده",
        "detail_fa": (
            f"در ۲۴ ساعت گذشته {int(v)} خطا یا خطای بحرانی در Event Viewer "
            "ثبت شده است. تعداد بالا معمولاً یعنی یک مشکل تکرارشونده وجود "
            "دارد — بررسی نوع خطاها گام بعدی است."
        ),
        "steps": [],
        "tool_ids": [14],
    }


def _r_slow_boot(s):
    v = _val(s, "boot_time_sec")
    if v is None or v < 60:
        return None
    return {
        "id": "slow_boot",
        "severity": WARNING,
        "title_fa": "زمان بوت طولانی است",
        "detail_fa": (
            f"آخرین بوت {v:g} ثانیه طول کشیده. بوت سالم روی SSD معمولاً "
            "زیر ۳۰ ثانیه است. برنامه‌های استارتاپ و سرویس‌های اضافه "
            "معمول‌ترین علت‌اند."
        ),
        "steps": [],
        "tool_ids": [24, 13],
    }


RULES = [
    _r_pending_reboot,      # اول: تا ری‌استارت نشود بقیه بی‌اثرند
    _r_disk_critical,
    _r_sfc_corrupt,
    _r_dism_health,
    _r_ram_pressure,
    _r_dns_broken,
    _r_defender_off,
    _r_temp_bloat,
    _r_startup_bloat,
    _r_problem_drivers,
    _r_many_errors,
    _r_net_slow,
    _r_slow_boot,
]

# سنجه‌هایی که برای اجرای همهٔ قواعد لازم است
REQUIRED_METRICS = [
    "disk_c_free_pct", "disk_c_free_gb", "ram_free_pct", "temp_size_mb",
    "startup_count", "sfc_corrupt", "dism_health", "pending_reboot",
    "net_latency_ms", "dns_ok", "error_events_24h", "problem_drivers",
    "defender_realtime", "boot_time_sec",
]

# سنجه‌های سریع — برای بررسی فوری بدون انتظار
FAST_METRICS = [
    "disk_c_free_pct", "disk_c_free_gb", "ram_free_pct",
    "startup_count", "pending_reboot", "problem_drivers",
]


def diagnose(snap=None, fast=False):
    """
    اجرای همهٔ قواعد روی یک عکس از سیستم.

    fast=True فقط سنجه‌های سریع را می‌خواند (چند ثانیه به‌جای ~۱ دقیقه).
    """
    if snap is None:
        keys = FAST_METRICS if fast else REQUIRED_METRICS
        snap = health_metrics.snapshot(keys)

    findings = []
    for rule in RULES:
        try:
            f = rule(snap)
            if f:
                findings.append(f)
        except Exception:
            continue        # یک قاعدهٔ خراب نباید کل تشخیص را بشکند

    findings.sort(key=lambda x: _SEVERITY_ORDER.get(x["severity"], 9))

    # مراحل تعمیر پیشنهادی، بدون تکرار و به ترتیب اولویت
    steps, seen = [], set()
    for f in findings:
        for st in f.get("steps", []):
            if st not in seen:
                seen.add(st)
                steps.append(st)

    counts = {
        "critical": sum(1 for f in findings if f["severity"] == CRITICAL),
        "warning":  sum(1 for f in findings if f["severity"] == WARNING),
        "info":     sum(1 for f in findings if f["severity"] == INFO),
    }

    return {
        "findings": findings,
        "counts": counts,
        "suggested_steps": steps,
        "snapshot": snap,
        "healthy": not findings,
        "summary_fa": _summary(counts, len(findings)),
    }


def _summary(counts, total):
    if total == 0:
        return "✅ در بررسی محلی هیچ مشکل شناخته‌شده‌ای پیدا نشد."
    parts = []
    if counts["critical"]:
        parts.append(f"{counts['critical']} مورد بحرانی")
    if counts["warning"]:
        parts.append(f"{counts['warning']} هشدار")
    if counts["info"]:
        parts.append(f"{counts['info']} نکته")
    return "بررسی محلی: " + "، ".join(parts) + " یافت شد."


def format_for_ai(result):
    """
    تبدیل یافته‌ها به متن برای AI.

    هدف: AI وقتش را صرف کشف دوبارهٔ چیزهایی که قطعی می‌دانیم نکند و
    روی تحلیل عمیق‌تر تمرکز کند.
    """
    if not result or not result.get("findings"):
        return ("### بررسی محلی سیستم\n"
                "هیچ مشکل شناخته‌شده‌ای در بررسی قاعده‌محور پیدا نشد.")

    lines = ["### بررسی محلی سیستم (قاعده‌محور، بدون AI)", ""]
    lines.append(result.get("summary_fa", ""))
    lines.append("")

    for f in result["findings"]:
        lines.append(f"**[{_SEVERITY_FA.get(f['severity'], '')}] {f['title_fa']}**")
        lines.append(f["detail_fa"])
        lines.append("")

    if result.get("suggested_steps"):
        lines.append("مراحل تعمیر پیشنهادی بر اساس این یافته‌ها: "
                     + "، ".join(result["suggested_steps"]))
        lines.append("")

    lines.append(
        "این یافته‌ها قطعی و اندازه‌گیری‌شده‌اند — دوباره بررسی‌شان نکن. "
        "روی تحلیل علت ریشه‌ای و مواردی که اینجا پوشش داده نشده تمرکز کن."
    )
    return "\n".join(lines)
