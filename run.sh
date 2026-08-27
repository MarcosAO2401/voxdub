#!/usr/bin/env bash
# VoxDub — arranque en un comando (Linux/macOS).
# Si existe el binario autónomo, lo usa directo (cero instalación).
# Si no, prepara el entorno (venv + deps + build del frontend) y levanta API + UI.
set -e
cd "$(dirname "$0")"

# En Termux /tmp es de solo lectura: usar un temporal escribible.
export TMPDIR="$PWD/.tmp"
mkdir -p "$TMPDIR"

BIN="dist_backend/voxdub-backend"
if [ -x "$BIN" ] && file "$BIN" 2>/dev/null | grep -q "executable"; then
  echo "==> VoxDub: usando binario autónomo (sin instalación)."
  exec "$BIN"
fi

echo "==> VoxDub: preparando frontend..."
if [ ! -f web/dist/index.html ]; then
  (cd web && npm install && npm run build)
else
  echo "    web/dist ya existe; omito build (borra web/dist para reconstruir)."
fi

echo "==> VoxDub: preparando backend (venv)..."
if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
pip install -q -r requirements.txt 2>&1 | tail -2 || true

echo "==> VoxDub: levantando en http://127.0.0.1:8001 ..."
# Abre el navegador automáticamente (best-effort).
(sleep 3; (command -v xdg-open >/dev/null && xdg-open http://127.0.0.1:8001) || (command -v open >/dev/null && open http://127.0.0.1:8001)) >/dev/null 2>&1 &
PYTHONPATH=src/backend python -m voxdub.cli serve --host 127.0.0.1 --port 8001
