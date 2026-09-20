$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$RuntimeDir = Join-Path $ProjectRoot ".run"

foreach ($Name in @("frontend", "backend")) {
    $PidFile = Join-Path $RuntimeDir "$Name.pid"
    if (-not (Test-Path $PidFile)) { continue }
    $ProcessId = [int](Get-Content $PidFile -Raw)
    $Process = Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    if ($null -ne $Process) {
        Stop-Process -Id $ProcessId -Force
        Write-Host "$Name 已停止。" -ForegroundColor Yellow
    }
    Remove-Item $PidFile -Force
}
