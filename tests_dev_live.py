# -*- coding: utf-8 -*-
"""تست زندهٔ تب توسعه — endpointها با پروژهٔ واقعی"""
import json
import os, os, shutil, sys, tempfile, urllib.error, urllib.request

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
        with urllib.request.urlopen(req, timeout=90) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8') or '{}')

# پروژهٔ نمونه
ROOT = tempfile.mkdtemp(prefix='devlive_')
os.makedirs(os.path.join(ROOT, 'src'))
os.makedirs(os.path.join(ROOT, 'node_modules', 'x'))
def w(rel, t):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(t)
w('README.md', '# پروژه\nتوضیح')
w('src/main.py', 'def main():\n    return 1\n')
w('src/app.js', 'const a = 1;\n')
w('.gitignore', 'ignored.txt\n')
w('ignored.txt', 'محرمانه')
w('node_modules/x/i.js', 'x')

print("═" * 62)
print("۱) باز کردن پروژه")
print("═" * 62)
st, d = post('/api/ws_open', {'path': ROOT})
chk(st == 200 and d.get('success'), f"باز شد ({st})")
chk(d.get('file_count', 0) >= 4, f"{d.get('file_count')} فایل")
paths = [n['path'] for n in d.get('nodes', [])]
chk('src/main.py' in paths, "فایل تودرتو در درخت")
chk('ignored.txt' not in paths, "gitignore رعایت شد")
chk(not any('node_modules' in p for p in paths), "node_modules رد شد")
chk('lang' in [n for n in d['nodes'] if n['name'] == 'main.py'][0], "زبان تشخیص داده شد")

print()
print("═" * 62)
print("۲) امنیت — مسیرهای ممنوع")
print("═" * 62)
for bad in ['C:\\Windows', '/etc', '/']:
    st, d2 = post('/api/ws_open', {'path': bad})
    chk(not d2.get('success'), f"«{bad}» رد شد", d2.get('error', '')[:40])
post('/api/ws_open', {'path': ROOT})

print()
print("═" * 62)
print("۳) خواندن فایل")
print("═" * 62)
st, d = post('/api/ws_read', {'path': 'src/main.py'})
chk(d.get('success'), "خوانده شد")
chk('def main' in d.get('content', ''), "محتوا درست")
chk(d.get('lang') == 'python', "زبان python")
chk('mtime' in d, "mtime برگشت")
MTIME = d.get('mtime')

print()
print("═" * 62)
print("۴) امنیت — فرار از ریشه")
print("═" * 62)
for evil in ['../../../etc/passwd', '..\\..\\windows\\system32\\config\\sam',
             '/etc/passwd']:
    st, d2 = post('/api/ws_read', {'path': evil})
    chk(not d2.get('success'), f"«{evil[:32]}» مسدود شد", d2.get('error', '')[:35])
st, d2 = post('/api/ws_write', {'path': '../../../tmp/pwned.txt', 'content': 'x'})
chk(not d2.get('success'), "نوشتن خارج از ریشه مسدود شد")
chk(not os.path.exists('/tmp/pwned.txt'), "فایل ساخته نشد")

print()
print("═" * 62)
print("۵) نوشتن + پشتیبان + تعارض")
print("═" * 62)
st, d = post('/api/ws_write', {'path': 'src/main.py',
                               'content': 'def main():\n    return 2\n',
                               'mtime': MTIME})
chk(d.get('success'), "نوشته شد")
chk(d.get('backup'), f"پشتیبان: {d.get('backup')}")

st, d2 = post('/api/ws_write', {'path': 'src/main.py',
                                'content': 'x', 'mtime': MTIME - 500})
chk(not d2.get('success') and d2.get('conflict'), "mtime قدیمی → تعارض")

st, d3 = post('/api/ws_backups')
chk(d3.get('success') and len(d3.get('backups', [])) >= 1,
    f"{len(d3.get('backups', []))} پشتیبان")

bk = d3['backups'][0]['name']
st, d4 = post('/api/ws_restore', {'backup': bk, 'path': 'src/main.py'})
chk(d4.get('success'), "بازگردانی موفق")
st, d5 = post('/api/ws_read', {'path': 'src/main.py'})
chk('return 1' in d5.get('content', ''), "محتوای اصلی برگشت")

print()
print("═" * 62)
print("۶) جست‌وجو")
print("═" * 62)
st, d = post('/api/ws_search', {'query': 'def '})
chk(d.get('success'), f"{len(d.get('hits', []))} نتیجه")
chk(any('main.py' in h['path'] for h in d.get('hits', [])), "main.py پیدا شد")
chk(not any('ignored' in h['path'] for h in d.get('hits', [])), "فایل gitignore جست‌وجو نشد")

print()
print("═" * 62)
print("۷) درخت و اطلاعات پروژه")
print("═" * 62)
st, d = post('/api/ws_tree')
chk(d.get('success') and len(d.get('nodes', [])) > 0, "درخت مجدد")
st, d = post('/api/ws_info')
chk(d.get('success') and d.get('root'), f"اطلاعات: {d.get('name')}")

print()
print("═" * 62)
print("۸) چت کد — بدون کلید API باید پیام واضح بدهد")
print("═" * 62)
st, d = post('/api/ws_chat', {'question': 'این کد چه می‌کند؟',
                              'files': ['src/main.py']})
chk(st == 200, f"پاسخ {st}")
chk(d.get('error') or d.get('reply'), "پاسخ یا خطای مشخص")
if d.get('error'):
    chk('کلید API' in d['error'], f"پیام واضح: {d['error'][:50]}")
chk('context' in d, "اطلاعات زمینه برگشت")
if d.get('context'):
    chk(d['context']['included'] == ['src/main.py'], "فایل درست پیوست شد")
    chk(d['context']['chars'] > 0, f"{d['context']['chars']} کاراکتر")

st, d = post('/api/ws_chat', {'question': '', 'files': []})
chk(st == 400, f"سوال خالی رد شد ({st})")

print()
print("═" * 62)
print("۹) امنیت — endpointهای جدید محافظت می‌شوند")
print("═" * 62)
for ep in ['/api/ws_open', '/api/ws_read', '/api/ws_write', '/api/ws_tree',
           '/api/ws_search', '/api/ws_chat', '/api/ws_restore']:
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
print("۹/۵) ترمینال توسعه و پیش‌نمایش زنده")
print("═" * 62)

# ── ws_exec: ترمینال توسعه ──
st, d = post('/api/ws_exec', {'cmd': 'format c:'})
chk(not d.get('success') and 'مسدود' in str(d.get('error', '')),
     "ws_exec دستور مخرب را مسدود کرد")

st, d = post('/api/ws_exec', {'cmd': 'python --version'})
if d.get('needs_consent'):
    st2, d2 = post('/api/ws_exec', {'cmd': d.get('cmd', 'python --version'),
                                    'confirm': True})
    chk(d2.get('success'), "ws_exec با تأیید صریح اجرا شد")
    chk('Python' in str(d2.get('stdout', '')), "خروجی ws_exec بازگشت")
else:
    chk(d.get('success'), "ws_exec اجرا شد")

st, d = post('/api/ws_exec', {'cmd': ''})
chk(not d.get('success'), "ws_exec دستور خالی را رد کرد")

# ── پیش‌نمایش زنده (ws_preview + /dev-asset/) ──
_pvi = html.index('window.__TOOLBOX_PREVIEW_TOKEN__ = "')
_pv_start = _pvi + len('window.__TOOLBOX_PREVIEW_TOKEN__ = "')
PVT = html[_pv_start:html.index('"', _pv_start)]
w('preview_demo.html',
  '<!DOCTYPE html><html><head><title>pv</title></head><body><h1>hi</h1></body></html>')
_pv_q = urllib.parse.quote(PVT)


def _get(path):
    req = urllib.request.Request(BASE + path, method='GET')
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf-8', 'replace')

c, body = _get('/api/ws_preview?path=preview_demo.html&token=' + _pv_q)
chk(c == 200 and 'href="/dev-asset/"' in body,
     f"پیش‌نمایش با توکن → {c} (base تزریق شد)")
c, _ = _get('/api/ws_preview?path=preview_demo.html')
chk(c == 403, f"پیش‌نمایش بدون توکن → {c}")
c, _ = _get('/api/ws_preview?path=..%2Foutside&token=' + _pv_q)
chk(c == 400, f"مسیر فرار از پروژه رد شد → {c}")
c, body = _get('/dev-asset/preview_demo.html?token=' + _pv_q)
chk(c == 200, f"دارایی با توکن → {c}")
c, _ = _get('/dev-asset/preview_demo.html')
chk(c == 403, f"دارایی بدون توکن → {c}")

print()
print("═" * 62)
print("۱۰) بستن پروژه و سلامت بقیه")
print("═" * 62)
st, d = post('/api/ws_close')
chk(d.get('success'), "بسته شد")
st, d = post('/api/ws_read', {'path': 'src/main.py'})
chk(not d.get('success'), "خواندن بعد از بستن رد شد")

st, d = post('/api/personas')
keys = [p['key'] for p in d.get('personas', [])]
chk('coder' not in keys, f"نقش coder در نوار چت پنهان است: {keys}")
chk(len(keys) == 5, f"۵ نقش قابل مشاهده ({len(keys)})")

for ep, data in [('/api/local_diagnose', {'fast': True}),
                 ('/api/baseline_list', {}), ('/api/db_stats', {})]:
    st, _ = post(ep, data)
    chk(st == 200, f"{ep} → {st}")

shutil.rmtree(ROOT, ignore_errors=True)
print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
