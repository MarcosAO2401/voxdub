import argparse
import json
import os
import sys
from .pipeline import Orchestrator


def cmd_transcribe(args):
    orch = Orchestrator(workdir=args.workdir)
    segments, res = orch.run_phase1(args.video, use_mock=args.mock)
    print(json.dumps({
        "status": res.status.value,
        "details": res.details,
        "metrics": res.metrics,
        "segments": [s.__dict__ for s in (segments or [])],
    }, indent=2, ensure_ascii=False))
    if res.status.value != "verified":
        print("AUDITORIA: transcribe NO verificado. No avanzar.", file=sys.stderr)
        return 1
    print("AUDITORIA: transcribe VERIFICADO. Listo para Fase 2.")
    return 0


def cmd_process(args):
    orch = Orchestrator(workdir=args.workdir)
    segments, res = orch.run_phase2(args.video, use_mock=args.mock)
    print(json.dumps({
        "status": res.status.value,
        "details": res.details,
        "metrics": res.metrics,
    }, indent=2, ensure_ascii=False))
    if res.status.value != "verified":
        print("AUDITORIA: etapa NO verificada. No avanzar.", file=sys.stderr)
        return 1
    print("AUDITORIA: transcribe + detect VERIFICADOS. Listo para Fase 3.")
    return 0


def cmd_translate(args):
    orch = Orchestrator(workdir=args.workdir)
    segments, res = orch.run_phase3(args.video, use_mock=args.mock, target_lang=args.lang)
    print(json.dumps({
        "status": res.status.value,
        "details": res.details,
        "metrics": res.metrics,
        "sample": [s.__dict__ for s in (segments or [])][:3],
    }, indent=2, ensure_ascii=False))
    if res.status.value != "verified":
        print("AUDITORIA: etapa NO verificada. No avanzar.", file=sys.stderr)
        return 1
    print("AUDITORIA: transcribe + detect + translate VERIFICADOS. Listo para Fase 4.")
    return 0


def cmd_synthesize(args):
    orch = Orchestrator(workdir=args.workdir)
    segments, res = orch.run_phase4(
        args.video, use_mock=args.mock, target_lang=args.lang, voice_dir=args.voice_dir
    )
    print(json.dumps({
        "status": res.status.value,
        "details": res.details,
        "metrics": res.metrics,
        "audio_files": [s.audio_path for s in (segments or [])][:3],
    }, indent=2, ensure_ascii=False))
    if res.status.value != "verified":
        print("AUDITORIA: etapa NO verificada. No avanzar.", file=sys.stderr)
        return 1
    print("AUDITORIA: transcribe + detect + translate + synthesize VERIFICADOS. Listo para Fase 5.")
    return 0


def cmd_build(args):
    orch = Orchestrator(workdir=args.workdir)
    segments, res = orch.run_phase5(
        args.video, use_mock=args.mock, target_lang=args.lang,
        voice_dir=args.voice_dir, out_path=args.out,
    )
    print(json.dumps({
        "status": res.status.value,
        "details": res.details,
        "metrics": res.metrics,
    }, indent=2, ensure_ascii=False))
    if res.status.value != "verified":
        print("AUDITORIA: pipeline NO verificado. No avanzar.", file=sys.stderr)
        return 1
    print(f"AUDITORIA: PIPELINE COMPLETO VERIFICADO. Video en {args.out}")
    return 0


def cmd_serve(args):
    import uvicorn
    from .api import app
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def main():
    p = argparse.ArgumentParser(prog="voxdub")
    sub = p.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("transcribe", help="Fase 1: transcribir video")
    t.add_argument("video")
    t.add_argument("--mock", action="store_true", help="usar transcriptor mock (offline)")
    t.add_argument("--workdir", default="/tmp/voxdub_work")
    t.set_defaults(func=cmd_transcribe)

    p2 = sub.add_parser("process", help="Fase 1+2: transcribir y detectar hablantes")
    p2.add_argument("video")
    p2.add_argument("--mock", action="store_true", help="usar adaptadores mock (offline)")
    p2.add_argument("--workdir", default="/tmp/voxdub_work")
    p2.set_defaults(func=cmd_process)

    p3 = sub.add_parser("translate", help="Fase 1+2+3: + traducir")
    p3.add_argument("video")
    p3.add_argument("--mock", action="store_true", help="usar adaptadores mock (offline)")
    p3.add_argument("--lang", default="es", help="idioma destino")
    p3.add_argument("--workdir", default="/tmp/voxdub_work")
    p3.set_defaults(func=cmd_translate)

    p4 = sub.add_parser("synthesize", help="Fase 1..4: + sintetizar voz TTS")
    p4.add_argument("video")
    p4.add_argument("--mock", action="store_true", help="adaptador mock (offline)")
    p4.add_argument("--lang", default="es")
    p4.add_argument("--voice-dir", default="voices")
    p4.add_argument("--workdir", default="/tmp/voxdub_work")
    p4.set_defaults(func=cmd_synthesize)

    p5 = sub.add_parser("build", help="Pipeline completo Fase 1..5: exporta .mp4 doblado")
    p5.add_argument("video")
    p5.add_argument("--mock", action="store_true", help="adaptadores mock (offline)")
    p5.add_argument("--lang", default="es")
    p5.add_argument("--voice-dir", default="voices")
    p5.add_argument("--out", default="/tmp/voxdub_work/out.mp4")
    p5.add_argument("--workdir", default="/tmp/voxdub_work")
    p5.set_defaults(func=cmd_build)

    p5.set_defaults(func=cmd_build)

    p6 = sub.add_parser("serve", help="Levanta API + frontend compilado en un solo comando")
    p6.add_argument("--host", default="127.0.0.1")
    p6.add_argument("--port", type=int, default=8000)
    p6.set_defaults(func=cmd_serve)

    args = p.parse_args()
    sys.exit(args.func(args))


if __name__ == "__main__":
    main()
