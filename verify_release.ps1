$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

if (-not (Test-Path $PythonExe)) {
    throw "请先运行 .\setup.ps1。"
}

Write-Host "[1/4] 后端测试" -ForegroundColor Cyan
Push-Location $BackendDir
try {
    & $PythonExe -m pytest -q
} finally {
    Pop-Location
}

Write-Host "[2/4] 前端 Lint" -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm.cmd run lint
    Write-Host "[3/4] 前端生产构建" -ForegroundColor Cyan
    npm.cmd run build
} finally {
    Pop-Location
}

Write-Host "[4/4] 模型文件存在性" -ForegroundColor Cyan
$RequiredModels = @(
    "backend\app\ml\artifacts\environment_forecast_v0.1\final_model.pt",
    "backend\app\ml\artifacts\environment_forecast_v0.2\champion_registry.json",
    "backend\app\artifacts\disease\v0.1\model.pt"
)
foreach ($RelativePath in $RequiredModels) {
    $FullPath = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path $FullPath)) {
        throw "缺少模型产物：$RelativePath"
    }
}

Write-Host "发布包验证通过。" -ForegroundColor Green

