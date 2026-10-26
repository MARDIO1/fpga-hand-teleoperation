@echo off
rem Rebuild the first-board combined overlay without loading it on hardware.
setlocal
set "XILINX_LOCAL_USER_DATA=no"
set "VIVADO=T:\SDK\vivado\2025.2\Vivado\bin\vivado.bat"
cd /d "%~dp0"
call "%VIVADO%" -mode batch -nolog -nojournal -source create_project.tcl -tclargs build
exit /b %errorlevel%
