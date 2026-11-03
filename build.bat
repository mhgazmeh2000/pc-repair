@echo off
setlocal enabledelayedexpansion
title Build PC Repair Toolbox Pro

REM Always run from the folder that contains THIS script, even when
REM the user starts it from another directory (Explorer, cmd, ...).
REM All project files must sit next to build.bat.
cd /d "%~dp0"

echo ============================================================
echo    PC Repair Toolbox Pro - EXE Builder
echo ============================================================
echo.

REM ---------- Step 1: Check Python ----------
set PYCMD=python
%PYCMD% --version >nul 2>&1
if errorlevel 1 (
    set PYCMD=py
    !PYCMD! --version >nul 2>&1
    if errorlevel 1 (
        echo [ERROR] Python not found.
        echo.
        echo Install Python from https://www.python.org/downloads/
        echo IMPORTANT: check "Add Python to PATH" during setup.
        echo.
        pause
        exit /b 1
    )
)
for /f "tokens=2" %%v in ('%PYCMD% --version 2^>^&1') do set PYVER=%%v
echo [1/5] Python %PYVER% found.
echo.

REM ---------- Step 2: Install dependencies ----------
echo [2/5] Installing required packages...
REM pip upgrade is skipped on purpose: it is not required and often
REM times out behind a filtered connection, wasting 75+ seconds.
REM
REM Two tiers of packages:
REM   REQUIRED  = requests, urllib3, PyInstaller, webview, win32crypt
REM               (without these the EXE cannot be built or run properly)
REM   OPTIONAL  = socks (PySocks) - only needed for the SOCKS proxy
REM               feature. The app runs fine without it (direct connection),
REM               so a missing PySocks must NEVER abort the build.
REM
REM If everything is already installed, we skip the network entirely.
%PYCMD% -c "import requests, urllib3, PyInstaller, webview, win32crypt" >nul 2>&1
set REQOK=0
if not errorlevel 1 set REQOK=1
%PYCMD% -c "import socks" >nul 2>&1
set SOCKSOK=0
if not errorlevel 1 set SOCKSOK=1

if !REQOK!==1 if !SOCKSOK!==1 (
    echo       All packages already installed - skipping download.
    goto :deps_ok
)
if !REQOK!==1 if !SOCKSOK!==0 (
    echo       Required packages present. Optional PySocks missing - will try to fetch.
)

echo       Some packages missing. Downloading...
%PYCMD% -m pip install -r requirements.txt --quiet --disable-pip-version-check
if errorlevel 1 (
    echo.
    echo [WARNING] Package installation had errors.
    echo           This is usually a network/firewall issue.
    echo.
)

REM Re-check ONLY the required packages after the install attempt.
%PYCMD% -c "import requests, urllib3, PyInstaller, webview, win32crypt" >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Required packages are missing. Cannot continue.
    echo         Install manually:
    echo             pip install requests urllib3 pyinstaller pywebview pywin32
    pause
    exit /b 1
)

REM Optional PySocks: warn but continue if still absent.
%PYCMD% -c "import socks" >nul 2>&1
if errorlevel 1 (
    echo.
    echo [NOTE] PySocks is not installed. The SOCKS5 proxy option will be
    echo        unavailable, but the app works over a direct/HTTP connection.
    echo        To enable it later:  pip install PySocks
    echo.
) else (
    echo       All packages present - continuing.
)
:deps_ok
echo       Done.
echo.

REM ---------- Step 3: Verify project files ----------
echo [3/5] Verifying project files...
set MISSING=0
for %%f in (pc_toolbox_pro.py backend_server.py repair_runner.py command_guard.py gpu_inspector.py system_query.py database.py providers.py model_info.py attachments.py chat_memory.py system_inspector.py proxy.py security.py health_metrics.py local_diagnosis.py baseline.py restore_point.py repair_history.py event_catalog.py workspace.py code_changes.py pc_toolbox_app.html tools_data.json pc_toolbox_pro.spec) do (
    if not exist "%%f" (
        echo       [MISSING] %%f
        set MISSING=1
    )
)
if !MISSING!==1 (
    echo.
    echo [ERROR] Some files are missing. Cannot continue.
    echo         Current folder: !CD!
    echo         build.bat must sit in the project folder, next to
    echo         backend_server.py and pc_toolbox_pro.py.
    pause
    exit /b 1
)
echo       All files present.
echo.

REM ---------- Step 3b: Config sanity check ----------
REM PyInstaller only follows imports of the MAIN file. Modules imported
REM by backend_server must be listed in hiddenimports, or the EXE will
REM crash with ImportError on the user's machine.
echo.
echo ------------------------------------------------------------
echo   Build configuration check
echo   (verifies every module is declared in the .spec file)
echo ------------------------------------------------------------
%PYCMD% tests_build.py
if errorlevel 1 (
    echo.
    echo [ERROR] Build configuration check failed. See details above.
    echo         Fix the issues before building.
    pause
    exit /b 1
)
echo.

REM ---------- Step 4: Clean previous build ----------
echo [4/5] Cleaning previous build...
if exist "build" rd /s /q "build" >nul 2>&1
if exist "dist"  rd /s /q "dist"  >nul 2>&1
echo       Done.
echo.

REM ---------- Step 5: Build EXE ----------
echo [5/5] Building executable...
echo       This takes 2-5 minutes. Please wait.
echo.
%PYCMD% -m PyInstaller pc_toolbox_pro.spec --clean --noconfirm
if errorlevel 1 (
    echo.
    echo [ERROR] Build failed. See the error message above.
    pause
    exit /b 1
)

echo.
echo ============================================================
if exist "dist\PC_Repair_Toolbox_Pro.exe" (
    echo    BUILD SUCCESSFUL
    echo.
    for %%A in ("dist\PC_Repair_Toolbox_Pro.exe") do set /a SIZE_MB=%%~zA/1048576
    echo    File: dist\PC_Repair_Toolbox_Pro.exe
    echo    Size: !SIZE_MB! MB
    echo.
    echo    This is a standalone file. You can copy it to your
    echo    Desktop or any other Windows computer.
) else (
    echo    [WARNING] EXE was not created. Check the output above.
)
echo ============================================================
echo.
pause
