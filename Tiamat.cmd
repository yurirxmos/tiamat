@echo off
setlocal

chcp 65001 >nul
set "ROOT_DIR=%~dp0"
set "APP_FILE=%ROOT_DIR%tiamat\tray_app.pyw"
set "RUN_CMD="

if not exist "%APP_FILE%" (
    echo Nao foi possivel localizar "%APP_FILE%".
    pause
    exit /b 1
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import pystray, PIL" >nul 2>nul
    if not errorlevel 1 (
        where pythonw >nul 2>nul
        if not errorlevel 1 set "RUN_CMD=pythonw"
    )
)

if not defined RUN_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import pystray, PIL" >nul 2>nul
        if not errorlevel 1 (
            where pyw >nul 2>nul
            if not errorlevel 1 set "RUN_CMD=pyw -3"
        )
    )
)

if not defined RUN_CMD (
    echo Nenhum interpretador Python com pystray e Pillow foi encontrado.
    echo Instale as dependencias com: pip install -r tiamat\requirements.txt
    pause
    exit /b 1
)

start "" /b %RUN_CMD% "%APP_FILE%"
exit /b 0
