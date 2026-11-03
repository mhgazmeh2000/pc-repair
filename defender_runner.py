# -*- coding: utf-8 -*-
"""اجرای کنترل‌شدهٔ اسکن Defender در Thread؛ فقط Quick/Full با تأیید UI."""
import os, subprocess, threading, time, uuid

_JOBS, _LOCK = {}, threading.Lock()

def start_scan(scan_type="quick", path=""):
    scan_type = (scan_type or "quick").lower()
    if scan_type not in ("quick", "full", "custom"):
        return {"success": False, "error": "نوع اسکن نامعتبر است."}
    if scan_type == "custom" and not path:
        return {"success": False, "error": "مسیر اسکن سفارشی مشخص نشده است."}
    if os.name != "nt": return {"success": False, "error": "فقط در ویندوز در دسترس است."}
    jid = "defscan_" + uuid.uuid4().hex[:10]
    job = {"job_id": jid, "status": "running", "type": scan_type, "started_at": time.time(), "output": "در حال شروع اسکن…"}
    with _LOCK: _JOBS[jid] = job
    def run():
        cmd = "Start-MpScan -ScanType QuickScan" if scan_type == "quick" else "Start-MpScan -ScanType FullScan"
        if scan_type == "custom":
            safe = path.replace("'", "''")
            cmd = f"Start-MpScan -ScanPath '{safe}'"
        try:
            r = subprocess.run(["powershell","-NoProfile","-NonInteractive","-Command",cmd], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=7200, creationflags=getattr(subprocess,"CREATE_NO_WINDOW",0))
            job.update(status="done" if r.returncode == 0 else "error", output=(r.stdout or r.stderr or "اسکن پایان یافت."), finished_at=time.time())
        except subprocess.TimeoutExpired:
            job.update(status="error", output="اسکن بیش از زمان مجاز داخلی طول کشید.", finished_at=time.time())
        except Exception as e:
            job.update(status="error", output=str(e), finished_at=time.time())
    threading.Thread(target=run, daemon=True, name=jid).start()
    return {"success": True, "job_id": jid, "type": scan_type}

def job_status(job_id):
    with _LOCK: job = _JOBS.get(job_id)
    return {"success": bool(job), **(job or {"error":"اسکن یافت نشد."})}
