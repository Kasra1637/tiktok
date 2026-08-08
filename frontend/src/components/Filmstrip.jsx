import { useState } from "react";
import { mediaUrl } from "../lib/api";
import { Check, Film, ImageOff } from "lucide-react";

function FrameImage({ src, alt }) {
  const [failed, setFailed] = useState(false);
  const [retried, setRetried] = useState(false);

  if (failed) {
    return (
      <div className="flex h-[160px] w-full items-center justify-center bg-secondary/60 md:h-[190px]">
        <ImageOff className="h-5 w-5 text-muted-foreground/40" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className="h-[160px] w-full object-cover transition-transform duration-500 ease-out-expo group-hover:scale-[1.05] md:h-[190px]"
      onError={(e) => {
        // Retry once (the dynamic endpoint may need a moment to recover the frame)
        if (!retried) {
          setRetried(true);
          setTimeout(() => {
            e.target.src = src + (src.includes("?") ? "&" : "?") + "retry=1";
          }, 2000);
        } else {
          setFailed(true);
        }
      }}
    />
  );
}

export function Filmstrip({ frames, selectedIndex, onSelect }) {
  return (
    <div className="surface rounded-2xl p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Film className="h-3.5 w-3.5 text-[color:var(--brand-teal)]" />
          <span className="eyebrow">Extracted frames</span>
        </div>
        <span className="text-[11px] text-muted-foreground">
          Tap a frame to pick your swap target
        </span>
      </div>

      <div className="relative">
        <div className="filmstrip-scroll no-scrollbar -mx-1 flex gap-3 overflow-x-auto px-1 pb-2 scroll-px-1">
          {frames.map((frame) => {
            const selected = selectedIndex === frame.index;
            return (
              <button
                key={frame.index}
                onClick={() => onSelect(frame.index)}
                data-testid={`filmstrip-frame-button-${frame.index}`}
                aria-pressed={selected}
                className={`group relative w-[120px] shrink-0 overflow-hidden rounded-xl border transition-[transform,box-shadow,border-color] duration-200 focus-visible:outline-none md:w-[140px] ${
                  selected
                    ? "-translate-y-0.5 border-[color:var(--brand-teal)] shadow-[var(--glow-indigo)]"
                    : "border-[color:var(--hairline)] hover:-translate-y-0.5 hover:border-[color:var(--indigo-45)] hover:shadow-[var(--shadow-md)]"
                }`}
              >
                <FrameImage src={mediaUrl(frame.media_url)} alt={`Frame ${frame.index}`} />
                {/* Dim unselected frames so the active one visually wins. */}
                <span
                  aria-hidden="true"
                  className={`pointer-events-none absolute inset-0 transition-opacity duration-200 ${
                    selected ? "opacity-0" : "bg-background/35 group-hover:opacity-0"
                  }`}
                />
                <span className="absolute bottom-2 left-2 rounded-full bg-black/70 px-2 py-0.5 text-[11px] font-medium text-white backdrop-blur-sm">
                  {frame.timestamp_seconds}s
                </span>
                {selected && (
                  <span className="absolute right-2 top-2 inline-flex items-center gap-1 rounded-full bg-[color:var(--brand-teal)] px-2 py-0.5 text-[10px] font-bold text-white shadow-[var(--shadow-sm)]">
                    <Check className="h-2.5 w-2.5" /> Hook
                  </span>
                )}
              </button>
            );
          })}
        </div>
        {/* Edge fades hint at horizontal scrollability without extra chrome */}
        <div className="pointer-events-none absolute inset-y-0 left-0 w-8 bg-gradient-to-r from-[color:var(--card)] to-transparent opacity-80" />
        <div className="pointer-events-none absolute inset-y-0 right-0 w-8 bg-gradient-to-l from-[color:var(--card)] to-transparent opacity-80" />
      </div>
    </div>
  );
}
export default Filmstrip;
