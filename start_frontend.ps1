$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$FrontendDir = Join-Path $ProjectRoot "frontend"

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { throw "前端依赖不存在，请先运行 .\setup.ps1。" }
$Listener = Get-NetTCPConnection -State Listen -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $Listener) { throw "端口 5173 已被占用，PID $($Listener.OwningProcess)。" }

Set-Location $FrontendDir
npm.cmd run dev -- --host 127.0.0.1 --port 5173 --strictPort
