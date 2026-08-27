import React, { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";

type Stage = { name: string; status: string; details?: string; metrics?: any };
type JobState = { id: string; status: string; stages: Stage[]; output: string | null; error: string | null; subtitles?: any };
type Seg = { index: number; start: number; end: number; speaker?: string; gender?: string; source: string; target: string };

const STATUS: Record<string, string> = {
  pending: "⧗ pendiente",
  queued: "⧗ en cola",
  running: "▶ ejecutando",
  verified: "✓ verificado",
  done: "✓ listo",
  failed: "✗ falló",
};
function statusColor(s: string) {
  if (s === "verified" || s === "done") return "text-cyan-300";
  if (s === "failed") return "text-red-400";
  if (s === "running") return "text-indigo-300";
  return "text-white/50";
}

const API = (typeof window !== "undefined" && window.location?.origin) || "";
const LANG_NAMES: Record<string, string> = {
  es: "Español", en: "Inglés", fr: "Francés", de: "Alemán", it: "Italiano",
  pt: "Portugués", ru: "Ruso", ja: "Japonés", zh: "Chino", ko: "Coreano", ar: "Árabe",
};
const STAGES = ["transcribe", "detect", "translate", "synthesize", "lipsync", "mux"];

const TERMS = {
  title: "Términos de uso y responsabilidad",
  responsible_use:
    "El usuario es el ÚNICO responsable del uso que dé a VoxDub. La aplicación es una herramienta local de traducción y doblaje; quien la usa asume entera responsabilidad por el contenido procesado y por el cumplimiento de las leyes y condiciones de las plataformas de origen.",
  rules: [
    "Procesa únicamente videos de tu propiedad o con autorización expresa del titular.",
    "No clones la voz de personas reales sin su consentimiento; la app usa TTS estándar/generado por IA.",
    "Cumples las leyes de derechos de autor y los ToS de YouTube/TikTok/Instagram/Facebook/etc. al aportar enlaces.",
    "El procesamiento es local; tú decides y respondes por los archivos y URLs que ingresas.",
  ],
  disclaimer:
    "VoxDub se entrega 'tal cual', sin garantías. El uso indebido es responsabilidad exclusiva del usuario.",
};

function fmt(t: number) {
  const s = Math.floor(t);
  return `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;
}

export default function App() {
  const [mode, setMode] = useState<"file" | "url">("file");
  const [file, setFile] = useState<File | null>(null);
  const [filePreview, setFilePreview] = useState<string | null>(null);
  const [url, setUrl] = useState("");
  const [lang, setLang] = useState("es");
  const [srcLang, setSrcLang] = useState("");
  const [voice, setVoice] = useState("default");
  const [aimode, setAimode] = useState<"mock" | "free" | "real">("mock");
  const [burn, setBurn] = useState(false);
  const [job, setJob] = useState<JobState | null>(null);
  const [busy, setBusy] = useState(false);
  const [connError, setConnError] = useState<string | null>(null);
  const [showLegal, setShowLegal] = useState(false);
  const [accepted, setAccepted] = useState(
    typeof localStorage !== "undefined" && localStorage.getItem("voxdub_accepted") === "1"
  );
  const [backendReady, setBackendReady] = useState(false);
  const [connecting, setConnecting] = useState(true);
  const [realAsrAvailable, setRealAsrAvailable] = useState(true);

  useEffect(() => {
    let alive = true;
    let tries = 0;
    const tick = async () => {
      try {
        const r = await fetch(`${API}/legal`, { method: "GET" });
        if (alive && r.ok) { setBackendReady(true); setConnecting(false); return; }
      } catch {}
      tries += 1;
      if (alive && tries < 60) setTimeout(tick, 1000);
      else if (alive) setConnecting(false);
    };
    tick();
    // Check real ASR capability
    if (alive) {
      fetch(`${API}/capabilities`).then(r => r.json()).then(d => {
        if (alive && d?.real_asr === false) setRealAsrAvailable(false);
      }).catch(() => {});
    }
    return () => { alive = false; };
  }, []);
  const [transcript, setTranscript] = useState<Seg[]>([]);
  const [edited, setEdited] = useState<Record<number, string>>({});

  function reset() {
    setJob(null);
    setBusy(false);
    setConnError(null);
    setFile(null);
    setFilePreview(null);
    setUrl("");
    setTranscript([]);
    setEdited({});
  }

  async function cancelJob() {
    if (!job) return;
    try {
      await fetch(`${API}/jobs/${job.id}/cancel`, { method: "POST" });
    } catch {}
  }

  async function start() {
    if (mode === "file" && !file) return;
    if (mode === "url" && !url.trim()) return;
    setBusy(true);
    setConnError(null);
    try {
      const aiParam = aimode === "mock" ? "mock" : "free";
      const mockParam = aimode === "real" ? "false" : "true";
      const qs = `mock=${mockParam}&ai=${aiParam}&target_lang=${encodeURIComponent(lang)}&voice_style=${encodeURIComponent(voice)}`
        + (srcLang ? `&source_lang=${encodeURIComponent(srcLang)}` : "")
        + (burn ? "&burn=true" : "");
      let res: Response;
      if (mode === "file") {
        const fd = new FormData();
        fd.append("file", file!);
        res = await fetch(`${API}/jobs?${qs}`, { method: "POST", body: fd });
      } else {
        res = await fetch(`${API}/jobs?${qs}&url=${encodeURIComponent(url.trim())}`, { method: "POST" });
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setConnError(err.error || err.detail || `error ${res.status} del servidor`);
        setBusy(false);
        return;
      }
      const data = await res.json();
      setJob({ id: data.job_id, status: "queued", stages: [], output: null, error: null });
      poll(data.job_id);
    } catch (e) {
      setConnError("No se pudo conectar al backend. ¿Está corriendo VoxDub?");
      setBusy(false);
    }
  }

  async function poll(id: string) {
    for (let i = 0; i < 240; i++) {
      try {
        const r = await fetch(`${API}/jobs/${id}`);
        if (!r.ok) {
          setConnError("No se pudo obtener el estado del job.");
          break;
        }
        const j: JobState = await r.json();
        setJob(j);
        if (j.status === "done" && transcript.length === 0) {
          const t = await fetch(`${API}/jobs/${id}/transcript`).then((x) => x.json()).catch(() => null);
          if (t?.segments) {
            setTranscript(t.segments);
            setEdited(Object.fromEntries(t.segments.map((s: Seg) => [s.index, s.target])));
          }
        }
        if (j.status === "done" || j.status === "failed") break;
      } catch {
        setConnError("Se perdió la conexión con el backend.");
        break;
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    setBusy(false);
  }

  async function applyTranslation() {
    if (!job) return;
    const overrides: Record<string, string> = {};
    for (const s of transcript) {
      const v = edited[s.index];
      if (v != null && v !== s.target) overrides[String(s.index)] = v;
    }
    setBusy(true);
    setConnError(null);
    try {
      const res = await fetch(`${API}/jobs/${job.id}/apply_translation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ overrides }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        setConnError(err.detail || `error ${res.status}`);
        setBusy(false);
        return;
      }
      setJob({ ...job, status: "running" });
      setTranscript([]);
      setEdited({});
      poll(job.id);
    } catch {
      setConnError("No se pudo aplicar la edición.");
      setBusy(false);
    }
  }

  const failed = job?.status === "failed";
  const done = job?.status === "done";

  return (
    <div className="relative min-h-screen flex flex-col">
      <div className="aurora-bg" />
      <div className="relative z-10 flex flex-col min-h-screen">
        <motion.header
          initial={{ y: -20, opacity: 0 }}
          animate={{ y: 0, opacity: 1 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="flex items-center justify-between px-5 py-3 glass border-b border-white/10"
        >
          <span className="text-xl font-bold gradient-text tracking-tight">VoxDub</span>
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.96 }}
            onClick={() => setShowLegal(true)}
            className="px-3 py-1.5 rounded-lg border border-white/15 text-xs text-white/70 hover:text-white"
          >
            Términos de uso
          </motion.button>
        </motion.header>

        <AnimatePresence>
          {connError && (
            <motion.div
              initial={{ opacity: 0, height: 0 }}
              animate={{ opacity: 1, height: "auto" }}
              exit={{ opacity: 0, height: 0 }}
              className="bg-red-900/50 text-red-200 text-sm px-4 py-2 border-b border-red-700/50"
            >
              {connError}
            </motion.div>
          )}
          {failed && job?.error && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-red-900/50 text-red-200 text-sm px-4 py-2 border-b border-red-700/50"
            >
              Falló el proceso: {job.error}
            </motion.div>
          )}
          {job?.warning && (
            <motion.div
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              className="bg-amber-900/50 text-amber-200 text-sm px-4 py-2 border-b border-amber-700/50"
            >
              Aviso: {job.warning}
            </motion.div>
          )}
        </AnimatePresence>

        {!backendReady && !connecting && (
          <div className="bg-red-900/50 text-red-200 text-sm px-4 py-2 border-b border-red-700/50">
            El motor de VoxDub no responde. Si estás en la app de escritorio, esperá unos segundos; si persiste, reiniciá la aplicación.
          </div>
        )}

        <motion.div
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex gap-2 p-3 glass border-b border-white/10 flex-wrap"
        >
          {STAGES.map((st) => {
            const cur = job?.stages.find((s) => s.name === st);
            const active = cur?.status === "running";
            return (
              <motion.div
                key={st}
                animate={active ? { opacity: [0.6, 1, 0.6] } : { opacity: 1 }}
                transition={active ? { repeat: Infinity, duration: 1.4 } : {}}
                className="px-3 py-1 rounded-full border border-white/10 text-sm bg-white/5"
              >
                <span className="text-white/50">{st}</span>
                <span className={`ml-2 font-mono text-xs ${statusColor(cur?.status || "")}`}>
                  {cur ? STATUS[cur.status] : STATUS["pending"]}
                </span>
                {cur?.engine && (
                  <span className={`ml-1 text-[10px] px-1 rounded ${
                    cur.engine === "mock" ? "bg-white/10 text-white/40" : "bg-cyan-500/20 text-cyan-300"
                  }`}>{cur.engine}</span>
                )}
              </motion.div>
            );
          })}
        </motion.div>

        <div className="flex-1 grid grid-cols-3 gap-3 p-4">
          <motion.div
            initial={{ opacity: 0, x: -16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.1 }}
            className="col-span-1 glass rounded-2xl p-4 text-sm space-y-4"
          >
            <p className="text-white/60 text-xs uppercase tracking-widest">Configurar</p>
            <div className="flex gap-2">
              <motion.button whileTap={{ scale: 0.96 }} onClick={() => setMode("file")}
                className={`px-3 py-1.5 rounded-lg text-xs ${mode === "file" ? "btn-primary text-white" : "border border-white/15 text-white/70"}`}>
                Subir archivo
              </motion.button>
              <motion.button whileTap={{ scale: 0.96 }} onClick={() => setMode("url")}
                className={`px-3 py-1.5 rounded-lg text-xs ${mode === "url" ? "btn-primary text-white" : "border border-white/15 text-white/70"}`}>
                Desde enlace
              </motion.button>
            </div>

            {job?.detected_languages && job.detected_languages.length > 0 && (
              <p className="text-cyan-300 text-[11px]">
                Idioma(s) detectado(s):{" "}
                {job.detected_languages.map((l: string) => LANG_NAMES[l] || l).join(", ")}
                {" "}→ se traduce al idioma elegido arriba (por defecto Español).
              </p>
            )}

            {mode === "file" ? (
              <input type="file" accept="video/*" onChange={(e) => {
                const f = e.target.files?.[0] || null;
                setFile(f);
                setFilePreview(f ? URL.createObjectURL(f) : null);
              }} className="text-xs" disabled={busy} />
            ) : (
              <input type="url" placeholder="https://.../video.mp4" value={url} onChange={(e) => setUrl(e.target.value)}
                className="w-full bg-black/30 border border-white/15 rounded-lg px-3 py-2 text-sm outline-none focus:border-cyan-400/60" disabled={busy} />
             )}
            {mode === "file" && filePreview && (
              <video src={filePreview} controls className="w-full rounded-lg mt-1 max-h-44 bg-black/40" />
            )}

            <div>
              <label className="text-white/50 text-xs">Idioma destino</label>
              <select className="w-full bg-black/30 border border-white/15 rounded-lg px-3 py-2 text-sm outline-none focus:border-cyan-400/60" value={lang} onChange={(e) => setLang(e.target.value)} disabled={busy}>
                <option value="es">Español</option><option value="en">Inglés</option><option value="fr">Francés</option>
                <option value="de">Alemán</option><option value="it">Italiano</option><option value="pt">Portugués</option>
                <option value="ru">Ruso</option><option value="ja">Japonés</option><option value="zh">Chino</option><option value="ko">Coreano</option><option value="ar">Árabe</option>
              </select>
            </div>
            <div>
              <label className="text-white/50 text-xs">Idioma origen (opcional, mejora la IA)</label>
              <select className="w-full bg-black/30 border border-white/15 rounded-lg px-3 py-2 text-sm outline-none focus:border-cyan-400/60" value={srcLang} onChange={(e) => setSrcLang(e.target.value)} disabled={busy}>
                <option value="">Auto (detectar)</option><option value="es">Español</option><option value="en">Inglés</option>
                <option value="fr">Francés</option><option value="de">Alemán</option><option value="it">Italiano</option>
                <option value="pt">Portugués</option><option value="ru">Ruso</option><option value="ja">Japonés</option>
                <option value="zh">Chino</option><option value="ko">Coreano</option><option value="ar">Árabe</option>
              </select>
            </div>
            <div>
              <label className="text-white/50 text-xs">Estilo de voz</label>
              <select className="w-full bg-black/30 border border-white/15 rounded-lg px-3 py-2 text-sm outline-none focus:border-cyan-400/60" value={voice} onChange={(e) => setVoice(e.target.value)} disabled={busy}>
                <option value="default">Por defecto (según género)</option>
                <option value="ia-voice-female-01">Femenina</option>
                <option value="ia-voice-male-01">Masculina</option>
              </select>
            </div>
            <div>
              <label className="text-white/50 text-xs">Modo de IA</label>
              <div className="flex gap-2 mt-1 flex-wrap">
                <motion.button whileTap={{ scale: 0.96 }} onClick={() => setAimode("mock")}
                  className={`px-2 py-1 rounded-lg text-xs ${aimode === "mock" ? "btn-primary text-white" : "border border-white/15 text-white/70"}`}>
                  Mock local
                </motion.button>
                <motion.button whileTap={{ scale: 0.96 }} onClick={() => setAimode("free")}
                  className={`px-2 py-1 rounded-lg text-xs ${aimode === "free" ? "btn-primary text-white" : "border border-white/15 text-white/70"}`}>
                  IA gratuita (nube)
                </motion.button>
                <motion.button whileTap={{ scale: 0.96 }} onClick={() => setAimode("real")}
                  className={`px-2 py-1 rounded-lg text-xs ${aimode === "real" ? "btn-primary text-white" : "border border-white/15 text-white/70"}`}
                  disabled={!realAsrAvailable}
                  title={!realAsrAvailable ? "ASR real no disponible (faster-whisper no instalado)" : undefined}
                >
                  Real (ASR local + nube)
                </motion.button>
              </div>
              <p className="text-white/40 text-[11px] mt-1">
                {aimode === "real"
                  ? "ASR real con Whisper local (detecta el idioma hablado). Traduce y habla con IA gratuita en la nube (MyMemory + edge-tts). Requiere descargar el modelo Whisper la 1ª vez."
                  : aimode === "free"
                  ? "Traducción MyMemory + voz edge-tts (ambas gratuitas, sin clave)."
                  : "Todo simulado offline (texto y audio de ejemplo)."}
              </p>
            </div>
            <label className="flex items-center gap-2 text-xs text-white/70">
              <input type="checkbox" checked={burn} onChange={(e) => setBurn(e.target.checked)} disabled={busy} />
              Quemar subtítulos en el video (hardsub)
            </label>

            {(connecting && !backendReady) && (
              <p className="text-indigo-300 text-[11px]">Iniciando el motor de VoxDub…</p>
            )}
            {!accepted && (
              <p className="text-amber-300 text-[11px]">Aceptá los términos de uso (arriba a la derecha) para empezar.</p>
            )}
            <motion.button
              whileHover={{ scale: 1.03 }}
              whileTap={{ scale: 0.97 }}
              disabled={busy || !backendReady || !accepted || (mode === "file" ? !file : !url.trim())}
              onClick={start}
              className="w-full px-4 py-2.5 rounded-xl btn-primary text-white text-sm font-medium disabled:opacity-40"
            >
              {busy ? "Procesando…" : "Traducir y doblar"}
            </motion.button>
            {busy && job && job.status === "running" && (
              <button onClick={cancelJob} className="px-3 py-1.5 rounded-lg border border-red-400/40 text-xs text-red-300 hover:bg-red-500/10">Cancelar</button>
            )}
            {(done || failed) && (
              <button onClick={reset} className="px-3 py-1.5 rounded-lg border border-white/15 text-xs text-white/70">Nuevo video</button>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, scale: 0.98 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ delay: 0.15 }}
            className="col-span-1 glass rounded-2xl flex items-center justify-center overflow-hidden bg-black/40"
          >
            {done && job?.output ? (
              <video src={`${API}/jobs/${job.id}/download`} controls className="max-h-full w-full" />
            ) : (
              <span className="text-white/40 text-sm">Preview del video</span>
            )}
          </motion.div>

          <motion.div
            initial={{ opacity: 0, x: 16 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: 0.2 }}
            className="col-span-1 glass rounded-2xl p-4 text-sm"
          >
            <p className="text-white/60 text-xs uppercase tracking-widest mb-2">Estado</p>
            {job ? (
              <ul className="space-y-1 font-mono text-xs">
                {job.stages.map((s) => (
                  <li key={s.name} className={statusColor(s.status)}>{s.name}: {STATUS[s.status] || s.status}</li>
                ))}
                {done && job.output && (
                  <li><a className="text-cyan-300 hover:underline" href={`${API}/jobs/${job.id}/download`}>Descargar .mp4</a></li>
                )}
                {done && job.subtitles && (
                  <li className="flex gap-3">
                    <a className="text-cyan-300 hover:underline" href={`${API}/jobs/${job.id}/subtitles?srt`}>.srt</a>
                    <a className="text-cyan-300 hover:underline" href={`${API}/jobs/${job.id}/subtitles?vtt`}>.vtt</a>
                  </li>
                )}
              </ul>
            ) : (
              <p className="text-white/40">Elegí un video o enlace para empezar.</p>
            )}
          </motion.div>
        </div>

        <AnimatePresence>
          {job && transcript.length > 0 && (
            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 30 }}
              className="glass border-t border-white/10 p-4"
            >
              <div className="flex items-center justify-between mb-3">
                <p className="text-sm font-semibold text-white/80">Transcripción y traducción <span className="text-white/40 font-normal">(revisá y editá antes de regenerar)</span></p>
                <motion.button whileHover={{ scale: 1.03 }} whileTap={{ scale: 0.97 }} onClick={applyTranslation} disabled={busy}
                  className="px-3 py-1.5 rounded-xl btn-primary text-white text-xs disabled:opacity-40">Aplicar y regenerar</motion.button>
              </div>
              <div className="space-y-2 max-h-72 overflow-auto pr-1">
                {transcript.map((s) => (
                  <div key={s.index} className="grid grid-cols-[70px_1fr_1fr] gap-3 text-xs">
                    <span className="text-white/40 pt-1">{fmt(s.start)}–{fmt(s.end)}</span>
                    <div>
                      <p className="text-white/40">Original</p>
                      <p className="text-white/70">{s.source}</p>
                    </div>
                    <div>
                      <p className="text-white/40">Traducido</p>
                      <textarea className="w-full bg-black/30 border border-white/15 rounded-lg px-2 py-1 text-white/90 outline-none focus:border-cyan-400/60" value={edited[s.index] ?? s.target} onChange={(e) => setEdited({ ...edited, [s.index]: e.target.value })} rows={2} />
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      <AnimatePresence>
        {showLegal && (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70"
            onClick={() => setShowLegal(false)}
          >
            <motion.div
              initial={{ scale: 0.92, y: 20 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.92, y: 20 }}
              onClick={(e) => e.stopPropagation()}
              className="glass rounded-2xl max-w-lg w-full p-6 text-sm space-y-3 max-h-[85vh] overflow-auto"
            >
              <h2 className="text-xl font-bold gradient-text">{TERMS.title}</h2>
              <p className="text-white/70">{TERMS.responsible_use}</p>
              <ul className="list-disc pl-5 space-y-1 text-white/70">
                {TERMS.rules.map((r, i) => <li key={i}>{r}</li>)}
              </ul>
              <p className="text-red-300/80 text-xs">{TERMS.disclaimer}</p>
              <div className="flex justify-end gap-2 pt-2">
                <motion.button whileTap={{ scale: 0.96 }} onClick={() => { setAccepted(true); if (typeof localStorage !== "undefined") localStorage.setItem("voxdub_accepted", "1"); setShowLegal(false); }}
                  className="px-3 py-1.5 rounded-xl btn-primary text-white text-xs">Entendido, soy responsable</motion.button>
                <button onClick={() => setShowLegal(false)} className="px-3 py-1.5 rounded-xl border border-white/15 text-xs text-white/70">Cerrar</button>
              </div>
              {accepted && <p className="text-cyan-300 text-xs">✔ Términos aceptados en este dispositivo.</p>}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
