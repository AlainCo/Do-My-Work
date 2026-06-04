@setlocal
@echo off
set SCRIPTDIR=%~dp0.
set LLAMA_ARG_MODEL=Ministral-3-14B-Instruct-2512-Q4_K_M.gguf
%SCRIPTDIR%\start-llamacpp.bat
@endlocal
