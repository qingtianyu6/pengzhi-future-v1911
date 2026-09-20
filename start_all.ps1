$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir = Join-Path $ProjectRoot "backend"
$FrontendDir = Join-Path $ProjectRoot "frontend"
$RuntimeDir = Join-Path $ProjectRoot ".run"
$PythonExe = Join-Path $BackendDir ".venv\Scripts\python.exe"

function Assert-PortFree([int]$Port, [string]$Name) {
    $Listener = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($null -ne $Listener) {
        $PidText = if ($Listener.OwningProcess) { "，PID $($Listener.OwningProcess)" } else { "" }
        throw "$Name 端口 $Port 已被占用$PidText。请先关闭占用程序，或运行 .\stop_all.ps1 后重试。"
    }
}

function Wait-Http([string]$Url, [System.Diagnostics.Process]$Process, [string]$ErrorLog, [int]$Attempts = 40) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        if ($Process.HasExited) {
            $Tail = if (Test-Path $ErrorLog) { (Get-Content $ErrorLog -Tail 16) -join [Environment]::NewLine } else { "没有错误日志。" }
            throw "进程启动失败。`n$Tail"
        }
        try {
            $Response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 2
            if ($Response.StatusCode -ge 200 -and $Response.StatusCode -lt 500) { return }
        } catch {
            Start-Sleep -Milliseconds 500
        }
    }
    throw "服务未在预期时间内就绪：$Url。请查看 $ErrorLog。"
}

if (-not (Test-Path $PythonExe)) {
    throw "后端虚拟环境不存在，请先运行 .\setup.ps1。"
}
if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    throw "前端依赖不存在，请先运行 .\setup.ps1。"
}

Assert-PortFree 8000 "后端"
Assert-PortFree 5173 "前端"
New-Item -ItemType Directory -Force -Path $RuntimeDir | Out-Null

$BackendOut = Join-Path $RuntimeDir "backend.out.log"
$BackendErr = Join-Path $RuntimeDir "backend.err.log"
$FrontendOut = Join-Path $RuntimeDir "frontend.out.log"
$FrontendErr = Join-Path $RuntimeDir "frontend.err.log"

$BackendProcess = Start-Process -FilePath $PythonExe `
    -ArgumentList @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory $BackendDir -PassThru `
    -RedirectStandardOutput $BackendOut -RedirectStandardError $BackendErr
$BackendProcess.Id | Set-Content -Encoding ascii (Join-Path $RuntimeDir "backend.pid")

try {
    Wait-Http "http://127.0.0.1:8000/api/health" $BackendProcess $BackendErr
} catch {
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    throw
}

$FrontendProcess = Start-Process -FilePath "npm.cmd" `
    -ArgumentList @("run", "dev", "--", "--host", "127.0.0.1", "--port", "5173", "--strictPort") `
    -WorkingDirectory $FrontendDir -PassThru `
    -RedirectStandardOutput $FrontendOut -RedirectStandardError $FrontendErr
$FrontendProcess.Id | Set-Content -Encoding ascii (Join-Path $RuntimeDir "frontend.pid")

try {
    Wait-Http "http://127.0.0.1:5173" $FrontendProcess $FrontendErr
} catch {
    Stop-Process -Id $FrontendProcess.Id -Force -ErrorAction SilentlyContinue
    Stop-Process -Id $BackendProcess.Id -Force -ErrorAction SilentlyContinue
    throw
}

Write-Host "后端已启动：http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "前端已启动：http://127.0.0.1:5173" -ForegroundColor Green
Write-Host "接口文档：http://127.0.0.1:8000/docs" -ForegroundColor Green
Start-Process "http://127.0.0.1:5173"
