# -*- coding: utf-8 -*-
"""
system_query.py — پرس‌وجوی اطلاعات سیستم برای دستیار AI
====================================================================
هدف: AI بتواند هر اطلاعاتی که برای عیب‌یابی لازم دارد را درخواست کند،
بدون اینکه دسترسی اجرای دستور دلخواه داشته باشد.

مدل امنیتی:
    AI فقط می‌تواند از یک «فهرست بسته» انتخاب کند. هر آیتم یک تابع
    از پیش تعریف‌شده است که خروجی محدود و پاک‌سازی‌شده برمی‌گرداند.
    AI هرگز رشته دستور نمی‌فرستد — فقط نام آیتم.

    این طراحی عمدی است: اگر AI می‌توانست دستور دلخواه اجرا کند،
    prompt injection مستقیماً به اجرای کد تبدیل می‌شد.
"""

import os
import re
import json
import time
import base64
import platform
import subprocess

_CACHE = {}
_CACHE_TTL = 30  # ثانیه


def _run(cmd, timeout=20):
    if os.name != 'nt':
        return ""
    try:
        # encoding=utf-8: خروجی PowerShell را با UTF-8 می‌خوانیم (پس از
        # تنظیم OutputEncoding داخل اسکریپت) — رمزگشایی با locale (cp1252)
        # متن فارسی را به حروف نامفهوم تبدیل می‌کرد.
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                           shell=True, timeout=timeout, errors="ignore")
        return (r.stdout or "").strip()
    except Exception as e:
        return f"[خطا در اجرا: {e}]"


def _ps(script, timeout=25):
    """
    اجرای اسکریپت PowerShell بدون خرابی متن فارسی.

    مشکل نسخهٔ قبلی: اسکریپت با -Command "..." از طریق cmd.exe (shell=True)
    ارسال می‌شد؛ cmd.exe متن غیر-ASCII را با کدپیج OEM به «؟» تبدیل می‌کرد و
    کوئوت‌های escape‌شده (\") هم ناقص می‌ماندند — نتیجهٔ خروجی خالی یا متن
    نامفهوم. اینجا اسکریپت با -EncodedCommand (Base64 UTF-16LE) فرستاده
    می‌شود که کاملاً از دستکاری cmd.exe در امان است.
    """
    if os.name != 'nt':
        return ""
    # کوئوت‌های دوتایی داخل اسکریپت‌های قدیمی به‌صورت \" نوشته شده‌اند
    # (مخصوص -Command) — با EncodedCommand باید به «"» ساده برگردند.
    script = script.replace('\\"', '"')
    # خروجی را UTF-8 کن تا متن فارسی درست خوانده شود
    script = "[Console]::OutputEncoding=[Text.Encoding]::UTF8; " + script
    b64 = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
    return _run('powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass '
                f'-EncodedCommand {b64}', timeout)


def _limit(text, max_lines=40, max_chars=3000):
    """خروجی را برای صرفه‌جویی توکن محدود می‌کند."""
    if not text:
        return "(خروجی خالی)"
    lines = [l.rstrip() for l in text.split("\n") if l.strip()]
    if len(lines) > max_lines:
        lines = lines[:max_lines] + [f"... ({len(lines) - max_lines} خط دیگر)"]
    out = "\n".join(lines)
    return out[:max_chars] + ("\n...[بریده شد]" if len(out) > max_chars else "")


# ---------------------------------------------------------------------------
# توابع جمع‌آوری اطلاعات
# ---------------------------------------------------------------------------
def _q_os():
    if os.name != 'nt':
        return f"{platform.system()} {platform.release()} ({platform.machine()})"
    return _limit(_ps(
        "$o=Get-CimInstance Win32_OperatingSystem; "
        "\\\"$($o.Caption) | Build $($o.BuildNumber) | نصب: $($o.InstallDate) | "
        "آخرین بوت: $($o.LastBootUpTime)\\\""), 10)


def _q_cpu():
    return _limit(_ps(
        "Get-CimInstance Win32_Processor | "
        "Select-Object Name,NumberOfCores,NumberOfLogicalProcessors,"
        "MaxClockSpeed,LoadPercentage | Format-List | Out-String"), 20)


def _q_memory():
    if os.name != 'nt':
        return "(فقط ویندوز)"
    return _limit(_ps(
        "$m=Get-CimInstance Win32_OperatingSystem; "
        "$t=[math]::Round($m.TotalVisibleMemorySize/1MB,2); "
        "$f=[math]::Round($m.FreePhysicalMemory/1MB,2); "
        "\\\"کل: $t GB | آزاد: $f GB | مصرف: $([math]::Round(($t-$f)/$t*100,1))%\\\"; "
        "Get-CimInstance Win32_PhysicalMemory | "
        "Select-Object @{N='ماژول';E={[math]::Round($_.Capacity/1GB,0).ToString()+'GB'}},"
        "Speed,Manufacturer | Format-Table -AutoSize | Out-String"), 20)


def _q_disks():
    return _limit(_ps(
        "Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3' | "
        "Select-Object DeviceID,@{N='TotalGB';E={[math]::Round($_.Size/1GB,1)}},"
        "@{N='FreeGB';E={[math]::Round($_.FreeSpace/1GB,1)}},"
        "@{N='Used%';E={[math]::Round(($_.Size-$_.FreeSpace)/$_.Size*100,1)}} | "
        "Format-Table -AutoSize | Out-String"), 25)


def _q_disk_health():
    return _limit(_ps(
        "Get-PhysicalDisk | Select-Object FriendlyName,MediaType,"
        "HealthStatus,OperationalStatus,"
        "@{N='SizeGB';E={[math]::Round($_.Size/1GB,0)}} | "
        "Format-Table -AutoSize | Out-String"), 25)


def _q_startup():
    return _limit(_ps(
        "Get-CimInstance Win32_StartupCommand | "
        "Select-Object Name,Command,Location | "
        "Format-Table -AutoSize -Wrap | Out-String"), 35)


def _q_top_cpu():
    return _limit(_ps(
        "Get-Process | Sort-Object CPU -Descending | Select-Object -First 12 "
        "Name,Id,@{N='CPU_s';E={[math]::Round($_.CPU,1)}},"
        "@{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
        "Format-Table -AutoSize | Out-String"), 20)


def _q_top_memory():
    return _limit(_ps(
        "Get-Process | Sort-Object WorkingSet64 -Descending | Select-Object -First 12 "
        "Name,Id,@{N='RAM_MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
        "Format-Table -AutoSize | Out-String"), 20)


def _q_services_stopped():
    return _limit(_ps(
        "Get-Service | Where-Object {$_.StartType -eq 'Automatic' -and "
        "$_.Status -ne 'Running'} | Select-Object Name,DisplayName,Status | "
        "Format-Table -AutoSize | Out-String"), 30)


def _q_network():
    return _limit(_run("ipconfig /all", 15), 45)


def _q_network_test():
    out = []
    out.append("--- ping 8.8.8.8 ---")
    out.append(_run("ping -n 3 8.8.8.8", 20))
    out.append("--- DNS ---")
    out.append(_run("nslookup google.com", 15))
    return _limit("\n".join(out), 35)


def _q_events_system():
    return _limit(_ps(
        "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;"
        "StartTime=(Get-Date).AddDays(-7)} -MaxEvents 15 -ErrorAction SilentlyContinue | "
        "Select-Object TimeCreated,Id,ProviderName,"
        "@{N='Msg';E={$_.Message.Substring(0,[Math]::Min(120,$_.Message.Length))}} | "
        "Format-List | Out-String"), 60, 4000)


def _q_events_app():
    return _limit(_ps(
        "Get-WinEvent -FilterHashtable @{LogName='Application';Level=1,2;"
        "StartTime=(Get-Date).AddDays(-7)} -MaxEvents 15 -ErrorAction SilentlyContinue | "
        "Select-Object TimeCreated,Id,ProviderName,"
        "@{N='Msg';E={$_.Message.Substring(0,[Math]::Min(120,$_.Message.Length))}} | "
        "Format-List | Out-String"), 60, 4000)


def _q_bsod():
    return _limit(_ps(
        "Get-WinEvent -FilterHashtable @{LogName='System';Id=41,1001,6008} "
        "-MaxEvents 10 -ErrorAction SilentlyContinue | "
        "Select-Object TimeCreated,Id,"
        "@{N='Msg';E={$_.Message.Substring(0,[Math]::Min(150,$_.Message.Length))}} | "
        "Format-List | Out-String"), 40)


def _q_drivers_problem():
    return _limit(_ps(
        "Get-CimInstance Win32_PnPEntity | "
        "Where-Object {$_.ConfigManagerErrorCode -ne 0} | "
        "Select-Object Name,DeviceID,ConfigManagerErrorCode,Status | "
        "Format-List | Out-String"), 40)


def _q_installed():
    return _limit(_ps(
        "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*,"
        "HKLM:\\Software\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\* "
        "-ErrorAction SilentlyContinue | Where-Object DisplayName | "
        "Select-Object DisplayName,DisplayVersion,Publisher | "
        "Sort-Object DisplayName | Format-Table -AutoSize | Out-String"), 60, 4500)


def _q_updates():
    return _limit(_ps(
        "Get-HotFix | Sort-Object InstalledOn -Descending | Select-Object -First 15 "
        "HotFixID,Description,InstalledOn | Format-Table -AutoSize | Out-String"), 25)


def _q_temp_size():
    if os.name != 'nt':
        return "(فقط ویندوز)"
    # فقط دو محل اصلی تمپ؛ پوشهٔ SoftwareDistribution (کش آپدیت ویندوز)
    # عمداً نیست چون روی بعضی سیستم‌ها صدها‌هزار فایل دارد و پاسخ AI را
    # ده‌ها ثانیه متوقف می‌کند.
    return _limit(_ps(
        "$p=@($env:TEMP,'C:\\Windows\\Temp');"
        "foreach($d in $p){ if(Test-Path $d){ "
        "$s=(Get-ChildItem $d -Recurse -Force -ErrorAction SilentlyContinue | "
        "Measure-Object Length -Sum); "
        "\\\"$d : $([math]::Round($s.Sum/1MB,1)) MB در $($s.Count) فایل\\\" } }"), 30)


def _q_power():
    return _limit(_ps(
        "powercfg /getactivescheme; "
        "Get-CimInstance Win32_Battery | Select-Object EstimatedChargeRemaining,"
        "BatteryStatus | Format-List | Out-String"), 15)


def _q_defender():
    return _limit(_ps(
        "Get-MpComputerStatus -ErrorAction SilentlyContinue | "
        "Select-Object AntivirusEnabled,RealTimeProtectionEnabled,"
        "AntivirusSignatureLastUpdated,QuickScanEndTime | Format-List | Out-String"), 15)


def _q_uptime():
    return _limit(_ps(
        "$b=(Get-CimInstance Win32_OperatingSystem).LastBootUpTime; "
        "$u=(Get-Date)-$b; "
        "\\\"آخرین بوت: $b | روشن به مدت: $($u.Days) روز و $($u.Hours) ساعت\\\""), 10)


# ---------------------------------------------------------------------------
# پرس‌وجوهای افزوده — نقاط کوری که در بررسی‌های قبلی پوشش نداشتند
# ---------------------------------------------------------------------------

def _q_scheduled_tasks():
    """
    وظایف زمان‌بندی‌شده. بدافزار و برنامه‌های مزاحم اغلب اینجا پنهان
    می‌شوند چون کاربر معمولاً فقط استارتاپ را نگاه می‌کند.
    وظایف مایکروسافت فیلتر می‌شوند تا فهرست قابل خواندن بماند.
    """
    return _limit(_ps(
        "Get-ScheduledTask -ErrorAction SilentlyContinue | "
        "Where-Object {$_.State -ne 'Disabled' -and "
        "$_.TaskPath -notlike '\\\\Microsoft\\\\*'} | "
        "Select-Object TaskName,TaskPath,State | "
        "Format-Table -AutoSize -Wrap | Out-String"), 35)


def _q_smart():
    """
    مقادیر خام S.M.A.R.T — پیش‌بینی مرگ دیسک.
    ReallocatedSectorCount و PendingSector مهم‌ترین‌اند: هر مقدار
    غیرصفر یعنی دیسک در حال از دست دادن سکتور است.
    """
    return _limit(_ps(
        "Get-PhysicalDisk | ForEach-Object { "
        "$d=$_; "
        "\\\"=== $($d.FriendlyName) ($($d.MediaType)) ===\\\"; "
        "\\\"سلامت: $($d.HealthStatus) | وضعیت: $($d.OperationalStatus)\\\"; "
        "try{ $r=$d | Get-StorageReliabilityCounter -ErrorAction Stop; "
        "\\\"دما: $($r.Temperature)C | ساعت کارکرد: $($r.PowerOnHours) | \\\"+"
        "\\\"خطای خواندن: $($r.ReadErrorsTotal) | خطای نوشتن: $($r.WriteErrorsTotal) | \\\"+"
        "\\\"عمر باقیمانده: $($r.Wear)%\\\" }catch{ '(شمارنده‌های قابلیت اطمینان در دسترس نیست)' } }"),
        30)


def _q_pending_reboot():
    """
    ری‌استارت معلق. خیلی از «تعمیر کار نکرد»ها فقط همین است —
    تا ری‌استارت نشود تغییرات اعمال نمی‌شوند.
    """
    return _limit(_ps(
        "$r=@(); "
        "if(Test-Path 'HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\"
        "Component Based Servicing\\\\RebootPending'){$r+='به‌روزرسانی اجزای ویندوز (CBS)'} "
        "if(Test-Path 'HKLM:\\\\SOFTWARE\\\\Microsoft\\\\Windows\\\\CurrentVersion\\\\"
        "WindowsUpdate\\\\Auto Update\\\\RebootRequired'){$r+='Windows Update'} "
        "if(Get-ItemProperty -Path 'HKLM:\\\\SYSTEM\\\\CurrentControlSet\\\\Control\\\\"
        "Session Manager' -Name PendingFileRenameOperations "
        "-ErrorAction SilentlyContinue){$r+='تغییر نام فایل‌های قفل‌شده'} "
        "if($r.Count){\\\"ری‌استارت معلق است. دلیل:\\\"; $r | ForEach-Object {\\\" - $_\\\"}} "
        "else{'ری‌استارت معلقی وجود ندارد.'}"), 15)


def _q_disk_io():
    """
    تأخیر و صف دیسک. کندی دیسک را از کندی CPU جدا می‌کند —
    تأخیر بالای ۲۵ میلی‌ثانیه یعنی گلوگاه واقعی دیسک است.
    """
    return _limit(_ps(
        "try{ $c=Get-Counter -Counter "
        "'\\\\PhysicalDisk(_Total)\\\\Avg. Disk sec/Read',"
        "'\\\\PhysicalDisk(_Total)\\\\Avg. Disk sec/Write',"
        "'\\\\PhysicalDisk(_Total)\\\\Current Disk Queue Length',"
        "'\\\\PhysicalDisk(_Total)\\\\% Disk Time' "
        "-SampleInterval 1 -MaxSamples 2 -ErrorAction Stop; "
        "$c.CounterSamples | Group-Object Path | ForEach-Object { "
        "$avg=($_.Group | Measure-Object CookedValue -Average).Average; "
        "$n=$_.Name -replace '.*\\\\\\\\',''; "
        "if($n -like '*sec/*'){\\\"$n : $([math]::Round($avg*1000,2)) ms\\\"} "
        "else{\\\"$n : $([math]::Round($avg,2))\\\"} } "
        "}catch{ '(شمارنده‌های کارایی در دسترس نیست)' }"), 20)


def _q_pagefile():
    """
    حافظهٔ مجازی. اندازهٔ نامناسب یا مصرف بالا نشانهٔ فشار حافظه است.
    """
    return _limit(_ps(
        "Get-CimInstance Win32_PageFileUsage | "
        "Select-Object Name,@{N='اندازه(MB)';E={$_.AllocatedBaseSize}},"
        "@{N='مصرف(MB)';E={$_.CurrentUsage}},"
        "@{N='بیشینه(MB)';E={$_.PeakUsage}} | Format-List | Out-String; "
        "$cs=Get-CimInstance Win32_ComputerSystem; "
        "\\\"مدیریت خودکار: $($cs.AutomaticManagedPagefile)\\\"; "
        "$os=Get-CimInstance Win32_OperatingSystem; "
        "\\\"حافظه مجازی کل: $([math]::Round($os.TotalVirtualMemorySize/1MB,1)) GB | \\\"+"
        "\\\"آزاد: $([math]::Round($os.FreeVirtualMemory/1MB,1)) GB\\\""), 20)


def _q_reliability():
    """
    شاخص پایداری ویندوز (۱ تا ۱۰) و روند آن.
    افت ناگهانی نمره یعنی چیزی اخیراً خراب شده.
    """
    return _limit(_ps(
        "try{ Get-CimInstance Win32_ReliabilityStabilityMetrics "
        "-ErrorAction Stop | Sort-Object TimeGenerated -Descending | "
        "Select-Object -First 10 "
        "@{N='تاریخ';E={$_.TimeGenerated}},"
        "@{N='نمره';E={[math]::Round($_.SystemStabilityIndex,2)}} | "
        "Format-Table -AutoSize | Out-String "
        "}catch{ '(شاخص پایداری در دسترس نیست — معمولاً چند روز پس از نصب ویندوز فعال می‌شود)' }"),
        20)


def _q_thermal():
    """
    دمای CPU و کاهش سرعت حرارتی. throttling یعنی سیستم عمداً کند
    شده تا نسوزد — علت کندی که با هیچ تعمیر نرم‌افزاری حل نمی‌شود.
    """
    return _limit(_ps(
        "$found=$false; "
        "try{ $t=Get-CimInstance -Namespace root/WMI "
        "-ClassName MSAcpi_ThermalZoneTemperature -ErrorAction Stop; "
        "$t | ForEach-Object { $found=$true; "
        "\\\"دمای ناحیه: $([math]::Round(($_.CurrentTemperature/10)-273.15,1)) درجه\\\" } "
        "}catch{} "
        "try{ $p=Get-CimInstance Win32_Processor; "
        "\\\"سرعت فعلی: $($p.CurrentClockSpeed) MHz از حداکثر $($p.MaxClockSpeed) MHz\\\"; "
        "if($p.CurrentClockSpeed -lt ($p.MaxClockSpeed*0.7)){"
        "'هشدار: پردازنده با کمتر از ۷۰٪ سرعت اسمی کار می‌کند — احتمال کاهش سرعت حرارتی یا تنظیم انرژی'} "
        "}catch{} "
        "if(-not $found){'(حسگر دمای ACPI روی این سیستم گزارش نمی‌دهد — از ابزار سازنده استفاده کنید)'}"),
        20)


def _q_firewall_rules():
    """
    قوانین فایروال فعال که ترافیک را مسدود می‌کنند.
    قانون اشتباه، علت رایج «اینترنت دارم ولی این برنامه کار نمی‌کند» است.
    """
    return _limit(_ps(
        "$b=Get-NetFirewallRule -Enabled True -Action Block "
        "-ErrorAction SilentlyContinue; "
        "\\\"تعداد قوانین مسدودکننده فعال: $(@($b).Count)\\\"; "
        "$b | Select-Object -First 20 DisplayName,Direction,Profile | "
        "Format-Table -AutoSize -Wrap | Out-String; "
        "Get-NetFirewallProfile -ErrorAction SilentlyContinue | "
        "Select-Object Name,Enabled,DefaultInboundAction,DefaultOutboundAction | "
        "Format-Table -AutoSize | Out-String"), 35)


# ---------------------------------------------------------------------------
# فهرست بسته اطلاعات قابل درخواست
# ---------------------------------------------------------------------------
QUERIES = {
    "os_info":          ("مشخصات سیستم‌عامل و نسخه ویندوز", _q_os),
    "cpu":              ("مشخصات و بار پردازنده", _q_cpu),
    "memory":           ("وضعیت حافظه RAM و ماژول‌ها", _q_memory),
    "disks":            ("فضای درایوها", _q_disks),
    "disk_health":      ("سلامت فیزیکی دیسک‌ها (SSD/HDD)", _q_disk_health),
    "uptime":           ("مدت روشن بودن سیستم", _q_uptime),
    "startup_apps":     ("برنامه‌های اجرا هنگام راه‌اندازی", _q_startup),
    "top_cpu":          ("۱۲ فرآیند پرمصرف پردازنده", _q_top_cpu),
    "top_memory":       ("۱۲ فرآیند پرمصرف حافظه", _q_top_memory),
    "stopped_services": ("سرویس‌های خودکار که اجرا نشده‌اند", _q_services_stopped),
    "network_config":   ("پیکربندی کامل شبکه", _q_network),
    "network_test":     ("تست اتصال اینترنت و DNS", _q_network_test),
    "events_system":    ("خطاهای بحرانی System در ۷ روز اخیر", _q_events_system),
    "events_app":       ("خطاهای بحرانی Application در ۷ روز اخیر", _q_events_app),
    "bsod_history":     ("سابقه کرش و خاموشی ناگهانی", _q_bsod),
    "problem_drivers":  ("دستگاه‌های دارای مشکل درایور", _q_drivers_problem),
    "installed_apps":   ("نرم‌افزارهای نصب‌شده", _q_installed),
    "windows_updates":  ("۱۵ به‌روزرسانی اخیر ویندوز", _q_updates),
    "temp_files":       ("حجم فایل‌های موقت", _q_temp_size),
    "power_plan":       ("طرح انرژی و وضعیت باتری", _q_power),
    "defender_status":  ("وضعیت آنتی‌ویروس Defender", _q_defender),
    # ── افزوده‌های گام ۳: نقاط کوری که قبلاً پوشش نداشتند ──
    "scheduled_tasks":  ("وظایف زمان‌بندی‌شده غیرمایکروسافت", _q_scheduled_tasks),
    "smart_attributes": ("مقادیر S.M.A.R.T و سلامت فیزیکی دیسک", _q_smart),
    "pending_reboot":   ("ری‌استارت معلق و دلیل آن", _q_pending_reboot),
    "disk_io_latency":  ("تأخیر و صف دیسک (تفکیک کندی دیسک از CPU)", _q_disk_io),
    "page_file":        ("حافظه مجازی و فایل صفحه", _q_pagefile),
    "reliability_index": ("شاخص پایداری ویندوز و روند آن", _q_reliability),
    "thermal_throttling": ("دمای پردازنده و کاهش سرعت حرارتی", _q_thermal),
    "firewall_rules":   ("قوانین مسدودکننده فایروال", _q_firewall_rules),
}


def list_queries():
    return [{"key": k, "desc": v[0]} for k, v in QUERIES.items()]


def run_query(key):
    """یک پرس‌وجو را اجرا می‌کند (با کش ۳۰ ثانیه‌ای)."""
    if key not in QUERIES:
        return {"success": False, "error": f"پرس‌وجوی «{key}» تعریف نشده است."}

    now = time.time()
    hit = _CACHE.get(key)
    if hit and now - hit[0] < _CACHE_TTL:
        return {"success": True, "key": key, "desc": QUERIES[key][0],
                "output": hit[1], "cached": True}

    desc, fn = QUERIES[key]
    try:
        out = fn()
    except Exception as e:
        out = f"[خطا: {e}]"
    _CACHE[key] = (now, out)
    return {"success": True, "key": key, "desc": desc, "output": out, "cached": False}


def run_queries(keys):
    """چند پرس‌وجو را اجرا و به متن آماده برای AI تبدیل می‌کند."""
    # سقف ۱۲ تا: اگر مدل بیش از این بخواهد بقیه بی‌صدا حذف نمی‌شوند و AI
    # به‌اشتباه «داده در دسترس نیست» نمی‌گوید (قبلاً سقف ۸ بود).
    valid = [k for k in (keys or []) if k in QUERIES][:12]
    results, blocks = [], []
    for k in valid:
        r = run_query(k)
        results.append(r)
        out = r["output"]
        if not out or out == "(خروجی خالی)":
            # به‌جای متن بی‌محتوا، به AI بگوییم چرا داده نیست تا پاسخش
            # دقیق باشد نه «متاسفانه در دسترس نیست».
            out = ("(دادهٔ این پرس‌وجو در این سیستم گزارش نشد — احتمالاً "
                   "محیط مجازی/بدون سخت‌افزارِ مربوطه، یا نیازمند دسترسی "
                   "ادمین)")
        blocks.append(f"### {r['desc']}  ({k})\n```\n{out}\n```")
    text = "\n\n".join(blocks) if blocks else ""
    # سقف کل متن تا context مدل پر نشود
    if len(text) > 15000:
        text = text[:15000] + "\n...[بقیهٔ داده بریده شد]"
    return {
        "success": True,
        "requested": valid,
        "unknown": [k for k in (keys or []) if k not in QUERIES],
        "results": results,
        "text": text,
    }


def detect_requests(reply_text):
    """
    درخواست‌های AI را از متن پاسخ استخراج می‌کند.

    قرارداد: مدل می‌نویسد
        [NEED_INFO: events_system, top_cpu]
    """
    if not reply_text:
        return []
    keys = []
    for m in re.finditer(r'\[NEED_INFO:\s*([^\]]+)\]', reply_text, re.I):
        for part in m.group(1).split(','):
            k = part.strip().strip('`"\'')
            if k in QUERIES and k not in keys:
                keys.append(k)
    return keys


def strip_requests(reply_text):
    """نشانگر [NEED_INFO: ...] را از متن نمایش‌داده‌شده حذف می‌کند."""
    return re.sub(r'\[NEED_INFO:[^\]]*\]', '', reply_text or '').strip()


if __name__ == "__main__":
    print(f"{len(QUERIES)} پرس‌وجو تعریف شده:\n")
    for q in list_queries():
        print(f"  {q['key']:20} {q['desc']}")
