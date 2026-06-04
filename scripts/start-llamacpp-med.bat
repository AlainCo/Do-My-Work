@setlocal
@echo off
set SCRIPTDIR=%~dp0.
set LLAMA_ARG_MODEL=Ministral-3-8B-Instruct-2512-Q5_K_M.gguf
%SCRIPTDIR%\start-llamacpp.bat
@endlocal
