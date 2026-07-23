@echo off
setlocal

cd /d "%~dp0"

where git >nul 2>nul
if errorlevel 1 (
    echo Git no esta disponible en PATH.
    pause
    exit /b 1
)

git rev-parse --is-inside-work-tree >nul 2>nul
if errorlevel 1 (
    echo Esta carpeta no es un repositorio de Git.
    pause
    exit /b 1
)

:menu
cls
echo ========================================
echo  Astrogato Vector - Git
echo ========================================
echo.
echo Carpeta: %CD%
echo.
echo Estado actual:
git status --short
echo.
echo [1] Guardar git diff en diff-fecha.txt
echo [2] Subir cambios a GitHub
echo [3] Guardar diff y subir cambios
echo [4] Salir
echo.
set /p "OPTION=Elige una opcion: "

if "%OPTION%"=="1" (
    call :save_diff
    pause
    goto menu
)

if "%OPTION%"=="2" (
    call :push_changes
    pause
    goto menu
)

if "%OPTION%"=="3" (
    call :save_diff
    if errorlevel 1 (
        pause
        goto menu
    )
    call :push_changes
    pause
    goto menu
)

if "%OPTION%"=="4" (
    exit /b 0
)

echo Opcion no valida.
pause
goto menu

:timestamp
for /f %%A in ('powershell -NoProfile -Command "Get-Date -Format yyyy-MM-dd_HH-mm-ss"') do set "STAMP=%%A"
exit /b 0

:save_diff
call :timestamp
set "DIFF_FILE=diff-%STAMP%.txt"
git diff > "%DIFF_FILE%"
if errorlevel 1 (
    echo No fue posible guardar el diff.
    exit /b 1
)
echo Diff guardado en %DIFF_FILE%
exit /b 0

:push_changes
set "HAS_CHANGES="
for /f "delims=" %%A in ('git status --porcelain') do set "HAS_CHANGES=1"

if not defined HAS_CHANGES (
    echo No hay cambios para subir.
    exit /b 0
)

echo.
set /p "COMMIT_MSG=Mensaje del commit (Enter para usar fecha): "
if "%COMMIT_MSG%"=="" (
    call :timestamp
    set "COMMIT_MSG=Actualizacion %STAMP%"
)
set "COMMIT_MSG=%COMMIT_MSG:"='%"

git add .
if errorlevel 1 (
    echo Fallo git add.
    exit /b 1
)

git commit -m "%COMMIT_MSG%"
if errorlevel 1 (
    echo Fallo git commit.
    exit /b 1
)

git push
if errorlevel 1 (
    echo Fallo git push.
    exit /b 1
)

echo Cambios subidos correctamente.
exit /b 0
