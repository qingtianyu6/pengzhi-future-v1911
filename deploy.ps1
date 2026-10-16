param(
    [string]$ServerIp = '134.175.41.179',
    [string]$DeployUser = 'ubuntu'
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$archive = Join-Path $env:TEMP 'promax-deploy.tgz'

& tar --exclude='backend/.env' --exclude='backend/.venv' --exclude='backend/venv' --exclude='backend/data' --exclude='backend/uploads' --exclude='frontend/node_modules' --exclude='frontend/dist' --exclude='node_modules' --exclude='.venv' --exclude='venv' --exclude='__pycache__' --exclude='.pytest_cache' --exclude='*.db' --exclude='*.sqlite*' --exclude='*.log' --exclude='.git' --exclude='*.zip' -czf $archive Dockerfile docker-compose.yml .dockerignore backend frontend
if ($LASTEXITCODE -ne 0) { throw 'Source archive failed.' }

& scp -o BatchMode=yes $archive "${DeployUser}@${ServerIp}:/opt/promax/source.tgz"
if ($LASTEXITCODE -ne 0) { throw 'Source transfer failed.' }

& ssh -o BatchMode=yes "${DeployUser}@${ServerIp}" 'cd /opt/promax && tar -xzf source.tgz && sudo -n docker compose config >/dev/null && sudo -n docker compose build && sudo -n docker compose up -d && sudo -n docker compose ps'
if ($LASTEXITCODE -ne 0) { throw 'Remote deployment failed.' }
