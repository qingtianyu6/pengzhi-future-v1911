param([ValidateSet('mock','real')][string]$DeviceMode = '', [switch]$PinsVerified, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'greenhouse.config.ps1')
if (-not $DeviceMode) { $DeviceMode = $GreenhouseDeviceMode }
$backend = Join-Path $root 'backend'
$frontend = Join-Path $root 'frontend'
$python = Join-Path $backend '.venv\Scripts\python.exe'
$runtime = Join-Path $root '.run\greenhouse'
New-Item -ItemType Directory -Force $runtime | Out-Null
if (-not (Test-Path $python)) {
    & python -m venv (Join-Path $backend '.venv')
    & $python -m pip install -r (Join-Path $backend 'requirements.txt')
    if ($LASTEXITCODE) { throw 'Backend dependency installation failed.' }
}
if (-not (Test-Path (Join-Path $frontend 'node_modules'))) {
    Push-Location $frontend
    try { & npm.cmd ci; if ($LASTEXITCODE) { throw 'npm ci failed.' } } finally { Pop-Location }
}
foreach ($port in @($GreenhouseBackendPort,$GreenhouseFrontendPort)) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "Port $port is occupied. Use scripts/stop_greenhouse_demo.ps1 or change greenhouse.config.ps1." }
}
$env:GREENHOUSE_DEVICE_MODE = $DeviceMode
if ($DeviceMode -eq 'real') {
    if (-not $PinsVerified) { throw 'REAL mode requires verified physical wiring; supply -PinsVerified after completing HARDWARE_TODO.md.' }
    $env:GREENHOUSE_REAL_ENABLED = 'YES_PINS_VERIFIED'
    & (Join-Path $PSScriptRoot 'start_serial_bridge.ps1')
    $env:GREENHOUSE_BRIDGE_URL = "http://127.0.0.1:$GreenhouseBridgePort"
} else { $env:GREENHOUSE_REAL_ENABLED = '' }
# Keep all simulation sessions/logs and demo accounts in a separate database.
$env:DATABASE_URL = 'sqlite:///' + ((Join-Path $runtime 'demo.db') -replace '\\','/')
$env:CORS_ORIGINS = "http://127.0.0.1:$GreenhouseFrontendPort,http://localhost:$GreenhouseFrontendPort"
$env:VITE_API_PROXY_TARGET = "http://127.0.0.1:$GreenhouseBackendPort"
$env:VITE_API_BASE_URL = '/api'
$api = $null; $web = $null
function Wait-Ready($url,$process,$err) {
    for ($i=0; $i -lt 90; $i++) {
        if ($process.HasExited) { throw ((Get-Content $err -Tail 20) -join "`n") }
        try { $r=Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2; if ($r.StatusCode -eq 200) { return } } catch { Start-Sleep -Milliseconds 500 }
    }
    throw "Service did not start: $url. See $err"
}
try {
    $api=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.main:app','--host','127.0.0.1','--port',"$GreenhouseBackendPort") -WorkingDirectory $backend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'backend.out.log') -RedirectStandardError (Join-Path $runtime 'backend.err.log')
    Wait-Ready "http://127.0.0.1:$GreenhouseBackendPort/api/health" $api (Join-Path $runtime 'backend.err.log')
    $web=Start-Process -FilePath (Get-Command node.exe).Source -ArgumentList @(('"'+(Join-Path $frontend 'node_modules/vite/bin/vite.js')+'"'),'--host','127.0.0.1','--port',"$GreenhouseFrontendPort",'--strictPort') -WorkingDirectory $frontend -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'frontend.out.log') -RedirectStandardError (Join-Path $runtime 'frontend.err.log')
    Wait-Ready "http://127.0.0.1:$GreenhouseFrontendPort" $web (Join-Path $runtime 'frontend.err.log')
    @{ backend=$api.Id; frontend=$web.Id } | ConvertTo-Json | Set-Content (Join-Path $runtime 'demo-pids.json')
} catch {
    if ($web -and -not $web.HasExited) { Stop-Process -Id $web.Id }
    if ($api -and -not $api.HasExited) { Stop-Process -Id $api.Id }
    throw
}
$url="http://127.0.0.1:$GreenhouseFrontendPort/platform/autonomy?mode=guest"
Write-Host "Greenhouse simulation ready: $url" -ForegroundColor Green
if ($DeviceMode -eq 'real') { Write-Host 'Guest page still uses MOCK. Register/sign in on this demo server to access REAL mode.' }
if (-not $NoBrowser) { Start-Process $url }
