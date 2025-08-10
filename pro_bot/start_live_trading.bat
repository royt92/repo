@echo off
setlocal EnableExtensions
echo === LIVE START ===

REM Prefer .env.live, else use existing .env (MODE=live)

if exist ".env.live" (
  copy /Y ".env.live" ".env" >nul
  set MODE_VAL=live
) else (
  if exist ".env" (
    for /f "tokens=1,2 delims==" %%a in ('findstr /i "^MODE=" ".env"') do set MODE_VAL=%%b
  ) else (
    echo ERROR: No .env.live or .env found. Create one with MODE=live
    exit /b 1
  )
)

if /i not "%MODE_VAL%"=="live" (
  echo ERROR: MODE is not live (MODE=%MODE_VAL%). Set MODE=live in .env
  exit /b 1
)

REM Choose python
set "PYEXE=py"
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"

%PYEXE% -m src.app daemon
endlocal

