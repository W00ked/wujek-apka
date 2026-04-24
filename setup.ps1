# Przygotowanie środowiska (Windows PowerShell). Uruchom z katalogu projektu:
#   Set-Location ...\vieo; .\setup.ps1
$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
Set-Location $root

$npx = if (Test-Path "C:\Program Files\nodejs\npx.cmd") { "C:\Program Files\nodejs\npx.cmd" } else { "npx" }
$hf = "hyperframes@0.4.17"

Write-Host "== Python venv + pip install ==" -ForegroundColor Cyan
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    python -m venv .venv
}
& .\.venv\Scripts\python.exe -m pip install -U pip
& .\.venv\Scripts\python.exe -m pip install -e "."

Write-Host "== Playwright (Chromium) ==" -ForegroundColor Cyan
& .\.venv\Scripts\python.exe -m playwright install chromium

Write-Host "== HyperFrames Chrome (CLI $hf) ==" -ForegroundColor Cyan
Push-Location "hyperframes_composition"
try {
    & $npx --yes $hf browser ensure
} finally {
    Pop-Location
}

if (-not (Test-Path ".env")) {
    Write-Host "== Utwórz plik .env (skopiuj z .env.example i uzupełnij klucze API) ==" -ForegroundColor Yellow
} else {
    Write-Host "== .env już istnieje ==" -ForegroundColor Green
}

Write-Host ""
Write-Host "Gotowe. Uruchomienie: .\.venv\Scripts\Activate.ps1  →  logi-video --config config.yaml ..." -ForegroundColor Green
