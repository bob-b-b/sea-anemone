#ifndef AppName
  #define AppName "SeaAnemone"
#endif

#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

#ifndef AppPublisher
  #define AppPublisher "HydrogeophysicsGroup"
#endif

#ifndef ExeName
  #define ExeName "SeaAnemone.exe"
#endif

#ifndef RunBatName
  #define RunBatName "run_SeaAnemone.bat"
#endif

#ifndef RunLauncherName
  #define RunLauncherName "run_SeaAnemone.vbs"
#endif

#ifndef InnoCompression
  #define InnoCompression "lzma2/fast"
#endif

#ifndef InnoSolid
  #define InnoSolid "no"
#endif

#ifndef DistDir
  #ifexist "dist\SeaAnemone\{#ExeName}"
    #define DistDir "dist\SeaAnemone"
  #elifexist "dist\SeaAnemone.dist\{#ExeName}"
    #define DistDir "dist\SeaAnemone.dist"
  #else
    #define DistDir "dist\app.dist"
  #endif
#endif

[Setup]
AppId=HydrogeophysicsGroup.SeaAnemone
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
OutputDir=dist\installer
OutputBaseFilename={#AppName}Installer
Compression={#InnoCompression}
SolidCompression={#InnoSolid}
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayIcon={app}\{#ExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Files]
Source: "{#DistDir}\\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs; Excludes: "torch\\include\\*,$RECYCLE.BIN\\*,*.pdb,*.lib,*.exp"

[Icons]
Name: "{group}\\{#AppName}"; Filename: "{app}\\{#RunBatName}"; WorkingDir: "{app}"; IconFilename: "{app}\\{#ExeName}"
Name: "{autodesktop}\\{#AppName}"; Filename: "{app}\\{#RunBatName}"; WorkingDir: "{app}"; IconFilename: "{app}\\{#ExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional icons:"; Flags: unchecked

[Run]
Filename: "{app}\\{#RunBatName}"; Description: "Launch {#AppName}"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
