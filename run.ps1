# Run Forge CLI using project venv (never system Python)
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "[Forge] .venv not found. Run: .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

& $VenvPython (Join-Path $Root "main.py") @args
exit $LASTEXITCODE
