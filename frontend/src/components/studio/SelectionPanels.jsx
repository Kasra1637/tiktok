import { Button } from "../ui/button";

import { Badge } from "../ui/badge";
import { Alert, AlertDescription } from "../ui/alert";

import { GroupLabel } from "../SectionCard";

import { FitBadge } from "../FitBadge";

import { sentenceCase } from "../../lib/copyCase";
import { angleDetails, angleFitScore, formatVerdicts, goalFitScore } from "../../lib/angleSubtitle";
import { angleSetAge } from "../../lib/angleFreshness";
import { BUSY_ETA_SECONDS } from "../../lib/busyEta";
import {
  readPieceSeconds,
  sectionSplit,
  clampHookSeconds,
  DEFAULT_HOOK_SECONDS,
} from "../../lib/videoLength";
import { TriangleAlert as AlertTriangle, Target, Check, Sparkles, RefreshCw, ChevronDown } from "lucide-react";

/* The single instruction for the angle picker, shared by the empty state
   (click generates the six) and the reveal state (click shows the six).
   One line on purpose: three stacked explanations said the same thing in
   different words, and the step stalled on reading instead of moving. The
   verb is deliberately neutral — "get" covers generating fresh angles and
   revealing pre-generated ones, so the line never disagrees with its button. */
const ANGLES_CTA_COPY = "Get your six audience angles, then pick one to move forward.";

/* The single instruction for the goal picker, shared by the empty state
   (click generates the six) and the reveal state (click shows the six).
   One line on purpose: three stacked explanations said the same thing in
   different words, and the step stalled on reading instead of moving. The
   verb is deliberately neutral — "get" covers generating fresh goals and
   revealing pre-generated ones, so the line never disagrees with its button. */
const GOALS_CTA_COPY = "Get your six video goals for this angle, then pick one to move forward.";

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
  // The opening the founder will see (ADR 0089). It is built from the angle's
  // First 3 Seconds Promise server-side, so this line and the "In your video"
  // line below it describe ONE opening rather than two. A response without the
  // server-composed shape (an older stub) falls back to the template's own
  // opening structure, as before.
  const shapeLine =
    typeof scene.shape === "string" && scene.shape.trim()
      ? scene.shape.trim()
      : "";
  const opening = shapeLine || (
    typeof r.template.opening_structure === "string" && r.template.opening_structure.trim()
      ? sentenceCase(r.template.opening_structure.trim())
      : ""
  );
  // Where and when that one opening happens, and that the person on screen is
  // the founder's own uploaded photo — never a described face or a named kind
  // of person. Falls back to the bare moment when the server did not send it.
  const staging =
    typeof scene.staging === "string" && scene.staging.trim()
      ? scene.staging.trim()
      : "";
  // What THIS template does next, as its own line: the shape is the promise,
  // so the template's development can never read as a second opening.
  const development =
    typeof scene.development === "string" && scene.development.trim()
      ? scene.development.trim()
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
      {development && (
        <p className="mt-1 text-sm text-foreground/80" data-testid="template-development">
          <span className="text-muted-foreground">Develops as: </span>
          {development}
        </p>
      )}
      {moment && !misfit && (
        <p className="mt-1 text-sm text-foreground/80" data-testid="template-angle-moment">
          <span className="text-muted-foreground">In your video: </span>
          {staging || moment}
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
export function TemplateShape({ template, middle: actualMiddle = "" }) {
  const total = readPieceSeconds(null, template);
  const hook = clampHookSeconds(template?.hook_seconds) || DEFAULT_HOOK_SECONDS;
  const split = sectionSplit(total, hook);
  // Once a plan exists, the middle THIS video speaks is the approved script,
  // never the template's generic middle about a different video (ADR 0108).
  const spokenMiddle = String(actualMiddle || "").trim();
  const middle = spokenMiddle
    ? spokenMiddle.split(/(?<=[.!?])\s+/)[0]
    : middleStructure(template);
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
  // The approved hook line, when a plan already exists. The picked angle's
  // "First 3 seconds promise" row then quotes what the video actually opens
  // with, never the angle's paraphrase promising unspoken words (ADR 0108).
  hookLine = "",
}) {
  // Processing lives on the button itself: busy paints the looping sweep and
  // the label names the work concisely ("Generating angles"). The sweep loops
  // because the wait length is unknowable — a counted fill would freeze at
  // full long before the call settles, unlike every other CTA on the step.
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
        etaSeconds={BUSY_ETA_SECONDS.angles}
        data-testid="generate-angles-button"
      >
        <Sparkles className="h-3.5 w-3.5" />
            {gateButtonLabel}
          </Button>
          {!generating && (
            <p className="text-sm text-muted-foreground" data-testid="angles-cta-copy" data-subtitle="">
              {ANGLES_CTA_COPY}
            </p>
          )}
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
          etaSeconds={BUSY_ETA_SECONDS.angles}
          data-testid="regenerate-angles-button"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          {generating ? "Regenerating angles" : "Regenerate angles"}
            </Button>
            {angleSetFreshness && !generating && (
              <p className="text-sm text-muted-foreground" data-testid="angle-set-freshness">
                Refreshed {angleSetFreshness}
              </p>
            )}
            {!objective && !generating && (
              <p className="text-sm text-muted-foreground" data-testid="angles-aim-hint" data-subtitle="">
                Pick a goal first — regenerating aims fresh angles at it.
              </p>
            )}
          </div>
      {notice && (
        <Alert variant="warning" data-testid="angle-regen-notice">
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
        const details = picked ? angleDetails(a, hookLine) : [];
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

/**
 * Goal picker shared by the Audience & template step and Review recovery. Its
 * six angle-conditioned suggestions use the same state, so
 * selecting a goal still triggers the existing template/plan synchronization.
 *
 * Landing is always gated: one "Generate goals" action, never a finished
 * list. The first click always generates fresh — the facet-ordered
 * `suggestions` fallback from the server is never rendered as the initial
 * list, so a new video never lands on auto-populated goals. A set generated
 * moments ago in-session is then revealed free on step re-entry, so returning
 * never spends a second call. "Shuffle" appears only beside a visible list,
 * where it always has a current generation to act on.
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
  // static facet list when the angle row carries none. Kept for the Review
  // recovery call sites and for the pre-generate fallback copy inspection,
  // but never rendered as the initial list — the gate owns first view.
  suggestions,
  // Live goals generated on the founder's click, each
  // {name, description, why_it_fits, fit_score}. Null until generated: the
  // panel shows the gate in the meantime (and on failure keeps it).
  liveGoals = null,
  showGoals = false,
  onGenerate,
  generating = false,
  generationError = null,
  onRegenerate,
  regenerating = false,
}) {
  const knownGoals = Array.isArray(options) ? options : [];
  const liveByName = {};
  if (Array.isArray(liveGoals)) {
    liveGoals.forEach((g) => {
      if (g && g.name) liveByName[g.name] = g;
    });
  }
  const liveOrdered =
    Array.isArray(liveGoals) && liveGoals.length > 0
      ? liveGoals.map((g) => g.name).filter((goal) => knownGoals.includes(goal))
      : [];
  const orderedGoals =
    liveOrdered.length > 0
      ? liveOrdered
      : Array.isArray(suggestions) && suggestions.length > 0
        ? suggestions.filter((goal) => knownGoals.includes(goal))
        : [];
  const rankedGoals = orderedGoals.length > 0
    ? orderedGoals
    : (recommendations || []).filter((goal) => knownGoals.includes(goal));
  // The reveal gate (the goals analogue of the angles gate above): the list
  // is visible only when the founder clicked Generate (showGoals / liveGoals)
  // or when a goal is already picked (a draft or deep link that already names
  // one has been viewed by definition). The facet-ordered `suggestions` /
  // `recommendations` lists are never shown on first view — they are the
  // auto-populated output the gate exists to withhold. A draft whose only
  // goals come from the facet list still renders them once a goal is picked,
  // so resuming never strands the founder on an empty required control.
  const revealed = showGoals || Boolean(value) || (Array.isArray(liveGoals) && liveGoals.length > 0);
  const featured = revealed
    ? [...new Set([...rankedGoals, ...knownGoals])].slice(0, 6)
    : [];
  const outsideRecommendation = Boolean(value && !featured.includes(value));
  const liveOutcomes = {};
  const liveFitReasons = {};
  const liveScores = {};
  if (Array.isArray(liveGoals)) {
    liveGoals.forEach((g) => {
      if (!g || !g.name) return;
      if (g.description) liveOutcomes[g.name] = g.description;
      if (g.why_it_fits) liveFitReasons[g.name] = g.why_it_fits;
      if (Number.isFinite(Number(g.fit_score))) liveScores[g.name] = g.fit_score;
    });
  }
  const shownOutcomes = { ...(outcomes || {}), ...liveOutcomes };
  const shownFitReasons = { ...(fitReasons || {}), ...liveFitReasons };
  // Fit badge: when a live fit_score exists for this goal/angle, use it —
  // that's the model's per-angle, per-goal measurement of alignment. When no
  // score exists, render NO badge rather than summing thumbs across all goals
  // of that kind (satisfaction arithmetic is not alignment).
  const _fitFor = (goal, index) => {
    const liveScore = liveScores?.[goal];
    if (Number.isFinite(Number(liveScore))) {
      const score = Math.min(10, Math.max(0, Math.floor(Number(liveScore))));
      return { score, basis: `fit ${score} of 10 for this angle` };
    }
    return null;
  };

  // Shuffling is a free reshuffle of the same six — the button's busy label
  // and looping sweep carry the wait, like every other CTA on this step. A
  // counted fill would freeze at full long before the reshuffle settles.

  if (!angle) {
    /* The waits marker, and nothing to read in it: no goal button may render
       before an angle exists, and this is what the smoke suite asserts in
       their place. The red jump back lives in the owning panel, never here —
       one gap, one button, or two missing prerequisites render two competing
       "first" actions. */
    return <div data-testid="goal-waits-for-angle" />;
  }

  // The gate names what the click will do: generating fresh is a model call
  // with a wait. The label is intentionally neutral — "Get your six video
  // goals" covers generating fresh goals and revealing an in-session set, so
  // the line never disagrees with its button. A custom label (Review's
  // redirect off this step) is not used by the goal picker call sites, but
  // the honesty rule would always win.
  const gateButtonLabel = generating ? "Generating goals" : "Generate goals";

  const body = !revealed ? (
    <div className="space-y-4">
      {generationError && (
        <Alert variant="destructive" data-testid="goals-generation-error">
          <AlertDescription>{generationError}</AlertDescription>
        </Alert>
      )}
      <Button
        variant="accent"
        className="gap-1.5"
        onClick={onGenerate}
        disabled={generating}
        busy={generating}
        data-testid="generate-goals-button"
      >
        <Sparkles className="h-3.5 w-3.5" />
        {gateButtonLabel}
      </Button>
      {!generating && (
        <p className="text-sm text-muted-foreground" data-testid="goals-cta-copy" data-subtitle="">
          {GOALS_CTA_COPY}
        </p>
      )}
    </div>
  ) : (
  <div className="space-y-4">
    {generationError && (
      <p className="text-sm text-destructive" role="alert" data-testid="goals-generation-error">
        {generationError} The suggested goals below are unchanged.
      </p>
    )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" role="group" aria-label={`Recommended video goals for ${angle.label}`} data-testid="goals-grid">
        {featured.map((goal, index) => {
          const selected = value === goal;
          // 0–10 fit for this goal under the selected angle: annotates the
          // card, never reorders the six. Rank is this angle's persisted
          // suggestion order, tally is the goal's own win share. A live-goal
          // fit_score replaces the computed score; when no score exists, no
          // badge renders rather than summing thumbs.
          const fit = _fitFor(goal, index);
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
                  {fit && <FitBadge score={fit.score} basis={fit.basis} testId={`goal-fit-score-${goal}`} />}
                  {selected && <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />}
                </span>
              </span>
              {shownOutcomes?.[goal] && (
                <span className="mt-1 block text-sm leading-relaxed text-muted-foreground">
                  {sentenceCase(shownOutcomes[goal])}
                </span>
              )}
              {/* One descriptive line stays visible: the outcome when there is
                  one, otherwise the fit reason. The fit reason behind an
                  outcome, plus both verdict counts, tuck into a disclosure so
                  six cards scan instead of shouting. Every testid stays in the
                  DOM either way. */}
              {!shownOutcomes?.[goal] && shownFitReasons?.[goal] && (
                <span
                  data-testid={`goal-fit-${goal}`}
                  className="mt-1 block text-sm leading-relaxed text-muted-foreground"
                >
                  {sentenceCase(shownFitReasons[goal])}
                </span>
              )}
              {(Boolean(shownOutcomes?.[goal] && shownFitReasons?.[goal]) ||
                formatVerdicts(angle?.evidence) ||
                formatVerdicts(objectiveEvidence?.[goal]) ||
                formatVerdicts(pairEvidence?.[`${angle?.kind}‖${goal}`])) && (
                <details className="mt-1">
                  <summary className="cursor-pointer text-sm text-muted-foreground">
                    Why this goal fits
                  </summary>
                  <div className="mt-1 space-y-1">
                    {shownOutcomes?.[goal] && shownFitReasons?.[goal] && (
                      <span
                        data-testid={`goal-fit-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {sentenceCase(shownFitReasons[goal])}
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
  </div>
  );

  return (
    <section className="space-y-4" aria-labelledby="video-goal-label" data-testid="angle-goal-picker">
      <div className="space-y-1">
        <div className="flex items-start justify-between gap-2">
          <GroupLabel as="h3" icon={Target} id="video-goal-label">
            Video goal <span className="text-muted-foreground">(required)</span>
          </GroupLabel>
          {onRegenerate && revealed && featured.length > 0 && (
            <div className="flex shrink-0 items-center gap-1.5">
              <Button
                variant="ghost"
                size="sm"
                className="gap-1.5 shrink-0"
                onClick={onRegenerate}
                disabled={regenerating}
                busy={regenerating}
                title="Same six suggestions, a different ranking. Shuffling never changes the six goals — regenerate angles for genuinely new direction. Your selection is kept."
                data-testid="regenerate-goals-button"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                {regenerating ? "Shuffling goals" : "Shuffle"}
              </Button>
            </div>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {revealed && featured.length > 0
            ? `${featured.length === 6 ? "Six" : featured.length} suggestions for “${angle.label}”.`
            : `Goal suggestions for “${angle.label}” are ready when you click.`}{" "}
          The angle shapes this video — the goal shapes the campaign it serves.
        </p>
      </div>
      {body}
    </section>
  );
}
