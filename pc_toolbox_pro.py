# -*- coding: utf-8 -*-
"""
===================================================================
PC Repair Toolbox Pro + AI Agent (Unified Integration)
شامل تمامی ۴۲ ابزار ویندوز + عیب‌یاب هوشمند AI + پروکسی SOCKS5
===================================================================
"""

import sys
import os
import json
import time
import threading
import backend_server
import system_inspector
import proxy

# Safe JSON parsing
TOOLS_DATA_JSON = """[{"id": 1, "name_en": "Installed Apps", "name_fa": "برنامه‌های نصب‌شده", "category_en": "Apps & Features", "category_fa": "برنامه‌ها و قابلیت‌ها", "command": "start ms-settings:appsfeatures", "badge_admin": false, "badge_may_vary": false, "desc": "صفحه مدیریت برنامه‌ها و اپلیکیشن‌های جدید در تنظیمات مدرن ویندوز.", "guide": "۱. روی دکمه اجرای ابزار کلیک کنید تا تنظیمات Apps & Features ویندوز باز شود.\\n۲. از کادر جستجو برنامه مورد نظر خود را پیدا کنید.\\n۳. با کلیک روی منوی سه‌نقطه کنار هر برنامه، گزینه‌های Uninstall (حذف) یا Advanced Options (تعمیر و بازنشانی) را انتخاب کنید.", "warning": "برنامه‌های پایه سیستمی مایکروفرت را که با عملکرد ویندوز در ارتباط هستند حذف نکنید."}, {"id": 2, "name_en": "Default Apps", "name_fa": "برنامه‌های پیش‌فرض", "category_en": "Apps & Features", "category_fa": "برنامه‌ها و قابلیت‌ها", "command": "start ms-settings:defaultapps", "badge_admin": false, "badge_may_vary": false, "desc": "مدیریت برنامه‌های پیش‌فرض سیستم برای باز کردن انواع فایل‌ها و لینک‌ها.", "guide": "۱. پس از اجرای ابزار، مرورگر، برنامه ایمیل یا پلیر دلخواه را انتخاب کنید.\\n۲. می‌توانید پسوند فایل خاصی (مانند pdf. یا mp4.) را جستجو کرده و برنامه پیش‌فرض آن را تغییر دهید.", "warning": "تغییر برنامه‌های پیش‌فرض فایل‌های حساس سیستمی ممکن است نحوه اجرای آن‌ها را تغییر دهد."}, {"id": 3, "name_en": "Optional Features", "name_fa": "ویژگی‌های اختیاری", "category_en": "Apps & Features", "category_fa": "برنامه‌ها و قابلیت‌ها", "command": "start ms-settings:optionalfeatures", "badge_admin": false, "badge_may_vary": false, "desc": "افزودن یا حذف ویژگی‌های اختیاری و ابزارهای توسعه‌دهندگان ویندوز.", "guide": "۱. روی Add a feature کلیک کنید تا قابلیت‌های قابل دانلود نشان داده شوند.\\n۲. ویژگی‌هایی مانند OpenSSH Client، ابزارهای گرافیکی قدیمی یا زبان‌ها را انتخاب و نصب کنید.", "warning": "حذف ویژگی‌های جانبی ضروری ممکن است باعث کار نکردن برخی برنامه‌های تخصصی شود."}, {"id": 4, "name_en": "Programs and Features", "name_fa": "برنامه‌ها و قابلیت‌های کلاسیک", "category_en": "Apps & Features", "category_fa": "برنامه‌ها و قابلیت‌ها", "command": "appwiz.cpl", "badge_admin": false, "badge_may_vary": false, "desc": "محیط سنتّی و کلاسیک کنترل‌پنل برای مدیریت و حذف نرم‌افزارهای دسکتاپ.", "guide": "۱. پس از باز شدن پنجره، لیست نرم‌افزارها را مشاهده کنید.\\n۲. برنامه مورد نظر را انتخاب کرده و روی Uninstall/Change در بالای جدول کلیک کنید.\\n۳. از منوی سمت چپ می‌توانید View installed updates را برای مدیریت آپدیت‌ها انتخاب کنید.", "warning": "هنگام حذف درایورهای سخت‌افزاری و بسته‌های کدهای ++C دقت کنید."}, {"id": 5, "name_en": "Registry Editor", "name_fa": "ویرایشگر رجیستری (Regedit)", "category_en": "Advanced", "category_fa": "تنظیمات پیشرفته سیستم", "command": "regedit.exe", "badge_admin": true, "badge_may_vary": false, "desc": "پایگاه داده مرکزی تنظیمات پیکربندی پایه‌ای ویندوز و نرم‌افزارها.", "guide": "۱. با دسترسی Admin ویرایشگر را باز کنید.\\n۲. در درخت سمت چپ کلیدهای HKEY_LOCAL_MACHINE یا HKEY_CURRENT_USER را باز کنید.\\n۳. قبل از هر ویرایش، از منوی File گزینه Export را بزنید تا فایل پشتیبان reg. ساخته شود.", "warning": "هشدار بسیار مهم: ویرایش یا حذف اشتباه کلیدهای رجیستری می‌تواند باعث خرابی و بالانیامدن ویندوز شود!"}, {"id": 6, "name_en": "Local Group Policy", "name_fa": "ویرایشگر پالیسی محلی (Group Policy)", "category_en": "Advanced", "category_fa": "تنظیمات پیشرفته سیستم", "command": "gpedit.msc", "badge_admin": true, "badge_may_vary": true, "desc": "مدیریت سیاست‌های امنیتی، دسترسی کاربران و تنظیمات گروهی سیستم.", "guide": "۱. ابزار را باز کرده و به بخش Computer Configuration یا User Configuration بروید.\\n۲. گزینه‌های Administrative Templates را جهت تنظیم سیاست‌های اپلیکیشن‌ها و سیستم ویرایش کنید.\\n۳. روی هر پالیسی دابل کلیک کرده و حالت Enabled یا Disabled را تعیین کنید.", "warning": "این ابزار به‌صورت پیش‌فرض فقط در نسخه Windows Pro / Enterprise فعال است. در نسخه Home نیازمند فعال‌سازی دستی است."}, {"id": 7, "name_en": "Advanced System Properties", "name_fa": "تنظیمات پیشرفته سیستم", "category_en": "Advanced", "category_fa": "تنظیمات پیشرفته سیستم", "command": "sysdm.cpl", "badge_admin": false, "badge_may_vary": false, "desc": "پنجره تنظیمات پیشرفته ویندوز شامل عملکرد، متغیرهای محیطی و System Restore.", "guide": "۱. تب Advanced را انتخاب کنید.\\n۲. در بخش Performance روی Settings کلیک کنید تا افکت‌ها و حافظه مجازی (Virtual Memory) را تنظیم کنید.\\n۳. دکمه Environment Variables برای تنظیم متغیرهای سیستمی مانند PATH استفاده می‌شود.", "warning": "حذف یا تغییر اشتباه متغیرهای PATH باعث عدم شناسایی دستورات در ترمینال می‌شود."}, {"id": 8, "name_en": "Windows Security", "name_fa": "امنیت ویندوز (Microsoft Defender)", "category_en": "Security", "category_fa": "امنیت و دسترسی‌ها", "command": "start windowsdefender:", "badge_admin": false, "badge_may_vary": false, "desc": "مرکز جامع مدیریت امنیت، آنتی‌ویروس و دیواره آتش ویندوز.", "guide": "۱. بخش Virus & threat protection را باز کنید.\\n۲. روی Quick scan یا Full scan جهت اسکن سیستم کلیک کنید.\\n۳. در صورت نیاز به غیرفعال‌سازی موقت محافظت زنده، به Manage settings بروید.", "warning": "خاموش ماندن طولانی‌مدت Real-time protection سیستم شما را در معرض تهدید بدافزارها قرار می‌دهد."}, {"id": 9, "name_en": "Firewall Advanced", "name_fa": "فایروال پیشرفته ویندوز", "category_en": "Security", "category_fa": "امنیت و دسترسی‌ها", "command": "wf.msc", "badge_admin": true, "badge_may_vary": false, "desc": "مدیریت دقیق قوانین ورود و خروج ترافیک شبکه برای برنامه‌ها و پورت‌ها.", "guide": "۱. از پنل سمت چپ Inbound Rules (ترافیک ورودی) یا Outbound Rules (ترافیک خروجی) را انتخاب کنید.\\n۲. با زدن New Rule می‌توانید دسترسی یک برنامه یا پورت TCP/UDP خاص به شبکه را مسدود یا مجاز کنید.", "warning": "مسدود کردن اشتباه پورت‌های سیستمی باعث قطعی ارتباط اینترنت یا سرویس‌های آنلاین می‌شود."}, {"id": 10, "name_en": "BitLocker", "name_fa": "رمزگذاری درایوها (BitLocker)", "category_en": "Security", "category_fa": "امنیت و دسترسی‌ها", "command": "control /name Microsoft.BitLockerDriveEncryption", "badge_admin": true, "badge_may_vary": true, "desc": "ابزار رمزنگاری پیشرفته درایوهای هارد دیسک و حافظه‌های جانبی.", "guide": "۱. درایو مورد نظر را انتخاب کرده و Turn on BitLocker را بزنید.\\n۲. یک رمز عبور قوی تعیین کنید.\\n۳. فایل کلید بازیابی (Recovery Key) را حتماً در یک فلش یا اکانت مایکروسافت ذخیره کنید.", "warning": "هشدار: در صورت فراموشی رمز و گم شدن کلید بازیابی، اطلاعات درایو به هیچ وجه قابل بازگردانی نخواهد بود!"}, {"id": 11, "name_en": "User Account Control", "name_fa": "کنترل حساب کاربر (UAC)", "category_en": "Security", "category_fa": "امنیت و دسترسی‌ها", "command": "UserAccountControlSettings.exe", "badge_admin": true, "badge_may_vary": false, "desc": "تنظیم سطح هشدارهای امنیتی هنگام تغییرات سیستمی و اجرای برنامه‌ها.", "guide": "۱. اسلایدر را بین ۴ سطح تغییر دهید.\\n۲. سطح دوم (پیش‌فرض) بهترین تعادل را میان امنیت و راحتی کار ایجاد می‌کند.\\n۳. روی OK کلیک کنید تا تغییرات اعمال شود.", "warning": "قراردادن اسلایدر روی سطح پایین (Never Notify) امنیت سیستم را به شدت کاهش می‌دهد."}, {"id": 12, "name_en": "Device Manager", "name_fa": "مدیریت دستگاه‌ها (Device Manager)", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "devmgmt.msc", "badge_admin": true, "badge_may_vary": false, "desc": "مشاهده سخت‌افزارهای نصب‌شده، مدیریت درایورها و عیب‌یابی قطعات.", "guide": "۱. شاخه قطعه مورد نظر (مانند Display adapters یا Network adapters) را باز کنید.\\n۲. روی درایور راست‌کلیک کرده و Update driver یا Uninstall device را بزنید.\\n۳. علامت تعجب زرد رنگ نشان‌دهنده نصب نبودن صحیح درایور است.", "warning": "غیرفعال کردن قطعات حیاتی ممکن است عملکرد ورودی/خروجی سیستم را مختل کند."}, {"id": 13, "name_en": "Services", "name_fa": "سرویس‌های ویندوز (Services)", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "services.msc", "badge_admin": true, "badge_may_vary": false, "desc": "مدیریت سرویس‌های پس‌زمینه ویندوز و کنترل وضعیت اجرای آن‌ها.", "guide": "۱. سرویس مورد نظر را در جدول پیدا کنید.\\n۲. روی آن دابل‌کلیک کرده و Startup type را روی Automatic، Manual یا Disabled تنظیم کنید.\\n۳. با دکمه‌های Start و Stop می‌توانید سرویس را در لحظه کنترل کنید.", "warning": "غیرفعال کردن سرویس‌های پایه ویندوز ممکن است باعث اختلال در کل سیستم‌عامل شود."}, {"id": 14, "name_en": "Event Viewer", "name_fa": "نمایش‌دهنده رویدادها (Event Viewer)", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "eventvwr.msc", "badge_admin": true, "badge_may_vary": false, "desc": "ابزار تحلیل و مشاهده گزارش‌های خطا و رویدادهای سیستم‌عامل.", "guide": "۱. از پنل سمت چپ مسیر Windows Logs -> System یا Application را انتخاب کنید.\\n۲. خطاهایی که آیکون قرمز رنگ دارند را بررسی کرده و کد Event ID آن‌ها را مشاهده کنید.\\n۳. برای عیب‌یابی کرش‌ها و کرش‌های ناگهانی بهترین ابزار است.", "warning": "برخی هشدارهای زرد و خطاهای غیرتکراری طبیعی هستند و نیازی به دستکاری ندارند."}, {"id": 15, "name_en": "Disk Management", "name_fa": "مدیریت دیسک و پارتیشن‌ها", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "diskmgmt.msc", "badge_admin": true, "badge_may_vary": false, "desc": "پارتیشن‌بندی، فرمت دیسک و تغییر حروف درایورها.", "guide": "۱. روی پارتیشن مورد نظر راست‌کلیک کنید.\\n۲. برای کم کردن حجم Shrink Volume و برای افزودن حجم Extend Volume را بزنید.\\n۳. گزینه Format برای پاک‌سازی کامل درایو استفاده می‌شود.", "warning": "حذف پارتیشن یا فرمت کردن، تمامی اطلاعات موجود روی آن درایو را پاک می‌کند!"}, {"id": 16, "name_en": "System Information", "name_fa": "اطلاعات کامل سیستم (Msinfo32)", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "msinfo32.exe", "badge_admin": false, "badge_may_vary": false, "desc": "مشاهده جزئیات کامل سخت‌افزار، نسخه BIOS، مدل مادربورد و سیستم‌عامل.", "guide": "۱. ابزار را باز کرده و بخش System Summary را مطالعه کنید.\\n۲. مشخصات پردازنده، میزان رم، حالت BIOS (UEFI/Legacy) و نسخه دقیق ویندوز درج شده است.\\n۳. می‌توانید مشخصات را در یک فایل متنی خروجی بگیرید.", "warning": "این ابزار صرفاً جهت اطلاع‌رسانی است و تغییری در سیستم ایجاد نمی‌کند."}, {"id": 17, "name_en": "Control Panel", "name_fa": "کنترل پنل کلاسیک", "category_en": "System Tools", "category_fa": "ابزارهای مدیریتی سیستم", "command": "control.exe", "badge_admin": false, "badge_may_vary": false, "desc": "دسترسی یک‌جا به تمامی ابزارها و تنظیمات سنتّی و قدیمی ویندوز.", "guide": "۱. پس از باز شدن، در بالا سمت راست View by را روی Small icons بگذارید.\\n۲. به بیش از ۳۰ ابزار مدیریتی و تنظیمات سیستم دسترسی مستقیم خواهید داشت.", "warning": "تنظیمات سیستمی را تنها در صورت داشتن آگاهی تغییر دهید."}, {"id": 18, "name_en": "Startup Apps", "name_fa": "برنامه‌های استارت‌آپ", "category_en": "Performance", "category_fa": "ارتقا و پایش عملکرد", "command": "start ms-settings:startup", "badge_admin": false, "badge_may_vary": false, "desc": "مدیریت برنامه‌هایی که هنگام روشن شدن ویندوز خودکار اجرا می‌شوند.", "guide": "۱. لیست برنامه‌های استارت‌آپ را مرور کنید.\\n۲. سوئیچ برنامه‌های غیرضروری (مانند آپدیترها یا پیام‌رسان‌ها) را Off کنید تا سرعت بوت زیاد شود.", "warning": "برنامه‌های امنیتی و درایورهای اصلی را غیرفعال نکنید."}, {"id": 19, "name_en": "Task Manager", "name_fa": "مدیریت وظایف (Task Manager)", "category_en": "Performance", "category_fa": "ارتقا و پایش عملکرد", "command": "taskmgr.exe", "badge_admin": false, "badge_may_vary": false, "desc": "پایش مصرف منابع، بستن برنامه‌های هنگ‌کرده و مدیریت پردازش‌ها.", "guide": "۱. کلیدهای Ctrl + Shift + Esc را بزنید یا روی دکمه کلیک کنید.\\n۲. برنامه‌های پرمصرف در بخش CPU یا Memory را پیدا کنید.\\n۳. روی برنامه هنگ‌کرده راست‌کلیک کرده و End task را بزنید.", "warning": "پردازش‌های پایه سیستمی ویندوز مانند Windows Explorer را نبندید."}, {"id": 20, "name_en": "Power Options", "name_fa": "تنظیمات مصرف انرژی (Power Options)", "category_en": "Performance", "category_fa": "ارتقا و پایش عملکرد", "command": "powercfg.cpl", "badge_admin": false, "badge_may_vary": false, "desc": "تنظیم پلن‌های مصرف انرژی برای کارایی بالاتر یا ذخیره باتری.", "guide": "۱. یکی از طرح‌های High Performance یا Balanced را انتخاب کنید.\\n۲. با کلیک روی Change plan settings زمان خاموش شدن صفحه و Sleep را تنظیم کنید.", "warning": "حالت High Performance مصرف باتری لپ‌تاپ را افزایش می‌دهد."}, {"id": 21, "name_en": "Visual Effects", "name_fa": "افکت‌های بصری و جلوه‌های گرافیکی", "category_en": "Performance", "category_fa": "ارتقا و پایش عملکرد", "command": "SystemPropertiesPerformance.exe", "badge_admin": false, "badge_may_vary": false, "desc": "بهینه‌سازی انیمیشن‌ها و جلوه‌های تصویری ویندوز برای افزایش سرعت.", "guide": "۱. برای سیستم‌های ضعیف گزینه Adjust for best performance را علامت بزنید.\\n۲. این کار تمام انیمیشن‌های اضافی را خاموش کرده و سرعت پنجره‌ها را بسیار بالا می‌برد.", "warning": "ظاهر گرافیکی پنجره‌ها کمی ساده‌تر و بدون انیمیشن خواهد شد."}, {"id": 22, "name_en": "Resource Monitor", "name_fa": "پایش دقیق منابع (Resource Monitor)", "category_en": "Performance", "category_fa": "ارتقا و پایش عملکرد", "command": "resmon.exe", "badge_admin": true, "badge_may_vary": false, "desc": "تحلیل بسیار جزئی و لحظه‌ای از مصرف CPU، RAM، دیسک و شبکه.", "guide": "۱. تب Disk را باز کنید تا ببینید کدام برنامه در حال خواندن/نوشتن هارد است.\\n۲. در تب Network مصرف پهنای باند هر برنامه را آنلاین بررسی کنید.", "warning": "این ابزار تخصصی پایش است؛ برای بستن برنامه‌ها Task Manager پیشنهاد می‌شود."}, {"id": 23, "name_en": "SFC Scan", "name_fa": "اسکن و تعمیر فایل‌های سیستمی (SFC)", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "cmd.exe /k sfc /scannow", "badge_admin": true, "badge_may_vary": false, "desc": "اسکن جامع و جایگزینی خودکار فایل‌های سیستمی آسیب‌دیده ویندوز.", "guide": "۱. دکمه اجرا را بزنید تا ترمینال با دسترسی Admin باز شود.\\n۲. منتظر بمانید درصد اسکن به ۱۰۰٪ برسد.\\n۳. در صورت یافتن فایل خراب، ویندوز خودکار آن را جایگزین می‌کند.", "warning": "تا پایان فرآیند پنجره مشکی ترمینال را نبندید."}, {"id": 24, "name_en": "DISM RestoreHealth", "name_fa": "تعمیر ایمیج ویندوز (DISM)", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "cmd.exe /k DISM /Online /Cleanup-Image /RestoreHealth", "badge_admin": true, "badge_may_vary": false, "desc": "بازسازی و تعمیر مخزن اصلی فایل‌های ویندوز (Component Store).", "guide": "۱. ابزار را اجرا کنید.\\n۲. این فرآیند حدود ۱۰ الی ۲۰ دقیقه طول می‌کشد و فایل‌های سالم را دانلود می‌کند.\\n۳. پس از پایان، پیام Restoration operation completed successfully ظاهر می‌شود.", "warning": "نیازمند اتصال پایدار اینترنت برای دانلود فایل‌های سلامتی ویندوز است."}, {"id": 25, "name_en": "Full Windows Repair", "name_fa": "تعمیر کامل و ترکیبی ویندوز", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "cmd.exe /k sfc /scannow && DISM /Online /Cleanup-Image /RestoreHealth", "badge_admin": true, "badge_may_vary": false, "desc": "اجرای متوالی دو دستور SFC و DISM برای عیب‌یابی و تعمیر کامل.", "guide": "۱. این گزینه ابتدا اسکن SFC را انجام داده و بلافاصله DISM را اجرا می‌کند.\\n۲. کامل‌ترین راهکار عیب‌یابی نرم‌افزاری ویندوز بدون نیاز به نصب مجدد است.", "warning": "زمان‌بر است؛ تا پایان کامل پردازش صبور باشید."}, {"id": 26, "name_en": "Windows Update", "name_fa": "آپدیت ویندوز (Windows Update)", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "start ms-settings:windowsupdate", "badge_admin": false, "badge_may_vary": false, "desc": "بررسی و دریافت آخرین پچ‌های امنیتی و بروزرسانی‌های سیستم‌عامل.", "guide": "۱. روی دکمه Check for updates کلیک کنید.\\n۲. آپدیت‌ها دانلود و نصب می‌شوند.\\n۳. در صورت نیاز سیستم را ریستارت کنید.", "warning": "موقع نصب آپدیت‌ها سیستم را خاموش نکنید."}, {"id": 27, "name_en": "Create Restore Point", "name_fa": "ایجاد نقطه بازگردانی (Restore Point)", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "SystemPropertiesProtection.exe", "badge_admin": true, "badge_may_vary": false, "desc": "ذخیره وضعیت فعلی فایل‌های سیستمی جهت بازگردانی در صورت بروز مشکل.", "guide": "۱. درایو C را انتخاب کنید.\\n۲. روی دکمه Create کلیک کرده و یک نام توضیحی بنویسید.\\n۳. روی Create کلیک کنید تا نسخه پشتیبان سیستمی ساخته شود.", "warning": "نقطه بازگردانی فقط از فایل‌های سیستمی بک‌آپ می‌گیرد، نه فایل‌های شخصی شما."}, {"id": 28, "name_en": "System Restore", "name_fa": "بازیابی سیستم (System Restore)", "category_en": "Repair Windows", "category_fa": "تعمیر و بازگردانی ویندوز", "command": "rstrui.exe", "badge_admin": true, "badge_may_vary": false, "desc": "بازگرداندن فایل‌ها و تنظیمات ویندوز به تاریخ نقاط بازگردانی قبلی.", "guide": "۱. ابزار را اجرا کرده و Next را بزنید.\\n۲. تاریخی که سیستم در آن وضعیت سالم داشته را انتخاب کنید.\\n۳. فرآیند بازگردانی را تایید کنید تا سیستم ریستارت شود.", "warning": "تغییرات نرم‌افزاری ایجادشده بعد از آن تاریخ لغو خواهند شد."}, {"id": 29, "name_en": "Fix Internet", "name_fa": "تعمیر هوشمند قطعی اینترنت", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "cmd.exe /k ipconfig /flushdns && ipconfig /release && ipconfig /renew && netsh winsock reset", "badge_admin": true, "badge_may_vary": false, "desc": "اسکریپت همه‌جانبه برای رفع اکثر اختلالات و قطعی‌های شبکه و اینترنت.", "guide": "۱. با زدن دکمه، دستورات پاک‌سازی کش DNS، تمدید IP و بازنشانی Winsock اجرا می‌شوند.\\n۲. پس از اتمام، سیستم را ریستارت کنید تا اتصال کامل برقرار شود.", "warning": "اتصال اینترنت برای چند ثانیه قطع شده و مجددا وصل می‌شود."}, {"id": 30, "name_en": "Flush DNS", "name_fa": "پاک‌سازی کش دی‌ان‌اس (Flush DNS)", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "cmd.exe /k ipconfig /flushdns", "badge_admin": true, "badge_may_vary": false, "desc": "تخلیه حافظه موقت DNS جهت حل مشکل باز نشدن صفحات وب.", "guide": "۱. دکمه را بزنید تا دستور اجرا شود.\\n۲. پیام Successfully flushed the DNS Resolver Cache ظاهر می‌شود.\\n۳. مرورگر را رفرش کنید.", "warning": "کاملاً ایمن است و هیچ مشکلی ایجاد نمی‌کند."}, {"id": 31, "name_en": "Reset Winsock", "name_fa": "بازنشانی پروتکل شبکه (Reset Winsock)", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "cmd.exe /k netsh winsock reset", "badge_admin": true, "badge_may_vary": false, "desc": "تعمیر و بازسازی کاتالوگ ارتباطی Winsock شبکه ویندوز.", "guide": "۱. ابزار را اجرا کنید.\\n۲. پس از مشاهده پیام موفقیت، سیستم را ریستارت کنید.", "warning": "تنظیمات سفارشی برخی برنامه‌های پروکسی یا VPN پاک می‌شود."}, {"id": 32, "name_en": "Renew IP Address", "name_fa": "تمدید آدرس IP", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "cmd.exe /k ipconfig /release && ipconfig /renew", "badge_admin": true, "badge_may_vary": false, "desc": "رهاسازی و دریافت مجدد آدرس IP از مودم (DHCP).", "guide": "۱. اجرای ابزار باعث قطع لحظه‌ای IP فعلی و در خواست IP جدید می‌شود.\\n۲. رفع خطاهای تداخل آدرس IP (IP Conflict).", "warning": "برای چند ثانیه شبکه قطع می‌شود."}, {"id": 33, "name_en": "Network Connections", "name_fa": "مدیریت کارت‌های شبکه (NCPA)", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "ncpa.cpl", "badge_admin": false, "badge_may_vary": false, "desc": "مشاهده و تنظیم کارت‌های شبکه Wi-Fi و LAN.", "guide": "۱. روی کارت شبکه مورد نظر راست‌کلیک کنید.\\n۲. گزینه‌های Disable/Enable یا Properties (جهت تنظیم ست کردن DNS یا IP دستی) را استفاده کنید.", "warning": "غیرفعال کردن کارت شبکه ارتباط شما را قطع می‌کند."}, {"id": 34, "name_en": "Network Status", "name_fa": "وضعیت شبکه و مصرف حجم", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "start ms-settings:network-status", "badge_admin": false, "badge_may_vary": false, "desc": "مشاهده وضعیت اتصال اینترنت و میزان مصرف داده برنامه‌ها.", "guide": "۱. وضعیت سلامت اتصال را بررسی کنید.\\n۲. بخش Data usage میزان مصرف حجم اینترنت هر نرم‌افزار را نشان می‌دهد.", "warning": "این بخش صرفاً نمایشی است."}, {"id": 35, "name_en": "Proxy Settings", "name_fa": "تنظیمات پروکسی سیستم", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "start ms-settings:network-proxy", "badge_admin": false, "badge_may_vary": false, "desc": "مدیریت پروکسی‌های سیستمی جهت حل مشکل قطعی سایت‌ها.", "guide": "۱. در صورت باز نشدن سایت‌ها، بررسی کنید که گزینه Use a proxy server خاموش باشد.\\n۲. در صورت نیاز به پروکسی خاص، آدرس و پورت را وارد کنید.", "warning": "پروکسی روشن و نامعتبر باعث قطع دسترسی مرورگرها به اینترنت می‌شود."}, {"id": 36, "name_en": "Windows Firewall", "name_fa": "فایروال ویندوز (Firewall)", "category_en": "Network", "category_fa": "شبکه و اینترنت", "command": "firewall.cpl", "badge_admin": false, "badge_may_vary": false, "desc": "پنجره اصلی دیواره آتش ویندوز برای مدیریت دسترسی‌ها.", "guide": "۱. جهت اجازه دادن به یک برنامه، روی Allow an app or feature... کلیک کنید.\\n۲. می‌توانید فایروال را روشن یا خاموش کنید.", "warning": "خاموش کردن فایروال سیستم را در برابر حملات شبکه‌ای آسیب‌پذیر می‌کند."}, {"id": 37, "name_en": "Clean Temporary Files", "name_fa": "پاک‌سازی فایل‌های موقت", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "start ms-settings:storagesense", "badge_admin": false, "badge_may_vary": false, "desc": "حذف ایمن فایل‌های اضافی Temp بدون آسیب به اطلاعات شخصی.", "guide": "۱. ابزار را باز کرده و آیتم‌های موقت را انتخاب کنید.\\n۲. دکمه Remove files را برای آزادسازی گیگابایت‌ها فضا بزنید.", "warning": "پوشه Downloads را مگر در صورت عدم نیاز علامت نزنید."}, {"id": 38, "name_en": "Disk Cleanup", "name_fa": "پاک‌سازی دیسک (Disk Cleanup)", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "cleanmgr.exe", "badge_admin": false, "badge_may_vary": false, "desc": "ابزار کلاسیک پاک‌سازی دیسک و فایل‌های آپدیت قبلی ویندوز.", "guide": "۱. درایو C را انتخاب و OK بزنید.\\n۲. مربع‌های مورد نظر را علامت بزنید.\\n۳. برای پاک‌سازی فایل‌های سیستمی قدیمی روی Clean up system files کلیک کنید.", "warning": "پاک کردن فایل‌های آپدیت قدیمی امکان دانگرید را از بین می‌برد."}, {"id": 39, "name_en": "Storage Settings", "name_fa": "تنظیمات فضای ذخیره‌سازی", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "start ms-settings:storage", "badge_admin": false, "badge_may_vary": false, "desc": "آنالیز گرافیکی حجم اشغال‌شده توسط عکس‌ها، برنامه‌ها و فایل‌ها.", "guide": "۱. دسته‌بندی پرحجم را باز کنید.\\n۲. فایل‌های بلااستفاده را شناسایی و مدیریت کنید.", "warning": "قبل از حذف فایل‌ها مطمئن شوید نیازی به آن‌ها ندارید."}, {"id": 40, "name_en": "Storage Sense", "name_fa": "حسگر هوشمند حافظه (Storage Sense)", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "start ms-settings:storagesense", "badge_admin": false, "badge_may_vary": false, "desc": "پاک‌سازی خودکار و زمان‌بندی‌شده فایل‌های موقت و سطل زباله.", "guide": "۱. کلید Storage Sense را روی On بگذارید.\\n۲. زمان‌بندی (هفتگی یا ماهانه) را انتخاب کنید تا ویندوز خودکار دیسک را تمیز نگه دارد.", "warning": "کاملاً ایمن و مفید است."}, {"id": 41, "name_en": "Temp Folder", "name_fa": "پوشه فایل‌های موقت (%temp%)", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "explorer.exe %temp%", "badge_admin": false, "badge_may_vary": false, "desc": "باز کردن مستقیم پوشه فایل‌های موقت کاربر در File Explorer.", "guide": "۱. کلیدهای Ctrl + A را بزنید تا همه انتخاب شوند.\\n۲. کلید Shift + Delete را بزنید تا حجم هارد آزاد شود.\\n۳. اگر پیامی داد که فایلی در حال استفاده است گزینه‌ی Skip را انتخاب کنید.", "warning": "فایل‌های در حال استفاده پاک نخواهند شد."}, {"id": 42, "name_en": "Recycle Bin", "name_fa": "سطل بازیافت (Recycle Bin)", "category_en": "Clean & Storage", "category_fa": "پاک‌سازی و مدیریت حافظه", "command": "explorer.exe shell:RecycleBinFolder", "badge_admin": false, "badge_may_vary": false, "desc": "باز کردن سطل زباله ویندوز جهت خالی‌سازی یا بازیابی فایل‌ها.", "guide": "۱. فایل‌هایی که اشتباهاً حذف شده‌اند را Restore کنید.\\n۲. برای آزادسازی کامل حجم روی Empty Recycle Bin کلیک کنید.", "warning": "پس از تخلیه سطل زباله، بازیابی نیازمند نرم‌افزارهای ریکاوری تخصصی خواهد بود."}]"""
TOOLS_DATA = json.loads(TOOLS_DATA_JSON)

# Engine 1: pywebview (Edge WebView2) - 100% Identical to HTML
HAS_WEBVIEW = False
try:
    import webview
    HAS_WEBVIEW = True
except ImportError:
    HAS_WEBVIEW = False

# Engine 2: PyQt6 with RTL Layout and Modern QSS Styling
HAS_PYQT = False
try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QLabel, QPushButton, QLineEdit, QScrollArea, QFrame, QGridLayout,
        QDialog, QTextEdit, QMessageBox
    )
    from PyQt6.QtCore import Qt
    HAS_PYQT = True
except ImportError:
    HAS_PYQT = False

# Engine 3: Tkinter Fallback
import tkinter as tk
from tkinter import ttk, messagebox, scrolledtext


# Start Backend Server in Background Thread
def start_backend_thread():
    t = threading.Thread(target=backend_server.start_server, daemon=True)
    t.start()
    time.sleep(0.5)

# WEBVIEW ENGINE (PRIORITY 1)
class WebviewApi:
    def run_cmd(self, cmd):
        backend_server.log_event(f"SUCCESS: Tool executed via API: {cmd}")
        if os.name == 'nt':
            os.system(f"start {cmd}")
        return True

    def _native_pick(self, dialog_type):
        """دیالوگ بومی ویندوز (pywebview) — مسیر انتخاب‌شده یا None."""
        try:
            import webview
            if webview.windows:
                picked = webview.windows[0].create_file_dialog(dialog_type)
                if picked:
                    first = picked[0]
                    # در pywebview نسخه‌های قدیمی، ورودی اول (نام، مسیر) است
                    if isinstance(first, (tuple, list)) and len(first) > 1:
                        first = first[1]
                    return first
        except Exception as e:
            backend_server.log_event(f"Webview browse failed: {e}")
        return None

    def _tk_pick(self, mode="folder"):
        """دیالوگ tkinter — وقتی pywebview در دسترس نیست (fallback).

        از _pick_path بک‌اند استفاده می‌کند (دیالوگ tkinter یکسان) تا
        کد تکراری ننویسیم؛ هر استثنایی (مثلاً بدون نمایشگر/نشست GUI)
        به‌جای نشت به فرانت، None برمی‌گرداند.
        """
        try:
            return backend_server._pick_path(mode) or None
        except Exception as e:
            backend_server.log_event(f"Tk browse failed: {e}")
            return None

    def browse_folder(self):
        """انتخاب پوشه با دیالوگ بومی (دکمهٔ مرور در توسعه نرم‌افزار)."""
        if not HAS_WEBVIEW:
            return self._tk_pick("folder")
        return self._native_pick(webview.FOLDER_DIALOG) or None

    def browse_file(self):
        """انتخاب فایل با دیالوگ بومی."""
        if not HAS_WEBVIEW:
            return self._tk_pick("file")
        return self._native_pick(webview.OPEN_DIALOG) or None

    def open_log(self):
        log_file = backend_server.LOG_FILE
        if not os.path.exists(log_file):
            with open(log_file, "w", encoding="utf-8") as f:
                f.write("=== PC Repair Toolbox Pro & AI Agent Log ===\n")
        if os.name == 'nt':
            os.system(f"notepad.exe {log_file}")
        return True

def _prepare_webview_storage():
    """
    یک پوشه داده پایدار و کاملاً ASCII برای WebView2 آماده می‌کند.

    چرا لازم است؟
      pywebview به‌صورت پیش‌فرض یک پوشه موقت تصادفی در %TEMP% می‌سازد.
      این باعث دو مشکل می‌شود:

      ۱. اگر نام کاربری ویندوز کاراکتر غیرانگلیسی داشته باشد (مثلاً فارسی)،
         مسیر به شکل کوتاه 8.3 در می‌آید (C:\\Users\\MF4CE~1.GAZ\\...) و
         موتور WebView2 نمی‌تواند در آن بنویسد →
         خطای «We couldn't create the data directory»

      ۲. با uac_admin=True فرآیند بالا می‌آید و %TEMP% به مسیر دیگری
         اشاره می‌کند که ممکن است دسترسی نوشتن نداشته باشد.

    راه‌حل: مسیری که هیچ‌وقت نام کاربری در آن نیست و همیشه ASCII است.
    """
    candidates = []

    if os.name == 'nt':
        # ProgramData همیشه ASCII است و با دسترسی ادمین قابل نوشتن
        pd = os.environ.get("ProgramData")
        if pd:
            candidates.append(os.path.join(pd, "PCRepairToolbox", "WebView2"))
        # ریشه درایو سیستم — آخرین راه مطمئن
        sysdrive = os.environ.get("SystemDrive", "C:")
        candidates.append(os.path.join(sysdrive + "\\", "PCRepairToolbox", "WebView2"))
        # LOCALAPPDATA فقط اگر کاملاً ASCII باشد
        lad = os.environ.get("LOCALAPPDATA")
        if lad and lad.isascii():
            candidates.append(os.path.join(lad, "PCRepairToolbox", "WebView2"))
    else:
        candidates.append(os.path.join(os.path.expanduser("~"), ".pcrepairtoolbox", "webview"))

    for path in candidates:
        try:
            if not path.isascii():
                continue
            os.makedirs(path, exist_ok=True)
            probe = os.path.join(path, ".writetest")
            with open(probe, "w") as f:
                f.write("ok")
            os.remove(probe)
            # WebView2 این متغیر محیطی را مستقیماً می‌خواند
            os.environ["WEBVIEW2_USER_DATA_FOLDER"] = path
            backend_server.log_event(f"WebView2 data folder: {path}")
            return path
        except Exception as e:
            backend_server.log_event(f"WebView2 folder unusable ({path}): {e}")
            continue

    backend_server.log_event("WARNING: no writable WebView2 folder found; using default.")
    return None


def open_in_browser():
    """اگر پنجره داخلی بالا نیامد، رابط را در مرورگر پیش‌فرض باز می‌کند."""
    import webbrowser
    url = f"http://127.0.0.1:{backend_server.PORT}/"
    backend_server.log_event(f"Falling back to system browser: {url}")
    try:
        webbrowser.open(url)
    except Exception as e:
        backend_server.log_event(f"Browser fallback failed: {e}")
        print(f"\nرابط کاربری در این آدرس در دسترس است:\n  {url}\n")

    # در حالت --noconsole هیچ کنسولی نیست، پس کاربر باید بداند چه خبر است
    if getattr(sys, 'frozen', False) and os.name == 'nt':
        try:
            import ctypes
            ctypes.windll.user32.MessageBoxW(
                None,
                "پنجره داخلی برنامه اجرا نشد، بنابراین رابط کاربری در مرورگر "
                f"پیش‌فرض شما باز شد:\n\n{url}\n\n"
                "این پیام را باز نگه دارید — با بستن آن، برنامه خاتمه می‌یابد.",
                "PC Repair Toolbox Pro",
                0x40  # MB_ICONINFORMATION
            )
            return  # کاربر OK زد → خروج تمیز
        except Exception:
            pass

    # سرور باید زنده بماند وگرنه مرورگر صفحه خالی نشان می‌دهد
    try:
        sys.stdout.write(f"[PC Repair Toolbox] در حال اجرا: {url}\n")
        sys.stdout.write("برای بستن برنامه Ctrl+C بزنید.\n")
        sys.stdout.flush()
    except Exception:
        pass
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass


def run_webview_app():
    start_backend_thread()
    storage = _prepare_webview_storage()
    api = WebviewApi()

    try:
        kwargs = dict(
            url=f"http://127.0.0.1:{backend_server.PORT}/",
            js_api=api,
            width=1250,
            height=850,
        )
        # storage_path در pywebview 4+ پشتیبانی می‌شود
        if storage:
            try:
                webview.create_window(
                    "PC Repair Toolbox Pro + AI Agent - عیب‌یاب هوشمند ویندوز",
                    **kwargs
                )
                webview.start(private_mode=False, storage_path=storage)
                return
            except TypeError:
                # نسخه قدیمی‌تر pywebview این آرگومان‌ها را ندارد
                pass
            except Exception as e:
                backend_server.log_event(f"WebView2 start with storage_path failed: {e}")

        # تلاش دوم: بدون آرگومان‌های اضافه
        webview.create_window(
            "PC Repair Toolbox Pro + AI Agent - عیب‌یاب هوشمند ویندوز",
            **kwargs
        )
        webview.start()

    except Exception as e:
        backend_server.log_event(f"WebView engine failed: {e}")
        print(f"[هشدار] موتور WebView2 اجرا نشد: {e}")
        open_in_browser()


# PYQT6 ENGINE WITH RTL (PRIORITY 2)
if HAS_PYQT:
    class ToolCardPyQt(QFrame):
        def __init__(self, tool_data, parent_window):
            super().__init__()
            self.tool = tool_data
            self.parent_window = parent_window
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.init_ui()

        def init_ui(self):
            self.setStyleSheet("""
                QFrame {
                    background-color: #1e293b;
                    border: 1px solid #334155;
                    border-radius: 14px;
                    padding: 12px;
                }
                QFrame:hover { border: 1px solid #3b82f6; background-color: #24334a; }
            """)

            layout = QVBoxLayout()
            layout.setSpacing(6)

            badge_layout = QHBoxLayout()
            badge_layout.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            if self.tool['badge_admin']:
                lbl_admin = QLabel("🛡 Admin")
                lbl_admin.setStyleSheet("color: #f87171; background: rgba(239, 68, 68, 0.2); padding: 2px 6px; border-radius: 6px; font-size: 10px;")
                badge_layout.addWidget(lbl_admin)
            if self.tool['badge_may_vary']:
                lbl_vary = QLabel("⚠️ May Vary")
                lbl_vary.setStyleSheet("color: #fbbf24; background: rgba(245, 158, 11, 0.2); padding: 2px 6px; border-radius: 6px; font-size: 10px;")
                badge_layout.addWidget(lbl_vary)
            badge_layout.addStretch()
            layout.addLayout(badge_layout)

            lbl_fa = QLabel(self.tool['name_fa'])
            lbl_fa.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_fa.setStyleSheet("color: white; font-weight: bold; font-size: 15px;")
            layout.addWidget(lbl_fa)

            lbl_en = QLabel(self.tool['name_en'])
            lbl_en.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_en.setStyleSheet("color: #60a5fa; font-size: 11px; font-family: monospace;")
            layout.addWidget(lbl_en)

            lbl_desc = QLabel(self.tool['desc'])
            lbl_desc.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_desc.setWordWrap(True)
            lbl_desc.setStyleSheet("color: #94a3b8; font-size: 11px; line-height: 1.5;")
            layout.addWidget(lbl_desc)

            layout.addStretch()

            btn_run = QPushButton("▶ اجرای ابزار")
            btn_run.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1:0, y1:0, x2:1, y2:1, stop:0 #2563eb, stop:1 #1d4ed8);
                    color: white;
                    border-radius: 8px;
                    padding: 8px;
                    font-weight: bold;
                    font-size: 12px;
                }
                QPushButton:hover { background: #3b82f6; }
            """)
            btn_run.clicked.connect(self.run_tool)
            layout.addWidget(btn_run)

            btn_guide = QPushButton("📖 راهنما و آموزش")
            btn_guide.setStyleSheet("""
                QPushButton {
                    background-color: rgba(255,255,255,0.05);
                    color: #94a3b8;
                    border: 1px solid #334155;
                    border-radius: 8px;
                    padding: 6px;
                    font-size: 11px;
                }
                QPushButton:hover { background-color: rgba(255,255,255,0.1); color: white; }
            """)
            btn_guide.clicked.connect(self.show_guide)
            layout.addWidget(btn_guide)

            self.setLayout(layout)

        def run_tool(self):
            cmd = self.tool['command']
            backend_server.log_event(f"SUCCESS: Tool executed: {cmd}")
            if os.name == 'nt':
                os.system(f"start {cmd}")
            else:
                QMessageBox.information(self, "اجرای ابزار", f"دستور زیر در ویندوز اجرا می‌شود:\n\n{cmd}")

        def show_guide(self):
            dialog = GuideDialogPyQt(self.tool, self)
            dialog.exec()

    class GuideDialogPyQt(QDialog):
        def __init__(self, tool, parent=None):
            super().__init__(parent)
            self.tool = tool
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.setWindowTitle(f"راهنما: {tool['name_fa']}")
            self.setMinimumSize(600, 500)
            self.setStyleSheet("background-color: #0f172a; color: white;")
            self.init_ui()

        def init_ui(self):
            layout = QVBoxLayout()
            layout.setSpacing(12)

            title = QLabel(f"{self.tool['name_fa']} ({self.tool['name_en']})")
            title.setAlignment(Qt.AlignmentFlag.AlignRight)
            title.setStyleSheet("font-size: 18px; font-weight: bold; color: #38bdf8;")
            layout.addWidget(title)

            cat = QLabel(f"دسته‌بندی: {self.tool['category_fa']}")
            cat.setAlignment(Qt.AlignmentFlag.AlignRight)
            cat.setStyleSheet("color: #94a3b8; font-size: 12px;")
            layout.addWidget(cat)

            layout.addWidget(QLabel("📌 شرح و کارکرد اصلی:"))
            desc = QTextEdit()
            desc.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            desc.setPlainText(self.tool['desc'])
            desc.setReadOnly(True)
            desc.setStyleSheet("background-color: #1e293b; color: #e2e8f0; border-radius: 8px; border: 1px solid #334155;")
            desc.setMaximumHeight(70)
            layout.addWidget(desc)

            layout.addWidget(QLabel("💻 دستور اجرای مستقیم ویندوز:"))
            cmd = QLineEdit(self.tool['command'])
            cmd.setReadOnly(True)
            cmd.setStyleSheet("background-color: #1e293b; color: #38bdf8; font-family: monospace; border-radius: 6px; padding: 6px;")
            layout.addWidget(cmd)

            layout.addWidget(QLabel("📑 نحوه کار و آموزش قدم به قدم:"))
            guide = QTextEdit()
            guide.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            guide.setPlainText(self.tool['guide'])
            guide.setReadOnly(True)
            guide.setStyleSheet("background-color: #1e293b; color: #e2e8f0; border-radius: 8px; border: 1px solid #334155;")
            layout.addWidget(guide)

            layout.addWidget(QLabel("⚠️ نکات ایمنی و هشدارها:"))
            warn = QTextEdit()
            warn.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            warn.setPlainText(self.tool['warning'])
            warn.setReadOnly(True)
            warn.setStyleSheet("background-color: rgba(239, 68, 68, 0.1); color: #fca5a5; border-radius: 8px; border: 1px solid #ef4444;")
            warn.setMaximumHeight(70)
            layout.addWidget(warn)

            btn_run = QPushButton("🚀 اجرای مستقیم این ابزار در ویندوز")
            btn_run.setStyleSheet("background-color: #2563eb; color: white; padding: 10px; font-weight: bold; border-radius: 8px;")
            btn_run.clicked.connect(self.run_tool)
            layout.addWidget(btn_run)

            self.setLayout(layout)

        def run_tool(self):
            cmd = self.tool['command']
            if os.name == 'nt':
                os.system(f"start {cmd}")
            else:
                QMessageBox.information(self, "اجرای ابزار", f"دستور زیر در ویندوز اجرا می‌شود:\n\n{cmd}")

    class MainWindowPyQt(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.setWindowTitle("PC Repair Toolbox Pro + AI Agent - عیب‌یاب هوشمند ویندوز")
            self.resize(1150, 780)
            self.setStyleSheet("background-color: #0b1120; color: white;")
            self.init_ui()

        def init_ui(self):
            sidebar = QFrame()
            sidebar.setFixedWidth(220)
            sidebar.setStyleSheet("background-color: #0f172a; border-left: 1px solid #1e293b;")
            sb_layout = QVBoxLayout()

            lbl_brand = QLabel("PC Repair & AI\nPro (42 Tools)")
            lbl_brand.setAlignment(Qt.AlignmentFlag.AlignRight)
            lbl_brand.setStyleSheet("font-size: 16px; font-weight: bold; color: #38bdf8; margin-bottom: 20px;")
            sb_layout.addWidget(lbl_brand)

            btn_all = QPushButton("🌐 تمامی ابزارها")
            btn_all.setStyleSheet("text-align: right; background-color: #1e293b; color: #38bdf8; padding: 8px; border-radius: 6px; font-weight: bold;")
            btn_all.clicked.connect(lambda: self.filter_category("all"))
            sb_layout.addWidget(btn_all)

            categories = [
                ("Apps & Features", "📦 برنامه‌ها و قابلیت‌ها"),
                ("Advanced", "⚙️ تنظیمات پیشرفته"),
                ("Security", "🛡 امنیتی و دسترسی‌ها"),
                ("System Tools", "🛠 ابزارهای مدیریتی"),
                ("Performance", "🚀 ارتقای عملکرد"),
                ("Repair Windows", "🩺 تعمیر و بازگردانی"),
                ("Network", "🌐 شبکه و اینترنت"),
                ("Clean & Storage", "🧹 پاک‌سازی و حافظه")
            ]

            for cat_en, cat_fa in categories:
                btn = QPushButton(cat_fa)
                btn.setStyleSheet("""
                    QPushButton {
                        text-align: right;
                        background-color: transparent;
                        color: #94a3b8;
                        padding: 8px;
                        border-radius: 6px;
                    }
                    QPushButton:hover { background-color: #1e293b; color: #38bdf8; }
                """)
                btn.clicked.connect(lambda checked, c=cat_en: self.filter_category(c))
                sb_layout.addWidget(btn)

            sb_layout.addStretch()
            sidebar.setLayout(sb_layout)

            right_panel = QVBoxLayout()

            search_box = QHBoxLayout()
            self.search_input = QLineEdit()
            self.search_input.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.search_input.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.search_input.setPlaceholderText("🔎 جستجوی نام ابزار یا دستور ویندوز...")
            self.search_input.setStyleSheet("background-color: #1e293b; color: white; padding: 10px; border-radius: 20px; border: 1px solid #334155;")
            self.search_input.textChanged.connect(self.populate_tools)
            search_box.addWidget(self.search_input)
            right_panel.addLayout(search_box)

            scroll = QScrollArea()
            scroll.setWidgetResizable(True)
            scroll.setStyleSheet("border: none; background-color: transparent;")

            self.grid_widget = QWidget()
            self.grid_widget.setLayoutDirection(Qt.LayoutDirection.RightToLeft)
            self.grid_layout = QGridLayout()
            self.grid_layout.setSpacing(15)
            self.grid_widget.setLayout(self.grid_layout)
            scroll.setWidget(self.grid_widget)

            right_panel.addWidget(scroll)

            container = QWidget()
            c_layout = QHBoxLayout()
            c_layout.addWidget(sidebar)
            c_layout.addLayout(right_panel)
            container.setLayout(c_layout)
            self.setCentralWidget(container)

            self.current_category = "all"
            self.populate_tools()

        def filter_category(self, cat):
            self.current_category = cat
            self.populate_tools()

        def populate_tools(self):
            for i in reversed(range(self.grid_layout.count())): 
                widget = self.grid_layout.itemAt(i).widget()
                if widget:
                    widget.setParent(None)

            search_query = self.search_input.text().lower().strip()

            row, col = 0, 0
            for tool in TOOLS_DATA:
                if self.current_category != "all" and tool['category_en'] != self.current_category:
                    continue

                if search_query:
                    match = (search_query in tool['name_fa'].lower() or 
                             search_query in tool['name_en'].lower() or 
                             search_query in tool['command'].lower() or
                             search_query in tool['category_fa'].lower())
                    if not match:
                        continue

                card = ToolCardPyQt(tool, self)
                self.grid_layout.addWidget(card, row, col)
                col += 1
                if col >= 3:
                    col = 0
                    row += 1


# TKINTER FALLBACK (PRIORITY 3)
class TkAppRTL(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("PC Repair Toolbox Pro + AI Agent - عیب‌یاب هوشمند ویندوز")
        self.geometry("1150x750")
        self.configure(bg="#0b1120")

        self.current_category = "all"
        self.init_ui()

    def init_ui(self):
        main_frame = tk.Frame(self, bg="#0b1120")
        main_frame.pack(fill=tk.BOTH, expand=True)

        sidebar = tk.Frame(main_frame, bg="#0f172a", width=250, relief=tk.FLAT, bd=0)
        sidebar.pack(side=tk.RIGHT, fill=tk.Y, padx=0, pady=0)

        title_lbl = tk.Label(sidebar, text="PC Repair & AI\nPro (42 Tools)", font=("Segoe UI", 13, "bold"), fg="#38bdf8", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        title_lbl.pack(fill=tk.X, padx=15, pady=20)

        btn_all = tk.Button(sidebar, text="🌐 تمامی ابزارها", font=("Segoe UI", 10, "bold"), fg="#38bdf8", bg="#1e293b", activebackground="#334155", activeforeground="white", bd=0, relief=tk.FLAT, command=lambda: self.filter_cat("all"), anchor="e")
        btn_all.pack(fill=tk.X, padx=10, pady=4)

        categories = [
            ("Apps & Features", "📦 برنامه‌ها و قابلیت‌ها"),
            ("Advanced", "⚙️ تنظیمات پیشرفته"),
            ("Security", "🛡 امنیتی و دسترسی‌ها"),
            ("System Tools", "🛠 ابزارهای مدیریتی"),
            ("Performance", "🚀 ارتقای عملکرد"),
            ("Repair Windows", "🩺 تعمیر و بازگردانی"),
            ("Network", "🌐 شبکه و اینترنت"),
            ("Clean & Storage", "🧹 پاک‌سازی و حافظه")
        ]

        for cat_en, cat_fa in categories:
            btn = tk.Button(sidebar, text=cat_fa, font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a", activebackground="#1e293b", activeforeground="#38bdf8", bd=0, relief=tk.FLAT, command=lambda c=cat_en: self.filter_cat(c), anchor="e")
            btn.pack(fill=tk.X, padx=10, pady=2)

        right_panel = tk.Frame(main_frame, bg="#0b1120")
        right_panel.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=15, pady=15)

        search_frame = tk.Frame(right_panel, bg="#1e293b", bd=1, relief=tk.SOLID)
        search_frame.pack(fill=tk.X, pady=(0, 15))

        self.search_var = tk.StringVar()
        self.search_var.trace("w", lambda *args: self.populate())

        search_entry = tk.Entry(search_frame, textvariable=self.search_var, font=("Segoe UI", 11), bg="#1e293b", fg="white", insertbackground="white", bd=0, justify=tk.RIGHT)
        search_entry.pack(fill=tk.X, padx=12, pady=8)

        canvas = tk.Canvas(right_panel, bg="#0b1120", highlightthickness=0)
        scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=canvas.yview)
        self.scroll_frame = tk.Frame(canvas, bg="#0b1120")

        self.scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=self.scroll_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.populate()

    def filter_cat(self, cat):
        self.current_category = cat
        self.populate()

    def populate(self):
        for widget in self.scroll_frame.winfo_children():
            widget.destroy()

        search_q = self.search_var.get().lower().strip()

        row, col = 0, 0
        for tool in TOOLS_DATA:
            if self.current_category != "all" and tool['category_en'] != self.current_category:
                continue

            if search_q:
                match = (search_q in tool['name_fa'].lower() or 
                         search_q in tool['name_en'].lower() or 
                         search_q in tool['command'].lower() or
                         search_q in tool['category_fa'].lower())
                if not match:
                    continue

            card = tk.Frame(self.scroll_frame, bg="#1e293b", bd=1, relief=tk.SOLID, width=250, height=200)
            card.grid(row=row, column=col, padx=10, pady=10, sticky="nsew")

            lbl_fa = tk.Label(card, text=tool['name_fa'], font=("Segoe UI", 11, "bold"), fg="white", bg="#1e293b", anchor="e", justify=tk.RIGHT)
            lbl_fa.pack(fill=tk.X, padx=10, pady=(10, 2))

            lbl_en = tk.Label(card, text=tool['name_en'], font=("Consolas", 8), fg="#60a5fa", bg="#1e293b", anchor="e", justify=tk.RIGHT)
            lbl_en.pack(fill=tk.X, padx=10, pady=(0, 6))

            lbl_desc = tk.Label(card, text=tool['desc'], font=("Segoe UI", 8), fg="#94a3b8", bg="#1e293b", wraplength=230, justify=tk.RIGHT, anchor="e")
            lbl_desc.pack(fill=tk.X, padx=10, pady=(0, 10))

            btn_run = tk.Button(card, text="▶ اجرای ابزار", font=("Segoe UI", 9, "bold"), fg="white", bg="#2563eb", activebackground="#3b82f6", activeforeground="white", bd=0, command=lambda t=tool: self.run_tool(t))
            btn_run.pack(fill=tk.X, padx=10, pady=3)

            btn_guide = tk.Button(card, text="📖 راهنما و آموزش", font=("Segoe UI", 8), fg="#e2e8f0", bg="#334155", activebackground="#475569", activeforeground="white", bd=0, command=lambda t=tool: self.show_guide(t))
            btn_guide.pack(fill=tk.X, padx=10, pady=(0, 10))

            col += 1
            if col >= 3:
                col = 0
                row += 1

    def run_tool(self, tool):
        cmd = tool['command']
        backend_server.log_event(f"SUCCESS: Tool executed: {cmd}")
        if os.name == 'nt':
            os.system(f"start {cmd}")
        else:
            messagebox.showinfo("اجرای ابزار", f"دستور زیر در ویندوز اجرا می‌شود:\n\n{cmd}")

    def show_guide(self, tool):
        top = tk.Toplevel(self)
        top.title(f"راهنما: {tool['name_fa']}")
        top.geometry("600x550")
        top.configure(bg="#0f172a")

        lbl_title = tk.Label(top, text=f"{tool['name_fa']} ({tool['name_en']})", font=("Segoe UI", 13, "bold"), fg="#38bdf8", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        lbl_title.pack(fill=tk.X, padx=15, pady=(15, 5))

        lbl_cat = tk.Label(top, text=f"دسته‌بندی: {tool['category_fa']}", font=("Segoe UI", 9), fg="#94a3b8", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        lbl_cat.pack(fill=tk.X, padx=15, pady=(0, 10))

        lbl_d_head = tk.Label(top, text="📌 شرح و کارکرد اصلی:", font=("Segoe UI", 9, "bold"), fg="white", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        lbl_d_head.pack(fill=tk.X, padx=15)

        txt_desc = tk.Text(top, height=3, font=("Segoe UI", 9), bg="#1e293b", fg="#e2e8f0", bd=0, padx=8, pady=8)
        txt_desc.insert(tk.END, tool['desc'])
        txt_desc.config(state=tk.DISABLED)
        txt_desc.pack(fill=tk.X, padx=15, pady=(2, 10))

        lbl_c_head = tk.Label(top, text="💻 دستور اجرای مستقیم ویندوز:", font=("Segoe UI", 9, "bold"), fg="white", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        lbl_c_head.pack(fill=tk.X, padx=15)

        ent_cmd = tk.Entry(top, font=("Consolas", 10), bg="#1e293b", fg="#38bdf8", bd=0, justify=tk.RIGHT)
        ent_cmd.insert(0, tool['command'])
        ent_cmd.config(state="readonly")
        ent_cmd.pack(fill=tk.X, padx=15, pady=(2, 10))

        lbl_g_head = tk.Label(top, text="📑 نحوه کار و آموزش قدم به قدم:", font=("Segoe UI", 9, "bold"), fg="white", bg="#0f172a", justify=tk.RIGHT, anchor="e")
        lbl_g_head.pack(fill=tk.X, padx=15)

        txt_guide = scrolledtext.ScrolledText(top, height=8, font=("Segoe UI", 9), bg="#1e293b", fg="#e2e8f0", bd=0, padx=8, pady=8)
        txt_guide.insert(tk.END, tool['guide'])
        txt_guide.config(state=tk.DISABLED)
        txt_guide.pack(fill=tk.X, padx=15, pady=(2, 10))

        btn_r = tk.Button(top, text="🚀 اجرای مستقیم این ابزار در ویندوز", font=("Segoe UI", 10, "bold"), fg="white", bg="#2563eb", activebackground="#3b82f6", activeforeground="white", bd=0, command=lambda: self.run_tool(tool))
        btn_r.pack(fill=tk.X, padx=15, pady=15)


def main():
    """
    ترتیب انتخاب موتور رابط کاربری، با fallback در هر مرحله.
    اگر همه شکست بخورند، رابط در مرورگر پیش‌فرض باز می‌شود تا
    برنامه هرگز بدون پنجره نماند.

    پرچم‌های خط فرمان:
        --browser   مستقیماً در مرورگر باز کن (دور زدن WebView2)
        --tk        استفاده از موتور Tkinter
    """
    args = [a.lower() for a in sys.argv[1:]]

    if "--browser" in args or os.environ.get("PCRT_BROWSER") == "1":
        start_backend_thread()
        open_in_browser()
        return

    if "--tk" in args:
        start_backend_thread()
        TkAppRTL().mainloop()
        return

    if HAS_WEBVIEW:
        try:
            run_webview_app()
            return
        except Exception as e:
            backend_server.log_event(f"Webview engine crashed: {e}")

    if HAS_PYQT:
        try:
            start_backend_thread()
            app = QApplication(sys.argv)
            window = MainWindowPyQt()
            window.show()
            sys.exit(app.exec())
        except SystemExit:
            raise
        except Exception as e:
            backend_server.log_event(f"PyQt6 engine failed: {e}")

    try:
        start_backend_thread()
        app = TkAppRTL()
        app.mainloop()
        return
    except Exception as e:
        backend_server.log_event(f"Tkinter engine failed: {e}")

    # آخرین راه: مرورگر سیستم
    start_backend_thread()
    open_in_browser()


if __name__ == "__main__":
    main()
