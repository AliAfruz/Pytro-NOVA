; Per-user Windows 64-bit installer for the portable Pytro-NOVA distribution.
#define AppVersion "3.9.4"
#define PortableDir "..\..\dist\Pytro-NOVA-v" + AppVersion + "-Windows-x64"

[Setup]
AppId={{F492E3DF-71C1-4C5B-B9ED-9C720E833E7E}
AppName=Pytro-NOVA
AppVersion={#AppVersion}
AppPublisher=Pytro-NOVA contributors
DefaultDirName={localappdata}\Programs\Pytro-NOVA
DefaultGroupName=Pytro-NOVA
OutputDir=..\..\dist
OutputBaseFilename=Pytro-NOVA-Setup-v{#AppVersion}-Windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\PytroNOVA.exe

[Files]
Source: "{#PortableDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Pytro-NOVA"; Filename: "{app}\PytroNOVA.exe"

[Run]
Filename: "{app}\PytroNOVA.exe"; Description: "Launch Pytro-NOVA"; Flags: nowait postinstall skipifsilent
