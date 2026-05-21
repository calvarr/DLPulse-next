# Build NSIS installer from PyInstaller dist/DLPulseNext/
$ErrorActionPreference = "Stop"

$Root = if ($args[0]) { $args[0] } else { Get-Location }
Push-Location $Root
try {
    $source = Join-Path $Root "dist\DLPulseNext"
    if (-not (Test-Path (Join-Path $source "DLPulseNext.exe"))) {
        throw "Missing dist\DLPulseNext\DLPulseNext.exe — run PyInstaller first."
    }
    $source = (Resolve-Path -LiteralPath $source).Path

    $candidates = @(
        "${env:ProgramFiles(x86)}\NSIS\makensis.exe",
        "$env:ProgramFiles\NSIS\makensis.exe",
        "C:\Program Files (x86)\NSIS\makensis.exe"
    )
    $makensis = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if (-not $makensis) {
        throw "makensis.exe not found. Install NSIS (e.g. choco install nsis -y)."
    }

    $nsi = Join-Path $Root "packaging\windows\DLPulseNext.nsi"
    if (-not (Test-Path $nsi)) {
        throw "Missing $nsi"
    }

    $sourceNsis = $source -replace "\\", "/"
    $nsisArgs = @(
        "/DSOURCE_DIR=$sourceNsis",
        "/DEXE_NAME=DLPulseNext.exe"
    )
    $redist = Join-Path $Root "packaging\windows\redist"
    if (Test-Path (Join-Path $redist "dotnet")) {
        $redistNsis = (Resolve-Path -LiteralPath $redist).Path -replace "\\", "/"
        $nsisArgs += "/DREDIST_DIR=$redistNsis"
        Write-Host "NSIS REDIST_DIR=$redistNsis"
    } else {
        Write-Warning "packaging/windows/redist missing — run stage_runtimes.ps1 on Windows first"
    }
    $installers = Join-Path $redist "installers"
    if (Test-Path $installers) {
        $instNsis = (Resolve-Path -LiteralPath $installers).Path -replace "\\", "/"
        $nsisArgs += "/DINSTALLERS_DIR=$instNsis"
    }
    & $makensis @nsisArgs $nsi
    if ($LASTEXITCODE -ne 0) {
        throw "makensis exited with $LASTEXITCODE"
    }

    $out = Join-Path $Root "build\DLPulseNext-Setup.exe"
    if (-not (Test-Path $out)) {
        throw "Missing output: $out"
    }
    Write-Host "Installer: $out"
}
finally {
    Pop-Location
}
