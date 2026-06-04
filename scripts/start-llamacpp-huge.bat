@setlocal
@echo off
set SCRIPTDIR=%~dp0.
set LLAMA_ARG_MODEL=Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf
%SCRIPTDIR%\start-llamacpp.bat
@endlocal
