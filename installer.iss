; Inno Setup Script for "ស្ដេចកាត់វីដេអូ" (King Video Cutter)
; Generates a professional single Windows installer (.exe)

#define MyAppName "ស្ដេចកាត់វីដេអូ - King Video Cutter"
#define MyAppEnglishName "King Video Cutter"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "King Tools"
#define MyAppExeName "KingVideoCutter.exe"

[Setup]
AppId={{D41A28F4-8E82-4E28-BF98-10D189873E41}
AppName={#MyAppEnglishName}
AppVerName={#MyAppName} v{#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\King Video Cutter
DefaultGroupName={#MyAppEnglishName}
AllowNoIcons=yes
OutputDir=installer_output
OutputBaseFilename=KingVideoCutter_Setup_v1.0.0
SetupIconFile=assets\icons\app_icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
DisableProgramGroupPage=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\KingVideoCutter\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; NOTE: Don't use "Flags: ignoreversion" on any shared system files

[Icons]
Name: "{group}\{#MyAppEnglishName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\app_icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppEnglishName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppEnglishName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\assets\icons\app_icon.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
