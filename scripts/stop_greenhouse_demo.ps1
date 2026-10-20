$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$runtime=Join-Path $root '.run\greenhouse'
$file=Join-Path $runtime 'demo-pids.json'
if (Test-Path $file) {
    $ids=Get-Content $file -Raw | ConvertFrom-Json
    foreach($taskPid in @($ids.backend,$ids.frontend)) {
        # PID reuse protection: verify command line and project directory before stopping.
        $proc=Get-CimInstance Win32_Process -Filter "ProcessId=$taskPid" -ErrorAction SilentlyContinue
        if ($proc -and $proc.CommandLine.IndexOf($root,[StringComparison]::OrdinalIgnoreCase) -ge 0 -and (($proc.CommandLine -like '*app.main:app*') -or ($proc.CommandLine -match 'vite[\\/]bin[\\/]vite\.js'))) {
            Stop-Process -Id $taskPid -PassThru -ErrorAction SilentlyContinue | Wait-Process -ErrorAction SilentlyContinue
        }
    }
    Remove-Item -LiteralPath $file
}
Write-Host 'Demo processes stopped. Hardware lease/watchdog closes outputs; bridge can stay running.'
