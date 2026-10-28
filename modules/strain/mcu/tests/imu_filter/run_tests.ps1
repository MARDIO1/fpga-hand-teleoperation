$ErrorActionPreference = 'Stop'

$TestRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$McuRoot = Resolve-Path (Join-Path $TestRoot '..\..')
$FilterRoot = Join-Path $McuRoot 'Drivers\BSP\imu_filter'
$BuildRoot = Join-Path $TestRoot 'build'

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

$HostExe = Join-Path $BuildRoot 'test_imu_filter.exe'
gcc -std=c11 -O2 -Wall -Wextra -Werror `
    -I $FilterRoot `
    (Join-Path $FilterRoot 'imu_filter.c') `
    (Join-Path $TestRoot 'test_imu_filter.c') `
    -lm -o $HostExe

& $HostExe
if ($LASTEXITCODE -ne 0) {
    throw "Host IMU filter tests failed with exit code $LASTEXITCODE"
}

$ArmObject = Join-Path $BuildRoot 'imu_filter_cm3.o'
arm-none-eabi-gcc -std=c11 -O2 -Wall -Wextra -Werror `
    -mcpu=cortex-m3 -mthumb -mfloat-abi=soft `
    -ffunction-sections -fdata-sections -ffreestanding `
    -I $FilterRoot `
    -c (Join-Path $FilterRoot 'imu_filter.c') `
    -o $ArmObject

if ($LASTEXITCODE -ne 0) {
    throw "Cortex-M3 static compilation failed with exit code $LASTEXITCODE"
}

arm-none-eabi-size $ArmObject
