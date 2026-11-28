import { ShieldCheck } from "lucide-react";
import { GroupLabel } from "./SectionCard";
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "./ui/tooltip";

/**
 * The Craft check card, shared by Create's Review step and
 * HookSnap's hook section (Kasra's order, Nov 27 2026: the exact
 * same indicator in both places). Presentation only — the report's
 * fields, scores and words are the server's, unchanged; which words
 * were scored is the caller's side (Create scores the hook + script
 * pair, HookSnap the hook alone).
 */

/** The craft score's band in the founder's terms. It is a mirror, not a gate:
 *  no band refuses a render, and the copy says so. */
const QUALITY_BAND_NOTES = {
  distinctive: "Distinctive. The words are doing the work.",
  strong: "Strong. One craft note would sharpen it.",
  competent_but_generic:
    "Competent but generic. The hook or the spoken line is leaving performance on the table.",
  performance_risk: "Weak. Likely to lose the scroll or sound written.",
  off_brief: "Off-brief. Rewrite before rendering.",
};

function qualityBandNote(report) {
  return QUALITY_BAND_NOTES[report?.band] || "Advisory craft score for the saved words.";
}

/** The one label treatment inside a craft tooltip: the metric's title
 *  and the "On this clip" / "To lift it" headings all wear it, so a
 *  tooltip reads as one labeled panel in the app's label format (Kasra's
 *  ask, Nov 14) and the pieces can never drift into different styles. */
const TOOLTIP_LABEL_CLASS =
  "text-xs font-semibold uppercase tracking-[0.08em] text-primary-foreground/70";

/** What each craft dimension means, in plain words, for the tile tooltip.
 *  Two short parts per dimension: what it measures, and how the score is
 *  earned. Written from the scorer's own rubric (backend/creative_quality.py)
 *  so the words describe the same checks that produced the number — but in
 *  the founder's language, not the rubric's. Kept terse on the founder's
 *  word (Nov 14): the explanation is a glance, not a lecture — the
 *  rubric's own evidence under "On this clip" carries the detail. The
 *  clip-specific evidence and next step still come from the server under
 *  their own labels; this map is only the standing explanation of the
 *  dimension itself. */
const DIMENSION_EXPLANATIONS = {
  hook_stopping_power: {
    measures:
      "Whether the opening makes a scrolling viewer stop. Hook and cover text score together.",
    earned:
      "A problem, one concrete detail and an open gap earn. Diary openings, app talk and sales asks lose.",
  },
  audience_truth: {
    measures:
      "Whether it sounds like something your viewer would actually say about their own life.",
    earned:
      "First person and familiar routines earn. Third-person reporting, mood words, marketer voice and app talk lose.",
  },
  clarity: {
    measures:
      "Whether each line is one thought a listener can follow in a single listen.",
    earned:
      "Nothing over 24 words; the hook earns at 12 words or fewer. Vague pointers lose.",
  },
  concreteness: {
    measures:
      "Whether the viewer can picture the moment, not just understand it.",
    earned:
      "Place, action, time and a body detail earn. Abstract words and a vague payoff lose.",
  },
  story_arc: {
    measures:
      "Whether hook and script work as one story — problem, deepening, an ending that opens the demo.",
    earned:
      "Insight, a mid-story shift and answering the hook early earn. The open ending is paid in Demo handoff. Repeating the hook, quoting or wrapping up loses.",
  },
  spoken_naturalness: {
    measures:
      "Whether the lines sound like talking, not writing, when read aloud.",
    earned:
      "Contractions and short sentences earn. Written phrases, quotes and self-narration lose.",
  },
  demo_handoff: {
    measures:
      "Whether the script's last line leaves a question open for the demo.",
    earned:
      "Ending open, on the question the demo answers, earns most. A neat wrap-up or app talk loses.",
  },
  trust_compliance: {
    measures:
      "Whether the lines stay an honest customer story, with no claim the video can't back.",
    earned:
      "Starts at full score. Sales asks, naming the app and invented claims lose points.",
  },
};

/**
 * The craft check card: a score ring and the eight scored dimensions as
 * compact tiles side by side.
 *
 * Presentation only — the report's fields, scores and words are the
 * server's, unchanged. The layout is what changed, per the founder's ask:
 * the old card stacked every dimension's full advice under its score, so
 * the card read as a wall of copy. No advice text prints on the card at
 * all now: a top-fix callout under the header was removed on the
 * founder's word, so the card is the grade and the tiles, nothing more.
 *
 * The dimensions' maxima differ ON PURPOSE (the weights are the scoring:
 * hook stopping power is /20, audience truth /15, several are /10), so
 * tiles compare by proportion of their own max — the slim bar — never by
 * raw score. The weakest tile(s) by that proportion wear a stronger
 * indigo edge so the eye lands on what to fix first.
 *
 * Each tile explains itself on hover, focus or tap (audit 2026-11-14,
 * finding 4): the tooltip leads with a plain-words explanation of the
 * dimension (DIMENSION_EXPLANATIONS, written from the scorer's rubric),
 * then carries the rubric's OWN words for this clip — the evidence lines
 * and next step the server scored this pair with — under their own
 * labels, so the standing explanation and the clip's verdict stay
 * visibly separate and can never disagree with the scorer. The first
 * pass dumped the evidence as bare paragraphs with no header, no
 * explanation and no labels; the founder found that disorganized and
 * hard to read, so the tooltip now follows the app's labeled-panel
 * structure: header, explanation, labeled sections.
 * Nothing new prints on the card; the explanation is on demand only.
 */
// The Craft check's honest 0-10 scale (ADR 0300, the founder's
// ruling): the points a category can actually award fall short of
// its weight in two categories — Hook caps at 17 of 20, Audience
// truth at 13 of 15 — so the true ceiling is 95 of the 100 points,
// and a score shown "of 100" could never reach its own top. Every
// surface now shows the score out of 10, divided by what is
// actually achievable: zero is the worst, ten is the best a pair
// can earn. The server sends score10 on every fresh report; the
// caps mirror the server's only so a report saved before the
// scale change still reads true.
const CRAFT_ACHIEVABLE_CAPS = { hook_stopping_power: 17, audience_truth: 13 };
const craftAchievableMax = (dimension) =>
  Number(dimension?.achievable_max)
  || CRAFT_ACHIEVABLE_CAPS[dimension?.key]
  || Number(dimension?.max)
  || 0;
const craftScore10 = (score, achievable) =>
  achievable > 0 ? Math.round(((Number(score) || 0) / achievable) * 100) / 10 : 0;
const craftReportScore10 = (report, dimensions) => {
  if (typeof report?.score10 === "number") return report.score10;
  const achievableTotal = dimensions.length > 0
    ? dimensions.reduce((sum, dimension) => sum + craftAchievableMax(dimension), 0)
    : 95;
  return craftScore10(report?.total, achievableTotal);
};
const craftDimensionScore10 = (dimension) =>
  typeof dimension?.score10 === "number"
    ? dimension.score10
    : craftScore10(dimension?.score, craftAchievableMax(dimension));
const formatScore10 = (value) => {
  const rounded = Math.round((Number(value) || 0) * 10) / 10;
  return Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
};

export function CraftCheckCard({ report }) {
  const dimensions = Object.values(report?.dimensions || {});
  const total10 = craftReportScore10(report, dimensions);
  const fraction = Math.max(0, Math.min(1, total10 / 10));
  const ratioOf = (dimension) => craftDimensionScore10(dimension) / 10;
  const weakestRatio = dimensions.length > 0
    ? Math.min(...dimensions.map(ratioOf))
    : null;
  const ringRadius = 26;
  const ringCircumference = 2 * Math.PI * ringRadius;
  return (
    <div className="inset-panel space-y-4" data-testid="quality-report">
      <div className="flex items-center gap-4">
        <div
          className="relative h-16 w-16 shrink-0"
          role="img"
          aria-label={`Craft score ${formatScore10(total10)} of 10${report?.grade ? `, grade ${report.grade}` : ""}`}
        >
          <svg viewBox="0 0 64 64" className="h-16 w-16 -rotate-90" aria-hidden="true">
            <circle
              cx="32"
              cy="32"
              r={ringRadius}
              fill="none"
              strokeWidth="6"
              style={{ stroke: "var(--indigo-15)" }}
            />
            <circle
              cx="32"
              cy="32"
              r={ringRadius}
              fill="none"
              strokeWidth="6"
              strokeLinecap="round"
              style={{
                stroke: "var(--brand-indigo)",
                strokeDasharray: ringCircumference,
                strokeDashoffset: ringCircumference * (1 - fraction),
              }}
            />
          </svg>
          <span className="absolute inset-0 flex items-center justify-center font-display text-base font-semibold">
            {report?.grade}
          </span>
        </div>
        <div className="min-w-0 space-y-1">
          <GroupLabel icon={ShieldCheck}>Craft check</GroupLabel>
          <p className="text-sm text-muted-foreground">
            {formatScore10(total10)}/10
          </p>
          <p className="text-sm text-muted-foreground">
            {qualityBandNote(report)}
          </p>
        </div>
      </div>
      {dimensions.length > 0 && (
        <TooltipProvider delayDuration={200}>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2" data-testid="quality-dimensions">
            {dimensions.map((dimension) => {
              const score10 = craftDimensionScore10(dimension);
              const pct = Math.round(score10 * 10);
              const isWeakest = weakestRatio !== null && ratioOf(dimension) === weakestRatio;
              const evidence = Array.isArray(dimension.evidence)
                ? dimension.evidence.filter((line) => String(line || "").trim())
                : [];
              return (
                <Tooltip key={dimension.key}>
                  <TooltipTrigger asChild>
                    <li
                      data-testid="quality-dimension"
                      data-weakest={isWeakest ? "true" : undefined}
                      tabIndex={0}
                      className="surface-compact space-y-2"
                      style={isWeakest
                        ? { borderColor: "var(--indigo-45)", backgroundColor: "var(--indigo-4)" }
                        : undefined}
                    >
                      <div className="flex flex-wrap items-baseline justify-between gap-2">
                        <p className="text-sm font-semibold">{dimension.label}</p>
                        <p className="text-sm text-muted-foreground">{formatScore10(score10)}/10</p>
                      </div>
                      <div
                        role="progressbar"
                        aria-valuemin={0}
                        aria-valuemax={10}
                        aria-valuenow={score10}
                        aria-label={dimension.label}
                        className="h-1.5 w-full overflow-hidden rounded-full bg-[color:var(--indigo-8)]"
                      >
                        <div
                          className="h-full rounded-full bg-gradient-to-r from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] transition-[width] duration-500"
                          style={{ width: `${pct}%` }}
                        />
                      </div>
                    </li>
                  </TooltipTrigger>
                  {/* The aria-label is load-bearing, not decoration
                      (ADR 0188): Radix renders a tooltip's children
                      TWICE — once visible, and once in a visually
                      hidden accessible copy the trigger's
                      aria-describedby points at. With no aria-label
                      the hidden copy repeats the whole findings-and-
                      advice block word for word, so any read of the
                      tooltip's text (a paste, a screen reader's text
                      pass) heard everything twice. The label replaces
                      the hidden copy with the one-line summary; the
                      findings and advice now exist exactly once. */}
                  <TooltipContent
                    data-testid={`quality-dimension-tip-${dimension.key}`}
                    className="max-w-xs space-y-2.5"
                    aria-label={`${dimension.label}: ${formatScore10(score10)} of 10`}
                  >
                    <div className="flex items-baseline justify-between gap-3">
                      <p className={TOOLTIP_LABEL_CLASS}>{dimension.label}</p>
                      <p className="text-primary-foreground/70">
                        {formatScore10(score10)}/10
                      </p>
                    </div>
                    {DIMENSION_EXPLANATIONS[dimension.key] && (
                      <div className="space-y-1">
                        <p>{DIMENSION_EXPLANATIONS[dimension.key].measures}</p>
                        <p>{DIMENSION_EXPLANATIONS[dimension.key].earned}</p>
                      </div>
                    )}
                    {evidence.length > 0 && (
                      <div className="space-y-1">
                        <p className={TOOLTIP_LABEL_CLASS}>
                          On this clip
                        </p>
                        <ul className="list-disc space-y-0.5 pl-4">
                          {evidence.map((line, index) => (
                            <li key={index}>{line}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                    {dimension.next_step && (
                      <div className="space-y-1">
                        <p className={TOOLTIP_LABEL_CLASS}>
                          To lift it
                        </p>
                        <p>{dimension.next_step}</p>
                      </div>
                    )}
                    {!DIMENSION_EXPLANATIONS[dimension.key] && !evidence.length && !dimension.next_step && (
                      <p>{dimension.label} — scored out of 10.</p>
                    )}
                  </TooltipContent>
                </Tooltip>
              );
            })}
          </ul>
        </TooltipProvider>
      )}
      <p className="text-sm text-muted-foreground">
        Advisory only — it never blocks a render.
      </p>
    </div>
  );
}
