param(
    [switch]$KeepLogs
)

$ErrorActionPreference = "Stop"

$TaskName = "SEU Campus Auto Login OSS"
$AppName = "SEUCampusAutoLoginOSS"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$InstalledExe = Join-Path $InstallDir "app\SEUCampusAutoLoginOSS.exe"
$StartupLink = Join-Path ([Environment]::GetFolderPath("Startup")) "SEU Campus Auto Login OSS.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "SEU Campus Auto Login OSS"

$Task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($Task) {
    Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
}
$HelperPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) "autostart.ps1"
if (Test-Path -LiteralPath $HelperPath) {
    . $HelperPath
    Stop-SEUInstalledProcesses -InstallAppDir (Join-Path $InstallDir "app")
}
if (Test-Path -LiteralPath $StartupLink) {
    Remove-Item -LiteralPath $StartupLink -Force
}
if (Test-Path -LiteralPath $StartMenuDir) {
    $ExpectedMenu = [IO.Path]::GetFullPath((Join-Path ([Environment]::GetFolderPath("Programs")) "SEU Campus Auto Login OSS"))
    if ([IO.Path]::GetFullPath($StartMenuDir) -ne $ExpectedMenu) { throw "拒绝删除非预期开始菜单目录。" }
    Remove-Item -LiteralPath $StartMenuDir -Recurse -Force
}

if (Test-Path -LiteralPath $InstalledExe) {
    & $InstalledExe forget-credential
    if ($LASTEXITCODE -ne 0) { throw "删除公开版凭据失败，已保留程序供再次卸载。" }
}
else {
    Write-Warning "未找到公开版程序；如有需要，请在 Credential Manager 中删除 SEUCampusAutoLoginOSS/SEU-WLAN。"
}

if (Test-Path -LiteralPath $InstallDir) {
    $LocalAppDataPath = [IO.Path]::GetFullPath($env:LOCALAPPDATA).TrimEnd('\')
    $ResolvedInstallDir = [IO.Path]::GetFullPath($InstallDir).TrimEnd('\')
    $ExpectedInstallDir = Join-Path $LocalAppDataPath $AppName
    if (-not $ResolvedInstallDir.Equals($ExpectedInstallDir, [StringComparison]::OrdinalIgnoreCase)) {
        throw "拒绝删除非预期目录：$ResolvedInstallDir"
    }
    if ($KeepLogs) {
        Get-ChildItem -LiteralPath $InstallDir -Force | Where-Object Name -NotIn @("logs", "diagnostics") | Remove-Item -Recurse -Force
        Write-Host "已保留公开版日志和诊断目录：$InstallDir" -ForegroundColor Yellow
    }
    else {
        Remove-Item -LiteralPath $InstallDir -Recurse -Force
    }
}

Write-Host "开源版已卸载；私人版本未被修改。" -ForegroundColor Green
