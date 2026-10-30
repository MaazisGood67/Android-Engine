#define AppName "MaazXdroid"
#define AppVersion "0.2.1"

[Setup]
AppId={{A86B0B78-9D50-4BE4-93E6-7F5E9B7CF002}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=MaazXdroid
DefaultDirName={localappdata}\Programs\MaazXdroid
DefaultGroupName=MaazXdroid
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64
OutputDir=..\dist\installer
OutputBaseFilename=MaazXdroidSetup
SetupIconFile=..\assets\maazxdroid.ico
UninstallDisplayIcon={app}\MaazXdroid.exe
WizardStyle=modern
Compression=lzma2
SolidCompression=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "..\dist\MaazXdroid.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\MaazXdroid"; Filename: "{app}\MaazXdroid.exe"
Name: "{autodesktop}\MaazXdroid"; Filename: "{app}\MaazXdroid.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\MaazXdroid.exe"; Description: "Launch MaazXdroid"; Flags: postinstall nowait skipifsilent