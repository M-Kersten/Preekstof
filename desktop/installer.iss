; Inno Setup script for the Windows installer: Preekstof-Setup.exe.
; Built by desktop/build.py with ISCC /DVersion=... /DDist=...\Preekstof /DOut=...
;
; Installs for this user only, in %LOCALAPPDATA%\Programs\Preekstof: no administrator
; password, which a church laptop's volunteer often does not have. Uninstalling removes the
; app and leaves the church's own work in %USERPROFILE%\Preekstof alone.

#ifndef Version
  #define Version "0.0.0"
#endif

[Setup]
AppId={{8C1F7E2A-5B3D-4E6F-9A1B-2C3D4E5F6A7B}
AppName=Preekstof
AppVersion={#Version}
AppVerName=Preekstof {#Version}
AppPublisher=Merijn Kersten
AppPublisherURL=https://m-kersten.github.io/Preekstof/
DefaultDirName={localappdata}\Programs\Preekstof
DefaultGroupName=Preekstof
DisableProgramGroupPage=yes
DisableDirPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#Out}
OutputBaseFilename=Preekstof-Setup
SetupIconFile=icons\preekstof.ico
UninstallDisplayIcon={app}\Preekstof.exe
UninstallDisplayName=Preekstof
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Languages]
Name: "dutch"; MessagesFile: "compiler:Languages\Dutch.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"

[InstallDelete]
; A new version replaces the old one whole: two versions' libraries side by side in one
; folder is an app nobody can predict.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "{#Dist}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Preekstof"; Filename: "{app}\Preekstof.exe"
Name: "{autodesktop}\Preekstof"; Filename: "{app}\Preekstof.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Preekstof.exe"; Description: "{cm:LaunchProgram,Preekstof}"; Flags: nowait postinstall skipifsilent
