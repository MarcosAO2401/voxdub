#!/usr/bin/env python3
"""Descarga segura de una voz Piper hacia voices/ con verificación SHA256.

Uso:
  python scripts/fetch_voice.py --name es_ES-carlfm-low \
      --url https://URL_BASE/es_ES-carlfm-low.onnx \
      --sha256 <hash-esperado>

Seguridad:
  - La URL y el hash se pasan explícitamente (pinned source, no confianza ciega).
  - Si se omite --sha256, el script lo calcula y lo muestra (modo "aprender hash").
  - No se sobrescribe una voz existente sin --force.
"""
import argparse
import hashlib
import os
import sys
import urllib.request


def sha256_of(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--name", required=True, help="nombre base, p.ej. es_ES-carlfm-low")
    ap.add_argument("--url", required=True, help="URL directa del .onnx")
    ap.add_argument("--sha256", default=None, help="hash SHA256 esperado (opcional)")
    ap.add_argument("--voice-dir", default="voices")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    out_dir = args.voice_dir
    os.makedirs(out_dir, exist_ok=True)
    dest = os.path.join(out_dir, f"{args.name}.onnx")

    if os.path.exists(dest) and not args.force:
        print(f"Ya existe {dest}. Usa --force para sobreescribir.")
        return

    print(f"Descargando {args.url} ...")
    urllib.request.urlretrieve(args.url, dest)

    digest = sha256_of(dest)
    print(f"SHA256 descargado: {digest}")
    if args.sha256:
        if digest.lower() != args.sha256.lower():
            print("ERROR: hash no coincide. Abortando (posible alteración).", file=sys.stderr)
            os.remove(dest)
            sys.exit(1)
        print("Hash verificado OK.")
    else:
        print("Sugerencia: guarda este hash y pásalo con --sha256 en próximas descargas.")

    # Descargar también el .onnx.json de metadatos si existe
    meta = args.url + ".json"
    try:
        urllib.request.urlretrieve(meta, os.path.join(out_dir, f"{args.name}.onnx.json"))
        print("Metadatos .onnx.json descargados.")
    except Exception:
        print("Metadatos .onnx.json no disponibles (opcional).")

    print(f"Voz lista en {dest}. Actualiza voices/manifest.json si quieres usarla por defecto.")


if __name__ == "__main__":
    main()
