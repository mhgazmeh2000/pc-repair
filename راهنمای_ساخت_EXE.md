# 📦 راهنمای ساخت فایل اجرایی (EXE) و اجرای برنامه

> ⚠️ **مهم:** این مراحل باید روی **ویندوز** انجام شود. PyInstaller cross-compile نمی‌کند — یعنی روی لینوکس یا مک نمی‌توانید `.exe` ویندوزی بسازید.

---

## 🚀 روش سریع (پیشنهادی)

همه فایل‌های پروژه را در **یک پوشه** بگذارید، سپس یکی از این دو را اجرا کنید:

| فایل | نحوه اجرا | توضیح |
|---|---|---|
| **`build.ps1`** ⭐ | راست‌کلیک ← **Run with PowerShell** | پیام‌ها فارسی و رنگی |
| `build.bat` | دابل‌کلیک | پیام‌ها انگلیسی، سازگار با همه ویندوزها |

هر دو یک کار می‌کنند:
1. بررسی نصب بودن پایتون
2. نصب کتابخانه‌های لازم
3. بررسی کامل بودن فایل‌ها
4. پاک‌سازی ساخت قبلی
5. ساخت exe

بعد از ۲ تا ۵ دقیقه، فایل شما اینجاست:
```
dist\PC_Repair_Toolbox_Pro.exe
```

> **چرا `build.bat` انگلیسی است؟**
> `cmd.exe` فایل‌های `.bat` را با کدپیج قدیمی OEM می‌خواند — **قبل از اینکه دستور `chcp 65001` اثر کند**. برای همین متن فارسی داخل `.bat` به کاراکترهای بی‌معنی تبدیل و به‌عنوان دستور اجرا می‌شود. راه‌حل قطعی: نگه داشتن `.bat` به‌صورت کاملاً ASCII. اگر پیام فارسی می‌خواهید، از `build.ps1` استفاده کنید.

### ❌ اگر خطای `'n' is not recognized` دیدید

یعنی نسخه قدیمی `build.bat` (که فارسی داشت) را اجرا کرده‌اید. نسخه جدید را جایگزین کنید — الان کاملاً ASCII است و این خطا رخ نمی‌دهد.

### ❌ اگر PowerShell اجازه اجرا نداد

پیام `execution of scripts is disabled on this system`:
```powershell
powershell -ExecutionPolicy Bypass -File build.ps1
```

---

## 🔧 روش دستی (مرحله‌به‌مرحله)

### پیش‌نیاز: نصب پایتون

اگر پایتون ندارید، از [python.org](https://www.python.org/downloads/) نصب کنید.

> 🔴 **حیاتی:** هنگام نصب حتماً تیک **«Add Python to PATH»** را بزنید. اگر این تیک را نزنید، دستور `python` در CMD شناخته نمی‌شود.

بررسی نصب:
```cmd
python --version
```

---

### گام ۱ — باز کردن CMD در پوشه پروژه

در File Explorer وارد پوشه پروژه شوید، در نوار آدرس بالا `cmd` تایپ کنید و Enter بزنید.

---

### گام ۲ — نصب کتابخانه‌ها

```cmd
pip install -r requirements.txt
```

---

### گام ۳ — تست قبل از ساخت exe

**این مرحله را رد نکنید.** خیلی راحت‌تر است که مشکل را اینجا پیدا کنید تا بعد از ۵ دقیقه build:

```cmd
python pc_toolbox_pro.py
```

اگر پنجره برنامه باز شد ✅ برو به گام بعد.
اگر خطا داد، بخش [عیب‌یابی](#-عیبیابی-مشکلات-رایج) را ببینید.

---

### گام ۴ — ساخت exe

```cmd
pyinstaller pc_toolbox_pro.spec --clean --noconfirm
```

فایل نهایی: `dist\PC_Repair_Toolbox_Pro.exe`

---

## ▶️ اجرای برنامه

روی `PC_Repair_Toolbox_Pro.exe` دابل‌کلیک کنید.

**چه اتفاقی می‌افتد:**
1. پنجره UAC ظاهر می‌شود → **Yes** را بزنید
   *(چون `uac_admin=True` تنظیم شده، ابزارهای SFC و DISM بدون خطا کار می‌کنند)*
2. سرور داخلی روی پورت ۸۰۸۰ بالا می‌آید (اگر اشغال بود، خودکار ۸۰۸۱ یا ۸۰۸۲)
3. پنجره برنامه با رابط کاربری فارسی باز می‌شود

فایل exe **کاملاً مستقل** است — می‌توانید آن را روی هر کامپیوتر ویندوزی کپی کنید، حتی اگر پایتون نصب نباشد.

---

## ⚙️ تنظیمات قابل تغییر در `pc_toolbox_pro.spec`

| تنظیم | مقدار فعلی | توضیح |
|---|---|---|
| `uac_admin=True` | فعال | همیشه با دسترسی ادمین اجرا شود |
| `console=False` | غیرفعال | پنجره سیاه CMD نمایش داده نشود |
| `upx=True` | فعال | فشرده‌سازی برای کاهش حجم |
| `icon='icon.ico'` | کامنت | برای آیکون سفارشی، فایل `icon.ico` بگذارید و کامنت را بردارید |

### کاهش حجم exe

اگر `PyQt6` را لازم ندارید (چون `pywebview` بهتر است)، حجم را حدود **۱۰۰ مگابایت** کم کنید:

۱. در `requirements.txt` خط `PyQt6` را حذف کنید
۲. در `pc_toolbox_pro.spec` به `excludes` اضافه کنید:
```python
excludes=['matplotlib', 'numpy', 'PyQt6', ...]
```

---

## 🛠 عیب‌یابی مشکلات رایج

### ❌ `'python' is not recognized`
پایتون در PATH نیست. پایتون را دوباره نصب کنید و تیک **Add Python to PATH** را بزنید. یا در CMD از `py` به‌جای `python` استفاده کنید.

---

### ❌ `'pyinstaller' is not recognized`
به‌جای آن این را بزنید:
```cmd
python -m PyInstaller pc_toolbox_pro.spec --clean --noconfirm
```

---

### ❌ `ModuleNotFoundError: No module named 'requests'`
```cmd
pip install requests urllib3 PySocks
```
> این مشکل در نسخه اصلی پروژه وجود داشت چون `requests` در `requirements.txt` نبود. الان رفع شده.

---

### ⬜ exe باز می‌شود ولی صفحه سفید است
یعنی فایل HTML داخل exe نیست. مطمئن شوید:
- از فایل `.spec` استفاده می‌کنید (نه دستور ساده `pyinstaller pc_toolbox_pro.py`)
- `pc_toolbox_app.html` و `tools_data.json` کنار فایل‌های پایتون هستند

اگر می‌خواهید بدون `.spec` بسازید، باید `--add-data` را دستی بدهید:
```cmd
pyinstaller --noconsole --onefile --uac-admin ^
  --add-data "pc_toolbox_app.html;." ^
  --add-data "tools_data.json;." ^
  --hidden-import repair_runner ^
  --hidden-import system_inspector ^
  --hidden-import proxy ^
  --hidden-import socks ^
  pc_toolbox_pro.py
```

---

### ⬜ خطای «We couldn't create the data directory»

پیام کامل: *Microsoft Edge can't read and write to its data directory: C:\Users\XXXX~1.YYY\AppData\Local\Temp\...\EBWebView*

**علت:** موتور WebView2 نمی‌تواند در پوشه موقتی که pywebview ساخته بنویسد. معمولاً وقتی رخ می‌دهد که:
- نام کاربری ویندوز کاراکتر غیرانگلیسی (مثلاً فارسی) داشته باشد — ویندوز آن را به شکل کوتاه `MF4CE~1.GAZ` نشان می‌دهد
- برنامه با دسترسی ادمین اجرا شود و `%TEMP%` به مسیر محافظت‌شده اشاره کند

**رفع شده:** برنامه حالا پوشه داده WebView2 را صریحاً روی مسیری پایدار و کاملاً ASCII تنظیم می‌کند:
```
C:\ProgramData\PCRepairToolbox\WebView2
```
و اگر آن هم قابل نوشتن نبود، به `C:\PCRepairToolbox\WebView2` می‌رود.

**اگر باز هم دیدید:** با پرچم مرورگر اجرا کنید:
```cmd
PC_Repair_Toolbox_Pro.exe --browser
```
رابط کاربری در مرورگر پیش‌فرض شما باز می‌شود — تمام قابلیت‌ها کار می‌کنند.

راه دیگر: نصب یا تعمیر **WebView2 Runtime** از سایت مایکروسافت:
`https://developer.microsoft.com/microsoft-edge/webview2/`

---

### 🎛 پرچم‌های خط فرمان

| پرچم | کار |
|---|---|
| `--browser` | باز کردن در مرورگر پیش‌فرض (دور زدن WebView2) |
| `--tk` | استفاده از موتور Tkinter |
| `set SERVER_PORT=9000` | تعیین پورت دلخواه |

---

### 🛡 آنتی‌ویروس exe را قرنطینه می‌کند

این **کاملاً طبیعی** است و مخصوص برنامه شما نیست. فایل‌های PyInstaller با `--onefile` خودشان را در `%TEMP%` باز می‌کنند و این رفتار شبیه بدافزار است (false positive).

راه‌حل‌ها:
- فایل را در Windows Defender به Exclusions اضافه کنید
- برای توزیع عمومی: exe را **کد ساین** کنید (نیاز به گواهی دیجیتال)
- یا از حالت `--onedir` به‌جای `--onefile` استفاده کنید (کمتر مشکوک است)

---

### 🐌 exe کند بالا می‌آید (۳ تا ۱۰ ثانیه)

طبیعی است. حالت `--onefile` هر بار محتوا را در پوشه موقت باز می‌کند. برای اجرای سریع‌تر، در `.spec` حالت `onedir` را استفاده کنید (به‌جای یک فایل، یک پوشه می‌سازد که سریع‌تر اجرا می‌شود).

---

### 🔌 خطای پورت اشغال

دیگر پیش نمی‌آید — برنامه به‌صورت خودکار پورت‌های ۸۰۸۰، ۸۰۸۱، ۸۰۸۲ را امتحان می‌کند و اگر همه اشغال بودند، یک پورت آزاد از سیستم می‌گیرد.

اگر می‌خواهید پورت مشخصی باشد:
```cmd
set SERVER_PORT=9000
PC_Repair_Toolbox_Pro.exe
```

---

## ✅ تست‌های انجام‌شده

برای اطمینان از درستی پیکربندی، این موارد تست شد:

| تست | نتیجه |
|---|---|
| ساخت exe با فایل `.spec` | ✅ موفق |
| `pc_toolbox_app.html` داخل exe | ✅ موجود |
| `tools_data.json` داخل exe | ✅ موجود |
| ماژول‌های `repair_runner`, `proxy`, `system_inspector` | ✅ موجود |
| اجرا در پوشه ایزوله (بدون فایل منبع) | ✅ HTTP 200، ۸۸٬۹۵۳ بایت |
| سرو شدن HTML از داخل exe | ✅ عنوان و محتوا صحیح |
| endpoint `/api/repair_steps` | ✅ ۹ مرحله برگرداند |
| دکمه تعمیر و نوار پیشرفت در HTML | ✅ موجود |
| انتخاب خودکار پورت وقتی ۸۰۸۰ اشغال است | ✅ به ۸۰۸۱ رفت |

---

## 📋 چک‌لیست نهایی قبل از توزیع

- [ ] `python pc_toolbox_pro.py` بدون خطا اجرا می‌شود
- [ ] exe ساخته شده و در `dist\` است
- [ ] exe را در یک **پوشه خالی دیگر** کپی و تست کرده‌اید
- [ ] UAC درست ظاهر می‌شود
- [ ] چند ابزار را تست کرده‌اید (مثلاً Device Manager)
- [ ] دکمه «اجرای خودکار دستورات تعمیراتی» زنجیره را کامل اجرا می‌کند
- [ ] `app_settings.json` را همراه exe توزیع **نمی‌کنید** (حاوی کلید API شماست)

---

## 📁 فایل‌های لازم برای build

```
pc_toolbox_pro.py         ← نقطه ورود
backend_server.py         ← سرور
repair_runner.py          ← موتور زنجیره تعمیر
system_inspector.py       ← تشخیص سیستم
proxy.py                  ← پروکسی AI
pc_toolbox_app.html       ← رابط کاربری  (bundle می‌شود)
tools_data.json           ← داده ۴۲ ابزار (bundle می‌شود)
pc_toolbox_pro.spec       ← پیکربندی build
requirements.txt          ← کتابخانه‌ها
build.bat                 ← اسکریپت خودکار
```
