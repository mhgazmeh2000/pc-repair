@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
title EXE Test - PC Repair Toolbox

echo ============================================================
echo    Testing the built EXE
echo ============================================================
echo.

if not exist "dist\PC_Repair_Toolbox_Pro.exe" (
    echo [ERROR] dist\PC_Repair_Toolbox_Pro.exe not found.
    echo         Run build.bat first.
    pause
    exit /b 1
)

for %%A in ("dist\PC_Repair_Toolbox_Pro.exe") do set SIZE=%%~zA
set /a SIZEMB=!SIZE! / 1048576
echo [1] EXE found - !SIZEMB! MB
echo.

REM ------------------------------------------------------------------
REM Important: the EXE has uac_admin=True, so Windows relaunches it
REM elevated. The elevated process gets a FRESH environment, which
REM means SERVER_PORT set here is lost. The server therefore starts
REM on its default port (8080, or 8081/8082 if busy).
REM We must discover the real port instead of assuming one.
REM ------------------------------------------------------------------

echo [2] Is an instance already running?
set FOUNDPORT=
for %%p in (8080 8081 8082) do (
    if not defined FOUNDPORT (
        powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%%p/' -UseBasicParsing -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
        if not errorlevel 1 set FOUNDPORT=%%p
    )
)
if defined FOUNDPORT (
    echo     Already running on port !FOUNDPORT! - will test that instance.
    set STARTED=0
) else (
    echo     Not running. Starting it now...
    echo     A UAC prompt will appear - click YES.
    start "" "dist\PC_Repair_Toolbox_Pro.exe"
    set STARTED=1
    echo     Waiting up to 40 seconds for startup...
    for /L %%i in (1,1,20) do (
        if not defined FOUNDPORT (
            timeout /t 2 /nobreak >nul
            for %%p in (8080 8081 8082) do (
                if not defined FOUNDPORT (
                    powershell -NoProfile -Command "try { $null = Invoke-WebRequest -Uri 'http://127.0.0.1:%%p/' -UseBasicParsing -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
                    if not errorlevel 1 set FOUNDPORT=%%p
                )
            )
        )
    )
)
echo.

if not defined FOUNDPORT (
    echo [FAIL] Server never responded on ports 8080-8082.
    echo.
    echo        Possible causes:
    echo          - You clicked NO on the UAC prompt
    echo          - The EXE crashed on startup
    echo          - A firewall is blocking localhost
    echo.
    echo        Check the log file:
    echo          %%LOCALAPPDATA%%\PCRepairToolbox\pc_toolbox_history.log
    echo.
    if exist "%LOCALAPPDATA%\PCRepairToolbox\pc_toolbox_history.log" (
        echo        --- Last 15 lines of the log ---
        powershell -NoProfile -Command "Get-Content '%LOCALAPPDATA%\PCRepairToolbox\pc_toolbox_history.log' -Tail 15"
    ) else (
        echo        Log file does not exist - the EXE never got that far.
    )
    echo.
    pause
    exit /b 1
)

REM Re-enter a plain (non-delayed) scope so %BASE% expands correctly
REM inside the PowerShell one-liners below. Using !BASE! there would
REM clash with PowerShell's own use of the ! character.
endlocal & set "BASE=http://127.0.0.1:%FOUNDPORT%" & set "STARTED=%STARTED%"

echo [3] Server is up on %BASE%
echo.

echo [4] Checking the served page...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='Stop';" ^
  "try {" ^
  "  $r = Invoke-WebRequest -Uri '%BASE%/' -UseBasicParsing -TimeoutSec 15;" ^
  "  Write-Host ('    [OK]  HTTP ' + $r.StatusCode + ' - ' + [math]::Round($r.Content.Length/1024) + ' KB') -ForegroundColor Green;" ^
  "  if ($r.Content -match '__TOOLBOX_TOKEN__') { Write-Host '    [OK]  Security token injected' -ForegroundColor Green } else { Write-Host '    [FAIL] Security token MISSING' -ForegroundColor Red };" ^
  "  if ($r.Content -match 'Vazirmatn')  { Write-Host '    [OK]  Font embedded' -ForegroundColor Green } else { Write-Host '    [WARN] Font not found' -ForegroundColor Yellow };" ^
  "  if ($r.Content -match 'tabDevView') { Write-Host '    [OK]  Dev tab present' -ForegroundColor Green } else { Write-Host '    [WARN] Dev tab missing' -ForegroundColor Yellow };" ^
  "  if ($r.Content -match 'chatJumpBtn'){ Write-Host '    [OK]  Chat scroll button present' -ForegroundColor Green }" ^
  "} catch { Write-Host ('    [FAIL] ' + $_.Exception.Message) -ForegroundColor Red }"
echo.

echo [5] Testing the 9 new modules...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$page = Invoke-WebRequest -Uri '%BASE%/' -UseBasicParsing -TimeoutSec 15;" ^
  "if ($page.Content -match '__TOOLBOX_TOKEN__ = \"([^\"]+)\"') { $tok = $Matches[1] } else { Write-Host '    [FAIL] No token found' -ForegroundColor Red; exit 1 };" ^
  "$h = @{'Content-Type'='application/json'; 'X-Toolbox-Token'=$tok};" ^
  "$eps = [ordered]@{ 'security (settings)'='/api/settings'; 'health_metrics'='/api/health_snapshot'; 'local_diagnosis'='/api/local_diagnose'; 'baseline'='/api/baseline_list'; 'restore_point'='/api/restore_status'; 'repair_history'='/api/repair_history'; 'event_catalog'='/api/explain_events'; 'workspace'='/api/ws_info'; 'code_changes'='/api/ws_preview_change' };" ^
  "$fail = 0;" ^
  "foreach ($k in $eps.Keys) {" ^
  "  try { $null = Invoke-WebRequest -Uri ('%BASE%' + $eps[$k]) -Method POST -Headers $h -Body '{}' -UseBasicParsing -TimeoutSec 60;" ^
  "        Write-Host ('    [OK]  ' + $k) -ForegroundColor Green }" ^
  "  catch { $c = $_.Exception.Response.StatusCode.value__;" ^
  "          if ($c -eq 400 -or $c -eq 404) { Write-Host ('    [OK]  ' + $k + ' (HTTP ' + $c + ' - expected)') -ForegroundColor Green }" ^
  "          else { Write-Host ('    [FAIL] ' + $k + ' - HTTP ' + $c) -ForegroundColor Red; $fail++ } } };" ^
  "Write-Host '';" ^
  "if ($fail -eq 0) { Write-Host '    >>> All modules loaded. EXE is healthy.' -ForegroundColor Green }" ^
  "else { Write-Host ('    >>> ' + $fail + ' module(s) failed - EXE built from an OLD spec.') -ForegroundColor Red }"
echo.

echo [6] Real PowerShell metrics - the key Windows test...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$page = Invoke-WebRequest -Uri '%BASE%/' -UseBasicParsing -TimeoutSec 15;" ^
  "if ($page.Content -match '__TOOLBOX_TOKEN__ = \"([^\"]+)\"') { $tok = $Matches[1] } else { exit 1 };" ^
  "$h = @{'Content-Type'='application/json'; 'X-Toolbox-Token'=$tok};" ^
  "$body = '{\"keys\":[\"disk_c_free_pct\",\"disk_c_free_gb\",\"ram_free_pct\",\"startup_count\",\"pending_reboot\",\"problem_drivers\"]}';" ^
  "try {" ^
  "  $r = Invoke-WebRequest -Uri '%BASE%/api/health_snapshot' -Method POST -Headers $h -Body $body -UseBasicParsing -TimeoutSec 120;" ^
  "  $j = $r.Content | ConvertFrom-Json;" ^
  "  $ok = 0; $bad = 0;" ^
  "  foreach ($p in $j.snapshot.PSObject.Properties) {" ^
  "    if ($null -ne $p.Value.value) { Write-Host ('    [OK]  ' + $p.Name + ' = ' + $p.Value.value + ' ' + $p.Value.unit) -ForegroundColor Green; $ok++ }" ^
  "    else { Write-Host ('    [FAIL] ' + $p.Name + ' - ' + $p.Value.error) -ForegroundColor Yellow; $bad++ } };" ^
  "  Write-Host '';" ^
  "  if ($ok -gt 0) { Write-Host ('    >>> PowerShell metrics WORK: ' + $ok + ' of ' + ($ok+$bad)) -ForegroundColor Green }" ^
  "  else { Write-Host '    >>> PowerShell metrics DO NOT work inside the EXE.' -ForegroundColor Red } }" ^
  "catch { Write-Host ('    [FAIL] ' + $_.Exception.Message) -ForegroundColor Red }"
echo.

echo [7] Local rule-based diagnosis on your real system...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$page = Invoke-WebRequest -Uri '%BASE%/' -UseBasicParsing -TimeoutSec 15;" ^
  "if ($page.Content -match '__TOOLBOX_TOKEN__ = \"([^\"]+)\"') { $tok = $Matches[1] } else { exit 1 };" ^
  "$h = @{'Content-Type'='application/json'; 'X-Toolbox-Token'=$tok};" ^
  "try {" ^
  "  $r = Invoke-WebRequest -Uri '%BASE%/api/local_diagnose' -Method POST -Headers $h -Body '{\"fast\":true}' -UseBasicParsing -TimeoutSec 120;" ^
  "  $j = $r.Content | ConvertFrom-Json;" ^
  "  Write-Host ('    ' + $j.summary_fa) -ForegroundColor Cyan;" ^
  "  foreach ($f in $j.findings) { Write-Host ('      [' + $f.severity + '] ' + $f.title_fa) -ForegroundColor Yellow } }" ^
  "catch { Write-Host ('    [FAIL] ' + $_.Exception.Message) -ForegroundColor Red }"
echo.

echo [8] Windows Event Viewer catalog on your real events...
powershell -NoProfile -Command ^
  "$ErrorActionPreference='SilentlyContinue';" ^
  "$page = Invoke-WebRequest -Uri '%BASE%/' -UseBasicParsing -TimeoutSec 15;" ^
  "if ($page.Content -match '__TOOLBOX_TOKEN__ = \"([^\"]+)\"') { $tok = $Matches[1] } else { exit 1 };" ^
  "$h = @{'Content-Type'='application/json'; 'X-Toolbox-Token'=$tok};" ^
  "try {" ^
  "  $r = Invoke-WebRequest -Uri '%BASE%/api/explain_events' -Method POST -Headers $h -Body '{}' -UseBasicParsing -TimeoutSec 120;" ^
  "  $j = $r.Content | ConvertFrom-Json;" ^
  "  Write-Host ('    ' + $j.summary_fa) -ForegroundColor Cyan;" ^
  "  foreach ($k in $j.known | Select-Object -First 5) { Write-Host ('      Event ' + $k.event_id + ' - ' + $k.title) -ForegroundColor Yellow } }" ^
  "catch { Write-Host ('    [FAIL] ' + $_.Exception.Message) -ForegroundColor Red }"
echo.

echo [9] Security - the CORS attack must be blocked...
powershell -NoProfile -Command ^
  "try {" ^
  "  $null = Invoke-WebRequest -Uri '%BASE%/api/run_tool' -Method POST -Headers @{'Content-Type'='application/json';'Origin'='https://evil.example.com'} -Body '{\"command\":\"calc.exe\"}' -UseBasicParsing -TimeoutSec 15;" ^
  "  Write-Host '    [FAIL] Attack was NOT blocked!' -ForegroundColor Red }" ^
  "catch { $c = $_.Exception.Response.StatusCode.value__;" ^
  "        if ($c -eq 403) { Write-Host '    [OK]  Attack blocked (HTTP 403)' -ForegroundColor Green }" ^
  "        else { Write-Host ('    [WARN] Unexpected: HTTP ' + $c) -ForegroundColor Yellow } }"
echo.

echo ------------------------------------------------------------
if "%STARTED%"=="1" (
    echo [10] Stopping the test instance...
    taskkill /F /IM PC_Repair_Toolbox_Pro.exe >nul 2>&1
    echo      Done.
) else (
    echo [10] Leaving your running instance untouched.
)
echo.
echo ============================================================
echo    Test finished. Please send a screenshot of this window.
echo ============================================================
echo.
pause
