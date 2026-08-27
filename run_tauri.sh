#!/usr/bin/env bash
# VoxDub — app de escritorio (Tauri) en un comando.
# Requiere: Rust + el paquete de desarrollo de webkit de tu SO
#   Linux:  sudo apt install libwebkit2gtk-4.1-dev build-essential
#   macOS:  Xcode (xcode-select --install)
#   Windows: Visual Studio Build Tools + WebView2
set -e
cd "$(dirname "$0")/web"

# Tripla por defecto según el SO (pásala como $1 para sobreescribir).
TRIPLE="${1:-}"
if [ -z "$TRIPLE" ]; then
  case "$(uname -s)" in
    Darwin)  TRIPLE="aarch64-apple-darwin" ;;
    Linux)   TRIPLE="x86_64-unknown-linux-gnu" ;;
    MINGW*|MSYS*|CYGWIN*) TRIPLE="x86_64-pc-windows-msvc" ;;
    *)       TRIPLE="x86_64-unknown-linux-gnu" ;;
  esac
fi

npm install
bash ../scripts/prepare_tauri_sidecar.sh "$TRIPLE"
npm run tauri:dev      # modo desarrollo (ventana nativa)
# Para generar el instalable:  npm run tauri:build
