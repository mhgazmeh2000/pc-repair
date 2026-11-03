# -*- mode: python ; coding: utf-8 -*-
"""
فایل پیکربندی PyInstaller برای PC Repair Toolbox Pro

ساخت:
    pyinstaller pc_toolbox_pro.spec --clean --noconfirm

خروجی:
    dist\\PC_Repair_Toolbox_Pro.exe
"""

block_cipher = None

a = Analysis(
    ['pc_toolbox_pro.py'],
    pathex=[],
    binaries=[],

    # ── فایل‌های داده ────────────────────────────────────────────────
    # این‌ها حتماً باید bundle شوند وگرنه exe صفحه سفید نشان می‌دهد.
    # کد با sys._MEIPASS آن‌ها را پیدا می‌کند.
    datas=[
        ('pc_toolbox_app.html', '.'),
        ('tools_data.json', '.'),
    ],

    # ── ماژول‌هایی که PyInstaller خودش پیدا نمی‌کند ──────────────────
    hiddenimports=[
        # ── ماژول‌های پایه ──
        'repair_runner',
        'command_guard',
        'gpu_inspector',
        'system_query',
        'database',
        'providers',
        'model_info',
        'attachments',
        'chat_memory',
        'system_inspector',
        'proxy',
        'backend_server',

        # ── امنیت و عیب‌یابی پیشرفته ──
        # بدون این‌ها exe با ImportError می‌افتد چون PyInstaller فقط
        # importهای فایل اصلی را دنبال می‌کند، نه importهای backend_server
        'security',           # توکن نشست، رمزنگاری کلید، ناشناس‌سازی
        'health_metrics',     # ۱۴ سنجهٔ عددی برای حلقهٔ بستهٔ تأیید
        'local_diagnosis',    # ۱۳ قاعدهٔ تشخیص محلی
        'baseline',           # خط پایه و تشخیص انحراف
        'restore_point',      # نقطهٔ بازگشت ویندوز
        'repair_history',     # حافظهٔ بین‌جلسه‌ای تعمیرها
        'event_catalog',      # فرهنگ ۵۱ رویداد ویندوز
        'defender_inspector', # وضعیت، تهدیدها و Exclusionهای Defender
        'defender_runner',    # اجرای کنترل‌شده اسکن Defender

        # ── تب توسعهٔ نرم‌افزار ──
        'workspace',          # مدیریت پوشهٔ پروژه
        'code_changes',       # استخراج و اعمال diff

        # ── وابستگی‌های خارجی ──
        'socks',              # PySocks — با import پویا صدا زده می‌شود
        'urllib3',
        'requests',
        'win32crypt',        # Windows DPAPI برای رمزنگاری API key
        'webview',           # رابط اصلی HTML در نسخه EXE
        'webview.platforms.edgechromium',
        'webview.platforms.winforms',

        # ── tkinter برای دیالوگ بومی انتخاب مسیر ──
        # backend_server._pick_path داخل تابع import می‌کند
        # (import tkinter / from tkinter import filedialog)؛ PyInstaller
        # importهای داخل تابع را دنبال نمی‌کند — بدون این‌ها دکمهٔ مرور
        # در exe با ImportError می‌افتد.
        'tkinter',
        'tkinter.filedialog',
        'tkinter.ttk',
        'tkinter.scrolledtext',

        # win32crypt (DPAPI) عمداً اینجا نیست: اگر pywin32 نصب نباشد
        # PyInstaller خطا می‌دهد. security.py خودش با try/except
        # واردش می‌کند و بدون آن هم کار می‌کند (کلید رمز نمی‌شود).
    ],

    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],

    # ── حذف ماژول‌های سنگین و بلااستفاده ─────────────────────────────
    # حجم exe را به‌طور قابل‌توجهی کم می‌کند
    excludes=[
        'matplotlib',
        'numpy',
        'pandas',
        'scipy',
        'PIL',
        'pytest',
        'notebook',
        'IPython',
    ],

    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='PC_Repair_Toolbox_Pro',

    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,

    # پنجره کنسول سیاه نمایش داده نشود
    console=False,

    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,

    # آیکون — اگر فایل icon.ico کنار پروژه گذاشتید، خط زیر را از حالت
    # کامنت خارج کنید
    # icon='icon.ico',

    # ── دسترسی Administrator ─────────────────────────────────────────
    # 'admin'  → همیشه با UAC بالا می‌آید (ابزارهای SFC/DISM بدون خطا کار می‌کنند)
    # None     → اجرای عادی، هر ابزار جدا UAC می‌خواهد
    uac_admin=True,
)
