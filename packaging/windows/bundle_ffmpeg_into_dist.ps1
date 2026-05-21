# After PyInstaller onedir, copy imageio-ffmpeg binary to ffmpeg.exe (and ffprobe when available)
# so yt-dlp postprocessors and subprocess callers find standard names next to DLPulseNext.exe.
#
# Usage: pwsh -File packaging/windows/bundle_ffmpeg_into_dist.ps1 [REPO_ROOT]
param(
    [Parameter(Position = 0)]
    [string]$RepoRoot = ""
)

$ErrorActionPreference = "Stop"
if (-not $RepoRoot) { $RepoRoot = (Get-Location).Path }
Push-Location $RepoRoot
try {
    $py = if ($env:PYTHON) { $env:PYTHON } else { "python" }
    $dist = Join-Path $RepoRoot "dist\DLPulseNext"
    if (-not (Test-Path (Join-Path $dist "DLPulseNext.exe"))) {
        throw "Missing dist\DLPulseNext\DLPulseNext.exe — run PyInstaller first."
    }

    $ffmpeg = (& $py -c "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())" 2>$null).Trim()
    if (-not $ffmpeg -or -not (Test-Path -LiteralPath $ffmpeg)) {
        throw "imageio-ffmpeg did not provide an ffmpeg executable (PYTHON=$py)."
    }

    $destFfmpeg = Join-Path $dist "ffmpeg.exe"
    Copy-Item -LiteralPath $ffmpeg -Destination $destFfmpeg -Force
    Write-Host "bundle_ffmpeg_into_dist: $destFfmpeg"

    $ioDir = Split-Path -Parent $ffmpeg
    $ffprobeSrc = Join-Path $ioDir "ffprobe.exe"
    $destProbe = Join-Path $dist "ffprobe.exe"
    if (Test-Path -LiteralPath $ffprobeSrc) {
        Copy-Item -LiteralPath $ffprobeSrc -Destination $destProbe -Force
        Write-Host "bundle_ffmpeg_into_dist: $destProbe (imageio folder)"
    }
    elseif (Get-Command ffprobe -ErrorAction SilentlyContinue) {
        $fp = (Get-Command ffprobe).Source
        Copy-Item -LiteralPath $fp -Destination $destProbe -Force
        Write-Host "bundle_ffmpeg_into_dist: $destProbe (PATH)"
    }
    else {
        Write-Warning "bundle_ffmpeg_into_dist: no ffprobe — some yt-dlp merges may still work."
    }
}
finally {
    Pop-Location
}
