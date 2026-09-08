function New-SEUEventTrigger {
    param([string]$Subscription)
    $TriggerClass = Get-CimClass -Namespace "Root/Microsoft/Windows/TaskScheduler" -ClassName "MSFT_TaskEventTrigger"
    $Trigger = New-CimInstance -CimClass $TriggerClass -ClientOnly
    $Trigger.Enabled = $true
    $Trigger.Delay = "PT5S"
    $Trigger.Subscription = $Subscription
    return $Trigger
}

function Register-SEUAutostart {
    param(
        [string]$TaskName,
        [string]$Executable,
        [string]$WorkingDirectory,
        [string]$StartupLink,
        [string]$RunArguments = "run-once --automatic --no-browser-fallback --network-wait-seconds 120"
    )
    try {
        $CurrentUser = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
        $Action = New-ScheduledTaskAction -Execute $Executable -Argument $RunArguments -WorkingDirectory $WorkingDirectory
        $Logon = New-ScheduledTaskTrigger -AtLogOn -User $CurrentUser
        $Logon.Delay = "PT10S"
        # 补查覆盖 DHCP 延迟、快速启动和事件日志未产生的情况；无结束日期。
        $Periodic = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(2) -RepetitionInterval (New-TimeSpan -Minutes 2)
        $Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)
        $Principal = New-ScheduledTaskPrincipal -UserId $CurrentUser -LogonType Interactive -RunLevel Limited
        $Registration = @{
            TaskName = $TaskName; Action = $Action; Settings = $Settings; Principal = $Principal
            Description = "登录、网络重连、睡眠唤醒后检查校园网，每两分钟补查；仅在用户已登录时运行。"
            Force = $true; ErrorAction = "Stop"
        }
        try {
            $Network = New-SEUEventTrigger -Subscription @'
<QueryList><Query Id="0" Path="Microsoft-Windows-NetworkProfile/Operational"><Select Path="Microsoft-Windows-NetworkProfile/Operational">*[System[Provider[@Name='Microsoft-Windows-NetworkProfile'] and EventID=10000]]</Select></Query></QueryList>
'@
            $Resume = New-SEUEventTrigger -Subscription @'
<QueryList><Query Id="0" Path="System"><Select Path="System">*[System[Provider[@Name='Microsoft-Windows-Power-Troubleshooter'] and EventID=1]]</Select></Query></QueryList>
'@
            Register-ScheduledTask @Registration -Trigger @($Logon, $Network, $Resume, $Periodic) | Out-Null
            $Mode = "scheduled-events-periodic"
        }
        catch {
            Write-Warning "无法注册事件触发器，改用登录触发和每两分钟补查。"
            Register-ScheduledTask @Registration -Trigger @($Logon, $Periodic) | Out-Null
            $Mode = "scheduled-periodic"
        }
        if (Test-Path -LiteralPath $StartupLink) {
            Remove-Item -LiteralPath $StartupLink -Force
        }
        return $Mode
    }
    catch {
        Write-Warning "任务计划不可用，改用当前用户启动项持续监测网络。"
        $Shell = New-Object -ComObject WScript.Shell
        $Shortcut = $Shell.CreateShortcut($StartupLink)
        $Shortcut.TargetPath = $Executable
        $Shortcut.Arguments = "watch --interval 120"
        $Shortcut.WorkingDirectory = $WorkingDirectory
        $Shortcut.Description = "校园网后台监测，每两分钟检查重连或唤醒后的网络"
        $Shortcut.Save()
        return "startup-watch"
    }
}

function Stop-SEUInstalledProcesses {
    param([string]$InstallAppDir)
    # 只处理公开版安装目录中的两个程序，升级和卸载不会结束其他 Python 或浏览器。
    $Expected = @(
        [IO.Path]::GetFullPath((Join-Path $InstallAppDir "SEUCampusAutoLoginOSS.exe")),
        [IO.Path]::GetFullPath((Join-Path $InstallAppDir "SEUCampusAutoLoginOSSBackground.exe"))
    )
    Get-CimInstance Win32_Process -Filter "Name = 'SEUCampusAutoLoginOSS.exe' OR Name = 'SEUCampusAutoLoginOSSBackground.exe'" | ForEach-Object {
        if ($_.ExecutablePath -and $Expected -contains [IO.Path]::GetFullPath($_.ExecutablePath)) {
            Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue
        }
    }
}
