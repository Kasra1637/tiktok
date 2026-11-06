import { IconTile } from "./IconTile";
import { useReducedMotionPreference } from "../lib/reducedMotion";

export function EmptyState({ icon, title, description, action, headingLevel = "h2" }) {
  const Heading = headingLevel;
  const reduceMotion = useReducedMotionPreference();

  return (
    <div
      className="card-enter"
      style={reduceMotion ? { animation: "none" } : undefined}
    >
      <div className="relative overflow-hidden rounded-2xl border border-dashed border-[color:var(--hairline-strong)] bg-card/40 px-6 py-14 text-center backdrop-blur-sm">
        {/* Soft indigo pool behind the icon keeps the dashed box from reading
            as an error state. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-40"
          style={{
            background: "radial-gradient(400px circle at 50% 0%, var(--indigo-10), transparent 70%)",
          }}
        />
        <div className="relative flex flex-col items-center justify-center gap-4">
          {icon && (
            <span
              className="card-enter"
              style={reduceMotion ? { animation: "none" } : undefined}
            >
              <IconTile icon={icon} size="empty" />
            </span>
          )}
          <Heading className="font-display text-base font-semibold tracking-tight">{title}</Heading>
          {description && (
            <p className="max-w-md text-base leading-relaxed text-muted-foreground">{description}</p>
          )}
          {action && <div>{action}</div>}
        </div>
      </div>
    </div>
  );
}
export default EmptyState;
