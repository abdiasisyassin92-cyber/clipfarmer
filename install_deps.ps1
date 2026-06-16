# ClipFarmer — Dependency Installer
# Run from PowerShell: .\install_deps.ps1

Write-Host "`n=== ClipFarmer Dependency Installer ===" -ForegroundColor Cyan

$packages = @(
    "requests",
    "yt-dlp",
    "openai-whisper",
    "google-auth-oauthlib",
    "google-api-python-client",
    "crewai",
    "crewai-tools",
    "litellm",
    "customtkinter",
    "keyboard",
    "python-dotenv"
)

foreach ($pkg in $packages) {
    Write-Host "`nInstalling $pkg..." -ForegroundColor Yellow
    pip install $pkg --quiet
    if ($LASTEXITCODE -eq 0) {
        Write-Host "  OK: $pkg" -ForegroundColor Green
    } else {
        Write-Host "  FAILED: $pkg" -ForegroundColor Red
    }
}

Write-Host "`n=== Done. Run: python clipfarmer\scheduler.py ===" -ForegroundColor Cyan
