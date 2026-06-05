# Forge — create .venv and install dependencies (does NOT touch system Python)
$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$VenvPython = Join-Path $Root ".venv\Scripts\python.exe"
$VenvPip = Join-Path $Root ".venv\Scripts\pip.exe"

Write-Host "==> Forge: creating virtual environment at .venv" -ForegroundColor Cyan
if (-not (Test-Path $VenvPython)) {
    py -3 -m venv (Join-Path $Root ".venv")
    if ($LASTEXITCODE -ne 0) { throw "venv creation failed" }
}

Write-Host "==> Upgrading pip (inside venv)" -ForegroundColor Cyan
& $VenvPython -m pip install -U pip

# Prefer official PyPI if mirror is blocked
$Index = if ($env:PIP_INDEX_URL) { $env:PIP_INDEX_URL } else { "https://pypi.org/simple" }

Write-Host "==> Installing requirements.txt + editable forge package" -ForegroundColor Cyan
& $VenvPip install -r (Join-Path $Root "requirements.txt") -i $Index
& $VenvPip install -e $Root -i $Index

Write-Host ""
Write-Host "Done. Activate with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host ""
Write-Host "Then run:" -ForegroundColor Green
Write-Host "  .\run.ps1 --scenario security"
Write-Host "  .\run.ps1 --web"
