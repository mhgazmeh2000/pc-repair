# -*- coding: utf-8 -*-
"""تست health_metrics و local_diagnosis با داده‌های ساختگی"""
import sys
sys.path.insert(0, '/home/user/pc-repair')
import health_metrics as hm
import local_diagnosis as ld

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

def mk(key, value, label="x", unit="", higher=True, error=""):
    return {"key": key, "label_fa": label, "unit": unit,
            "higher_is_better": higher, "value": value, "error": error}

print("═" * 60)
print("۱) ساختار سنجه‌ها")
print("═" * 60)
chk(len(hm.METRICS) == 14, f"{len(hm.METRICS)} سنجه تعریف شده")
chk(all(callable(v) for v in hm.METRICS.values()), "همه توابع قابل فراخوانی‌اند")
chk(len(hm.STEP_METRICS) == 9, f"نگاشت برای {len(hm.STEP_METRICS)} مرحله تعمیر")
# هر سنجهٔ نگاشت‌شده باید واقعاً وجود داشته باشد
missing = [m for lst in hm.STEP_METRICS.values() for m in lst if m not in hm.METRICS]
chk(not missing, "همه سنجه‌های نگاشت موجودند", str(missing))

print()
print("═" * 60)
print("۲) metrics_for_steps — بدون تکرار")
print("═" * 60)
r = hm.metrics_for_steps(["temp_clean", "cleanmgr"])
chk("disk_c_free_pct" in r, "سنجهٔ مشترک آمده")
chk(len(r) == len(set(r)), f"بدون تکرار: {r}")
chk(hm.metrics_for_steps([]) == [], "لیست خالی → خالی")
chk(hm.metrics_for_steps(None) == [], "None → خالی")
chk(hm.metrics_for_steps(["ناموجود"]) == [], "مرحلهٔ ناشناس → خالی")

print()
print("═" * 60)
print("۳) compare — سناریوی «واقعاً حل شد»")
print("═" * 60)
before = {"disk_c_free_pct": mk("disk_c_free_pct", 4.2, "فضای آزاد C", "%", True)}
after  = {"disk_c_free_pct": mk("disk_c_free_pct", 31.8, "فضای آزاد C", "%", True)}
c = hm.compare(before, after)
chk(c["verdict"] == "resolved", f"حکم: {c['verdict']}")
chk(c["improved"] == 1, "یک سنجه بهبود یافت")
chk(abs(c["rows"][0]["delta"] - 27.6) < 0.01, f"دلتا درست: {c['rows'][0]['delta']}")
print(f"     {c['summary_fa']}")

print()
print("═" * 60)
print("۴) compare — سناریوی «تغییر نکرد» (مهم‌ترین حالت)")
print("═" * 60)
before = {"disk_c_free_pct": mk("disk_c_free_pct", 8.0, "فضا", "%", True)}
after  = {"disk_c_free_pct": mk("disk_c_free_pct", 8.2, "فضا", "%", True)}
c = hm.compare(before, after)
chk(c["verdict"] == "no_change", f"۰.۲٪ نویز است نه بهبود → {c['verdict']}")
chk(c["rows"][0]["status"] == "unchanged", "وضعیت unchanged")
txt = hm.format_for_ai(c)
chk("به ریشهٔ مشکل نخورده" in txt, "متن AI هشدار می‌دهد تکرار نکند")
print(f"     {c['summary_fa']}")

print()
print("═" * 60)
print("۵) compare — جهت بهبود معکوس (کمتر = بهتر)")
print("═" * 60)
before = {"temp_size_mb": mk("temp_size_mb", 3000, "temp", "MB", False)}
after  = {"temp_size_mb": mk("temp_size_mb", 120, "temp", "MB", False)}
c = hm.compare(before, after)
chk(c["verdict"] == "resolved", "کاهش حجم temp = بهبود")
chk(c["rows"][0]["delta"] == -2880, f"دلتا منفی: {c['rows'][0]['delta']}")

# و برعکس: افزایش تأخیر شبکه = بد
before = {"net_latency_ms": mk("net_latency_ms", 30, "تأخیر", "ms", False)}
after  = {"net_latency_ms": mk("net_latency_ms", 250, "تأخیر", "ms", False)}
c = hm.compare(before, after)
chk(c["verdict"] == "regressed", f"افزایش تأخیر = افت → {c['verdict']}")
chk("بدتر" in hm.format_for_ai(c), "متن AI هشدار افت می‌دهد")

print()
print("═" * 60)
print("۶) compare — حالت‌های مرزی")
print("═" * 60)
c = hm.compare({}, {})
chk(c["verdict"] == "unknown", "دو عکس خالی")
c = hm.compare({"x": mk("x", None)}, {"x": mk("x", 5)})
chk(c["rows"][0]["status"] == "unknown", "مقدار None → unknown")
c = hm.compare({"x": mk("x", 1, higher=True)}, {"x": mk("x", 0, higher=True)})
chk(c["verdict"] == "regressed", "سنجهٔ وضعیتی ۱→۰ = افت")
c = hm.compare({"a": mk("a", 1, higher=True), "b": mk("b", 10, "b", "", False)},
               {"a": mk("a", 0, higher=True), "b": mk("b", 1, "b", "", False)})
chk(c["verdict"] == "partial", f"یکی بهتر یکی بدتر → {c['verdict']}")
chk(hm.format_for_ai(None) == "", "ورودی None → متن خالی")

print()
print("═" * 60)
print("۷) قواعد تشخیص محلی")
print("═" * 60)
chk(len(ld.RULES) == 13, f"{len(ld.RULES)} قاعده")
missing = [m for m in ld.REQUIRED_METRICS if m not in hm.METRICS]
chk(not missing, "همه سنجه‌های موردنیاز موجودند", str(missing))
chk(all(m in ld.REQUIRED_METRICS for m in ld.FAST_METRICS), "سنجه‌های سریع زیرمجموعه‌اند")

# سیستم سالم
healthy = {
    "disk_c_free_pct": mk("disk_c_free_pct", 55), "disk_c_free_gb": mk("disk_c_free_gb", 200),
    "ram_free_pct": mk("ram_free_pct", 45), "temp_size_mb": mk("temp_size_mb", 200),
    "startup_count": mk("startup_count", 8), "sfc_corrupt": mk("sfc_corrupt", 0),
    "dism_health": mk("dism_health", 0), "pending_reboot": mk("pending_reboot", 0),
    "net_latency_ms": mk("net_latency_ms", 25), "dns_ok": mk("dns_ok", 1),
    "error_events_24h": mk("error_events_24h", 3), "problem_drivers": mk("problem_drivers", 0),
    "defender_realtime": mk("defender_realtime", 1), "boot_time_sec": mk("boot_time_sec", 22),
}
r = ld.diagnose(healthy)
chk(r["healthy"], "سیستم سالم → بدون یافته")
chk(r["counts"]["critical"] == 0, "صفر مورد بحرانی")
print(f"     {r['summary_fa']}")

print()
print("═" * 60)
print("۸) سیستم بیمار — هر قاعده باید فعال شود")
print("═" * 60)
sick = {
    "disk_c_free_pct": mk("disk_c_free_pct", 3.1), "disk_c_free_gb": mk("disk_c_free_gb", 7),
    "ram_free_pct": mk("ram_free_pct", 4), "temp_size_mb": mk("temp_size_mb", 6000),
    "startup_count": mk("startup_count", 31), "sfc_corrupt": mk("sfc_corrupt", 1),
    "dism_health": mk("dism_health", 1), "pending_reboot": mk("pending_reboot", 1),
    "net_latency_ms": mk("net_latency_ms", 450), "dns_ok": mk("dns_ok", 0),
    "error_events_24h": mk("error_events_24h", 88), "problem_drivers": mk("problem_drivers", 3),
    "defender_realtime": mk("defender_realtime", 0), "boot_time_sec": mk("boot_time_sec", 140),
}
r = ld.diagnose(sick)
ids = [f["id"] for f in r["findings"]]
chk(len(r["findings"]) == 13, f"همهٔ ۱۳ قاعده فعال شد ({len(r['findings'])})", str(ids))
chk(r["findings"][0]["severity"] == "critical", "بحرانی‌ها اول مرتب شده‌اند")
chk("pending_reboot" in ids, "ری‌استارت معلق تشخیص داده شد")
chk(r["counts"]["critical"] >= 5, f"{r['counts']['critical']} مورد بحرانی")
chk(len(r["suggested_steps"]) > 0, f"مراحل پیشنهادی: {r['suggested_steps']}")
chk(len(r["suggested_steps"]) == len(set(r["suggested_steps"])), "مراحل بدون تکرار")
print(f"     {r['summary_fa']}")

print()
print("═" * 60)
print("۹) آستانه‌ها — نباید بیش از حد حساس باشند")
print("═" * 60)
borderline = dict(healthy)
borderline["disk_c_free_pct"] = mk("disk_c_free_pct", 12)
borderline["startup_count"] = mk("startup_count", 14)
borderline["error_events_24h"] = mk("error_events_24h", 15)
r = ld.diagnose(borderline)
chk(r["healthy"], f"مقادیر مرزی هشدار الکی نمی‌دهند ({[f['id'] for f in r['findings']]})")

# دقیقاً روی مرز
edge = dict(healthy)
edge["disk_c_free_pct"] = mk("disk_c_free_pct", 9.9)
r = ld.diagnose(edge)
chk(any(f["id"] == "disk_low" for f in r["findings"]), "۹.۹٪ هشدار می‌دهد")

print()
print("═" * 60)
print("۱۰) متن خروجی برای AI")
print("═" * 60)
t = ld.format_for_ai(ld.diagnose(sick))
chk("بررسی محلی" in t, "عنوان دارد")
chk("بحرانی" in t, "سطح خطر فارسی")
chk("دوباره بررسی‌شان نکن" in t, "به AI می‌گوید کار تکراری نکند")
chk(len(t) > 400, f"متن به‌قدر کافی کامل است ({len(t)} کاراکتر)")
t2 = ld.format_for_ai(ld.diagnose(healthy))
chk("هیچ مشکل" in t2, "سیستم سالم هم متن مناسب دارد")

# قاعدهٔ خراب نباید کل تشخیص را بشکند
bad = {"disk_c_free_pct": "این عدد نیست"}
try:
    r = ld.diagnose(bad)
    chk(True, "داده‌های خراب باعث کرش نمی‌شوند")
except Exception as e:
    chk(False, "کرش کرد", str(e))

print()
print("─" * 60)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
