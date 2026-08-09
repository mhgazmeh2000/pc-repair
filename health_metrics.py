# -*- coding: utf-8 -*-
"""
سنجه‌های عددی سلامت سیستم — پایهٔ «حلقهٔ بستهٔ تأیید نتیجه»

چرا این ماژول جدا از system_query است؟
──────────────────────────────────────
system_query خروجی *متنی* می‌دهد که برای خواندن AI عالی است، اما
قابل مقایسه نیست. نمی‌شود گفت «این متن از آن متن بهتر است».

اینجا همان اطلاعات را به عدد تبدیل می‌کنیم:

    قبل از تعمیر:  disk_c_free_pct = 4.2
    بعد از تعمیر:  disk_c_free_pct = 31.8
    → بهبود ۲۷.۶ واحد  ✅ واقعاً حل شد

بدون این، AI دستور می‌داد، دستور اجرا می‌شد، و هیچ‌کس نمی‌دانست
مشکل حل شد یا نه. کاربر می‌گفت «هنوز کنده» و AI از صفر شروع می‌کرد.

هر سنجه یک دیکشنری برمی‌گرداند:
    key        شناسهٔ یکتا
    value      عدد (float) یا None اگر قابل اندازه‌گیری نبود
    unit       واحد برای نمایش
    label_fa   نام فارسی
    higher_is_better  جهت بهبود
    error      اگر اندازه‌گیری شکست خورد
"""

import os
import re
import subprocess

_TIMEOUT = 25


def _ps(script, timeout=_TIMEOUT):
    """اجرای PowerShell و برگرداندن stdout تمیز."""
    if os.name != "nt":
        return ""
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive",
             "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, timeout=timeout,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        out = r.stdout.decode("utf-8", errors="replace").strip()
        if not out:
            out = r.stderr.decode("utf-8", errors="replace").strip()
        return out
    except Exception:
        return ""


def _first_float(text):
    """اولین عدد اعشاری متن. None اگر نبود."""
    if not text:
        return None
    m = re.search(r"-?\d+(?:[.,]\d+)?", text.replace(",", "."))
    if not m:
        return None
    try:
        return float(m.group(0))
    except ValueError:
        return None


def _metric(key, label_fa, unit, higher_is_better, value=None, error=""):
    return {
        "key": key,
        "label_fa": label_fa,
        "unit": unit,
        "higher_is_better": higher_is_better,
        "value": value,
        "error": error,
    }


# ═══════════════════════════ سنجه‌ها ═══════════════════════════

def _m_disk_c_free_pct():
    m = _metric("disk_c_free_pct", "فضای آزاد درایو C", "%", True)
    out = _ps(
        "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; "
        "if($d){[math]::Round($d.FreeSpace/$d.Size*100,2)}"
    )
    v = _first_float(out)
    if v is None:
        m["error"] = "اندازه‌گیری ممکن نشد"
    else:
        m["value"] = v
    return m


def _m_disk_c_free_gb():
    m = _metric("disk_c_free_gb", "فضای آزاد درایو C", "GB", True)
    out = _ps(
        "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='C:'\"; "
        "if($d){[math]::Round($d.FreeSpace/1GB,2)}"
    )
    v = _first_float(out)
    if v is None:
        m["error"] = "اندازه‌گیری ممکن نشد"
    else:
        m["value"] = v
    return m


def _m_ram_free_pct():
    m = _metric("ram_free_pct", "حافظهٔ آزاد", "%", True)
    out = _ps(
        "$o=Get-CimInstance Win32_OperatingSystem; "
        "[math]::Round($o.FreePhysicalMemory/$o.TotalVisibleMemorySize*100,2)"
    )
    v = _first_float(out)
    if v is None:
        m["error"] = "اندازه‌گیری ممکن نشد"
    else:
        m["value"] = v
    return m


def _m_temp_size_mb():
    m = _metric("temp_size_mb", "حجم فایل‌های موقت", "MB", False)
    out = _ps(
        "$p=$env:TEMP; "
        "if(Test-Path $p){"
        "$s=(Get-ChildItem $p -Recurse -Force -ErrorAction SilentlyContinue | "
        "Measure-Object -Property Length -Sum).Sum; "
        "[math]::Round($s/1MB,2)} else {0}",
        timeout=40,
    )
    v = _first_float(out)
    if v is None:
        m["error"] = "اندازه‌گیری ممکن نشد"
    else:
        m["value"] = v
    return m


def _m_startup_count():
    m = _metric("startup_count", "تعداد برنامه‌های استارتاپ", "مورد", False)
    out = _ps("(Get-CimInstance Win32_StartupCommand | Measure-Object).Count")
    v = _first_float(out)
    if v is None:
        m["error"] = "اندازه‌گیری ممکن نشد"
    else:
        m["value"] = v
    return m


def _m_sfc_corrupt():
    """
    آیا SFC فساد فایل گزارش کرده؟ ۰ = سالم، ۱ = فساد یافت شد.
    از لاگ CBS خوانده می‌شود؛ اجرای دوبارهٔ SFC ۱۵ دقیقه طول می‌کشد.
    """
    m = _metric("sfc_corrupt", "فساد فایل‌های سیستمی", "وضعیت", False)
    out = _ps(
        "$l=\"$env:windir\\Logs\\CBS\\CBS.log\"; "
        "if(Test-Path $l){"
        "$h=Select-String -Path $l -Pattern 'Cannot repair member file' "
        "-ErrorAction SilentlyContinue | Select-Object -Last 1; "
        "if($h){1}else{0}} else {0}",
        timeout=35,
    )
    v = _first_float(out)
    m["value"] = 0.0 if v is None else v
    return m


def _m_dism_health():
    """۰ = سالم، ۱ = قابل تعمیر، ۲ = غیرقابل تعمیر."""
    m = _metric("dism_health", "سلامت ایمیج ویندوز", "وضعیت", False)
    if os.name != "nt":
        m["error"] = "فقط ویندوز"
        return m
    try:
        r = subprocess.run(
            ["DISM", "/Online", "/Cleanup-Image", "/CheckHealth"],
            capture_output=True, timeout=90,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        txt = (r.stdout.decode("utf-8", errors="replace") or "").lower()
        if "no component store corruption" in txt or "قابل تعمیر" not in txt and "repairable" not in txt:
            m["value"] = 0.0
        elif "repairable" in txt:
            m["value"] = 1.0
        else:
            m["value"] = 2.0
    except Exception:
        m["error"] = "اجرای DISM ممکن نشد"
    return m


def _m_pending_reboot():
    """
    ۱ = ری‌استارت معلق دارد.
    خیلی از «تعمیر کار نکرد»ها فقط همین است.
    """
    m = _metric("pending_reboot", "ری‌استارت معلق", "وضعیت", False)
    out = _ps(
        "$k1='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\"
        "Component Based Servicing\\RebootPending'; "
        "$k2='HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\"
        "WindowsUpdate\\Auto Update\\RebootRequired'; "
        "if((Test-Path $k1) -or (Test-Path $k2)){1}else{0}"
    )
    v = _first_float(out)
    m["value"] = 0.0 if v is None else v
    return m


def _m_net_latency_ms():
    m = _metric("net_latency_ms", "تأخیر شبکه", "میلی‌ثانیه", False)
    out = _ps(
        "try{$p=Test-Connection -ComputerName 8.8.8.8 -Count 2 "
        "-ErrorAction Stop; "
        "[math]::Round(($p | Measure-Object -Property ResponseTime "
        "-Average).Average,0)}catch{-1}",
        timeout=20,
    )
    v = _first_float(out)
    if v is None or v < 0:
        m["error"] = "اینترنت در دسترس نیست"
    else:
        m["value"] = v
    return m


def _m_dns_ok():
    m = _metric("dns_ok", "کارکرد DNS", "وضعیت", True)
    out = _ps(
        "try{$null=Resolve-DnsName -Name www.microsoft.com "
        "-ErrorAction Stop; 1}catch{0}",
        timeout=20,
    )
    v = _first_float(out)
    m["value"] = 0.0 if v is None else v
    return m


def _m_error_events_24h():
    m = _metric("error_events_24h", "خطاهای سیستمی ۲۴ ساعت گذشته", "مورد", False)
    out = _ps(
        "$s=(Get-Date).AddHours(-24); "
        "try{(Get-WinEvent -FilterHashtable @{LogName='System';"
        "Level=1,2;StartTime=$s} -ErrorAction Stop | "
        "Measure-Object).Count}catch{0}",
        timeout=40,
    )
    v = _first_float(out)
    m["value"] = 0.0 if v is None else v
    return m


def _m_problem_drivers():
    m = _metric("problem_drivers", "درایورهای مشکل‌دار", "مورد", False)
    out = _ps(
        "(Get-CimInstance Win32_PnPEntity | "
        "Where-Object {$_.ConfigManagerErrorCode -ne 0} | "
        "Measure-Object).Count"
    )
    v = _first_float(out)
    m["value"] = 0.0 if v is None else v
    return m


def _m_defender_realtime():
    m = _metric("defender_realtime", "محافظت زندهٔ Defender", "وضعیت", True)
    out = _ps(
        "try{if((Get-MpComputerStatus -ErrorAction Stop)."
        "RealTimeProtectionEnabled){1}else{0}}catch{-1}"
    )
    v = _first_float(out)
    if v is None or v < 0:
        m["error"] = "Defender در دسترس نیست"
    else:
        m["value"] = v
    return m


def _m_boot_time_sec():
    m = _metric("boot_time_sec", "زمان آخرین بوت", "ثانیه", False)
    out = _ps(
        "try{$e=Get-WinEvent -FilterHashtable @{LogName="
        "'Microsoft-Windows-Diagnostics-Performance/Operational';"
        "Id=100} -MaxEvents 1 -ErrorAction Stop; "
        "[math]::Round($e.Properties[1].Value/1000,1)}catch{-1}",
        timeout=35,
    )
    v = _first_float(out)
    if v is None or v < 0:
        m["error"] = "گزارش کارایی در دسترس نیست"
    else:
        m["value"] = v
    return m


# ═══════════════════════════ رجیستری ═══════════════════════════

METRICS = {
    "disk_c_free_pct":   _m_disk_c_free_pct,
    "disk_c_free_gb":    _m_disk_c_free_gb,
    "ram_free_pct":      _m_ram_free_pct,
    "temp_size_mb":      _m_temp_size_mb,
    "startup_count":     _m_startup_count,
    "sfc_corrupt":       _m_sfc_corrupt,
    "dism_health":       _m_dism_health,
    "pending_reboot":    _m_pending_reboot,
    "net_latency_ms":    _m_net_latency_ms,
    "dns_ok":            _m_dns_ok,
    "error_events_24h":  _m_error_events_24h,
    "problem_drivers":   _m_problem_drivers,
    "defender_realtime": _m_defender_realtime,
    "boot_time_sec":     _m_boot_time_sec,
}

# ═══════════ کدام مرحلهٔ تعمیر روی کدام سنجه اثر دارد ═══════════
#
# این نگاشت قلب حلقهٔ بسته است: بعد از هر تعمیر فقط سنجه‌های مرتبط
# دوباره خوانده می‌شوند، نه همه‌شان. اندازه‌گیری برخی سنجه‌ها
# (مثل temp_size_mb) کند است و اندازه‌گیری بی‌مورد وقت تلف می‌کند.

STEP_METRICS = {
    "sfc":          ["sfc_corrupt", "error_events_24h"],
    "dism_check":   ["dism_health"],
    "dism_restore": ["dism_health", "sfc_corrupt"],
    "flushdns":     ["dns_ok", "net_latency_ms"],
    "winsock":      ["dns_ok", "net_latency_ms"],
    "renew_ip":     ["net_latency_ms", "dns_ok"],
    "temp_clean":   ["temp_size_mb", "disk_c_free_pct", "disk_c_free_gb"],
    "cleanmgr":     ["disk_c_free_pct", "disk_c_free_gb"],
    "chkdsk":       ["error_events_24h"],
}

# آستانهٔ معنادار بودن تغییر — زیر این مقدار نویز است، نه بهبود.
# مثلاً فضای دیسک همیشه چند دهم درصد بالا-پایین می‌شود.
NOISE_THRESHOLD = {
    "disk_c_free_pct":  0.5,
    "disk_c_free_gb":   0.3,
    "ram_free_pct":     3.0,
    "temp_size_mb":     10.0,
    "net_latency_ms":   15.0,
    "boot_time_sec":    3.0,
    "error_events_24h": 1.0,
}
_DEFAULT_NOISE = 0.001      # سنجه‌های وضعیتی: هر تغییری مهم است


def metrics_for_steps(step_keys):
    """سنجه‌های مرتبط با مجموعه‌ای از مراحل، بدون تکرار."""
    seen, out = set(), []
    for s in (step_keys or []):
        for k in STEP_METRICS.get(s, []):
            if k not in seen:
                seen.add(k)
                out.append(k)
    return out


def snapshot(keys=None):
    """
    عکس‌برداری از وضعیت فعلی.
    keys=None یعنی همهٔ سنجه‌ها (کند است — فقط برای خط پایه).
    """
    keys = list(METRICS.keys()) if keys is None else keys
    result = {}
    for k in keys:
        fn = METRICS.get(k)
        if not fn:
            continue
        try:
            result[k] = fn()
        except Exception as e:
            result[k] = _metric(k, k, "", True, error=str(e)[:80])
    return result


def compare(before, after):
    """
    مقایسهٔ دو عکس و تولید گزارش قابل فهم.

    برای هر سنجه یکی از این حالت‌ها:
        improved   بهتر شد
        worsened   بدتر شد
        unchanged  تغییر معنادار نکرد
        unknown    یکی از دو اندازه‌گیری شکست خورد
    """
    rows = []
    for key in (before or {}):
        b = (before or {}).get(key, {})
        a = (after or {}).get(key, {})
        bv, av = b.get("value"), a.get("value")

        row = {
            "key": key,
            "label_fa": b.get("label_fa") or a.get("label_fa") or key,
            "unit": b.get("unit") or a.get("unit") or "",
            "before": bv,
            "after": av,
            "delta": None,
            "status": "unknown",
        }

        if bv is None or av is None:
            row["note"] = b.get("error") or a.get("error") or "اندازه‌گیری نشد"
            rows.append(row)
            continue

        delta = av - bv
        row["delta"] = round(delta, 2)
        threshold = NOISE_THRESHOLD.get(key, _DEFAULT_NOISE)

        if abs(delta) < threshold:
            row["status"] = "unchanged"
        else:
            higher_better = b.get("higher_is_better", a.get("higher_is_better", True))
            improved = (delta > 0) if higher_better else (delta < 0)
            row["status"] = "improved" if improved else "worsened"

        rows.append(row)

    improved = sum(1 for r in rows if r["status"] == "improved")
    worsened = sum(1 for r in rows if r["status"] == "worsened")
    unchanged = sum(1 for r in rows if r["status"] == "unchanged")

    if improved and not worsened:
        verdict = "resolved"
    elif improved and worsened:
        verdict = "partial"
    elif worsened:
        verdict = "regressed"
    elif unchanged:
        verdict = "no_change"
    else:
        verdict = "unknown"

    return {
        "rows": rows,
        "improved": improved,
        "worsened": worsened,
        "unchanged": unchanged,
        "verdict": verdict,
        "summary_fa": _verdict_fa(verdict, improved, worsened, unchanged),
    }


def _verdict_fa(verdict, imp, wor, unc):
    return {
        "resolved":  f"✅ وضعیت بهتر شد — {imp} سنجه بهبود یافت.",
        "partial":   f"⚠️ بهبود جزئی — {imp} بهتر، {wor} بدتر شد.",
        "regressed": f"❌ وضعیت بدتر شد — {wor} سنجه افت کرد.",
        "no_change": f"➖ تغییر معناداری دیده نشد ({unc} سنجه ثابت ماند). "
                     "علت مشکل احتمالاً جای دیگری است.",
        "unknown":   "❓ اندازه‌گیری قابل اتکا نبود.",
    }.get(verdict, "")


def format_for_ai(cmp_result, step_titles=None):
    """
    تبدیل نتیجهٔ مقایسه به متن فارسی برای AI.

    این متن به مدل داده می‌شود تا بداند تعمیر مؤثر بوده یا نه و
    گام بعدی را بر همان اساس پیشنهاد دهد — نه از صفر شروع کند.
    """
    if not cmp_result or not cmp_result.get("rows"):
        return ""

    lines = ["## نتیجهٔ سنجش قبل و بعد از تعمیر", ""]
    if step_titles:
        lines.append("مراحل اجراشده: " + "، ".join(step_titles))
        lines.append("")

    lines.append(cmp_result.get("summary_fa", ""))
    lines.append("")
    lines.append("| سنجه | قبل | بعد | تغییر | وضعیت |")
    lines.append("|---|---|---|---|---|")

    icon = {"improved": "✅ بهبود", "worsened": "❌ افت",
            "unchanged": "➖ بدون تغییر", "unknown": "❓ نامشخص"}

    for r in cmp_result["rows"]:
        b = "—" if r["before"] is None else f"{r['before']:g}"
        a = "—" if r["after"] is None else f"{r['after']:g}"
        d = "—" if r["delta"] is None else f"{r['delta']:+g}"
        u = r["unit"]
        lines.append(
            f"| {r['label_fa']} | {b} {u} | {a} {u} | {d} | {icon.get(r['status'], '')} |"
        )

    lines.append("")
    v = cmp_result.get("verdict")
    if v == "no_change":
        lines.append(
            "**توجه:** هیچ سنجه‌ای تغییر معنادار نکرد. یعنی این تعمیرها به "
            "ریشهٔ مشکل نخورده‌اند. به‌جای تکرار همین دستورها، علت دیگری را "
            "بررسی کن و در صورت نیاز اطلاعات بیشتری بخواه."
        )
    elif v == "regressed":
        lines.append(
            "**هشدار:** وضعیت بدتر شده است. بررسی کن آیا یکی از دستورها "
            "عارضهٔ جانبی داشته و راه بازگشت را پیشنهاد بده."
        )
    elif v == "partial":
        lines.append(
            "**توجه:** بخشی بهتر و بخشی بدتر شد. روی سنجه‌هایی که افت "
            "کرده‌اند تمرکز کن."
        )
    return "\n".join(lines)
