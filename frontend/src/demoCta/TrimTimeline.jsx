import { clipWindow, formatTime, MIN_CLIP_SECONDS } from "./constants";
import { Button } from "../components/ui/button";

/** Compact source-space trim tracks; the existing seek strip owns output time. */
export function TrimTimeline({ clips, onTrim, disabled }) {
  return <div className="space-y-3 border-t border-[color:var(--hairline)] pt-3" data-testid="trim-timeline" aria-label="Clip timeline">
    {clips.filter((clip) => clip.duration > 0).map((clip) => {
      const run = clipWindow(clip.duration, clip.start, undefined, clip.end);
      const minimum = Math.min(MIN_CLIP_SECONDS, clip.duration);
      const change = (edge, value) => onTrim(clip.id, edge === "start" ? value : run.start, edge === "end" ? value : run.end);
      return <div key={clip.id} className="space-y-2" data-testid={`${clip.id}-trim-track`}>
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-semibold">{clip.label}</span>
          <span className="font-mono text-xs tabular-nums">{formatTime(run.start)} → {formatTime(run.end)} · {run.duration.toFixed(1)}s</span>
        </div>
        <div className="relative h-2 overflow-hidden rounded-full bg-secondary" aria-hidden="true">
          <span className="absolute inset-y-0 bg-[color:var(--brand-indigo)]" style={{ left: `${run.start / clip.duration * 100}%`, width: `${run.duration / clip.duration * 100}%` }} />
        </div>
        <div className="grid grid-cols-2 gap-3">
          {["start", "end"].map((edge) => <label key={edge} className="space-y-1 text-sm text-muted-foreground">
            <span>{edge === "start" ? "In" : "Out"}</span>
            <input type="range" className="block min-h-8 w-full accent-[color:var(--brand-indigo)]" disabled={disabled}
              aria-label={`${clip.label} ${edge} trim`} data-testid={`${clip.id}-trim-${edge}`}
              min={edge === "start" ? 0 : run.start + minimum} max={edge === "start" ? run.end - minimum : clip.duration}
              step="0.01" value={edge === "start" ? run.start : run.end}
              onChange={(event) => change(edge, Number(event.target.value))} />
          </label>)}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="ghost" disabled={disabled || !clip.active} onClick={() => onTrim(clip.id, Math.min(run.end - minimum, Math.max(0, clip.playhead)), run.end)}>In at playhead</Button>
          <Button size="sm" variant="ghost" disabled={disabled || !clip.active} onClick={() => onTrim(clip.id, run.start, Math.min(clip.duration, Math.max(run.start + minimum, clip.playhead)))}>Out at playhead</Button>
          <Button size="sm" variant="ghost" disabled={disabled} onClick={() => onTrim(clip.id, 0, null)}>Full clip</Button>
        </div>
      </div>;
    })}
  </div>;
}
