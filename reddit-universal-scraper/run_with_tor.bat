@echo off
echo ==================================================
echo 🤖 REDDIT UNIVERSAL SCRAPER (TOR MODE)
echo ==================================================

:: Check if Tor is already running
tasklist /FI "IMAGENAME eq tor.exe" 2>NUL | find /I /N "tor.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [OK] Tor is already running in the background.
) else (
    echo [INIT] Starting Tor Network...
    start /B "" "C:\Users\17spa\Downloads\tor-expert-bundle-windows-x86_64-15.0.19\tor\tor.exe" --ControlPort 9051 --CookieAuthentication 0
    :: Give Tor 3 seconds to bootstrap
    timeout /t 3 /nobreak > NUL
)

echo.
echo [INIT] Activating Python Virtual Environment...
call .\venv\Scripts\activate.bat

echo.
echo [RUN] Launching Scraper...
:: If the user didn't pass any arguments, run the default MachineLearning test
if "%~1"=="" (
    python main.py MachineLearning --mode tier3 --limit 5
) else (
    :: Otherwise, pass all arguments provided to the bat file into python
    python main.py %*
)

echo.
pause
