@echo off
rem Rebuild the Vivado project from build_overlay.tcl.
setlocal
set "VIVADO=T:\SDK\vivado\2025.2\Vivado\bin\vivado.bat"
cd /d "%~dp0"
call "%VIVADO%" -mode batch -nolog -nojournal -source build_overlay.tcl
exit /b %errorlevel%
