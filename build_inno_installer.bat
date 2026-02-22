@echo off
setlocal enableextensions

set "SCRIPT=%~dp0build_installer_inno.iss"
set "APPVERSION=%~1"
set "MODE=%~2"

if /I "%~1"=="fast" (
  set "APPVERSION="
  set "MODE=fast"
) else if /I "%~1"=="release" (
  set "APPVERSION="
  set "MODE=release"
)

if "%MODE%"=="" set "MODE=fast"

if /I "%MODE%"=="release" (
  set "INNO_COMPRESSION=lzma2/ultra64"
  set "INNO_SOLID=yes"
) else (
  set "INNO_COMPRESSION=lzma2/fast"
  set "INNO_SOLID=no"
)

if not exist "%SCRIPT%" (
  echo [ERROR] Inno script not found: %SCRIPT%
  exit /b 1
)

set "ISCC=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist "%ISCC%" set "ISCC=%ProgramFiles%\Inno Setup 6\ISCC.exe"

if not exist "%ISCC%" (
  echo [ERROR] ISCC.exe not found. Please install Inno Setup 6 first.
  echo Download: https://jrsoftware.org/isdl.php
  exit /b 1
)

if "%APPVERSION%"=="" (
  echo [INFO] Building installer with default AppVersion from .iss
  echo [INFO] Build mode: %MODE%  ^(Compression=%INNO_COMPRESSION%, Solid=%INNO_SOLID%^)
  "%ISCC%" /DInnoCompression=%INNO_COMPRESSION% /DInnoSolid=%INNO_SOLID% "%SCRIPT%"
) else (
  echo [INFO] Building installer with AppVersion=%APPVERSION%
  echo [INFO] Build mode: %MODE%  ^(Compression=%INNO_COMPRESSION%, Solid=%INNO_SOLID%^)
  "%ISCC%" /DAppVersion=%APPVERSION% /DInnoCompression=%INNO_COMPRESSION% /DInnoSolid=%INNO_SOLID% "%SCRIPT%"
)

if errorlevel 1 (
  echo [ERROR] Inno Setup build failed.
  exit /b 1
)

echo [OK] Installer build finished. Check: dist\installer
endlocal
