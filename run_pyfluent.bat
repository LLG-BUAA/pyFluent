@echo off
setlocal

cd /d "%~dp0"

set "PYTHON_EXE=C:\Users\LLG-P\AppData\Local\Microsoft\WindowsApps\python3.11.exe"

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python executable not found:
    echo %PYTHON_EXE%
    echo.
    pause
    exit /b 1
)

"%PYTHON_EXE%" "%~dp0pyfluent_ui.py"
set "EXIT_CODE=%ERRORLEVEL%"

if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] pyFluent exited with code %EXIT_CODE%.
    pause
)

exit /b %EXIT_CODE%