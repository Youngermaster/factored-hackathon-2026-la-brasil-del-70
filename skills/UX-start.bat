@echo off
rem UX-start.bat: start the local backend (PostgreSQL and the API) and the web app, then open the browser.
rem
rem It assumes the one-time setup is done on this machine (.env exists and the database is seeded).
rem For the first setup or a repair, ask your agent to run skills/UX-Backend-start/SKILL.md.
rem It never reads or prints .env, never deletes volumes or data, and never touches git.
rem
rem Usage (double-click, or from any folder):
rem   UX-start.bat                 start everything and open http://localhost:5173
rem   UX-start.bat --no-browser    start everything without opening the browser
rem   UX-start.bat status          show the containers and the API health
rem   UX-start.bat stop            stop the containers; the database stays in its volume
rem   UX-start.bat https://host    open an already deployed server instead of starting locally

setlocal EnableExtensions
set "SELF=%~nx0"
set "WEB_URL=http://localhost:5173/"
set "API_READY_URL=http://localhost:8000/health/ready"
set "DOCKER_DESKTOP=%ProgramFiles%\Docker\Docker\Docker Desktop.exe"
set "OPEN_BROWSER=1"
set "EXIT_CODE=0"

pushd "%~dp0.." || goto :no_repo
if not exist "docker-compose.yml" (
  popd
  goto :no_repo
)

set "ACTION=%~1"
if "%ACTION%"=="" goto :start
if /i "%ACTION%"=="--no-browser" (
  set "OPEN_BROWSER=0"
  goto :start
)
if /i "%ACTION%"=="stop" goto :stop
if /i "%ACTION%"=="status" goto :status
if /i "%ACTION:~0,4%"=="http" goto :remote
echo [UX-start] Unknown option "%ACTION%". Use no option, --no-browser, status, stop, or a server URL.
set "EXIT_CODE=2"
goto :end

:start
call :ensure_docker || goto :fail

if not exist ".env" (
  echo [UX-start] .env is missing, so the one-time setup has not run on this machine.
  echo            Ask your agent to run skills/UX-Backend-start, or run "make env" and "make seed".
  goto :fail
)
if not exist "apps\web\.env.local" (
  echo [UX-start] Note: apps\web\.env.local is missing, so the sign-in page hides the demo persona list.
)

echo [UX-start] Starting PostgreSQL, the API, and the web app. The first start can take a few minutes.
docker compose --profile api --profile web up -d --wait --wait-timeout 600
if errorlevel 1 (
  echo [UX-start] A container did not become healthy. Last API log lines:
  docker compose logs --no-color --tail 40 api
  goto :fail
)

set "CUSTOMERS="
for /f "usebackq delims=" %%C in (`docker compose exec -T postgres sh -c "psql -U $POSTGRES_USER -d $POSTGRES_DB -tAc 'select count(*) from app.customers'" 2^>nul`) do set "CUSTOMERS=%%C"
if not defined CUSTOMERS set "CUSTOMERS=0"
if "%CUSTOMERS%"=="0" (
  echo [UX-start] Warning: the database has no customers yet, so sign-in will fail.
  echo            Ask your agent to run skills/UX-Backend-start to build the data and seed it.
) else (
  echo [UX-start] Database ready with %CUSTOMERS% customers.
)

call :wait_url "%API_READY_URL%" "The API" || goto :fail
call :wait_url "%WEB_URL%" "The web app" || goto :fail

if "%OPEN_BROWSER%"=="1" start "" "%WEB_URL%"
echo.
echo [UX-start] Ready.
echo   Web app:   %WEB_URL%
echo   API docs:  http://localhost:8000/docs
echo   Sign in with a demo persona, for example acc-mx-accounts, agent-demo-01, or evaluator-demo-01.
echo   The one-time code is shown on screen in demo mode.
echo   Stop with: skills\UX-start.bat stop
goto :end

:status
call :ensure_docker || goto :fail
docker compose --profile api --profile web ps
echo.
curl.exe -s --max-time 5 "%API_READY_URL%"
echo.
goto :end

:stop
call :ensure_docker || goto :fail
echo [UX-start] Stopping the containers. The database stays in its volume.
docker compose --profile "*" down
goto :end

:remote
echo [UX-start] Opening the deployed server at %ACTION%
curl.exe -s -o nul --max-time 10 "%ACTION%"
if errorlevel 1 echo [UX-start] Warning: %ACTION% did not answer; opening it anyway.
start "" "%ACTION%"
goto :end

rem ---------------------------------------------------------------------------------------------
rem Subroutines

:ensure_docker
"%SystemRoot%\System32\where.exe" docker >nul 2>&1
if errorlevel 1 (
  echo [UX-start] Docker is not installed. Install Docker Desktop, then run this again.
  exit /b 1
)
docker info >nul 2>&1
if not errorlevel 1 exit /b 0
if not exist "%DOCKER_DESKTOP%" (
  echo [UX-start] The Docker engine is not running. Start Docker Desktop, then run this again.
  exit /b 1
)
echo [UX-start] Starting Docker Desktop and waiting for its engine, up to 3 minutes.
start "" "%DOCKER_DESKTOP%"
set /a DOCKER_WAIT=0
:ensure_docker_loop
"%SystemRoot%\System32\PING.EXE" -n 4 127.0.0.1 >nul
docker info >nul 2>&1
if not errorlevel 1 (
  echo [UX-start] Docker is running.
  exit /b 0
)
set /a DOCKER_WAIT+=3
if %DOCKER_WAIT% GEQ 180 (
  echo [UX-start] Docker did not start within 3 minutes. Open Docker Desktop and read its message.
  echo            For "Virtualization support not detected", see the Troubleshooting table in
  echo            skills\UX-Backend-start\SKILL.md.
  exit /b 1
)
goto :ensure_docker_loop

:wait_url
set /a URL_WAIT=0
:wait_url_loop
curl.exe -s -f -o nul --max-time 5 "%~1" >nul 2>&1
if not errorlevel 1 (
  echo [UX-start] %~2 is answering at %~1
  exit /b 0
)
set /a URL_WAIT+=1
if %URL_WAIT% GEQ 150 (
  echo [UX-start] %~2 did not answer at %~1 within 5 minutes.
  exit /b 1
)
"%SystemRoot%\System32\PING.EXE" -n 3 127.0.0.1 >nul
goto :wait_url_loop

:no_repo
echo [UX-start] Keep this file in the skills folder of the repository: docker-compose.yml was not found.
set "EXIT_CODE=1"
goto :end_no_popd

:fail
echo [UX-start] Stopped. See the Troubleshooting table in skills\UX-Backend-start\SKILL.md.
set "EXIT_CODE=1"

:end
popd

:end_no_popd
rem Keep the window open when the file was double-clicked, so the messages can be read.
echo %cmdcmdline% | "%SystemRoot%\System32\find.exe" /i "%SELF%" >nul && pause
endlocal & exit /b %EXIT_CODE%
