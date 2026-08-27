# VoxDub — arranque en un comando (Windows PowerShell).
# Prepara el entorno (venv + deps + build del frontend) y levanta API + UI.
$ErrorActionPreference = "Stop"
cd $PSScriptRoot

Write-Host "==> VoxDub: preparando frontend..."
if (-not (Test-Path web/dist/index.html)) {
  Push-Location web
  npm install
  npm run build
  Pop-Location
} else {
  Write-Host "    web/dist ya existe; omito build."
}

Write-Host "==> VoxDub: preparando backend (venv)..."
if (-not (Test-Path .venv)) {
  python -m venv .venv
}
. .venv/Scripts/Activate.ps1
pip install -q -r requirements.txt faster-whisper edge-tts yt-dlp | Select-Object -Last 2

Write-Host "==> VoxDub: levantando en http://127.0.0.1:8000 ..."
Start-Process "http://127.0.0.1:8000"
$env:PYTHONPATH = "src/backend"
python -m voxdub.cli serve --host 127.0.0.1 --port 8000
