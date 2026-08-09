# -*- coding: utf-8 -*-
"""
فرهنگ رویدادهای ویندوز — تبدیل کد خام به معنی و راه‌حل

مسئله‌ای که حل می‌کند
─────────────────────
Event Viewer چیزی مثل این می‌دهد:

    Event ID 41, Kernel-Power
    The system has rebooted without cleanly shutting down first.

کاربر فارسی‌زبان از این هیچ نمی‌فهمد، و AI هم باید هر بار توضیحش را
از نو تولید کند — یعنی توکن مصرف کند برای چیزی که ثابت است.

اینجا ۵۰ رویداد پرتکرار با توضیح فارسی، شدت، علت‌های محتمل و مراحل
تعمیر پیشنهادی نگاشت شده‌اند. رایگان، آفلاین، قطعی.

ساختار هر مدخل
──────────────
    title       عنوان کوتاه فارسی
    severity    critical | warning | info
    meaning     توضیح ساده — چه اتفاقی افتاده
    causes      علت‌های محتمل، به ترتیب احتمال
    steps       کلید مراحل REPAIR_STEPS برای رفع
    tool_ids    شناسهٔ ابزارهای مرتبط در tools_data.json
"""

import re

CRITICAL = "critical"
WARNING = "warning"
INFO = "info"

_SEV_FA = {CRITICAL: "بحرانی", WARNING: "هشدار", INFO: "اطلاع"}


# کلید: (Event ID، بخشی از نام Provider یا None برای هر Provider)
CATALOG = {
    # ═══════════ برق و خاموشی ناگهانی ═══════════
    (41, "Kernel-Power"): {
        "title": "خاموشی ناگهانی بدون Shutdown صحیح",
        "severity": CRITICAL,
        "meaning": "سیستم بدون خاموش شدن درست ری‌استارت شده — یعنی برق قطع "
                   "شده، دکمهٔ پاور نگه داشته شده، یا سیستم کرش کرده است.",
        "causes": ["منبع تغذیه ناکافی یا معیوب",
                   "داغ شدن بیش از حد CPU یا GPU",
                   "رم معیوب",
                   "درایور ناسازگار که باعث کرش شده"],
        "steps": ["chkdsk"],
        "tool_ids": [14, 43],
    },
    (6008, None): {
        "title": "خاموشی غیرمنتظرهٔ قبلی",
        "severity": WARNING,
        "meaning": "ویندوز تشخیص داده که آخرین بار درست خاموش نشده است.",
        "causes": ["قطع برق", "کرش سیستم", "خاموش کردن اجباری"],
        "steps": [],
        "tool_ids": [14],
    },
    (6005, None): {
        "title": "شروع به کار سرویس ثبت رویداد",
        "severity": INFO,
        "meaning": "ویندوز بالا آمده است. این رویداد طبیعی است و "
                   "نشانهٔ زمان روشن شدن سیستم است.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },
    (6006, None): {
        "title": "خاموش شدن صحیح سیستم",
        "severity": INFO,
        "meaning": "ویندوز به‌درستی خاموش شده است. طبیعی است.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },
    (6013, None): {
        "title": "مدت روشن بودن سیستم",
        "severity": INFO,
        "meaning": "گزارش روزانهٔ مدت روشن بودن. طبیعی است.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },

    # ═══════════ صفحهٔ آبی و کرش ═══════════
    (1001, "BugCheck"): {
        "title": "صفحهٔ آبی مرگ (BSOD)",
        "severity": CRITICAL,
        "meaning": "سیستم با خطای بحرانی متوقف شده و فایل dump ساخته است. "
                   "کد توقف در متن رویداد، علت دقیق را نشان می‌دهد.",
        "causes": ["درایور معیوب یا ناسازگار",
                   "رم خراب",
                   "فایل سیستمی آسیب‌دیده",
                   "مشکل سخت‌افزاری"],
        "steps": ["sfc", "dism_restore"],
        "tool_ids": [12, 14],
    },
    (1000, "Application Error"): {
        "title": "کرش یک برنامه",
        "severity": WARNING,
        "meaning": "یک برنامه به‌طور غیرمنتظره بسته شده است. نام برنامه و "
                   "ماژول مقصر در متن رویداد آمده.",
        "causes": ["باگ در خود برنامه",
                   "کتابخانهٔ سیستمی آسیب‌دیده",
                   "ناسازگاری با نسخهٔ ویندوز",
                   "کمبود حافظه"],
        "steps": ["sfc"],
        "tool_ids": [1, 4],
    },
    (1002, "Application Hang"): {
        "title": "قفل شدن برنامه",
        "severity": WARNING,
        "meaning": "برنامه پاسخ نمی‌داده و ویندوز آن را بسته است.",
        "causes": ["عملیات طولانی روی رشتهٔ اصلی برنامه",
                   "کندی دیسک",
                   "کمبود حافظه"],
        "steps": [],
        "tool_ids": [23, 25],
    },
    (1005, None): {
        "title": "خطای دسترسی به حافظه",
        "severity": CRITICAL,
        "meaning": "ویندوز نتوانسته به بخشی از حافظه دسترسی پیدا کند.",
        "causes": ["رم معیوب", "درایور خراب"],
        "steps": [],
        "tool_ids": [23],
    },

    # ═══════════ دیسک و فایل‌سیستم ═══════════
    (7, "disk"): {
        "title": "خطای بلوک بد روی دیسک",
        "severity": CRITICAL,
        "meaning": "دیسک بلوک معیوب گزارش کرده است. این نشانهٔ جدی خرابی "
                   "فیزیکی دیسک است.",
        "causes": ["فرسودگی دیسک", "کابل SATA معیوب", "قطع برق حین نوشتن"],
        "steps": ["chkdsk"],
        "tool_ids": [15, 27],
    },
    (11, "disk"): {
        "title": "خطای کنترلر دیسک",
        "severity": CRITICAL,
        "meaning": "کنترلر دیسک خطای سخت‌افزاری گزارش کرده است.",
        "causes": ["کابل معیوب یا شل", "پورت SATA خراب", "دیسک در حال مرگ"],
        "steps": ["chkdsk"],
        "tool_ids": [15],
    },
    (51, "disk"): {
        "title": "خطای صفحه‌بندی هنگام نوشتن روی دیسک",
        "severity": WARNING,
        "meaning": "ویندوز هنگام کار با حافظهٔ مجازی به خطا خورده است.",
        "causes": ["بخش‌های معیوب دیسک", "دیسک پر", "کابل معیوب"],
        "steps": ["chkdsk", "temp_clean"],
        "tool_ids": [15, 38],
    },
    (55, "Ntfs"): {
        "title": "خرابی ساختار فایل‌سیستم NTFS",
        "severity": CRITICAL,
        "meaning": "ساختار فایل‌سیستم آسیب دیده و نیاز به بررسی با CHKDSK دارد.",
        "causes": ["خاموشی ناگهانی", "بخش معیوب دیسک", "قطع اتصال حین نوشتن"],
        "steps": ["chkdsk"],
        "tool_ids": [15],
    },
    (98, "Ntfs"): {
        "title": "خطای فراداده NTFS",
        "severity": WARNING,
        "meaning": "ویندوز مشکلی در فرادادهٔ فایل‌سیستم پیدا کرده است.",
        "causes": ["خرابی جزئی فایل‌سیستم"],
        "steps": ["chkdsk"],
        "tool_ids": [15],
    },
    (129, None): {
        "title": "بازنشانی کنترلر ذخیره‌سازی",
        "severity": WARNING,
        "meaning": "کنترلر دیسک به دستوری پاسخ نداده و مجبور به بازنشانی شده. "
                   "معمولاً باعث فریز چندثانیه‌ای سیستم می‌شود.",
        "causes": ["درایور SATA/NVMe قدیمی", "مشکل تغذیه", "دیسک در حال خرابی"],
        "steps": [],
        "tool_ids": [12, 15],
    },
    (153, None): {
        "title": "لغو درخواست ورودی/خروجی دیسک",
        "severity": WARNING,
        "meaning": "درخواستی به دیسک بیش از حد طول کشیده و لغو شده است.",
        "causes": ["دیسک کند یا در حال خرابی", "بار زیاد روی دیسک"],
        "steps": [],
        "tool_ids": [15],
    },

    # ═══════════ سرویس‌ها ═══════════
    (7000, "Service Control Manager"): {
        "title": "سرویس شروع نشد",
        "severity": WARNING,
        "meaning": "یکی از سرویس‌های ویندوز نتوانسته اجرا شود.",
        "causes": ["فایل سرویس حذف یا خراب شده",
                   "وابستگی سرویس اجرا نشده",
                   "دسترسی ناکافی"],
        "steps": ["sfc"],
        "tool_ids": [13],
    },
    (7001, "Service Control Manager"): {
        "title": "سرویس به‌خاطر وابستگی اجرا نشد",
        "severity": WARNING,
        "meaning": "سرویس منتظر سرویس دیگری بوده که آن هم اجرا نشده است.",
        "causes": ["زنجیرهٔ وابستگی شکسته", "سرویس پایه غیرفعال شده"],
        "steps": [],
        "tool_ids": [13],
    },
    (7009, "Service Control Manager"): {
        "title": "مهلت اتصال به سرویس تمام شد",
        "severity": WARNING,
        "meaning": "سرویس در زمان مقرر پاسخ نداده است.",
        "causes": ["کندی سیستم هنگام بوت", "دیسک کند", "بار زیاد استارتاپ"],
        "steps": [],
        "tool_ids": [13, 24],
    },
    (7011, None): {
        "title": "مهلت انتظار سرویس",
        "severity": WARNING,
        "meaning": "سرویس در مهلت مقرر به فرمان پاسخ نداده است.",
        "causes": ["کندی دیسک", "قفل شدن سرویس"],
        "steps": [],
        "tool_ids": [13],
    },
    (7023, None): {
        "title": "سرویس با خطا متوقف شد",
        "severity": WARNING,
        "meaning": "سرویس اجرا شده ولی با خطا خاتمه یافته است.",
        "causes": ["پیکربندی نادرست", "فایل‌های خراب"],
        "steps": ["sfc"],
        "tool_ids": [13],
    },
    (7031, None): {
        "title": "سرویس به‌طور غیرمنتظره متوقف شد",
        "severity": WARNING,
        "meaning": "سرویس کرش کرده و ویندوز می‌خواهد دوباره اجرایش کند.",
        "causes": ["باگ در سرویس", "فایل‌های آسیب‌دیده"],
        "steps": ["sfc"],
        "tool_ids": [13],
    },
    (7034, None): {
        "title": "کرش مکرر سرویس",
        "severity": CRITICAL,
        "meaning": "سرویس چندین بار پشت‌سرهم کرش کرده است.",
        "causes": ["فایل سرویس خراب", "تداخل با نرم‌افزار دیگر"],
        "steps": ["sfc", "dism_restore"],
        "tool_ids": [13],
    },

    # ═══════════ درایور ═══════════
    (219, "Kernel-PnP"): {
        "title": "بارگذاری درایور ناموفق",
        "severity": WARNING,
        "meaning": "ویندوز نتوانسته درایور یک دستگاه را بارگذاری کند.",
        "causes": ["درایور ناسازگار", "فایل درایور خراب", "دستگاه معیوب"],
        "steps": [],
        "tool_ids": [12, 44],
    },
    (10110, None): {
        "title": "مشکل راه‌اندازی دستگاه",
        "severity": WARNING,
        "meaning": "دستگاهی درست راه‌اندازی نشده است.",
        "causes": ["درایور نامناسب", "تداخل منابع سخت‌افزاری"],
        "steps": [],
        "tool_ids": [12],
    },
    (4101, "Display"): {
        "title": "بازیابی درایور گرافیک (TDR)",
        "severity": WARNING,
        "meaning": "درایور کارت گرافیک پاسخ نداده و ویندوز آن را بازنشانی "
                   "کرده است. معمولاً صفحه یک لحظه سیاه می‌شود.",
        "causes": ["درایور گرافیک ناپایدار",
                   "داغ شدن کارت گرافیک",
                   "اورکلاک ناپایدار",
                   "منبع تغذیه ناکافی"],
        "steps": [],
        "tool_ids": [43, 44, 47, 48],
    },
    (14, "nvlddmkm"): {
        "title": "خطای درایور NVIDIA",
        "severity": WARNING,
        "meaning": "درایور کارت گرافیک NVIDIA خطا گزارش کرده است.",
        "causes": ["نسخهٔ درایور ناسازگار", "داغ شدن", "اورکلاک"],
        "steps": [],
        "tool_ids": [44, 47],
    },

    # ═══════════ شبکه ═══════════
    (1014, "DNS Client Events"): {
        "title": "پاسخ ندادن سرور DNS",
        "severity": WARNING,
        "meaning": "درخواست تبدیل نام دامنه بی‌پاسخ مانده است.",
        "causes": ["DNS نامعتبر در تنظیمات", "قطعی اینترنت", "فایروال یا فیلترینگ"],
        "steps": ["flushdns", "winsock"],
        "tool_ids": [30, 33, 35],
    },
    (4227, "Tcpip"): {
        "title": "شکست در برقراری اتصال TCP",
        "severity": WARNING,
        "meaning": "ویندوز نتوانسته اتصال شبکه برقرار کند.",
        "causes": ["پیکربندی نادرست شبکه", "پروکسی نامعتبر", "کمبود پورت آزاد"],
        "steps": ["winsock", "renew_ip"],
        "tool_ids": [31, 33],
    },
    (4201, "Tcpip"): {
        "title": "اتصال کابل شبکه برقرار شد",
        "severity": INFO,
        "meaning": "کارت شبکه اتصال را تشخیص داده است. طبیعی است.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },
    (4202, "Tcpip"): {
        "title": "قطع اتصال کابل شبکه",
        "severity": WARNING,
        "meaning": "کارت شبکه اتصال را از دست داده است.",
        "causes": ["کابل شل یا معیوب", "خاموش شدن مودم", "درایور شبکه"],
        "steps": ["renew_ip"],
        "tool_ids": [33],
    },
    (1129, None): {
        "title": "شکست در پردازش Group Policy",
        "severity": WARNING,
        "meaning": "ویندوز نتوانسته به کنترلر دامنه دسترسی پیدا کند.",
        "causes": ["نبود اتصال به شبکهٔ سازمانی", "تنظیمات دامنه"],
        "steps": [],
        "tool_ids": [6],
    },

    # ═══════════ فایل‌های سیستمی و به‌روزرسانی ═══════════
    (1001, "Windows Error Reporting"): {
        "title": "گزارش خطای ویندوز",
        "severity": INFO,
        "meaning": "ویندوز گزارشی از یک خطا ثبت کرده است. جزئیات در متن رویداد.",
        "causes": [],
        "steps": [],
        "tool_ids": [14],
    },
    (20, "WindowsUpdateClient"): {
        "title": "نصب ناموفق به‌روزرسانی",
        "severity": WARNING,
        "meaning": "یک به‌روزرسانی ویندوز نصب نشده است.",
        "causes": ["فضای دیسک ناکافی",
                   "خرابی مخزن به‌روزرسانی",
                   "قطع اینترنت حین دانلود"],
        "steps": ["dism_restore", "temp_clean"],
        "tool_ids": [37, 38],
    },
    (1033, "MsiInstaller"): {
        "title": "نصب یا حذف نرم‌افزار",
        "severity": INFO,
        "meaning": "یک بستهٔ MSI نصب یا حذف شده است.",
        "causes": [],
        "steps": [],
        "tool_ids": [1, 4],
    },
    (11707, "MsiInstaller"): {
        "title": "نصب موفق نرم‌افزار",
        "severity": INFO,
        "meaning": "نصب با موفقیت کامل شد.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },
    (11708, "MsiInstaller"): {
        "title": "نصب ناموفق نرم‌افزار",
        "severity": WARNING,
        "meaning": "نصب نرم‌افزار شکست خورده و برگشت داده شده است.",
        "causes": ["دسترسی ناکافی", "فضای ناکافی", "نسخهٔ قبلی خراب"],
        "steps": [],
        "tool_ids": [1, 4],
    },

    # ═══════════ امنیت ═══════════
    (4625, None): {
        "title": "تلاش ناموفق برای ورود",
        "severity": WARNING,
        "meaning": "کسی با نام کاربری یا رمز اشتباه تلاش کرده وارد شود.",
        "causes": ["اشتباه تایپی کاربر",
                   "سرویسی با اطلاعات قدیمی",
                   "تلاش نفوذ (اگر تکرار زیاد باشد)"],
        "steps": [],
        "tool_ids": [11],
    },
    (1116, "Windows Defender"): {
        "title": "شناسایی بدافزار",
        "severity": CRITICAL,
        "meaning": "Defender یک تهدید پیدا کرده است.",
        "causes": ["دانلود آلوده", "فلش آلوده", "نرم‌افزار کرک‌شده"],
        "steps": [],
        "tool_ids": [8],
    },
    (1117, "Windows Defender"): {
        "title": "اقدام علیه بدافزار انجام شد",
        "severity": WARNING,
        "meaning": "Defender تهدید را قرنطینه یا حذف کرده است.",
        "causes": [],
        "steps": [],
        "tool_ids": [8],
    },
    (5007, "Windows Defender"): {
        "title": "تغییر پیکربندی Defender",
        "severity": WARNING,
        "meaning": "تنظیمات آنتی‌ویروس عوض شده است. اگر خودتان تغییری "
                   "نداده‌اید، ممکن است بدافزار آن را دستکاری کرده باشد.",
        "causes": ["تغییر دستی کاربر", "نصب آنتی‌ویروس دیگر", "بدافزار"],
        "steps": [],
        "tool_ids": [8],
    },

    # ═══════════ کارایی ═══════════
    (100, "Diagnostics-Performance"): {
        "title": "گزارش کارایی بوت",
        "severity": INFO,
        "meaning": "مدت زمان بالا آمدن ویندوز ثبت شده است.",
        "causes": [],
        "steps": [],
        "tool_ids": [24],
    },
    (101, "Diagnostics-Performance"): {
        "title": "برنامهٔ کندکنندهٔ بوت",
        "severity": WARNING,
        "meaning": "یک برنامه بوت را کند کرده است. نام آن در متن رویداد آمده.",
        "causes": ["برنامهٔ استارتاپ سنگین"],
        "steps": [],
        "tool_ids": [24],
    },
    (103, "Diagnostics-Performance"): {
        "title": "سرویس کندکنندهٔ بوت",
        "severity": WARNING,
        "meaning": "یک سرویس زمان بوت را طولانی کرده است.",
        "causes": ["سرویس با راه‌اندازی کند"],
        "steps": [],
        "tool_ids": [13],
    },
    (109, "Kernel-Power"): {
        "title": "درخواست خاموشی کرنل",
        "severity": INFO,
        "meaning": "کرنل فرآیند خاموش شدن را آغاز کرده است.",
        "causes": [],
        "steps": [],
        "tool_ids": [],
    },
    (2004, "Resource-Exhaustion-Detector"): {
        "title": "کمبود حافظهٔ سیستم",
        "severity": CRITICAL,
        "meaning": "ویندوز تشخیص داده حافظه تمام شده و برنامه‌هایی را "
                   "بسته است. نام پرمصرف‌ترین‌ها در متن رویداد آمده.",
        "causes": ["نشتی حافظه در یک برنامه",
                   "رم ناکافی برای بار کاری",
                   "حافظهٔ مجازی کوچک"],
        "steps": [],
        "tool_ids": [23, 25, 7],
    },
    (2013, "srv"): {
        "title": "فضای دیسک بحرانی",
        "severity": CRITICAL,
        "meaning": "فضای آزاد دیسک به حد بحرانی رسیده است.",
        "causes": ["فایل‌های موقت انباشته", "فایل‌های به‌روزرسانی قدیمی"],
        "steps": ["temp_clean", "cleanmgr"],
        "tool_ids": [37, 38, 39],
    },

    # ═══════════ اپلیکیشن و .NET ═══════════
    (1026, ".NET Runtime"): {
        "title": "کرش برنامهٔ دات‌نت",
        "severity": WARNING,
        "meaning": "برنامه‌ای که با .NET نوشته شده کرش کرده است.",
        "causes": ["باگ برنامه", "نسخهٔ .NET ناسازگار یا خراب"],
        "steps": [],
        "tool_ids": [3, 4],
    },
    (10016, "DistributedCOM"): {
        "title": "خطای دسترسی DCOM",
        "severity": INFO,
        "meaning": "یک مؤلفه اجازهٔ دسترسی نداشته. این خطا در ویندوز ۱۰ و ۱۱ "
                   "بسیار رایج است و معمولاً بی‌خطر — مایکروسافت هم "
                   "توصیه به نادیده گرفتنش کرده است.",
        "causes": ["تنظیمات پیش‌فرض دسترسی DCOM"],
        "steps": [],
        "tool_ids": [],
    },
    (36871, "Schannel"): {
        "title": "خطای رمزنگاری TLS",
        "severity": WARNING,
        "meaning": "برقراری اتصال امن ناموفق بوده است.",
        "causes": ["تاریخ سیستم نادرست",
                   "گواهی منقضی",
                   "پروتکل TLS قدیمی غیرفعال"],
        "steps": [],
        "tool_ids": [35],
    },
    (1079, None): {
        "title": "خطای دسترسی سرویس",
        "severity": WARNING,
        "meaning": "سرویسی به منبعی دسترسی نداشته است.",
        "causes": ["مجوزهای نادرست", "حساب سرویس تغییر کرده"],
        "steps": [],
        "tool_ids": [13],
    },
}

# نگاشت سریع فقط بر اساس ID، برای وقتی Provider ناشناخته است
_BY_ID = {}
for (eid, prov), info in CATALOG.items():
    _BY_ID.setdefault(eid, []).append((prov, info))


def lookup(event_id, provider=""):
    """
    یافتن اطلاعات یک رویداد.

    اول تطبیق دقیق (ID + Provider)، بعد تطبیق فقط با ID.
    اگر چند مدخل با یک ID باشد و Provider نخواند، None برمی‌گردد —
    حدس زدن بدتر از نگفتن است.
    """
    try:
        eid = int(event_id)
    except (TypeError, ValueError):
        return None

    entries = _BY_ID.get(eid)
    if not entries:
        return None

    prov = (provider or "").lower()

    # تطبیق دقیق با Provider
    for p, info in entries:
        if p and p.lower() in prov:
            return dict(info, event_id=eid, provider=p)

    # مدخل بدون قید Provider
    for p, info in entries:
        if p is None:
            return dict(info, event_id=eid, provider="")

    # چند مدخل ولی هیچ‌کدام نخواند
    if len(entries) == 1:
        p, info = entries[0]
        return dict(info, event_id=eid, provider=p, uncertain=True)
    return None


# الگوهای استخراج از متن خام Event Viewer
_ID_PATTERNS = [
    re.compile(r"\bId\s*[:=]\s*(\d{1,5})\b", re.I),
    re.compile(r"\bEvent\s*ID\s*[:=]?\s*(\d{1,5})\b", re.I),
    re.compile(r"شناسه\s*[:=]?\s*(\d{1,5})"),
]
_PROV_PATTERNS = [
    re.compile(r"ProviderName\s*[:=]\s*(.+)", re.I),
    re.compile(r"Provider\s*[:=]\s*(.+)", re.I),
    re.compile(r"Source\s*[:=]\s*(.+)", re.I),
]


def parse_events(text, limit=25):
    """
    استخراج رویدادها از خروجی خام Event Viewer.

    خروجی `Get-WinEvent ... | Format-List` بلوک‌هایی با
    `Id : 41` و `ProviderName : Microsoft-Windows-Kernel-Power` دارد.
    """
    if not text:
        return []

    found = []
    seen = set()
    cur_id = cur_prov = None

    for line in str(text).split("\n"):
        for pat in _ID_PATTERNS:
            m = pat.search(line)
            if m:
                if cur_id is not None:
                    key = (cur_id, cur_prov or "")
                    if key not in seen:
                        seen.add(key)
                        found.append((cur_id, cur_prov or ""))
                cur_id = int(m.group(1))
                cur_prov = None
                break
        for pat in _PROV_PATTERNS:
            m = pat.search(line)
            if m:
                cur_prov = m.group(1).strip()
                break

    if cur_id is not None:
        key = (cur_id, cur_prov or "")
        if key not in seen:
            found.append((cur_id, cur_prov or ""))

    return found[:limit]


def explain_text(raw_text, limit=15):
    """
    تحلیل متن خام Event Viewer و برگرداندن رویدادهای شناخته‌شده.
    """
    pairs = parse_events(raw_text, limit=limit * 2)
    known, unknown = [], []

    for eid, prov in pairs:
        info = lookup(eid, prov)
        if info:
            known.append(info)
        else:
            unknown.append({"event_id": eid, "provider": prov})
        if len(known) >= limit:
            break

    # بحرانی‌ها اول
    order = {CRITICAL: 0, WARNING: 1, INFO: 2}
    known.sort(key=lambda x: order.get(x.get("severity"), 9))

    steps, seen_steps = [], set()
    tools, seen_tools = [], set()
    for k in known:
        for s in k.get("steps", []):
            if s not in seen_steps:
                seen_steps.add(s)
                steps.append(s)
        for t in k.get("tool_ids", []):
            if t not in seen_tools:
                seen_tools.add(t)
                tools.append(t)

    counts = {
        "critical": sum(1 for k in known if k["severity"] == CRITICAL),
        "warning": sum(1 for k in known if k["severity"] == WARNING),
        "info": sum(1 for k in known if k["severity"] == INFO),
    }

    return {
        "success": True,
        "known": known,
        "unknown": unknown,
        "counts": counts,
        "suggested_steps": steps,
        "tool_ids": tools,
        "summary_fa": _summary(counts, len(known), len(unknown)),
    }


def _summary(counts, n_known, n_unknown):
    if not n_known and not n_unknown:
        return "رویداد قابل تحلیلی در متن پیدا نشد."
    parts = []
    if counts["critical"]:
        parts.append(f"{counts['critical']} بحرانی")
    if counts["warning"]:
        parts.append(f"{counts['warning']} هشدار")
    if counts["info"]:
        parts.append(f"{counts['info']} اطلاعی")
    txt = f"{n_known} رویداد شناخته‌شده"
    if parts:
        txt += " (" + "، ".join(parts) + ")"
    if n_unknown:
        txt += f" و {n_unknown} رویداد ناشناخته"
    return "📋 " + txt + "."


def format_for_ai(result, max_items=8):
    """
    متن فارسی برای زمینهٔ AI.

    هدف: AI وقتش را صرف توضیح دوبارهٔ رویدادهای شناخته‌شده نکند و
    روی ترکیب آنها و علت ریشه‌ای تمرکز کند.
    """
    if not result or not result.get("known"):
        return ""

    lines = ["### تحلیل رویدادهای Event Viewer (فرهنگ داخلی)", ""]
    lines.append(result.get("summary_fa", ""))
    lines.append("")

    for k in result["known"][:max_items]:
        if k["severity"] == INFO:
            continue        # رویدادهای اطلاعی به AI ارزش افزوده نمی‌دهند
        sev = _SEV_FA.get(k["severity"], "")
        prov = f" · {k['provider']}" if k.get("provider") else ""
        lines.append(f"**[{sev}] Event {k['event_id']}{prov} — {k['title']}**")
        lines.append(k["meaning"])
        if k.get("causes"):
            lines.append("علت‌های محتمل: " + "، ".join(k["causes"]))
        lines.append("")

    if result.get("unknown"):
        ids = "، ".join(str(u["event_id"]) for u in result["unknown"][:10])
        lines.append(f"رویدادهای ناشناخته که باید خودت تحلیل کنی: {ids}")
        lines.append("")

    lines.append(
        "معنی این رویدادها از فرهنگ داخلی آمده و قطعی است — دوباره "
        "توضیحشان نده. روی این تمرکز کن که ترکیب این رویدادها چه "
        "الگویی می‌سازد و علت ریشه‌ای چیست."
    )
    return "\n".join(lines)


def catalog_size():
    return len(CATALOG)
