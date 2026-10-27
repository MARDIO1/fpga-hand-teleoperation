param([string]$VivadoBin = '')
$ErrorActionPreference = 'Stop'
$moduleRoot = Split-Path $PSScriptRoot -Parent
$output = Join-Path $moduleRoot 'vivado/output/simulation'
New-Item -ItemType Directory -Path $output -Force | Out-Null
function Tool([string]$name) {
    if ($VivadoBin) { return Join-Path $VivadoBin "$name.bat" }
    return (Get-Command $name -ErrorAction Stop).Source
}
$cases = @(
    @{ Top='tb_stereo_line_controller'; Files=@('rtl/capture/stereo_line_controller.v','sim/tb_stereo_line_controller.sv') },
    @{ Top='tb_hdmi_timing_monitor'; Files=@('rtl/display/hdmi_timing_monitor.v','sim/tb_hdmi_timing_monitor.sv') },
    @{ Top='tb_stream_preproc'; Files=@('rtl/depth/stereo_stream_preproc.v','sim/tb_stream_preproc.sv') },
    @{ Top='tb_stream_chain'; Files=@('rtl/depth/stereo_sad.sv','rtl/depth/stereo_stream_preproc.v','sim/tb_stream_preproc.sv','sim/tb_stream_chain.sv') },
    @{ Top='tb_depth_video_overlay'; Files=@('rtl/depth/depth_video_overlay.v','sim/tb_depth_video_overlay.sv') }
)
foreach ($lanes in @(4,8,16)) {
    $cases += @{ Top="tb_sad_$lanes"; Name="sad_$lanes"; Files=@('rtl/depth/stereo_sad.sv','sim/tb_stereo_sad.sv') }
}
foreach ($case in $cases) {
    $name = if ($case.Name) { $case.Name } else { $case.Top }
    $folder = Join-Path $output $name
    New-Item -ItemType Directory -Path $folder -Force | Out-Null
    Push-Location $folder
    try {
        $files = @($case.Files | ForEach-Object { Join-Path $moduleRoot $_ })
        & (Tool 'xvlog') -sv -i (Join-Path $moduleRoot 'rtl/depth') @files *> compile.log
        if ($LASTEXITCODE -ne 0) { throw "xvlog failed: $folder/compile.log" }
        $elab = @($case.Top,'-s','test_snapshot')
        & (Tool 'xelab') @elab *> elaborate.log
        if ($LASTEXITCODE -ne 0) { throw "xelab failed: $folder/elaborate.log" }
        & (Tool 'xsim') test_snapshot -runall *> simulate.log
        $log = Get-Content simulate.log -Raw
        # XSim may exit zero even when the testbench calls $fatal.
        if ($LASTEXITCODE -ne 0 -or $log -match '(?m)^Fatal:|^ERROR:' -or $log -notmatch 'PASS') {
            throw "Simulation did not pass: $folder/simulate.log"
        }
        Write-Output "PASS $name"
    } finally { Pop-Location }
}
