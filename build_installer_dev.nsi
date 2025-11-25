!define APPNAME "AnemoneDev"
!define VERSION "1.0"
!define COMPANY "HydrogeophysicsGroup"

OutFile "${APPNAME}Installer.exe"
InstallDir "$PROGRAMFILES\${APPNAME}"
RequestExecutionLevel admin

Page directory
Page instfiles
UninstPage uninstConfirm
UninstPage instfiles

Section "Install"
    SetOutPath "$INSTDIR"

    ; Copy Python embedded distribution
    DetailPrint "Copying Python files..."
    SetOutPath "$INSTDIR\python"
    File /r "python_dev\*.*"
    
    ; Copy application files
    DetailPrint "Copying application files..."
    SetOutPath "$INSTDIR\app"
    File /r "app\*.*"
    
    ; Copy root files
    DetailPrint "Copying configuration files..."
    SetOutPath "$INSTDIR"
    File "requirements.txt"
    File "setup.bat"
    File "run_app.bat"
    File "run_app_silent.vbs"
    File "run_app_console.bat"

    ; Run setup script
    DetailPrint "Installing Python dependencies (this may take a few minutes)..."
    ExecWait '"$INSTDIR\setup.bat"'

    ; Create shortcuts
    DetailPrint "Creating shortcuts..."
    CreateDirectory "$SMPROGRAMS\${APPNAME}"
    CreateShortCut "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk" "$INSTDIR\run_app_console.bat"
    CreateShortCut "$DESKTOP\${APPNAME}.lnk" "$INSTDIR\run_app_console.bat"

    ; Write uninstall entry
    WriteUninstaller "$INSTDIR\Uninstall.exe"
    
    DetailPrint "Installation complete!"
SectionEnd

Section "Uninstall"
    Delete "$SMPROGRAMS\${APPNAME}\${APPNAME}.lnk"
    RMDir "$SMPROGRAMS\${APPNAME}"
    Delete "$DESKTOP\${APPNAME}.lnk"
    RMDir /r "$INSTDIR"
SectionEnd