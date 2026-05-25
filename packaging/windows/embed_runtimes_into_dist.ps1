# Copy staged .NET + WebView2 into PyInstaller dist so they ship inside SOURCE_DIR (NSIS File /r).
param([string]$Root = ".")

$ErrorActionPreference = "Stop"
$dist = Join-Path $Root "dist\DLPulseNext"
$redist = Join-Path $Root "packaging\windows\redist"

if (-not (Test-Path (Join-Path $dist "DLPulseNext.exe"))) {
    throw "Missing dist\DLPulseNext\DLPulseNext.exe"
}

$dotnetSrc = Join-Path $redist "dotnet"
if (Test-Path (Join-Path $dotnetSrc "host\fxr")) {
    $dotnetDest = Join-Path $dist "dotnet"
    if (Test-Path $dotnetDest) { Remove-Item -Recurse -Force $dotnetDest }
    Copy-Item -Recurse -Force $dotnetSrc $dotnetDest
    Write-Host "Embedded dotnet -> $dotnetDest"
} else {
    Write-Warning "No staged dotnet under $redist (run stage_runtimes.ps1)"
}

$wv2Src = Join-Path $redist "WebView2Runtime"
if (Test-Path (Join-Path $wv2Src "*")) {
    $wv2Dest = Join-Path $dist "WebView2Runtime"
    if (Test-Path $wv2Dest) { Remove-Item -Recurse -Force $wv2Dest }
    Copy-Item -Recurse -Force $wv2Src $wv2Dest
    Write-Host "Embedded WebView2 -> $wv2Dest"
}
