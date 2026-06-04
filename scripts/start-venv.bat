@echo off
:: Activate venv
cd /d %~dp0..
call .venv\Scripts\activate.bat
echo Python virtual env activated in %CD%
set PATH=%CD%\scripts;%PATH%
echo Path added toward: %CD%\scripts
cmd /k