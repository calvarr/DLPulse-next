; NSIS installer for DLPulse Next (PyInstaller onedir).
; makensis /DSOURCE_DIR=C:/path/to/DLPulseNext /DEXE_NAME=DLPulseNext.exe DLPulseNext.nsi

Unicode true

!ifndef SOURCE_DIR
  !error "Pass /DSOURCE_DIR=... (PyInstaller dist/DLPulseNext folder)"
!endif
!ifndef EXE_NAME
  !define EXE_NAME "DLPulseNext.exe"
!endif

!define PRODUCT_NAME "DLPulse Next"

Name "${PRODUCT_NAME}"
OutFile "..\..\build\DLPulseNext-Setup.exe"
InstallDir "$PROGRAMFILES64\DLPulse Next"
RequestExecutionLevel admin
; Allow overwrite when the exe is not locked (installer kills running app first).
SetOverwrite on

!include "LogicLib.nsh"

; Stop a running DLPulse Next (browser-fallback mode keeps the process alive).
!macro KillRunningApp
  DetailPrint "Closing any running ${PRODUCT_NAME}..."
  ExecWait '$\"$SYSDIR\taskkill.exe$\" /F /IM ${EXE_NAME} /T' $0
  ExecWait '$\"$SYSDIR\taskkill.exe$\" /F /IM ffmpeg.exe /T' $0
  Sleep 800
!macroend

Function .onInit
  !insertmacro KillRunningApp
FunctionEnd

Function un.onInit
  !insertmacro KillRunningApp
FunctionEnd

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "DLPulse Next"
  !insertmacro KillRunningApp

!ifdef REDIST_DIR
  IfFileExists "${REDIST_DIR}\dotnet\host\fxr\*.*" 0 +4
    DetailPrint "Bundled .NET Desktop Runtime 8 (x64)..."
    SetOutPath "$INSTDIR\dotnet"
    File /r "${REDIST_DIR}\dotnet\*.*"
  IfFileExists "${REDIST_DIR}\WebView2Runtime\*.*" 0 +4
    DetailPrint "Bundled Microsoft Edge WebView2 Runtime..."
    SetOutPath "$INSTDIR\WebView2Runtime"
    File /r "${REDIST_DIR}\WebView2Runtime\*.*"
!endif

; WEBVIEW2_BOOTSTRAPPER is set at compile time only when stage_runtimes downloaded the bootstrapper
; (CI hosts with preinstalled WebView2 get a portable copy instead — no bootstrapper file).
!ifdef WEBVIEW2_BOOTSTRAPPER
  DetailPrint "Installing Microsoft Edge WebView2 Runtime..."
  SetOutPath "$INSTDIR\_installers"
  File "${WEBVIEW2_BOOTSTRAPPER}"
  ExecWait '"$INSTDIR\_installers\MicrosoftEdgeWebview2Setup.exe" /silent /install' $0
!endif

  SetOutPath "$INSTDIR"
  ; Retry locked files once after another kill (common when upgrading over a running build).
  ClearErrors
  File /r "${SOURCE_DIR}\*.*"
  ${If} ${Errors}
    !insertmacro KillRunningApp
    Sleep 1000
    ClearErrors
    File /r "${SOURCE_DIR}\*.*"
  ${EndIf}
  CreateDirectory "$SMPROGRAMS\DLPulse Next"
  CreateShortCut "$SMPROGRAMS\DLPulse Next\DLPulse Next.lnk" "$INSTDIR\${EXE_NAME}" "" "" 0
  CreateShortCut "$DESKTOP\DLPulse Next.lnk" "$INSTDIR\${EXE_NAME}" "" "" 0
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "DisplayIcon" "$INSTDIR\${EXE_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "UninstallString" '"$INSTDIR\uninstall.exe"'
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoModify" 1
  WriteRegDWORD HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}" "NoRepair" 1
  WriteUninstaller "$INSTDIR\uninstall.exe"
SectionEnd

Section Uninstall
  !insertmacro KillRunningApp
  Delete "$DESKTOP\DLPulse Next.lnk"
  Delete "$SMPROGRAMS\DLPulse Next\DLPulse Next.lnk"
  RMDir "$SMPROGRAMS\DLPulse Next"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
