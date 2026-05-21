# Stage portable .NET Desktop 8 + WebView2 for the NSIS installer (Windows CI / dev).
# Usage: pwsh -File packaging/windows/stage_runtimes.ps1
param([string]$DotNetVersion = "8.0.22")

$ErrorActionPreference = "Stop"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Redist = Join-Path $PSScriptRoot "redist"
$Installers = Join-Path $Redist "installers"
$DotNetDir = Join-Path $Redist "dotnet"
$WebView2Dir = Join-Path $Redist "WebView2Runtime"

foreach ($d in @($Redist, $Installers, $DotNetDir, $WebView2Dir)) {
    if (Test-Path $d) { Remove-Item -Recurse -Force $d }
    New-Item -ItemType Directory -Force -Path $d | Out-Null
}

function Get-RemoteFile([string]$Url, [string]$Dest) {
    Write-Host "GET $Url"
    Invoke-WebRequest -Uri $Url -OutFile $Dest -UseBasicParsing
}

function Expand-DotnetZipInto([string]$ZipPath, [string]$DestDir) {
    $extractTemp = Join-Path $env:TEMP ("dotnet-extract-" + [guid]::NewGuid().ToString("n"))
    New-Item -ItemType Directory -Force -Path $extractTemp | Out-Null
    try {
        Expand-Archive -LiteralPath $ZipPath -DestinationPath $extractTemp -Force
        $roots = @($extractTemp)
        $roots += Get-ChildItem -Path $extractTemp -Directory -ErrorAction SilentlyContinue | ForEach-Object { $_.FullName }
        $picked = $roots | Where-Object {
            (Test-Path (Join-Path $_ "host\fxr")) -or
            (Test-Path (Join-Path $_ "shared"))
        } | Sort-Object { $_.Length } | Select-Object -First 1
        if (-not $picked) {
            throw "No host/fxr or shared/ in extracted zip ($ZipPath)"
        }
        Get-ChildItem -LiteralPath $picked | Copy-Item -Destination $DestDir -Recurse -Force
    }
    finally {
        if (Test-Path $extractTemp) { Remove-Item -Recurse -Force $extractTemp }
    }
}

# CoreCLR host + Microsoft.NETCore.App (required for pythonnet / hostfxr).
$coreZipUrl = "https://builds.dotnet.microsoft.com/dotnet/Runtime/$DotNetVersion/dotnet-runtime-$DotNetVersion-win-x64.zip"
$coreZipPath = Join-Path $env:TEMP "dotnet-runtime-$DotNetVersion-win-x64.zip"
Get-RemoteFile $coreZipUrl $coreZipPath
Expand-DotnetZipInto $coreZipPath $DotNetDir
Remove-Item -Force $coreZipPath

# WinForms / WPF shared framework (windowsdesktop zip has no host/ — only shared/Microsoft.WindowsDesktop.App).
$desktopZipUrl = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/$DotNetVersion/windowsdesktop-runtime-$DotNetVersion-win-x64.zip"
$desktopZipPath = Join-Path $env:TEMP "windowsdesktop-runtime-$DotNetVersion-win-x64.zip"
Get-RemoteFile $desktopZipUrl $desktopZipPath
Expand-DotnetZipInto $desktopZipPath $DotNetDir
Remove-Item -Force $desktopZipPath

$installerUrl = "https://builds.dotnet.microsoft.com/dotnet/WindowsDesktop/$DotNetVersion/windowsdesktop-runtime-$DotNetVersion-win-x64.exe"
Get-RemoteFile $installerUrl (Join-Path $Installers "windowsdesktop-runtime-$DotNetVersion-win-x64.exe")

if (-not (Test-Path (Join-Path $DotNetDir "host\fxr"))) {
    throw "Invalid dotnet layout under $DotNetDir (missing host\fxr after merging runtime zips)"
}
if (-not (Test-Path (Join-Path $DotNetDir "shared\Microsoft.WindowsDesktop.App"))) {
    throw "Invalid dotnet layout under $DotNetDir (missing Microsoft.WindowsDesktop.App)"
}
Write-Host "OK dotnet -> $DotNetDir"

# --- WebView2 (portable copy from build host, else bootstrapper for NSIS silent install) ---
$wv2Copied = $false
$wv2Sources = @(
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView\Application",
    "${env:ProgramFiles}\Microsoft\EdgeWebView\Application",
    "${env:ProgramFiles(x86)}\Microsoft\EdgeWebView"
)
foreach ($src in $wv2Sources) {
    if (-not (Test-Path $src)) { continue }
    $exe = Get-ChildItem -Path $src -Recurse -Filter "msedgewebview2.exe" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($exe) {
        $dest = Join-Path $WebView2Dir "Application"
        if ($exe.DirectoryName -like "*\Application\*") {
            $appRoot = $exe.DirectoryName
            while ($appRoot -and (Split-Path -Leaf $appRoot) -ne "Application") {
                $parent = Split-Path $appRoot -Parent
                if (-not $parent -or $parent -eq $appRoot) { break }
                $appRoot = $parent
            }
            if ((Split-Path -Leaf $appRoot) -eq "Application") {
                Copy-Item -Recurse -Force $appRoot $dest
            } else {
                Copy-Item -Recurse -Force $exe.DirectoryName $WebView2Dir
            }
        } else {
            Copy-Item -Recurse -Force $exe.DirectoryName $WebView2Dir
        }
        Write-Host "OK WebView2 copied from $($exe.DirectoryName)"
        $wv2Copied = $true
        break
    }
}

if (-not $wv2Copied) {
    Write-Host "WebView2 not on host; bundling bootstrapper for silent install during setup"
    Get-RemoteFile "https://go.microsoft.com/fwlink/?linkid=2124703" (Join-Path $Installers "MicrosoftEdgeWebview2Setup.exe")
}

@"
dotnet_version=$DotNetVersion
webview2_portable_copied=$wv2Copied
"@ | Set-Content -Encoding UTF8 (Join-Path $Redist "manifest.txt")

Write-Host "Redist ready: $Redist"
