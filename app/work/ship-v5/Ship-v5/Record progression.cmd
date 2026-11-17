@echo off
"%~dp0CaptureEncounter.exe" --watch
echo Exit code: %errorlevel%
pause
