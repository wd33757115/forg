@echo off
cd /d "%~dp0"

if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "%~dp0main.py" %*
    exit /b %ERRORLEVEL%
)

echo [Forge] .venv not found. Run setup.bat first.
echo         setup.bat
exit /b 1
