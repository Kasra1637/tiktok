import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { LazyHeroVideo } from "./LazyHeroVideo";
import { GroupLabel } from "./SectionCard";
import { Play, RotateCcw, Check, Film } from "lucide-react";

/**
 * Hypothetical processing demo — NOT a render.
 *
 * A front-end-only simulation that shows what happens AFTER the four wizard
 * steps, for founders (and demos) that cannot or should not spend a real
 * render yet. It never calls the API, never touches `_submit_generation`,
 * and never produces a file: the "clip" below is a mock frame with a
 * timeline, not a video element with a source.
 *
 * Labelled hypothetical at every state so it can never be mistaken for the
 * real render above it. The real Generate button stays the only path to a
 * video.
 */
const STAGES = [
  { key: "lock", label: "Locking your approved script" },
  { key: "render", label: "Rendering hook + story in one pass" },
  { key: "stitch", label: "Stitching one clip" },
];

function prefersReducedMotion() {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function HypotheticalProcessing({ pieceSeconds = 12, modelName = "" }) {
  const [phase, setPhase] = useState("idle");
  const [stageIndex, setStageIndex] = useState(0);
  const timers = useRef([]);

  const clearTimers = useCallback(() => {
    timers.current.forEach((t) => window.clearTimeout(t));
    timers.current = [];
  }, []);

  useEffect(() => clearTimers, [clearTimers]);

  const start = useCallback(() => {
    clearTimers();
    if (prefersReducedMotion()) {
      setStageIndex(STAGES.length - 1);
      setPhase("done");
      return;
    }
    setPhase("running");
    setStageIndex(0);
    STAGES.forEach((_, i) => {
      if (i === 0) return;
      timers.current.push(
        window.setTimeout(() => setStageIndex(i), i * 1700)
      );
    });
    timers.current.push(
      window.setTimeout(() => setPhase("done"), STAGES.length * 1700)
    );
  }, [clearTimers]);

  const reset = useCallback(() => {
    clearTimers();
    setPhase("idle");
    setStageIndex(0);
  }, [clearTimers]);

  const progress =
    phase === "done"
      ? 100
      : phase === "running"
        ? Math.round(((stageIndex + 1) / (STAGES.length + 1)) * 100)
        : 0;


  return (
    <div
      className="space-y-3 border-t border-dashed border-[color:var(--hairline-strong)] pt-3"
      data-testid="hypothetical-processing"
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={Film}>Hypothetical demo — not a render</GroupLabel>
        <Badge variant="outline" className="text-xs">
          No video is generated
        </Badge>
      </div>
      <p className="text-sm text-muted-foreground">
        A front-end preview only. Nothing renders, nothing is billed.
      </p>

      {phase === "idle" && (
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" size="sm" onClick={start} data-testid="hypothetical-start">
            <Play className="h-3.5 w-3.5" /> Show hypothetical processing
          </Button>
        </div>
      )}

      {phase === "running" && (
        <div className="space-y-3" aria-live="polite">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm font-semibold">{STAGES[stageIndex].label}…</p>
            <span className="text-xs text-muted-foreground">{progress}%</span>
          </div>
          <div
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={progress}
            aria-label="Hypothetical processing progress"
            className="h-2 w-full overflow-hidden rounded-full bg-[color:var(--indigo-8)]"
          >
            <div
              className="h-full rounded-full bg-gradient-to-r from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] transition-[width] duration-500"
              style={{ width: `${progress}%` }}
            />
          </div>
          <ul className="space-y-1.5">
            {STAGES.map((s, i) => (
              <li
                key={s.key}
                className={`animate-fade-up flex items-center gap-2 text-xs ${
                  i < stageIndex
                    ? "text-muted-foreground"
                    : i === stageIndex
                      ? "font-semibold text-foreground"
                      : "text-muted-foreground"
                }`}
                style={{ animationDelay: `${i * 60}ms` }}
              >
                {i < stageIndex ? (
                  <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
                ) : (
                  <span
                    aria-hidden="true"
                    className={`h-2 w-2 rounded-full ${
                      i === stageIndex
                        ? "bg-[color:var(--brand-indigo)]"
                        : "border border-current opacity-40"
                    }`}
                  />
                )}
                {s.label}
                {i === stageIndex ? "…" : ""}
              </li>
            ))}
          </ul>
          <div className="flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={reset}>
              Cancel preview
            </Button>
          </div>
        </div>
      )}

      {phase === "done" && (
        <div className="space-y-3" aria-live="polite">
          {/* Clean interface mock: the recorded wizard + Demo CTA canvas in a
              portrait frame that matches the capture, so the whole interface
              shows with no cropping. No app header, footer, or browser chrome
              inside the video — playback runs at 8x. */}
          <div className="mx-auto w-full max-w-[300px] overflow-hidden rounded-xl border border-[color:var(--hairline-strong)] bg-black">
            <div className="relative aspect-[9/13] w-full">
              <LazyHeroVideo
                className="absolute inset-0 block h-full w-full object-contain"
                poster={`${process.env.PUBLIC_URL}/hero-demo-poster.jpg`}
                sources={[
                  { src: `${process.env.PUBLIC_URL}/hero-demo.webm`, type: "video/webm" },
                  { src: `${process.env.PUBLIC_URL}/hero-demo.mp4`, type: "video/mp4" },
                ]}
                ariaLabel="Hypothetical preview at 8x speed: the Create Video wizard interface and the Demo CTA canvas, full interface"
              />
              <span className="absolute left-2 top-2 rounded-full border border-[color:var(--hairline-strong)] bg-black/60 px-2 py-0.5 text-xs font-semibold text-white">
                0:{String(pieceSeconds).padStart(2, "0")} hypothetical{modelName ? ` · ${modelName}` : ""}
              </span>
              <span className="absolute inset-x-0 bottom-0 bg-black/60 px-2 py-1 text-center text-xs font-semibold uppercase tracking-wide text-white">
                Hypothetical — not a real render
              </span>
            </div>
          </div>

          <div className="space-y-3">
              <ul className="space-y-1.5">
                {[
                  "Hook & middle in one clip",
                  "Demo footage & CTA stay yours to attach",
                ].map((line, i) => (
                  <li
                    key={line}
                    className="animate-fade-up flex gap-2 text-xs text-muted-foreground"
                    style={{ animationDelay: `${i * 70}ms` }}
                  >
                    <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>

              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" onClick={start} data-testid="hypothetical-replay">
                  <RotateCcw className="h-3.5 w-3.5" /> Replay simulation
                </Button>
                <Button variant="ghost" size="sm" onClick={reset}>
                  Dismiss preview
                </Button>
              </div>
            </div>
        </div>
      )}
    </div>
  );
}

export default HypotheticalProcessing;
