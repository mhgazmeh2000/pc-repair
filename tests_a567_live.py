# -*- coding: utf-8 -*-
"""تست زندهٔ الف‑۵ · الف‑۶ · الف‑۷"""
import atexit, json, os, socket, subprocess, sys
import time as _t
import urllib.error, urllib.request

def _free_port():
    s = socket.socket(); s.bind(('127.0.0.1', 0))
    p = s.getsockname()[1]; s.close(); return p

PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"
env = dict(os.environ, SERVER_PORT=str(PORT))
srv = subprocess.Popen([sys.executable, 'backend_server.py'],
                       cwd='/home/user/pc-repair', env=env,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
atexit.register(lambda: srv.kill())
for _ in range(60):
    try:
        urllib.request.urlopen(f"{BASE}/", timeout=2); break
    except Exception:
        _t.sleep(0.5)

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

with urllib.request.urlopen(f"{BASE}/") as r:
    html = r.read().decode('utf-8')
i = html.index('__TOOLBOX_TOKEN__ = "') + len('__TOOLBOX_TOKEN__ = "')
TOKEN = html[i:html.index('"', i)]

def post(path, data=None):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(data or {}).encode('utf-8'),
        headers={'Content-Type': 'application/json', 'X-Toolbox-Token': TOKEN},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')

print("═" * 62)
print("۱) الف‑۵ — نقطهٔ بازگشت")
print("═" * 62)
st, d = post('/api/restore_status')
chk(st == 200 and d.get('success'), f"وضعیت ({st})")
chk('is_admin' in d, f"وضعیت ادمین: {d.get('is_admin')}")
chk('enabled' in d, f"وضعیت محافظت: {d.get('enabled')}")

st, d = post('/api/restore_create', {'reason': 'تست'})
chk(st == 200, f"ساخت پاسخ داد ({st})")
chk(not d.get('success'), "روی لینوکس ناموفق — بدون ادعای دروغ")
chk('ویندوز' in d.get('error', ''), f"پیام: {d.get('error','')[:45]}")

st, d = post('/api/restore_list')
chk(d.get('success'), "فهرست بدون کرش")
st, d = post('/api/restore_enable')
chk(st == 200, "روشن‌کردن پاسخ داد")

print()
print("═" * 62)
print("۲) الف‑۶ — حافظهٔ بین‌جلسه‌ای")
print("═" * 62)
st, d = post('/api/repair_history')
chk(st == 200 and d.get('success'), f"پاسخ ({st})")
chk('total' in d and 'summary_fa' in d, "ساختار کامل")
chk('ineffective_steps' in d, "فهرست مراحل بی‌اثر")
print(f"     {d.get('summary_fa','')}")

st, d = post('/api/repair_history_clear')
chk(d.get('success'), "پاک‌سازی")

print()
print("═" * 62)
print("۳) الف‑۷ — فرهنگ رویداد")
print("═" * 62)
RAW = """Id           : 41
ProviderName : Microsoft-Windows-Kernel-Power

Id           : 7031
ProviderName : Service Control Manager

Id           : 77777
ProviderName : Unknown"""
st, d = post('/api/explain_events', {'text': RAW})
chk(st == 200 and d.get('success'), f"تحلیل ({st})")
chk(len(d.get('known', [])) == 2, f"۲ رویداد شناخته‌شده ({len(d.get('known',[]))})")
chk(len(d.get('unknown', [])) == 1, "۱ ناشناخته")
chk(d.get('report_fa'), "گزارش متنی برای AI")
chk('counts' in d, f"شمارش: {d.get('counts')}")
chk(d['known'][0]['severity'] == 'critical', "بحرانی اول")
print(f"     {d.get('summary_fa','')}")

st, d = post('/api/explain_events', {})
chk(st == 200 and d.get('success'), "بدون متن — خودش می‌خواند")

st, d = post('/api/event_lookup', {'event_id': 4101,
                                   'provider': 'Microsoft-Windows-Display'})
chk(d.get('success'), f"جست‌وجوی تکی: {d.get('title','')}")
chk('tool_ids' in d, "ابزارهای مرتبط")

st, d = post('/api/event_lookup', {'event_id': 99999})
chk(st == 404, f"رویداد ناشناخته → {st}")
chk('AI' in d.get('error', ''), "راهنمایی به AI")

print()
print("═" * 62)
print("۴) امنیت — endpointهای جدید")
print("═" * 62)
for ep in ['/api/restore_status', '/api/restore_create', '/api/restore_enable',
           '/api/repair_history', '/api/repair_history_clear',
           '/api/explain_events', '/api/event_lookup']:
    req = urllib.request.Request(
        BASE + ep, data=b'{}',
        headers={'Content-Type': 'application/json',
                 'Origin': 'https://evil.example.com'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    chk(code == 403, f"{ep} رد شد ({code})")

print()
print("═" * 62)
print("۵) سلامت کل سیستم")
print("═" * 62)
for ep, data in [('/api/local_diagnose', {'fast': True}),
                 ('/api/baseline_list', {}),
                 ('/api/health_snapshot', {'keys': ['ram_free_pct']}),
                 ('/api/ws_tree', {}),
                 ('/api/system_query', {'keys': ['os_info']}),
                 ('/api/db_stats', {}),
                 ('/api/personas', {})]:
    st, _ = post(ep, data)
    chk(st == 200, f"{ep} → {st}")

st, d = post('/api/settings')
chk(st == 200, "تنظیمات")

print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
