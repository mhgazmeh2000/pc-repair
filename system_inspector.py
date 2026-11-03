# -*- coding: utf-8 -*-
"""
System Inspector Module for PC Repair Toolbox Pro
Gathers Windows system diagnostics, disk space, event logs (Critical/Error), network, and health status.
"""

import os
import sys
import platform
import subprocess
import json
import time

def get_windows_event_errors():
    events = []
    if os.name == 'nt':
        # Query recent Critical (1) and Error (2) events from System log
        try:
            cmd_sys = 'wevtutil qe System /q:"*[System[(Level=1 or Level=2)]]" /f:text /c:5'
            res = subprocess.run(cmd_sys, capture_output=True, text=True, shell=True, timeout=5)
            if res.stdout and len(res.stdout.strip()) > 0:
                lines = [l.strip() for l in res.stdout.split("\n") if l.strip()]
                events.append({
                    "log_name": "System",
                    "event_count": len(lines) // 5 or 1,
                    "details": " ".join(lines[:12])
                })
        except Exception as e:
            events.append({"log_name": "System", "error": str(e)})

        # Query recent Critical (1) and Error (2) events from Application log
        try:
            cmd_app = 'wevtutil qe Application /q:"*[System[(Level=1 or Level=2)]]" /f:text /c:5'
            res = subprocess.run(cmd_app, capture_output=True, text=True, shell=True, timeout=5)
            if res.stdout and len(res.stdout.strip()) > 0:
                lines = [l.strip() for l in res.stdout.split("\n") if l.strip()]
                events.append({
                    "log_name": "Application",
                    "event_count": len(lines) // 5 or 1,
                    "details": " ".join(lines[:12])
                })
        except Exception as e:
            events.append({"log_name": "Application", "error": str(e)})

    return events

def get_system_diagnostics():
    info = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "hostname": platform.node(),
        "python_version": platform.python_version(),
        "disk_c": {},
        "memory": {},
        "network": {},
        "event_viewer_logs": get_windows_event_errors(),
        "health_issues": []
    }

    # CPU and memory — these fields power the System Center UI as well as AI context.
    # platform.processor() is often empty on Windows, therefore query CIM as fallback.
    try:
        cpu_name = platform.processor().strip()
        if os.name == 'nt' and not cpu_name:
            r = subprocess.run(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)"],
                capture_output=True, text=True, timeout=6,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            cpu_name = (r.stdout or "").strip()
        info["cpu"] = {"name": cpu_name or "نامشخص"}
    except Exception as e:
        info["cpu"] = {"error": str(e)}

    try:
        if os.name == 'nt':
            import ctypes
            class _MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]
            mem = _MEMORYSTATUSEX()
            mem.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(mem)):
                total = round(mem.ullTotalPhys / (1024 ** 3), 1)
                available = round(mem.ullAvailPhys / (1024 ** 3), 1)
                info["memory"] = {
                    "total_gb": total, "available_gb": available,
                    "percent_used": int(mem.dwMemoryLoad),
                }
    except Exception as e:
        info["memory"] = {"error": str(e)}

    # Disk Space C:
    try:
        if os.name == 'nt':
            import ctypes
            free_bytes = ctypes.c_ulonglong(0)
            total_bytes = ctypes.c_ulonglong(0)
            ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                ctypes.c_wchar_p("C:\\"),
                None,
                ctypes.pointer(total_bytes),
                ctypes.pointer(free_bytes)
            )
            total_gb = round(total_bytes.value / (1024**3), 2)
            free_gb = round(free_bytes.value / (1024**3), 2)
            used_gb = round(total_gb - free_gb, 2)
            percent_used = round((used_gb / total_gb) * 100, 1) if total_gb > 0 else 0
            
            info["disk_c"] = {
                "total_gb": total_gb,
                "free_gb": free_gb,
                "used_gb": used_gb,
                "percent_used": percent_used
            }
            
            if percent_used > 85:
                info["health_issues"].append(f"کمبود فضای درایو C: {percent_used}% اشغال شده است ({free_gb} گیگابایت آزاد).")
    except Exception as e:
        info["disk_c"]["error"] = str(e)

    # Network Diagnostic
    try:
        if os.name == 'nt':
            res = subprocess.run("ipconfig /all", capture_output=True, text=True, shell=True, timeout=5)
            has_ip = "IPv4" in res.stdout or "IP Address" in res.stdout
            info["network"] = {
                "connected": has_ip,
                "details": "IP Address detected" if has_ip else "No active IPv4 address found"
            }
            if not has_ip:
                info["health_issues"].append("عدم شناسایی آدرس IP فعال در کارت شبکه.")
    except Exception as e:
        info["network"]["error"] = str(e)

    # Temp Files Scan
    try:
        temp_dir = os.environ.get("TEMP", "")
        if temp_dir and os.path.exists(temp_dir):
            temp_files_count = 0
            temp_size_bytes = 0
            for root, dirs, files in os.walk(temp_dir):
                temp_files_count += len(files)
                for f in files:
                    try:
                        temp_size_bytes += os.path.getsize(os.path.join(root, f))
                    except Exception:
                        pass
            temp_mb = round(temp_size_bytes / (1024**2), 1)
            info["temp_files"] = {
                "count": temp_files_count,
                "size_mb": temp_mb
            }
            if temp_mb > 500:
                info["health_issues"].append(f"حجم زیاد فایل‌های موقت Temp: {temp_mb} مگابایت ({temp_files_count} فایل).")
    except Exception as e:
        info["temp_files_error"] = str(e)

    if info["event_viewer_logs"]:
        info["health_issues"].append(f"تعداد {len(info['event_viewer_logs'])} گزارش خطای مهم در Event Viewer ویندوز ثبت شده است.")

    return info

if __name__ == "__main__":
    print(json.dumps(get_system_diagnostics(), ensure_ascii=False, indent=2))
