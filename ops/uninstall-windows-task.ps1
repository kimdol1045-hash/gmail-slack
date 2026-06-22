$ErrorActionPreference = "Stop"

$TaskName = "GmailChatMirror"
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task: $TaskName"

