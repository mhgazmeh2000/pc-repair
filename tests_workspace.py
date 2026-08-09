# -*- coding: utf-8 -*-
"""تست ماژول workspace — با تمرکز روی امنیت مسیر"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, '/home/user/pc-repair')
import workspace as ws

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

# ── ساخت پروژهٔ نمونه ──
ROOT = tempfile.mkdtemp(prefix='ws_test_')
os.makedirs(os.path.join(ROOT, 'src', 'utils'), exist_ok=True)
os.makedirs(os.path.join(ROOT, 'node_modules', 'lodash'), exist_ok=True)
os.makedirs(os.path.join(ROOT, '.git'), exist_ok=True)
os.makedirs(os.path.join(ROOT, 'dist'), exist_ok=True)

def w(rel, txt):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f: f.write(txt)

w('README.md', '# پروژهٔ تست\nتوضیح فارسی')
w('src/main.py', 'def main():\n    print("سلام")\n    return 0\n')
w('src/utils/helper.py', 'def add(a, b):\n    return a + b\n')
w('src/app.js', 'const x = 1;\nconsole.log(x);\n')
w('.gitignore', 'secret.txt\n*.tmp\nlogs/\n')
w('secret.txt', 'رمز محرمانه')
w('build.tmp', 'موقت')
w('node_modules/lodash/index.js', 'module.exports = {};')
w('dist/bundle.js', 'bundled')
w('logs/app.log', 'log line')
# فایل باینری
with open(os.path.join(ROOT, 'icon.bin'), 'wb') as f:
    f.write(b'\x00\x01\x02\x03' * 100)

print("═" * 62)
print("۱) باز کردن پروژه")
print("═" * 62)
r = ws.open_project(ROOT)
chk(r['success'], "پروژه باز شد")
chk(r['has_git'], "وجود .git تشخیص داده شد")
chk(r['gitignore_rules'] == 3, f"۳ قانون gitignore خوانده شد ({r['gitignore_rules']})")
chk(r['writable'], "قابل نوشتن")
chk(ws.current_root() == os.path.realpath(ROOT), "ریشه ثبت شد")

print()
print("═" * 62)
print("۲) امنیت — پوشه‌های ممنوع")
print("═" * 62)
for bad in ['C:\\Windows', 'C:\\Program Files', '/etc', '/usr', '/']:
    r = ws.open_project(bad)
    chk(not r['success'], f"«{bad}» رد شد", r.get('error', '')[:40])
r = ws.open_project('')
chk(not r['success'], "مسیر خالی رد شد")
r = ws.open_project('/مسیر/که/نیست')
chk(not r['success'], "مسیر ناموجود رد شد")

ws.open_project(ROOT)   # بازگشت به پروژهٔ تست

print()
print("═" * 62)
print("۳) درخت فایل — احترام به gitignore و پوشه‌های ساخته‌شده")
print("═" * 62)
t = ws.build_tree()
paths = [n['path'] for n in t['nodes']]
chk(t['success'], f"درخت ساخته شد ({t['file_count']} فایل، {t['dir_count']} پوشه)")
chk('src/main.py' in paths, "فایل عادی هست")
chk('src/utils/helper.py' in paths, "فایل تودرتو هست")
chk('secret.txt' not in paths, "فایل gitignore شده پنهان است")
chk('build.tmp' not in paths, "الگوی *.tmp اعمال شد")
chk(not any('logs/' in p for p in paths), "پوشهٔ logs/ در gitignore پنهان شد")
chk(not any('node_modules' in p for p in paths), "node_modules رد شد")
chk(not any(p.startswith('.git/') for p in paths), ".git رد شد")
chk(not any(p.startswith('dist') for p in paths), "dist رد شد")

md = next((n for n in t['nodes'] if n['name'] == 'README.md'), None)
chk(md and md['lang'] == 'markdown', "زبان markdown تشخیص داده شد")
py = next((n for n in t['nodes'] if n['name'] == 'main.py'), None)
chk(py and py['lang'] == 'python' and py['text'], "زبان python + متنی بودن")
b = next((n for n in t['nodes'] if n['name'] == 'icon.bin'), None)
chk(b and not b['text'], "فایل .bin غیرمتنی علامت خورد")

print()
print("═" * 62)
print("۴) امنیت — فرار از ریشه (path traversal)")
print("═" * 62)
for evil in ['../../../etc/passwd', '..\\..\\..\\windows\\system32\\config\\sam',
             '/etc/passwd', 'src/../../../../etc/hosts', '....//....//etc/passwd']:
    r = ws.read_file(evil)
    # هر سه پیام یعنی «مسدود شد»: خارج از ریشه، مسیر مطلق، یا ناموجود
    blocked = (not r['success']) and any(
        k in r.get('error', '')
        for k in ('خارج از پوشه', 'مسیر باید نسبت', 'وجود ندارد'))
    chk(blocked, f"«{evil[:38]}» مسدود شد", r.get('error', '')[:40])

r = ws.write_file('../../../tmp/hacked.txt', 'نفوذ')
chk(not r['success'], "نوشتن خارج از ریشه مسدود شد")
chk(not os.path.exists('/tmp/hacked.txt'), "فایل واقعاً ساخته نشد")

print()
print("═" * 62)
print("۵) خواندن فایل")
print("═" * 62)
r = ws.read_file('src/main.py')
chk(r['success'], "خوانده شد")
chk('سلام' in r['content'], "محتوای فارسی درست")
chk(r['lang'] == 'python', "زبان درست")
chk(r['lines'] == 4, f"شمارش خط ({r['lines']})")
chk('mtime' in r, "زمان تغییر برگشت")

r = ws.read_file('icon.bin')
chk(not r['success'] and 'باینری' in r['error'], "فایل باینری رد شد")
r = ws.read_file('nope.py')
chk(not r['success'], "فایل ناموجود رد شد")
r = ws.read_file('src')
chk(not r['success'] and 'پوشه' in r['error'], "پوشه به‌جای فایل رد شد")

# فایل‌های بزرگ دیگر بلاک نمی‌شوند — باید باز شوند (با پرچم large اگر خیلی بزرگ‌اند)
big = os.path.join(ROOT, 'big.py')
with open(big, 'w') as f: f.write('x = 1\n' * 120000)
r = ws.read_file('big.py')
chk(r['success'], "فایل بزرگ باز می‌شود")
os.remove(big)

huge = os.path.join(ROOT, 'huge.py')
with open(huge, 'w') as f: f.write('x = 1\n' * 1600000)  # ~۱۱ مگابایت
r = ws.read_file('huge.py')
chk(r['success'] and r.get('large'), "پرچم large برای فایل خیلی بزرگ")
# با max_kb فقط ابتدا خوانده می‌شود و truncated پرچم می‌خورد
r2 = ws.read_file('huge.py', max_kb=64)
chk(r2['success'] and r2.get('truncated'), "با max_kb پرچم truncated می‌آید")
chk(len(r2['content']) < 128 * 1024, "محتوا محدود شده است")
os.remove(huge)

print()
print("═" * 62)
print("۶) نوشتن + پشتیبان خودکار")
print("═" * 62)
orig = ws.read_file('src/main.py')['content']
r = ws.write_file('src/main.py', 'def main():\n    print("جدید")\n')
chk(r['success'], "نوشته شد")
chk(r['backup'], f"پشتیبان ساخته شد: {r.get('backup')}")
chk(not r['created'], "فایل موجود بود، نه جدید")
chk(ws.read_file('src/main.py')['content'].find('جدید') != -1, "محتوا عوض شد")

bl = ws.list_backups()
chk(bl['success'] and len(bl['backups']) >= 1, f"فهرست پشتیبان ({len(bl['backups'])})")

rr = ws.restore_backup(bl['backups'][0]['name'], 'src/main.py')
chk(rr['success'], "بازگردانی موفق")
chk('سلام' in ws.read_file('src/main.py')['content'], "محتوای اصلی برگشت")

r = ws.write_file('src/new_file.py', '# جدید\n')
chk(r['success'] and r['created'], "فایل جدید ساخته شد")
chk(r['backup'] is None, "برای فایل جدید پشتیبان لازم نیست")

print()
print("═" * 62)
print("۷) تشخیص تعارض mtime")
print("═" * 62)
info = ws.read_file('src/app.js')
r = ws.write_file('src/app.js', 'const y = 2;\n', expected_mtime=info['mtime'])
chk(r['success'], "نوشتن با mtime درست موفق")
r = ws.write_file('src/app.js', 'const z = 3;\n', expected_mtime=info['mtime'] - 500)
chk(not r['success'] and r.get('conflict'), "mtime قدیمی → تعارض تشخیص داده شد")
chk('بیرون از برنامه تغییر کرده' in r['error'], "پیام فارسی گویا")

print()
print("═" * 62)
print("۸) جست‌وجو در فایل‌ها")
print("═" * 62)
r = ws.search_in_files('def ')
chk(r['success'], f"جست‌وجو انجام شد ({len(r['hits'])} نتیجه)")
chk(any('main.py' in h['path'] for h in r['hits']), "main.py پیدا شد")
chk(all('line' in h and 'text' in h for h in r['hits']), "شماره خط و متن دارد")
chk(not any('secret' in h['path'] for h in r['hits']), "فایل gitignore جست‌وجو نشد")

r = ws.search_in_files('a')
chk(not r['success'], "عبارت خیلی کوتاه رد شد")
r = ws.search_in_files('عبارتی_که_نیست_۱۲۳')
chk(r['success'] and len(r['hits']) == 0, "عبارت ناموجود → صفر نتیجه")

print()
print("═" * 62)
print("۹) ساخت زمینه برای AI")
print("═" * 62)
c = ws.build_context(['src/main.py', 'src/utils/helper.py'])
chk(c['success'], "زمینه ساخته شد")
chk(len(c['included']) == 2, "دو فایل شامل شد")
chk('```python' in c['text'], "بلوک کد با زبان")
chk('### فایل: src/main.py' in c['text'], "سرصفحهٔ فایل")
chk(c['chars'] > 0, f"{c['chars']} کاراکتر")

c2 = ws.build_context(['src/main.py'], max_chars=50)
chk(len(c2['skipped']) == 1, "سقف حجم رعایت شد")
chk('سقف حجم' in c2['skipped'][0]['reason'], "دلیل رد شدن گزارش شد")

c3 = ws.build_context(['nope.py'])
chk(len(c3['skipped']) == 1, "فایل ناموجود در skipped")

print()
print("═" * 62)
print("۹ب) ضمیمه‌کردن پوشه — کل پروژه و زیرپوشه")
print("═" * 62)
# کل پروژه: gitignore و باینری باید حذف شوند
whole = ws.build_context(['.'])
chk(whole['success'], "کل پروژه باز شد")
inc = whole['included']
chk('src/main.py' in inc and 'src/utils/helper.py' in inc, "فایل‌های src شامل شدند")
chk(not any('secret.txt' in i for i in inc), "secret.txt (gitignore) حذف شد")
chk(not any('node_modules' in i for i in inc), "node_modules (gitignore) حذف شد")
chk(not any('dist' in i for i in inc), "dist/ حذف شد")
chk(not any('icon.bin' in i for i in inc), "فایل باینری حذف شد")
chk(len(whole['folders']) == 1, "آمار یک پوشه (کل پروژه)")
chk(whole['folders'][0]['name'] == os.path.basename(ROOT), "نام کل پروژه = نام ریشه")

# زیرپوشه: مسیرها باید نسبت به ریشهٔ پروژه باشند
sub = ws.build_context(['src'])
chk(sub['success'], "زیرپوشهٔ src باز شد")
sub_inc = sub['included']
chk('src/utils/helper.py' in sub_inc, "مسیر تو در تو درست است (src/utils/helper.py)")
chk(not any(i.startswith('utils/') for i in sub_inc), "مسیر بدون پیشوند src وجود ندارد")
chk(any(f['path'] == 'src' for f in sub['folders']), "آمار زیرپوشه برگردانده شد")

# پوشهٔ همیشه‌ردشده: حتی ضمیمهٔ مستقیم هم نادیده گرفته می‌شود
nm = ws.build_context(['node_modules'])
chk(len(nm['included']) == 0, "node_modules → صفر فایل")
chk(not any(f['path'] == 'node_modules' for f in nm['folders']), "node_modules در آمار پوشه‌ها نیست")
chk(any('node_modules' in s['path'] for s in nm['skipped']), "دلیل رد شدن در skipped گزارش شد")

# پوشه‌های هم‌پوشان («.» + «src») نباید فایلی را دوبار بفرستند
over = ws.build_context(['.', 'src'])
chk(len(over['included']) == len(set(over['included'])), "هم‌پوشانی پوشه‌ها فایل تکراری نمی‌سازد")
chk(over['included'].count('src/main.py') == 1, "src/main.py فقط یک‌بار می‌آید")
# آمار «.» = همهٔ فایل‌های شامل‌شده
whole_meta = next(f for f in whole['folders'] if f['path'] == '.')
chk(whole_meta['files'] == len(whole['included']), "آمار کل پروژه = همهٔ فایل‌های شامل‌شده")

print()
print("═" * 62)
print("۱۰) خلاصهٔ پروژه برای AI")
print("═" * 62)
s = ws.project_summary()
chk('نام پروژه' in s, "نام پروژه")
chk('.py' in s, "پسوندهای غالب")
chk('src' in s, "پوشه‌های سطح اول")
chk('README.md' in s, "فایل‌های ریشه")

print()
print("═" * 62)
print("۱۱) بستن پروژه")
print("═" * 62)
ws.close_project()
chk(ws.current_root() is None, "ریشه پاک شد")
r = ws.read_file('src/main.py')
chk(not r['success'] and 'باز نشده' in r['error'], "خواندن بعد از بستن رد شد")
r = ws.build_tree()
chk(not r['success'], "درخت بعد از بستن رد شد")

shutil.rmtree(ROOT, ignore_errors=True)
print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
