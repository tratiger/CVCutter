param(
    [Parameter(Mandatory = $true)]
    [string]$ExePath,
    [double]$LaunchSlaSeconds = 5.0,
    [int]$TimeoutSeconds = 30,
    [string]$OutputPath = "test-output\installer-launch-metrics.json"
)

$resolvedExe = (Resolve-Path -Path $ExePath).Path
$outputFile = [System.IO.Path]::GetFullPath($OutputPath)
$outputDir = Split-Path -Parent $outputFile
if (-not (Test-Path -Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

$stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$process = Start-Process -FilePath $resolvedExe -PassThru
$status = "FAIL"
$launchSeconds = [double]::NaN

try {
    while ($stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
        $process.Refresh()
        if ($process.HasExited) {
            throw "Process exited before first window render. ExitCode=$($process.ExitCode)."
        }
        if (-not $process.HasExited -and $process.MainWindowHandle -ne 0) {
            $launchSeconds = [Math]::Round($stopwatch.Elapsed.TotalSeconds, 3)
            if ($launchSeconds -le $LaunchSlaSeconds) {
                $status = "PASS"
            }
            break
        }
        Start-Sleep -Milliseconds 100
    }

    if ([double]::IsNaN($launchSeconds)) {
        throw "Window render timeout: main window was not detected within $TimeoutSeconds seconds."
    }

    $metrics = [ordered]@{
        exe_path = $resolvedExe
        launch_seconds = $launchSeconds
        sla_seconds = $LaunchSlaSeconds
        timeout_seconds = $TimeoutSeconds
        status = $status
        measured_at_utc = (Get-Date).ToUniversalTime().ToString("o")
    }
    $metrics | ConvertTo-Json | Set-Content -Path $outputFile -Encoding UTF8
    $metrics | ConvertTo-Json -Depth 3 | Write-Output

    if ($status -ne "PASS") {
        throw "SC-007 failed: launch time ${launchSeconds}s exceeded SLA ${LaunchSlaSeconds}s."
    }
}
finally {
    if ($null -ne $process -and -not $process.HasExited) {
        Stop-Process -Id $process.Id
    }
}
