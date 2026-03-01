; ============================================================
;  Milhas UP Telegram Monitor — Instalador Windows
;  Requer: Inno Setup 6.x  https://jrsoftware.org/isinfo.php
;  Execute build\build.cmd ANTES de compilar este script.
; ============================================================

#define AppName      "Milhas UP Telegram Monitor"
#define AppVersion   "1.0.0"
#define AppPublisher "Milhas UP"
#define AppExeName   "MilhasUP.exe"
#define AppURL       "https://milhasup.com.br"

[Setup]
AppId={{F4A2C3E1-8B7D-4A9F-B2E6-1C3D5F7A9B0E}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir=..\dist\installer
OutputBaseFilename=MilhasUP_Setup_{#AppVersion}
SetupIconFile=..\assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName}
VersionInfoProductName={#AppName}

[Languages]
Name: "brazilianportuguese"; MessagesFile: "compiler:Languages\BrazilianPortuguese.isl"

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na área de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
Name: "startup";     Description: "Iniciar automaticamente com o Windows"; GroupDescription: "Inicialização:"; Flags: unchecked

[Files]
; Todos os arquivos da build (MilhasUP.exe + dependências + monitor_bg.exe)
Source: "..\dist\MilhasUP\MilhasUP\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Template de configuração (se o usuário ainda não tiver .env)
Source: "..\dist\MilhasUP\MilhasUP\.env.example"; DestDir: "{app}"; DestName: ".env.example"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}";            Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Desinstalar {#AppName}";Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}";      Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"; Tasks: desktopicon

[Registry]
; Inicialização automática com o Windows (opcional)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "MilhasUP"; \
    ValueData: """{app}\{#AppExeName}"""; \
    Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\{#AppExeName}"; \
    Description: "Iniciar {#AppName}"; \
    Flags: nowait postinstall skipifsilent

[UninstallRun]
; Para o monitor antes de desinstalar
Filename: "taskkill"; Parameters: "/F /IM MilhasUP.exe /IM monitor_bg.exe"; \
    Flags: runhidden; RunOnceId: "KillMonitor"

[Code]
// Verifica se o .env já existe; se não, cria uma cópia do exemplo
procedure CurStepChanged(CurStep: TSetupStep);
var
  EnvDest, ExampleSrc: string;
begin
  if CurStep = ssPostInstall then
  begin
    EnvDest    := ExpandConstant('{app}\.env');
    ExampleSrc := ExpandConstant('{app}\.env.example');
    if not FileExists(EnvDest) and FileExists(ExampleSrc) then
      FileCopy(ExampleSrc, EnvDest, False);
  end;
end;
