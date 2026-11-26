import { useEffect, useState } from "react";
import { createPortal } from "react-dom";

import { Button } from "../ui/button";

import { Badge } from "../ui/badge";
import { Alert, AlertDescription } from "../ui/alert";

import { GroupLabel, SectionHeading } from "../SectionCard";

import { FitBadge } from "../FitBadge";

import { sentenceCase } from "../../lib/copyCase";
import { angleDetails, angleFitScore, formatVerdicts, goalFitScore } from "../../lib/angleSubtitle";
import { angleSetAge } from "../../lib/angleFreshness";
import { BUSY_ETA_SECONDS } from "../../lib/busyEta";
import { TriangleAlert as AlertTriangle, Target, Check, Sparkles, RefreshCw, Maximize2, X, Image as ImageIcon } from "lucide-react";

import AssetLibrary from "../../pages/AssetLibrary";

/* ADR 0367: the angle and goal pickers' shared CTA copy lines are
   removed — the gate buttons name their own action, and a standing
   line under each only restated it. The empty states now stand on
   their buttons alone. */

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
 * One fixed skeleton on every card (ADR 0309, Kasra's order): the same slots
 * in the same order with the same styling from top to bottom — name, badges,
 * outcome, example, shape, develops, moment, verdict — whether or not a slot
 * carries text. A slot with nothing to say holds its line empty rather than
 * collapsing, so a missing field never reshapes the card; the name reserves
 * two lines and the outcome two, the verdict block anchors to the card's
 * foot, and every card in the row stands at the row's height. Text itself is
 * never cut to fit: a longer line simply takes its lines, the way the house
 * equal-height pattern (profileUi) already rules.
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
      className={`card-pickable animate-fade-up flex h-full w-full flex-col rounded-xl border p-4 text-left ${
        selected
          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
          : "border-[color:var(--hairline)]"
      }`}
    >
      <div>
        <span className="block min-h-12 text-base font-semibold" data-slot="name">
          {r.template.name}
        </span>
        <span className="mt-1 flex flex-wrap items-center gap-2" data-slot="badges">
          <Badge variant="secondary" className="text-xs">
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
      {/* The fixed skeleton (ADR 0309): every slot renders on every card, in
          this order, with this styling. A slot whose field is empty holds its
          line blank — the testid rides only on a slot carrying text, so the
          checks keep reading "the line that says it" exactly as before. */}
      <p
        className="mt-1 min-h-12 text-base text-foreground/90"
        data-slot="outcome"
        {...(outcome ? { "data-testid": "template-outcome" } : {})}
      >
        {outcome}
      </p>
      <p className="mt-1 min-h-5 text-sm text-foreground/80" data-slot="example">
        {example && (
          <>
            <span className="text-muted-foreground">Sounds like: </span>
            &ldquo;{example}&rdquo;
          </>
        )}
      </p>
      <p
        className="mt-1 min-h-5 text-sm text-muted-foreground"
        data-slot="shape"
        {...(opening ? { "data-testid": "template-structure" } : {})}
      >
        {opening && (
          <>
            <span className="text-muted-foreground">Shape: </span>
            {opening}
          </>
        )}
      </p>
      <p
        className="mt-1 min-h-5 text-sm text-foreground/80"
        data-slot="develops"
        {...(development ? { "data-testid": "template-development" } : {})}
      >
        {development && (
          <>
            <span className="text-muted-foreground">Develops as: </span>
            {development}
          </>
        )}
      </p>
      {misfit ? (
        <p
          className="mt-1 min-h-5 text-sm font-semibold text-foreground"
          data-slot="moment"
          data-testid="template-angle-misfit"
        >
          {misfit}
        </p>
      ) : (
        <p
          className="mt-1 min-h-5 text-sm text-foreground/80"
          data-slot="moment"
          {...(moment ? { "data-testid": "template-angle-moment" } : {})}
        >
          {moment && (
            <>
              <span className="text-muted-foreground">In your video: </span>
              {staging || moment}
            </>
          )}
        </p>
      )}
      {/* The verdict block anchors to the foot of the card (mt-auto), so the
          WHY IT FITS lines up across the row however the middle slots ran. */}
      <div className="mt-auto space-y-2 pt-2" data-slot="verdict">
        <p className="eyebrow">Why it fits</p>
        {/* The verdict: the strongest match, in body weight with the same
            tick the step pills use for "positive", so it reads as the reason
            rather than one of several. */}
        {verdict ? (
          <p
            className="flex items-start gap-1.5 text-base text-foreground"
            data-testid="template-fit-verdict"
          >
            <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span>{sentenceCase(verdict)}</span>
          </p>
        ) : (
          <p className="min-h-6" aria-hidden="true" />
        )}
      </div>
      {/* Supporting detail and limitations tuck into a disclosure: the card
          leads with its verdict, and the rest opens on demand. The verdict
          stays outside any list, and a single-reason card with no limits
          renders no disclosure at all. */}
      {(detail.length > 0 || limits.length > 0 || formatVerdicts(r.verdict_evidence)) && (
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
            {/* Whole-video verdicts for this TEMPLATE (ADR 0127): the
                founder's up/down calls on finished videos that went out
                with this template, tallied from the frozen bundles. Same
                counts, same styling as the goal cards' verdict lines —
                the signal that now ranks this card, shown on it. */}
            {formatVerdicts(r.verdict_evidence) && (
              <span
                data-testid={`template-verdict-evidence-${r.template.id}`}
                className="block text-sm leading-relaxed text-muted-foreground"
              >
                {formatVerdicts(r.verdict_evidence)} at this template
              </span>
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
 * The studio's angle-selection control. It lives on Audience & template —
 * the one place selection happens. Review & submit never hosts a copy of
 * this list: since ADR 0229 it names a missing angle in words and the
 * founder walks back by the rail segments or the sticky bar.
 *
 * On Audience & template the list renders on open: a founder whose app
 * already has angles lands on the four themselves, not on a click-to-reveal
 * gate (Part 3 removed that click — it cost a press on every fresh project
 * and bought nothing the list does not say itself). The set's age still
 * rides beside Regenerate, so a stale set reads as stale in plain view
 * rather than being hidden behind a button. Only an empty set shows the
 * "Generate angles" action, where the click is the generation itself.
 *
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
  onDismissNotice = null,
  // The empty set's one action is the generation itself, on this step —
  // the only step that generates angles. Steps whose job is something
  // else never host this control at all (ADR 0229).
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
  // The gated landing form, kept only for the Review recovery copy (see
  // the docstring above): the list stays behind the red action there,
  // shown only when `showAngles` says the founder has viewed it. The
  // Audience & template step never passes this — its list renders on open.
  landingGate = false,
  // The approved hook line, when a plan already exists. The picked angle's
  // "First 3 seconds promise" row then quotes what the video actually opens
  // with, never the angle's paraphrase promising unspoken words (ADR 0108).
  hookLine = "",
  // The draft's saved camera setup. For a fixed camera the rows already
  // arrive restated indoors from the server (ADR 0233); this prop only
  // drives the note that says so, so the founder is never left guessing
  // why an angle they wrote outdoors now reads as a room — and never
  // has to re-pick an angle to satisfy the setup.
  cameraSetup = "",
}) {
  // Angle details open in a centered pop-up over the whole page
  // (ADR 0330, as corrected at Kasra's live review): picking a row
  // selects the angle and opens its spec sheet in a fixed, centered
  // layer above every other element, so no card ever grows and the
  // two-up rows stay even. The pop-up is keyed by angle id — picking
  // another row moves it, re-picking the same row closes it, and
  // Escape, the backdrop, or the close button closes it too.
  const [popoverId, setPopoverId] = useState(null);
  useEffect(() => {
    if (!popoverId) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") setPopoverId(null);
    };
    const onDown = (event) => {
      if (!event.target.closest("[data-angle-popover-root]")) setPopoverId(null);
    };
    document.addEventListener("keydown", onKey);
    document.addEventListener("mousedown", onDown);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("mousedown", onDown);
    };
  }, [popoverId]);
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

  const openAngle = angles.find((a) => a.id === popoverId) || null;
  const openDetails = openAngle ? angleDetails(openAngle, hookLine) : [];
  const body = angles.length === 0 || (landingGate && !showAngles) ? (
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
        </div>
      ) : (
    <div className="space-y-4" data-testid="audience-angle-list">
      {/* Regeneration for a populated app: the endpoint replaces only
          AI-derived angles and keeps hand-written ones server-side, so this
          cannot discard founder work. */}
      <div className="pt-1">
        {/* ADR 0372 (Kasra's order): the freshness-and-hint line
            stands ABOVE the Regenerate button, right under the
            "Audience angle (required)" heading, and the hint is
            rewritten punchier and plainer — same meaning (pick a
            goal first; regenerating aims the fresh angles at it),
            58 chars inside the data-subtitle budget. The stamp,
            the separator and the one-line shape (ADR 0291) are
            unchanged, and the fixed-camera indoor note still
            stands below the button. */}
        {(angleSetFreshness || !objective) && !generating && (
          <div className="flex flex-wrap items-baseline gap-x-2">
            {angleSetFreshness && (
              <p className="text-sm text-muted-foreground" data-testid="angle-set-freshness">
                Refreshed {angleSetFreshness}
              </p>
            )}
            {angleSetFreshness && !objective && (
              <span aria-hidden="true" className="text-sm text-muted-foreground">·</span>
            )}
            {!objective && (
              <p className="text-sm text-muted-foreground" data-testid="angles-aim-hint" data-subtitle="">
                Pick your goal first — new angles will aim straight at it.
              </p>
            )}
          </div>
        )}
        <Button
          variant="secondary"
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
        {cameraSetup === "fixed" && !generating && (
          <p className="text-sm text-muted-foreground" data-testid="angles-fixed-indoor-note">
            With the fixed camera, these angles are staged indoors — an outdoor place shows as its indoor version.
          </p>
        )}
      </div>
      {notice && (
        <Alert variant="warning" data-testid="angle-regen-notice">
          <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>
            {notice}
            {onDismissNotice && (
              <span className="mt-2 flex flex-wrap gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={onDismissNotice}
                  data-testid="angle-regen-notice-dismiss"
                >
                  Dismiss
                </Button>
              </span>
            )}
          </AlertDescription>
        </Alert>
      )}
      {/* Selection opens the angle's details in a centered pop-up
          (ADR 0330). A closed row is its sentence-case title plus its
          fit pill, so the set compares without opening: the list is
          scanned by name, decided by score, and the pop-out icon at
          the row's right edge says the details open as a pop-up —
          audience, problem, promise, feature, the emotion it aims
          at, and any claim bounding it — never as an inline
          expansion, so no card grows and no row-mate is left with a
          dead stretch beneath it. The pop-up itself renders after
          the grid, below. */}
      {/* Two-up from lg (ADR 0328): a full-width row left a dead stretch
          between the title and the fit pill stranded at its far right.
          The cards stand in the same two-up grid rule as the step's
          template cards, each keeping its own height. Below lg the
          stack stands. */}
      <div className="grid grid-cols-1 items-start gap-4 lg:grid-cols-2" data-testid="angle-card-grid">
      {angles.map((a, i) => {
        const picked = angleId === a.id;
        const angleVerdicts =
          Math.max(0, Number(a.evidence?.wins) || 0) + Math.max(0, Number(a.evidence?.flops) || 0);
        const angleFit = angleFitScore({
          index: i,
          total: angles.length,
          evidence: a.evidence,
          contentFit: a.content_fit,
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
            className="animate-fade-up relative"
            data-angle-popover-root=""
          >
            <div
              className={`overflow-hidden rounded-xl border bg-card/70 ${
                picked
                  ? "border-[color:var(--indigo-35)]"
                  : "border-[color:var(--hairline)]"
              }`}
            >
            <button
              type="button"
              aria-pressed={picked}
              aria-haspopup="dialog"
              aria-expanded={popoverId === a.id}
              aria-controls={popoverId === a.id ? `angle-popover-${a.id}` : undefined}
              onClick={() => {
                onSelect(a.id);
                setPopoverId((current) => (current === a.id ? null : a.id));
              }}
              data-testid={`angle-option-${a.id}`}
              className={`flex w-full min-w-0 items-center gap-3 row-pad angle-option-row text-left transition-colors ${
                picked ? "bg-[color:var(--indigo-6)]" : ""
              }`}
            >
              {/* The fit pill leads the row (Kasra's ruling, Nov 25
                  2026): the check mark that used to open every row is
                  gone, and the score stands in its seat, so the list
                  is scanned by score first and name second. The
                  picked row still reads by its indigo wash and
                  border; only the pop-out icon stands at the right. */}
              <span className="shrink-0">
                <FitBadge
                  score={angleFit.score}
                  basis={angleFitBasis}
                  testId={`angle-row-fit-${a.id}`}
                />
              </span>
              <span className="min-w-0 truncate text-sm font-semibold">
                {sentenceCase(a.label).replace(/\.\s*$/, "")}
              </span>
              <Maximize2
                aria-hidden="true"
                data-testid="angle-row-popover-icon"
                className="ml-auto h-4 w-4 shrink-0 text-muted-foreground"
              />
            </button>
            </div>
            {/* The picked angle's fields above are read against the same fit
                pill the closed row already carries. Repeating the score in a
                second, titled row below the fields made one number look like
                two findings and added a whole block to the tallest card. */}
          </div>
        );
      })}
      </div>
      {openAngle && openDetails.length > 0 && createPortal(
        /* The spec sheet as a centered pop-up (ADR 0330, as corrected
           at Kasra's live review): a fixed layer over the whole page,
           the sheet wide and centered, standing above every other
           element. The anchored popover it replaces sat inside the
           card's own stacking layer — every card in the step arrives
           with a fade-up transform — so the goal cards and badges
           after the angles painted straight over it. A backdrop
           click puts it away, with the close button and Escape.
           ADR 0341: the layer renders through a portal on the
           document body, like the tour overlay — a fixed layer
           alone stays trapped inside whichever ancestor carries
           a transform, and dims only that section of the screen. */
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center p-4"
          data-angle-popover-root=""
        >
          <div
            aria-hidden="true"
            className="absolute inset-0 pop-scrim"
            onClick={() => setPopoverId(null)}
          />
          <div
            id={`angle-popover-${openAngle.id}`}
            data-testid={`angle-popover-${openAngle.id}`}
            role="dialog"
            aria-modal="true"
            aria-label={`${sentenceCase(openAngle.label).replace(/\.\s*$/, "")} details`}
            className="relative max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[color:var(--hairline)] bg-card shadow-lg"
          >
            <div className="flex items-center justify-between gap-2 border-b border-[color:var(--hairline)] row-pad">
              <span className="min-w-0 truncate text-sm font-semibold">
                {sentenceCase(openAngle.label).replace(/\.\s*$/, "")}
              </span>
              <button
                type="button"
                aria-label="Close angle details"
                data-testid={`angle-popover-close-${openAngle.id}`}
                onClick={() => setPopoverId(null)}
                className="shrink-0 text-muted-foreground"
              >
                <X aria-hidden="true" className="h-4 w-4" />
              </button>
            </div>
            <dl
              data-testid={`angle-details-${openAngle.id}`}
              className="divide-y divide-[color:var(--hairline)] row-pad"
            >
              {openDetails.map((row) => (
                <div key={row.label} className="post-kit-row">
                  <dt className="eyebrow sm:pt-1">{row.label}</dt>
                  <dd className="min-w-0 break-words text-base leading-relaxed text-foreground/90">
                    {row.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        </div>,
        document.body
      )}
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
 * angle-conditioned suggestions use the same state, so
 * selecting a goal still triggers the existing template/plan synchronization.
 *
 * Only the top 3 suggestions for the selected angle are shown (ADR 0131):
 * the ranked order — the server's live-goal selection when live goals
 * exist, the persisted facet order otherwise — is the relevance order,
 * and the cards stop at three. A goal already picked from outside the
 * three stays selected and is named by the outside note below.
 *
 * On Audience & template the three render on angle pick (Part 3 removed the
 * click-to-reveal gate here too): the persisted, facet-ordered suggestions
 * are the list — no duplicate Generate action rides beside it, only
 * "Shuffle" to reshuffle that same ranked set. The billed live generation lives
 * on live goals only where the gate still gates. The Review recovery copies
 * pass `landingGate` and keep the gated landing: one "Generate goals"
 * action, never a finished list — the facet-ordered `suggestions` fallback
 * is never rendered there as the initial list, so a founder fixing a plan
 * never lands on auto-populated goals. "Shuffle" appears only beside a
 * visible list, where it always has a current generation to act on.
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
  // Whole-video verdicts per goal (ADR 0124/0126): up/down calls on
  // finished videos, tallied server-side by the goal each video was made
  // for. Same map shape as objectiveEvidence; an objective with no
  // verdicts renders no line, exactly like the axes above.
  verdictObjectiveEvidence = {},
  // The six suggestions in the angle's profile-tailored PERSISTED variant
  // order, from the server (angle.goal_suggestions). Falls back to the
  // static facet list when the angle row carries none. On Audience &
  // template this IS the initial list; behind the gate (the Review
  // recovery call sites) it is kept for the pre-generate fallback copy
  // inspection and never rendered as the initial list — the gate owns
  // first view there.
  suggestions,
  // Live goals generated on the founder's click, each
  // {name, description, why_it_fits, fit_score}. Null until generated:
  // behind the gate the panel shows the gate in the meantime; ungated it
  // shows the persisted list — and on failure keeps whichever it showed.
  liveGoals = null,
  showGoals = false,
  onGenerate,
  generating = false,
  generationError = null,
  onRegenerate,
  regenerating = false,
  // The gated landing form, kept only for the Review recovery copies (see
  // the docstring above): the six stay behind the Generate action there.
  // The Audience & template step never passes this — its six render on
  // angle pick, with no Generate action beside them (Shuffle only).
  landingGate = false,
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
  // Visibility of the suggestions. On Audience & template they render on angle
  // pick — `landingGate` is false and the list is simply there. Behind the
  // gate (the Review recovery copies) the list is visible only when the
  // founder clicked Generate (showGoals / liveGoals) or when a goal is
  // already picked (a draft or deep link that already names one has been
  // viewed by definition): the facet-ordered `suggestions` /
  // `recommendations` lists are never shown there on first view — they are
  // the auto-populated output that gate exists to withhold. A draft whose
  // only goals come from the facet list still renders them once a goal is
  // picked, so resuming never strands the founder on an empty required
  // control.
  const revealed = !landingGate || showGoals || Boolean(value) || (Array.isArray(liveGoals) && liveGoals.length > 0);
  // Top 3 only (ADR 0131): rankedGoals is already in relevance order for
  // this angle — the live selection when live goals exist, the persisted
  // suggestion order otherwise — so the cards are its first three. The
  // vocabulary padding behind them only ever filled the old six-card
  // grid; with the cap at three it can never surface.
  const featured = revealed
    ? [...new Set([...rankedGoals, ...knownGoals])].slice(0, 3)
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
    </div>
  ) : (
  <div className="space-y-4">
    {generationError && (
      <p className="text-sm text-destructive-text" role="alert" data-testid="goals-generation-error">
        {generationError} The suggested goals below are unchanged.
      </p>
    )}
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" role="group" aria-label={`Recommended video goals for ${angle.label}`} data-testid="goals-grid">
        {featured.map((goal, index) => {
          const selected = value === goal;
          // 0–10 fit for this goal under the selected angle: annotates the
          // card, never reorders the three. Rank is this angle's persisted
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
                formatVerdicts(pairEvidence?.[`${angle?.kind}‖${goal}`]) ||
                formatVerdicts(verdictObjectiveEvidence?.[goal])) && (
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
                    {/* Whole-video verdicts for this GOAL (ADR 0124): the founder's
                        up/down calls on finished videos, tallied by the goal each
                        video was made for. Same counts, same styling — the live
                        signal beside the record axes above. */}
                    {formatVerdicts(verdictObjectiveEvidence?.[goal]) && (
                      <span
                        data-testid={`goal-verdict-evidence-${goal}`}
                        className="block text-sm leading-relaxed text-muted-foreground"
                      >
                        {formatVerdicts(verdictObjectiveEvidence[goal])} at this goal
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
          Your current goal, {humanize(value)}, is outside these suggestions. It stays selected unless you choose a suggested goal.
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
          {(onRegenerate && revealed && featured.length > 0) && (
            <div className="flex shrink-0 items-center gap-1.5">
              {/* Only Shuffle rides beside the revealed list now: the
                  small duplicate Generate action is gone (the six
                  suggestions are already here). The gated Review copies
                  keep their Generate action as the gate button below. */}
              {onRegenerate && revealed && featured.length > 0 && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="gap-1.5 shrink-0"
                  onClick={onRegenerate}
                  disabled={regenerating}
                  busy={regenerating}
                  title="Same suggestions, a different ranking — which three sit on top changes. Shuffling never changes the set itself — regenerate angles for genuinely new direction. Your selection is kept."
                  data-testid="regenerate-goals-button"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {regenerating ? "Shuffling goals" : "Shuffle"}
                </Button>
              )}
            </div>
          )}
        </div>
        <p className="text-sm text-muted-foreground">
          {revealed && featured.length > 0
            ? `${featured.length === 3 ? "Three" : featured.length} suggestions for “${angle.label}”.`
            : `Goal suggestions for “${angle.label}” are ready when you click.`}
        </p>
      </div>
      {body}
    </section>
  );
}

/* The presenter photo's anchor, owned here with the control itself: the
   page's scroll helpers, the substep caption and the onboarding tour all
   aim at this id, so the string lives exactly once, beside the element
   that carries it. */
export const TEMPLATE_PHOTO_ID = "template-photo";

/**
 * The presenter photo control — the fourth creation control, owned by the
 * selection structure like the angle, goal and template pickers above
 * (Part 3 moved it here from CreateVideo.jsx, where it was the one control
 * the page rendered inline). Presentational in the same way the panel
 * always was: it renders only once a template is picked (the page keeps
 * that condition), because with no template there is nothing to attach a
 * photo to — the section is hidden entirely rather than showing a blank
 * label. The project writes stay with the page: the control receives the
 * draft-preparation action and the project-adoption callbacks, and the
 * library's own attach/upload endpoints are unchanged.
 */
export function PresenterPhotoControl({
  project,
  profileId,
  busy = false,
  collapsed = false,
  card = false,
  onEnsureProject,
  onProjectChanged,
  onRefreshProject,
}) {
  // ADR 0356 (HookSnap only): `collapsed` stands the panel at its
  // headline alone — the GroupLabel renders exactly as it does open
  // and everything under it stands in a hidden wrapper, mounted and
  // unchanged, simply not shown. No toggle, no new chrome; callers
  // that never pass it (the Create wizard) render as before.
  // ADR 0358 (HookSnap only): `card` stands the panel as a section
  // card in its own right — the same `.surface` size and shape,
  // the same spacing rhythm and the same section heading (16px
  // glyph) its sibling sections wear — because on that page it IS
  // one of the sections, and the inset aside it wears inside the
  // Create wizard's step card read thinner and smaller beside
  // them. The wizard never passes it: inside a step card the
  // inset panel is the matching level, and it renders as before.
  const body = (
    <>
      <p className="text-sm text-muted-foreground" data-subtitle="">
        Upload one clear photo of the person you want on camera.
      </p>
      {!project ? (
        <>
          {!busy && (
            <p className="text-base text-muted-foreground">
              Preparing the video draft for your photo…
            </p>
          )}
          <Button variant="secondary" size="sm" disabled={busy} busy={busy} onClick={onEnsureProject} data-testid="prepare-draft-button">
            <ImageIcon className="h-3.5 w-3.5" />
            {busy ? "Preparing draft" : "Try preparing the draft again"}
          </Button>
        </>
      ) : (
        <>
          <AssetLibrary
            embedded
            profileId={profileId}
            projectId={project.id}
            projectAssets={project.assets}
            onProjectChanged={onProjectChanged}
            onChanged={onRefreshProject}
          />
        </>
      )}
    </>
  );
  return (
    <div
      id={TEMPLATE_PHOTO_ID}
      data-testid="template-photo"
      className={card ? "surface rounded-2xl scroll-mt-4 space-y-5" : "inset-panel scroll-mt-4 space-y-4"}
    >
      {card ? (
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0 space-y-1">
            <SectionHeading as="h2" icon={ImageIcon}>Presenter photo</SectionHeading>
          </div>
        </div>
      ) : (
        <GroupLabel icon={ImageIcon}>Presenter photo</GroupLabel>
      )}
      {collapsed ? <div hidden data-collapsed-body="">{body}</div> : body}
    </div>
  );
}

/**
 * What the selected template is still waiting on.
 *
 * Face-only product: the character reference is the single permitted asset
 * and every template requires exactly it. Without a photograph of the
 * person the model would invent one, and the founder would pay for a video
 * of somebody who looks nothing like them. The server refuses that case
 * before rendering, so this is the early warning rather than the guarantee.
 * It lives with the photo control it points at. It names the requirement
 * and carries no jump of its own (ADR 0229): the upload is reached by the
 * rail segments and the sticky bar, like every other step change.
 */
export function MissingRequirements({ identity }) {
  if (!identity || identity.length === 0) return null;

  return (
    <div className="inset-panel space-y-4">
      {/* The requirement leads and the explanation follows it: the panel
          names what is missing, in words — the upload itself is on the
          Audience & template step, reached by the segments and the bar.
          It used to point at a step called "Assets" whose only content
          was this same upload. */}
      <p className="text-base font-semibold">
        This template needs a character reference before it can generate
      </p>
      <p className="text-sm text-muted-foreground" data-subtitle="">
        Your photograph is what the generated video is built from.
      </p>
    </div>
  );
}
