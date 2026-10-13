import { ChevronDown } from "lucide-react";
import { cn } from "../lib/utils";
import { sentenceCase } from "../lib/copyCase";
import { GroupLabel } from "./SectionCard";

/**
 * Shared profile card system — the App Profile page's card language, on the
 * same tokens as the Content Angles list on Create Video's Audience & goal
 * step. The two screens are read side by side, so what a heading, a label
 * and a piece of chrome look like is decided here to match that list.
 *
 * Tokens (no one-off pixels), all taken from the Content Angles block:
 * - headings 14/500 sentence case (the angle row's title token) — never
 *   uppercase, never tracked, and no glyph beside them; the angle rows carry none
 * - field labels are the shared `GroupLabel` (12/600 uppercase muted
 *   `.eyebrow`) — the same label the angle detail panel uses for its own fields
 * - body 14/22, meta 12/18, chips 12/18 at the Badge shape the kind tag uses
 * - item gap 8 (gap-2 / space-y-2) and card padding px-4 py-3 — the angle
 *   row's rhythm, not a roomier one of our own
 * - card radius 16 (rounded-2xl); nested sub-cards are the shared
 *   `.inset-panel` (12px radius, 16px gutter) rather than a local copy of it
 * - one background + 1px hairline border everywhere, and no rule under a
 *   heading — the angle rows have none
 *
 * Rows that must stay equal-height use `items-stretch` on the grid and
 * `h-full` on the card. No fixed heights, no overflow-hidden, no line-clamp —
 * content is top-aligned and grows the whole row together.
 */

export const profileToneClass = {
  default: "",
  approved: "border-green-500/25 bg-green-500/[0.07]",
  review: "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]",
  enforced: "border-[color:var(--hairline-strong)] bg-secondary/30",
};

export function ProfileCard({ eyebrow, eyebrowClassName, tone = "default", testid, className, children }) {
  return (
    <section
      className={cn(
        "row-pad flex h-full flex-col gap-2 rounded-2xl border border-[color:var(--hairline)] bg-card/70",
        profileToneClass[tone],
        className
      )}
      {...(testid ? { "data-testid": testid } : {})}
    >
      {eyebrow && (
        <h3 className={cn("text-sm font-medium leading-[22px]", eyebrowClassName)}>
          {sentenceCase(eyebrow)}
        </h3>
      )}
      {children}
    </section>
  );
}

/**
 * One label inside a card: the shared 12px eyebrow + 14/22 body.
 *
 * `label` is optional for the same reason it is on InfoChipList: when the
 * card's own eyebrow already says it, naming it again here prints the same
 * string twice, one line apart. A label-less field renders its value alone,
 * with the margin the label would have carried.
 */
export function ProfileField({ label, value }) {
  if (!value) return null;
  return (
    <div className="min-w-0">
      {label ? <GroupLabel as="h4">{label}</GroupLabel> : null}
      <p
        className={cn(
          "whitespace-pre-wrap text-sm leading-[22px] text-foreground/90",
          label && "mt-1"
        )}
      >
        {sentenceCase(value)}
      </p>
    </div>
  );
}

/**
 * The single static chip renderer. The Badge shape the angle rows' kind tag
 * uses — 6px radius, 10x4 padding, 12/18 text — so a chip and a kind badge
 * are the same element at the same size; wrapping never changes the radius.
 * Fill stays subtle with no heavy border.
 */
export function InfoChipList({ label, items, tone = "default", labelClassName }) {
  if (!items.length) return null;
  const chipClass =
    tone === "review"
      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-foreground/90"
      : tone === "approved"
        ? "border-green-500/25 bg-green-500/10 text-foreground/90"
        : "border-[color:var(--hairline)] bg-secondary/40 text-foreground/90";
  return (
    <div className="min-w-0">
      {/* Label is optional: when the card eyebrow already says it, repeating it
          here renders the same string twice.

          It is the shared eyebrow, not a bespoke 11px row: every other label
          on this page and on the App Profile page is `.eyebrow`, and one
          label at a different size is what made the two pages disagree. */}
      {label ? (
        <GroupLabel className={labelClassName}>{label}</GroupLabel>
      ) : null}
      <ul className={cn("flex flex-wrap gap-3", label ? "mt-2" : "mt-0")}>
        {items.map((item, i) => (
          <li
            key={i}
            className={cn(
              "inline-flex items-center rounded-md border px-2.5 py-1 text-xs leading-[18px]",
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
      ? "border-[color:var(--hairline-strong)] bg-secondary/30"
      : tone === "review"
        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
        : "border-[color:var(--hairline)] bg-secondary/20";
  return (
    <div className={cn("rounded-xl border p-4", toneClass)}>
      <GroupLabel>{label}</GroupLabel>
      <ul className="mt-2 space-y-2 text-sm leading-[22px] text-foreground/90">
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
 * stay equal.
 *
 * The bar chrome is the Content Angles row's, because this page is read
 * against that list: px-4 py-3, a 14/500 sentence-case title with the count
 * summary beneath it in the row's 12/18 meta token, chevron right, indigo
 * hover. Opening reveals the angle panel's content chrome — a hairline under
 * the bar, then px-4 py-3 with 8px between cards. The old 14px uppercase
 * tracked heading and its brand-indigo glyph are gone with the restyle: the
 * angle rows carry neither.
 *
 * Native button = clickable + keyboard accessible with aria-expanded.
 * Grid-rows animation (200ms) opens without layout jump; the overflow-hidden
 * lives on the animation wrapper, never on a card.
 */
export function SectionGroup({ id, label, summary, open, onToggle, children }) {
  const contentId = `profile-group-${id}`;
  return (
    <section
      aria-label={label}
      data-testid={`group-${id}`}
      className="surface surface-flush min-w-0 overflow-hidden rounded-2xl space-y-0"
    >
      <button
        type="button"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => onToggle(id, !open)}
        className="row-pad flex w-full min-w-0 items-center justify-between gap-2 text-left transition duration-150 hover:bg-[color:var(--indigo-6)]"
      >
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-medium leading-[22px]">{label}</span>
          {summary ? (
            <span className="mt-1 block truncate text-xs leading-[18px] text-muted-foreground">
              {summary}
            </span>
          ) : null}
        </span>
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
          <div className="row-pad space-y-2 border-t border-[color:var(--hairline)]">{children}</div>
        </div>
      </div>
    </section>
  );
}

/** Equal-height grid: stretch rows, 8px gaps, top-aligned content. */
export function CardGrid({ className, children }) {
  return <div className={cn("grid grid-cols-1 items-stretch gap-2", className)}>{children}</div>;
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
        "inset-panel flex h-full flex-col gap-3",
        spanFull && "md:col-span-2"
      )}
    >
      <p className="text-sm font-medium leading-[22px]">{sentenceCase(title)}</p>
      {rows.filter(Boolean).length > 0 && (
        <>
          <div aria-hidden="true" className="h-px bg-[color:var(--hairline)]" />
          <div className="space-y-2">
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
