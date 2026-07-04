import { mediaUrl } from "../lib/api";

export function Filmstrip({ frames, selectedIndex, onSelect }) {
  return (
    <div className="relative">
      <div className="filmstrip-scroll flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 scroll-px-1">
        {frames.map((frame) => (
          <button
            key={frame.index}
            onClick={() => onSelect(frame.index)}
            data-testid={`filmstrip-frame-button-${frame.index}`}
            className={`group relative shrink-0 w-[120px] md:w-[140px] rounded-xl overflow-hidden border focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-teal)] transition-shadow transition-colors hover:shadow-[var(--shadow-tight)] ${
              selectedIndex === frame.index ? "ring-2 ring-[color:var(--brand-teal)] border-transparent" : "border-border hover:border-[color:rgba(13,148,136,0.45)]"
            }`}
          >
            <img
              src={mediaUrl(frame.media_url)}
              alt={`Frame ${frame.index}`}
              className="w-full h-[160px] md:h-[190px] object-cover transition-transform duration-300 group-hover:scale-[1.04]"
            />
            <span className="absolute bottom-2 left-2 rounded-full bg-black/70 text-white text-[11px] px-2 py-0.5">
              {frame.timestamp_seconds}s
            </span>
            {selectedIndex === frame.index && (
              <span className="absolute top-2 right-2 rounded-full bg-[color:var(--brand-teal)] text-white text-[10px] px-2 py-0.5 shadow-sm">
                Hook
              </span>
            )}
          </button>
        ))}
      </div>
      {/* Edge fades hint at horizontal scrollability without extra chrome */}
      <div className="pointer-events-none absolute inset-y-0 left-0 w-6 bg-gradient-to-r from-[color:var(--card)] to-transparent opacity-70" />
      <div className="pointer-events-none absolute inset-y-0 right-0 w-6 bg-gradient-to-l from-[color:var(--card)] to-transparent opacity-70" />
    </div>
  );
}
export default Filmstrip;
