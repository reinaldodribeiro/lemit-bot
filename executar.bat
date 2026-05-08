@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

python src\main.py
set EXITCODE=%ERRORLEVEL%

echo.
echo =====================================================
echo  Execucao finalizada (codigo: %EXITCODE%)
echo =====================================================
pause
endlocal
