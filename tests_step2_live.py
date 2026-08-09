# -*- coding: utf-8 -*-
"""تست زندهٔ گام ۲ — endpointهای جدید + UI"""
import json
import os
import sys
import urllib.request

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


def get_token():
    with urllib.request.urlopen(f"{BASE}/") as r:
        html = r.read().decode('utf-8')
    i = html.index('__TOOLBOX_TOKEN__ = "') + len('__TOOLBOX_TOKEN__ = "')
    return html[i:html.index('"', i)]


TOKEN = get_token()


def post(path, data=None, expect=200):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data or {}).encode('utf-8'),
        headers={'Content-Type': 'application/json',
                 'X-Toolbox-Token': TOKEN},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')


print("═" * 60)
print("۱) endpoint تشخیص محلی")
print("═" * 60)
st, d = post('/api/local_diagnose', {'fast': True})
chk(st == 200, f"پاسخ {st}")
chk(d.get('success'), "success=True")
chk('findings' in d, "کلید findings")
chk('counts' in d, "کلید counts")
chk('summary_fa' in d and d['summary_fa'], f"خلاصهٔ فارسی: {d.get('summary_fa','')[:50]}")
chk(isinstance(d.get('suggested_steps'), list), "مراحل پیشنهادی لیست است")
print(f"     یافته‌ها: {len(d.get('findings', []))} · {d.get('counts')}")
for f in d.get('findings', [])[:3]:
    print(f"       {f['severity']}: {f['title_fa']}")

print()
print("═" * 60)
print("۲) endpoint عکس سلامت")
print("═" * 60)
st, d = post('/api/health_snapshot', {'keys': ['disk_c_free_pct', 'ram_free_pct']})
chk(st == 200, f"پاسخ {st}")
chk(d.get('success'), "success=True")
snap = d.get('snapshot', {})
chk(len(snap) == 2, f"دو سنجه برگشت ({len(snap)})")
for k, v in snap.items():
    has = v.get('value') is not None
    print(f"     {k}: value={v.get('value')} error={v.get('error') or '—'}")
chk(all('label_fa' in v for v in snap.values()), "همه برچسب فارسی دارند")
chk(all('higher_is_better' in v for v in snap.values()), "جهت بهبود مشخص است")

print()
print("═" * 60)
print("۳) verify_fix بدون job — باید ۴۰۴ بدهد")
print("═" * 60)
st, d = post('/api/verify_fix', {'job_id': 'job_ناموجود'})
chk(st == 404, f"پاسخ {st}")
chk('error' in d, f"پیام خطا: {d.get('error')}")

st, d = post('/api/analyze_verification', {'job_id': 'ناموجود'})
chk(st == 404, f"analyze_verification هم ۴۰۴ ({st})")

print()
print("═" * 60)
print("۴) امنیت — endpointهای جدید هم محافظت می‌شوند")
print("═" * 60)
for ep in ['/api/local_diagnose', '/api/health_snapshot',
           '/api/verify_fix', '/api/analyze_verification']:
    req = urllib.request.Request(
        BASE + ep, data=b'{}',
        headers={'Content-Type': 'application/json',
                 'Origin': 'https://evil.example.com'},
        method='POST')
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            code = r.status
    except urllib.error.HTTPError as e:
        code = e.code
    chk(code == 403, f"{ep} بدون مجوز رد شد ({code})")

print()
print("═" * 60)
print("۵) endpointهای قبلی نشکسته‌اند")
print("═" * 60)
for ep, data in [('/api/system_query', {'keys': ['os_info']}),
                 ('/api/db_stats', {}),
                 ('/api/providers', {})]:
    st, d = post(ep, data)
    chk(st == 200, f"{ep} → {st}")

print()
print("─" * 60)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
