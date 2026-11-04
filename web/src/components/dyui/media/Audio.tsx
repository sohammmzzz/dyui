import { useEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Pause, Play, Volume2, VolumeX } from "lucide-react";
import { dur, ease } from "../../../lib/motion";
import { Bloom } from "../util/motion";
import { hash, optStr, safeMediaUrl } from "../util/props";
import type { DyProps } from "../util/types";
import "../styles/media.css";

const BARS = 64;
const clock = (s: number) => {
  if (!Number.isFinite(s) || s < 0) return "0:00";
  const m = Math.floor(s / 60);
  return `${m}:${String(Math.floor(s % 60)).padStart(2, "0")}`;
};

/** `audio` — a calm custom player with a deterministic waveform scrubber. */
export function Audio({ node }: DyProps) {
  const p = node.props;
  const src = safeMediaUrl(p.src ?? p.url);
  const title = optStr(p.title) ?? (src ? decodeURIComponent(src.split("/").pop()?.split("?")[0] ?? "") : "") ?? "Audio";
  const ref = useRef<HTMLAudioElement>(null);
  const wave = useRef<HTMLDivElement>(null);
  const [playing, setPlaying] = useState(false);
  const [t, setT] = useState(0);
  const [d, setD] = useState(0);
  const [muted, setMuted] = useState(false);
  const [error, setError] = useState(false);
  const bars = useMemo(() => {
    const h = hash(src ?? title);
    return Array.from({ length: BARS }, (_, i) => {
      const x = i / BARS;
      const v = 0.5 + 0.28 * Math.sin(x * 9 + (h % 7)) + 0.18 * Math.sin(x * 23 + (h % 13)) + 0.12 * Math.sin(x * 51 + (h % 5));
      const env = Math.min(1, x * 6, (1 - x) * 5);
      return Math.max(0.16, Math.min(1, v * (0.55 + 0.45 * env)));
    });
  }, [src, title]);

  useEffect(() => {
    if (!playing) return;
    let raf = 0;
    const tick = () => {
      const a = ref.current;
      if (a) setT(a.currentTime);
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [playing]);

  const toggle = () => {
    const a = ref.current;
    if (!a || error) return;
    if (a.paused) a.play().catch(() => setError(true));
    else a.pause();
  };
  const seekTo = (frac: number) => {
    const a = ref.current;
    if (!a || !d) return;
    a.currentTime = Math.max(0, Math.min(d, frac * d));
    setT(a.currentTime);
  };
  const onPointer = (e: PointerEvent<HTMLDivElement>) => {
    if (e.type === "pointermove" && e.buttons !== 1) return;
    const r = wave.current!.getBoundingClientRect();
    seekTo((e.clientX - r.left) / r.width);
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    const a = ref.current;
    if (!a) return;
    if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
      e.preventDefault();
      a.currentTime = Math.max(0, Math.min(d, a.currentTime + (e.key === "ArrowRight" ? 5 : -5)));
      setT(a.currentTime);
    } else if (e.key === " " || e.key === "Enter") {
      e.preventDefault();
      toggle();
    }
  };
  const progress = d ? t / d : 0;
  return (
    <Bloom className="dy-c dy-audio dy-panel" data-dy-ui="audio" data-playing={playing || undefined}>
      <button type="button" className="dy-audio-play" onClick={toggle} aria-label={playing ? "Pause" : "Play"} disabled={!src || error}>
        <AnimatePresence initial={false} mode="popLayout">
          <motion.span key={playing ? "pause" : "play"} initial={{ opacity: 0, scale: 0.6 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.6 }} transition={{ duration: dur[2], ease }} style={{ display: "inline-flex" }}>
            {playing ? <Pause width={17} height={17} fill="currentColor" strokeWidth={0} /> : <Play width={17} height={17} fill="currentColor" strokeWidth={0} style={{ marginLeft: 2 }} />}
          </motion.span>
        </AnimatePresence>
      </button>
      <div className="dy-audio-main">
        <div className="dy-audio-top">
          <span className="dy-audio-title dy-ellipsis">{title || "Audio"}</span>
          <span className="dy-audio-time">{error ? "Unavailable" : `${clock(t)} / ${clock(d)}`}</span>
        </div>
        <div
          ref={wave}
          className="dy-audio-wave"
          role="slider"
          tabIndex={src ? 0 : -1}
          aria-label="Seek"
          aria-valuemin={0}
          aria-valuemax={Math.round(d)}
          aria-valuenow={Math.round(t)}
          aria-valuetext={`${clock(t)} of ${clock(d)}`}
          onPointerDown={onPointer}
          onPointerMove={onPointer}
          onKeyDown={onKey}
        >
          {bars.map((h, i) => (
            <span key={i} className="dy-audio-bar" data-played={i / BARS < progress || undefined} style={{ height: `${h * 100}%`, ["--j" as any]: i }} />
          ))}
        </div>
      </div>
      <button type="button" className="dy-btn dy-btn--ghost dy-btn--icon dy-audio-mute" onClick={() => { const a = ref.current; if (a) { a.muted = !a.muted; setMuted(a.muted); } }} aria-label={muted ? "Unmute" : "Mute"}>
        {muted ? <VolumeX /> : <Volume2 />}
      </button>
      {src && (
        <audio
          ref={ref}
          src={src}
          preload="metadata"
          onLoadedMetadata={(e) => setD(e.currentTarget.duration)}
          onDurationChange={(e) => setD(e.currentTarget.duration)}
          onPlay={() => setPlaying(true)}
          onPause={() => setPlaying(false)}
          onEnded={() => setPlaying(false)}
          onTimeUpdate={(e) => !playing && setT(e.currentTarget.currentTime)}
          onError={() => setError(true)}
        />
      )}
    </Bloom>
  );
}
