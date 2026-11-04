import { clipWindow, formatTime, MIN_CLIP_SECONDS } from "./constants";
import { Button } from "../components/ui/button";

/**
 * The ruler under a track, drawn in source time: a hairline with one tick per
 * whole second, labelled every five. Pure presentation — it reads the clip
 * duration, never the playhead, so it cannot contradict the seek strip below.
 */
function Ruler({ duration }) {
  if (!Number.isFinite(duration) || duration <= 0) return null;
  const count = Math.floor(duration);
  const labels = [0];
  for (let s = 5; s <= count; s += 5) labels.push(s);
  const endLabel = Number.isInteger(duration) ? null : formatTime(duration);
  return (
    <div aria-hidden="true" className="relative h-4 select-none">
      {Array.from({ length: count + 1 }, (_, s) => (
        <span
          key={s}
          className={`absolute top-2 w-px -translate-x-1/2 ${s % 5 === 0 ? "h-2 bg-muted-foreground/40" : "h-1 bg-muted-foreground/20"}`}
          style={{ left: `${(s / duration) * 100}%` }}
        />
      ))}
      {labels.map((s) => (
        <span
          key={`label-${s}`}
          className="absolute top-0 -translate-x-1/2 font-mono text-[0.6875rem] leading-none text-muted-foreground"
          style={{ left: `${Math.min(100, Math.max(0, (s / duration) * 100))}%` }}
        >
          {s}s
        </span>
      ))}
      {endLabel && (
        <span
          className="absolute right-0 top-0 font-mono text-[0.6875rem] leading-none text-muted-foreground"
          style={{ transform: "none" }}
        >
          {endLabel}
        </span>
      )}
    </div>
  );
}

/** Compact source-space trim tracks; the existing seek strip owns output time. */
export function TrimTimeline({ clips, onTrim, disabled }) {
  const visible = clips.filter((clip) => clip.duration > 0);
  if (visible.length === 0) return null;
  return <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid="trim-timeline" aria-label="Clip timeline">
    {visible.map((clip) => {
      const run = clipWindow(clip.duration, clip.start, undefined, clip.end);
      const minimum = Math.min(MIN_CLIP_SECONDS, clip.duration);
      const change = (edge, value) => onTrim(clip.id, edge === "start" ? value : run.start, edge === "end" ? value : run.end);
      const keptPct = `${run.duration / clip.duration * 100}%`;
      const cutPct = `${run.start / clip.duration * 100}%`;
      const atStart = run.start <= 0.001;
      const atEnd = run.end >= clip.duration - 0.001;
      const trimmed = !atStart || !atEnd;
      return <div key={clip.id} className="inset-panel space-y-2.5" data-testid={`${clip.id}-trim-track`}>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-semibold">{clip.label}</span>
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${trimmed ? "bg-[color:var(--indigo-15)] text-[color:var(--brand-indigo)]" : "bg-secondary/60 text-muted-foreground"}`}>
            {run.duration.toFixed(1)}s kept
          </span>
        </div>
        <Ruler duration={clip.duration} />
        <div className="relative h-2.5 overflow-hidden rounded-full border border-[color:var(--hairline)] bg-secondary/40" role="img" aria-label={`${clip.label}: keeping ${run.duration.toFixed(1)} seconds from ${formatTime(run.start)} to ${formatTime(run.end)}`}>
          <span className="absolute inset-y-0 rounded-full bg-[color:var(--brand-indigo)]" style={{ left: cutPct, width: keptPct }} />
          <span className="absolute inset-y-0 left-0 w-0.5 bg-[color:var(--hairline-strong)]" style={{ left: `calc(${cutPct} - 1px)`, opacity: atStart ? 0 : 1 }} />
          <span className="absolute inset-y-0 w-0.5 bg-[color:var(--hairline-strong)]" style={{ left: `calc(${cutPct} + ${keptPct} - 1px)`, opacity: atEnd ? 0 : 1 }} />
        </div>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          {["start", "end"].map((edge) => <label key={edge} className="flex min-w-0 items-center gap-2 text-sm text-muted-foreground">
            <span>{edge === "start" ? "In" : "Out"}</span>
            <input type="range" className="tap-chip block min-h-8 w-24 min-w-24 accent-[color:var(--brand-indigo)]" disabled={disabled}
              aria-label={`${clip.label} ${edge} trim`} data-testid={`${clip.id}-trim-${edge}`}
              min={edge === "start" ? 0 : run.start + minimum} max={edge === "start" ? run.end - minimum : clip.duration}
              step="0.01" value={edge === "start" ? run.start : run.end}
              onChange={(event) => change(edge, Number(event.target.value))} />
            <span className="rounded-lg bg-secondary/60 px-2.5 py-1 font-mono text-xs tabular-nums text-foreground">
              {formatTime(edge === "start" ? run.start : run.end)}
            </span>
          </label>)}
          {trimmed && <Button type="button" className="tap-chip ml-auto" size="sm" variant="ghost" disabled={disabled} onClick={() => onTrim(clip.id, 0, null)}>Reset</Button>}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button className="tap-chip" size="sm" variant="ghost" disabled={disabled || !clip.active} onClick={() => onTrim(clip.id, Math.min(run.end - minimum, Math.max(0, clip.playhead)), run.end)}>In at playhead</Button>
          <Button className="tap-chip" size="sm" variant="ghost" disabled={disabled || !clip.active} onClick={() => onTrim(clip.id, run.start, Math.min(clip.duration, Math.max(run.start + minimum, clip.playhead)))}>Out at playhead</Button>
          <Button className="tap-chip" size="sm" variant="ghost" disabled={disabled} onClick={() => onTrim(clip.id, 0, null)}>Full clip</Button>
        </div>
      </div>;
    })}
  </div>;
}
