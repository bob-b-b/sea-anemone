@echo off
setlocal enableextensions

rem Fast packaging path (AV-friendly variant)
rem Usage: build_pyinstaller_fast.bat [AppName] [DistDir] [CleanFlag]
rem Example: build_pyinstaller_fast.bat SeaAnemone dist clean

set "APPNAME=%~1"
set "DISTDIR=%~2"
set "CLEANFLAG=%~3"

if "%APPNAME%"=="" set "APPNAME=SeaAnemone"
if "%DISTDIR%"=="" set "DISTDIR=dist"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"
set "ENTRY=%ROOT%\app\app.py"
set "PYI_BUILD=%ROOT%\build\pyi"
set "PYI_SPEC=%ROOT%\build\%APPNAME%.spec"

if not exist "%ENTRY%" (
	echo [ERROR] Entry file not found: %ENTRY%
	exit /b 1
)

if /I "%CLEANFLAG%"=="clean" (
	echo [INFO] Cleaning previous PyInstaller artifacts...
	if exist "%PYI_BUILD%" rd /s /q "%PYI_BUILD%"
	if exist "%PYI_SPEC%" del /q "%PYI_SPEC%"
	if exist "%ROOT%\%DISTDIR%\%APPNAME%" rd /s /q "%ROOT%\%DISTDIR%\%APPNAME%"
)

echo.
echo [INFO] Building fast onedir package with PyInstaller...
echo.

python -m PyInstaller ^
	--noconfirm ^
	--onedir ^
	--noconsole ^
	--name "%APPNAME%" ^
	--distpath "%ROOT%\%DISTDIR%" ^
	--workpath "%PYI_BUILD%" ^
	--specpath "%ROOT%\build" ^
	--hidden-import plotly.graph_objs._figure ^
	--hidden-import _plotly_utils.importers ^
	--collect-all plotly ^
	--collect-all dash ^
	--collect-all dash_bootstrap_components ^
	--add-data "%ROOT%\app\assets;assets" ^
	--add-data "%ROOT%\app\recent_projects.txt;app" ^
	--add-data "%ROOT%\docs\build\html;docs/build/html" ^
	"%ENTRY%"

if errorlevel 1 (
	echo.
	echo [ERROR] PyInstaller build failed.
	exit /b 1
)

set "OUTDIR=%ROOT%\%DISTDIR%\%APPNAME%"
echo.
echo [OK] Build finished: %OUTDIR%

if exist "%OUTDIR%\%APPNAME%.exe" (
	echo [OK] EXE: %OUTDIR%\%APPNAME%.exe
) else (
	echo [WARN] EXE not found in expected path.
)

set "RUNNER=%OUTDIR%\run_%APPNAME%.bat"
> "%RUNNER%" echo @echo off
>>"%RUNNER%" echo set "APPDIR=%%~dp0"
>>"%RUNNER%" echo start "" "%%APPDIR%%\%APPNAME%.exe"
>>"%RUNNER%" echo timeout /t 4 /nobreak ^>nul
>>"%RUNNER%" echo start "" "http://127.0.0.1:8050/"
echo [OK] Launcher: %RUNNER%

endlocal
