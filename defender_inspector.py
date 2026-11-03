# -*- coding: utf-8 -*-
"""خواندن امن وضعیت Microsoft Defender؛ هیچ تغییری خودکار اعمال نمی‌شود."""
import json
import os
import subprocess
import time


def _ps(script, timeout=30):
    if os.name != "nt":
        return False, "", "فقط در ویندوز در دسترس است."
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
             "-Command", script],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        return r.returncode == 0, (r.stdout or "").strip(), (r.stderr or "").strip()
    except subprocess.TimeoutExpired:
        return False, "", "زمان اجرای فرمان تمام شد."
    except Exception as e:
        return False, "", str(e)


def _json(script, timeout=30, default=None):
    ok, out, err = _ps(script, timeout)
    if not ok or not out:
        return default, err or "داده‌ای دریافت نشد"
    try:
        return json.loads(out), ""
    except Exception:
        return default, "پاسخ Defender قابل‌خواندن نبود"


def status():
    """خلاصهٔ قابل‌نمایش Defender، بدون مسیر یا شناسهٔ شخصی."""
    script = r"""
try {
  $s=Get-MpComputerStatus -ErrorAction Stop
  # در سیستم‌هایی که هنوز Quick/Full Scan انجام نشده، زمان‌ها null هستند.
  # فراخوانی مستقیم .ToString() روی null همان خطای تصویر را ایجاد می‌کرد.
  function Fmt-Date($v) { if ($null -eq $v) { return $null }; return $v.ToString('o') }
  [pscustomobject]@{
    antivirus_enabled=[bool]$s.AntivirusEnabled
    realtime_enabled=[bool]$s.RealTimeProtectionEnabled
    behavior_enabled=[bool]$s.BehaviorMonitorEnabled
    cloud_enabled=[bool]$s.MAPSReporting
    tamper_enabled=[bool]$s.IsTamperProtected
    signatures_updated=(Fmt-Date $s.AntivirusSignatureLastUpdated)
    signature_version=$s.AntivirusSignatureVersion
    quick_scan=(Fmt-Date $s.QuickScanEndTime)
    full_scan=(Fmt-Date $s.FullScanEndTime)
    engine_version=$s.AMEngineVersion
    product_version=$s.AMProductVersion
  } | ConvertTo-Json -Compress
} catch { @{error=$_.Exception.Message} | ConvertTo-Json -Compress }
"""
    data, err = _json(script, default={})
    if data.get("error"):
        return {"success": False, "available": False, "error": data["error"]}
    if err:
        return {"success": False, "available": False, "error": err}
    return {"success": True, "available": True, "status": data,
            "checked_at": time.strftime("%Y-%m-%d %H:%M:%S")}


def threats(limit=50):
    """تهدیدهای ثبت‌شده؛ مسیر فایل عمداً ارسال نمی‌شود."""
    script = rf"""
try {{
  $x=Get-MpThreatDetection -ErrorAction SilentlyContinue | Select-Object -First {int(limit)} ThreatID,ThreatStatusID,InitialDetectionTime,LastThreatStatusChangeTime,Resources
  @($x | ForEach-Object {{
    [pscustomobject]@{{id=$_.ThreatID; status=$_.ThreatStatusID; detected=$_.InitialDetectionTime.ToString('o'); changed=$_.LastThreatStatusChangeTime.ToString('o'); resource_count=@($_.Resources).Count}}
  }}) | ConvertTo-Json -Compress
}} catch {{ @() | ConvertTo-Json -Compress }}
"""
    data, err = _json(script, default=[])
    if isinstance(data, dict): data = [data]
    return {"success": not bool(err), "threats": data or [], "error": err}


def exclusions():
    """فهرست و درجه‌بندی استثناها؛ حذف یا تغییر انجام نمی‌دهد."""
    script = r"""
try { Get-MpPreference | Select-Object ExclusionPath,ExclusionProcess,ExclusionExtension | ConvertTo-Json -Compress } catch { @{error=$_.Exception.Message} | ConvertTo-Json -Compress }
"""
    data, err = _json(script, default={})
    if data.get("error"):
        return {"success": False, "items": [], "error": data["error"]}
    items = []
    suspicious = ("c:\\windows", "c:\\programdata", "\\appdata\\roaming", "\\appdata\\local\\temp", "c:\\")
    for typ, values in (("path", data.get("ExclusionPath") or []),
                        ("process", data.get("ExclusionProcess") or []),
                        ("extension", data.get("ExclusionExtension") or [])):
        if isinstance(values, str): values = [values]
        for value in values:
            low = str(value).lower()
            severity = "warning" if any(x in low for x in suspicious) or low in ("*.exe", "powershell.exe") else "info"
            items.append({"type": typ, "value": str(value), "severity": severity})
    return {"success": not bool(err), "items": items, "error": err}


def update_signatures():
    ok, out, err = _ps("Update-MpSignature -ErrorAction Stop; 'OK'", timeout=180)
    return {"success": ok and "OK" in out, "message": "تعریف‌های Defender به‌روزرسانی شدند." if ok else "به‌روزرسانی ناموفق بود.", "error": err or out}
