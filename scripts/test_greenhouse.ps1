param([switch]$AllBackend,[switch]$Browser)
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $PSScriptRoot
$python=Join-Path $root 'backend\.venv\Scripts\python.exe'
& $python -c 'import ziglang'
if ($LASTEXITCODE) { & $python -m pip install -r (Join-Path $root 'backend\requirements-greenhouse-dev.txt'); if ($LASTEXITCODE) { throw 'Development dependency installation failed.' } }
Push-Location (Join-Path $root 'backend')
try {
    $suite=if($AllBackend){'tests'}else{@('tests/test_greenhouse_simulation.py','tests/test_greenhouse_safety_edges.py')}
    & $python -m pytest $suite -q
    if ($LASTEXITCODE) { throw 'Backend tests failed.' }
} finally { Pop-Location }
& $python (Join-Path $root 'firmware\greenhouse_stm32\build.py')
if ($LASTEXITCODE) { throw 'Firmware build failed.' }
Push-Location (Join-Path $root 'frontend')
try { & npm.cmd run build; if ($LASTEXITCODE) { throw 'Frontend build failed.' } } finally { Pop-Location }
if ($Browser) { & $python (Join-Path $root 'backend\scripts\check_greenhouse_browser.py'); if ($LASTEXITCODE) { throw 'Browser verification failed.' } }
