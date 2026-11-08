<#
.SYNOPSIS
    runner-enroll.ps1 - enroll a Windows DevGate spoke with the monitor hub.

.DESCRIPTION
    Windows counterpart of scripts/runner-enroll.sh. Enrolls once (POST /enroll),
    stores the returned per-runner heartbeat token, and registers a Scheduled
    Task that posts a heartbeat on an interval and at startup.

    What it does NOT do, because the shell script's version of it does not
    translate: there is no systemd here, so the image-cycle, fleet-watchdog and
    secret-sweep units have no Windows equivalent. A Windows spoke enrolls,
    heartbeats, and is monitored; it does not run podman work, because it has no
    podman. That is the platform difference, stated rather than faked.

.PARAMETER HubUrl
    Base URL of the monitor hub, e.g. http://100.99.118.48:8443

.PARAMETER EnrollmentToken
    One-time enrollment token from HUB_ENROLLMENT_TOKENS on the hub.

.PARAMETER Repo
    OWNER/REPO this runner serves.

.PARAMETER Labels
    Comma-separated labels.

.PARAMETER RunnerName
    Runner name; defaults to the hostname.

.PARAMETER IntervalSec
    Heartbeat interval seconds; defaults to 300, matching HUB_HEARTBEAT_INTERVAL_SEC.

.EXAMPLE
    .\runner-enroll.ps1 -HubUrl http://100.99.118.48:8443 `
        -EnrollmentToken $tok -Repo TheArchitectit/oldfilefinder-private `
        -Labels windows,wpf
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$HubUrl,
    [Parameter(Mandatory = $true)][string]$EnrollmentToken,
    [Parameter(Mandatory = $true)][string]$Repo,
    [string]$Labels       = 'windows',
    [string]$RunnerName   = $env:COMPUTERNAME,
    [string]$HostAlias    = $env:COMPUTERNAME,
    [int]$IntervalSec     = 300
)

$ErrorActionPreference = 'Stop'

function Fail([string]$msg, [int]$code) { Write-Error $msg; exit $code }

if ($Repo -notmatch '^[^/]+/[^/]+$') { Fail "Repo must be OWNER/REPO, got '$Repo'" 1 }

$labelList = @($Labels -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })

$payload = [ordered]@{
    runner_name      = $RunnerName
    repo             = $Repo
    labels           = $labelList
    host_alias       = $HostAlias
    platform         = 'windows'
    enrollment_token = $EnrollmentToken
}
$json = $payload | ConvertTo-Json -Compress

Write-Output "[enroll:$RunnerName] POST $HubUrl/enroll"
try {
    $resp = Invoke-WebRequest -Uri "$HubUrl/enroll" -Method Post `
        -ContentType 'application/json' -Body $json -UseBasicParsing -TimeoutSec 30
    $doc = $resp.Content | ConvertFrom-Json
} catch {
    if ($_.Exception.Response) {
        $sc = [int]$_.Exception.Response.StatusCode
        Fail "[enroll:$RunnerName] hub answered $sc" 2
    }
    Fail "[enroll:$RunnerName] hub unreachable: $($_.Exception.Message)" 2
}

if (-not $doc.ok -or -not $doc.heartbeat_token) {
    Fail "[enroll:$RunnerName] hub did not return a heartbeat token" 2
}

# Heartbeat token and hub URL go to machine scope: the Scheduled Task runs as
# SYSTEM so it ticks whether or not anyone is logged in, and a user-scope
# variable would be invisible to that account.
[Environment]::SetEnvironmentVariable('HUB_URL',         $HubUrl,            'Machine')
[Environment]::SetEnvironmentVariable('RUNNER_NAME',     $RunnerName,        'Machine')
[Environment]::SetEnvironmentVariable('HEARTBEAT_TOKEN', $doc.heartbeat_token, 'Machine')
[Environment]::SetEnvironmentVariable('DEVGATE_PLATFORM','windows',           'Machine')

$here    = Split-Path -Parent $MyInvocation.MyCommand.Path
$hb      = Join-Path $here 'runner-heartbeat.ps1'
if (-not (Test-Path $hb)) { Fail "heartbeat script not found beside this one: $hb" 3 }

$taskName = "DevGateHeartbeat-$RunnerName"
$action = New-ScheduledTaskAction -Execute 'powershell.exe' `
    -Argument "-NoProfile -NonInteractive -ExecutionPolicy Bypass -File `"$hb`""
$triggerStart = New-ScheduledTaskTrigger -AtStartup
$triggerTick  = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Seconds $IntervalSec)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 5)

Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue
Register-ScheduledTask -TaskName $taskName -Action $action `
    -Trigger @($triggerStart, $triggerTick) -Settings $settings `
    -User 'SYSTEM' -RunLevel Highest | Out-Null

Write-Output "[enroll:$RunnerName] scheduled task '$taskName' every ${IntervalSec}s (SYSTEM)"

# SetEnvironmentVariable writes at machine scope, which the CURRENT process does
# not inherit — a process reads its environment once, at creation. Without this
# the immediate first heartbeat dies with "HUB_URL is not set" even though the
# variables were just stored correctly, and the operator reads that as a failed
# enrollment. The scheduled task is unaffected either way: it starts a new
# process, which does inherit them.
$env:HUB_URL          = $HubUrl
$env:RUNNER_NAME      = $RunnerName
$env:HEARTBEAT_TOKEN  = $doc.heartbeat_token
$env:DEVGATE_PLATFORM = 'windows'

Write-Output "[enroll:$RunnerName] first heartbeat:"
& $hb
exit $LASTEXITCODE
