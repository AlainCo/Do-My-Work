@echo off
setlocal

set "SCRIPT_DIR=%~dp0"
for %%I in ("%SCRIPT_DIR%..") do set "REPO_ROOT=%%~fI"

set "PYTHON_EXE=%REPO_ROOT%\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
    echo Could not find "%PYTHON_EXE%".
    echo Create the project virtual environment first, then run:
    echo   python -m pip install -e ".[dev]"
    echo   python -m pip install pyinstaller
    exit /b 1
)

if "%~1"=="--check" (
    echo Repo root: %REPO_ROOT%
    echo Python executable: %PYTHON_EXE%
    "%PYTHON_EXE%" -m PyInstaller --version >nul 2>nul
    if errorlevel 1 (
        echo PyInstaller is not available in the project environment.
        echo Install it with:
        echo   python -m pip install pyinstaller
        exit /b 1
    )
    echo PyInstaller: available
    exit /b 0
)

pushd "%REPO_ROOT%" >nul
"%PYTHON_EXE%" -m PyInstaller ^
  --noconfirm ^
  --clean ^
  --name do-my-work ^
  --console ^
  --paths src ^
  --collect-all trafilatura ^
  src/do_my_work/cli.py
set "EXIT_CODE=%ERRORLEVEL%"
popd >nul

if not "%EXIT_CODE%"=="0" (
    exit /b %EXIT_CODE%
)

echo Build completed.
echo Bundle path: %REPO_ROOT%\dist\do-my-work\
exit /b 0