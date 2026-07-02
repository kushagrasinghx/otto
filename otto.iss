; Inno Setup script for Otto -> builds a friendly Setup.exe installer.
;
; Prerequisites:
;   1. Build the app first:   pyinstaller otto.spec --noconfirm --clean
;      (produces dist\Otto.exe, which this script packages)
;   2. Install Inno Setup 6:  https://jrsoftware.org/isdl.php
;
; Compile:
;   - Open otto.iss in the Inno Setup Compiler and click Build, or
;   - Command line:  "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" otto.iss
;
; Output:  Output\Otto-Setup-1.0.exe

#define MyAppName "Otto"
#define MyAppVersion "1.1"
#define MyAppPublisher "Kushagra Singh"
#define MyAppURL "https://github.com/kushagrasinghx/otto"
#define MyAppExeName "Otto.exe"
#define MyAppId "{{8F3A2C1E-4B5D-4E6F-9A7B-1C2D3E4F5A6B}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}/releases
; Per-user install so no administrator prompt is needed.
PrivilegesRequired=lowest
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
DisableDirPage=auto
OutputDir=Output
OutputBaseFilename=Otto-Setup-{#MyAppVersion}
SetupIconFile=assets\icon.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
UninstallDisplayName={#MyAppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}.0
VersionInfoProductName={#MyAppName}
VersionInfoCompany={#MyAppPublisher}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; \
    GroupDescription: "Additional shortcuts:"
Name: "startupicon"; Description: "Start Otto automatically when I sign in"; \
    GroupDescription: "Startup:"

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; AppUserModelID matches what the app sets at runtime, so toast notifications
; show the Otto name + icon and the taskbar groups correctly.
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    AppUserModelID: "Otto"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: desktopicon; AppUserModelID: "Otto"
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; \
    Tasks: startupicon; AppUserModelID: "Otto"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; \
    Flags: nowait postinstall skipifsilent
