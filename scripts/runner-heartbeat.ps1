<#
.SYNOPSIS
    runner-heartbeat.ps1 - post ONE heartbeat for a Windows DevGate spoke.

.DESCRIPTION
    Windows counterpart of scripts/runner-heartbeat.sh. Same wire contract, same
    exit codes, no podman.

    Why a separate script rather than a flag on the shell one: the shell script
    is driven by systemd user units and a bash environment file, and neither
    exists on Windows. A Windows spoke runs this from a Scheduled Task with the
    same three required variables, so the hub sees one protocol and each host
    runs the automation it actually has.

    Required env (set as machine environment variables, or by the Scheduled Task):
      HUB_URL, RUNNER_NAME, HEARTBEAT_TOKEN

    Optional:
      DEVGATE_PLATFORM   defaults to "windows"; only here so a test can pin it.

    Exit codes (deliberately identical to the shell script):
      0   hub accepted the heartbeat (HTTP 200)
      1   required env missing
      22  hub answered with a non-200
      *   the WebClient's own failure when the hub could not be reached - a
          heartbeat that did not happen must never look like a pass.

    podman_ok: Windows has no podman, so this reports $null explicitly. The hub
    stores null and the runner's platform ("windows") is what stops that null
    being read as a broken Linux host. Omitting the key would be a different
    fact - "this host did not mention podman" - and the hub preserves the last
    value on an omission, which for a fresh Windows spoke would also be null but
    for the wrong reason.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'

function Fail([string]$msg, [int]$code) {
    Write-Error $msg
    exit $code
}

foreach ($required in @('HUB_URL', 'RUNNER_NAME', 'HEARTBEAT_TOKEN')) {
    if (-not [Environment]::GetEnvironmentVariable($required)) {
        Fail "$required is not set - check the Scheduled Task or machine environment" 1
    }
}

$hubUrl       = [Environment]::GetEnvironmentVariable('HUB_URL')
$runnerName   = [Environment]::GetEnvironmentVariable('RUNNER_NAME')
$heartbeat    = [Environment]::GetEnvironmentVariable('HEARTBEAT_TOKEN')
$platform     = [Environment]::GetEnvironmentVariable('DEVGATE_PLATFORM')
if (-not $platform) { $platform = 'windows' }

# Disk: the same threshold the shell script uses, so the fleet view means one
# thing regardless of platform. Percent used, not percent free.
$diskOk = $false
try {
    $drive = Get-CimInstance -ClassName Win32_LogicalDisk -Filter "DeviceID='C:'"
    if ($drive -and $drive.Size -gt 0) {
        $pctUsed = [math]::Round((($drive.Size - $drive.FreeSpace) / $drive.Size) * 100)
        $diskOk  = ($pctUsed -lt 90)
        Write-Verbose "disk used: $pctUsed%"
    }
} catch {
    # An unreadable disk is reported as not-ok, never as ok. A probe that dies
    # must not be indistinguishable from a healthy disk.
    Write-Verbose "disk probe failed: $($_.Exception.Message)"
}

# Last job: the runner's own _diag is the only local evidence of recent work.
# Absent means no job has run - null, not an empty string, because the hub
# treats "reported null" and "did not report" differently.
$workDir = if ($env:DEVGATE_WORK_DIR) { $env:DEVGATE_WORK_DIR } else { 'C:\_work' }
$lastJob = $null
try {
    $runs = Get-ChildItem -Path $workDir -Directory -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($runs) { $lastJob = $runs.Name }
} catch {
    Write-Verbose "job probe failed: $($_.Exception.Message)"
}

$body = [ordered]@{
    runner_name     = $runnerName
    heartbeat_token = $heartbeat
    platform        = $platform
    disk_ok         = $diskOk
    podman_ok       = $null      # no podman on Windows; see the note above
    last_job_seen   = $lastJob
}

$json = $body | ConvertTo-Json -Compress

# Keep the response for diagnosis, filename-safe for the same reason the shell
# script sanitises: a name the filesystem rejects dies before the status code is
# even read, which would turn a hub error into an unexplained exit.
$safeName = ($runnerName -replace '[^A-Za-z0-9_-]', '-')
$respPath = Join-Path $env:TEMP "devgate-hb-last-resp-$safeName.json"

try {
    $resp = Invoke-WebRequest -Uri "$hubUrl/heartbeat" -Method Post `
        -ContentType 'application/json' -Body $json -UseBasicParsing -TimeoutSec 30
    $code = [int]$resp.StatusCode
    if ($resp.Content) { Set-Content -Path $respPath -Value $resp.Content -Encoding UTF8 }
} catch {
    $code = 0
    if ($_.Exception.Response) {
        $code = [int]$_.Exception.Response.StatusCode
        try {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            Set-Content -Path $respPath -Value $reader.ReadToEnd() -Encoding UTF8
            $reader.Close()
        } catch { }
    } else {
        Write-Error "[hb:$runnerName] hub unreachable: $($_.Exception.Message)"
        exit 1
    }
}

Write-Output "[hb:$runnerName] HTTP $code"
if ($code -ne 200) {
    if (Test-Path $respPath) {
        Write-Error "[hb:$runnerName] hub response: $(Get-Content $respPath -Raw)"
    }
    exit 22
}
exit 0
