[Setup]
AppName=BusyLight Server Admin
AppVersion=1.0
DefaultDirName={userappdata}\BusyLightServerAdmin
OutputDir=dist
OutputBaseFilename=busylight_admin_installer
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
SetupIconFile=icon.ico

[Files]
; Copy compiled Nuitka app folder, including templates and dependencies
Source: "build\busylight_admin.dist\*"; DestDir: "{app}\busylight_admin.dist"; Flags: recursesubdirs createallsubdirs ignoreversion

; NSSM tool
Source: "extras\nssm.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\BusyLight Server Admin"; Filename: "{app}\busylight_admin.dist\busylight_admin.exe"
Name: "{group}\Uninstall BusyLight Server Admin"; Filename: "{uninstallexe}"

[Run]
; Register service with NSSM (Admin)
Filename: "{app}\nssm.exe"; Parameters: "install BusyLightServerAdmin ""{app}\busylight_admin.dist\busylight_admin.exe"" AppDirectory=""{app}\busylight_admin.dist"" AppStdout=""{app}\busylight.log"" AppStderr=""{app}\busylight.err.log"" Start=SERVICE_AUTO_START"; StatusMsg: "Installing BusyLight Server Admin as a service..."; Flags: runhidden waituntilterminated runascurrentuser

; Start the service after install
Filename: "{app}\nssm.exe"; Parameters: "start BusyLightServerAdmin"; StatusMsg: "Starting BusyLight Server Admin..."; Flags: runhidden waituntilterminated runascurrentuser postinstall

[UninstallRun]
; Stop the service
Filename: "{app}\nssm.exe"; Parameters: "stop BusyLightServerAdmin"; StatusMsg: "Stopping BusyLight Server Admin service..."; Flags: runhidden waituntilterminated runascurrentuser

; Remove the service
Filename: "{app}\nssm.exe"; Parameters: "remove BusyLightServerAdmin confirm"; StatusMsg: "Removing BusyLight Server Admin service..."; Flags: runhidden waituntilterminated runascurrentuser
