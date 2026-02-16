@echo off
setlocal enableextensions enabledelayedexpansion

rem === Usage ===
rem build_nuitka_sea_anemone.bat [AppName] [IconPath] [OutputDir] [BuildMode] [CleanFlag]
rem Example:
rem build_nuitka_sea_anemone.bat SeaAnemone "" dist standalone clean

set "APPNAME=%~1"
set "ICON=%~2"
set "DISTDIR=%~3"
set "BUILDMODE=%~4"
set "CLEANFLAG=%~5"

if "%APPNAME%"=="" set "APPNAME=SeaAnemone"
if "%DISTDIR%"=="" set "DISTDIR=dist"
if "%BUILDMODE%"=="" set "BUILDMODE=standalone"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "ENTRY=%ROOT%\app\app.py"
for %%I in ("%DISTDIR%") do set "DISTABS=%%~fI"

if not exist "%ENTRY%" (
  echo [ERROR] Entry file not found: %ENTRY%
  exit /b 1
)

if /I "%CLEANFLAG%"=="clean" (
  echo [INFO] Cleaning old build artifacts in %DISTABS% ...
  if not exist "%DISTABS%" mkdir "%DISTABS%"
  if exist "%DISTABS%\*.exe" del /q "%DISTABS%\*.exe"
  for /d %%D in ("%DISTABS%\*.build") do rd /s /q "%%~fD"
  for /d %%D in ("%DISTABS%\*.dist") do rd /s /q "%%~fD"
)

set "NUITKA_ARGS=--windows-console-mode=disable --output-dir=%DISTDIR% --assume-yes-for-downloads --enable-plugin=tk-inter --module-parameter=torch-disable-jit=yes --include-package=plotly.graph_objs --include-module=plotly.graph_objs._figure --include-package=_plotly_utils --include-package=narwhals --nofollow-import-to=plotly.matplotlylib.mplexporter.tests --nofollow-import-to=IPython --nofollow-import-to=pytest"

if /I "%BUILDMODE%"=="onefile" (
  set "NUITKA_ARGS=%NUITKA_ARGS% --onefile"
) else (
  set "NUITKA_ARGS=%NUITKA_ARGS% --standalone"
)

if not "%ICON%"=="" (
  if exist "%ICON%" (
    set "NUITKA_ARGS=%NUITKA_ARGS% --windows-icon-from-ico=%ICON%"
  ) else (
    echo [WARN] Icon file not found, skip icon: %ICON%
  )
)

if exist "%ROOT%\app\assets" set "NUITKA_ARGS=%NUITKA_ARGS% --include-data-dir=%ROOT%\app\assets=assets"
if exist "%ROOT%\app\recent_projects.txt" set "NUITKA_ARGS=%NUITKA_ARGS% --include-data-file=%ROOT%\app\recent_projects.txt=app/recent_projects.txt"
if exist "%ROOT%\docs\build\html" set "NUITKA_ARGS=%NUITKA_ARGS% --include-data-dir=%ROOT%\docs\build\html=docs/build/html"
if exist "%ROOT%\cache\dem" set "NUITKA_ARGS=%NUITKA_ARGS% --include-data-dir=%ROOT%\cache\dem=cache/dem"

set "NUITKA_ARGS=%NUITKA_ARGS% --output-filename=%APPNAME%.exe %ENTRY%"

echo.
echo [INFO] Build mode : %BUILDMODE%
echo [INFO] Output dir : %DISTDIR%
echo [INFO] Entry file : %ENTRY%
echo [INFO] Output abs : %DISTABS%
echo.
echo Running: python -m nuitka %NUITKA_ARGS%
echo.
python -m nuitka %NUITKA_ARGS%

if errorlevel 1 (
  echo.
  echo [ERROR] Nuitka build failed.
  exit /b 1
)

echo.
echo [OK] Nuitka build finished.

echo.
echo [INFO] Build artifacts:
if /I "%BUILDMODE%"=="onefile" (
  if exist "%DISTABS%\%APPNAME%.exe" (
    echo [OK] EXE: %DISTABS%\%APPNAME%.exe
  ) else (
    echo [WARN] Expected EXE not found. Searching under %DISTABS% ...
    dir /b /s "%DISTABS%\*.exe"
  )
) else (
  set "DISTFOLDER=%DISTABS%\app.dist"
  if exist "%DISTABS%\%APPNAME%.dist" set "DISTFOLDER=%DISTABS%\%APPNAME%.dist"
  echo [INFO] Dist folder: !DISTFOLDER!
  if exist "!DISTFOLDER!" (
    dir /b "!DISTFOLDER!\*.exe" 2>nul
    if errorlevel 1 echo [WARN] No EXE found yet in !DISTFOLDER!

    set "RUNNER=!DISTFOLDER!\run_!APPNAME!.bat"
    > "!RUNNER!" echo @echo off
    >>"!RUNNER!" echo setlocal
    >>"!RUNNER!" echo set "APPDIR=%%~dp0"
    >>"!RUNNER!" echo set "APP_EXE=!APPNAME!.exe"
    >>"!RUNNER!" echo set "URL=http://127.0.0.1:8050/"
    >>"!RUNNER!" echo for /f "tokens=5" %%%%p in ^('netstat -ano ^^^| findstr /R /C:":8050[ ]" ^^^| findstr "LISTENING"'^) do taskkill /F /PID %%%%p ^>nul 2^>nul
    >>"!RUNNER!" echo start "" "%%APPDIR%%%%APP_EXE%%"
    >>"!RUNNER!" echo powershell -NoProfile -ExecutionPolicy Bypass -Command "$u='http://127.0.0.1:8050/'; for($i=0;$i -lt 120;$i++){ try { $r=Invoke-WebRequest -Uri $u -UseBasicParsing -TimeoutSec 1; if($r.StatusCode -ge 200){ break } } catch {}; Start-Sleep -Milliseconds 500 }; Start-Process $u"
    >>"!RUNNER!" echo endlocal
    echo [OK] Launcher script created: !RUNNER!

    set "RUNNERVBS=!DISTFOLDER!\run_!APPNAME!.vbs"
    > "!RUNNERVBS!" echo Set fso = CreateObject("Scripting.FileSystemObject")
    >>"!RUNNERVBS!" echo Set sh = CreateObject("WScript.Shell")
    >>"!RUNNERVBS!" echo appDir = fso.GetParentFolderName(WScript.ScriptFullName)
    >>"!RUNNERVBS!" echo sh.Run """" ^& appDir ^& "\run_!APPNAME!.bat""", 0, False
    echo [OK] Hidden launcher script created: !RUNNERVBS!
  ) else (
    echo [WARN] Dist folder not found: !DISTFOLDER!
  )
)

endlocal
