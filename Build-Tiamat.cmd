@echo off
setlocal

chcp 65001 >nul
set "ROOT_DIR=%~dp0"
set "APP_FILE=%ROOT_DIR%tiamat\tray_app.pyw"
set "SPEC_FILE=%ROOT_DIR%Tiamat.spec"
set "PYTHON_CMD="

if not exist "%APP_FILE%" (
    echo Nao foi possivel localizar "%APP_FILE%".
    exit /b 1
)

call :remove_dir "%ROOT_DIR%build"
if errorlevel 1 exit /b 1

call :remove_dir "%ROOT_DIR%build-status"
if errorlevel 1 exit /b 1

call :remove_dir "%ROOT_DIR%dist"
if errorlevel 1 exit /b 1

call :remove_dir "%ROOT_DIR%dist-status"
if errorlevel 1 exit /b 1

if exist "%SPEC_FILE%" (
    del /f /q "%SPEC_FILE%" >nul 2>nul
    if exist "%SPEC_FILE%" (
        echo Nao foi possivel remover "%SPEC_FILE%".
        echo Feche qualquer processo que esteja usando o arquivo e tente novamente.
        exit /b 1
    )
)

where python >nul 2>nul
if not errorlevel 1 (
    python -c "import PyInstaller, pystray, PIL" >nul 2>nul
    if not errorlevel 1 set "PYTHON_CMD=python"
)

if not defined PYTHON_CMD (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 -c "import PyInstaller, pystray, PIL" >nul 2>nul
        if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
)

if not defined PYTHON_CMD (
    echo Nenhum interpretador Python com PyInstaller, pystray e Pillow foi encontrado.
    echo Instale as dependencias com: pip install -r tiamat\requirements.txt
    exit /b 1
)

%PYTHON_CMD% -m PyInstaller --noconfirm --clean --name Tiamat --onedir --windowed "%APP_FILE%"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo Build falhou com codigo %EXIT_CODE%.
    exit /b %EXIT_CODE%
)

echo.
echo Build concluido com sucesso.
echo Executavel: "%ROOT_DIR%dist\Tiamat\Tiamat.exe"
exit /b 0

:remove_dir
if not exist "%~1" exit /b 0

rmdir /s /q "%~1" >nul 2>nul
if exist "%~1" (
    echo Nao foi possivel remover "%~1".
    echo Feche o Tiamat ou qualquer processo usando essa pasta e tente novamente.
    exit /b 1
)

exit /b 0
