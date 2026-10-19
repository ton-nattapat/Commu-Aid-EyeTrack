; Inno Setup script for the Windows installer. Run it through build_windows.ps1, not directly.
; Installs for the current user only (no administrator password), with Start menu and desktop
; shortcuts. Settings, calibration and app.log stay in %USERPROFILE%\.commu_aid, so uninstalling
; or updating keeps them.

#ifndef AppVersion
  #define AppVersion "0.1.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\..\dist\Communication Aid"
#endif
#ifndef OutputDir
  #define OutputDir "..\..\dist"
#endif

[Setup]
AppId={{6C9C3E52-6E1B-4C8E-9A57-2B1E4E0B7A11}
AppName=Communication Aid
AppVersion={#AppVersion}
AppPublisher=ton-nattapat
DefaultDirName={autopf}\Communication Aid
DefaultGroupName=Communication Aid
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=CommunicationAid-{#AppVersion}-Windows-Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Communication Aid.exe

[Tasks]
Name: "desktopicon"; Description: "Put a Communication Aid icon on the desktop"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Read Me First.txt"; DestDir: "{app}"; Flags: ignoreversion isreadme

[Icons]
Name: "{group}\Communication Aid"; Filename: "{app}\Communication Aid.exe"
Name: "{group}\Communication Aid (mouse, no eye tracker)"; Filename: "{app}\Communication Aid.exe"; Parameters: "--mouse"
Name: "{group}\Read Me First"; Filename: "{app}\Read Me First.txt"
Name: "{group}\Uninstall Communication Aid"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Communication Aid"; Filename: "{app}\Communication Aid.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Communication Aid.exe"; Description: "Start Communication Aid now"; Flags: nowait postinstall skipifsilent
