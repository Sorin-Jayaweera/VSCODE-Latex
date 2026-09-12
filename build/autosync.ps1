# =========================================================================
#  autosync.ps1 -- register (or remove) a scheduled task that pushes this
#  workspace to GitHub on a timer.
#
#      .\build\autosync.ps1 -Install            # every 30 minutes
#      .\build\autosync.ps1 -Install -Minutes 60
#      .\build\autosync.ps1 -Status
#      .\build\autosync.ps1 -Remove
#
#  Runs as you, not SYSTEM, so it uses your stored GitHub credentials and
#  needs no administrator rights. It only runs while you are logged in.
# =========================================================================

[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Remove,
    [switch]$Status,
    [int]$Minutes = 30
)

$TaskName = "HMC Notes GitHub Sync"
$Root     = Split-Path -Parent $PSScriptRoot
$Script   = Join-Path $Root "build\sync.py"

function Get-PythonPath {
    $p = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $p) { $p = (Get-Command py -ErrorAction SilentlyContinue).Source }
    if (-not $p) { throw "Could not find python on PATH." }
    return $p
}

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction Stop
    Write-Host "Removed scheduled task '$TaskName'."
    return
}

if ($Status) {
    $t = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
    if (-not $t) {
        Write-Host "No scheduled task named '$TaskName'. Auto-sync is OFF."
        return
    }
    $info = Get-ScheduledTaskInfo -TaskName $TaskName
    Write-Host "Task     : $TaskName"
    Write-Host "State    : $($t.State)"
    Write-Host "Last run : $($info.LastRunTime)  (result $($info.LastTaskResult))"
    Write-Host "Next run : $($info.NextRunTime)"
    return
}

if ($Install) {
    $python = Get-PythonPath
    if (-not (Test-Path $Script)) { throw "Missing $Script" }

    $action = New-ScheduledTaskAction `
        -Execute $python `
        -Argument "`"$Script`"" `
        -WorkingDirectory $Root

    # Repeat indefinitely, starting a minute from now.
    $trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
        -RepetitionInterval (New-TimeSpan -Minutes $Minutes)

    $settings = New-ScheduledTaskSettingsSet `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries `
        -StartWhenAvailable `
        -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
        -MultipleInstances IgnoreNew

    Register-ScheduledTask `
        -TaskName $TaskName `
        -Action $action `
        -Trigger $trigger `
        -Settings $settings `
        -Description "Commits and pushes the HMC notes VS Code LaTeX workspace to GitHub." `
        -Force | Out-Null

    Write-Host "Installed '$TaskName': every $Minutes minutes."
    Write-Host "Turn it off with:  .\build\autosync.ps1 -Remove"
    return
}

Write-Host "Specify -Install, -Remove or -Status. See the top of this file."
