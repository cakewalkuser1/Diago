# Optional: download the full Operation CHARM (charm.li) database via BitTorrent (~700GB).
# You do NOT need this to use charm.li in Diago: the app opens manual links in your
# browser on demand (no local storage). Use this script only if you want the full archive.
#
# Usage:
#   .\scripts\download-charm-li.ps1                    # download torrent file only
#   .\scripts\download-charm-li.ps1 -OutputDir D:\charm # custom download directory
#   .\scripts\download-charm-li.ps1 -StartDownload      # open in default torrent app (if associated)
#
# After opening the torrent: add charm.li:17471 as a peer if you have trouble connecting.
# See https://charm.li/about.html

param(
    [string]$OutputDir = "",
    [switch]$StartDownload
)

$TorrentUrl = "https://charm.li/operation-charm.torrent"
$CharmPeer = "charm.li:17471"

# Default: project data folder or current directory
if (-not $OutputDir) {
    $ProjectRoot = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
    $OutputDir = Join-Path $ProjectRoot "data" "charm-li"
}

$Null = New-Item -ItemType Directory -Force -Path $OutputDir
$TorrentPath = Join-Path $OutputDir "operation-charm.torrent"

Write-Host "Operation CHARM (charm.li) — full database torrent"
Write-Host "Archive size: ~700GB. Ensure you have enough disk space and a BitTorrent client."
Write-Host ""

Write-Host "Downloading torrent file to: $TorrentPath"
try {
    Invoke-WebRequest -Uri $TorrentUrl -OutFile $TorrentPath -UseBasicParsing
    Write-Host "Saved: $TorrentPath"
} catch {
    Write-Error "Failed to download torrent: $_"
    exit 1
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Open the torrent in your BitTorrent client (qBittorrent, Transmission, etc.)."
Write-Host "  2. Choose a download location with at least 700GB free."
Write-Host "  3. If you have trouble connecting, add this peer: $CharmPeer"
Write-Host ""

if ($StartDownload) {
    if (Test-Path $TorrentPath) {
        Start-Process $TorrentPath
        Write-Host "Opened torrent in default application."
    }
} else {
    Write-Host "To open the torrent now, run: Start-Process '$TorrentPath'"
}
