$ErrorActionPreference = 'Stop'

$projectRoot = $PSScriptRoot
$gcc = 'T:\SDK\STM32CubeCLT_1.20.0\GNU-tools-for-STM32\bin\arm-none-eabi-gcc.exe'
$objcopy = 'T:\SDK\STM32CubeCLT_1.20.0\GNU-tools-for-STM32\bin\arm-none-eabi-objcopy.exe'
$sizeTool = 'T:\SDK\STM32CubeCLT_1.20.0\GNU-tools-for-STM32\bin\arm-none-eabi-size.exe'
$buildDirectory = Join-Path $projectRoot 'build'
$elf = Join-Path $buildDirectory 'strain_imu_f103.elf'
$map = Join-Path $buildDirectory 'strain_imu_f103.map'

New-Item -ItemType Directory -Force $buildDirectory | Out-Null

$includeDirectories = @(
    (Join-Path $projectRoot 'Core\Inc'),
    (Join-Path $projectRoot 'App\Inc'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Inc'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Inc\Legacy'),
    (Join-Path $projectRoot 'Drivers\CMSIS\Device\ST\STM32F1xx\Include'),
    (Join-Path $projectRoot 'Drivers\CMSIS\Include'),
    (Join-Path $projectRoot 'USB_DEVICE\App'),
    (Join-Path $projectRoot 'USB_DEVICE\Target'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Core\Inc'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Class\CDC\Inc'),
    (Join-Path $projectRoot '..\Drivers\BSP\imu_filter')
)

$sources = @(
    (Join-Path $projectRoot 'Core\Src\main.c'),
    (Join-Path $projectRoot 'Core\Src\stm32f1xx_hal_msp.c'),
    (Join-Path $projectRoot 'Core\Src\stm32f1xx_it.c'),
    (Join-Path $projectRoot 'Core\Src\system_stm32f1xx.c'),
    (Join-Path $projectRoot 'App\Src\app.c'),
    (Join-Path $projectRoot 'App\Src\mpu6050.c'),
    (Join-Path $projectRoot 'USB_DEVICE\App\usb_device.c'),
    (Join-Path $projectRoot 'USB_DEVICE\App\usbd_cdc_if.c'),
    (Join-Path $projectRoot 'USB_DEVICE\App\usbd_desc.c'),
    (Join-Path $projectRoot 'USB_DEVICE\Target\usbd_conf.c'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Core\Src\usbd_core.c'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Core\Src\usbd_ctlreq.c'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Core\Src\usbd_ioreq.c'),
    (Join-Path $projectRoot 'Middlewares\ST\STM32_USB_Device_Library\Class\CDC\Src\usbd_cdc.c'),
    (Join-Path $projectRoot '..\Drivers\BSP\imu_filter\imu_filter.c'),
    (Join-Path $projectRoot 'STM32CubeIDE\Application\User\Core\syscalls.c'),
    (Join-Path $projectRoot 'STM32CubeIDE\Application\User\Core\sysmem.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_adc.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_adc_ex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_cortex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_dma.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_exti.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_flash.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_flash_ex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_gpio.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_gpio_ex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_i2c.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_pwr.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_pcd.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_pcd_ex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_rcc.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_rcc_ex.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_hal_uart.c'),
    (Join-Path $projectRoot 'Drivers\STM32F1xx_HAL_Driver\Src\stm32f1xx_ll_usb.c'),
    (Join-Path $projectRoot 'STM32CubeIDE\Application\User\Startup\startup_stm32f103c8tx.s')
)

$arguments = @(
    '-mcpu=cortex-m3', '-mthumb', '-mfloat-abi=soft',
    '-DSTM32F103xB', '-DUSE_HAL_DRIVER',
    '-Os', '-g3', '-ffunction-sections', '-fdata-sections',
    '-Wall', '-Wextra', '-Werror=implicit-function-declaration'
)
foreach ($includeDirectory in $includeDirectories) {
    $arguments += ('-I' + $includeDirectory)
}
$arguments += $sources
$arguments += @(
    ('-T' + (Join-Path $projectRoot 'STM32CubeIDE\STM32F103C8TX_FLASH.ld')),
    '--specs=nano.specs', '--specs=nosys.specs',
    '-Wl,--gc-sections', ('-Wl,-Map=' + $map),
    '-Wl,--print-memory-usage', '-lm', '-o', $elf
)

& $gcc @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Firmware link failed with exit code $LASTEXITCODE"
}

& $objcopy -O binary $elf (Join-Path $buildDirectory 'strain_imu_f103.bin')
if ($LASTEXITCODE -ne 0) {
    throw "BIN generation failed with exit code $LASTEXITCODE"
}
& $objcopy -O ihex $elf (Join-Path $buildDirectory 'strain_imu_f103.hex')
if ($LASTEXITCODE -ne 0) {
    throw "HEX generation failed with exit code $LASTEXITCODE"
}
& $sizeTool $elf
if ($LASTEXITCODE -ne 0) {
    throw "Size reporting failed with exit code $LASTEXITCODE"
}
