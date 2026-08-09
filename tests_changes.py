# -*- coding: utf-8 -*-
"""تست موتور استخراج و اعمال تغییرات کد"""
import os, shutil, sys, tempfile
sys.path.insert(0, '/home/user/pc-repair')
import workspace as ws
import code_changes as cc

P = F = 0
def chk(c, m, e=''):
    global P, F
    if c: P += 1; print(f"  ✅ {m}")
    else: F += 1; print(f"  ❌ {m}" + (f"  → {e}" if e else ''))

ROOT = tempfile.mkdtemp(prefix='cc_')
os.makedirs(os.path.join(ROOT, 'src'))
def w(rel, t):
    p = os.path.join(ROOT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    open(p, 'w', encoding='utf-8').write(t)

w('src/main.py', 'def main():\n    print("سلام")\n    return 0\n')
w('src/app.js', 'const a = 1;\nconsole.log(a);\n')
w('README.md', '# پروژه\n')
ws.open_project(ROOT)
KNOWN = [n['path'] for n in ws.build_tree()['nodes'] if not n['dir']]

print("═" * 62)
print("۱) استخراج — نام فایل در سطر اول")
print("═" * 62)
reply = '''تابع را اصلاح می‌کنم:

```python
# فایل: src/main.py
def main():
    print("سلام دنیا")
    return 1
```

تمام شد.'''
r = cc.extract_changes(reply, KNOWN)
chk(r['success'] and len(r['changes']) == 1, f"۱ تغییر ({len(r['changes'])})")
c = r['changes'][0]
chk(c['path'] == 'src/main.py', f"مسیر: {c['path']}")
chk(c['confident'], "با اطمینان (نام صریح بود)")
chk('# فایل:' not in c['new_content'], "سطر راهنما حذف شد")
chk('سلام دنیا' in c['new_content'], "محتوا درست")
chk(c['exists_in_project'], "فایل موجود تشخیص داده شد")

# شکل‌های دیگر
for hint, lang in [('// File: src/app.js', 'javascript'),
                   ('# File: src/main.py', 'python'),
                   ('// src/app.js', 'javascript')]:
    rr = cc.extract_changes(f"```{lang}\n{hint}\nکد\n```", KNOWN)
    chk(len(rr['changes']) == 1 and rr['changes'][0]['confident'],
        f"شکل «{hint[:22]}» شناخته شد")

print()
print("═" * 62)
print("۲) استخراج — حدس از متن")
print("═" * 62)
reply2 = '''در فایل `src/app.js` این تغییر را بدهید:

```javascript
const a = 2;
console.log(a);
```'''
r = cc.extract_changes(reply2, KNOWN)
chk(len(r['changes']) == 1, "تغییر پیدا شد")
chk(r['changes'][0]['path'] == 'src/app.js', f"مسیر حدس زده شد: {r['changes'][0]['path']}")
chk(not r['changes'][0]['confident'], "پرچم confident=False (حدس بود)")

# نام تنها وقتی یکتاست
r = cc.extract_changes("فایل `README.md` را عوض کنید:\n\n```markdown\n# جدید\n```", KNOWN)
chk(len(r['changes']) == 1 and r['changes'][0]['path'] == 'README.md',
    "نام تنهای یکتا شناخته شد")

# بدون هیچ سرنخی → نادیده گرفته می‌شود
r = cc.extract_changes("این کد را ببینید:\n\n```python\nx = 1\n```", KNOWN)
chk(len(r['changes']) == 0, "بدون مقصد → تغییری استخراج نمی‌شود")

print()
print("═" * 62)
print("۳) بلوک‌های دستور نباید تغییر فایل شمرده شوند")
print("═" * 62)
reply3 = '''اول این را اجرا کنید:

```cmd
sfc /scannow
```

بعد فایل را عوض کنید:

```python
# فایل: src/main.py
def main(): pass
```'''
r = cc.extract_changes(reply3, KNOWN)
chk(len(r['changes']) == 1, f"فقط بلوک python ({len(r['changes'])})")
chk(r['changes'][0]['lang'] == 'python', "زبان درست")
chk('cmd' in r['note'], f"یادداشت: {r['note']}")

for bad in ['cmd', 'bat', 'powershell', 'shell', 'console', 'output']:
    rr = cc.extract_changes(f"```{bad}\nsome command\n```", KNOWN)
    chk(len(rr['changes']) == 0, f"زبان «{bad}» رد شد")

print()
print("═" * 62)
print("۴) چند تغییر در یک پاسخ")
print("═" * 62)
reply4 = '''دو فایل عوض می‌شوند:

```python
# فایل: src/main.py
def main():
    return 99
```

و همچنین:

```javascript
# فایل: src/app.js
const a = 42;
```'''
r = cc.extract_changes(reply4, KNOWN)
chk(len(r['changes']) == 2, f"۲ تغییر ({len(r['changes'])})")
chk([c['path'] for c in r['changes']] == ['src/main.py', 'src/app.js'], "ترتیب حفظ شد")
chk(len(set(c['id'] for c in r['changes'])) == 2, "شناسه‌های یکتا")

print()
print("═" * 62)
print("۵) پیش‌نمایش diff")
print("═" * 62)
ch = {"path": "src/main.py", "lang": "python",
      "new_content": 'def main():\n    print("سلام دنیا")\n    return 1\n'}
p = cc.build_preview(ch)
chk(p['success'], "پیش‌نمایش ساخته شد")
chk(not p['is_new'], "فایل موجود است")
chk(p['added'] == 2 and p['removed'] == 2, f"+{p['added']} −{p['removed']}")
chk(any(r['type'] == 'add' for r in p['rows']), "سطر افزوده")
chk(any(r['type'] == 'del' for r in p['rows']), "سطر حذف‌شده")
chk(any(r['type'] == 'same' for r in p['rows']), "سطر زمینه")
chk(p['mtime'] is not None, "mtime برای تشخیص تعارض")
adds = [r for r in p['rows'] if r['type'] == 'add']
chk(all(r['new_no'] and not r['old_no'] for r in adds), "شماره خط سطرهای افزوده")

print()
print("═" * 62)
print("۶) فایل جدید و محتوای یکسان")
print("═" * 62)
p = cc.build_preview({"path": "src/brand_new.py", "new_content": "x = 1\n"})
chk(p['success'] and p['is_new'], "فایل جدید تشخیص داده شد")
chk(p['added'] >= 1 and p['removed'] == 0, "همه‌چیز افزوده است")

cur = ws.read_file('src/main.py')['content']
p = cc.build_preview({"path": "src/main.py", "new_content": cur})
chk(p['identical'], "محتوای یکسان تشخیص داده شد")
chk('یکسان' in p['note'], "پیام فارسی")

p = cc.build_preview({"path": "../../../etc/passwd", "new_content": "x"})
chk(not p['success'], "مسیر خارج از ریشه رد شد")

print()
print("═" * 62)
print("۷) هشدار حذف بزرگ — محافظت از کد کاربر")
print("═" * 62)
w('src/big.py', '\n'.join(f'line_{i} = {i}' for i in range(40)) + '\n')
p = cc.build_preview({"path": "src/big.py", "new_content": "x = 1\n"})
chk(p['warning'], f"هشدار داده شد")
chk('حذف می‌کند' in p['warning'], "متن هشدار گویا")
print(f"     {p['warning'][:80]}")

# تغییر معمولی نباید هشدار بدهد
p2 = cc.build_preview({"path": "src/main.py",
                       "new_content": 'def main():\n    print("سلام")\n    return 5\n'})
chk(not p2['warning'], "تغییر کوچک هشدار ندارد")

print()
print("═" * 62)
print("۸) اعمال تغییر + پشتیبان")
print("═" * 62)
before = ws.read_file('src/main.py')['content']
ch = {"path": "src/main.py",
      "new_content": 'def main():\n    return 777\n'}
r = cc.apply_change(ch)
chk(r['success'], "اعمال شد")
chk(r.get('backup'), f"پشتیبان: {r.get('backup')}")
chk('777' in ws.read_file('src/main.py')['content'], "فایل واقعاً عوض شد")

rv = cc.revert_change('src/main.py', r['backup'])
chk(rv['success'], "بازگردانی موفق")
chk(ws.read_file('src/main.py')['content'] == before, "محتوای اصلی دقیقاً برگشت")

print()
print("═" * 62)
print("۹) تشخیص تعارض هنگام اعمال")
print("═" * 62)
info = ws.read_file('src/app.js')
r = cc.apply_change({"path": "src/app.js", "new_content": "const b = 9;\n"},
                    expected_mtime=info['mtime'])
chk(r['success'], "mtime درست → اعمال شد")
r = cc.apply_change({"path": "src/app.js", "new_content": "const c = 0;\n"},
                    expected_mtime=info['mtime'] - 999)
chk(not r['success'] and r.get('conflict'), "mtime قدیمی → تعارض")

print()
print("═" * 62)
print("۱۰) اعمال دسته‌ای")
print("═" * 62)
batch = [
    {"path": "src/main.py", "new_content": "def main():\n    return 1\n"},
    {"path": "src/newfile.py", "new_content": "y = 2\n"},
]
r = cc.apply_batch(batch)
chk(r['success'], "دسته موفق")
chk(len(r['applied']) == 2, f"۲ فایل اعمال شد")
chk(any(a['created'] for a in r['applied']), "فایل جدید علامت خورد")
chk('✅' in r['summary_fa'], f"خلاصه: {r['summary_fa']}")

# یکی خراب — بقیه باید ادامه دهند
batch2 = [
    {"path": "../../../etc/evil", "new_content": "x"},
    {"path": "src/ok.py", "new_content": "z = 3\n"},
]
r = cc.apply_batch(batch2)
chk(not r['success'], "دسته با یک خطا success=False")
chk(len(r['applied']) == 1, "فایل سالم اعمال شد")
chk(len(r['failed']) == 1, "فایل خراب گزارش شد")
chk('⚠️' in r['summary_fa'], f"خلاصهٔ جزئی: {r['summary_fa']}")
chk(os.path.exists(os.path.join(ROOT, 'src', 'ok.py')), "فایل سالم واقعاً ساخته شد")
chk(not os.path.exists('/etc/evil'), "فایل خارج از ریشه ساخته نشد")

print()
print("═" * 62)
print("۱۱) حالت‌های مرزی")
print("═" * 62)
chk(cc.extract_changes('', KNOWN)['changes'] == [], "متن خالی")
chk(cc.extract_changes(None, KNOWN)['changes'] == [], "None")
chk(cc.extract_changes('بدون هیچ بلوک کدی', KNOWN)['changes'] == [], "بدون بلوک")
r = cc.extract_changes("```python\n# فایل: a.py\n```", KNOWN)
chk(len(r['changes']) == 0, "بلوک خالی نادیده گرفته شد")
r = cc.apply_change({}, None)
chk(not r['success'], "تغییر بدون مسیر رد شد")
r = cc.apply_batch([])
chk('تغییری' in r['summary_fa'], "دستهٔ خالی پیام مناسب")

# سقف تعداد
many = "\n".join(f"```python\n# فایل: f{i}.py\nx={i}\n```" for i in range(30))
r = cc.extract_changes(many, KNOWN)
chk(len(r['changes']) <= cc.MAX_CHANGES, f"سقف {cc.MAX_CHANGES} رعایت شد ({len(r['changes'])})")

print()
print("═" * 62)
print("۱۲) پیش‌نمایش روی فایل بزرگ — بدون آوردن کل فایل به حافظه")
print("═" * 62)
big_path = os.path.join(ROOT, 'src', 'bigfile.txt')
os.makedirs(os.path.dirname(big_path), exist_ok=True)
with open(big_path, 'w', encoding='utf-8') as f:
    # فایلی چند برابر بزرگ‌تر از سقف پیش‌نمایش diff (۵۱۲KB) بساز
    f.write("line0\n" * (cc.PREVIEW_MAX_KB * 1500))
big_size = os.path.getsize(big_path)
chk(big_size > cc.PREVIEW_MAX_KB * 1024,
    f"فایل تست بزرگ است ({big_size // 1024}KB > {cc.PREVIEW_MAX_KB}KB)")

pb = cc.build_preview({"path": "src/bigfile.txt",
                        "new_content": "line0\nchanged\n",
                        "lang": "text"})
chk(pb.get('success'), "پیش‌نمایش فایل بزرگ ساخته شد")
chk(pb.get('file_truncated'), "پرچم file_truncated=True برای فایل بزرگ")
chk(pb.get('file_size') == big_size, "حجم فایل کامل گزارش شد",
    f"{pb.get('file_size')} != {big_size}")
chk(len(pb.get('rows', [])) <= cc.MAX_DIFF_LINES,
    "diff فقط روی ابتدای فایل ساخته شد (نه کل ۵MB)",
    f"rows={len(pb.get('rows', []))} > {cc.MAX_DIFF_LINES}")
chk(pb.get('truncated'),
    "پرچم truncated برای diff بریده‌شده ست شده")
# مبادا read_file بدون max_kb صدا زده شود — مستقیم بررسی کن
cur = ws.read_file('src/bigfile.txt')
chk(not cur.get('truncated'), "خواندن کامل بدون max_kb هنوز ممکن است")
cur_limited = ws.read_file('src/bigfile.txt', max_kb=cc.PREVIEW_MAX_KB)
chk(cur_limited.get('truncated'), "read_file با max_kb پرچم truncated می‌دهد")

shutil.rmtree(ROOT, ignore_errors=True)
print()
print("─" * 62)
print(f"نتیجه: {P} موفق، {F} ناموفق")
sys.exit(1 if F else 0)
