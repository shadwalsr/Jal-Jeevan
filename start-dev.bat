@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"

REM ============================================================
REM  JalJeev - start the full local stack
REM
REM    start-dev.bat          backend on 127.0.0.1 (this PC only)
REM    start-dev.bat lan      backend on 0.0.0.0   (reachable from
REM                           a phone on the same Wi-Fi - use this
REM                           for the Android app on a real device)
REM
REM  Named start-dev.bat, not start.bat, on purpose: a file called
REM  start.bat in this folder would shadow cmd's built-in START.
REM ============================================================

set "BIND=127.0.0.1"
set "MODE=local"
if /i "%~1"=="lan" (
  set "BIND=0.0.0.0"
  set "MODE=lan"
)

echo.
echo  ============================================
echo   JalJeev dev stack   [mode: %MODE%]
echo  ============================================
echo.

REM ---------- 0. sanity: are the pieces here? ----------
if not exist "backend\.venv\Scripts\python.exe" (
  echo  [X] backend\.venv not found.
  echo      Create it first:  cd backend ^&^& python -m venv .venv ^&^& .venv\Scripts\pip install -r requirements.txt
  goto :fail
)
if not exist "docker-compose.yml" (
  echo  [X] docker-compose.yml not found - are you running this from the repo root?
  goto :fail
)

REM ---------- 1. Docker Desktop ----------
REM Docker Desktop does not auto-start on this machine, and every other
REM step depends on it, so start it and wait rather than failing later.
echo  [1/5] Docker...
docker info >nul 2>&1
if errorlevel 1 (
  echo        not running - launching Docker Desktop, this takes ~30-60s
  if exist "%ProgramFiles%\Docker\Docker\Docker Desktop.exe" (
    start "" "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
  ) else (
    echo  [X] Docker Desktop not found at "%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
    echo      Start it manually, then re-run this script.
    goto :fail
  )
  set "READY="
  for /l %%i in (1,1,60) do (
    if not defined READY (
      ping -n 4 127.0.0.1 >nul
      docker info >nul 2>&1
      if not errorlevel 1 set "READY=1"
    )
  )
  if not defined READY (
    echo  [X] Docker did not come up in ~3 minutes. Start it manually and re-run.
    goto :fail
  )
)
echo        ready

REM ---------- 2. Postgres + Redis ----------
REM Only these two. The backend runs as a local process for fast
REM iteration, so we deliberately do NOT bring up the containerised
REM backend / celery services here.
echo  [2/5] Postgres (5433) + Redis (6379)...
docker compose up -d postgres redis
if errorlevel 1 (
  echo  [X] docker compose failed - see the output above.
  goto :fail
)

set "PGREADY="
for /l %%i in (1,1,40) do (
  if not defined PGREADY (
    docker exec jaljeev_postgres pg_isready -U postgres >nul 2>&1
    if not errorlevel 1 (
      set "PGREADY=1"
    ) else (
      ping -n 3 127.0.0.1 >nul
    )
  )
)
if not defined PGREADY (
  echo  [!] Postgres is not answering pg_isready yet. Continuing anyway -
  echo      the backend will retry, but watch for connection errors.
) else (
  echo        ready
)

REM ---------- 3. free port 8000 ----------
REM A stale uvicorn holding 8000 shows up as connection-refused errors
REM that look exactly like a code bug. Kill it explicitly.
echo  [3/5] Checking port 8000...
REM Parentheses are escaped below: an unescaped ^( inside a FOR block ends
REM the block early and batch fails with "- was unexpected at this time".
set "KILLED="
for /f "tokens=5" %%p in ('netstat -ano ^| findstr ":8000" ^| findstr "LISTENING"') do (
  echo        stale process on 8000 ^(PID %%p^) - stopping it
  taskkill /F /PID %%p >nul 2>&1
  set "KILLED=1"
)
if defined KILLED ping -n 3 127.0.0.1 >nul
echo        clear

REM ---------- 4. backend ----------
echo  [4/5] Backend  ^(uvicorn on %BIND%:8000^)...
start "JalJeev backend" cmd /k "cd /d "%~dp0backend" && .venv\Scripts\python.exe -m uvicorn app.main:app --host %BIND% --port 8000"

set "APIREADY="
for /l %%i in (1,1,45) do (
  if not defined APIREADY (
    ping -n 3 127.0.0.1 >nul
    curl -fsS -m 3 http://127.0.0.1:8000/health >nul 2>&1
    if not errorlevel 1 set "APIREADY=1"
  )
)
if not defined APIREADY (
  echo  [!] /health did not answer within ~90s. Check the backend window
  echo      for a traceback - it usually says exactly what is wrong.
) else (
  echo        healthy
)

REM ---------- 5. frontend ----------
echo  [5/5] Frontend ^(Vite on 5173^)...
if not exist "frontend\node_modules" (
  echo        node_modules missing - running npm install, this takes a minute
  pushd frontend
  call npm install
  popd
)
start "JalJeev frontend" cmd /k "cd /d "%~dp0frontend" && npm run dev"

REM ---------- done ----------
echo.
echo  ============================================
echo   Running
echo  ============================================
echo    Frontend    http://localhost:5173
echo    API         http://127.0.0.1:8000
echo    API docs    http://127.0.0.1:8000/docs
echo    Postgres    localhost:5433      Redis  localhost:6379
echo.

if "%MODE%"=="lan" (
  echo   For the Android app on a real phone, set the base URL in
  echo   Settings to one of these ^(same Wi-Fi as this PC^):
  for /f "tokens=2 delims=:" %%a in ('ipconfig ^| findstr /c:"IPv4 Address"') do (
    for /f "tokens=* delims= " %%b in ("%%a") do echo       http://%%b:8000
  )
  echo.
) else (
  echo   Android emulator: base URL is http://10.0.2.2:8000 ^(the default^).
  echo   For a real phone on Wi-Fi, re-run as:  start-dev.bat lan
  echo.
)

echo   Before a demo, warm the caches ^(~10-15 min ahead^):
echo       backend\.venv\Scripts\python.exe scripts\prewarm_demo.py
echo.
echo   Backend and frontend each have their own window. Close a window
echo   to stop that service. Containers keep running: docker compose stop
echo.
popd
endlocal
exit /b 0

:fail
echo.
echo  Startup aborted.
popd
endlocal
exit /b 1
