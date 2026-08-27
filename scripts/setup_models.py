"""Setup de modelos reales para VoxDub (ASR/diarización/lip-sync locales y gratuitos).

No es estrictamente necesario: el modo 'IA gratuita (nube)' ya produce doblaje real
(traducción MyMemory + voz edge-tts). Este script habilita el modo 'Real local',
donde la transcripción usa Whisper en tu máquina (sin costo, sin envío a la nube).

Uso:
    python scripts/setup_models.py
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def pip(pkgs):
    subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])


def main():
    print("== Instalando dependencias de modelos reales ==")
    pip(["faster-whisper", "pyannote.audio"])
    # Wav2Lip requiere torch; se instala bajo demanda por el usuario según su GPU/CPU.
    print("== Pre-descarga del modelo Whisper (tiny) ==")
    try:
        from faster_whisper import WhisperModel
        WhisperModel("tiny", device="auto", compute_type="int8")
        print("Whisper 'tiny' listo.")
    except Exception as e:
        print(f"No se pudo pre-descargar Whisper: {e}")

    print("== Descargando una voz Piper (español femenino) ==")
    voice_url = "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/dania/Medium/es_ES-dania-medium.onnx"
    try:
        subprocess.check_call([
            sys.executable, os.path.join(ROOT, "scripts", "fetch_voice.py"),
            "--name", "ia-voice-female-01",
            "--url", voice_url,
        ])
    except Exception as e:
        print(f"No se pudo descargar la voz Piper (la TTS local queda opcional): {e}")

    print("\n== Wav2Lip (lip-sync real) ==")
    repo = os.path.expanduser("~/Wav2Lip")
    try:
        print(f"Clonando Wav2Lip en {repo} ...")
        subprocess.check_call(["git", "clone", "https://github.com/Rudrabha/Wav2Lip", repo])
    except Exception as e:
        print(f"No se pudo clonar Wav2Lip (hazlo manual): {e}")
    # Descargar checkpoint GAN y el modelo de detección de rostro (s3fd).
    os.makedirs(os.path.join(repo, "checkpoints"), exist_ok=True)
    ckpt = os.path.join(repo, "checkpoints", "wav2lip_gan.pth")
    s3fd_dir = os.path.join(repo, "face_detection", "detection", "sfd")
    os.makedirs(s3fd_dir, exist_ok=True)
    s3fd = os.path.join(s3fd_dir, "s3fd.pth")
    try:
        print("Descargando wav2lip_gan.pth (436 MB)...")
        subprocess.check_call(["curl", "-L", "-o", ckpt,
                              "https://huggingface.co/camenduru/Wav2Lip/resolve/main/checkpoints/wav2lip_gan.pth"])
        print("Descargando s3fd.pth (89 MB)...")
        subprocess.check_call(["curl", "-L", "-o", s3fd,
                              "https://www.adrianbulat.com/downloads/python-fan/s3fd-619a316812.pth"])
    except Exception as e:
        print(f"No se pudieron descargar los pesos de Wav2Lip: {e}")
    print("Instalando torch + dependencias de Wav2Lip (puede ser pesado)...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "torch", "torchvision",
                              "face_alignment", "opencv-python", "numpy", "scipy", "yacs", "ipykernel"])
    except Exception as e:
        print(f"Instala torch manualmente para tu GPU/CPU: {e}")
    print("\nPara usar lip-sync real, exporta:")
    print(f"  export WAV2LIP_REPO={repo}")
    print(f"  export WAV2LIP_CKPT={ckpt}")

    print("\n== Pyannote (diarización/género real) ==")
    print("Los modelos de pyannote son gated. Necesitas un token de Hugging Face:")
    print("  1) crea HF_TOKEN en https://huggingface.co/settings/tokens")
    print("  2) acepta los términos de pyannote/speaker-diarization@2.1")
    print("  3) exporta: export HF_TOKEN=<tu_token>")
    print("El modo 'Real local' usará diarización real; si no, degrada a mock.")
    print("\nSetup completado.")


if __name__ == "__main__":
    main()
