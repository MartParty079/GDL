#ifndef AppVersion
  #error AppVersion must be supplied from app/version.py
#endif
#ifndef PackageRoot
  #error PackageRoot must point to the verified PyInstaller directory
#endif
#ifndef OutputRoot
  #error OutputRoot must be supplied
#endif
[Setup]
AppId={{ACAC162E-8C9A-4F0B-998F-710038B7C32D}
AppName=GDL Research Hub
AppVersion={#AppVersion}
AppPublisher=GDL Research Team
AppPublisherURL=https://github.com/MartParty079/GDL
DefaultDirName={localappdata}\Programs\GDL Research Hub
DefaultGroupName=GDL Research Hub
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputRoot}
OutputBaseFilename=GDLResearchHub-Setup
SetupIconFile=..\assets\app_icon.ico
UninstallDisplayIcon={app}\FuelCellProjectHub.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
RestartApplications=no
WizardStyle=modern
VersionInfoVersion={#AppVersion}
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#PackageRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\GDL Research Hub"; Filename: "{app}\FuelCellProjectHub.exe"
Name: "{autodesktop}\GDL Research Hub"; Filename: "{app}\FuelCellProjectHub.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\FuelCellProjectHub.exe"; Description: "Open GDL Research Hub"; Flags: nowait postinstall skipifsilent
; LocalAppData/FuelCellProjectHub remains untouched on upgrade and uninstall.
