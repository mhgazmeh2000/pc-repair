@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title Version Check - PC Repair Toolbox

echo ============================================================
echo    Version Check
echo ============================================================
echo.

set PYCMD=python
%PYCMD% --version >nul 2>&1
if errorlevel 1 set PYCMD=py

echo [1] Checking build.bat...
findstr /C:"tests_build.py" build.bat >nul 2>&1
if errorlevel 1 (
    echo     [OLD] build.bat does NOT have the config check.
    set OLDBAT=1
) else (
    echo     [OK]  build.bat has the config check.
    set OLDBAT=0
)
echo.

echo [2] Checking spec file for the 9 new modules...
set MISSING=0
for %%m in (security health_metrics local_diagnosis baseline restore_point repair_history event_catalog workspace code_changes) do (
    findstr /C:"'%%m'" pc_toolbox_pro.spec >nul 2>&1
    if errorlevel 1 (
        echo     [MISSING] %%m
        set MISSING=1
    )
)
if !MISSING!==0 (
    echo     [OK]  All 9 new modules are declared.
) else (
    echo     [OLD] Spec file is outdated - EXE will crash with ImportError.
)
echo.

echo [3] Checking module files exist...
set NOFILE=0
for %%f in (security.py health_metrics.py local_diagnosis.py baseline.py restore_point.py repair_history.py event_catalog.py workspace.py code_changes.py) do (
    if not exist "%%f" (
        echo     [MISSING] %%f
        set NOFILE=1
    )
)
if !NOFILE!==0 echo     [OK]  All 9 module files present.
echo.

echo [4] Running full config check...
if exist tests_build.py (
    %PYCMD% tests_build.py
) else (
    echo     [MISSING] tests_build.py not found - you have an old version.
    set OLDBAT=1
)
echo.

echo ============================================================
if !MISSING!==1 (
    echo    RESULT: OUTDATED FILES
    echo.
    echo    Download the project folder again, then run build.bat
) else if !OLDBAT!==1 (
    echo    RESULT: OUTDATED build.bat
    echo.
    echo    The spec is fine, but build.bat is old.
    echo    You can still build - just run: build.bat
) else (
    echo    RESULT: EVERYTHING UP TO DATE
    echo.
    echo    Safe to run build.bat
)
echo ============================================================
echo.
pause
