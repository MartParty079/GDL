#ifndef Channel
  #error Channel must be beta or stable
#endif
#if Channel == "beta"
  #define AppName "GDL Research Hub Beta"
  #define InstallerId "{9DC7B6A1-418F-4CD4-BAB0-A7D96E5189B6}"
  #define ExeName "GDLResearchHubBeta"
  #define OtherExe "FuelCellProjectHub.exe"
  #define Protocol "gdlresearchhubbeta"
  #define OutputName "GDLResearchHubBeta-Setup"
  #define IconName "app_icon_beta.ico"
#else
  #define AppName "GDL Research Hub"
  #define InstallerId "{ACAC162E-8C9A-4F0B-998F-710038B7C32D}"
  #define ExeName "FuelCellProjectHub"
  #define OtherExe "GDLResearchHubBeta.exe"
  #define Protocol "gdlresearchhub"
  #define OutputName "GDLResearchHub-Setup"
  #define IconName "app_icon.ico"
#endif
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
AppId={{#InstallerId}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=GDL Research Team
AppPublisherURL=https://github.com/MartParty079/GDL
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputRoot}
OutputBaseFilename={#OutputName}
SetupIconFile=..\assets\{#IconName}
UninstallDisplayIcon={app}\{#ExeName}.exe
Compression=lzma2
SolidCompression=yes
CloseApplications=yes
CloseApplicationsFilter={#ExeName}.exe
RestartApplications=no
WizardStyle=modern
VersionInfoVersion={#NumericVersion}
[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked
[Files]
Source: "{#PackageRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#ExeName}.exe"; Tasks: desktopicon
[Registry]
Root: HKCU; Subkey: "Software\Classes\{#Protocol}"; ValueType: string; ValueName: ""; ValueData: "URL:{#AppName} Sign In"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\{#Protocol}"; ValueType: string; ValueName: "URL Protocol"; ValueData: ""
Root: HKCU; Subkey: "Software\Classes\{#Protocol}\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#ExeName}.exe,0"
Root: HKCU; Subkey: "Software\Classes\{#Protocol}\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#ExeName}.exe"" ""%1"""
[Run]
Filename: "{app}\{#ExeName}.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent
; LocalAppData/FuelCellProjectHub remains untouched on upgrade and uninstall.

[Code]
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExistingVersion: String;
begin
  Result := '';
  if FileExists(ExpandConstant('{app}\{#OtherExe}')) then
    Result := 'Choose a separate installation folder for this edition.'
  else if GetVersionNumbersString(ExpandConstant('{app}\{#ExeName}.exe'), ExistingVersion) then
  begin
    if ComparePackedVersion(StrToVersion(ExistingVersion), StrToVersion('{#NumericVersion}')) > 0 then
      Result := 'A newer build is already installed. This installer will not downgrade it.';
  end;
end;
