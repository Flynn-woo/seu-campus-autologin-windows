param(
    [Parameter(Mandatory = $true)][string]$Executable,
    [Parameter(Mandatory = $true)][string]$OutputDir
)
$ErrorActionPreference = "Stop"
Import-Module ScheduledTasks
. (Join-Path (Split-Path -Parent $PSScriptRoot) "installer\autostart.ps1")
$TaskName = "SEU-OSS-Verification-" + [guid]::NewGuid().ToString("N")
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null
$StartupLink = Join-Path $OutputDir "live-test.lnk"
$Executable = (Resolve-Path -LiteralPath $Executable).Path
try {
    # 只运行版本检查，不读取凭据、发起认证或更改网络。
    $Mode = Register-SEUAutostart -TaskName $TaskName -Executable $Executable -WorkingDirectory (Split-Path -Parent $Executable) -StartupLink $StartupLink -RunArguments "--version"
    if ($Mode -ne "scheduled-events-periodic") { throw "当前测试账户无法验证完整任务触发器，模式：$Mode" }
    $Task = Get-ScheduledTask -TaskName $TaskName
    if ($Task.Triggers.Count -ne 4) { throw "真实任务未保存四个触发器" }
    Start-ScheduledTask -TaskName $TaskName
    $Deadline = (Get-Date).AddSeconds(30)
    do {
        Start-Sleep -Seconds 1
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        $Task = Get-ScheduledTask -TaskName $TaskName
    } until (($Info.LastRunTime.Year -gt 2000 -and $Task.State -ne "Running") -or (Get-Date) -gt $Deadline)
    if ($Info.LastTaskResult -ne 0 -or $Info.LastRunTime.Year -lt 2000) {
        throw "手动启动临时任务失败：状态=$($Task.State)，返回码=$($Info.LastTaskResult)，上次运行=$($Info.LastRunTime)"
    }
    $FirstRun = $Info.LastRunTime
    Write-Host "通过：真实计划任务保存了四个触发器，无窗口程序运行返回 0。正在验证两分钟定时触发。"
    $Deadline = (Get-Date).AddSeconds(150)
    do {
        Start-Sleep -Seconds 2
        $Info = Get-ScheduledTaskInfo -TaskName $TaskName
        $Task = Get-ScheduledTask -TaskName $TaskName
    } until (($Info.LastRunTime -gt $FirstRun -and $Task.State -ne "Running") -or (Get-Date) -gt $Deadline)
    if ($Info.LastRunTime -le $FirstRun -or $Info.LastTaskResult -ne 0) { throw "定时触发未成功" }
    @{
        trigger_count = $Task.Triggers.Count
        manual_task_result = 0
        periodic_task_result = $Info.LastTaskResult
        periodic_run_observed = $true
        console_window = $false
        credential_submission = $false
    } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $OutputDir "live-task-result.json") -Encoding UTF8
    Write-Host "通过：两分钟自动触发，无窗口程序返回 0。"
}
finally {
    Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue | Stop-ScheduledTask -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    if (Test-Path -LiteralPath $StartupLink) { Remove-Item -LiteralPath $StartupLink -Force }
}
