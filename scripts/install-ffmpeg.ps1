# Install FFmpeg for MP3/MP4 audio import (pydub dependency).
# Run: .\scripts\install-ffmpeg.ps1
# If ffmpeg is not found after install, open a NEW terminal (PATH updates there).

$ErrorActionPreference = "Stop"
Write-Host "Installing FFmpeg via winget..."
winget install --id Gyan.FFmpeg -e --accept-package-agreements --accept-source-agreements
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

# Refresh PATH in this session so ffmpeg works without restarting the terminal
$userPath = [Environment]::GetEnvironmentVariable("Path", "User")
$env:Path = "$userPath;$env:Path"

Write-Host ""
Write-Host "Done. Run: ffmpeg -version"
Write-Host "If that fails, open a new terminal and try again."
