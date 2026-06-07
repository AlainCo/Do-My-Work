@setlocal
@echo off
set SCRIPTDIR=%~dp0.
set LLAMA_ARG_MODEL=Mistral-Nemo-Instruct-2407-Q6_K_L.gguf
%SCRIPTDIR%\start-llamacpp.bat
@endlocal
