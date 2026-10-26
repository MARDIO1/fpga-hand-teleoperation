# Rebuild hand_core through a short, clean staging path required by Vitis HLS.
$ErrorActionPreference = "Stop"

$module = Split-Path -Parent $MyInvocation.MyCommand.Path
$stage = Join-Path $env:TEMP "fpga_hand_fusion_hls"
$tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
$stageFull = [IO.Path]::GetFullPath($stage)
if (-not $stageFull.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean non-temporary staging path: $stageFull"
}
if (Test-Path -LiteralPath $stageFull) {
    Remove-Item -LiteralPath $stageFull -Recurse -Force
}

New-Item -ItemType Directory -Path "$stageFull\hls","$stageFull\tests" | Out-Null
Copy-Item -LiteralPath "$module\hls\hand_core.cpp","$module\hls\hand_core.hpp" -Destination "$stageFull\hls"
Copy-Item -LiteralPath "$module\tests\hand_core_rtl_tb.cpp" -Destination "$stageFull\tests"
Copy-Item -LiteralPath "$module\hls_config.cfg" -Destination $stageFull

$vitis = "T:\SDK\vivado\2025.2\Vitis\bin"
Push-Location $stageFull
try {
    & "$vitis\v++.bat" -c --mode hls --config hls_config.cfg --work_dir build
    if ($LASTEXITCODE) { throw "HLS synthesis failed: $LASTEXITCODE" }
    $env:XILINX_LOCAL_USER_DATA = "no"
    & "$vitis\vitis-run.bat" --mode hls --config hls_config.cfg --work_dir build --package
    if ($LASTEXITCODE) { throw "HLS packaging failed: $LASTEXITCODE" }
} finally {
    Pop-Location
}

$destIp = "$module\build\hls\impl\ip"
$buildRoot = [IO.Path]::GetFullPath("$module\build").TrimEnd('\') + '\'
if (-not [IO.Path]::GetFullPath($destIp).StartsWith($buildRoot, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Refusing to clean IP path outside module build directory: $destIp"
}
if (Test-Path -LiteralPath $destIp) {
    Remove-Item -LiteralPath $destIp -Recurse -Force
}
New-Item -ItemType Directory -Path $destIp | Out-Null
Copy-Item -Path "$stageFull\build\hls\impl\ip\*" -Destination $destIp -Recurse
Copy-Item -LiteralPath "$stageFull\build\hand_core.zip" -Destination "$module\export\ip\hand_core.zip" -Force
Write-Output "HAND_CORE_HLS_BUILD_OK"
