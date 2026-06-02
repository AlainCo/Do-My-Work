
@echo off

if "%LLAMA_HOME%"=="" (
    echo LLAMA_HOME environment variable is not set. Please set it to the path of your llama server installation.
    exit /b 1
)
echo Using llamacpp server from LLAMA_HOME: %LLAMA_HOME%

if "%LLAMA_NBCORE%"=="" (
    echo LLAMA_NBCORE environment variable is not set. Please set it to the number of real processor cores on your llama server installation.
    exit /b 1
)

echo Using llamacpp core number: %LLAMA_NBCORE%

if "%LLAMA_MODEL%"=="" (
    echo LLAMA_MODEL environment variable is not set. Please set it to the name of the llama model you want to use.
    exit /b 1
)

echo Using llamacpp model: %LLAMA_MODEL%

if "%LLAMA_PORT%"=="" (
    echo LLAMA_PORT environment variable is not set. Set to 8000.
    set LLAMA_PORT=8000
)

echo Using llamacpp port: %LLAMA_PORT%

if "%LLAMA_CONTEXT%"=="" (
    echo LLAMA_CONTEXT environment variable is not set. Set to 4096.
    set LLAMA_CONTEXT=4096
)

echo Using llamacpp context size: %LLAMA_CONTEXT%




set PORT=8000
set LLAMA_CONTEXT=4096
rem set LLAMA_MODEL=Ministral-3-3B-Instruct-2512-Q4_K_M.gguf
rem set LLAMA_MODEL=Ministral-3-8B-Instruct-2512-Q5_K_M.gguf
rem set LLAMA_MODEL=Ministral-3-14B-Instruct-2512-Q4_K_M.gguf

set APPOPTS=--model "%LLAMA_HOME%\model\%LLAMA_MODEL%" --ctx-size %LLAMA_CONTEXT% 
set TRACEOPTS=
rem set TRACEOPTS=%TRACEOPTS% --verbose --metrics 
set TRACEOPTS=%TRACEOPTS% --log-verbosity 3
set NETOPTS=--host 127.0.0.1 --port %LLAMA_PORT%
set PERFOPTS=--threads %LLAMA_NBCORE%  --batch-size 512 --ubatch-size 512  --mlock

@echo on
"%LLAMA_HOME%\llama-server.exe" %APPOPTS% %NETOPTS% %PERFOPTS% %TRACEOPTS%
@echo off
echo.
pause
