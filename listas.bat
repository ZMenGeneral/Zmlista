@echo off
cd /d "%~dp0"
set "PYEXE="
where python 2>nul >nul
if %errorlevel%==0 set "PYEXE=python"
if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
if not defined PYEXE (
    echo Python no encontrado. Instalalo desde https://www.python.org
    pause
    exit /b 1
)
"%PYEXE%" "%~dp0MenuPrincipal.py" %*
echo.
pause
