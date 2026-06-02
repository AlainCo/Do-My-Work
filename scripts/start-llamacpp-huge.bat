@setlocal
@echo off
set SCRIPTDIR=%~dp0.
:: set LLAMA_MODEL=Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
:: set LLAMA_MODEL=Ministral-3-8B-Instruct-2512-Q5_K_M.gguf
:: set LLAMA_MODEL=Ministral-3-14B-Instruct-2512-Q4_K_M.gguf
set LLAMA_MODEL=Mistral-Small-3.2-24B-Instruct-2506-Q4_K_M.gguf
set LLAMA_CONTEXT=4096
%SCRIPTDIR%\start-llamacpp.bat
@endlocal
