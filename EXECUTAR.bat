@echo off
setlocal EnableExtensions
title Robo de Conferencia PDF

set "PROJECT_DIR=%~dp0"
if not exist "%PROJECT_DIR%app\" (
    set "PROJECT_DIR=C:\Users\paulo.junior\OneDrive\ROBOS\AUTOMACAO_NOTA_FISCAL\robo_conferencia_pdf\"
)

if not exist "%PROJECT_DIR%app\" (
    echo ERRO: pasta do projeto nao encontrada.
    echo Verifique o caminho configurado dentro de EXECUTAR.bat.
    goto :error
)

cd /d "%PROJECT_DIR%" || goto :error

set "VENV_DIR="
if exist ".venv\Scripts\activate.bat" set "VENV_DIR=.venv"
if not defined VENV_DIR if exist "venv\Scripts\activate.bat" set "VENV_DIR=venv"

if not defined VENV_DIR (
    echo ERRO: ambiente virtual .venv ou venv nao encontrado em:
    echo %CD%
    goto :error
)

call "%VENV_DIR%\Scripts\activate.bat"
if errorlevel 1 (
    echo ERRO: nao foi possivel ativar %VENV_DIR%.
    goto :error
)

set "ENTRYPOINT="
if exist "app\web\__main__.py" set "ENTRYPOINT=app.web"
if not defined ENTRYPOINT if exist "app\main.py" set "ENTRYPOINT=app.main"
if not defined ENTRYPOINT if exist "main.py" set "ENTRYPOINT=main.py"
if not defined ENTRYPOINT if exist "app.py" set "ENTRYPOINT=app.py"
if not defined ENTRYPOINT if exist "run.py" set "ENTRYPOINT=run.py"
if not defined ENTRYPOINT if exist "src\main.py" set "ENTRYPOINT=src\main.py"

if not defined ENTRYPOINT (
    echo ERRO: nenhum ponto de entrada conhecido foi localizado.
    goto :error
)

echo Projeto: %CD%
echo Ambiente virtual: %VENV_DIR%

if /i "%~1"=="--test" goto :test

if "%ENTRYPOINT%"=="app.web" (
    echo Comando: python -m app.web
    python -m app.web
) else if "%ENTRYPOINT%"=="app.main" (
    echo Comando: python -m app.main
    python -m app.main
) else (
    echo Comando: python "%ENTRYPOINT%"
    python "%ENTRYPOINT%"
)

if errorlevel 1 goto :error
exit /b 0

:test
echo Entrypoint detectado: %ENTRYPOINT%
if "%ENTRYPOINT%"=="app.web" (
    python -c "from app.web import app; resposta=app.test_client().get('/'); print('HTTP_TEST:', resposta.status_code); raise SystemExit(0 if resposta.status_code == 200 else 1)"
) else if "%ENTRYPOINT%"=="app.main" (
    python -c "from app.main import main; print('IMPORT_TEST: OK')"
) else (
    python -m py_compile "%ENTRYPOINT%"
)
if errorlevel 1 goto :error
echo TESTE DO EXECUTAR.BAT: OK
exit /b 0

:error
echo.
echo A execucao encontrou um erro.
echo Pressione qualquer tecla para fechar.
pause >nul
exit /b 1
