# -*- coding: utf-8 -*-
"""
gpu_inspector.py — تشخیص و عیب‌یابی کارت گرافیک
====================================================================
پشتیبانی از:
  • گرافیک مجتمع (Integrated): Intel UHD/Iris/Arc، AMD Radeon Graphics
  • گرافیک مجزا (Discrete/External): NVIDIA GeForce/RTX، AMD Radeon، Intel Arc
  • سیستم‌های Hybrid (Optimus / Switchable Graphics)

روش کار: از ابزارهای بومی ویندوز استفاده می‌شود تا نیازی به نصب
کتابخانه اضافه نباشد:
  - PowerShell CIM/WMI  → مشخصات کارت، درایور، وضعیت دستگاه
  - nvidia-smi          → دما، مصرف، حافظه، فرآیندها (فقط NVIDIA)
  - dxdiag              → اطلاعات DirectX
  - Event Viewer        → خطاهای TDR و کرش درایور
  - رجیستری             → تنظیمات TDR
"""

import os
import re
import json
import subprocess
import time

# کدهای خطای Device Manager که برای گرافیک معنادارند
DEVICE_ERROR_CODES = {
    1:  "دستگاه به‌درستی پیکربندی نشده است.",
    3:  "درایور خراب است یا حافظه/منابع سیستم کافی نیست.",
    10: "دستگاه نمی‌تواند راه‌اندازی شود (درایور یا سخت‌افزار معیوب).",
    12: "منابع کافی برای این دستگاه یافت نشد (تداخل منابع).",
    14: "دستگاه تا راه‌اندازی مجدد سیستم کار نخواهد کرد.",
    18: "درایورها باید مجدداً نصب شوند.",
    19: "اطلاعات رجیستری خراب است.",
    22: "دستگاه غیرفعال (Disabled) شده است.",
    28: "درایور این دستگاه نصب نشده است.",
    31: "ویندوز نمی‌تواند درایور مورد نیاز را بارگذاری کند.",
    43: "ویندوز دستگاه را متوقف کرد چون خطا گزارش داده (خطای رایج GPU).",
    45: "دستگاه در حال حاضر به سیستم متصل نیست.",
    48: "اجرای نرم‌افزار این دستگاه مسدود شده است.",
}

# نرم‌افزارهایی که به‌شدت به GPU وابسته‌اند
GPU_DEPENDENT_APPS = {
    "chrome.exe":        ("Google Chrome", "مرورگر — شتاب‌دهی سخت‌افزاری"),
    "msedge.exe":        ("Microsoft Edge", "مرورگر — شتاب‌دهی سخت‌افزاری"),
    "firefox.exe":       ("Firefox", "مرورگر — شتاب‌دهی سخت‌افزاری"),
    "Photoshop.exe":     ("Adobe Photoshop", "ویرایش تصویر — OpenGL/OpenCL"),
    "AfterFX.exe":       ("After Effects", "موشن گرافیک — رندر GPU"),
    "Premiere Pro.exe":  ("Premiere Pro", "تدوین ویدیو — شتاب Mercury"),
    "Illustrator.exe":   ("Adobe Illustrator", "گرافیک برداری — GPU"),
    "blender.exe":       ("Blender", "مدل‌سازی سه‌بعدی — رندر CUDA/OptiX"),
    "Code.exe":          ("VS Code", "ویرایشگر کد — رندر GPU"),
    "obs64.exe":         ("OBS Studio", "ضبط/استریم — انکود سخت‌افزاری"),
    "vlc.exe":           ("VLC", "پخش ویدیو — دیکود سخت‌افزاری"),
    "Discord.exe":       ("Discord", "شتاب‌دهی سخت‌افزاری"),
    "Unity.exe":         ("Unity Editor", "موتور بازی‌سازی"),
    "UnrealEditor.exe":  ("Unreal Engine", "موتور بازی‌سازی"),
    "davinci.exe":       ("DaVinci Resolve", "تدوین حرفه‌ای — GPU محور"),
    "steam.exe":         ("Steam", "پلتفرم بازی"),
    "dwm.exe":           ("Desktop Window Manager", "رابط گرافیکی ویندوز"),
}


def _run(cmd, timeout=15):
    """اجرای امن یک دستور و بازگرداندن خروجی متنی."""
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, shell=True,
                           timeout=timeout, errors="ignore")
        return (r.stdout or "").strip()
    except Exception:
        return ""


def _run_ps(script, timeout=20):
    """اجرای اسکریپت PowerShell و پارس خروجی JSON."""
    if os.name != 'nt':
        return None
    cmd = ('powershell -NoProfile -NonInteractive -ExecutionPolicy Bypass '
           f'-Command "{script}"')
    out = _run(cmd, timeout)
    if not out:
        return None
    try:
        data = json.loads(out)
        return data if isinstance(data, list) else [data]
    except Exception:
        return None


# ---------------------------------------------------------------------------
# ۱. شناسایی کارت‌های گرافیک
# ---------------------------------------------------------------------------
def get_gpu_list():
    """فهرست تمام کارت‌های گرافیک با مشخصات درایور و وضعیت."""
    gpus = []
    if os.name != 'nt':
        return gpus

    ps = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility,DriverVersion,DriverDate,"
        "AdapterRAM,VideoProcessor,CurrentHorizontalResolution,"
        "CurrentVerticalResolution,CurrentRefreshRate,Status,"
        "ConfigManagerErrorCode,PNPDeviceID,VideoModeDescription | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    rows = _run_ps(ps)

    if not rows:
        # پشتیبان: wmic روی ویندوزهای قدیمی‌تر
        out = _run('wmic path Win32_VideoController get Name,DriverVersion,AdapterRAM /format:list')
        cur = {}
        for line in out.split('\n'):
            line = line.strip()
            if '=' in line:
                k, v = line.split('=', 1)
                cur[k.strip()] = v.strip()
            elif cur:
                rows = rows or []
                rows.append(cur)
                cur = {}
        if cur:
            rows = (rows or []) + [cur]

    for r in (rows or []):
        name = (r.get("Name") or "").strip()
        if not name:
            continue
        vendor_raw = (r.get("AdapterCompatibility") or name or "").lower()
        if "nvidia" in vendor_raw:
            vendor = "NVIDIA"
        elif "intel" in vendor_raw:
            vendor = "Intel"
        elif "amd" in vendor_raw or "ati " in vendor_raw or "radeon" in vendor_raw:
            vendor = "AMD"
        elif "microsoft" in vendor_raw:
            vendor = "Microsoft"
        else:
            vendor = r.get("AdapterCompatibility") or "نامشخص"

        low = name.lower()
        # تشخیص مجتمع در برابر مجزا
        integrated_hints = ("uhd graphics", "hd graphics", "iris", "vega 3", "vega 5",
                            "vega 6", "vega 7", "vega 8", "radeon graphics",
                            "microsoft basic", "amd radeon(tm) graphics")
        is_integrated = any(h in low for h in integrated_hints)
        if vendor == "NVIDIA":
            is_integrated = False

        ram = r.get("AdapterRAM")
        try:
            # WMI برای کارت‌های بالای ۴ گیگ عدد اشتباه می‌دهد (محدودیت uint32)
            vram_gb = round(int(ram) / (1024 ** 3), 2) if ram and int(ram) > 0 else None
        except Exception:
            vram_gb = None

        err_code = r.get("ConfigManagerErrorCode")
        try:
            err_code = int(err_code) if err_code is not None else 0
        except Exception:
            err_code = 0

        drv_date = r.get("DriverDate") or ""
        m = re.search(r'(\d{4})(\d{2})(\d{2})', str(drv_date))
        driver_date = f"{m.group(1)}-{m.group(2)}-{m.group(3)}" if m else (str(drv_date)[:10] or "نامشخص")
        driver_age_days = None
        if m:
            try:
                t = time.mktime((int(m.group(1)), int(m.group(2)), int(m.group(3)),
                                 0, 0, 0, 0, 0, -1))
                driver_age_days = int((time.time() - t) / 86400)
            except Exception:
                pass

        gpus.append({
            "name": name,
            "vendor": vendor,
            "type": "مجتمع (Integrated)" if is_integrated else "مجزا (Discrete)",
            "is_integrated": is_integrated,
            "driver_version": r.get("DriverVersion") or "نامشخص",
            "driver_date": driver_date,
            "driver_age_days": driver_age_days,
            "vram_gb": vram_gb,
            "resolution": (f'{r.get("CurrentHorizontalResolution")}x{r.get("CurrentVerticalResolution")}'
                           if r.get("CurrentHorizontalResolution") else "نامشخص"),
            "refresh_hz": r.get("CurrentRefreshRate"),
            "status": r.get("Status") or "نامشخص",
            "error_code": err_code,
            "error_text": DEVICE_ERROR_CODES.get(err_code) if err_code else None,
            "pnp_id": r.get("PNPDeviceID") or "",
        })
    return gpus


# ---------------------------------------------------------------------------
# ۲. اطلاعات زنده NVIDIA
# ---------------------------------------------------------------------------
def get_nvidia_live():
    """دما، مصرف برق، حافظه و فرآیندها از nvidia-smi."""
    if os.name != 'nt':
        return None

    q = ("nvidia-smi --query-gpu=name,temperature.gpu,utilization.gpu,"
         "utilization.memory,memory.total,memory.used,power.draw,power.limit,"
         "driver_version,fan.speed,clocks.current.graphics "
         "--format=csv,noheader,nounits")
    out = _run(q, timeout=12)
    if not out or "not recognized" in out.lower() or "failed" in out.lower():
        return None

    cards = []
    for line in out.split('\n'):
        p = [x.strip() for x in line.split(',')]
        if len(p) < 9:
            continue

        def num(v):
            try:
                return float(v)
            except Exception:
                return None

        temp = num(p[1])
        mem_total, mem_used = num(p[4]), num(p[5])
        card = {
            "name": p[0],
            "temperature_c": temp,
            "gpu_util_pct": num(p[2]),
            "mem_util_pct": num(p[3]),
            "mem_total_mb": mem_total,
            "mem_used_mb": mem_used,
            "mem_used_pct": round(mem_used / mem_total * 100, 1) if mem_total and mem_used else None,
            "power_draw_w": num(p[6]),
            "power_limit_w": num(p[7]),
            "driver_version": p[8],
            "fan_pct": num(p[9]) if len(p) > 9 else None,
            "clock_mhz": num(p[10]) if len(p) > 10 else None,
        }
        # ارزیابی دما
        if temp is not None:
            if temp >= 87:
                card["temp_status"] = "بحرانی"
            elif temp >= 80:
                card["temp_status"] = "داغ"
            elif temp >= 70:
                card["temp_status"] = "گرم"
            else:
                card["temp_status"] = "نرمال"
        cards.append(card)

    # فرآیندهایی که از GPU استفاده می‌کنند
    procs = []
    pout = _run("nvidia-smi --query-compute-apps=pid,process_name,used_memory "
                "--format=csv,noheader,nounits", timeout=10)
    for line in (pout or "").split('\n'):
        p = [x.strip() for x in line.split(',')]
        if len(p) >= 3 and p[0].isdigit():
            procs.append({"pid": int(p[0]),
                          "name": os.path.basename(p[1]),
                          "vram_mb": p[2]})

    return {"cards": cards, "processes": procs} if cards else None


# ---------------------------------------------------------------------------
# ۳. نرم‌افزارهای وابسته به GPU
# ---------------------------------------------------------------------------
def get_gpu_apps():
    """
    نرم‌افزارهای در حال اجرا که از کارت گرافیک استفاده می‌کنند.
    از شمارنده‌های عملکرد GPU ویندوز ۱۰/۱۱ استفاده می‌شود.
    """
    if os.name != 'nt':
        return []

    apps = {}

    # روش ۱: شمارنده GPU Engine (دقیق‌ترین)
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "(Get-Counter '\\GPU Engine(*)\\Utilization Percentage').CounterSamples | "
        "Where-Object {$_.CookedValue -gt 0.5} | "
        "Select-Object InstanceName,CookedValue | ConvertTo-Json -Compress"
    )
    rows = _run_ps(ps, timeout=20)
    for r in (rows or []):
        inst = str(r.get("InstanceName", ""))
        m = re.search(r'pid_(\d+)', inst)
        if not m:
            continue
        pid = int(m.group(1))
        val = float(r.get("CookedValue") or 0)
        if pid in apps:
            apps[pid]["gpu_pct"] += val
        else:
            apps[pid] = {"pid": pid, "gpu_pct": val, "name": None}

    # تبدیل PID به نام فرآیند
    if apps:
        pid_list = ",".join(str(p) for p in list(apps)[:40])
        ps2 = (f"Get-Process -Id {pid_list} -ErrorAction SilentlyContinue | "
               "Select-Object Id,ProcessName,@{N='MB';E={[math]::Round($_.WorkingSet64/1MB,1)}} | "
               "ConvertTo-Json -Compress")
        prows = _run_ps(ps2, timeout=15)
        for r in (prows or []):
            pid = r.get("Id")
            if pid in apps:
                apps[pid]["name"] = (r.get("ProcessName") or "") + ".exe"
                apps[pid]["ram_mb"] = r.get("MB")

    result = []
    for a in apps.values():
        if not a.get("name"):
            continue
        known = GPU_DEPENDENT_APPS.get(a["name"])
        result.append({
            "name": a["name"],
            "friendly_name": known[0] if known else a["name"].replace(".exe", ""),
            "purpose": known[1] if known else "استفاده از شتاب‌دهی گرافیکی",
            "gpu_pct": round(a["gpu_pct"], 1),
            "ram_mb": a.get("ram_mb"),
            "known": bool(known),
        })

    result.sort(key=lambda x: x["gpu_pct"], reverse=True)
    return result[:15]


# ---------------------------------------------------------------------------
# ۴. خطاهای گرافیکی از Event Viewer
# ---------------------------------------------------------------------------
def get_gpu_errors():
    """
    خطاهای مرتبط با گرافیک از Event Viewer.
    مهم‌ترین: TDR (Event ID 4101) — ریست شدن درایور در حین کار.
    """
    if os.name != 'nt':
        return []

    errors = []

    # TDR — «Display driver stopped responding and has recovered»
    ps = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-WinEvent -FilterHashtable @{LogName='System';"
        "ProviderName='Display';StartTime=(Get-Date).AddDays(-30)} "
        "-MaxEvents 15 | Select-Object TimeCreated,Id,LevelDisplayName,Message | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    for r in (_run_ps(ps, timeout=25) or []):
        msg = (r.get("Message") or "")[:300]
        errors.append({
            "source": "Display",
            "event_id": r.get("Id"),
            "time": str(r.get("TimeCreated") or "")[:19],
            "level": r.get("LevelDisplayName") or "Error",
            "message": msg,
            "is_tdr": r.get("Id") == 4101 or "stopped responding" in msg.lower(),
        })

    # خطاهای درایور nvlddmkm / igfx / amdkmdap
    ps2 = (
        "$ErrorActionPreference='SilentlyContinue';"
        "Get-WinEvent -FilterHashtable @{LogName='System';Level=1,2;"
        "StartTime=(Get-Date).AddDays(-30)} -MaxEvents 60 | "
        "Where-Object {$_.ProviderName -match 'nvlddmkm|igfx|amdkmd|nvid|Display|DXGI'} | "
        "Select-Object -First 10 TimeCreated,Id,ProviderName,Message | "
        "ConvertTo-Json -Compress -Depth 3"
    )
    for r in (_run_ps(ps2, timeout=25) or []):
        errors.append({
            "source": r.get("ProviderName") or "GPU Driver",
            "event_id": r.get("Id"),
            "time": str(r.get("TimeCreated") or "")[:19],
            "level": "Error",
            "message": (r.get("Message") or "")[:300],
            "is_tdr": False,
        })

    return errors[:15]


# ---------------------------------------------------------------------------
# ۵. تحلیل و توصیه
# ---------------------------------------------------------------------------
def analyze_gpu_health(gpus, nvidia, errors, apps):
    """مشکلات را شناسایی و راهکار پیشنهاد می‌دهد."""
    issues = []

    for g in gpus:
        # خطای Device Manager
        if g["error_code"]:
            sev = "critical" if g["error_code"] in (10, 43, 31, 28) else "warning"
            issues.append({
                "severity": sev,
                "title": f'خطای دستگاه در «{g["name"]}» (کد {g["error_code"]})',
                "detail": g["error_text"] or "خطای نامشخص دستگاه.",
                "fix": "درایور را حذف و مجدداً نصب کنید. برای حذف کامل از DDU استفاده کنید.",
                "commands": ["devmgmt.msc"],
            })

        # درایور قدیمی
        age = g.get("driver_age_days")
        if age and age > 730:
            issues.append({
                "severity": "warning",
                "title": f'درایور «{g["name"]}» بسیار قدیمی است',
                "detail": f'حدود {age // 365} سال از تاریخ درایور ({g["driver_date"]}) می‌گذرد.',
                "fix": "از سایت رسمی سازنده آخرین نسخه درایور را نصب کنید.",
                "commands": ["devmgmt.msc"],
            })
        elif age and age > 365:
            issues.append({
                "severity": "info",
                "title": f'درایور «{g["name"]}» به‌روزرسانی نشده',
                "detail": f'تاریخ درایور: {g["driver_date"]} (حدود {age} روز پیش).',
                "fix": "به‌روزرسانی درایور می‌تواند عملکرد و پایداری را بهبود دهد.",
                "commands": ["devmgmt.msc"],
            })

        # درایور پایه مایکروسافت = درایور اصلی نصب نیست
        if "microsoft basic" in g["name"].lower():
            issues.append({
                "severity": "critical",
                "title": "درایور اختصاصی کارت گرافیک نصب نیست",
                "detail": "ویندوز از درایور پایه (Microsoft Basic Display Adapter) استفاده می‌کند. "
                          "شتاب‌دهی سخت‌افزاری، بازی و رزولوشن‌های بالا کار نمی‌کنند.",
                "fix": "درایور رسمی Intel / NVIDIA / AMD را نصب کنید.",
                "commands": ["devmgmt.msc", "dxdiag"],
            })

    # وضعیت زنده NVIDIA
    if nvidia:
        for c in nvidia["cards"]:
            t = c.get("temperature_c")
            if t and t >= 87:
                issues.append({
                    "severity": "critical",
                    "title": f'دمای بحرانی کارت گرافیک: {t}°C',
                    "detail": "دمای بالای ۸۷ درجه باعث کاهش خودکار فرکانس (Thermal Throttling) "
                              "و در بلندمدت آسیب سخت‌افزاری می‌شود.",
                    "fix": "فن و خروجی هوا را تمیز کنید، خمیر سیلیکون را تعویض کنید، "
                           "و جریان هوای کیس را بررسی کنید.",
                    "commands": [],
                })
            elif t and t >= 80:
                issues.append({
                    "severity": "warning",
                    "title": f'دمای بالای کارت گرافیک: {t}°C',
                    "detail": "دما در محدوده هشدار است.",
                    "fix": "گردوغبار فن‌ها را پاک کنید و تهویه کیس را بهبود دهید.",
                    "commands": [],
                })

            mp = c.get("mem_used_pct")
            if mp and mp > 92:
                issues.append({
                    "severity": "warning",
                    "title": f'حافظه گرافیکی تقریباً پر است ({mp}%)',
                    "detail": f'{c.get("mem_used_mb")} از {c.get("mem_total_mb")} مگابایت VRAM اشغال شده.',
                    "fix": "برنامه‌های سنگین گرافیکی را ببندید یا کیفیت گرافیک بازی را کم کنید.",
                    "commands": ["taskmgr"],
                })

    # خطاهای TDR
    tdr = [e for e in errors if e.get("is_tdr")]
    if tdr:
        issues.append({
            "severity": "critical",
            "title": f'ریست شدن درایور گرافیک (TDR) — {len(tdr)} بار در ۳۰ روز اخیر',
            "detail": "خطای «Display driver stopped responding and has recovered». "
                      "معمولاً نشانه ناپایداری درایور، اورکلاک بیش از حد، "
                      "کمبود توان منبع تغذیه یا داغ شدن GPU است.",
            "fix": "۱. درایور را با DDU کاملاً حذف و نسخه پایدار نصب کنید.\n"
                   "۲. اورکلاک را غیرفعال کنید.\n"
                   "۳. دما و منبع تغذیه را بررسی کنید.\n"
                   "۴. در صورت نیاز مقدار TdrDelay را در رجیستری افزایش دهید.",
            "commands": ["dxdiag", "eventvwr"],
        })
    elif len(errors) >= 3:
        issues.append({
            "severity": "warning",
            "title": f'{len(errors)} خطای مرتبط با گرافیک در Event Viewer',
            "detail": "خطاهای مکرر درایور گرافیک ثبت شده است.",
            "fix": "جزئیات خطاها را در Event Viewer بررسی و درایور را به‌روز کنید.",
            "commands": ["eventvwr"],
        })

    # سیستم Hybrid
    if len([g for g in gpus if g["vendor"] in ("NVIDIA", "AMD", "Intel")]) >= 2:
        disc = [g for g in gpus if not g["is_integrated"]]
        if disc:
            issues.append({
                "severity": "info",
                "title": "سیستم دو-گرافیکی (Hybrid) شناسایی شد",
                "detail": f'کارت مجزا: {disc[0]["name"]} — در چنین سیستم‌هایی ممکن است '
                          "برنامه‌های سنگین به‌اشتباه روی گرافیک مجتمع اجرا شوند.",
                "fix": "در تنظیمات ویندوز (Graphics Settings) برای هر برنامه، "
                       "گزینه High performance را انتخاب کنید.",
                "commands": ["start ms-settings:display-advancedgraphics"],
            })

    if not issues:
        issues.append({
            "severity": "ok",
            "title": "مشکل قابل توجهی در کارت گرافیک یافت نشد",
            "detail": "درایورها نصب‌اند، خطای دستگاه وجود ندارد و رویداد بحرانی ثبت نشده است.",
            "fix": "",
            "commands": [],
        })

    order = {"critical": 0, "warning": 1, "info": 2, "ok": 3}
    issues.sort(key=lambda x: order.get(x["severity"], 9))
    return issues


def get_full_gpu_report():
    """گزارش کامل گرافیک."""
    gpus = get_gpu_list()
    nvidia = get_nvidia_live()

    # Win32_VideoController.AdapterRAM در برخی درایورها uint32 است و برای
    # کارت‌های 8GB به بالا مقدارِ سقف‌خورده (اغلب 4GB) برمی‌گرداند. برای
    # NVIDIA، nvidia-smi مقدار واقعی حافظه اختصاصی را می‌دهد؛ آن را با
    # حفظ ترتیب کارت‌های NVIDIA جایگزین می‌کنیم.
    if nvidia and nvidia.get("cards"):
        nv_cards = list(nvidia["cards"])
        nv_index = 0
        for gpu in gpus:
            if gpu.get("vendor") != "NVIDIA" or nv_index >= len(nv_cards):
                continue
            total_mb = nv_cards[nv_index].get("mem_total_mb")
            nv_index += 1
            try:
                if total_mb and float(total_mb) > 0:
                    gpu["vram_gb"] = round(float(total_mb) / 1024, 2)
                    gpu["vram_source"] = "nvidia-smi"
            except (TypeError, ValueError):
                pass

    errors = get_gpu_errors()
    apps = get_gpu_apps()
    issues = analyze_gpu_health(gpus, nvidia, errors, apps)

    return {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "gpus": gpus,
        "gpu_count": len(gpus),
        "has_nvidia": any(g["vendor"] == "NVIDIA" for g in gpus),
        "has_intel": any(g["vendor"] == "Intel" for g in gpus),
        "has_amd": any(g["vendor"] == "AMD" for g in gpus),
        "is_hybrid": len(gpus) >= 2,
        "nvidia_live": nvidia,
        "gpu_apps": apps,
        "errors": errors,
        "error_count": len(errors),
        "tdr_count": len([e for e in errors if e.get("is_tdr")]),
        "issues": issues,
        "critical_count": len([i for i in issues if i["severity"] == "critical"]),
    }


if __name__ == "__main__":
    print(json.dumps(get_full_gpu_report(), ensure_ascii=False, indent=2))
