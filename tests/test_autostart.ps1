param([string]$OutputDir = (Join-Path $env:TEMP ([guid]::NewGuid().ToString())))
$ErrorActionPreference = "Stop"
Import-Module ScheduledTasks
. (Join-Path (Split-Path -Parent $PSScriptRoot) "installer\autostart.ps1")
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$Link = Join-Path $OutputDir "autostart-test.lnk"
$Executable = Join-Path $env:SystemRoot "System32\cmd.exe"

# 使用真实 Windows 触发器构造，仅替换注册调用；不创建正式任务或修改用户启动项。
function Register-ScheduledTask {
    [CmdletBinding()]
    param($TaskName, $Action, $Settings, $Principal, $Description, [switch]$Force, $Trigger)
    $script:Calls += 1
    if ($script:Failure -eq "always" -or ($script:Failure -eq "first" -and $script:Calls -eq 1)) {
        throw "模拟普通用户注册权限不足"
    }
    $script:Recorded = @{ Action = $Action; Settings = $Settings; Principal = $Principal; Triggers = $Trigger }
}

foreach ($Scenario in @("none", "first", "always")) {
    $script:Calls = 0
    $script:Failure = $Scenario
    $Mode = Register-SEUAutostart -TaskName "SEU-TEST-ONLY" -Executable $Executable -WorkingDirectory $OutputDir -StartupLink $Link
    if ($Scenario -eq "none") {
        if ($Mode -ne "scheduled-events-periodic" -or $Recorded.Triggers.Count -ne 4) { throw "完整触发器未安装" }
        $Subscriptions = @($Recorded.Triggers | Where-Object { $_.CimClass.CimClassName -eq "MSFT_TaskEventTrigger" } | ForEach-Object { $_.Subscription })
        if (-not ($Subscriptions -match "NetworkProfile") -or -not ($Subscriptions -match "Power-Troubleshooter")) { throw "事件订阅缺失" }
    }
    elseif ($Scenario -eq "first") {
        if ($Mode -ne "scheduled-periodic" -or $Recorded.Triggers.Count -ne 2) { throw "无事件权限时未保留周期补查" }
    }
    else {
        if ($Mode -ne "startup-watch" -or -not (Test-Path -LiteralPath $Link)) { throw "启动项回退失败" }
        $Shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($Link)
        if ($Shortcut.Arguments -ne "watch --interval 120") { throw "启动项必须持续监测" }
        if ($Shortcut.TargetPath -ne $Executable) { throw "启动项程序路径错误" }
        continue
    }
    if ($Recorded.Settings.DisallowStartIfOnBatteries -or $Recorded.Settings.StopIfGoingOnBatteries) { throw "电池模式不应阻止任务" }
    if ($Recorded.Settings.MultipleInstances -ne 2) { throw "重复事件不应并行提交" }
    if ($Recorded.Principal.LogonType -ne 3 -or $Recorded.Principal.RunLevel -ne 0) { throw "必须使用当前交互用户的普通权限" }
    if ($Recorded.Action.Arguments -notmatch "--automatic --no-browser-fallback") { throw "后台任务参数缺失" }
    $Timer = @($Recorded.Triggers | Where-Object { $_.Repetition.Interval -eq "PT2M" })
    if ($Timer.Count -ne 1 -or $Timer[0].Repetition.Duration) { throw "周期检查不应在一天后失效" }
}

# 从回退模式升级到任务计划后，应移除旧启动项。
$script:Calls = 0
$script:Failure = "none"
$Mode = Register-SEUAutostart -TaskName "SEU-TEST-ONLY" -Executable $Executable -WorkingDirectory $OutputDir -StartupLink $Link
if (Test-Path -LiteralPath $Link) { throw "升级遗留了重复启动项" }
Write-Host "通过：完整事件触发、周期回退、启动项持续监测、升级去重及电池模式设置。"
