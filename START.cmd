@echo off
setlocal
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0portable_start.ps1"
if errorlevel 1 (
    echo.
    echo Startup failed. Please keep the error above for troubleshooting.
    pause
)
endlocal
