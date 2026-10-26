@echo off
rem Build from a short temporary path because Vitis HLS rejects spaces.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_hls.ps1"
exit /b %errorlevel%
