$ErrorActionPreference = "Stop"

$TaskName = "GmailChatMirror"
$ProjectDir = "C:\gmail-chat"
$ScriptPath = Join-Path $ProjectDir "ops\run-gmail-chat.ps1"

$Action = New-ScheduledTaskAction `
  -Execute "powershell.exe" `
  -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$ScriptPath`""

$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)

Register-ScheduledTask `
  -TaskName $TaskName `
  -Action $Action `
  -Trigger $Trigger `
  -Settings $Settings `
  -Description "Run Gmail Chat Mirror at user logon" `
  -Force

Write-Host "Installed scheduled task: $TaskName"
Write-Host "Start it with: Start-ScheduledTask -TaskName $TaskName"

