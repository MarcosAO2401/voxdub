# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_submodules

hiddenimports = ['voxdub', 'voxdub.api', 'voxdub.jobs', 'voxdub.server', 'voxdub.pipeline.orchestrator', 'voxdub.pipeline.transcribe', 'voxdub.pipeline.detect', 'voxdub.pipeline.translate', 'voxdub.pipeline.synthesize', 'voxdub.pipeline.lipsync', 'voxdub.pipeline.mux', 'voxdub.pipeline.subtitles', 'edge_tts', 'faster_whisper']
hiddenimports += collect_submodules('edge_tts')
hiddenimports += collect_submodules('faster_whisper')


a = Analysis(
    ['/root/voxdub/scripts/entry.py'],
    pathex=['/root/voxdub/src/backend'],
    binaries=[('/root/voxdub/bin/ffmpeg', 'bin'), ('/root/voxdub/bin/ffprobe', 'bin')],
    datas=[('/root/voxdub/voices', 'voices'), ('/root/voxdub/web/dist', 'web/dist')],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='voxdub-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
