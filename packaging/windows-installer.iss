#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif
#ifndef AppName
  #define AppName "cutrix"
#endif
#ifndef AppPublisher
  #define AppPublisher "cutrix contributors"
#endif
#ifndef AppExeName
  #define AppExeName "cutrix"
#endif
#ifndef ProjectRoot
  #define ProjectRoot ".."
#endif

[Setup]
AppId={{0AEACB8E-A940-43FC-9B68-4174254C0D1B}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={localappdata}\Programs\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#ProjectRoot}\release
OutputBaseFilename={#AppExeName}-{#AppVersion}-windows-x64-setup
SetupIconFile={#ProjectRoot}\packaging\assets\app.ico
UninstallDisplayIcon={app}\{#AppExeName}.exe
LicenseFile={#ProjectRoot}\LICENSE
Compression=lzma2/normal
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
UninstallDisplayName={#AppName}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoCopyright=Copyright (c) 2026 {#AppPublisher}

[Tasks]
Name: "models"; Description: "Download AI models now (about 1.2 GB; internet required)"; Flags: checkedonce
Name: "desktopicon"; Description: "Create a desktop shortcut"; Flags: unchecked

[Files]
Source: "{#ProjectRoot}\dist\{#AppExeName}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "{#ProjectRoot}\packaging\verify-webview.ps1"; Flags: dontcopy

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExeName}.exe"; Description: "Open {#AppName}"; Flags: nowait postinstall skipifsilent; Check: CanLaunchApp

[Code]
var
  ModelSetupReady: Boolean;
  RuntimeDownloadPage: TDownloadWizardPage;

procedure InitializeWizard;
begin
  RuntimeDownloadPage := CreateDownloadPage('Desktop runtime',
    'Downloading the Microsoft WebView2 prerequisite from Microsoft.', nil);
  RuntimeDownloadPage.ShowBaseNameInsteadOfUrl := True;
end;

function WebViewInstalled: Boolean;
var
  Version: String;
  RuntimeKey: String;
begin
  RuntimeKey := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKCU, RuntimeKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0')) or
    (RegQueryStringValue(HKLM32, RuntimeKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  Bootstrapper: String;
begin
  Result := '';
  if WebViewInstalled then
    Exit;
  RuntimeDownloadPage.Clear;
  RuntimeDownloadPage.Add('https://go.microsoft.com/fwlink/p/?LinkId=2124703', 'MicrosoftEdgeWebview2Setup.exe', '');
  RuntimeDownloadPage.Show;
  try
    try
      RuntimeDownloadPage.Download;
    except
      Result := 'Microsoft WebView2 could not be downloaded. Check your connection and retry setup.';
      Exit;
    end;
  finally
    RuntimeDownloadPage.Hide;
  end;
  ExtractTemporaryFile('verify-webview.ps1');
  Bootstrapper := ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
      '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + ExpandConstant('{tmp}\verify-webview.ps1') +
      '" -InstallerPath "' + Bootstrapper + '"', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := 'Microsoft WebView2 installer verification could not run. Setup has stopped.';
    Exit;
  end;
  if ResultCode <> 0 then
  begin
    Result := 'Microsoft WebView2 installer signature verification failed. Setup has stopped.';
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installing the Microsoft WebView2 desktop runtime...';
  if not Exec(Bootstrapper, '/silent /install', '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    Result := 'The Microsoft WebView2 desktop runtime could not be installed. Retry setup.';
    Exit;
  end;
  if not WebViewInstalled then
    Result := 'Microsoft WebView2 installation did not complete. Restart Windows and retry setup.';
end;

function CanLaunchApp: Boolean;
begin
  Result := ModelSetupReady or not WizardIsTaskSelected('models');
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
begin
  if (CurStep = ssPostInstall) and WizardIsTaskSelected('models') then
  begin
    WizardForm.StatusLabel.Caption := 'Setting up AI models. Follow the download window to continue.';
    ModelSetupReady := Exec(ExpandConstant('{app}\{#AppExeName}.exe'), '--setup-models',
      ExpandConstant('{app}'), SW_SHOWNORMAL, ewWaitUntilTerminated, ResultCode);
    ModelSetupReady := ModelSetupReady and (ResultCode = 0);
    if not ModelSetupReady then
      MsgBox('The app is installed. Model setup was cancelled or did not finish.' + #13#10 +
        'Open the app when you are ready to retry. No incomplete model will be used.', mbInformation, MB_OK);
  end;
end;
