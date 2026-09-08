param(
    [switch]$SkipCurrentTest,
    [switch]$Reconfigure
)

$ErrorActionPreference = "Stop"
$TaskName = "SEU Campus Auto Login OSS"
$AppName = "SEUCampusAutoLoginOSS"
$SourceDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PackageRoot = Split-Path -Parent $SourceDir
$SourceAppDir = Join-Path $PackageRoot "app"
$InstallDir = Join-Path $env:LOCALAPPDATA $AppName
$InstallAppDir = Join-Path $InstallDir "app"
$InstalledExe = Join-Path $InstallAppDir "SEUCampusAutoLoginOSS.exe"
$BackgroundExe = Join-Path $InstallAppDir "SEUCampusAutoLoginOSSBackground.exe"
$PowerShellExe = Join-Path $env:SystemRoot "System32\WindowsPowerShell\v1.0\powershell.exe"
$StartupLink = Join-Path ([Environment]::GetFolderPath("Startup")) "SEU Campus Auto Login OSS.lnk"
$StartMenuDir = Join-Path ([Environment]::GetFolderPath("Programs")) "SEU Campus Auto Login OSS"
. (Join-Path $SourceDir "autostart.ps1")

Write-Host "=== 东南大学校园网自动登录公开版安装向导 ===" -ForegroundColor Cyan
Write-Host "请在日常使用的 Windows 账户中直接双击安装，无需切换管理员账户。"
Write-Host "仅支持 http://10.9.10.100/；该门户使用 HTTP，凭据传输不具备 TLS 保护。" -ForegroundColor Yellow

foreach ($Name in @("SEUCampusAutoLoginOSS.exe", "SEUCampusAutoLoginOSSBackground.exe", "_internal")) {
    if (-not (Test-Path -LiteralPath (Join-Path $SourceAppDir $Name))) {
        throw "安装包不完整。请下载 Releases 中的 Windows ZIP 并全部解压，再运行安装.cmd；不要下载 Source code，也不要单独复制 EXE。缺少：$Name"
    }
}

# 覆盖前停止本公开版旧进程，避免可执行文件被占用；已有凭据默认保留。
$ExistingTask = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($ExistingTask) {
    $ExistingTask | Disable-ScheduledTask -ErrorAction SilentlyContinue | Out-Null
    $ExistingTask | Stop-ScheduledTask -ErrorAction SilentlyContinue
}
Stop-SEUInstalledProcesses -InstallAppDir $InstallAppDir
New-Item -ItemType Directory -Path $InstallAppDir -Force | Out-Null
Copy-Item -Path (Join-Path $SourceAppDir "*") -Destination $InstallAppDir -Recurse -Force
foreach ($Name in @("uninstall.ps1", "autostart.ps1")) {
    Copy-Item -LiteralPath (Join-Path $SourceDir $Name) -Destination (Join-Path $InstallDir $Name) -Force
}

& $InstalledExe credential-status
if ($LASTEXITCODE -ne 0 -or $Reconfigure) {
    & $InstalledExe configure
    if ($LASTEXITCODE -ne 0) { throw "凭据配置未完成，尚未注册自动登录任务。" }
}
else {
    Write-Host "已保留当前 Windows 用户的公开版凭据。需要修改时请从开始菜单选择“配置凭据”。"
}

$Mode = Register-SEUAutostart -TaskName $TaskName -Executable $BackgroundExe -WorkingDirectory $InstallAppDir -StartupLink $StartupLink
Set-Content -LiteralPath (Join-Path $InstallDir "install_mode.txt") -Value $Mode -Encoding UTF8

New-Item -ItemType Directory -Path $StartMenuDir -Force | Out-Null
$Shell = New-Object -ComObject WScript.Shell
$Commands = @(
    @{ Name = "配置凭据.lnk"; Target = $InstalledExe; Arguments = "--pause configure" },
    @{ Name = "检查状态.lnk"; Target = $InstalledExe; Arguments = "--pause check" },
    @{ Name = "立即运行一次.lnk"; Target = $InstalledExe; Arguments = "--pause run-once --initial-delay 0" },
    @{ Name = "生成诊断报告.lnk"; Target = $InstalledExe; Arguments = "--pause diagnose" },
    @{
        Name = "卸载.lnk"; Target = $PowerShellExe
        Arguments = "-NoLogo -NoProfile -NoExit -ExecutionPolicy Bypass -File `"$(Join-Path $InstallDir 'uninstall.ps1')`""
    }
)
foreach ($Command in $Commands) {
    $Shortcut = $Shell.CreateShortcut((Join-Path $StartMenuDir $Command.Name))
    $Shortcut.TargetPath = $Command.Target
    $Shortcut.Arguments = $Command.Arguments
    $Shortcut.WorkingDirectory = $InstallDir
    $Shortcut.Save()
}

if (-not $SkipCurrentTest) {
    Write-Host "正在检查当前网络状态……" -ForegroundColor Cyan
    & $InstalledExe run-once --initial-delay 0 --network-wait-seconds 0 --no-browser-fallback
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "当前认证未完成；自动启动已经安装，请运行测试.cmd 查看状态和诊断报告。"
    }
}

if ($Mode -eq "startup-watch") {
    Start-Process -FilePath $BackgroundExe -ArgumentList "watch --interval 120" -WorkingDirectory $InstallAppDir -WindowStyle Hidden
    Write-Host "安装完成：使用启动项持续监测网络，每两分钟检查一次。" -ForegroundColor Green
}
else {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "安装完成：任务计划已启用，支持自动触发及每两分钟补查。模式：$Mode" -ForegroundColor Green
}
Write-Host "公开版安装目录：$InstallDir"
Write-Host "电脑重启后需先登录此 Windows 账户，后台程序才会运行。"
exit 0
