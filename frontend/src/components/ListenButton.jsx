import { Square, Volume2 } from "lucide-react";
import { cn } from "../lib/utils";
import { useListen } from "../hooks/useListen";

/**
 * The per-section listen toggle, for section headers and record bars.
 *
 * Hidden entirely where the browser cannot speak, so it can never sit on
 * screen doing nothing. Start/stop only — pause, stop and the speed switch
 * live once in the dock (AppShell), which is what keeps a page from growing
 * a second transport per section.
 */
export function ListenButton({ id, label, getBlocks, testId, className }) {
  const { supported, present, toggle } = useListen(id, getBlocks, label);

  if (!supported) return null;

  const Icon = present ? Square : Volume2;
  return (
    <button
      type="button"
      onClick={(event) => {
        event.preventDefault();
        event.stopPropagation();
        toggle();
      }}
      aria-pressed={present}
      aria-label={present ? `Stop reading: ${label}` : `Listen: ${label}`}
      title={present ? "Stop reading" : "Listen to this section"}
      data-testid={testId || `listen-${id}`}
      className={cn(
        "pill-studio tap-chip flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[color:var(--hairline)] text-muted-foreground transition-colors hover:text-foreground",
        present && "border-[color:var(--indigo-35)] text-[color:var(--brand-indigo)]",
        className
      )}
    >
      <Icon aria-hidden="true" className="h-3.5 w-3.5" />
    </button>
  );
}

export default ListenButton;
