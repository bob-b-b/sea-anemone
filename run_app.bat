@echo on
setlocal enabledelayedexpansion

rem Set the path to the embedded Python interpreter
set PYTHON_PATH=python\pythonw.exe

rem Launch the Dash application in the background using the PID wrapper
start "" "%PYTHON_PATH%" app\app.py

rem Wait for the server to start and PID file to be created
@echo off
:loop
timeout 1
netstat -na | findstr "8050" | findstr "127.0.0.1" | findstr "LISTENING" || goto :loop
echo Server is ready!


rem Get default browser and launch in app mode
set URL=http://127.0.0.1:8050/

rem Try to detect default browser
for /f "tokens=2*" %%a in ('reg query "HKEY_CURRENT_USER\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice" /v ProgId 2^>nul') do set BROWSER=%%b

rem Launch with appropriate flags based on browser
if "!BROWSER!"=="MSEdgeHTM" (
    start msedge --app=%URL%
) else if "!BROWSER!"=="ChromeHTML" (
    start chrome --app=%URL%
) else if "!BROWSER!"=="BraveHTML" (
    start brave --app=%URL%
) else (
    rem Fallback to default browser without app mode
    start "" "%URL%"
)

endlocal