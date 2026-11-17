@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0runtime\Attach-Full-Preview.ps1" -AtMainMenu
echo Exit code: %errorlevel%
pause
