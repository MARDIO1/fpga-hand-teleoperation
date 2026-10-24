@echo off
rem Build the identical algorithm with bundled Clang, without starting HLS services.
setlocal
set "VITIS=T:\SDK\vivado\2025.2\Vitis"
call "%VITIS%\settings64.bat"
cd /d "%~dp0"
if not exist build mkdir build
"%VITIS%\win64\tools\clang-16\bin\clang++.exe" --target=x86_64-w64-windows-gnu --sysroot=%VITIS%/tps/mingw/10.0.0/win64.o/nt -fuse-ld=lld -static -pthread -std=c++17 -O2 -Wall -Wextra -Wno-unknown-pragmas -Ihls hls/hand_core.cpp tests/hand_core_tb.cpp -o build/hand_test.exe
if errorlevel 1 exit /b 1
build\hand_test.exe
if errorlevel 1 exit /b 1
"%VITIS%\win64\tools\clang-16\bin\clang++.exe" --target=x86_64-w64-windows-gnu --sysroot=%VITIS%/tps/mingw/10.0.0/win64.o/nt -fuse-ld=lld -static -pthread -std=c++17 -O2 -Wall -Wextra -Wno-unknown-pragmas -Ihls hls/hand_core.cpp tests/hand_core_rtl_tb.cpp -o build/hand_rtl_test.exe
if errorlevel 1 exit /b 1
build\hand_rtl_test.exe
exit /b %errorlevel%
