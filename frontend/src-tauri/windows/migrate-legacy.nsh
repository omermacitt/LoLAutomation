; The published 0.0.2 Inno package owns this exact HKCU identity. Never recursively
; delete an installation folder: its own uninstaller removes only recorded files.
!define LEGACY_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\{9C9C7A35-6D5F-4A23-9A0A-7F3B78A9A5D1}_is1"
Var LegacyPath
Var LegacyCommand
Var LegacyAttempts
Var NativePath
Var NativeCommand
Var NativeAttempts

!macro NSIS_HOOK_PREINSTALL
  SetRegView 32
  ReadRegStr $LegacyPath HKCU "${LEGACY_KEY}" "InstallLocation"
  ${If} $LegacyPath == ""
    ReadRegStr $LegacyPath HKCU "${LEGACY_KEY}" "Inno Setup: App Path"
  ${EndIf}
  ${If} $LegacyPath == ""
    SetRegView 64
    ReadRegStr $LegacyPath HKCU "${LEGACY_KEY}" "InstallLocation"
    ${If} $LegacyPath == ""
      ReadRegStr $LegacyPath HKCU "${LEGACY_KEY}" "Inno Setup: App Path"
    ${EndIf}
  ${EndIf}
  ${If} $LegacyPath != ""
    ReadRegStr $LegacyCommand HKCU "${LEGACY_KEY}" "UninstallString"
    ; Inno's InstallLocation can have a trailing separator; use App Path, which
    ; is the canonical directory recorded by this specific installer.
    ReadRegStr $LegacyPath HKCU "${LEGACY_KEY}" "Inno Setup: App Path"
    ${If} $LegacyPath == ""
      MessageBox MB_OK|MB_ICONSTOP "Eski RunePilot kurulum yolu okunamadı. Windows Ayarları'ndan eski sürümü kaldırıp tekrar dene." /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
    ${If} $LegacyCommand != '$\"$LegacyPath\unins000.exe$\"'
      MessageBox MB_OK|MB_ICONSTOP "Eski RunePilot kaldırıcı kaydı doğrulanamadı. Eski sürümü Windows Ayarları'ndan kaldırıp tekrar dene." /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
    IfFileExists "$LegacyPath\RunePilot.exe" 0 legacy_invalid
    IfFileExists "$LegacyPath\unins000.exe" 0 legacy_invalid
    ; The old update button launches Setup and then quits. Wait for its exact
    ; executable to unlock; never kill a process or lose a pending editor save.
    StrCpy $LegacyAttempts 0
    legacy_wait:
    System::Call 'kernel32::CreateFileW(w "$LegacyPath\RunePilot.exe", i 0xC0000000, i 0, p 0, i 3, i 0, p 0) p .r0'
    ${If} $0 == -1
      IntOp $LegacyAttempts $LegacyAttempts + 1
      ${If} $LegacyAttempts >= 20
        MessageBox MB_OK|MB_ICONSTOP "Eski RunePilot hâlâ açık. Otomasyonu durdurup uygulamayı kapat; ardından güncellemeyi tekrar aç." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
      Sleep 1000
      Goto legacy_wait
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
    ExecWait '$LegacyCommand /VERYSILENT /SUPPRESSMSGBOXES /NORESTART /NOCLOSEAPPLICATIONS' $0
    ${If} $0 != 0
      MessageBox MB_OK|MB_ICONSTOP "Eski RunePilot kaldırılamadı. Uygulamayı kapatıp kurulumu tekrar dene. Ayarların korunur." /SD IDOK
      SetErrorLevel 1
      Abort
    ${EndIf}
    IfFileExists "$LegacyPath\RunePilot.exe" legacy_invalid
    Goto legacy_done
    legacy_invalid:
      MessageBox MB_OK|MB_ICONSTOP "Eski RunePilot dosyaları doğrulanamadı. Eski sürümü Windows Ayarları'ndan kaldırıp tekrar dene." /SD IDOK
      SetErrorLevel 1
      Abort
  ${EndIf}
  legacy_done:
  SetRegView 64
  ; Tauri's /UPDATE default overwrites files without running the old uninstaller.
  ; Use its recorded file list first so retired binaries/resources are removed.
  ReadRegStr $NativeCommand HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RunePilot" "UninstallString"
  ${If} $NativeCommand != ""
    ReadRegStr $NativePath HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RunePilot" "InstallLocation"
    StrCpy $0 $NativePath 1
    ${If} $0 == '$\"'
      StrCpy $NativePath $NativePath -1 1
    ${EndIf}
    ${If} $NativePath == ""
      Goto native_invalid
    ${EndIf}
    ${If} $NativeCommand != '$\"$NativePath\uninstall.exe$\"'
      Goto native_invalid
    ${EndIf}
    ReadRegStr $0 HKCU "Software\Microsoft\Windows\CurrentVersion\Uninstall\RunePilot" "MainBinaryName"
    ${If} $0 != "runepilot-desktop.exe"
      Goto native_invalid
    ${EndIf}
    IfFileExists "$NativePath\uninstall.exe" 0 native_invalid
    IfFileExists "$NativePath\runepilot-desktop.exe" 0 native_uninstall
    StrCpy $NativeAttempts 0
    native_wait:
    System::Call 'kernel32::CreateFileW(w "$NativePath\runepilot-desktop.exe", i 0xC0000000, i 0, p 0, i 3, i 0, p 0) p .r0'
    ${If} $0 == -1
      IntOp $NativeAttempts $NativeAttempts + 1
      ${If} $NativeAttempts >= 20
        MessageBox MB_OK|MB_ICONSTOP "RunePilot hâlâ açık. Uygulamayı normal biçimde kapatıp güncellemeyi tekrar aç." /SD IDOK
        SetErrorLevel 1
        Abort
      ${EndIf}
      Sleep 1000
      Goto native_wait
    ${EndIf}
    System::Call 'kernel32::CloseHandle(p r0)'
    native_uninstall:
    ClearErrors
    ExecWait '$NativeCommand /S /UPDATE _?=$NativePath' $0
    ${If} ${Errors}
    ${OrIf} $0 != 0
      Goto native_invalid
    ${EndIf}
    IfFileExists "$NativePath\runepilot-desktop.exe" native_invalid
    IfFileExists "$NativePath\runepilot-backend.exe" native_invalid
    ; _?= runs in place and cannot remove the uninstaller itself.
    Delete "$NativePath\uninstall.exe"
    Goto native_done
    native_invalid:
      MessageBox MB_OK|MB_ICONSTOP "Önceki RunePilot kurulumu güvenli biçimde kaldırılamadı. Uygulamayı kapatıp tekrar dene; oyun ayarların korunur." /SD IDOK
      SetErrorLevel 1
      Abort
  ${EndIf}
  native_done:
!macroend
