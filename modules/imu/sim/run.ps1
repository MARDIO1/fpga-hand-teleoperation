param([string]$VivadoBin = "D:/LenovoSoftstore/Install/2025.2/Vivado/bin")
$ErrorActionPreference = "Stop"
$simDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputDirectory = Join-Path $simDirectory "output"
New-Item -ItemType Directory -Force $outputDirectory | Out-Null
Push-Location -LiteralPath $outputDirectory
try {
    & (Join-Path $VivadoBin "xvlog.bat") --sv ../../rtl/i2c_register_master.v ../../rtl/mpu6050_acquisition.v ../../rtl/mpu6050_axi.v ../tb_mpu6050.sv (Join-Path $VivadoBin "../data/verilog/src/glbl.v")
    if ($LASTEXITCODE -ne 0) { throw "Verilog compilation failed" }
    & (Join-Path $VivadoBin "xelab.bat") -L unisims_ver tb_mpu6050 glbl -s tb_mpu6050_sim
    if ($LASTEXITCODE -ne 0) { throw "Simulation elaboration failed" }
    & (Join-Path $VivadoBin "xsim.bat") tb_mpu6050_sim -tclbatch ../run.tcl
    if ($LASTEXITCODE -ne 0) { throw "Simulation failed" }
    $simulationLog = Get-Content -LiteralPath "xsim.log" -Raw
    if ($simulationLog -match "Fatal:" -or $simulationLog -notmatch "PASS:") {
        throw "Simulation did not reach its passing checks"
    }
} finally { Pop-Location }
