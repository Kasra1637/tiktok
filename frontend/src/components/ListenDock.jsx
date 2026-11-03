import { Pause, Play, X } from "lucide-react";
import { useEffect, useState } from "react";
import {
  LISTEN_RATES,
  listenState,
  pause,
  resume,
  setRate,
  speechSupported,
  stop,
  subscribe,
} from "../lib/listen";

const ICON_BUTTON =
  "pill-studio tap-chip flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:text-foreground";

/**
 * The one voice bar for the whole session: what is playing, pause/resume,
 * stop, and the speed switch. It exists only while something is playing (or
 * while an error needs naming) and unmounts on settle *and* on error — no
 * chrome lives on the page after the voice stops.
 *
 * Positioned against the sidebar via `--app-sidebar-w` (published by AppShell)
 * so it centres on the content, not the window, exactly like other fixed
 * chrome in this app.
 */
export function ListenDock() {
  const supported = speechSupported();
  const [state, setState] = useState(() => listenState());

  useEffect(() => subscribe(setState), []);

  if (!supported) return null;
  if (state.status === "idle" && !state.error) return null;

  return (
    <div
      data-testid="listen-dock"
      role="status"
      aria-live="polite"
      className="fixed bottom-4 z-40 flex items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-card/95 px-3 py-1.5 shadow-[var(--shadow-lg)] backdrop-blur-xl"
      style={{
        left: "calc(50% + (var(--app-sidebar-w, 0px) / 2))",
        transform: "translateX(-50%)",
      }}
    >
      {state.error ? (
        <>
          <span className="max-w-[320px] truncate text-sm text-destructive" title={state.error}>
            {state.error}
          </span>
          <button type="button" onClick={stop} aria-label="Dismiss voice message" className={ICON_BUTTON}>
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        </>
      ) : (
        <>
          <span className="max-w-[220px] truncate text-sm" data-testid="listen-dock-label">
            Listening — {state.label || "this page"}
          </span>
          <button
            type="button"
            onClick={state.status === "paused" ? resume : pause}
            aria-label={state.status === "paused" ? "Resume reading" : "Pause reading"}
            data-testid="listen-dock-pause"
            className={ICON_BUTTON}
          >
            {state.status === "paused" ? (
              <Play aria-hidden="true" className="h-3.5 w-3.5" />
            ) : (
              <Pause aria-hidden="true" className="h-3.5 w-3.5" />
            )}
          </button>
          <div className="flex items-center gap-0.5" role="group" aria-label="Reading speed">
            {LISTEN_RATES.map((rate) => (
              <button
                key={rate}
                type="button"
                onClick={() => setRate(rate)}
                aria-pressed={state.rate === rate}
                data-testid={`listen-rate-${rate}`}
                className={`pill-studio tap-chip rounded-full px-2 py-1 text-xs font-semibold ${
                  state.rate === rate ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"
                }`}
              >
                {rate}×
              </button>
            ))}
          </div>
          <button
            type="button"
            onClick={stop}
            aria-label="Stop reading"
            data-testid="listen-dock-stop"
            className={ICON_BUTTON}
          >
            <X aria-hidden="true" className="h-3.5 w-3.5" />
          </button>
        </>
      )}
    </div>
  );
}

export default ListenDock;
