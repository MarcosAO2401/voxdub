"""Empaqueta el backend VoxDub como binario independiente (onefile) con PyInstaller.

Uso:
    PYTHONPATH=src/backend python scripts/build_backend.py
Salida:
    dist_backend/voxdub-backend  (binario autónomo de la API + frontend compilado)
"""
import os
import PyInstaller.__main__

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND = os.path.join(ROOT, "src", "backend")
ENTRY = os.path.join(ROOT, "scripts", "entry.py")

PyInstaller.__main__.run([
    ENTRY,
    "--name", "voxdub-backend",
    "--onefile",
    "--paths", BACKEND,
    "--hidden-import", "voxdub",
    "--hidden-import", "voxdub.api",
    "--hidden-import", "voxdub.jobs",
    "--hidden-import", "voxdub.server",
    "--hidden-import", "voxdub.pipeline.orchestrator",
    "--hidden-import", "voxdub.pipeline.transcribe",
    "--hidden-import", "voxdub.pipeline.detect",
    "--hidden-import", "voxdub.pipeline.translate",
    "--hidden-import", "voxdub.pipeline.synthesize",
    "--hidden-import", "voxdub.pipeline.lipsync",
    "--hidden-import", "voxdub.pipeline.mux",
    "--hidden-import", "voxdub.pipeline.subtitles",
    "--hidden-import", "edge_tts",
    "--collect-submodules", "edge_tts",
    "--hidden-import", "faster_whisper",
    "--collect-submodules", "faster_whisper",
    "--add-data", os.path.join(ROOT, "voices") + os.pathsep + "voices",
    "--add-data", os.path.join(ROOT, "web", "dist") + os.pathsep + "web/dist",
    "--add-binary", os.path.join(ROOT, "bin", "ffmpeg") + os.pathsep + "bin",
    "--add-binary", os.path.join(ROOT, "bin", "ffprobe") + os.pathsep + "bin",
    "--distpath", os.path.join(ROOT, "dist_backend"),
    "--workpath", os.path.join(ROOT, "build_backend"),
    "--noconfirm",
])
