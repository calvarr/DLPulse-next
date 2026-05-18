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

Page directory
Page instfiles

UninstPage uninstConfirm
UninstPage instfiles

Section "DLPulse Next"
  SetOutPath "$INSTDIR"
  File /r "${SOURCE_DIR}\*.*"
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
  Delete "$DESKTOP\DLPulse Next.lnk"
  Delete "$SMPROGRAMS\DLPulse Next\DLPulse Next.lnk"
  RMDir "$SMPROGRAMS\DLPulse Next"
  RMDir /r "$INSTDIR"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
SectionEnd
