# -*- coding: utf-8 -*-
"""تست زندهٔ گام ۳ — خط پایه + پرس‌وجوهای جدید"""
import json
import os
import sys
import urllib.request
import urllib.error

import atexit, socket, subprocess
import time as _t

def _free_port():
    _s = socket.socket(); _s.bind(('127.0.0.1', 0))
    _p = _s.getsockname()[1]; _s.close(); return _p

PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"

# سرور را خود تست بالا می‌آورد — وابستگی به فرآیند پس‌زمینهٔ shell
# تست را غیرقابل اتکا می‌کرد
_env = dict(os.environ, SERVER_PORT=str(PORT))
_srv = subprocess.Popen([sys.executable, 'backend_server.py'],
                        cwd=os.path.dirname(os.path.abspath(__file__)) or '.',
                        env=_env, stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
atexit.register(lambda: _srv.kill())
for _ in range(60):
    try:
        urllib.request.urlopen(f"{BASE}/", timeout=2); break
    except Exception:
        _t.sleep(0.5)
else:
    print("سرور بالا نیامد"); sys.exit(1)
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
        with urllib.request.urlopen(req, timeout=180) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')


print("═" * 62)
print("۱) الف‑۳ — پرس‌وجوهای جدید از طریق API")
print("═" * 62)
NEW = ['scheduled_tasks', 'smart_attributes', 'pending_reboot',
       'disk_io_latency', 'page_file', 'reliability_index',
       'thermal_throttling', 'firewall_rules']
st, d = post('/api/system_query', {'keys': NEW[:8]})
chk(st == 200, f"پاسخ {st}")
chk(d.get('success'), "success=True")
chk(len(d.get('requested', [])) == 8, f"۸ پرس‌وجو پذیرفته شد ({len(d.get('requested', []))})")
chk(not d.get('unknown'), f"هیچ کلید ناشناسی نیست: {d.get('unknown')}")
chk(len(d.get('results', [])) == 8, "۸ نتیجه برگشت")
chk(all(r.get('desc') for r in d.get('results', [])), "همه توضیح فارسی دارند")

print()
print("═" * 62)
print("۲) خط پایه — ثبت")
print("═" * 62)
st, d = post('/api/baseline_save', {'label': 'تست API', 'note': 'ثبت از تست'})
chk(st == 200, f"پاسخ {st}")
chk(d.get('success'), f"ثبت شد (id={d.get('id')})")
chk(d.get('metrics_total', 0) == 14, f"۱۴ سنجه ثبت شد ({d.get('metrics_total')})")
BID = d.get('id')

print()
print("═" * 62)
print("۳) خط پایه — فهرست")
print("═" * 62)
st, d = post('/api/baseline_list')
chk(st == 200 and d.get('success'), f"پاسخ {st}")
bls = d.get('baselines', [])
chk(len(bls) >= 1, f"{len(bls)} خط پایه")
chk(bls[0]['label'] == 'تست API', "برچسب درست")
chk('age_days' in bls[0], "سن محاسبه شد")
chk('snapshot' not in bls[0], "فهرست سبک است")

print()
print("═" * 62)
print("۴) خط پایه — مقایسه")
print("═" * 62)
st, d = post('/api/baseline_compare', {'id': BID})
chk(st == 200, f"پاسخ {st}")
chk(d.get('success'), "مقایسه انجام شد")
chk('rows' in d and 'worse' in d and 'better' in d, "ساختار کامل")
chk('summary_fa' in d, f"خلاصه: {d.get('summary_fa', '')[:60]}")
chk('report_fa' in d, "گزارش متنی برای AI ساخته شد")
# چون بلافاصله بعد از ثبت مقایسه شد، نباید انحراف باشد
chk(len(d.get('worse', [])) == 0, f"بلافاصله بعد از ثبت: بدون انحراف ({len(d.get('worse', []))})")

print()
print("═" * 62)
print("۵) خط پایه — حذف")
print("═" * 62)
st, d = post('/api/baseline_delete', {'id': BID})
chk(st == 200 and d.get('success'), "حذف موفق")
st, d = post('/api/baseline_list')
chk(all(b['id'] != BID for b in d.get('baselines', [])), "از فهرست حذف شد")

print()
print("═" * 62)
print("۶) مقایسه بدون خط پایه — پیام راهنما")
print("═" * 62)
for b in post('/api/baseline_list')[1].get('baselines', []):
    post('/api/baseline_delete', {'id': b['id']})
st, d = post('/api/baseline_compare', {})
chk(not d.get('success'), "بدون خط پایه → ناموفق")
chk('ثبت وضعیت سالم' in d.get('error', ''), f"راهنمای فارسی: {d.get('error', '')[:55]}")

st, d = post('/api/baseline_analyze', {})
chk(st == 404, f"analyze بدون خط پایه → {st}")

print()
print("═" * 62)
print("۷) امنیت — endpointهای جدید محافظت می‌شوند")
print("═" * 62)
for ep in ['/api/baseline_save', '/api/baseline_list', '/api/baseline_delete',
           '/api/baseline_compare', '/api/baseline_analyze']:
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
print("۸) endpointهای قبلی نشکسته‌اند")
print("═" * 62)
for ep, data in [('/api/local_diagnose', {'fast': True}),
                 ('/api/health_snapshot', {'keys': ['ram_free_pct']}),
                 ('/api/db_stats', {}),
                 ('/api/system_query', {'keys': ['os_info']})]:
    st, d = post(ep, data)
    chk(st == 200, f"{ep} → {st}")

print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
