# Register Auto Play Agent as a Windows Task Scheduler job (run as Administrator).
# Usage: powershell -ExecutionPolicy Bypass -File scripts\setup-scheduler.ps1 [-Time 02:00]
#Requires -Version 5.1

param(
    [string]$Time = "02:00"   # 24h format, e.g. "22:30"
)

$AgentDir  = Split-Path $PSScriptRoot -Parent
$ScriptPath = "$AgentDir\scripts\run.ps1"
$TaskName  = "AutoPlayAgent"

$action  = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptPath`"" `
    -WorkingDirectory $AgentDir

$trigger = New-ScheduledTaskTrigger -Daily -At $Time

$settings = New-ScheduledTaskSettingsSet `
    -ExecutionTimeLimit (New-TimeSpan -Hours 4) `
    -StartWhenAvailable `   # 자는 동안 시각을 놓쳤으면 깨어난 후 즉시 실행
    -WakeToRun

Register-ScheduledTask `
    -TaskName  $TaskName `
    -Action    $action `
    -Trigger   $trigger `
    -Settings  $settings `
    -RunLevel  Highest `
    -Force | Out-Null

Write-Host "Registered: '$TaskName' — runs daily at $Time"
Write-Host "Check: Task Scheduler > Task Scheduler Library > $TaskName"
Write-Host ""
Write-Host "Other commands:"
Write-Host "  Run now  : Start-ScheduledTask -TaskName '$TaskName'"
Write-Host "  Remove   : Unregister-ScheduledTask -TaskName '$TaskName' -Confirm:`$false"
