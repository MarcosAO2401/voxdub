#!/usr/bin/env bash
# Prepara el sidecar del backend para Tauri:
#   1) compila el backend Python en un binario autónomo (PyInstaller)
#   2) copia el binario a src-tauri/binaries/ con el sufijo del target triple
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

TARGET_TRIPLE="${1:-x86_64-unknown-linux-gnu}"
DEST_DIR="web/src-tauri/binaries"
mkdir -p "$DEST_DIR"

echo ">>> Compilando backend (PyInstaller)..."
PYTHONPATH=src/backend python scripts/build_backend.py

SRC="dist_backend/voxdub-backend"
if [ ! -f "$SRC" ]; then
  echo "ERROR: no se generó $SRC"; exit 1
fi

DEST="$DEST_DIR/voxdub-backend-$TARGET_TRIPLE"
cp "$SRC" "$DEST"
chmod +x "$DEST"
echo ">>> Sidecar listo en $DEST"
echo ">>> Luego: cd web && npm install && npm run tauri:build"
