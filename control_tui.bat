@echo off
setlocal
title Astrogato Vector TUI

cd /d "%~dp0"

uv --version >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
  echo No se encontro uv. Instala uv desde https://github.com/astral-sh/uv
  pause
  exit /b 1
)

uv run --with textual python tools\control_tui.py %*
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
  echo.
  echo La TUI termino con codigo %EXIT_CODE%.
  pause
)

exit /b %EXIT_CODE%
