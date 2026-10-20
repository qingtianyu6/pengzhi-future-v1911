$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
. (Join-Path $PSScriptRoot 'greenhouse.config.ps1')
$runtime=Join-Path $root '.run\greenhouse'
New-Item -ItemType Directory -Force $runtime | Out-Null
$secretFile=Join-Path $runtime 'bridge-token.xml'
# Windows DPAPI: encrypted token is readable only by this Windows user.
if (Test-Path $secretFile) {
    $secure=Import-Clixml -LiteralPath $secretFile
    $env:GREENHOUSE_BRIDGE_TOKEN=[System.Net.NetworkCredential]::new('', $secure).Password
} else {
    $bytes=New-Object byte[] 32
    $rng=[System.Security.Cryptography.RandomNumberGenerator]::Create(); $rng.GetBytes($bytes); $rng.Dispose()
    $env:GREENHOUSE_BRIDGE_TOKEN=[Convert]::ToBase64String($bytes)
    ConvertTo-SecureString $env:GREENHOUSE_BRIDGE_TOKEN -AsPlainText -Force | Export-Clixml -LiteralPath $secretFile
}
$env:GREENHOUSE_SERIAL_PORT=$GreenhouseSerialPort
$env:GREENHOUSE_SERIAL_BAUD="$GreenhouseSerialBaud"
$env:GREENHOUSE_BRIDGE_URL="http://127.0.0.1:$GreenhouseBridgePort"
$headers=@{Authorization='Bearer '+$env:GREENHOUSE_BRIDGE_TOKEN}
if (Get-NetTCPConnection -LocalPort $GreenhouseBridgePort -State Listen -ErrorAction SilentlyContinue) {
    try { $null=Invoke-RestMethod -Uri "$env:GREENHOUSE_BRIDGE_URL/status" -Headers $headers; Write-Host 'Existing authorized serial bridge reused.'; return }
    catch { throw 'Bridge port occupied by an unknown/unauthorized process.' }
}
$python=Join-Path $root 'backend\.venv\Scripts\python.exe'
& $python -c 'import serial'
if ($LASTEXITCODE) { & $python -m pip install pyserial==3.5; if ($LASTEXITCODE) { throw 'pyserial installation failed' } }
$process=Start-Process -FilePath $python -ArgumentList @('-m','uvicorn','app.greenhouse_sim.bridge:create_bridge','--factory','--host','127.0.0.1','--port',"$GreenhouseBridgePort") -WorkingDirectory (Join-Path $root 'backend') -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runtime 'bridge.out.log') -RedirectStandardError (Join-Path $runtime 'bridge.err.log')
$process.Id | Set-Content (Join-Path $runtime 'bridge.pid')
for ($i=0; $i -lt 40; $i++) {
    if ($process.HasExited) { throw ((Get-Content (Join-Path $runtime 'bridge.err.log') -Tail 15) -join "`n") }
    try { $null=Invoke-RestMethod -Uri "$env:GREENHOUSE_BRIDGE_URL/status" -Headers $headers; Write-Host 'Authorized loopback serial bridge ready.'; return } catch { Start-Sleep -Milliseconds 500 }
}
Stop-Process -Id $process.Id
throw 'Bridge startup timeout'
