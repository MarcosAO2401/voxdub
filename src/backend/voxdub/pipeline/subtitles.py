"""Generación de subtítulos (SRT/VTT) a partir de los segmentos traducidos.

Los subtítulos reflejan el audio doblado (texto traducido). Es una salida adicional
del pipeline, no una etapa auditada más (se produce junto al mux final).
"""


def _srt_time(t: float) -> str:
    t = max(0.0, float(t))
    ms = int(round((t - int(t)) * 1000))
    s = int(t) % 60
    m = (int(t) // 60) % 60
    h = int(t) // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _vtt_time(t: float) -> str:
    return _srt_time(t).replace(",", ".")


def _seg_text(seg) -> str:
    return getattr(seg, "text", "") or ""


def write_subtitles(segments: list, base_path: str) -> dict:
    """Escribe `<base>.srt` y `<base>.vtt`. Devuelve los paths generados."""
    srt_path = base_path + ".srt"
    vtt_path = base_path + ".vtt"

    srt_lines = []
    vtt_lines = ["WEBVTT", ""]
    for i, seg in enumerate(segments, 1):
        start = getattr(seg, "start", 0.0)
        end = getattr(seg, "end", 0.0)
        text = _seg_text(seg).strip()
        if not text:
            continue
        srt_lines.append(str(i))
        srt_lines.append(f"{_srt_time(start)} --> {_srt_time(end)}")
        srt_lines.append(text)
        srt_lines.append("")
        vtt_lines.append(f"{_vtt_time(start)} --> {_vtt_time(end)}")
        vtt_lines.append(text)
        vtt_lines.append("")

    with open(srt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(srt_lines))
    with open(vtt_path, "w", encoding="utf-8") as f:
        f.write("\n".join(vtt_lines))

    return {"srt": srt_path, "vtt": vtt_path}


def validate_subtitles(srt_path: str) -> tuple[bool, str]:
    if not srt_path or not __import__("os").path.exists(srt_path):
        return False, "subtítulos no generados"
    size = __import__("os").path.getsize(srt_path)
    if size == 0:
        return False, "subtítulos vacíos"
    return True, "ok"


def _font_for(lang: str) -> str:
    # libass usa el nombre; si no existe, cae a una fuente por defecto (no rompe).
    return {
        "ja": "Noto Sans CJK JP",
        "zh": "Noto Sans CJK SC",
        "ko": "Noto Sans CJK KR",
        "ar": "Noto Sans Arabic",
        "ru": "DejaVu Sans",
        "el": "DejaVu Sans",
    }.get(lang, "DejaVu Sans")


def burn_subtitles(video_path: str, srt_path: str, out_path: str, lang: str = "es") -> str:
    """Quema (hardsub) los subtítulos SRT en el video mediante ffmpeg.
    Devuelve out_path. Requiere ffmpeg con soporte de subtítulos (libass)."""
    import subprocess
    from . import audio
    # Escapar la ruta para el filtro subtitles=filename='...'
    esc = srt_path.replace("\\", "/").replace(":", r"\:").replace("'", r"\'")
    font = _font_for(lang).replace("'", r"\'")
    filter_str = (
        f"subtitles='{esc}':force_style="
        rf"'FontName={font},FontSize=22,PrimaryColour=&HFFFFFF&,OutlineColour=&H000000&,"
        r"BorderStyle=3,Outline=1,Shadow=0,Alignment=2'"
    )
    subprocess.check_call([
        audio.resolve_bin("ffmpeg"), "-y", "-i", video_path,
        "-vf", filter_str, "-c:a", "copy", out_path,
    ])
    return out_path
