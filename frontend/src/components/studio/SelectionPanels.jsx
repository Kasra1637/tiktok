import { useEffect, useRef, useState } from "react";

import { Button } from "../ui/button";

import { Badge } from "../ui/badge";
import { Alert, AlertDescription } from "../ui/alert";

import { GroupLabel } from "../SectionCard";

import { FitBadge } from "../FitBadge";

import { sentenceCase } from "../../lib/copyCase";
import { angleDetails, angleFitScore, formatVerdicts, goalFitScore } from "../../lib/angleSubtitle";
import { angleSetAge } from "../../lib/angleFreshness";
import {
  readPieceSeconds,
  sectionSplit,
  clampHookSeconds,
  DEFAULT_HOOK_SECONDS,
} from "../../lib/videoLength";
import { Loader as Loader2, TriangleAlert as AlertTriangle, Target, Check, Sparkles, RefreshCw, ChevronDown } from "lucide-react";

/* The single instruction for the angle picker, shared by the empty state
   (click generates the six) and the reveal state (click shows the six).
   One line on purpose: three stacked explanations said the same thing in
   different words, and the step stalled on reading instead of moving. The
   verb is deliberately neutral — "get" covers generating fresh angles and
   revealing pre-generated ones, so the line never disagrees with its button. */
const ANGLES_CTA_COPY = "Get your six audience angles, then pick one to move forward.";

function formatTemplateUse(n) {
  if (!n) return "Never used";
  return n === 1 ? "Used once" : `Used ${n} times`;
}

/**
 * One recommended template.
 *
 * Every fit reason and every limitation is shown, always. They used to be
 * collapsed behind a "Show all N more" link, which was wrong twice over: these
 * ARE the evidence for the choice the founder is making here, and the count
 * they were hiding behind is not a quality signal. The scorer emits one reason
 * per matched factor and sorts by weight, so a single "Built for the 'create
 * curiosity' objective" (3.0) outranks three 1.0 matches — and a miss becomes
 * a LIMITATION rather than a reason, so a template can match strongly and still
 * carry a caveat. Four reasons is not better than two.
 *
 * The score is therefore the number worth reading, and it is already computed
 * server-side (and already what the list is sorted by), so it is shown here
 * rather than left for the founder to infer from ordering.
 *
 * Two blocks, not one: a reason is the case FOR this template and a limitation
 * is the caveat ON it. Rendering them identically made a warning look like
 * supporting evidence.
 *
 * A div with button semantics rather than a <button> because the whole card is
 * the control. There is no longer a nested toggle — the previous one called
 * stopPropagation on click but not on keydown, so Enter and Space on the link
 * selected the template instead of expanding it.
 */
export function RecommendationCard({ r, selected, onSelect, index = 0 }) {
  const reasons = Array.isArray(r.why_it_fits) ? r.why_it_fits : [];
  // Where and when the selected angle opens (ADR 0084). A template whose own
  // staging contradicts it is ranked lower server-side and says so here, in
  // plain view rather than tucked into the disclosure.
  const scene = r.angle_scene && typeof r.angle_scene === "object" ? r.angle_scene : {};
  const moment = typeof scene.moment === "string" ? scene.moment.trim() : "";
  const misfit = scene.fits === false
    ? (Array.isArray(r.limitations) ? r.limitations : []).find((l) => String(l).startsWith("Doesn't fit this angle")) || ""
    : "";
  const limits = (Array.isArray(r.limitations) ? r.limitations : []).filter((l) => l !== misfit);
  const score = Number(r.score);
  // The server sorts reasons strongest-first and sends only the strings, so
  // the first reason IS the verdict and the rest is supporting detail. Shown
  // that way rather than as four identical paragraphs, which left the founder
  // unable to tell the decision from its evidence.
  const [verdict, ...detail] = reasons;
  const example =
    !scene.example_conflicts &&
    typeof r.template.example_preview === "string" && r.template.example_preview.trim()
      ? r.template.example_preview.trim()
      : "";
  // The viewer-facing outcome, when the row carries one. Curated rows always
  // do; tailored rows do once regenerated. Rendered as the card's lead line
  // in body weight so the first thing read is the result, not the mechanic.
  // Tailored rows are model-written, so this can open lowercase next to the
  // hand-written recommendation copy on the same card.
  const outcome =
    typeof r.template.outcome === "string" && r.template.outcome.trim()
      ? sentenceCase(r.template.outcome.trim())
      : "";
  // The structure is what the founder actually picks; the angle's moment
  // below it is where that structure is staged in their video.
  const opening =
    typeof r.template.opening_structure === "string" && r.template.opening_structure.trim()
      ? sentenceCase(r.template.opening_structure.trim())
      : "";
  return (
    // Staggered arrival like the angle and goal rows: a fresh ranking is
    // watched arriving instead of blinking in at once. Keyed by template id
    // at the call site, so only genuinely new sets replay it.
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      aria-pressed={selected}
      style={{ animationDelay: `${Math.min(index, 8) * 70}ms` }}
      className={`card-pickable animate-fade-up w-full rounded-xl border p-4 text-left ${
        selected
          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
          : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-base font-semibold">{r.template.name}</span>
        <span className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {r.suggested_duration}s
          </Badge>
          {Number.isFinite(score) && (
            // The sort key on a 0–10 scale: a weighted sum of matched
            // factors, clamped server-side, comparable only between these
            // cards. Shared FitBadge pill so the template score reads as the
            // same instrument as the angle and goal scores above it.
            <FitBadge
              score={score}
              basis="Fit score — a weighted sum of the factors this template matched, on a 0–10 scale. Only comparable against the other templates below."
              testId="template-fit-score"
            />
          )}
          <Badge variant="secondary" className="text-xs">
            {formatTemplateUse(r.template.times_used)}
          </Badge>
          {selected && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
        </span>
      </div>
      {outcome && (
        <p className="mt-1 text-base text-foreground/90" data-testid="template-outcome">
          {outcome}
        </p>
      )}
      {example && (
        <p className="mt-1 text-sm text-foreground/80">
          <span className="text-muted-foreground">Sounds like: </span>
          &ldquo;{example}&rdquo;
        </p>
      )}
      {opening && (
        <p className="mt-1 text-sm text-muted-foreground" data-testid="template-structure">
          <span className="text-muted-foreground">Shape: </span>
          {opening}
        </p>
      )}
      {moment && !misfit && (
        <p className="mt-1 text-sm text-foreground/80" data-testid="template-angle-moment">
          <span className="text-muted-foreground">In your video: </span>
          {moment}
        </p>
      )}
      {misfit && (
        <p className="mt-1 text-sm font-semibold text-foreground" data-testid="template-angle-misfit">
          {misfit}
        </p>
      )}
      {reasons.length > 0 && (
        <div className="mt-2 space-y-2">
          <p className="eyebrow">Why it fits</p>
          {/* The verdict: the strongest match, in body weight with the same
              tick the step pills use for "positive", so it reads as the reason
              rather than one of several. */}
          <p
            className="flex items-start gap-1.5 text-base text-foreground"
            data-testid="template-fit-verdict"
          >
            <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span>{sentenceCase(verdict)}</span>
          </p>
        </div>
      )}
      {/* Supporting detail and limitations tuck into a disclosure: the card
          leads with its verdict, and the rest opens on demand. The verdict
          stays outside any list, and a single-reason card with no limits
          renders no disclosure at all. */}
      {(detail.length > 0 || limits.length > 0) && (
        <details className="mt-2">
          <summary className="cursor-pointer text-sm text-muted-foreground">
            More on this fit
          </summary>
          <div className="mt-1 space-y-1">
            {detail.length > 0 && (
              <ul className="space-y-1">
                {detail.map((reason, i) => (
                  <li
                    key={`r-${i + 1}`}
                    className="flex items-start gap-1.5 text-sm leading-relaxed text-muted-foreground"
                  >
                    <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
                    <span>{sentenceCase(reason)}</span>
                  </li>
                ))}
              </ul>
            )}
            {limits.length > 0 && (
              <ul className="space-y-1">
                {limits.map((limitation, i) => (
                  <li
                    key={`l-${i}`}
                    className="flex items-start gap-1.5 text-sm leading-relaxed text-muted-foreground"
                  >
                    <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
                    <span>{sentenceCase(limitation)}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </details>
      )}
    </div>
  );
}

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * The middle's curated structure, under whichever name the row still carries.
 *
 * `middle_structure` replaced `continuation_structure` and a separate
 * `cta_pattern`: the old pair described a chain with a closing beat, which is
 * not what a template declares any more. Rows seeded before the change still
 * carry the retired name, and the backend reads it as a fallback for the same
 * reason. Reading only the new name would leave those templates showing a blank
 * where the curated middle lives, which reads as a template with nothing after
 * its opening.
 */
function middleStructure(template) {
  return String(template?.middle_structure || template?.continuation_structure || "");
}

/**
 * The shape of the piece a template produces: its length, its two section
 * lengths, and the curated middle.
 *
 * Shown on the template card because the template is where the length comes
 * from. A founder choosing between two openings is also choosing between two
 * lengths, and a picker on the step after this used to make that look
 * independent. The numbers are the ones the project will be seeded with, so
 * nothing on the later steps can quietly disagree.
 */
export function TemplateShape({ template }) {
  const total = readPieceSeconds(null, template);
  const hook = clampHookSeconds(template?.hook_seconds) || DEFAULT_HOOK_SECONDS;
  const split = sectionSplit(total, hook);
  const middle = middleStructure(template);
  return (
    <div className="mt-2 space-y-1">
      <p className="text-sm">
        <span className="font-semibold">{total}s piece</span>: a {split.hookSeconds}s hook, then a{" "}
        {split.middleSeconds}s middle.
      </p>
      {middle && <p className="text-sm text-muted-foreground">{sentenceCase(middle)}</p>}
    </div>
  );
}

/**
 * The studio's angle-selection control. It lives on Audience & template and on
 * Review & submit — one control, one behaviour, wherever the founder is asked
 * for it. The review copy picks the angle through the single red jump back to step 1,
 * never a second copy of this list: the goal picker there waits silently.
 *
 * Landing is always gated: one "Generate angles" action, never a finished list.
 * The first click always generates fresh — a cached set from an earlier
 * approval is never revealed as-is, so a new video never lands on a stale
 * "Refreshed 9h ago" set. A set generated moments ago in-session is then
 * revealed free on step re-entry, so returning never spends a second call.
 * "Regenerate angles" appears only beside a visible list, where it always
 * has a current generation to act on.
 */
export function AngleSelector({
  angles,
  angleId,
  onSelect,
  showAngles,
  generating = false,
  error = "",
  onGenerate,
  onRegenerate,
  notice = "",
  // The notice's way out, when one exists: { label, onClick, testId }. The
  // regen notice carries "Go to Review and rebuild" — a notice that names a
  // next step without offering it is a dead end. Rendered inside the alert so
  // the action reads as part of the message, not a second decision.
  noticeAction = null,
  onDismissNotice = null,
  // Steps other than Audience & template never generate inline: their red button
  // sends the founder to step 1, where selection lives, instead of spending
  // a call from a screen whose job is something else. The label names the
  // destination so the redirect never reads as a broken Generate.
  generateLabel = "Generate angles",
  generatingLabel = "Generating angles",
  // The video's picked goal, when one is picked. Angle generation aims the
  // fresh set at it; with none picked the set comes back broad, so the
  // step says so beside Regenerate instead of silently spending the call.
  objective = "",
  // Whether the angles in state were generated in-session rather than
  // loaded as cached rows. Only a fresh set is ever revealed free — the
  // honesty rule must never label a stale-cache reveal as anything but what
  // it costs, and a stale cache is not revealed at all: the click
  // regenerates it instead.
  sessionFresh = false,
}) {
  // Live count-up while a generation is in flight ("Reading angle 3 of 6…").
  // It answers the only question a spinner cannot — is this fresh work or a
  // cached list — and it unmounts the moment `generating` clears, so a
  // failure can never leave a frozen count beside the error alert. Capped at
  // the six-row contract; the interval is wall-clock display only, and the
  // rows below still arrive on the endpoint's real response.
  const [genCount, setGenCount] = useState(0);
  const genTimer = useRef(null);
  useEffect(() => {
    if (!generating) {
      setGenCount(0);
      return undefined;
    }
    setGenCount(1);
    genTimer.current = setInterval(() => {
      setGenCount((c) => (c >= 6 ? 6 : c + 1));
    }, 450);
    return () => {
      clearInterval(genTimer.current);
      genTimer.current = null;
    };
  }, [generating]);
  const progressLine = generating ? (
    <p className="text-sm text-muted-foreground" role="status" data-testid="angles-progress">
      Reading angle {genCount} of 6…
    </p>
  ) : null;
  // The gate names what the click will do: generating fresh is a model call
  // with a wait, while revealing a set generated moments ago in-session is
  // instant and free. A cached set from an earlier approval is never offered
  // as a free reveal — the click regenerates it instead — so "Show" can only
  // ever name the fresh set the founder just made. A custom label (Review's
  // redirect off this step) always wins — the honesty rule must never rename
  // a button that leaves the step.
  const gateButtonLabel = generating
    ? generatingLabel
    : generateLabel !== "Generate angles"
      ? generateLabel
      : angles.length > 0 && sessionFresh
        ? "Show your angles"
        : "Generate angles";
  // One line beside the refresh decision, never a number on a row: the set
  // is scanned by name, and only its staleness informs Regenerate. Null
  // (no parseable dates) renders nothing — no claim off a guess. Plain
  // copy, deliberately NOT a data-subtitle: the 55–60 char budget covers
  // label-attached helpers, and a dynamic age cannot hold a fixed length.
  const angleSetFreshness = angleSetAge(angles);

  const body = !showAngles || angles.length === 0 ? (
    // 12px, matching the Review step's "what's missing" panel: the red action
    // and the helper line under it are one gate section, and a tighter stack
    // here made the same ask read as a different control two steps later.
    // The action leads: the copy explains the button, so the button comes
    // first and the explanation follows it.
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button
        variant="accent"
        className="gap-1.5"
        onClick={onGenerate}
        disabled={generating}
        busy={generating}
        progress={generating ? genCount / 6 : null}
        data-testid="generate-angles-button"
      >
        {generating ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Sparkles className="h-3.5 w-3.5" />
        )}
            {gateButtonLabel}
          </Button>
          {progressLine}
      <p className="text-sm text-muted-foreground" data-testid="angles-cta-copy" data-subtitle="">
        {ANGLES_CTA_COPY}
      </p>
        </div>
      ) : (
    <div className="space-y-4" data-testid="audience-angle-list">
      {/* Regeneration for a populated app: the endpoint replaces only
          AI-derived angles and keeps hand-written ones server-side, so this
          cannot discard founder work. */}
      <div className="pt-1">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1.5"
          onClick={onRegenerate}
          disabled={generating}
          busy={generating}
          progress={generating ? genCount / 6 : null}
          data-testid="regenerate-angles-button"
        >
          {generating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          {generating ? "Regenerating angles" : "Regenerate angles"}
            </Button>
            {angleSetFreshness && (
              <p className="text-sm text-muted-foreground" data-testid="angle-set-freshness">
                Refreshed {angleSetFreshness}
              </p>
            )}
            {!objective && (
              <p className="text-sm text-muted-foreground" data-testid="angles-aim-hint" data-subtitle="">
                Pick a goal first — regenerating aims fresh angles at it.
              </p>
            )}
          </div>
          {progressLine}
      {notice && (
        <Alert data-testid="angle-regen-notice">
          <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>
            {notice}
            {(noticeAction || onDismissNotice) && (
              <span className="mt-2 flex flex-wrap gap-2">
                {noticeAction && (
                  <Button
                    variant="accent"
                    size="sm"
                    className="gap-1.5"
                    onClick={noticeAction.onClick}
                    data-testid={noticeAction.testId || "angle-regen-notice-action"}
                  >
                    {noticeAction.label}
                  </Button>
                )}
                {onDismissNotice && (
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={onDismissNotice}
                    data-testid="angle-regen-notice-dismiss"
                  >
                    Dismiss
                  </Button>
                )}
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}
      {/* Selection opens the angle. A closed row is its sentence-case title
          plus its fit pill, so the six compare without opening: the list is
          scanned by name, decided by score, and the picked row then shows
          what the strategy is written from — audience, problem, promise,
          feature, the emotion it aims at, and any claim bounding it. Only
          the picked row opens, because two open panels side by side are
          two half-read angles, and the fields are what the render
          downstream is held to. */}
      {angles.map((a, i) => {
        const picked = angleId === a.id;
        const details = picked ? angleDetails(a) : [];
        const angleVerdicts =
          Math.max(0, Number(a.evidence?.wins) || 0) + Math.max(0, Number(a.evidence?.flops) || 0);
        const angleFit = angleFitScore({
          index: i,
          total: angles.length,
          evidence: a.evidence,
        });
        const angleFitBasis = angleVerdicts
          ? `${angleFit.basis} · at this angle kind`
          : angleFit.basis;
        return (
          // Staggered arrival: each row fades up ~70ms after the previous, so
          // a fresh set is watched arriving instead of blinking in at once.
          // Keyed by row id, so the cascade plays on mount and on genuinely
          // new sets — never on a re-render of the same rows. Collapses to
          // instant under prefers-reduced-motion via .animate-fade-up.
          <div
            key={a.id}
            style={{ animationDelay: `${Math.min(i, 8) * 70}ms` }}
            className={`animate-fade-up overflow-hidden rounded-xl border bg-card/70 ${
              picked
                ? "border-[color:var(--indigo-35)]"
                : "border-[color:var(--hairline)]"
            }`}
          >
            <button
              type="button"
              aria-pressed={picked}
              aria-expanded={picked}
              aria-controls={picked ? `angle-details-${a.id}` : undefined}
              onClick={() => onSelect(a.id)}
              data-testid={`angle-option-${a.id}`}
              className={`flex w-full min-w-0 items-center gap-3 row-pad text-left transition-colors hover:bg-[color:var(--indigo-6)] ${
                picked ? "bg-[color:var(--indigo-6)]" : ""
              }`}
            >
              {/* One check per row, always: muted until picked, indigo once
                  open. The per-kind glyphs are gone — twelve icons made the
                  list something you decode rather than scan. */}
              <Check
                aria-hidden="true"
                data-testid="angle-row-check"
                className={`h-4 w-4 shrink-0 ${
                  picked ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"
                }`}
              />
              <span className="min-w-0 flex-1 truncate text-sm font-semibold">
                {sentenceCase(a.label).replace(/\.\s*$/, "")}
              </span>
              {/* The fittest score rides on the closed row, so the list can be
                  compared without opening any angle — and picking re-shows
                  the same pill on the now-open row rather than a second
                  titled badge, which read one number as two findings. */}
              <span className="shrink-0">
                <FitBadge
                  score={angleFit.score}
                  basis={angleFitBasis}
                  testId={`angle-row-fit-${a.id}`}
                />
              </span>
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
                  picked ? "rotate-180" : ""
                }`}
              />
            </button>
            {picked && details.length > 0 && (
              /* One spec sheet, not a spaced stack: divided rows with the
                  shared eyebrow label and body value, the same language
                  Post copy and History context already read in. */
              <dl
                id={`angle-details-${a.id}`}
                data-testid={`angle-details-${a.id}`}
                className="divide-y divide-[color:var(--hairline)] border-t border-[color:var(--hairline)] row-pad"
              >
                {details.map((row) => (
                  <div key={row.label} className="post-kit-row">
                    <dt className="eyebrow sm:pt-1">{row.label}</dt>
                    <dd className="min-w-0 break-words text-base leading-relaxed text-foreground/90">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
            {/* The picked angle's fields above are read against the same fit
                pill the closed row already carries. Repeating the score in a
                second, titled row below the fields made one number look like
                two findings and added a whole block to the tallest card. */}
          </div>
        );
      })}
    </div>
  );

  return (
    <div className="inset-panel space-y-4">
      <GroupLabel as="label" icon={Target}>
        Audience angle <span className="text-muted-foreground">(required)</span>
      </GroupLabel>
      {body}
    </div>
  );
}

/**  * Goal picker shared by the Audience & template step and Review recovery. Its
 * six angle-conditioned suggestions use the same state, so
 * selecting a goal still triggers the existing template/plan synchronization.
 *
 * Each card shows the goal's general outcome plus an optional angle-specific
 * fit line explaining why that goal suits the selected angle. The fit line is
 * explanatory text only: it never changes selection, ranking, or saving.
 *
 * It picks a GOAL, never an angle. It used to fall back to its own plain list
 * of angle names when none was picked, which is the second implementation
 * `AngleSelector` above replaced — that fallback now renders only the waits
 * marker, and the step above it owns choosing the angle.
 */
export function AngleGoalPicker({
  angle,
  value,
  onPick,
  options,
  recommendations,
  outcomes,
  fitReasons,
  objectiveEvidence = {},
  pairEvidence = {},
  // The six suggestions in the angle's profile-tailored PERSISTED variant
  // order, from the server (angle.goal_suggestions). Falls back to the
  // static facet list when the angle row carries none.
  suggestions,
  onRegenerate,
  regenerating = false,
}) {
  const knownGoals = Array.isArray(options) ? options : [];
  const orderedGoals =
    Array.isArray(suggestions) && suggestions.length > 0
      ? suggestions.filter((goal) => knownGoals.includes(goal))
      : [];
  const rankedGoals = orderedGoals.length > 0
    ? orderedGoals
    : (recommendations || []).filter((goal) => knownGoals.includes(goal));
  const featured = [...new Set([...rankedGoals, ...knownGoals])].slice(0, 6);
  const outsideRecommendation = Boolean(value && !featured.includes(value));

  // Live count-up while the six reshuffle ("Shuffling goal 3 of 6…"). Same
  // contract as the angle count-up: narrates fresh work, unmounts on settle
  // or error, capped at the visible total so it never over-counts.
  const [shuffleCount, setShuffleCount] = useState(0);
  const shuffleTimer = useRef(null);
  const shuffleTotal = Math.max(featured.length, 1);
  useEffect(() => {
    if (!regenerating) {
      setShuffleCount(0);
      return undefined;
    }
    setShuffleCount(1);
    shuffleTimer.current = setInterval(() => {
      setShuffleCount((c) => (c >= shuffleTotal ? shuffleTotal : c + 1));
    }, 450);
    return () => {
      clearInterval(shuffleTimer.current);
      shuffleTimer.current = null;
    };
  }, [regenerating, shuffleTotal]);

  if (!angle) {
    /* The waits marker, and nothing to read in it: no goal button may render
       before an angle exists, and this is what the smoke suite asserts in
       their place. The red jump back lives in the owning panel, never here —
       one gap, one button, or two missing prerequisites render two competing
       "first" actions. */
    return <div data-testid="goal-waits-for-angle" />;
  }

  return (
    <section className="space-y-4" aria-labelledby="video-goal-label" data-testid="angle-goal-picker">
      <div className="space-y-1">
        <div className="flex items-start justify-between gap-2">
          <GroupLabel as="h3" icon={Target} id="video-goal-label">
            Video goal <span className="text-muted-foreground">(required)</span>
          </GroupLabel>
          <div className="flex shrink-0 items-center gap-1.5">
            {onRegenerate && featured.length > 0 && (
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={onRegenerate}
                disabled={regenerating}
                busy={regenerating}
                progress={regenerating ? shuffleCount / shuffleTotal : null}
                title="Same six suggestions, a different ranking. Shuffling never changes the six goals — regenerate angles for genuinely new direction. Your selection is kept."
                data-testid="regenerate-goals-button"
              >
                {regenerating ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RefreshCw className="h-3.5 w-3.5" />
                )}
                {regenerating ? "Shuffling goals" : "Shuffle"}
              </Button>
            )}
          </div>
        </div>
        <p className="text-sm text-muted-foreground">
          {featured.length > 0
            ? `${featured.length === 6 ? "Six" : featured.length} suggestions for “${angle.label}”.`
            : `Goal suggestions for “${angle.label}” are unavailable. Try reloading the page.`}{" "}
          The angle shapes this video — the goal shapes the campaign it serves.
        </p>
      </div>
      {regenerating && (
        <p className="text-sm text-muted-foreground" role="status" data-testid="goals-progress">
          Shuffling goal {shuffleCount} of {shuffleTotal}…
        </p>
      )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" role="group" aria-label={`Recommended video goals for ${angle.label}`} data-testid="goals-grid">
        {featured.map((goal, index) => {
          const selected = value === goal;
          // 0–10 fit for this goal under the selected angle: annotates the
          // card, never reorders the six. Rank is this angle's persisted
          // suggestion order, tally is the goal's own win share.
          const fit = goalFitScore({
            index,
            total: featured.length,
            evidence: objectiveEvidence?.[goal],
            hasFitReason: Boolean(fitReasons?.[goal]),
          });
          return (
            // Staggered arrival, same language as the angle rows: a fresh
            // order is watched arriving instead of blinking in at once. Keyed
            // by goal, so only genuinely new sets replay it.
            <button
              key={goal}
              type="button"
              aria-pressed={selected}
              data-testid={`recommended-goal-${goal}`}
              onClick={() => onPick(goal)}
              style={{ animationDelay: `${Math.min(index, 8) * 70}ms` }}
              className={`card-pickable animate-fade-up w-full rounded-xl border p-4 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-35)] ${
                selected
                  ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                  : "border-[color:var(--hairline)]"
              }`}
            >
              <span className="flex items-center justify-between gap-2 text-sm font-semibold">
                {humanize(goal)}
                <span className="flex shrink-0 items-center gap-1.5">
                  <FitBadge score={fit.score} basis={fit.basis} testId={`goal-fit-score-${goal}`} />
                  {selected && <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />}
                </span>
              </span>
              {outcomes?.[goal] && (
                <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">
                  {sentenceCase(outcomes[goal])}
                </span>
              )}
              {/* One descriptive line stays visible: the outcome when there is
                  one, otherwise the fit reason. The fit reason behind an
                  outcome, plus both verdict counts, tuck into a disclosure so
                  six cards scan instead of shouting. Every testid stays in the
                  DOM either way. */}
              {!outcomes?.[goal] && fitReasons?.[goal] && (
                <span
                  data-testid={`goal-fit-${goal}`}
                  className="mt-1 block text-sm leading-relaxed text-muted-foreground"
                >
                  {sentenceCase(fitReasons[goal])}
                </span>
              )}
              {(Boolean(outcomes?.[goal] && fitReasons?.[goal]) ||
                formatVerdicts(angle?.evidence) ||
                formatVerdicts(objectiveEvidence?.[goal]) ||
                formatVerdicts(pairEvidence?.[`${angle?.kind}‖${goal}`])) && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-sm text-muted-foreground">
                    Why this goal fits
                  </summary>
                  <div className="mt-1 space-y-1">
                    {outcomes?.[goal] && fitReasons?.[goal] && (
                      <span
                        data-testid={`goal-fit-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {sentenceCase(fitReasons[goal])}
                      </span>
                    )}
                    {/* Founder verdicts for the selected angle's KIND, carried on the
                        angle row too. Shown only as counts so one verdict never reads
                        as a verdict on the goal itself; the six stay in fetched order. */}
                    {formatVerdicts(angle?.evidence) && (
                      <span
                        data-testid={`goal-angle-evidence-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {formatVerdicts(angle.evidence)} at this angle kind
                      </span>
                    )}
                    {/* Objective-level tally: wins/flops per GOAL, shared across kinds.
                        Same counts, same styling, different axis — the goal picker is
                        the surface where the objective axis answers "what wins here". */}
                    {formatVerdicts(objectiveEvidence?.[goal]) && (
                      <span
                        data-testid={`goal-objective-evidence-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {formatVerdicts(objectiveEvidence[goal])} for this goal
                      </span>
                    )}
                    {/* Intersection tally: this KIND for this GOAL. The most
                        specific evidence on the card — a proven pairing names
                        what neither axis alone can. Same counts, same styling. */}
                    {formatVerdicts(pairEvidence?.[`${angle?.kind}‖${goal}`]) && (
                      <span
                        data-testid={`goal-pair-evidence-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {formatVerdicts(pairEvidence[`${angle.kind}‖${goal}`])} for this pairing
                      </span>
                    )}
                  </div>
                </details>
              )}
              {index === 0 && <span className="sr-only">Best fit suggestion. </span>}
            </button>
          );
        })}
      </div>
      {outsideRecommendation && (
        <p className="text-sm text-muted-foreground" data-testid="goal-outside-recommendations">
          Your current goal, {humanize(value)}, is outside these six suggestions. It stays selected unless you choose a suggested goal.
        </p>
      )}
    </section>
  );
}
