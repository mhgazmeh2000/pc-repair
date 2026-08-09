# PC Repair Toolbox Pro - EXE Builder (PowerShell)
# اجرا:  راست‌کلیک روی فایل ← Run with PowerShell
# یا در PowerShell:  .\build.ps1
#
# برخلاف فایل .bat، پاورشل با UTF-8 مشکلی ندارد و متن فارسی درست نمایش داده می‌شود.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$Host.UI.RawUI.WindowTitle = "ساخت فایل اجرایی PC Repair Toolbox Pro"

function Write-Step($n, $text) { Write-Host "[$n/5] $text" -ForegroundColor Cyan }
function Write-Ok($text)       { Write-Host "      $text" -ForegroundColor Green }
function Write-Err($text)      { Write-Host "[خطا] $text" -ForegroundColor Red }

Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host "   ساخت فایل اجرایی PC Repair Toolbox Pro" -ForegroundColor Yellow
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""

# ---------- ۱. بررسی پایتون ----------
$py = $null
foreach ($cmd in @("python", "py")) {
    try {
        $v = & $cmd --version 2>&1
        if ($LASTEXITCODE -eq 0) { $py = $cmd; $pyver = $v; break }
    } catch { }
}

if (-not $py) {
    Write-Err "پایتون پیدا نشد."
    Write-Host ""
    Write-Host "  پایتون را از این آدرس نصب کنید:" -ForegroundColor White
    Write-Host "  https://www.python.org/downloads/" -ForegroundColor White
    Write-Host ""
    Write-Host "  مهم: هنگام نصب حتماً تیک «Add Python to PATH» را بزنید." -ForegroundColor Yellow
    Write-Host ""
    Read-Host "برای خروج Enter بزنید"
    exit 1
}
Write-Step 1 "پایتون شناسایی شد: $pyver"
Write-Host ""

# ---------- ۲. نصب کتابخانه‌ها ----------
Write-Step 2 "در حال نصب کتابخانه‌های مورد نیاز..."
& $py -m pip install --upgrade pip --quiet
& $py -m pip install -r requirements.txt --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Err "نصب کتابخانه‌ها ناموفق بود. اتصال اینترنت را بررسی کنید."
    Read-Host "برای خروج Enter بزنید"
    exit 1
}
Write-Ok "نصب کامل شد."
Write-Host ""

# ---------- ۳. بررسی فایل‌ها ----------
Write-Step 3 "بررسی فایل‌های پروژه..."
$required = @(
    "pc_toolbox_pro.py", "backend_server.py", "repair_runner.py",
    "command_guard.py", "gpu_inspector.py", "system_query.py", "database.py", "providers.py", "model_info.py", "attachments.py", "chat_memory.py", "system_inspector.py", "proxy.py",
    # ماژول‌های امنیت و عیب‌یابی پیشرفته
    "security.py", "health_metrics.py", "local_diagnosis.py", "baseline.py",
    "restore_point.py", "repair_history.py", "event_catalog.py",
    # تب توسعهٔ نرم‌افزار
    "workspace.py", "code_changes.py",
    "pc_toolbox_app.html", "tools_data.json", "pc_toolbox_pro.spec"
)
$missing = $required | Where-Object { -not (Test-Path $_) }
if ($missing) {
    Write-Err "فایل‌های زیر موجود نیستند:"
    $missing | ForEach-Object { Write-Host "      • $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "  همه فایل‌ها باید در یک پوشه باشند." -ForegroundColor Yellow
    Read-Host "برای خروج Enter بزنید"
    exit 1
}
Write-Ok "هر $($required.Count) فایل موجود است."
Write-Host ""

# ---------- ۳ب. بررسی پیکربندی ساخت ----------
# PyInstaller فقط importهای فایل اصلی را دنبال می‌کند. ماژول‌هایی که
# backend_server وارد می‌کند اگر در hiddenimports نباشند، exe روی
# سیستم کاربر با ImportError می‌افتد.
Write-Host "      بررسی پیکربندی ساخت..." -ForegroundColor Gray
& $PYCMD tests_build.py
if ($LASTEXITCODE -ne 0) {
    Write-Err "بررسی پیکربندی ناموفق بود. موارد بالا را رفع کنید."
    Read-Host "برای خروج Enter بزنید"
    exit 1
}
Write-Host ""

# ---------- ۴. پاک‌سازی ----------
Write-Step 4 "پاک‌سازی فایل‌های ساخت قبلی..."
foreach ($d in @("build", "dist")) {
    if (Test-Path $d) { Remove-Item $d -Recurse -Force }
}
Write-Ok "انجام شد."
Write-Host ""

# ---------- ۵. ساخت exe ----------
Write-Step 5 "در حال ساخت فایل اجرایی..."
Write-Host "      (این مرحله ۲ تا ۵ دقیقه طول می‌کشد، صبور باشید)" -ForegroundColor DarkGray
Write-Host ""

& $py -m PyInstaller pc_toolbox_pro.spec --clean --noconfirm
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Err "ساخت exe ناموفق بود. متن خطای بالا را بررسی کنید."
    Read-Host "برای خروج Enter بزنید"
    exit 1
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Yellow
$exe = "dist\PC_Repair_Toolbox_Pro.exe"
if (Test-Path $exe) {
    $sizeMB = [math]::Round((Get-Item $exe).Length / 1MB, 1)
    Write-Host "   ✅ ساخت با موفقیت انجام شد!" -ForegroundColor Green
    Write-Host ""
    Write-Host "   فایل : $exe" -ForegroundColor White
    Write-Host "   حجم  : $sizeMB مگابایت" -ForegroundColor White
    Write-Host ""
    Write-Host "   این فایل مستقل است. می‌توانید آن را روی دسکتاپ" -ForegroundColor White
    Write-Host "   یا هر کامپیوتر ویندوزی دیگر کپی کنید." -ForegroundColor White
} else {
    Write-Host "   ⚠️ فایل exe ساخته نشد. خروجی بالا را بررسی کنید." -ForegroundColor Red
}
Write-Host "============================================================" -ForegroundColor Yellow
Write-Host ""
Read-Host "برای بستن Enter بزنید"
