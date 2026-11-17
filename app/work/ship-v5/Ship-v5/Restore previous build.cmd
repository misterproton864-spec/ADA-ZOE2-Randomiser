@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0Install-preview.ps1" -Restore
echo Exit code: %errorlevel%
pause
