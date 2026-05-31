
@echo off

if "%LLAMA_HOME%"=="" (
    echo LLAMA_HOME environment variable is not set. Please set it to the path of your llama server installation.
    exit /b 1
)
echo Using llama server from LLAMA_HOME: %LLAMA_HOME%

set PORT=8000
set CTXSIZE=8192
set MODEL=Ministral-3-3B-Instruct-2512-Q4_K_M.gguf

set APPOPTS=-m "%LLAMA_HOME%\model\%MODEL%" --ctx-size %CTXSIZE% 
set TRACEOPTS=
rem set TRACEOPTS=%TRACEOPTS% --verbose 
set TRACEOPTS=%TRACEOPTS% --metrics
set NETOPTS=--host 127.0.0.1 --port %PORT%
set PERFOPTS=-t 12  --batch-size 512 --ubatch-size 512  --mlock

@echo on
"%LLAMA_HOME%\llama-server.exe" %APPOPTS% %NETOPTS% %PERFOPTS% %TRACEOPTS%
@echo off
echo.
pause
