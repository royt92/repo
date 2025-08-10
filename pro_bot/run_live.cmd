@echo off
setlocal EnableExtensions
echo === LIVE START (CMD) ===

if exist ".env.live" copy /Y ".env.live" ".env" >nul
if not exist ".env" (
  echo ERROR: .env not found. Create .env or .env.live with MODE=live
  exit /b 1
)

set "MODE_VAL="
for /f "tokens=1,2 delims==" %%A in ('findstr /i "^MODE=" ".env"') do set "MODE_VAL=%%B"
if /i not "%MODE_VAL%"=="live" (
  echo ERROR: MODE is not live (MODE=%MODE_VAL%). Set MODE=live in .env
  exit /b 1
)

set "PYEXE=py"
if exist ".venv\Scripts\python.exe" set "PYEXE=.venv\Scripts\python.exe"
%PYEXE% -m src.app daemon
exit /b %errorlevel%


