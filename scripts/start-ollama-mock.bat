@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Could not find "%PYTHON_EXE%".
    echo Install the project environment first, then run:
    echo   python -m pip install -e ".[mock-ollama]"
    exit /b 1
)

if "%~1"=="--check" (
    echo Repo root: %REPO_ROOT%
    echo Python executable: %PYTHON_EXE%
    exit /b 0
)

pushd "%REPO_ROOT%" >nul
"%PYTHON_EXE%" -m tests.support.ollama_mock_server
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

exit /b %EXIT_CODE%