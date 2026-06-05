@echo off
REM Forge — create .venv and install deps (isolated from system Python)
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo ==^> Creating .venv ...
    py -3 -m venv .venv
    if errorlevel 1 exit /b 1
)

echo ==^> Upgrading pip ...
".venv\Scripts\python.exe" -m pip install -U pip

echo ==^> Installing requirements ...
".venv\Scripts\pip.exe" install -r requirements.txt -i https://pypi.org/simple
".venv\Scripts\pip.exe" install -e . -i https://pypi.org/simple

echo.
echo Done. Activate:  .venv\Scripts\activate.bat
echo Run:            run.bat --scenario security
exit /b 0
