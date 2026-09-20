$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) { throw "后端环境不存在，请先运行 .\setup.ps1。" }
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) { throw "前端依赖不存在，请先运行 .\setup.ps1。" }
$Listener = Get-NetTCPConnection -State Listen -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -First 1
if ($null -ne $Listener) { throw "端口 8000 已被占用，PID $($Listener.OwningProcess)。请关闭旧服务后再启动。" }

Write-Host "正在构建前端..." -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "前端构建失败。" }
} finally {
    Pop-Location
}

Write-Host "生产服务启动中：http://127.0.0.1:8000" -ForegroundColor Green
Set-Location $BackendDir
$env:HOST = "0.0.0.0"
$env:PORT = "8000"
& $PythonExe run.py
