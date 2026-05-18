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
    & $makensis /DSOURCE_DIR="$sourceNsis" /DEXE_NAME="DLPulseNext.exe" $nsi
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
