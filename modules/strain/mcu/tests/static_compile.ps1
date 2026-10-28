$ErrorActionPreference = 'Stop'

$TestRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$McuRoot = Resolve-Path (Join-Path $TestRoot '..')
$ProjectPath = Join-Path $McuRoot 'Projects\MDK-ARM\START0.uvprojx'
$ProjectRoot = Split-Path -Parent $ProjectPath
$BuildRoot = Join-Path $TestRoot 'build\cm3-objects'

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null

[xml]$Project = Get-Content -Raw -LiteralPath $ProjectPath
$Target = $Project.Project.Targets.Target
$Controls = $Target.TargetOption.TargetArmAds.Cads.VariousControls
$Defines = @($Controls.Define -split ',' | Where-Object { $_ })
$IncludeDirectories = @(
    foreach ($RelativeInclude in ($Controls.IncludePath -split ';')) {
        if ($RelativeInclude) {
            [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $RelativeInclude))
        }
    }
)
$SourceFiles = @(
    foreach ($Group in $Target.Groups.Group) {
        foreach ($File in $Group.Files.File) {
            if ($File.FileType -eq '1') {
                [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot $File.FilePath))
            }
        }
    }
)

$CommonArguments = @(
    '-std=c11', '-O2', '-Wall', '-Wextra',
    '-Werror=implicit-function-declaration', '-Werror=return-type',
    '-mcpu=cortex-m3', '-mthumb', '-mfloat-abi=soft',
    '-ffunction-sections', '-fdata-sections', '-ffreestanding'
)
foreach ($Define in $Defines) {
    $CommonArguments += "-D$Define"
}
foreach ($IncludeDirectory in $IncludeDirectories) {
    $CommonArguments += @('-I', $IncludeDirectory)
}

foreach ($SourceFile in $SourceFiles) {
    $ObjectName = ([System.IO.Path]::GetFileNameWithoutExtension($SourceFile)) + '.o'
    $ObjectPath = Join-Path $BuildRoot $ObjectName
    & arm-none-eabi-gcc @CommonArguments -c $SourceFile -o $ObjectPath
    if ($LASTEXITCODE -ne 0) {
        throw "Cortex-M3 compilation failed: $SourceFile"
    }
}

$Objects = @(Get-ChildItem -LiteralPath $BuildRoot -Filter '*.o' -File)
$TotalBytes = ($Objects | Measure-Object -Property Length -Sum).Sum
Write-Host "PASS: compiled $($SourceFiles.Count) project C files for Cortex-M3"
Write-Host "Object files: $($Objects.Count), total bytes on disk: $TotalBytes"
