[Setup]
AppName=BusyLightServer
AppVersion=1.0
DefaultDirName={userappdata}\BusyLightServer
OutputDir=dist
OutputBaseFilename=busylight_installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog

[Files]
; Copy compiled Nuitka app folder
Source: "build\busylight_server.dist\*"; DestDir: "{app}\busylight_server.dist"; Flags: recursesubdirs ignoreversion

; Kuando installer
Source: "extras\Kuando_HTTP_Service_Setup.msi"; DestDir: "{tmp}"; Flags: ignoreversion

; NSSM tool
Source: "extras\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\BusyLight Server"; Filename: "{app}\busylight_server.dist\busylight_server.exe"
Name: "{group}\Uninstall BusyLight Server"; Filename: "{uninstallexe}"

[Run]
; 1. Install Kuando MSI silently
Filename: "msiexec.exe"; Parameters: "/i ""{tmp}\Kuando_HTTP_Service_Setup.msi"" /quiet"; StatusMsg: "Installing Kuando HTTP Service..."; Flags: runhidden waituntilterminated

; 2. Register service with NSSM (use correct working dir and logs)
Filename: "{app}\nssm.exe"; Parameters: "install BusyLightServer ""{app}\busylight_server.dist\busylight_server.exe"" AppDirectory=""{app}\busylight_server.dist"" AppStdout=""{app}\busylight.log"" AppStderr=""{app}\busylight.err.log"" Start=SERVICE_AUTO_START"; StatusMsg: "Installing BusyLightServer as a service..."; Flags: runhidden waituntilterminated runascurrentuser

; 3. Start the service right after install
Filename: "{app}\nssm.exe"; Parameters: "start BusyLightServer"; StatusMsg: "Starting BusyLightServer..."; Flags: runhidden waituntilterminated runascurrentuser postinstall

[UninstallRun]
; 1. Stop the service
Filename: "{app}\nssm.exe"; Parameters: "stop BusyLightServer"; StatusMsg: "Stopping BusyLightServer service..."; Flags: runhidden waituntilterminated runascurrentuser

; 2. Remove service
Filename: "{app}\nssm.exe"; Parameters: "remove BusyLightServer confirm"; StatusMsg: "Removing BusyLightServer service..."; Flags: runhidden waituntilterminated runascurrentuser
