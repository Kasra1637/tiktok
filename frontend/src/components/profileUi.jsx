import { ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import { sentenceCase } from "../lib/copyCase";

/**
 * Shared profile card system — one card language for the App Profile page
 * and the Create Video Audience & goal step.
 *
 * Tokens (no one-off pixels):
 * - card gap 16 (gap-4), card padding 20 (p-5), item gap 12 (gap-3)
 * - card radius 16 (rounded-2xl), nested sub-card radius 12 (rounded-xl) + padding 16 (p-4)
 * - label 11px uppercase muted, body 14/22, meta 12/18, chip 13/18
 * - one background + 1px hairline border everywhere
 *
 * Rows that must stay equal-height use `items-stretch` on the grid and
 * `h-full` on the card. No fixed heights, no overflow-hidden, no line-clamp —
 * content is top-aligned and grows the whole row together.
 */

export const profileToneClass = {
  default: "",
  approved: "border-green-500/25 bg-green-500/[0.07]",
  review: "border-amber-500/25 bg-amber-500/[0.07]",
  enforced: "border-red-500/25 bg-red-500/[0.07]",
};

export function ProfileCard({ eyebrow, eyebrowClassName, tone = "default", testid, className, children }) {
  return (
    <section
      className={cn(
        "flex h-full flex-col gap-3 rounded-2xl border border-[color:var(--hairline)] bg-card/70 p-5",
        profileToneClass[tone],
        className
      )}
      {...(testid ? { "data-testid": testid } : {})}
    >
      {eyebrow && (
        <>
          <h3
            className={cn(
              "text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground",
              eyebrowClassName
            )}
          >
            {eyebrow}
          </h3>
          <div aria-hidden="true" className="h-px bg-[color:var(--hairline)]" />
        </>
      )}
      {children}
    </section>
  );
}

/** One label inside a card: 11px uppercase muted + 14/22 body. */
export function ProfileField({ label, value }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      <h4 className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </h4>
      <p className="mt-1 whitespace-pre-wrap text-sm leading-[22px] text-foreground/90">{sentenceCase(value)}</p>
    </div>
  );
}

/**
 * The single static chip renderer. Fixed 10px radius + 6x12 padding +
 * 32px min-height; wrapping never changes the radius, fill stays subtle
 * with no heavy border.
 */
export function InfoChipList({ label, items, tone = "default", labelClassName }) {
  if (!items.length) return null;
  const chipClass =
    tone === "enforced"
      ? "border-red-500/25 bg-red-500/10 text-foreground/90"
      : tone === "review"
        ? "border-amber-500/25 bg-amber-500/10 text-foreground/90"
        : tone === "approved"
          ? "border-green-500/25 bg-green-500/10 text-foreground/90"
          : "border-[color:var(--hairline)] bg-secondary/40 text-foreground/90";
  const labelTone =
    tone === "enforced"
      ? "text-[color:var(--destructive,oklch(0.65_0.2_25))]"
      : "text-foreground";
  return (
    <div className="min-w-0">
      <span className={cn("text-[11px] font-semibold uppercase tracking-[0.08em]", labelTone, labelClassName)}>
        {label}
      </span>
      <ul className="mt-3 flex flex-wrap gap-3">
        {items.map((item, i) => (
          <li
            key={i}
            className={cn(
              "inline-flex min-h-8 items-center rounded-[10px] border px-3 py-1.5 text-[13px] leading-[18px]",
              chipClass
            )}
          >
            {sentenceCase(item)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Bulleted companion for longer phrases: same 12/16 nested-card tokens. */
export function InfoListBlock({ label, items, tone = "default" }) {
  if (!items.length) return null;
  const toneClass =
    tone === "banned"
      ? "border-red-500/25 bg-red-500/[0.07]"
      : tone === "review"
        ? "border-amber-500/25 bg-amber-500/[0.07]"
        : "border-[color:var(--hairline)] bg-secondary/20";
  return (
    <div className={cn("rounded-xl border p-4", toneClass)}>
      <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
        {label}
      </span>
      <ul className="mt-3 space-y-3 text-sm leading-[22px] text-foreground/90">
        {items.map((item, i) => (
          <li key={i} className="flex gap-3">
            <span className="mt-[9px] h-1 w-1 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
            <span className="min-w-0">{sentenceCase(item)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * One collapsible group of cards — never per card, so equal-height rows
 * stay equal. Lightweight bar header (not a card): label, data-computed
 * summary, chevron. Native button = clickable + keyboard accessible with
 * aria-expanded. Grid-rows animation (200ms) opens without layout jump;
 * the overflow-hidden lives on the animation wrapper, never on a card.
 */
export function SectionGroup({ id, label, summary, open, onToggle, children }) {
  const contentId = `profile-group-${id}`;
  return (
    <section aria-label={label} data-testid={`group-${id}`} className="min-w-0">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => onToggle(id, !open)}
        className="flex w-full min-w-0 items-center gap-3 rounded-[10px] px-1 py-1 text-left transition-colors hover:bg-secondary/30"
      >
        <span className="shrink-0 text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
          {label}
        </span>
        {summary ? (
          <span className="min-w-0 flex-1 text-xs leading-[18px] text-muted-foreground">
            {summary}
          </span>
        ) : (
          <span className="flex-1" />
        )}
        <ChevronDown
          className={cn(
            "h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200",
            open && "rotate-180"
          )}
        />
      </button>
      <div
        id={contentId}
        className="grid transition-all duration-200 ease-out"
        style={{ gridTemplateRows: open ? "1fr" : "0fr", opacity: open ? 1 : 0 }}
      >
        <div className="min-h-0 overflow-hidden">
          <div className="space-y-4 pt-3">{children}</div>
        </div>
      </div>
    </section>
  );
}

/** Equal-height grid: stretch rows, 16px gaps, top-aligned content. */
export function CardGrid({ className, children }) {
  return <div className={cn("grid grid-cols-1 items-stretch gap-4", className)}>{children}</div>;
}

/**
 * Nested statement card (feature-to-outcome / objection): title, hairline,
 * then identically-styled meta rows. An odd last card spans both columns so
 * the grid never leaves an orphan half-row.
 */
export function StatementCard({ title, rows, spanFull }) {
  return (
    <div
      className={cn(
        "flex h-full flex-col gap-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-4",
        spanFull && "md:col-span-2"
      )}
    >
      <p className="text-sm font-medium leading-[22px]">{sentenceCase(title)}</p>
      {rows.filter(Boolean).length > 0 && (
        <>
          <div aria-hidden="true" className="h-px bg-[color:var(--hairline)]" />
          <div className="space-y-1.5">
            {rows.filter(Boolean).map((row, i) => (
              <p key={i} className="text-xs leading-[18px] text-muted-foreground">
                {sentenceCase(row)}
              </p>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
