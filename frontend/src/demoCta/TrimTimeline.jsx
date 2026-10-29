import { clipWindow, formatTime, MIN_CLIP_SECONDS } from "./constants";
import { Button } from "../components/ui/button";

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
      return <div key={clip.id} className="inset-panel space-y-2.5" data-testid={`${clip.id}-trim-track`}>
        <div className="flex items-baseline justify-between gap-2">
          <span className="text-sm font-semibold">{clip.label}</span>
          <span className="font-mono text-xs tabular-nums text-muted-foreground">{formatTime(run.start)} → {formatTime(run.end)} · {run.duration.toFixed(1)}s</span>
        </div>
        <div className="relative h-2 overflow-hidden rounded-full bg-secondary" role="img" aria-label={`${clip.label}: keeping ${run.duration.toFixed(1)} seconds from ${formatTime(run.start)} to ${formatTime(run.end)}`}>
          <span className="absolute inset-y-0 rounded-full bg-[color:var(--brand-indigo)]" style={{ left: cutPct, width: keptPct }} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {["start", "end"].map((edge) => <label key={edge} className="space-y-1 text-sm text-muted-foreground">
            <span className="flex items-baseline justify-between gap-2">
              <span>{edge === "start" ? "In" : "Out"}</span>
              <span className="font-mono text-xs tabular-nums">{formatTime(edge === "start" ? run.start : run.end)}</span>
            </span>
            <input type="range" className="tap-chip block min-h-8 w-full accent-[color:var(--brand-indigo)]" disabled={disabled}
              aria-label={`${clip.label} ${edge} trim`} data-testid={`${clip.id}-trim-${edge}`}
              min={edge === "start" ? 0 : run.start + minimum} max={edge === "start" ? run.end - minimum : clip.duration}
              step="0.01" value={edge === "start" ? run.start : run.end}
              onChange={(event) => change(edge, Number(event.target.value))} />
          </label>)}
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
