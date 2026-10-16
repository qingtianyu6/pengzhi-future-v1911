param([switch]$WithBrowser)
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
    if ($LASTEXITCODE -ne 0) { throw "后端测试失败，退出码：$LASTEXITCODE" }
} finally {
    Pop-Location
}

Write-Host "[2/4] 前端 Lint" -ForegroundColor Cyan
Push-Location $FrontendDir
try {
    npm.cmd run lint
    if ($LASTEXITCODE -ne 0) { throw "前端 Lint 失败，退出码：$LASTEXITCODE" }
    Write-Host "[3/4] 前端生产构建" -ForegroundColor Cyan
    npm.cmd run build
    if ($LASTEXITCODE -ne 0) { throw "前端生产构建失败，退出码：$LASTEXITCODE" }
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

if ($WithBrowser) {
    Write-Host "浏览器操作检查（需要本机前端已运行）" -ForegroundColor Cyan
    python (Join-Path $ProjectRoot "improvements_20261014\smoke_e2e.py")
    if ($LASTEXITCODE -ne 0) { throw "浏览器操作检查失败" }
}

Write-Host "发布包验证通过。" -ForegroundColor Green
