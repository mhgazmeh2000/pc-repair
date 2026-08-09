# -*- coding: utf-8 -*-
"""تست زندهٔ تب Changes — چرخهٔ کامل استخراج تا بازگردانی"""
import json, os, shutil, sys, tempfile, urllib.error, urllib.request

import atexit, socket, subprocess, time as _t

def _free_port():
    _s = socket.socket(); _s.bind(('127.0.0.1', 0))
    _p = _s.getsockname()[1]; _s.close(); return _p

PORT = _free_port()
BASE = f"http://127.0.0.1:{PORT}"

# سرور را خود تست بالا می‌آورد — فرآیند پس‌زمینهٔ shell بین
# فراخوانی‌های ابزار حفظ نمی‌شود و تست را غیرقابل اتکا می‌کرد
_env = dict(os.environ, SERVER_PORT=str(PORT))
_srv = subprocess.Popen([sys.executable, 'backend_server.py'],
                        cwd='/home/user/pc-repair', env=_env,
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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

ROOT = tempfile.mkdtemp(prefix='chglive_')
os.makedirs(os.path.join(ROOT, 'src'))
def w(rel, t):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(t)
w('src/main.py', 'def main():\n    print("سلام")\n    return 0\n')
w('src/app.js', 'const a = 1;\n')

post('/api/ws_open', {'path': ROOT})

print("═" * 62)
print("۱) پیش‌نمایش تغییر روی فایل موجود")
print("═" * 62)
CH = {"id": "c1", "path": "src/main.py", "lang": "python",
      "new_content": 'def main():\n    print("سلام دنیا")\n    return 1\n'}
st, p = post('/api/ws_preview_change', {'change': CH})
chk(st == 200 and p.get('success'), f"پیش‌نمایش ({st})")
chk(not p.get('is_new'), "فایل موجود")
chk(p.get('added') == 2 and p.get('removed') == 2, f"+{p.get('added')} −{p.get('removed')}")
chk(any(r['type'] == 'add' for r in p.get('rows', [])), "سطر افزوده")
chk(any(r['type'] == 'del' for r in p.get('rows', [])), "سطر حذف‌شده")
chk(p.get('mtime'), "mtime برای تعارض")
MT = p.get('mtime')

print()
print("═" * 62)
print("۲) هیچ چیزی هنوز نوشته نشده")
print("═" * 62)
on_disk = open(os.path.join(ROOT, 'src', 'main.py'), encoding='utf-8').read()
chk('سلام دنیا' not in on_disk, "فایل دست‌نخورده — پیش‌نمایش نمی‌نویسد")

print()
print("═" * 62)
print("۳) اعمال با تأیید")
print("═" * 62)
st, d = post('/api/ws_apply_change', {'change': CH, 'mtime': MT})
chk(d.get('success'), "اعمال شد")
chk(d.get('backup'), f"پشتیبان: {d.get('backup')}")
on_disk = open(os.path.join(ROOT, 'src', 'main.py'), encoding='utf-8').read()
chk('سلام دنیا' in on_disk, "فایل واقعاً عوض شد")
BK = d.get('backup')

print()
print("═" * 62)
print("۴) بازگردانی")
print("═" * 62)
st, d = post('/api/ws_revert_change', {'path': 'src/main.py', 'backup': BK})
chk(d.get('success'), "بازگردانی موفق")
on_disk = open(os.path.join(ROOT, 'src', 'main.py'), encoding='utf-8').read()
chk('سلام دنیا' not in on_disk and 'return 0' in on_disk, "محتوای اصلی برگشت")

print()
print("═" * 62)
print("۵) تعارض mtime")
print("═" * 62)
st, d = post('/api/ws_apply_change', {'change': CH, 'mtime': MT - 9999})
chk(not d.get('success') and d.get('conflict'), "mtime قدیمی → تعارض")

print()
print("═" * 62)
print("۶) فایل جدید")
print("═" * 62)
NEW = {"id": "c2", "path": "src/created.py", "new_content": "x = 42\n"}
st, p = post('/api/ws_preview_change', {'change': NEW})
chk(p.get('is_new'), "فایل جدید تشخیص داده شد")
chk(p.get('removed') == 0, "چیزی حذف نمی‌شود")
st, d = post('/api/ws_apply_change', {'change': NEW})
chk(d.get('success') and d.get('created'), "فایل ساخته شد")
chk(os.path.exists(os.path.join(ROOT, 'src', 'created.py')), "روی دیسک هست")

print()
print("═" * 62)
print("۷) اعمال دسته‌ای")
print("═" * 62)
BATCH = [
    {"id": "b1", "path": "src/app.js", "new_content": "const a = 2;\n"},
    {"id": "b2", "path": "src/extra.py", "new_content": "y = 1\n"},
]
st, d = post('/api/ws_apply_batch', {'changes': BATCH})
chk(d.get('success'), "دسته موفق")
chk(len(d.get('applied', [])) == 2, "۲ فایل")
chk('✅' in d.get('summary_fa', ''), f"{d.get('summary_fa')}")

# یکی خراب
st, d = post('/api/ws_apply_batch', {'changes': [
    {"path": "../../../etc/evil", "new_content": "x"},
    {"path": "src/safe.py", "new_content": "ok = 1\n"}]})
chk(not d.get('success'), "success=False با یک خطا")
chk(len(d.get('applied', [])) == 1, "فایل سالم اعمال شد")
chk(len(d.get('failed', [])) == 1, "خطا گزارش شد")
chk(not os.path.exists('/etc/evil'), "فایل خارج از ریشه ساخته نشد")

print()
print("═" * 62)
print("۸) امنیت — مسیر خارج از پروژه")
print("═" * 62)
for bad in ['../../../etc/passwd', '/etc/hosts', '..\\..\\windows\\win.ini']:
    st, p = post('/api/ws_preview_change',
                 {'change': {'path': bad, 'new_content': 'x'}})
    st2, d2 = post('/api/ws_apply_change',
                   {'change': {'path': bad, 'new_content': 'x'}})
    chk(not d2.get('success'), f"«{bad[:30]}» نوشتن مسدود شد")

for ep in ['/api/ws_preview_change', '/api/ws_apply_change',
           '/api/ws_apply_batch', '/api/ws_revert_change']:
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
print("۹) استخراج تغییر از پاسخ AI (چرخهٔ ws_chat)")
print("═" * 62)
st, d = post('/api/ws_chat', {'question': 'تست', 'files': ['src/main.py']})
chk(st == 200, f"پاسخ {st}")
chk('changes' in d, "کلید changes در پاسخ هست")
chk(isinstance(d.get('changes'), list), "لیست است")

print()
print("═" * 62)
print("۱۰) سلامت بقیهٔ سیستم")
print("═" * 62)
for ep, data in [('/api/ws_tree', {}), ('/api/ws_read', {'path': 'src/main.py'}),
                 ('/api/local_diagnose', {'fast': True}),
                 ('/api/baseline_list', {}), ('/api/db_stats', {})]:
    st, _ = post(ep, data)
    chk(st == 200, f"{ep} → {st}")

shutil.rmtree(ROOT, ignore_errors=True)
print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
