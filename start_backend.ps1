$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) { throw "后端虚拟环境不存在，请先运行 .\setup.ps1。" }
$Listener = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $Listener) { throw "端口 8000 已被占用，PID $($Listener.OwningProcess)。" }

Set-Location $BackendDir
& $PythonExe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
