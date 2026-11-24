$ErrorActionPreference = 'Stop'
$appPath = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot 'app\app.py'))
$listeners = @(
    Get-NetTCPConnection -LocalPort 8050 -State Listen -ErrorAction SilentlyContinue |
        Select-Object -ExpandProperty OwningProcess -Unique
)

if ($listeners.Count -eq 0) {
    Write-Output 'No application is listening on port 8050.'
    exit 0
}

$processes = @(Get-CimInstance -ClassName Win32_Process)
$pythonApps = @(
    $processes | Where-Object {
        $_.ExecutablePath -and
        $_.CommandLine -and
        [System.IO.Path]::GetFileName($_.ExecutablePath) -match '^pythonw?\.exe$' -and
        $_.CommandLine.IndexOf($appPath, [System.StringComparison]::OrdinalIgnoreCase) -ge 0
    }
)
$rootIds = @()

foreach ($listenerId in $listeners) {
    $listenerProcess = $pythonApps | Where-Object { $_.ProcessId -eq $listenerId } | Select-Object -First 1
    if (-not $listenerProcess) {
        Write-Error "Port 8050 belongs to another process (PID $listenerId); refusing to stop it."
        exit 1
    }

    $rootProcess = $listenerProcess
    while ($true) {
        $parentProcess = $pythonApps |
            Where-Object { $_.ProcessId -eq $rootProcess.ParentProcessId } |
            Select-Object -First 1
        if (-not $parentProcess) {
            break
        }
        $rootProcess = $parentProcess
    }

    if ($rootIds -notcontains $rootProcess.ProcessId) {
        $rootIds += $rootProcess.ProcessId
    }
}

foreach ($rootId in $rootIds) {
    & "$env:SystemRoot\System32\taskkill.exe" /PID $rootId /T /F
    if ($LASTEXITCODE -ne 0) {
        Write-Error "Could not stop the Anemone process tree (PID $rootId)."
        exit 1
    }
}

Write-Output 'Anemone has been stopped.'
