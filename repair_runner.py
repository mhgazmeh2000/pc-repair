# -*- coding: utf-8 -*-
"""
repair_runner.py — موتور اجرای زنجیره‌ای دستورات تعمیراتی
====================================================================
این ماژول باگ «اجرای ناقص دستورات پیشنهادی AI» را رفع می‌کند.

مشکل نسخه قبلی:
    دستور 'cmd.exe /k sfc /scannow && cleanmgr.exe' به execute_command_elevated
    داده می‌شد که خودش دوباره آن را داخل 'cmd /k ...' می‌پیچید. نتیجه یک
    cmd تودرتو بود که با /k باز می‌ماند و && دوم هرگز اجرا نمی‌شد.

راه‌حل این ماژول:
    ۱. هر مرحله یک دستور مستقل است (نه یک رشته && طولانی)
    ۲. تولید یک اسکریپت .bat موقت که مراحل را پشت‌سرهم و با گزارش اجرا می‌کند
    ۳. یک‌بار UAC برای کل زنجیره (نه هر مرحله جدا)
    ۴. نوشتن وضعیت هر مرحله در یک فایل JSON تا UI بتواند پیشرفت را نشان دهد
"""

import os
import re
import json
import time
import uuid
import subprocess
import tempfile
import threading

# ---------------------------------------------------------------------------
# تعریف مراحل تعمیر — هر مرحله یک واحد اتمی و مستقل
# ---------------------------------------------------------------------------
# نکته: هیچ‌کدام از این‌ها 'cmd.exe /k' ندارند. فقط خود دستور خام.
REPAIR_STEPS = {
    "sfc": {
        "title_fa": "اسکن و بازسازی فایل‌های سیستمی (SFC)",
        "cmd": "sfc /scannow",
        "admin": True,
        "eta_min": 15,
        "critical": False,   # اگر شکست خورد، ادامه بده
    },
    "dism_check": {
        "title_fa": "بررسی سلامت ایمیج ویندوز (DISM CheckHealth)",
        "cmd": "DISM /Online /Cleanup-Image /CheckHealth",
        "admin": True,
        "eta_min": 2,
        "critical": False,
    },
    "dism_restore": {
        "title_fa": "تعمیر مخزن ایمیج ویندوز (DISM RestoreHealth)",
        "cmd": "DISM /Online /Cleanup-Image /RestoreHealth",
        "admin": True,
        "eta_min": 20,
        "critical": False,
    },
    "flushdns": {
        "title_fa": "پاک‌سازی کش DNS",
        "cmd": "ipconfig /flushdns",
        "admin": True,
        "eta_min": 1,
        "critical": False,
    },
    "winsock": {
        "title_fa": "بازنشانی Winsock",
        "cmd": "netsh winsock reset",
        "admin": True,
        "eta_min": 1,
        "critical": False,
        "needs_reboot": True,
    },
    "renew_ip": {
        "title_fa": "تمدید آدرس IP",
        "cmd": "ipconfig /release && ipconfig /renew",
        "admin": True,
        "eta_min": 1,
        "critical": False,
    },
    "temp_clean": {
        "title_fa": "پاک‌سازی فایل‌های موقت",
        # فقط محتوای Temp پاک می‌شود، نه خودِ پوشه.
        # نسخه قبلی با rd /s /q خودِ %TEMP% را حذف می‌کرد؛ اگر ساختن
        # دوباره‌اش شکست می‌خورد، برنامه‌های در حال اجرا به مشکل
        # می‌خوردند. حذف زیرپوشه‌ها با forfiles امن‌تر است.
        "cmd": 'del /q /f /s "%TEMP%\\*" 2>nul & '
               'for /d %i in ("%TEMP%\\*") do @rd /s /q "%i" 2>nul',
        "admin": False,
        "eta_min": 2,
        "critical": False,
    },
    "cleanmgr": {
        "title_fa": "پاک‌سازی دیسک (Disk Cleanup)",
        # sagerun نیاز به sageset قبلی دارد؛ /verylowdisk حالت خودکار بی‌نیاز از UI
        "cmd": "cleanmgr /verylowdisk",
        "admin": False,
        "eta_min": 5,
        "critical": False,
        "interactive": True,   # ممکن است پنجره باز کند
    },
    "chkdsk": {
        "title_fa": "بررسی سلامت دیسک (CHKDSK - فقط اسکن)",
        "cmd": "chkdsk C: /scan",
        "admin": True,
        "eta_min": 10,
        "critical": False,
    },
}

# پلن پیش‌فرضی که دکمه «اجرای خودکار دستورات AI» استفاده می‌کند
DEFAULT_PLAN = ["sfc", "dism_restore", "flushdns", "temp_clean"]

# وضعیت اجراهای در جریان: job_id -> dict
_JOBS = {}
_JOBS_LOCK = threading.Lock()

# اگر زنجیره‌ای «running» باشد ولی مدت‌ها لاگ‌اش به‌روز نشده، یعنی پنجرهٔ
# مدیریتی (UAC) وسط اجرا بسته شده و فرآیند پاورشل مرده — بدون این بررسی،
# وضعیت برای همیشه «running» می‌ماند. این آستانه (ثانیه) همان تشخیص مرگ است.
# از متغیر محیطی PC_TOOLBOX_STALE_SECONDS هم می‌شود تنظیمش کرد.
STALE_RUNNING_SECONDS = int(
    os.environ.get("PC_TOOLBOX_STALE_SECONDS", "600") or 600)


def _log_stale(job_id, log_path=None, max_age=STALE_RUNNING_SECONDS):
    """آیا زنجیره مدت‌هاست به‌روز نشده؟ (نشانهٔ مرگ فرآیند)

    اول mtime فایل لاگ را می‌سنجد؛ اگر لاگ نبود (حذف شده)، mtime فایل
    وضعیت را می‌سنجد. اگر هیچ‌کدام نبود، False برمی‌گرداند تا زنجیره‌ای که
    هنوز شروع نشده (لاگ ساخته‌شده ولی PS1 هنوز Set-State نکرده) مرده
    قلمداد نشود.
    """
    if not log_path:
        log_path = os.path.join(_state_dir(), f"{job_id}.log")
    state_path = os.path.join(_state_dir(), f"{job_id}.json")
    try:
        if os.path.exists(log_path):
            mtime = os.path.getmtime(log_path)
        elif os.path.exists(state_path):
            mtime = os.path.getmtime(state_path)
        else:
            return False
        return (time.time() - mtime) > max_age
    except OSError:
        return False


def _mark_interrupted(job_id, current=None, total=None):
    """وضعیت زنجیره را interrupted می‌کند (هم فایل وضعیت هم لاگ)."""
    state_file = os.path.join(_state_dir(), f"{job_id}.json")
    data = {"job": job_id, "status": "interrupted"}
    try:
        if os.path.exists(state_file):
            # utf-8-sig: فایل‌های وضعیت را PowerShell با Set-Content می‌نویسد
            # که در 5.1 یک BOM در ابتدا اضافه می‌کند — json.load روی آن خطا می‌دهد
            with open(state_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                data.update(raw)
    except Exception:
        pass
    if current is not None:
        data["current"] = current
    if total is not None:
        data["total"] = total
    data["status"] = "interrupted"
    data["interrupted_at"] = time.time()
    try:
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except Exception:
        pass
    # فقط اگر قبلاً علامت [INTERRUPTED] ننوشته‌ایم append کن — اگر نوشتن
    # state شکست بخورد و poll دوباره بیاید، خط تکراری در لاگ ننشیند.
    log_path = os.path.join(_state_dir(), f"{job_id}.log")
    try:
        if os.path.exists(log_path):
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                if "[INTERRUPTED]" in f.read():
                    return
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("\n[INTERRUPTED] اجرا ناتمام ماند — پنجرهٔ مدیریتی بسته شد "
                    "یا فرآیند متوقف شد.\n")
    except Exception:
        pass


def sweep_stale_jobs(max_age=STALE_RUNNING_SECONDS):
    """زنجیره‌های مرده را پیدا و interrupted می‌کند.

    وقتی پنجرهٔ مدیریتی وسط اجرا بسته شود، فرآیند پاورشل می‌میرد و هیچ‌وقت
    status نهایی (done/cancelled) نمی‌نویسد — فایل وضعیت برای همیشه «running»
    می‌ماند. این تابع با مقایسهٔ زمان آخرین نوشتن لاگ با آستانهٔ STALE، چنین
    زنجیره‌هایی را تشخیص و وضعیت‌شان را interrupted می‌کند.

    بازگشت: لیست job_idهایی که پاکسازی شدند.
    """
    cleaned = []
    d = _state_dir()
    try:
        names = os.listdir(d)
    except OSError:
        return cleaned
    for fn in names:
        if not fn.endswith(".json"):
            continue
        job_id = fn[:-5]
        try:
            with open(os.path.join(d, fn), "r", encoding="utf-8-sig",
                      errors="ignore") as f:
                st = json.load(f)
        except Exception:
            continue
        if not isinstance(st, dict) or st.get("status") != "running":
            continue
        if _log_stale(job_id, os.path.join(d, f"{job_id}.log"), max_age):
            _mark_interrupted(job_id, st.get("current"), st.get("total"))
            cleaned.append(job_id)
    return cleaned


def _reconstruct_job(job_id):
    """وقتی job در حافظه نیست (مثلاً بعد از ریاستارت سرور)، از روی دیسک می‌سازد
    تا لاگ و وضعیت زنجیره‌های قبلی همچنان قابل نمایش باشد."""
    d = _state_dir()
    log_path = os.path.join(d, f"{job_id}.log")
    if not os.path.exists(log_path):
        return None
    info = {"id": job_id, "log": log_path, "total": 0, "steps": [],
            "started_at": None}
    try:
        with open(os.path.join(d, f"{job_id}.json"), "r", encoding="utf-8-sig",
                  errors="ignore") as f:
            st = json.load(f)
        if isinstance(st, dict):
            info["total"] = st.get("total", 0)
    except Exception:
        pass
    return info


def _state_dir():
    d = os.path.join(tempfile.gettempdir(), "pc_toolbox_jobs")
    os.makedirs(d, exist_ok=True)
    return d


def build_batch_script(step_keys, job_id):
    """
    یک اسکریپت .bat می‌سازد که مراحل را پشت‌سرهم اجرا می‌کند.

    چرا .bat به‌جای && زنجیره‌ای؟
      • && در cmd فقط وقتی ادامه می‌دهد که ERRORLEVEL صفر باشد. SFC حتی در
        حالت موفق گاهی کد غیرصفر برمی‌گرداند → زنجیره نصفه می‌ماند.
        اینجا هر مرحله مستقل است و ERRORLEVEL فقط ثبت می‌شود.
      • خروجی هر مرحله در فایل لاگ ذخیره می‌شود.
      • وضعیت در فایل JSON نوشته می‌شود تا UI پیشرفت را نشان دهد.
    """
    log_file    = os.path.join(_state_dir(), f"{job_id}.log")
    cancel_file = os.path.join(_state_dir(), f"{job_id}.cancel")
    state_file  = os.path.join(_state_dir(), f"{job_id}.json")

    def ps_str(t):
        """رشته را برای درج امن در single-quote پاورشل آماده می‌کند."""
        return str(t).replace("'", "''")

    total = len(step_keys)

    L = [
        "# PC Repair Toolbox - Automated Repair Sequence",
        "# تولید خودکار — دست نزنید",
        "",
        # UTF-8 کامل: هم ورودی هم خروجی. برخلاف .bat که cmd آن را با
        # کدپیج OEM می‌خواند، پاورشل فایل را با BOM به‌درستی UTF-8 می‌خواند
        # و متن فارسی سالم می‌ماند.
        "$OutputEncoding = [Console]::OutputEncoding = " +
        "[Console]::InputEncoding = [Text.UTF8Encoding]::new($false)",
        "try { chcp 65001 > $null } catch {}",
        "$ErrorActionPreference = 'Continue'",
        "$ProgressPreference = 'SilentlyContinue'",
        "",
        f"$LogFile    = '{ps_str(log_file)}'",
        f"$CancelFile = '{ps_str(cancel_file)}'",
        f"$StateFile  = '{ps_str(state_file)}'",
        f"$Total      = {total}",
        "",
        "$host.UI.RawUI.WindowTitle = 'PC Repair Toolbox — اجرای دستورات تعمیراتی'",
        "",
        # ── لاگ‌نویسی مقاوم به قفل ──
        # مشکل قدیمی: Add-Content برای *هر خط* فایل را باز و بسته می‌کرد.
        # در حین DISM (صدها خط در ثانیه) هر باز کردن می‌توانست با اسکن
        # آنتی‌ویروس یا خوانندهٔ live-tail برخورد کند → «being used by
        # another process». حالا فایل یک‌بار با StreamWriter باز می‌شود
        # (FileShare.ReadWrite + تلاش مجدد) و تا پایان زنجیره باز می‌ماند؛
        # دیگر هیچ باز/بسته‌ای در میان نیست که قفل بخورد.
        # خطای Add-Content هم «غیرترمینال» بود و try/catch آن را نمی‌گرفت؛
        # StreamWriter خطای ترمینال می‌دهد که catch واقعاً می‌گیرد.
        "function Open-Log {",
        "    $fs = [System.IO.File]::Open($LogFile, [System.IO.FileMode]::Append,",
        "          [System.IO.FileAccess]::Write, [System.IO.FileShare]::ReadWrite)",
        "    $script:LogWriter = [System.IO.StreamWriter]::new(",
        "        $fs, [System.Text.UTF8Encoding]::new($false))",
        "    $script:LogWriter.AutoFlush = $true",
        "}",
        "function Close-Log {",
        "    try { if ($null -ne $script:LogWriter) { $script:LogWriter.Dispose() } } catch {}",
        "}",
        "$script:LogWriter = $null",
        "function Write-Log([string]$Text) {",
        "    # SFC (و برخی ابزارهای ویندوز) وقتی خروجی‌شان pipe می‌شود",
        "    # UTF-16LE می‌فرستند؛ دیکد UTF-8 آن را به «حرف+NUL» تبدیل می‌کند",
        "    # (مثل V\\u0000e\\u0000r...). پاک‌سازی NUL اینجا به‌عنوان شبکهٔ ایمنی",
        "    # انجام می‌شود تا هر متنی که به لاگ می‌رسد خوانا باشد.",
        "    $Text = $Text.Replace([string][char]0, '')",
        "    for ($i = 0; $i -lt 6; $i++) {",
        "        try {",
        "            if ($null -eq $script:LogWriter) { Open-Log }",
        "            $script:LogWriter.WriteLine($Text)",
        "            return",
        "        } catch {",
        "            Start-Sleep -Milliseconds 200",
        "            try { $script:LogWriter.Dispose() } catch {}",
        "            $script:LogWriter = $null",
        "        }",
        "    }",
        "}",
        "function Set-State([hashtable]$S) {",
        "    # PID همین PowerShell ثبت می‌شود تا لغو فقط درخت همین job را بکشد.",
        "    $S['pid'] = $PID",
        "    $json = $S | ConvertTo-Json -Compress",
        "    for ($i = 0; $i -lt 6; $i++) {",
        "        try {",
        "            Set-Content -LiteralPath $StateFile -Value $json " +
        "-Encoding UTF8 -ErrorAction Stop",
        "            return",
        "        } catch { Start-Sleep -Milliseconds 200 }",
        "    }",
        "}",
        "function Line { Write-Host ('─' * 62) -ForegroundColor DarkGray }",
        "",
        "Write-Host ''",
        "Write-Host '  PC Repair Toolbox Pro' -ForegroundColor Cyan",
        f"Write-Host '  {total} دستور به ترتیب اجرا می‌شود' -ForegroundColor Gray",
        "Line",
        "Write-Host ''",
        "",
    ]

    for idx, key in enumerate(step_keys, 1):
        step = REPAIR_STEPS.get(key)
        if not step:
            continue
        title = ps_str(step["title_fa"])
        cmd   = step["cmd"]

        L += [
            f"# ═══ مرحله {idx} ═══",
            "if (Test-Path -LiteralPath $CancelFile) { goto_cancelled }",
            f"Write-Host ''",
            f"Write-Host '[{idx}/{total}] ' -ForegroundColor Yellow -NoNewline",
            f"Write-Host '{title}' -ForegroundColor White",
            f"Write-Host '      {ps_str(cmd)}' -ForegroundColor DarkCyan",
            "Line",
            "",
            f"Set-State @{{ job='{job_id}'; current={idx}; total={total}; " +
            f"step='{key}'; status='running' }}",
            f"Write-Log '[{idx}/{total}] {title}'",
            f"Write-Log '__STEP_BEGIN {idx} '",
            "",
            "$sw = [Diagnostics.Stopwatch]::StartNew()",
            "$global:LASTEXITCODE = 0",
            "$stepFailed = $false",
            "",
            # ── قلب کار ──
            # چرا Tee-Object نه؟
            #   در PowerShell 5.1 پارامتر -Append فقط با -FilePath ترکیب
            #   می‌شود، نه -LiteralPath. نتیجه خطای AmbiguousParameterSet
            #   بود و دستور اصلاً اجرا نمی‌شد — ولی چون $LASTEXITCODE
            #   دست‌نخورده صفر می‌ماند، برنامه «موفق» گزارش می‌داد.
            #
            # روش فعلی: خروجی خط‌به‌خط از پایپ‌لاین خوانده می‌شود و
            # همزمان روی صفحه چاپ و در فایل نوشته می‌گردد. هم جریانی
            # است، هم به نسخه پاورشل وابسته نیست.
            "try {",
            f"    & cmd.exe /c '{ps_str(cmd)}' 2>&1 | ForEach-Object {{",
            "        $line = $_.ToString()",
            "        # SFC وقتی pipe می‌شود UTF-16LE می‌فرستد؛ دیکد UTF-8 آن را",
            "        # به حرف+NUL تبدیل می‌کند (V\\u0000e\\u0000r...). NULها را",
            "        # حذف می‌کنیم تا هم روی صفحه هم در لاگ خوانا باشد.",
            "        $line = $line.Replace([string][char]0, '')",
            "        Write-Host $line",
            "        Write-Log $line",
            "    }",
            "    $rc = $LASTEXITCODE",
            "} catch {",
            "    $stepFailed = $true",
            "    $rc = -1",
            "    $msg = $_.Exception.Message",
            "    Write-Host ('   خطا: ' + $msg) -ForegroundColor Red",
            "    Write-Log ('ERROR: ' + $msg)",
            "}",
            "if ($null -eq $rc) { $rc = 0 }",
            "",
            "$sw.Stop()",
            "$sec = [math]::Round($sw.Elapsed.TotalSeconds, 1)",
            "",
            "if ($stepFailed) {",
            "    Write-Host ('   ✗ اجرا نشد — ' + $sec + ' ثانیه') -ForegroundColor Red",
            "} elseif ($rc -eq 0) {",
            "    Write-Host ('   ✓ موفق — ' + $sec + ' ثانیه') -ForegroundColor Green",
            "} else {",
            "    Write-Host ('   ✗ کد خروجی ' + $rc + ' — ' + $sec + ' ثانیه') " +
            "-ForegroundColor Yellow",
            "}",
            f"Write-Log ('__STEP_END {idx} rc=' + $rc + ' sec=' + $sec)",
            "Write-Log ('   result rc=' + $rc)",
            "Write-Host ''",
            "",
        ]

    L += [
        "if (Test-Path -LiteralPath $CancelFile) { goto_cancelled }",
        "",
        f"Set-State @{{ job='{job_id}'; current={total}; total={total}; status='done' }}",
        "Line",
        "Write-Host '  ✅ تمام مراحل به پایان رسید' -ForegroundColor Green",
        "Write-Host ('  گزارش کامل: ' + $LogFile) -ForegroundColor DarkGray",
        "Line",
        "Write-Host ''",
        "Close-Log",
        "Write-Host 'برای بستن این پنجره کلیدی را فشار دهید...' -ForegroundColor DarkGray",
        "$null = $host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')",
        "exit 0",
    ]

    # پاورشل goto ندارد؛ لغو را با تابعی که پنجره را می‌بندد شبیه‌سازی می‌کنیم
    cancel_block = [
        "function goto_cancelled {",
        f"    Set-State @{{ job='{job_id}'; status='cancelled'; total={total} }}",
        "    Remove-Item -LiteralPath $CancelFile -Force -ErrorAction SilentlyContinue",
        "    Write-Host ''",
        "    Line",
        "    Write-Host '  ⛔ اجرا توسط شما لغو شد' -ForegroundColor Red",
        "    Write-Host '  مراحل باقی‌مانده انجام نشدند' -ForegroundColor DarkGray",
        "    Line",
        "    Write-Log '[CANCELLED] chain stopped by user'",
        "    Write-Host ''",
        "    Close-Log",
        "    Write-Host 'برای بستن کلیدی را فشار دهید...' -ForegroundColor DarkGray",
        "    $null = $host.UI.RawUI.ReadKey('NoEcho,IncludeKeyDown')",
        "    exit 1",
        "}",
        "",
    ]
    # تعریف تابع باید پیش از اولین استفاده باشد
    L = L[:8] + cancel_block + L[8:]

    ps1_path = os.path.join(_state_dir(), f"{job_id}.ps1")
    # BOM لازم است: PowerShell 5.1 ویندوز بدون آن فایل را با کدپیج
    # سیستم می‌خواند و متن فارسی خراب می‌شود.
    with open(ps1_path, "w", encoding="utf-8-sig", newline="\r\n") as f:
        f.write("\n".join(L))

    # فایل خالی لاگ بساز تا live tail بلافاصله چیزی برای خواندن داشته باشد
    try:
        open(log_file, "w", encoding="utf-8").close()
    except Exception:
        pass

    return ps1_path, log_file


def run_custom_chain(commands, titles=None, elevate=True):
    """
    یک زنجیره دلخواه از دستورات را پشت‌سرهم اجرا می‌کند.

    برخلاف run_repair_plan که فقط مراحل از پیش تعریف‌شده را می‌پذیرد،
    این تابع برای دستوراتی است که AI در چت پیشنهاد داده.
    هر دستور باید قبلاً از command_guard عبور کرده باشد.
    """
    if not commands:
        return {"success": False, "error": "هیچ دستوری برای اجرا وجود ندارد."}

    titles = titles or []
    job_id = f"chain_{int(time.time())}_{uuid.uuid4().hex[:6]}"

    # مراحل موقتی بساز تا از همان موتور .bat استفاده کنیم
    temp_steps = {}
    keys = []
    for i, cmd in enumerate(commands):
        key = f"_c{i}"
        temp_steps[key] = {
            "title_fa": titles[i] if i < len(titles) else cmd[:60],
            "cmd": cmd,
            "admin": True,
            "eta_min": 5,
            "critical": False,
        }
        keys.append(key)

    # موقتاً به REPAIR_STEPS اضافه کن تا build_batch_script بتواند بخواند
    REPAIR_STEPS.update(temp_steps)
    try:
        bat_path, log_file = build_batch_script(keys, job_id)
        step_list = [{"key": k, "title_fa": temp_steps[k]["title_fa"],
                      "cmd": temp_steps[k]["cmd"]} for k in keys]
    finally:
        for k in keys:
            REPAIR_STEPS.pop(k, None)

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id, "steps": step_list, "total": len(keys),
            "script": bat_path,
            "bat": bat_path, "log": log_file, "started_at": time.time(),
        }

    if os.name != "nt":
        return {"success": True, "job_id": job_id, "simulated": True,
                "total": len(keys), "steps": step_list, "bat_path": bat_path,
                "note": "شبیه‌سازی (سیستم غیر ویندوزی)."}

    try:
        if elevate:
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Start-Process powershell -Verb RunAs -ArgumentList "
                 "'-NoProfile','-ExecutionPolicy','Bypass','-File',"
                 f"'{bat_path}'"], shell=False)
        else:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy",
                              "Bypass", "-File", bat_path], shell=False)
    except Exception as e:
        return {"success": False, "error": f"خطا در اجرای زنجیره: {e}"}

    return {"success": True, "job_id": job_id, "total": len(keys),
            "steps": step_list, "elevated": elevate}


def run_repair_plan(step_keys=None, elevate=True):
    """
    زنجیره تعمیر را اجرا می‌کند و job_id برمی‌گرداند.
    فقط یک بار UAC می‌پرسد.
    """
    if not step_keys:
        step_keys = list(DEFAULT_PLAN)

    # فیلتر مراحل ناشناخته
    step_keys = [k for k in step_keys if k in REPAIR_STEPS]
    if not step_keys:
        return {"success": False, "error": "هیچ مرحله معتبری انتخاب نشده است."}

    job_id = f"job_{int(time.time())}_{uuid.uuid4().hex[:6]}"
    bat_path, log_file = build_batch_script(step_keys, job_id)

    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "id": job_id,
            "steps": [{"key": k, "title_fa": REPAIR_STEPS[k]["title_fa"]} for k in step_keys],
            "total": len(step_keys),
            "script": bat_path,
            "bat": bat_path,
            "log": log_file,
            "started_at": time.time(),
        }

    needs_admin = elevate and any(REPAIR_STEPS[k]["admin"] for k in step_keys)

    if os.name != "nt":
        return {
            "success": True, "job_id": job_id, "simulated": True,
            "total": len(step_keys),
            "bat_path": bat_path,
            "steps": _JOBS[job_id]["steps"],
            "note": "شبیه‌سازی (سیستم غیر ویندوزی) — اسکریپت ساخته شد ولی اجرا نشد.",
        }

    try:
        if needs_admin:
            # یک بار UAC برای کل زنجیره. shell=False و آرگومان‌های جدا.
            subprocess.Popen(
                ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command",
                 "Start-Process powershell -Verb RunAs -ArgumentList "
                 "'-NoProfile','-ExecutionPolicy','Bypass','-File',"
                 f"'{bat_path}'"],
                shell=False,
            )
        else:
            subprocess.Popen(["powershell", "-NoProfile", "-ExecutionPolicy",
                              "Bypass", "-File", bat_path], shell=False)
    except Exception as e:
        return {"success": False, "error": f"خطا در اجرای اسکریپت: {e}"}

    return {
        "success": True,
        "job_id": job_id,
        "total": len(step_keys),
        "steps": _JOBS[job_id]["steps"],
        "elevated": needs_admin,
    }


def cancel_job(job_id):
    """
    یک زنجیره در حال اجرا را لغو می‌کند.

    روش کار دو مرحله‌ای:
      ۱. یک فایل «پرچم لغو» ساخته می‌شود. اسکریپت .bat پیش از هر مرحله
         وجود آن را چک می‌کند و اگر باشد، از حلقه خارج می‌شود.
         این کار مراحل *بعدی* را متوقف می‌کند.
      ۲. فرآیندی که همین حالا در حال اجراست (مثلاً sfc) هم kill می‌شود،
         وگرنه کاربر باید تا پایان یک مرحله ۱۵ دقیقه‌ای صبر کند.

    نکته ایمنی: فقط فرآیندهایی که خودمان اجرا کرده‌ایم متوقف می‌شوند.
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)

    if not job:
        return {"success": False, "error": "این زنجیره یافت نشد."}

    # ۱. پرچم لغو
    flag = os.path.join(_state_dir(), f"{job_id}.cancel")
    try:
        with open(flag, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception as e:
        return {"success": False, "error": f"ثبت درخواست لغو ناموفق بود: {e}"}

    with _JOBS_LOCK:
        job["cancelled"] = True

    killed = []
    if os.name == "nt":
        # فقط درخت فرزندِ PowerShell همین job را متوقف کن. نسخهٔ قبلی با
        # /IM همهٔ نمونه‌های sfc/DISM/chkdsk سیستم را می‌کشت؛ بنابراین ممکن
        # بود تعمیر دستی یا برنامهٔ دیگری قربانی لغو این job شود.
        pid = None
        state_file = os.path.join(_state_dir(), f"{job_id}.json")
        try:
            with open(state_file, "r", encoding="utf-8-sig") as f:
                pid = int((json.load(f) or {}).get("pid") or 0) or None
        except Exception:
            pass
        if pid:
            try:
                r = subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)],
                                   capture_output=True, text=True, timeout=10,
                                   shell=False)
                if r.returncode == 0:
                    killed.append(f"job process tree (PID {pid})")
            except Exception:
                pass

    # وضعیت را روی cancelled بگذار تا UI متوجه شود
    try:
        state_file = os.path.join(_state_dir(), f"{job_id}.json")
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump({"job": job_id, "status": "cancelled",
                       "current": 0, "total": job.get("total", 0)}, f)
    except Exception:
        pass

    return {"success": True, "job_id": job_id,
            "killed": killed,
            "message": "درخواست لغو ثبت شد."
                       + (f" فرآیندهای متوقف‌شده: {', '.join(killed)}" if killed else "")}


# الگوهای نویز که در خروجی SFC/DISM/CHKDSK تکرار می‌شوند و
# هیچ اطلاعاتی به کاربر یا AI نمی‌دهند.
_NOISE = [
    # نوار پیشرفت DISM:  [=====        42.0%              ]
    re.compile(r'^\s*\[=*\s*[\d.]+%\s*\]?\s*$'),
    re.compile(r'^\s*\[[=\s]*\]\s*$'),
    # SFC:  Verification 42% complete.
    re.compile(r'(Verification|Verifying)\s+\d+%\s+complete', re.I),
    # CHKDSK:  42 percent complete.
    re.compile(r'^\s*\d+\s+percent\s+complete', re.I),
    # خطوط فقط نقطه یا خط تیره
    re.compile(r'^[\s.\-_=]{3,}$'),
]


def _denoise(raw):
    """
    خروجی خام ابزارهای ویندوز را به لاگ خوانا تبدیل می‌کند.

    چرا لازم است؟ DISM نوار پیشرفت را به‌جای بازنویسی یک خط،
    صدها بار چاپ می‌کند. یک اجرای ۲۰ دقیقه‌ای می‌تواند ۵۰۰۰ خط
    تولید کند که ۹۵٪ آن تکرار درصد است — هم خواندنش سخت است،
    هم توکن AI را هدر می‌دهد.
    """
    out, prev, dup = [], None, 0
    for line in (raw or "").split("\n"):
        s = line.rstrip()
        # SFC وقتی pipe می‌شود UTF-16LE می‌فرستد؛ دیکد UTF-8 آن را به
        # «حرف+NUL» تبدیل می‌کند. NULها را حذف می‌کنیم تا هم الگوهای
        # نویز بتوانند خط را تشخیص دهند هم خروجی خوانا باشد.
        s = s.replace("\x00", "")
        if not s.strip():
            continue
        if any(p.search(s) or p.match(s) for p in _NOISE):
            continue
        # خطوط پشت‌سرهم یکسان را جمع کن
        if s == prev:
            dup += 1
            continue
        if dup:
            out.append(f"   ... ({dup} بار تکرار)")
            dup = 0
        prev = s
        out.append(s)
    if dup:
        out.append(f"   ... ({dup} بار تکرار)")
    return out


def get_job_live(job_id, offset=0, max_bytes=20000):
    """
    خروجی زنده را از یک نقطه مشخص به بعد برمی‌گرداند (live tail).

    رابط کاربری فقط بخش جدید را می‌گیرد، نه کل فایل — این باعث می‌شود
    نمایش لحظه‌ای روان باشد حتی وقتی لاگ چند مگابایت شده.
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        job = _reconstruct_job(job_id)   # زنجیرهٔ جلسات قبلی سرور
    if not job:
        return {"success": False, "error": "این زنجیره یافت نشد."}

    log_path = job.get("log", "")
    if not log_path or not os.path.exists(log_path):
        return {"success": True, "chunk": "", "offset": offset,
                "size": 0, "running": True}

    try:
        size = os.path.getsize(log_path)
        if offset > size:      # فایل ریست شده
            offset = 0
        with open(log_path, "rb") as f:
            f.seek(offset)
            raw = f.read(max_bytes)

        # فقط تا آخرین خط کامل را مصرف کن.
        # اگر وسط یک خط ببریم، آن خط در این chunk ناقص و در chunk بعدی
        # بی‌سر می‌شود و در نمایش به هم می‌چسبند.
        nl = raw.rfind(b"\n")
        if nl == -1:
            if len(raw) < max_bytes:
                # خط هنوز کامل نشده — دفعه بعد می‌خوانیمش
                raw = b""
        else:
            raw = raw[:nl + 1]

        new_offset = offset + len(raw)
        chunk = raw.decode("utf-8", "ignore")
    except Exception as e:
        return {"success": False, "error": str(e)}

    # پاک‌سازی نشانگرهای داخلی و نویز پیشرفت
    kept = []
    current_step = None
    for line in chunk.split("\n"):
        m = re.match(r'__STEP_BEGIN (\d+)', line)
        if m:
            current_step = int(m.group(1))
            continue
        if line.startswith("__STEP_END"):
            continue
        kept.append(line)
    visible = _denoise("\n".join(kept))

    state = get_job_status(job_id)
    return {
        "success": True,
        # \n انتهایی لازم است تا chunk بعدی به این نچسبد
        "chunk": ("\n".join(visible) + "\n") if visible else "",
        "offset": new_offset,
        "size": size,
        "step": current_step,
        "status": state.get("status", "running"),
        "current": state.get("current", 0),
        "total": state.get("total", job.get("total", 0)),
    }


def get_job_output(job_id, max_chars=6000):
    """
    خروجی کامل یک زنجیره را برای ارسال به AI برمی‌گرداند.

    لاگ خام ممکن است هزاران خط باشد (مثلاً DISM درصد پیشرفت را
    خط‌به‌خط می‌نویسد). برای صرفه‌جویی در توکن:
      • خطوط تکراری پیشرفت حذف می‌شوند
      • اگر باز هم طولانی بود، ابتدا و انتهای هر بخش نگه داشته می‌شود
    """
    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        job = _reconstruct_job(job_id)   # زنجیرهٔ جلسات قبلی سرور
    if not job:
        return {"success": False, "error": "این زنجیره یافت نشد."}

    log_path = job.get("log", "")
    raw = ""
    if log_path and os.path.exists(log_path):
        try:
            with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
                raw = f.read()
        except Exception as e:
            return {"success": False, "error": f"خواندن لاگ ناموفق بود: {e}"}

    cleaned = _denoise(raw)

    text = "\n".join(cleaned)
    truncated = False
    if len(text) > max_chars:
        head = text[: max_chars // 2]
        tail = text[-(max_chars // 2):]
        text = head + "\n\n...[بخش میانی حذف شد]...\n\n" + tail
        truncated = True

    # استخراج کد خروجی هر مرحله
    results = []
    for m in re.finditer(r'\[(\d+)/(\d+)\]\s*(.+?)\n(.*?)(?=\[\d+/\d+\]|\Z)',
                         "\n".join(cleaned) + "\n", re.S):
        body = m.group(4)
        rc = re.search(r'result rc=(\d+)', body)
        results.append({
            "step": int(m.group(1)),
            "total": int(m.group(2)),
            "title": m.group(3).strip(),
            "exit_code": int(rc.group(1)) if rc else None,
            "ok": (rc and rc.group(1) == "0") if rc else None,
        })

    state = get_job_status(job_id)
    return {
        "success": True,
        "job_id": job_id,
        "status": state.get("status", "unknown"),
        "steps": job.get("steps", []),
        "results": results,
        "output": text,
        "truncated": truncated,
        "line_count": len(cleaned),
    }


def get_job_status(job_id):
    """وضعیت لحظه‌ای یک زنجیره را برمی‌گرداند (برای نمایش پیشرفت در UI)."""
    state_file = os.path.join(_state_dir(), f"{job_id}.json")
    info = {"job_id": job_id, "status": "unknown", "current": 0, "total": 0}

    with _JOBS_LOCK:
        job = _JOBS.get(job_id)
    if not job:
        job = _reconstruct_job(job_id)   # زنجیرهٔ جلسات قبلی سرور
    if job:
        info["total"] = job["total"]
        info["steps"] = job["steps"]

    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8-sig", errors="ignore") as f:
                raw = json.load(f)
            info.update(raw)
        except Exception:
            pass

    # اگر وضعیت روی دیسک «running» است ولی لاگ مدت‌هاست به‌روز نشده،
    # یعنی پنجرهٔ مدیریتی وسط اجرا بسته شده و فرآیند مرده — interrupted کن.
    if info.get("status") == "running" and _log_stale(job_id):
        _mark_interrupted(job_id, info.get("current"), info.get("total"))
        info["status"] = "interrupted"

    # چند خط آخر لاگ
    if job and os.path.exists(job["log"]):
        try:
            with open(job["log"], "r", encoding="utf-8", errors="ignore") as f:
                info["tail"] = [ln.replace("\x00", "")
                                 for ln in f.readlines()[-25:]]
        except Exception:
            pass

    return info


def extract_plan_from_ai_reply(reply_text):
    """
    از متن پاسخ AI، مراحل تعمیر را استخراج می‌کند.
    این باعث می‌شود دکمه «اجرای خودکار» واقعاً همان چیزی را اجرا کند که
    AI پیشنهاد داده — نه یک دستور هاردکد.
    """
    if not reply_text:
        return list(DEFAULT_PLAN)

    low = reply_text.lower()
    plan = []

    # ترتیب مهم است: SFC قبل از DISM، شبکه بعد از فایل سیستم
    if "sfc" in low or "scannow" in low:
        plan.append("sfc")
    if "restorehealth" in low or ("dism" in low and "restore" in low):
        plan.append("dism_restore")
    elif "dism" in low:
        plan.append("dism_check")
    if "chkdsk" in low:
        plan.append("chkdsk")
    if "flushdns" in low or "کش dns" in low or "کش دی‌ان‌اس" in low:
        plan.append("flushdns")
    if "winsock" in low:
        plan.append("winsock")
    if "release" in low and "renew" in low:
        plan.append("renew_ip")
    if "temp" in low or "فایل‌های موقت" in low or "کش" in low:
        plan.append("temp_clean")
    if "cleanmgr" in low or "disk cleanup" in low or "پاک‌سازی دیسک" in low:
        plan.append("cleanmgr")

    # حذف تکراری‌ها با حفظ ترتیب
    seen, ordered = set(), []
    for k in plan:
        if k not in seen:
            seen.add(k)
            ordered.append(k)

    return ordered or list(DEFAULT_PLAN)


if __name__ == "__main__":
    # تست محلی: ساخت اسکریپت و نمایش محتوای آن
    jid = "job_demo"
    bat, log = build_batch_script(DEFAULT_PLAN, jid)
    print(f"اسکریپت ساخته شد: {bat}\n")
    print(open(bat, encoding="utf-8").read())
