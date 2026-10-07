@echo off
setlocal
title YOURE A BETA GDL Analysis v209 - Fiji Watchdog
color 0A
echo ============================================================
echo YOURE A BETA v209 - Persistent Fiji Watchdog
echo Existing Fiji/ImageJ instances will be force-closed first.
echo A crashed Fiji session will be reported, relaunched, and rerun.
echo This command prompt stays open until you close it.
echo ============================================================
echo.
set "SCRIPT_DIR=%~dp0"
set "LAUNCHER=%SCRIPT_DIR%Defaults and Other Stuff\GDL_Analysis_Launcher_v209.py"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%LAUNCHER%"
) else (
    python "%LAUNCHER%"
)
set "WATCHDOG_EXIT=%ERRORLEVEL%"
echo.
echo ============================================================
echo Fiji watchdog stopped with exit code %WATCHDOG_EXIT%.
echo This window will remain open. Press any key to close it.
echo ============================================================
pause >nul
endlocal
