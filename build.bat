@echo off
setlocal EnableDelayedExpansion
chcp 65001 >nul 2>&1

echo =====================================================
echo  Lemit Bot - Script de Build para Windows
echo =====================================================
echo.

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo ERRO: Python nao encontrado. Instale Python 3.11 ou superior.
    echo Download: https://www.python.org/downloads/
    pause
    exit /b 1
)

:: Create/activate virtual environment
if not exist ".venv\Scripts\activate.bat" (
    echo Criando ambiente virtual...
    python -m venv .venv
    if errorlevel 1 (
        echo ERRO: Falha ao criar ambiente virtual.
        pause
        exit /b 1
    )
    echo Ambiente virtual criado.
)

echo Ativando ambiente virtual...
call .venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt --quiet --upgrade
if errorlevel 1 (
    echo ERRO: Falha ao instalar dependencias.
    pause
    exit /b 1
)

echo Instalando navegador Playwright Chromium...
playwright install chromium
if errorlevel 1 (
    echo ERRO: Falha ao instalar Playwright Chromium.
    pause
    exit /b 1
)

echo.
echo Compilando executavel com PyInstaller...
pyinstaller lemit_bot.spec --clean --noconfirm
if errorlevel 1 (
    echo ERRO: Falha no PyInstaller.
    pause
    exit /b 1
)

echo.
echo Montando pacote de distribuicao...

:: Copy config template (without real credentials)
echo - Copiando config.json template...
copy "config.json" "dist\lemit_bot\config.json" /Y >nul

:: Copy README
if exist "README.txt" (
    copy "README.txt" "dist\lemit_bot\README.txt" /Y >nul
    echo - Copiando README.txt...
)

:: Create runtime folders
echo - Criando pastas de runtime...
if not exist "dist\lemit_bot\entrada"     mkdir "dist\lemit_bot\entrada"
if not exist "dist\lemit_bot\saida"       mkdir "dist\lemit_bot\saida"
if not exist "dist\lemit_bot\logs"        mkdir "dist\lemit_bot\logs"
if not exist "dist\lemit_bot\checkpoint"  mkdir "dist\lemit_bot\checkpoint"

:: Copy Playwright Chromium browser to bundle
echo - Copiando binarios do Chromium...
set "PW_PATH=%LOCALAPPDATA%\ms-playwright"
if exist "%PW_PATH%" (
    if not exist "dist\lemit_bot\ms-playwright" mkdir "dist\lemit_bot\ms-playwright"
    xcopy "%PW_PATH%\chromium*" "dist\lemit_bot\ms-playwright\" /E /I /Y /Q 2>nul
    if errorlevel 1 (
        echo AVISO: Falha ao copiar Chromium. O bot precisara do Playwright instalado na maquina destino.
    ) else (
        echo   Chromium copiado de: %PW_PATH%
    )
) else (
    echo AVISO: Playwright nao encontrado em %PW_PATH%
    echo        Execute 'playwright install chromium' manualmente e repita o build.
)

echo.
echo =====================================================
echo  Build concluido!
echo  Pacote em: dist\lemit_bot\
echo =====================================================
echo.
echo Proximo passo: edite dist\lemit_bot\config.json com suas credenciais,
echo coloque sua planilha em dist\lemit_bot\entrada\ e execute lemit_bot.exe
echo.
pause
