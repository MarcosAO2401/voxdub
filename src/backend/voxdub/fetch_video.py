"""Descarga de videos desde una URL para el pipeline de traducción/doblaje.

Soporta:
  - Enlaces directos a .mp4/.mov/... vía HTTP(S) (stdlib, sin dependencias).
  - Plataformas (YouTube/TikTok/etc.) si `yt-dlp` está instalado (opcional).
El llamador es responsable de que la URL sea de contenido propio o autorizado.
"""
import os
import shutil
import subprocess
import sys
import urllib.request

HTTP_TIMEOUT = 120  # anti-cuelgue; el tamaño es ilimitado por decisión del producto


def download_video(url: str, dest: str) -> str:
    """Descarga `url` a `dest`. Lanza RuntimeError con mensaje claro si falla."""
    os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)

    # 1) Plataformas (yt-dlp) si está disponible y el enlace no es un archivo directo.
    if "yt_dlp" in sys.modules or _looks_like_platform(url):
        try:
            import yt_dlp  # type: ignore
            ydl_opts = {"outtmpl": dest, "format": "mp4/best", "quiet": True,
                        "no_warnings": True, "socket_timeout": HTTP_TIMEOUT}
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                return dest
        except ImportError:
            pass  # caer a HTTP directo
        except Exception as e:
            if _looks_like_platform(url):
                raise RuntimeError(
                    f"No se pudo descargar desde la plataforma: {e}. "
                    "Instala yt-dlp: pip install yt-dlp"
                )

    # 2) Descarga HTTP(S) directa (tamaño ilimitado; solo se controla el timeout).
    if url.startswith(("http://", "https://")):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "VoxDub/0.1"})
            with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as r, open(dest, "wb") as f:
                for chunk in iter(lambda: r.read(1024 * 1024), b""):
                    f.write(chunk)
            if os.path.exists(dest) and os.path.getsize(dest) > 0:
                return dest
            raise RuntimeError("descarga vacía")
        except Exception as e:
            if os.path.exists(dest):
                os.remove(dest)
            raise RuntimeError(f"No se pudo descargar el video desde {url}: {e}")

    raise RuntimeError(f"URL no soportada o vacía: {url}")


def _looks_like_platform(url: str) -> bool:
    low = url.lower()
    return any(h in low for h in ("youtube.com", "youtu.be", "tiktok.com",
                                  "instagram.com", "facebook.com", "vimeo.com",
                                  "twitter.com", "x.com"))
