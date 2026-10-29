@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
    echo Ambiente Python nao encontrado. Consulte o README para preparar o projeto.
    pause
    exit /b 1
)
echo.
echo Horulince - Central de testes
echo Abra http://127.0.0.1:8765 no navegador.
echo Mantenha esta janela aberta. Para encerrar, pressione Ctrl+C.
echo.
".venv\Scripts\python.exe" -m horulince painel --abrir
if errorlevel 1 pause
