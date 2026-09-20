$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Get-Command python -ErrorAction SilentlyContinue)) {
    throw "未找到 Python。请先安装 Python 3.11 或 3.12，并勾选 Add Python to PATH。"
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    throw "未找到 npm。请先安装 Node.js 20 LTS。"
}

if (-not (Test-Path $PythonExe)) {
    Write-Host "[1/4] 创建后端虚拟环境..." -ForegroundColor Cyan
    python -m venv (Join-Path $BackendDir ".venv")
}

Write-Host "[2/4] 安装后端依赖..." -ForegroundColor Cyan
& $PythonExe -m pip install --upgrade pip
& $PythonExe -m pip install -r (Join-Path $BackendDir "requirements.txt")

Write-Host "[3/4] 安装前端依赖..." -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm.cmd ci
} finally {
    Pop-Location
}

Write-Host "[4/4] 安装完成。开发运行 .\start_all.ps1；生产运行 .\start_production.ps1。" -ForegroundColor Green

