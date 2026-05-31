
@echo off
cd %~dp0
set MODEL=model\Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
set LLAMAHOME=llama-b9442-bin-win-cpu-x64
set PORT=8000
set CTXSIZE=8192

@echo on
%LLAMAHOME%\llama-server.exe ^
  -m %MODEL% ^
  --host 127.0.0.1 ^
  --port %PORT% ^
  --ctx-size %CTXSIZE% ^
  -t 12 ^
  --batch-size 512 ^
  --ubatch-size 512 ^
  --verbose ^
  --mlock
@echo off
echo.
pause
