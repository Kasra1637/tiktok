import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { GroupLabel, SectionHeading } from "../components/SectionCard";
import { Skeleton } from "../components/ui/skeleton";
import SafetyPanel from "../components/SafetyPanel";
import HookContinuityPanel from "../components/HookContinuityPanel";
import GenerationPanel from "../components/GenerationPanel";
import { ThumbPair } from "../components/ThumbPair";
import { ComponentThumbs } from "../components/ComponentThumbs";
import AssetLibrary from "./AssetLibrary";
import { api, getErrorMessage } from "../lib/api";
import { recordSignal, recordThumb, classifyScriptEdit } from "../lib/feedback";
import {
  partitionProfiles,
  profileLabel,
  describeUnapprovedCount,
  describeEmptySelection,
} from "../lib/profileSelection";
// requiredAssetStatus left with the per-requirement checklist it fed. The photo
// section now reports the one requirement directly, next to the photograph, so
// the template card only has to say whether anything is still owed.
import {
  blockingRequirements,
} from "../lib/templateRequirements";
import { sentenceCase } from "../lib/copyCase";
import { angleDetails, formatVerdicts } from "../lib/angleSubtitle";
import {
  readPieceSeconds,
  sectionSplit,
  clampHookSeconds,
  DEFAULT_HOOK_SECONDS,
} from "../lib/videoLength";
// FileText was the "Creative plan" step's icon. That step held nothing but a
// button and is now the top of Review, so the icon went with it.
import { Clapperboard, Loader as Loader2, TriangleAlert as AlertTriangle, Briefcase, Target, LayoutTemplate, Image as ImageIcon, Check, Sparkles, RefreshCw, Save, CircleCheck as CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, FileText, AudioLines, ListChecks, ShieldCheck, Ruler } from "lucide-react";
// toast left with AttachedPhoto, the only place on this page that raised one.
// Detaching now happens inside the photo section, which reports its own
// outcome.

// The order is the product, and it is deliberate.
//
//   profile -> angle -> template -> assets -> plan -> review -> Hook + Story
//
// The script is written, checked for banned claims and read by the founder
// BEFORE any video is rendered. The last step then renders the piece that
// script describes: the strategy is built from the approved plan, so the words
// the founder read are the words that get rendered.
//
// This was the other way round. The hook came first, so a founder approved a
// strategy on trust, rendered, and only then read a script describing a
// different video — with the claim check and the SafetyPanel running against
// text nobody had looked at before the render.
/**
 * The five steps, in order.
 *
 * Was seven. "Assets" and "Creative plan" were steps that existed only to hold a
 * button, and both are now part of the step they belonged to:
 *
 *   - Assets was a photo upload. The template step already says what a template
 *     needs from you and already links to it, so the upload moved there and the
 *     step went from "pick a template, then leave to attach a photo, then come
 *     back" to one continuous decision.
 *   - Creative plan was a "Generate plan" button whose result you immediately had
 *     to go to the next screen to read. It is now the top of Review, which is
 *     where the plan is actually read and edited.
 *
 * The step count is not a vanity metric; every extra step is a place a founder
 * can stall with nothing to do, and nothing is generated until the last one.
 *
 * Last, because this is the only step that calls the model. The plan is text
 * only, and it is what that step renders.
 *
 * Named for what it produces rather than for the old hook-first workflow: one
 * render containing a hook and a middle. The demo and the close are the
 * founder's own footage, added afterwards in their editor.
 */
const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & goal", icon: Target },
  { key: "template", label: "Template & photo", icon: LayoutTemplate },
  { key: "review", label: "Review", icon: CheckCircle2 },
  { key: "hook", label: "Hook + Story", icon: Sparkles },
];

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
function RecommendationCard({ r, selected, onSelect, index = 0 }) {
  const reasons = Array.isArray(r.why_it_fits) ? r.why_it_fits : [];
  const limits = Array.isArray(r.limitations) ? r.limitations : [];
  const score = Number(r.score);
  // The server sorts reasons strongest-first and sends only the strings, so
  // the first reason IS the verdict and the rest is supporting detail. Shown
  // that way rather than as four identical paragraphs, which left the founder
  // unable to tell the decision from its evidence.
  const [verdict, ...detail] = reasons;
  const example =
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
      className={`card-pickable animate-fade-up w-full rounded-xl border p-5 text-left ${
        selected
          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
          : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
      }`}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-semibold">{r.template.name}</span>
        <span className="flex flex-wrap items-center gap-2">
          <Badge variant="outline" className="text-xs">
            {r.suggested_duration}s
          </Badge>
          {Number.isFinite(score) && (
            // The sort key on a 0–10 scale: a weighted sum of matched
            // factors, clamped server-side, comparable only between these
            // cards. The "/10" marks the scale so a fit never reads as
            // open-ended.
            <Badge
              variant="outline"
              className="text-xs"
              data-testid="template-fit-score"
              title="Fit score — a weighted sum of the factors this template matched, on a 0–10 scale. Only comparable against the other templates below."
            >
              Fit {score}/10
            </Badge>
          )}
          <Badge variant="secondary" className="text-xs">
            {formatTemplateUse(r.template.times_used)}
          </Badge>
          {selected && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
        </span>
      </div>
      {outcome && (
        <p className="mt-1 text-sm text-foreground/90" data-testid="template-outcome">
          {outcome}
        </p>
      )}
      {example && (
        <p className="mt-1 text-xs text-foreground/80">
          <span className="text-muted-foreground">Sounds like: </span>
          &ldquo;{example}&rdquo;
        </p>
      )}
      {reasons.length > 0 && (
        <div className="mt-2 space-y-2">
          <p className="eyebrow">Why it fits</p>
          {/* The verdict: the strongest match, in body weight with the same
              tick the step pills use for "positive", so it reads as the reason
              rather than one of several. */}
          <p
            className="flex items-start gap-1.5 text-sm text-foreground"
            data-testid="template-fit-verdict"
          >
            <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span>{sentenceCase(verdict)}</span>
          </p>
          {/* Supporting detail: muted, marked as a list, tighter leading. A
              single-reason card renders the verdict alone with no list. */}
          {detail.length > 0 && (
            <ul className="space-y-1">
              {detail.map((reason, i) => (
                <li
                  key={`r-${i + 1}`}
                  className="flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground"
                >
                  <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
                  <span>{sentenceCase(reason)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {limits.length > 0 && (
        <ul className="space-y-1">
          {limits.map((limitation, i) => (
            <li
              key={`l-${i}`}
              className="flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground"
            >
              <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
              <span>{sentenceCase(limitation)}</span>
            </li>
          ))}
        </ul>
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
function TemplateShape({ template }) {
  const total = readPieceSeconds(null, template);
  const hook = clampHookSeconds(template?.hook_seconds) || DEFAULT_HOOK_SECONDS;
  const split = sectionSplit(total, hook);
  const middle = middleStructure(template);
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs">
        <span className="font-semibold">{total}s piece</span>: a {split.hookSeconds}s hook, then a{" "}
        {split.middleSeconds}s middle.
      </p>
      {middle && <p className="text-xs text-muted-foreground">{sentenceCase(middle)}</p>}
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
 */
function MissingRequirements({ identity, onGoToTemplatePhoto }) {
  if (!identity || identity.length === 0) return null;

  return (
    <div className="inset-panel space-y-2">
      <p className="text-sm font-semibold">
        This template needs a character reference before it can generate
      </p>
      <p className="text-xs text-muted-foreground" data-subtitle="">
        Your photograph is what the generated video is built from.
      </p>
      {/* The button says where the upload is, and the upload is on the template
          step now. It used to point at a step called "Assets" whose only
          content was this same upload. */}
      {onGoToTemplatePhoto && (
        <Button variant="secondary" size="sm" onClick={onGoToTemplatePhoto}>
          <ImageIcon className="h-3.5 w-3.5" /> Add your photo
        </Button>
      )}
    </div>
  );
}

/**
 * What changed on Review and what it means downstream.
 *
 * Read-only explanatory panel: which edits are still unsaved, whether the
 * downstream strategy needs rebuilding, and whether the newest rendered clip
 * still reflects the current plan and strategy. It never edits, rebuilds, or
 * renders anything itself — the existing Save, Rebuild, and Generate controls
 * keep their confirmations and gates, and nothing here triggers a paid render.
 *
 * Honest about missing history. There is no plan-history table, so "what
 * changed" is derived only from unsaved edits against the saved plan — never
 * fabricated from a previous snapshot. The clip comparison reads the newest
 * generation's recorded script/strategy versions; when the record carries no
 * versions (or no finished clip exists) it says so instead of guessing.
 */
const REVIEW_EDIT_LABELS = {
  hook_line: "Hook line",
  script: "Script",
  demo_brief: "Demo note",
  visual_direction: "Visual direction",
  voice_direction: "Voice direction",
  tone: "Tone",
  beat_timeline: "Shot timeline",
};

function ReviewRevisionsPanel({ project, edits, hasEdits, onGoToHookStory }) {
  const scriptVersion = Number(project?.script_version) || 0;
  const strategy = project?.strategy || {};
  const hasStrategy = Boolean(strategy?.hook_line);
  const strategyVersion = Number(project?.strategy_version) || 0;
  const strategyScriptVersion = Number(project?.strategy_script_version) || 0;
  const staleStrategy = hasStrategy && project?.strategy_is_current === false;
  const angleStale =
    hasStrategy &&
    String(strategy?.content_angle_id || "") !== String(project?.content_angle_id || "");

  const [clip, setClip] = useState(null);
  const [clipLoaded, setClipLoaded] = useState(false);
  const projectId = project?.id;
  useEffect(() => {
    let cancelled = false;
    if (!projectId || !scriptVersion) {
      setClip(null);
      setClipLoaded(false);
      return undefined;
    }
    setClipLoaded(false);
    api
      .getGenerations({ studio_project_id: projectId, limit: 1 })
      .then((data) => {
        if (cancelled) return;
        setClip(data?.generations?.[0] || null);
        setClipLoaded(true);
      })
      .catch(() => {
        if (cancelled) return;
        setClip(null);
        setClipLoaded(true);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, scriptVersion]);

  if (!scriptVersion) return null;

  const editedLabels = Object.keys(edits || {}).map(
    (key) => REVIEW_EDIT_LABELS[key] || humanize(key)
  );

  // A strategy row without a recorded version is missing history, not proof
  // of a match: the server numbers every build, so v0 means the record
  // predates the versioning rather than that it matches the current plan.
  const strategyUnversioned = hasStrategy && !strategyVersion;

  const clipIsCurrent =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    typeof clip.script_version === "number" &&
    typeof clip.strategy_version === "number" &&
    clip.script_version === scriptVersion &&
    clip.strategy_version === strategyVersion;
  const clipIsStale =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    typeof clip.script_version === "number" &&
    typeof clip.strategy_version === "number" &&
    (clip.script_version !== scriptVersion || clip.strategy_version !== strategyVersion);
  const clipUnversioned =
    clipLoaded &&
    clip &&
    clip.status === "completed" &&
    (typeof clip.script_version !== "number" || typeof clip.strategy_version !== "number");

  // One status line: the saved-plan state plus the single next thing to do.
  // Priority is unchanged — unsaved edits first (the render gate refuses
  // them), then strategy staleness (a paid render built from the wrong
  // words), then clip staleness.
  const planState =
    `Plan v${scriptVersion} · ` +
    ((project?.hook_line || project?.script) ? "has words." : "empty.");
  let status;
  if (hasEdits) {
    status =
      `${planState} Unsaved edits in: ${editedLabels.join(", ")}. ` +
      "Save below first — rendering needs the saved plan.";
  } else if (!hasStrategy) {
    status = `${planState} No strategy yet — build it on Hook + Story before rendering.`;
  } else if (strategyUnversioned) {
    status =
      `${planState} Strategy exists but its version was not recorded — ` +
      "rebuild it on Hook + Story before rendering.";
  } else if (staleStrategy) {
    status =
      `${planState} Strategy v${strategyVersion} was built from plan v${strategyScriptVersion}. ` +
      "Rebuild the strategy before rendering, or the clip follows the older plan.";
  } else if (angleStale) {
    status =
      `${planState} Strategy was built for a different audience angle. ` +
      "Rebuild it for the current angle before rendering.";
  } else if (!clipLoaded) {
    status = `${planState} Strategy v${strategyVersion} matches. Checking for rendered clips…`;
  } else if (clipIsStale) {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      `Rendered clip reflects plan v${clip.script_version} and strategy v${clip.strategy_version} — ` +
      "re-render on Hook + Story.";
  } else if (clipUnversioned) {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      "Rendered clip's versions were not recorded — re-render if you edited since.";
  } else if (clip && clip.status !== "completed") {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      `Latest render is ${clip.status || "not finished"} — finish or retry it on Hook + Story.`;
  } else if (clipIsCurrent) {
    status =
      `${planState} Strategy v${strategyVersion} matches · rendered clip is current.`;
  } else {
    status =
      `${planState} Strategy v${strategyVersion} matches. ` +
      "No rendered clip yet — render on Hook + Story when ready.";
  }

  return (
    <div
      className="inset-panel space-y-2"
      data-testid="review-revisions"
    >
      <span className="eyebrow block">Revisions &amp; consequences</span>
      <p className="text-sm" data-testid="revisions-status">
        {status}
      </p>
      {onGoToHookStory && (
        <Button variant="secondary" size="sm" onClick={onGoToHookStory}>
          Review strategy on Hook + Story
        </Button>
      )}
    </div>
  );
}

/**
 * The studio's one angle-selection control, reused by every step that offers it.
 *
 * This was inline on the Audience & goal step alone. Review and Hook + Story
 * each carried their own plainer version — a flat list of angle names beside a
 * "Pick a template" pill — so the same choice rendered three ways: no check
 * mark, no expansion, and no way to regenerate. One control, one behaviour,
 * wherever the founder is asked for it.
 *
 * Landing is always gated: one "Generate angles" action, never a finished list.
 * The click reveals a pre-generated set for free (the server generates on
 * approval) and generates fresh only when there is nothing to show, so no
 * step can spend a call the founder did not ask for. "Regenerate angles"
 * appears only beside a visible list, where it always has a current generation
 * to act on.
 *
 * `bare` drops the `.inset-panel` frame and renders content only. It exists
 * because Review and Hook + Story already sit inside an inset-panel of their
 * own, and a bordered aside inside a bordered aside is the box-in-a-box the
 * container levels in design_guidelines.md §4 reserve.
 */
function AngleSelector({
  angles,
  angleId,
  onSelect,
  showAngles,
  generating = false,
  error = "",
  onGenerate,
  onRegenerate,
  notice = "",
  bare = false,
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
    <p className="text-xs text-muted-foreground" role="status" data-testid="angles-progress">
      Reading angle {genCount} of 6…
    </p>
  ) : null;
  const body = !showAngles || angles.length === 0 ? (
    <div className="space-y-2">
      <p className="text-xs text-muted-foreground" data-testid="angles-cta-copy" data-subtitle="">
        {ANGLES_CTA_COPY}
      </p>
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      <Button
        variant="brand"
        className="gap-1.5"
        onClick={onGenerate}
        disabled={generating}
        data-testid="generate-angles-button"
      >
        {generating ? (
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
        ) : (
          <Sparkles className="h-3.5 w-3.5" />
        )}
        {generating ? "Generating…" : "Generate angles"}
          </Button>
          {progressLine}
        </div>
      ) : (
    <div className="space-y-2" data-testid="audience-angle-list">
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
          data-testid="regenerate-angles-button"
        >
          {generating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <RefreshCw className="h-3.5 w-3.5" />
          )}
          {generating ? "Regenerating…" : "Regenerate angles"}
            </Button>
          </div>
          {progressLine}
      {notice && (
        <Alert data-testid="angle-regen-notice">
          <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}
      {/* Selection opens the angle. A closed row is its uppercase title and
          nothing else: the list is scanned by name, and the picked row then
          shows what the strategy is written from — audience, problem,
          promise, feature, the emotion it aims at, and any claim bounding it.
          Only the picked row opens, because two open panels side by side are
          two half-read angles, and the fields are what the render downstream
          is held to. */}
      {angles.map((a, i) => {
        const picked = angleId === a.id;
        const details = picked ? angleDetails(a) : [];
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
              <span className="min-w-0 flex-1 truncate text-sm font-semibold uppercase leading-[22px] tracking-[0.08em] text-muted-foreground">
                {sentenceCase(a.label).replace(/\.\s*$/, "")}
              </span>
              <ChevronDown
                className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
                  picked ? "rotate-180" : ""
                }`}
              />
            </button>
            {picked && details.length > 0 && (
              <dl
                id={`angle-details-${a.id}`}
                data-testid={`angle-details-${a.id}`}
                className="space-y-2 border-t border-[color:var(--hairline)] row-pad"
              >
                {details.map((row) => (
                  <div key={row.label} className="min-w-0">
                    <dt className="eyebrow">{row.label}</dt>
                    <dd className="mt-1 text-sm leading-[22px] text-foreground/90">
                      {row.value}
                    </dd>
                  </div>
                ))}
              </dl>
            )}
          </div>
        );
      })}
    </div>
  );

  if (bare) return body;

  return (
    <div className="inset-panel space-y-2">
      <GroupLabel as="label" icon={Target}>
        Audience angle <span className="text-muted-foreground">(required)</span>
      </GroupLabel>
      {body}
    </div>
  );
}

/**
 * Goal picker shared by the Audience & goal step and Review recovery. Its
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
function AngleGoalPicker({
  angle,
  value,
  onPick,
  options,
  recommendations,
  outcomes,
  fitReasons,
  objectiveEvidence = {},
  // The six suggestions in the angle's PERSISTED variant order, from the
  // server (angle.goal_suggestions). Falls back to the static facet list
  // when the angle row carries none.
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
    /* The waits marker only. This used to fall back to a flat list of angle
       names of its own — no check mark, no expansion, no regenerate — which is
       the second implementation `AngleSelector` replaced. Every step now picks
       the angle through that one control, and this picker states plainly that
       it is waiting for it. */
    return (
      <div className="space-y-2" data-testid="goal-waits-for-angle">
        <p className="text-xs text-muted-foreground" data-subtitle="">
          Pick an audience angle first — goals are ranked for it.
        </p>
      </div>
    );
  }

  return (
    <section className="space-y-2" aria-labelledby="video-goal-label" data-testid="angle-goal-picker">
      <div className="space-y-1">
        <div className="flex items-start justify-between gap-2">
          <GroupLabel as="h3" icon={Target} id="video-goal-label">
            Video goal <span className="text-muted-foreground">(required)</span>
          </GroupLabel>
          {onRegenerate && featured.length > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="gap-1.5 shrink-0"
              onClick={onRegenerate}
              disabled={regenerating}
              title="Same six suggestions, a different ranking. Shuffling never changes the six goals — regenerate angles for genuinely new direction. Your selection is kept."
              data-testid="regenerate-goals-button"
            >
              {regenerating ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" />
              ) : (
                <RefreshCw className="h-3.5 w-3.5" />
              )}
              {regenerating ? "Shuffling…" : "Shuffle"}
            </Button>
          )}
        </div>
        <p className="text-xs text-muted-foreground">
          {featured.length > 0
            ? `${featured.length === 6 ? "Six" : featured.length} suggestions for “${angle.label}”.`
            : `Goal suggestions for “${angle.label}” are unavailable. Try reloading the page.`}{" "}
          The angle stays the story’s focus; the goal shapes what the overall campaign should achieve.
        </p>
      </div>
      {regenerating && (
        <p className="text-xs text-muted-foreground" role="status" data-testid="goals-progress">
          Shuffling goal {shuffleCount} of {shuffleTotal}…
        </p>
      )}
      <div className="grid gap-2 sm:grid-cols-2" role="group" aria-label={`Recommended video goals for ${angle.label}`}>
        {featured.map((goal, index) => {
          const selected = value === goal;
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
              className={`card-pickable animate-fade-up rounded-xl border p-5 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-35)] ${
                selected
                  ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                  : "border-[color:var(--hairline)]"
              }`}
            >
              <span className="flex items-center justify-between gap-2 text-sm font-semibold">
                {humanize(goal)}
                {selected && <Check aria-hidden="true" className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />}
              </span>
              {outcomes?.[goal] && (
                <span className="mt-1 block text-xs leading-relaxed text-muted-foreground">
                  {sentenceCase(outcomes[goal])}
                </span>
              )}
              {fitReasons?.[goal] && (
                <span
                  data-testid={`goal-fit-${goal}`}
                  className="mt-1 block text-xs leading-relaxed text-muted-foreground"
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
                  className="mt-1 block text-xs leading-relaxed text-muted-foreground"
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
                  className="mt-1 block text-xs leading-relaxed text-muted-foreground"
                >
                  {formatVerdicts(objectiveEvidence[goal])} for this goal
                </span>
              )}
              {index === 0 && <span className="sr-only">Best fit suggestion. </span>}
            </button>
          );
        })}
      </div>
      {outsideRecommendation && (
        <p className="text-xs text-muted-foreground" data-testid="goal-outside-recommendations">
          Your current goal, {humanize(value)}, is outside these six suggestions. It stays selected unless you choose a suggested goal.
        </p>
      )}
    </section>
  );
}

/**
 * Live narration while the plan writes. The artifact arrives whole, so there
 * is nothing honest to count — but its sections are known up front (hook,
 * script, shots, demo note), and naming the current one beats a static line
 * that never moves. Unmounts with its branch, so a failure can never strand
 * it beside the error; the interval dies with the component.
 */
function PlanPhaseLine() {
  const phases = ["Writing the hook…", "Writing the script…", "Placing the shots…", "Adding the demo note…"];
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % phases.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);
  return (
    <span role="status" data-testid="plan-progress">
      {phases[index]}
    </span>
  );
}

function StepShell({ icon: Icon, title, children }) {
  return (
    <div className="space-y-5">
      {Icon && (
        <div className="space-y-1">
          {title && <SectionHeading icon={Icon}>{title}</SectionHeading>}
        </div>
      )}
      {children}
    </div>
  );
}

/** What each progress state means, in words. Used for the pill tooltip and
 *  the aria-label, because both a tick and a dashed border are shape-only. */
const STEP_STATE_COPY = {
  done: "done",
  todo: "not started",
  blocked: "needs something from you",
};

/**
 * Whether each step is satisfied, in the wizard's own terms.
 *
 * Returns one entry per STEPS item in order. `blocked` is not an error state —
 * it is the only step that can be waiting on the founder, and it is
 * distinguished from `todo` because the remedy is different: a todo is
 * downstream of work not yet done, a blocked step is the next thing they must
 * do.
 *
 * Review counts as satisfied once a plan exists. It does NOT require the
 * plan to be marked ready: that is a deliberate final gate the founder sets
 * themselves after reading, and ticking the step for it would claim the
 * workflow is finished when the last read is still ahead of them.
 */
function stepCompletion({ profileId, objective, angleId, templateId, project, missingIdentity, hasEdits }) {
  const hasPhoto = missingIdentity.length === 0;
  return STEPS.map((step) => {
    let state = "done";
    if (step.key === "profile") state = profileId ? "done" : "todo";
    // The angle is required, not optional: the strategy and the render are
    // built around it, so a video without one is the generic framing this
    // step exists to prevent. Objective alone no longer satisfies it.
    else if (step.key === "angle") state = angleId && objective ? "done" : "blocked";
    else if (step.key === "template") {
      if (!templateId) state = "blocked";
      else if (!hasPhoto) state = "blocked";
    } else if (step.key === "review") {
      // A plan with unsaved edits is not reviewed. The step says so itself, and
      // a tick here would tell the founder they had finished reading a script
      // they had changed and not stored.
      if (!project?.script_version) state = "todo";
      else if (hasEdits) state = "blocked";
    } else {
      // The render step has NO completion state, deliberately. A clip can be
      // generated, but the workflow does not end there - it ends at "attach
      // your own demo", which happens in the founder's editor and cannot be
      // observed from here. So this step is never ticked: doing so would claim
      // the job is finished when the half the founder still has to shoot is not.
      // It reports what is waiting instead.
      state = templateId && !hasPhoto ? "blocked" : "todo";
    }
    return { step, state };
  });
}

export default function CreateVideo() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  // The server's updated_at for each project this wizard has adopted from a
  // server response, so a row that is already current is never re-read or
  // re-adopted. Declared here, above every effect that reads or writes it: a
  // dep array is evaluated during render, and the deep-link load below uses it
  // long before the Review step that first needed it was in view.
  const syncedProjectsRef = useRef({});

  const [step, setStep] = useState(0);
  const [profiles, setProfiles] = useState([]);
  const [angles, setAngles] = useState([]);
  // The GOAL axis of the verdict tally, keyed by objective name and fetched
  // with the angles (`objective_evidence` on the same response). Own state,
  // because it is not per angle: a goal's verdicts are shared across kinds, so
  // they cannot hang off one angle row. Cleared wherever angles are cleared.
  const [objectiveEvidence, setObjectiveEvidence] = useState({});
  const adoptAngles = useCallback((data, onAngles = () => {}) => {
    setAngles(data?.angles || []);
    setObjectiveEvidence(data?.objective_evidence || {});
    onAngles(data?.angles || []);
    return data?.angles;
  }, []);
  // Angles can be generated from in here, not just on the profile page:
  // sending the founder out of the wizard to make an optional angle usable
  // was a round trip the flow never offered a way back from.
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [angleError, setAngleError] = useState(null);
  // Click-to-view gate for angles. Landing on this step always starts gated:
  // one "Generate angles" CTA, never a finished list — and "Regenerate" only
  // ever appears beside a visible list, i.e. when there is a current
  // generation to be unhappy with. The reveal is session-local on purpose:
  // persisting it put returning founders straight onto selections they didn't
  // ask to see. A pick bypasses the gate entirely — a draft or deep link
  // that already names an angle has been viewed by definition.
  const [anglesRevealed, setAnglesRevealed] = useState(false);
  const revealAngles = useCallback(() => {
    setAnglesRevealed(true);
  }, []);
  // Cycling goal suggestions on the selected angle. Persists server-side per
  // angle, so the re-read of the angles list is the new state.
  const [cyclingGoals, setCyclingGoals] = useState(false);
  const [angleRegenNotice, setAngleRegenNotice] = useState(null);
  // What a completed angle regen cost: how many of the profile's drafts were
  // built on angles it replaced. Shown as a one-line notice after the fact —
  // the pre-click confirm only covers the selected angle, so this is how a
  // draft on a DIFFERENT angle learns it lost its story. Count of 0 shows
  // nothing: a clean regen is not news.
  const [facets, setFacets] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [recError, setRecError] = useState(null);
  const [recKey, setRecKey] = useState("");
  const [tailored, setTailored] = useState({ key: "", templates: [] });
  const [templates, setTemplates] = useState([]);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // A plan attempt ran and failed (or draft creation refused). While true,
  // Review shows the retry path instead of the generating spinner: without
  // this the failure state is indistinguishable from an attempt in flight,
  // and the spinner spins forever because the auto latch (below) rightly
  // refuses to re-fire the same selection-set on its own. Cleared whenever a
  // new attempt starts.
  const [planFailed, setPlanFailed] = useState(false);

  const [selectedProfileId, setSelectedProfileId] = useState(params.get("profile") || "");
  const [angleId, setAngleId] = useState(params.get("angle") || "");
  const [templateId, setTemplateId] = useState(params.get("template") || "");
  const [objective, setObjective] = useState("");
  // There is no length state and no intent state any more, and that is the
  // whole point of this step's current shape. Duration is computed: a template
  // declares the length its mechanic suits, the project seeds from it, and the
  // render is that long in one pass. `extendIntent` ("hook only" versus "extend
  // into a full video") asked a question about a chain that no longer exists —
  // there is no hook-only render to choose between.
  const [tone, setTone] = useState("");
  const [edits, setEdits] = useState({});
  // Thumbs verdict on the saved Review plan: up advances to Hook + Story,
  // down records the rejection and asks the AI for a fresh plan. Manual
  // editing stays untouched — this is an additive fast path, not a
  // replacement, so the claim check and ready gate keep working as before.
  const [reviewThumb, setReviewThumb] = useState(0);
  // Consecutive AI refinements per saved plan version. Capped so a thumbs-down
  // loop can never spin the text model unboundedly on one plan.
  const reviewRefinesRef = useRef({});

  const profileId = project?.brand_profile_id || selectedProfileId;
  // Every app lands gated: switching apps re-arms the CTA so a revealed set
  // for one app never leaks into another app's first view.
  useEffect(() => {
    setAnglesRevealed(false);
  }, [profileId]);
  const angle = angles.find((a) => a.id === angleId) || null;
  // The list reads revealed when the gate was clicked, or when the pick names
  // a real row — selecting an angle is itself the viewing the gate asks for.
  // A pick alone is deliberately not enough: a stale ?angle= param or a draft
  // pointing at a deleted angle must not open a list of strangers on first
  // view, which is the exact screenshot this rule fixes.
  const showAngles = anglesRevealed || Boolean(angle);
  const template = templates.find((t) => t.id === templateId) || null;
  const objectiveOptions = facets?.objectives || [];
  const recommendedObjectives = angle
    ? facets?.angle_goal_recommendations?.[angle.kind] || []
    : [];
  const objectiveOutcomes = facets?.objective_outcomes || {};
  const objectiveFitReasons = angle
    ? facets?.angle_goal_fit_reasons?.[angle.kind] || {}
    : {};

  useEffect(() => {
    let cancelled = false;
    api.getTemplateFacets().then(setFacets).catch(() => setFacets(null));
    api
      .getAppProfiles()
      .then(async (data) => {
        const list = data.profiles || [];
        if (cancelled) return;
        setProfiles(list);
        // Only approved profiles may enter the studio. The `?profile=` deep
        // link is a different path: it preselects a specific app and is
        // handled further down. Both must agree on what counts as approved, so
        // both go through the same partition rather than repeating the filter.
        const approved = partitionProfiles(list).approved;
        const requestedProjectId = params.get("project");
        if (requestedProjectId) {
          try {
            const draft = await api.getStudioProject(requestedProjectId);
            const draftProfile = approved.find((p) => p.id === draft.brand_profile_id);
            if (!draftProfile) {
              throw new Error("That draft project is unavailable or its App Profile is not approved.");
            }
            const angleData = await api
              .getContentAngles(draftProfile.id)
              .catch(() => ({ angles: [] }));
            if (cancelled) return;
            setProject(draft);
            // This row came from the server, so it is already current: recording
            // it means the Review re-read has nothing to reconcile and does not
            // fire. Without that, every deep link issued a second identical
            // request whose late resolution updated state after the check (or
            // the founder) had moved on.
            syncedProjectsRef.current[draft.id] = draft.updated_at || "";
            adoptAngles(angleData);
            setAngleId(draft.content_angle_id || "");
            setTemplateId(draft.template_id || "");
            setObjective(draft.objective || "");
            setTone(draft.tone || "");
            setRecommendations([]);
            setRecError(null);
            setEdits({});
            // A duplicate always arrives with its plan intact, so it opens on
            // Review; an unplanned draft still needs a photo before a plan can
            // be written. Both indices are looked up by KEY rather than written
            // as numbers: the wizard was seven steps and is now five, and a
            // hardcoded index is exactly what silently sent a deep link past
            // the end of the wizard.
            setStep(
              draft.script_version > 0
                ? STEPS.findIndex((s) => s.key === "review")
                : STEPS.findIndex((s) => s.key === "template")
            );
          } catch (err) {
            if (cancelled) return;
            setError(getErrorMessage(err));
          }
          return;
        }
        const preselected = params.get("profile");
        const chosen =
          approved.find((p) => p.id === preselected) || approved[0] || null;
        if (chosen) {
          // The pick must live in state: profileId drives recommendations,
          // canGenerate, and draft creation, and selectProfile is the only
          // other writer. Reading it from URL params alone left it empty.
          setSelectedProfileId(chosen.id);
          setStep(1);
          api.getContentAngles(chosen.id).then((d) => adoptAngles(d)).catch(() => {
            setAngles([]);
            setObjectiveEvidence({});
          });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [params]);

  useEffect(() => {
    api
      .getTemplates()
      .then((d) => setTemplates((d.templates || []).filter((t) => t.is_usable)))
      .catch(() => setTemplates([]));
  }, []);

  // Set once the founder picks a template themselves, and never cleared.
  //
  // This is what makes the default selection safe. The recommender reorders on
  // this app's own recorded feedback (feedback.template_feedback_adjustment
  // shifts a score by up to 4 points either way), so its top pick is
  // meaningful — and reordering it on every reload meant a founder's deliberate
  // choice could be silently replaced by whatever ranked first that time, which
  // discarded the adjustment the click was overriding.
  const templateChosenByHand = useRef(false);
  const recRequestRef = useRef(0);

  const loadRecommendations = useCallback(
    async (pid, aid) => {
      if (!pid) return;
      // Recommendations are keyed to the exact profile/angle/objective that
      // requested them. A slow response for a previous key must never populate
      // the step the founder is now reading, and rows for a previous key must
      // not linger while the new key loads.
      const request = ++recRequestRef.current;
      const key = `${pid || ""}:${aid || ""}:${objective || ""}`;
      setRecKey(key);
      setRecommendations([]);
      setRecError(null);
      try {
        const rec = await api.getTemplateRecommendations(pid, {
          angle_id: aid || undefined,
          objective: objective || undefined,
          limit: 6,
        });
        if (recRequestRef.current !== request) return;
        const rows = rec.recommendations || [];
        setRecKey(key);
        setRecommendations(rows);
        setRecError(null);
        // Preselection moved to its own effect below: it must wait until the
        // tailored set for this key is ready, otherwise the top curated card
        // is picked before the custom templates exist.
      } catch (err) {
        if (recRequestRef.current !== request) return;
        // An empty list used to mean three different things: nothing ranked,
        // nothing compatible, or the request failed. The third one stranded the
        // founder in front of a step that looked merely thin, so the reason is
        // shown rather than absorbed.
        setRecKey(key);
        setRecommendations([]);
        setRecError(getErrorMessage(err));
      }
    },
    [objective]
  );

  useEffect(() => {
    loadRecommendations(profileId, angleId);
  }, [profileId, angleId, loadRecommendations]);

  // Tailored templates generate per (profile, selected objective) — the
  // objective does not exist at approve time, so this is where the request
  // belongs. Auto-fires once per key while the founder reads the step
  // (cache hits return instantly); the button below forces a refresh.
  // Guarded by ref so a remount never pays for a second generation.
  const tailorKeyRef = useRef("");
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState(null);
  const [tailorCount, setTailorCount] = useState(0);
  const tailorTimer = useRef(null);
  const runTailoring = useCallback(async (regenerate) => {
    if (!profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    setTailoring(true);
    setTailorError(null);
    try {
      const res = await api.ensureObjectiveTemplates(profileId, {
        objective,
        ...(regenerate ? { regenerate: true } : {}),
      });
      // A response for a previous profile/objective must not mark the current
      // step ready: that is exactly how pre-made cards appeared before the
      // current app's custom set existed.
      if (tailorKeyRef.current !== key) return;
      setTailored({
        key,
        templates: Array.isArray(res?.templates) ? res.templates : [],
      });
      if (res.generated) {
        await loadRecommendations(profileId, angleId);
      }
      if (res.error) setTailorError(res.error);
    } catch (err) {
      if (tailorKeyRef.current !== key) return;
      setTailored({ key, templates: [] });
      setTailorError(getErrorMessage(err));
    } finally {
      if (tailorKeyRef.current === key) setTailoring(false);
    }
  }, [profileId, objective, angleId, loadRecommendations]);

  // The step's single CTA: "Generate angles", shown on landing instead of any
  // list. The click reveals a pre-generated set for free when one exists
  // (generated on approval — no endpoint call, no spend, no pick change), and
  // generates fresh only when there is nothing to show. Either way the list
  // — and with it "Regenerate" — appears only after this click, so
  // regenerating is always aimed at a current generation.
  //
  // Offered through this one button because the bare generate endpoint
  // replaces the whole set: a generate affordance on a populated list could
  // silently discard angles the founder wrote by hand on the profile page.
  const handleGenerateAngles = useCallback(async () => {
    if (!profileId || generatingAngles) return;
    if (angles.length > 0) {
      revealAngles();
      return;
    }
    setGeneratingAngles(true);
    setAngleError(null);
    try {
      const data = await api.generateContentAngles(profileId);
      const fresh = adoptAngles(data) || [];
      // Generated in-session at the founder's own click: there is nothing to
      // gate, so the fresh six render immediately.
      revealAngles();
      // The fresh set has new row ids, so a previous pick would dangle and
      // the goal picker would collapse to its wait state. Park the founder
      // on the strongest new angle; an empty set clears the pick.
      if (!fresh.some((a) => a && a.id === angleId)) {
        setAngleId(fresh.length > 0 ? fresh[0].id : "");
      }
      if (!data.angles?.length) {
        setAngleError("The model returned no usable angles. Try again.");
      }
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setGeneratingAngles(false);
    }
  }, [profileId, angleId, generatingAngles, angles.length, revealAngles]);

  // Regenerating the audience angles without leaving the wizard. Offered on
  // a populated list too, because the regenerate endpoint keeps hand-written
  // angles server-side: what the founder wrote on the profile page survives
  // this call. (The bare generate endpoint replaces the whole set and stays
  // empty-list-only — that distinction is why these are two buttons.)
  //
  // But generated angles that have a project built on them are deleted and
  // rewritten fresh: the draft survives, the story it was planned around does
  // not. A confirm at the click — the same pattern as plan regen — names that
  // before it happens instead of two screens later.
  const handleRegenerateAngles = useCallback(async () => {
    if (!profileId) return;
    const selectedHasProject = Boolean(project && project.content_angle_id && project.content_angle_id === angleId);
    if (selectedHasProject) {
      const ok =
        typeof window === "undefined" || typeof window.confirm !== "function"
          ? false
          : window.confirm(
              "A draft on this step is built around the angle you picked. Regenerating replaces that " +
                "angle's text with new material and the draft loses its story. Continue?"
            );
      if (!ok) return;
    }
    setGeneratingAngles(true);
    setAngleError(null);
    setAngleRegenNotice(null);
    try {
      const data = await api.regenerateContentAngles(profileId);
      const fresh = adoptAngles(data) || [];
      // Replacement rows carry new ids: a pick aimed at the old set would
      // dangle and the goal picker would collapse to its wait state just
      // when fresh options arrived. A surviving row (a kept manual angle)
      // keeps the founder's pick; otherwise park on the strongest new one.
      if (!fresh.some((a) => a && a.id === angleId)) {
        setAngleId(fresh.length > 0 ? fresh[0].id : "");
      }
      const affected = Number(data?.projects_affected) || 0;
      if (affected > 0) {
        setAngleRegenNotice(
          `Regenerated. ${affected} ${affected === 1 ? "draft was" : "drafts were"} built on the replaced angles and lost their story — reopen ${affected === 1 ? "it" : "them"} to re-plan.`
        );
      }
      if (!data.angles?.length) {
        setAngleError("The model returned no usable angles. Try again.");
      }
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setGeneratingAngles(false);
    }
  }, [profileId, angleId, project]);

  // Cycle the selected angle's six goal suggestions. Free (no model call),
  // and the server persists the variant, so re-reading the list brings back
  // the exact new order for every consumer of the angles state.
  const handleRegenerateGoals = useCallback(async () => {
    if (!profileId || !angleId) return;
    setCyclingGoals(true);
    try {
      await api.regenerateContentAngleGoals(profileId, angleId);
      const data = await api.getContentAngles(profileId);
      adoptAngles(data);
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setCyclingGoals(false);
    }
  }, [profileId, angleId, adoptAngles]);

  useEffect(() => {
    if (step !== 2 || !profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    if (tailorKeyRef.current === key) return;
    tailorKeyRef.current = key;
    runTailoring(false);
  }, [step, profileId, objective, runTailoring]);

  // Template cards stay hidden until this profile/objective has its own custom
  // set. Recommendations otherwise arrive first and show pre-made cards before
  // the tailored templates exist. On a tailoring failure with no custom set,
  // the ranked curated fallback is shown instead of an empty step.
  const tailorKey = profileId && objective ? `${profileId}:${objective}` : "";
  const recRequestKey = `${profileId || ""}:${angleId || ""}:${objective || ""}`;
  const tailoredReady = Boolean(
    tailorKey && tailored.key === tailorKey && tailored.templates.length > 0
  );
  const tailorFallbackVisible = Boolean(
    tailorKey &&
      tailored.key === tailorKey &&
      tailored.templates.length === 0 &&
      tailorError &&
      !tailoring
  );
  const recommendationsVisible = Boolean(
    objective &&
      recKey &&
      recKey === recRequestKey &&
      (tailoredReady || tailorFallbackVisible)
  );
  // Once the custom set is ready, only its templates are shown. The ranked
  // curated fallback remains available when tailoring fails with no custom
  // set, so a model outage does not strand the step.
  const visibleRecommendations = useMemo(() => {
    if (!recommendationsVisible) return [];
    if (!tailoredReady) return recommendations;
    const tailoredIds = new Set(
      (tailored.templates || []).map((t) => t?.id).filter(Boolean)
    );
    return recommendations.filter((r) => tailoredIds.has(r?.template?.id));
  }, [recommendationsVisible, tailoredReady, tailored.templates, recommendations]);

  // Live count-up while templates tailor ("Reading template 2 of 4…"). The
  // total is the outgoing list — the only honest denominator mid-flight —
  // and the line unmounts on settle or error, same contract as the other
  // generation counts.
  const tailorTotal = Math.max(visibleRecommendations.length, 1);
  useEffect(() => {
    if (!tailoring) {
      setTailorCount(0);
      return undefined;
    }
    setTailorCount(1);
    tailorTimer.current = setInterval(() => {
      setTailorCount((c) => (c >= tailorTotal ? tailorTotal : c + 1));
    }, 450);
    return () => {
      clearInterval(tailorTimer.current);
      tailorTimer.current = null;
    };
  }, [tailoring, tailorTotal]);
  // Preselect the top pick only once its key is displayable. Deliberately not
  // "on every reload": a reload must never move a selection the founder made,
  // so the only conditions are that nothing is selected and nothing has ever
  // been hand-picked.
  useEffect(() => {
    if (!recommendationsVisible) return;
    if (templateId || templateChosenByHand.current) return;
    if (visibleRecommendations.length === 0) return;
    setTemplateId(visibleRecommendations[0].template.id);
  }, [visibleRecommendations, recommendationsVisible, templateId]);

  const selectProfile = async (id) => {
    setSelectedProfileId(id);
    setAngles([]);
    setAngleId("");
    setRecommendations([]);
    setRecError(null);
    setEdits({});
    setProject(null);
    // The template is cleared with everything else, because it was chosen
    // against the previous app's profile. This was latent before; auto-selection
    // made it reachable, since a template preselected for one app would survive
    // the switch and the new profile's recommendations would then see a
    // selection already made and decline to preselect theirs.
    setTemplateId("");
    // The objective and tone were left behind, which is the same bug for a
    // different field: both are creative direction chosen against the PREVIOUS
    // app, and both are written onto the next project in createProject. Carrying
    // them over means the new app's plan is built toward another app's goal,
    // and the Audience & goal step shows a choice the founder already made for
    // a product they just switched away from.
setObjective("");
        setTone("");
        // The latch is per-app, not per-session: a deliberate pick for one app says
        // nothing about the next one, so the new app starts from its own top pick.
        templateChosenByHand.current = false;
        try {
          const d = await api.getContentAngles(id);
          adoptAngles(d);
        } catch {
          setAngles([]);
          setObjectiveEvidence({});
    }
    setStep(1);
  };

  const createProject = async (overrides = {}) => {
    setBusy(true);
    setError(null);
    try {
      // Neither duration_seconds nor extend_intent is sent, on either path.
      //
      // The length is the template's: create_studio_project reads
      // `default_duration` off the template the founder just picked and seeds
      // the project from it, so sending a number here could only be a stale
      // copy of a decision the founder is not making. The two columns this used
      // to write are still in the SQLite schema and are still accepted on the
      // request model, so an old payload would be accepted and silently
      // discarded — which is exactly the kind of write that looks like it did
      // something and did nothing.
      const created = project?.id
        ? await api.updateStudioProject(project.id, {
            content_angle_id: angleId || "",
            template_id: templateId || "",
            objective,
            tone,
            ...overrides,
          })
        : await api.createStudioProject({
            brand_profile_id: profileId,
            content_angle_id: angleId || "",
            template_id: templateId || "",
            objective,
            tone,
          });
      setProject(created);
      return created;
    } catch (err) {
      setError(getErrorMessage(err));
      return null;
    } finally {
      setBusy(false);
    }
  };

  /**
   * Make sure a draft exists without the founder having to ask.
   *
   * The render step writes to a studio project, and the plan is meant to be
   * validated BEFORE anything is rendered. Previously the project was only   * created by the plan step, which forced the Assets step to carry a manual
   * "Create draft" button purely to get out of the way.
   *
   * So: as soon as an App Profile and a hook template are both chosen, the
   * draft is created or updated in the background. A draft calls no model —
   * only a marked-ready generation renders — so doing this eagerly costs
   * nothing. Returns the project, or null when it cannot be created.
   */
  const ensureProject = useCallback(async () => {
    if (!profileId || !templateId) return null;
    try {
      if (project?.id) {
        // Keep the draft's selections in step with the wizard without
        // disturbing a plan that already exists.
        if (
          project.template_id === templateId &&
          // Both sides normalize to "": the writes below send angleId || "",
          // so comparing against (angleId || null) never matched an empty
          // angle and every call fell through to a wasted update write -- which
          // the eager-create effect above turned into an infinite
          // update -> setProject -> re-fire loop.
          (project.content_angle_id || "") === (angleId || "") &&
          project.objective === (objective || "")
        ) {
          return project;
        }
        // duration_seconds is deliberately NOT sent here, and neither is
        // anything else that would move the length. The project already carries
        // the length it was seeded with, and once a plan exists the server
        // refuses a change to it outright — the beats in the shot timeline were
        // clamped to that number, so a separate write could only produce a
        // timeline that no longer adds up.
        const updated = await api.updateStudioProject(project.id, {
          content_angle_id: angleId || "",
          template_id: templateId || "",
          objective,
          tone,
        });
        setProject(updated);
        return updated;
      }
      const created = await api.createStudioProject({
        brand_profile_id: profileId,
        content_angle_id: angleId || "",
        template_id: templateId || "",
        objective,
        tone,
      });
      setProject(created);
      return created;
    } catch (err) {
      // A failure here is not fatal: the plan step still creates the draft and
      // surfaces the error properly. Swallowing it here would just show an
      // empty render step with no explanation.
      setError(getErrorMessage(err));
      return null;
    }
  }, [profileId, templateId, angleId, objective, tone, project]);

  // Wire up the eager creation the ensureProject docstring promises: as soon
  // as a profile and template are both chosen, the draft is created (or kept
  // in step) in the background. Without this the render step shows "Create the
  // draft" instead of the Generate button whenever a founder reaches it by the
  // step pills rather than through the Review step, which is exactly when the
  // button "sometimes" vanishes. A ref guards against concurrent calls because
  // ensureProject is async and the effect re-fires on every project write.
  const ensureProjectInFlight = useRef(false);
  const lastSyncedKey = useRef("");
  useEffect(() => {
    if (!profileId || !templateId || ensureProjectInFlight.current) return;
    // One sync per selection-set. Without this, any server echo that differs
    // from what was sent (a dropped angle, a normalized field, or a stub that
    // answers a create with a canned project) would ping-pong
    // update -> setProject -> re-fire forever, because this effect re-runs on
    // every project write. The manual buttons bypass the guard and call
    // ensureProject directly.
    const key = `${profileId}:${templateId}:${angleId || ""}:${objective || ""}`;
    if (lastSyncedKey.current === key) return;
    lastSyncedKey.current = key;
    ensureProjectInFlight.current = true;
    ensureProject().finally(() => {
      ensureProjectInFlight.current = false;
    });
  }, [profileId, templateId, angleId, objective, ensureProject]);

  const handleGeneratePlan = async () => {
    if (!angle || !objective) {
      setError("Choose an audience angle and a video goal before generating the plan.");
      setPlanFailed(true);
      return;
    }
    // Single flight. Concurrent triggers — a double-tapped Regenerate, the
    // auto effect racing a manual retry — must not stack minute-long model
    // calls: each holds `busy`, so stacked flights read as a frozen page
    // with every control disabled. A call already in flight owns the
    // outcome; the extra tap is dropped. The buttons it could come from are
    // `busy`-disabled anyway, so this only ever bites on same-tick races.
    if (planInFlightRef.current) return;
    planInFlightRef.current = true;
    const ready = await createProject();
    if (!ready) {
      // createProject already reported the error above. Record the outcome
      // so Review offers the retry instead of the generating spinner.
      planInFlightRef.current = false;
      setPlanFailed(true);
      return;
    }
    setPlanFailed(false);
    setBusy(true);
    setError(null);
    try {
      // Switching template after a plan already exists is a rejection of the
      // template the first plan was built from. Recorded here rather than at
      // selection time, because selecting a template is a normal part of the
      // flow and only the replacement is a signal.
      if (ready.script_version > 0 && ready.template_id && ready.template_id !== templateId) {
        recordSignal("template_rejected", "template_changed", {
          brand_profile_id: profileId,
          studio_project_id: ready.id,
          template_id: ready.template_id,
        });
      }
      const updated = await api.generatePlan(ready.id, {
        objective,
        tone,
      });
      // A freshly generated plan is exactly the text the founder is about to
      // read on Review, so the project is marked ready as part of generating
      // it. There is no manual mark-ready control anywhere: a click that could
      // only confirm what the studio already knew was a button with no meaning,
      // and its absence was read as the render button being broken. The server
      // recomputes claim safety on this call and refuses when a prohibited
      // claim is present, so the gate is unchanged -- it just happens without
      // the founder having to say "I saw it".
      //
      // A refusal is kept as the plan's own state rather than surfaced as a
      // thrown error, because the plan landed and is readable; the render
      // button then states the real reason (a prohibited claim, a missing
      // photograph) instead of the screen looking broken.
      let settled = updated;
      let readyError = null;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        // The plan landed and is readable, so this is not a failure of the step.
        // The render button below names the real reason (a prohibited claim, or
        // a photograph still owed); swallowing this without comment is what made
        // a refused project look broken rather than gated.
        settled = updated;
        readyError = err;
      }
      // Record what the server now holds, so the Review re-read knows this state is
      // already current and cannot resolve an older row over it. Taken from
      // `settled`, not `updated`: marking ready is itself a write, so its row is
      // the fresher of the two.
      if (settled?.id) {
        syncedProjectsRef.current[settled.id] = settled.updated_at || "";
      }
      // A refusal is stated rather than swallowed, so a founder who lands on a
      // disabled render button can read why instead of assuming the app broke.
      setError(readyError ? getErrorMessage(readyError) : null);
      setProject(settled);
      setEdits({});
      setReviewThumb(0);
      // Straight to the top of Review, which is this step now: the plan is the
      // thing to read, and the render step below it is the first one that
      // calls the model. The old indices were 5 (Review) and 6 (Hook and
      // middle); merging the plan step into Review moved both down by one.
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err));
      setPlanFailed(true);
    } finally {
      planInFlightRef.current = false;
      setBusy(false);
    }
  };

  /* Takes the founder to the photo upload, wherever they currently are.
     It lives on the template step now, so this both jumps to that step and
     scrolls to the field — otherwise "Add your photo" would land them on a step
     with nothing obviously about photographs in view. */
  const scrollToTemplatePhoto = () => {
    setStep(2);
    // After the step renders, not before: the element does not exist yet.
    requestAnimationFrame(() => {
      document
        .getElementById("template-photo")
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  };

  const handleSaveEdits = async () => {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      // Measured against the saved script, not the textarea, so a save that
      // changes nothing records nothing.
      const editSignal = Object.prototype.hasOwnProperty.call(edits, "script")
        ? classifyScriptEdit(project.script, edits.script)
        : "";
      const updated = await api.updateStudioProject(project.id, edits);
      if (editSignal) {
        recordSignal("script_edited", editSignal, {
          brand_profile_id: profileId,
          studio_project_id: project.id,
          template_id: project.template_id,
        });
      }
      // A content save un-readies the project server-side (ready_for_generation
      // -> draft), because the strategy and the approval both describe the text
      // as it was before this edit. Re-marked here for the same reason plan
      // generation marks it: the founder just reviewed the exact words they
      // saved, so the approval still describes what they read, and there is no
      // manual mark-ready control for them to reach for instead.
      //
      // The readiness rule this encodes: an edit the founder saved after reading
      // it keeps the project approved, and a server refusal (a claim that is now
      // prohibited, a photograph detached) is reported rather than hidden -- so
      // the render button is disabled with a stated reason instead of the screen
      // looking broken.
      let settled = updated;
      let readyError = null;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        settled = updated;
        readyError = err;
      }
      if (settled?.id) {
        syncedProjectsRef.current[settled.id] = settled.updated_at || "";
      }
      setError(readyError ? getErrorMessage(readyError) : null);
      setProject(settled);
      setEdits({});
      setReviewThumb(0);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // Thumbs-down on Review asks the AI for a better plan; thumbs-up records
  // the approval and moves to Hook + Story. Down reuses the existing plan
  // generation (claim check + ready marking included), capped at three
  // refinements per saved plan version so the loop always terminates.
  const handleReviewThumb = async (next) => {
    setReviewThumb(next);
    if (next === 0 || !project?.id) return;
    recordThumb("plan", next, {
      brand_profile_id: profileId,
      studio_project_id: project.id,
      template_id: project.template_id,
      detail: `plan v${Number(project.script_version) || 0}`,
    });
    if (next === 1) {
      setStep(4);
      return;
    }
    const versionKey = String(Number(project.script_version) || 0);
    const used = Number(reviewRefinesRef.current[versionKey] || 0);
    if (used >= 3) {
      setError(
        "Three fresh plans written for this version already — edit the script by hand or pick another template before refining again."
      );
      // No refinement happened, so the thumb must not stay pressed: left
      // active it claims a fourth plan is coming that the cap forbids.
      setReviewThumb(0);
      return;
    }
    reviewRefinesRef.current[versionKey] = used + 1;
    await handleGeneratePlan();
    setReviewThumb(0);
  };

  // A template can be selected either via URL param (templateId) or stored
  // on the project (project.template_id). The URL param wins when present
  // because it reflects the founder's current intent; the project's value is
  // a fallback for cases like auto-generation on Review where the URL param
  // hasn't been set yet but the project already knows its template.
  const effectiveTemplateId = templateId || project?.template_id;
  const canGenerate = Boolean(profileId && effectiveTemplateId);

  // First missing choice in flow order, for the one red button on panels that
  // refuse to generate until the plan's inputs exist. Profile, then angle,
  // then goal (both live on step 1), then template. The button below names
  // the destination, so this stays data — never a second copy of the labels.
  // Each label carries "first" on purpose: the founder is being sent back
  // because this action gates everything after it, and the button must say
  // so rather than reading as a plain navigation link.
  const firstGap = !profileId
    ? { step: 0, label: "Choose an App Profile first" }
    : !angle
      ? { step: 1, label: "Pick an audience angle first" }
      : !objective
        ? { step: 1, label: "Set the video goal first" }
        : !effectiveTemplateId
          ? { step: 2, label: "Pick a template first" }
          : null;

  // Face-only product: every template requires exactly the character
  // reference, and the backend refuses a generation without one (see
  // _studio_identity_references) as well as any project still holding
  // retired uploads. The requirement used to be decoration: it was listed
  // on the template but nothing stopped the click, so a render could
  // go out with no identity input and the model free to invent a presenter.
  //
  // Kept separate from canGenerate on purpose — "you have not chosen a template
  // yet" and "you still owe this template a photograph" are different problems
  // and the founder needs to be told which one they have. The split lives in
  // a tested helper rather than inline here.
  const effectiveTemplate = template || project?.template_id ? { ...template, id: template?.id || project?.template_id } : null;
  const missingIdentity = effectiveTemplate
    ? blockingRequirements(effectiveTemplate.required_assets, project?.assets)
    : [];
  // Server-side refusal is the guarantee; this is the early warning. Not folded
  // into canGenerate, because "you have not chosen a template yet" and "you
  // still owe this template a photograph" are different problems.
  const blockedOnAssets = Boolean(effectiveTemplate) && missingIdentity.length > 0;
  // What the generated piece is and how long it will be — a statement, not a
  // control. Once a project exists its own number is the authority, because
  // that is the length the plan's beat timeline was written to and the length
  // the render is asked for. Before that, the selected template's declared
  // length is what the project will be seeded from, so showing it predicts the
  // same value rather than offering a second one.
  //
  // The hook/middle breakdown is not shown here any more. It lived in a "What
  // you get" card on this step, which was a block of prose between the two
  // choices the step is actually for; the same numbers are on Review, where the
  // length is a read-only field, and the picked angle's own panel.
  const pieceSeconds = readPieceSeconds(project, template);

  const editValue = (key, fallback) =>
    edits[key] !== undefined ? edits[key] : project?.[key] ?? fallback;
  const hasEdits = Object.keys(edits).length > 0;

  // Tone is editable here and also seeds the plan, so a change has to move
  // both or going back and regenerating would silently reinstate the old value.
  // Length has no editor on this step at all, editable or otherwise: it is the
  // template's number, and the plan's beat timeline is built to it.
  const editTone = (value) => {
    setTone(value);
    setEdits((prev) => ({ ...prev, tone: value }));
  };

  // The goal the plan is written toward: the wizard's own choice wins, and the
  // draft's stored goal is the fallback so landing on Review with a complete
  // draft always auto-fires — even when this session's state lost the choice
  // (pill-jump, reload) while the server row kept it. Without the fallback the
  // step shows the goal picker and waits, although everything the plan needs
  // is already decided.
  const effectiveObjective = objective || project?.objective || "";

  // Auto-generate the plan on entering Review with a ready draft that has
  // none yet. The step exists to READ the plan, so arriving to an empty step
  // plus a button was a wasted click on every first pass. Same gates as the
  // manual retry below (a profile, a template, a goal, nothing in flight):
  // without them there is nothing to write the plan from. When a gate is
  // unmet the step names the missing input instead of spinning; a failed
  // attempt sets planFailed and offers the retry, and the latch below means
  // a failure never loops. Regenerating an existing plan stays a deliberate,
  // confirmed click. Placed after the renderability consts above:
  // the dep array reads them during render, so this cannot live above their
  // declarations the way the other effects do.
  const planAutoAttempted = useRef("");
  // Single-flight latch for plan generation, owned by handleGeneratePlan.
  // `busy` state cannot do this job: two taps in the same tick both read the
  // still-false state, so both would start a model call. A ref flips
  // synchronously, collapsing the race before the first await.
  const planInFlightRef = useRef(false);
  useEffect(() => {
    // The plan needs a profile, a template and a goal. The character photo is
    // required to RENDER, not to write the plan, so it does not gate this.
    if (step !== 3 || busy || !canGenerate || !angle) return;
    if (!objective && project?.objective) {
      // The draft already holds the goal but this session's state does not:
      // adopt it so the gates below read one consistent choice and the plan
      // starts on arrival. Returned from, not fallen through, because the
      // state update re-runs this effect and the fire happens there — firing
      // here would send the draft's goal while `objective` is still empty.
      setObjective(project.objective);
      return;
    }
    if (!objective) return;
    if (project?.script_version) return;
    const key = `${profileId}:${templateId}:${angleId || ""}:${objective || ""}:${tone || ""}`;
    if (planAutoAttempted.current === key) return;
    planAutoAttempted.current = key;
    handleGeneratePlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleGeneratePlan is a render-scoped closure, same as handleGenerateStrategy in the auto-build below; the key ref guards re-fires, and listing it would re-run the effect on every render.
  }, [step, busy, canGenerate, objective, profileId, templateId, angleId, angle, tone, project?.id, project?.script_version, project?.objective]);

  // Review reads the project's words, so it must read them from the server
  // rather than trust whatever the wizard last held. An eager draft update
  // issued while the plan was still being written can resolve after it, which
  // leaves the editors showing a copy of the row from before the plan landed:
  // an empty Hook line and Script above a plan that the render step can count
  // characters in. Re-fetching on entry makes this step authoritative.
  //
  // Guarded three ways, because a read that fights a write is worse than no
  // read at all:
  //   - Keyed on the row's own version stamps, so it re-syncs only when the
  //     server has something new, and a refetch cannot loop against itself.
  //   - Unsaved edits always win; the founder's words are never overwritten.
  //   - Readiness is one-way. The plan handler marks the project ready right
  //     after generating, and this read was able to resolve with the row from
  //     just before that and quietly downgrade an approved project to a draft
  //     -- which left the render button disabled on the next step with nothing
  //     on screen to explain it. A read may move a project forward; it may
  //     never move one back.
  const reviewSynced = useRef("");
  const editsRef = useRef(edits);
  useEffect(() => {
    editsRef.current = edits;
  }, [edits]);
  useEffect(() => {
    if (step !== 3 || !project?.id || busy) return;
    // A row the wizard already adopted from a server response needs no read,
    // and cannot be improved on by another one. That covers the deep-link load
    // and the plan handler's own settled row.
    //
    // The second case is not just a wasted request. Marking ready is itself a
    // write, and a read issued around it could resolve with the row from before
    // it -- quietly downgrading an approved project to a draft and leaving the
    // render button disabled on the next step with nothing on screen to explain
    // it. Skipping the read is the fix; a one-way adoption below is the backstop
    // for any read that still happens.
    if (syncedProjectsRef.current[project.id] !== undefined) {
      return;
    }
    const key = `${project.id}:${project.updated_at || ""}:${project.script_version || 0}`;
    if (reviewSynced.current === key) return;
    reviewSynced.current = key;
    let cancelled = false;
    api
      .getStudioProject(project.id)
      .then((fresh) => {
        if (cancelled || !fresh) return;
        if (Object.keys(editsRef.current).length > 0) return;
        if (project.status === "ready_for_generation" && fresh.status !== "ready_for_generation") {
          return;
        }
        syncedProjectsRef.current[project.id] = fresh.updated_at || "";
        setProject(fresh);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [step, project?.id, project?.updated_at, project?.script_version, project?.status, busy]);

  /* Progress state, derived rather than tracked. A founder can reach any step
     from any other, so nothing here can be a counter that advances — the pills
     have to be recomputed from what actually exists, or they go stale the moment
     they change something on an earlier step. */
  const stepStates = stepCompletion({
    profileId,
    objective,
    angleId,
    templateId,
    project,
    missingIdentity,
    hasEdits,
  });

  /* What a satisfied pill names beside its tick. Derived like the states, so
     a changed pick renames its pill on the next render instead of going
     stale. Only done pills carry one: anything earlier has nothing picked
     yet, and the render step never completes. */
  function pillValue(key) {
    if (key === "profile") {
      return profiles.find((p) => p.id === profileId)?.brand_name || null;
    }
    if (key === "angle") {
      return angles.find((a) => a.id === angleId)?.label || objective || null;
    }
    if (key === "template") {
      return template?.name || null;
    }
    if (key === "review") {
      return project?.script_version ? `Plan v${project.script_version}` : null;
    }
    return null;
  }

  const stepContent = renderStep();

  function renderStep() {
    if (step === 0) {
      // The gate and the explanation come from one place, so the picker can
      // never become permissive while still claiming it excludes the rest.
      const { approved, unapproved } = partitionProfiles(profiles);
      return (
        /* Titled like every other step. Title only, no description: the
           rail's own sentence names the one thing to do here, and a second
           sentence restating it is the duplication step 3's title-only shell
           already avoids. */
        <StepShell
          icon={Briefcase}
          title="App Profile"
        >
          {approved.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No approved App Profile"
              description={describeEmptySelection(profiles)}
              action={
                <Button variant="brand" asChild>
                  <Link to="/brand">Create or approve an App Profile</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid gap-3 [grid-template-columns:repeat(auto-fit,minmax(min(100%,20rem),20rem))]">
              {/* Auto-fit with a capped column: one app sits in a single tidy
                  card instead of stretching full width, and more apps flow
                  into further columns as the frame allows — no breakpoint to
                  update when the second or fifth app arrives. */}
              {approved.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={profileId === p.id}
                  onClick={() => selectProfile(p.id)}
                  className={`card-pickable rounded-2xl border p-5 text-left ${
                    profileId === p.id
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-sm font-semibold">{p.brand_name}</span>
                    {profileId === p.id && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">
                    {p.app_category || p.niche || "Category not set"}
                  </p>
                </button>
              ))}
            </div>
          )}

          {unapproved.length > 0 && (
            <div className="rounded-2xl border border-[color:var(--hairline)] bg-secondary/20 p-5">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-semibold">
                    {describeUnapprovedCount(unapproved.length)}
                  </p>
                  {unapproved.length > 3 ? (
                    <details className="mt-0.5">
                      <summary className="cursor-pointer text-xs text-muted-foreground">
                        Show all {unapproved.length} apps
                      </summary>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {unapproved.map(profileLabel).join(", ")}
                      </p>
                    </details>
                  ) : (
                    <p className="mt-1 text-xs text-muted-foreground">
                      {unapproved.map(profileLabel).join(", ")}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground" data-subtitle="">
                    Draft profiles need review before a video can use them.
                  </p>
                  <Button variant="secondary" size="sm" asChild className="mt-3">
                    <Link to="/brand">Review in App Profile</Link>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </StepShell>
      );
    }

    if (step === 1) {
      return (
        <StepShell
          icon={Target}
          title="Audience & goal"
        >
          <div className="space-y-4" data-testid="audience-goal-step">
            {/* No description on this shell. It carried one three times over:
                the progress rail's own sentence above it, and the angle's hint
                below it, both named the same instruction. The rail's sentence is
                gone now too, and what remains here is text specific to what is
                on screen — the angle you picked, and the goals ranked for it.

                The angle is required: the strategy and the render are built
                around it, so a video without one is the generic framing this
                step exists to prevent. Each block on this step is its own
                bordered card so the picker and the goal list
                read as separate organized units. */}
            <AngleSelector
              angles={angles}
              angleId={angleId}
              onSelect={setAngleId}
              showAngles={showAngles}
              generating={generatingAngles}
              error={angleError}
              onGenerate={handleGenerateAngles}
              onRegenerate={handleRegenerateAngles}
              notice={angleRegenNotice}
            />

            {/* The goal step is intentionally downstream of the angle. The panel
                only exists once there is an angle to show goals for: before
                that the picker renders just its waits marker, and wrapping an
                empty marker in an inset-panel is how the stray empty box below
                the angle panel happened. */}
            <div className={angle ? "inset-panel" : undefined}>
<AngleGoalPicker
              angle={angle}
              value={objective}
              onPick={setObjective}
              options={objectiveOptions}
              recommendations={recommendedObjectives}
              outcomes={objectiveOutcomes}
              fitReasons={objectiveFitReasons}
              objectiveEvidence={objectiveEvidence}
              suggestions={angle?.goal_suggestions}
              onRegenerate={handleRegenerateGoals}
              regenerating={cyclingGoals}
            />
            </div>

            {angle && objective && (
              <ComponentThumbs
                component="goal"
                question="Is this the right goal for your customers?"
                hint="Rates the goal only. It shapes future goal suggestions for this app."
                resetKey={`${angleId}:${objective}`}
                refs={{
                  brand_profile_id: profileId,
                  studio_project_id: project?.id,
                  detail: `objective=${objective};kind=${angle.kind || ""}`,
                }}
                testId="goal-feedback"
              />
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 2) {
      return (
        <StepShell
          icon={LayoutTemplate}
          title="Choose a template & add your photo"
        >
          <div className="space-y-4">
            {/* No description here either: it restated the rail and then
                pre-empted the Presenter photo section's own instruction, which
                sits directly under it. The photo is described where it is
                attached, not twice above it. */}
            {/* No objective means no honest scoring to show. The card list used
                to render anyway with the empty rationale the scorer returns, so a
                founder could pick the top card from reasons that did not mention
                their goal at all. */}
            {!objective && (
              <div className="inset-panel space-y-2">
                {/* Same recessed sub-card as the angle picker: eyebrow label,
                    one helper line, the coral action beneath. The dashed
                    centered box said the same thing with more chrome and a
                    quieter button. */}
                <GroupLabel icon={LayoutTemplate}>Template</GroupLabel>
                <p className="text-xs text-muted-foreground" data-subtitle="">
                  Set the goal first, then the templates are ranked for it.
                </p>
                <Button variant="brand" onClick={() => setStep(1)} className="gap-1.5">
                  <Target className="h-3.5 w-3.5" /> Set the goal
                </Button>
              </div>
            )}
            {profileId && objective && (
              <div className="flex flex-wrap items-center gap-2">
                {tailoring ? (
                  <>
                    <p className="flex items-center gap-2 text-xs text-muted-foreground">
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      Tailoring templates for this goal…
                    </p>
                    <p className="text-xs text-muted-foreground" role="status" data-testid="templates-progress">
                      Reading template {tailorCount} of {tailorTotal}…
                    </p>
                  </>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => runTailoring(true)}
                    title="Replace this goal's tailored templates with a fresh set"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Regenerate tailored templates
                  </Button>
                )}
              </div>
            )}
            {tailorError && !tailoring && (
              <p className="text-xs text-muted-foreground">{tailorError}</p>
            )}
            {objective && recommendationsVisible && visibleRecommendations.length === 0 && (
              <div className="inset-panel">
                <p className="text-sm">No templates recommended for this app yet.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {recError
                    ? `Ranking failed (${recError}).`
                    : "Nothing ranked for this profile and goal."}
                </p>
              </div>
            )}
            {objective && recommendationsVisible && visibleRecommendations.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">
                  {tailoredReady ? "Tailored for this app" : "Recommended"}
                </span>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {visibleRecommendations.map((r, i) => (
                  <RecommendationCard
                    key={r.template.id}
                    r={r}
                    index={i}
                    selected={templateId === r.template.id}
                    onSelect={() => {
                      // Latched, so a later reload cannot move this pick.
                      templateChosenByHand.current = true;
                      setTemplateId(r.template.id);
                    }}
                  />
                ))}
                </div>
              </div>
            )}

            {template && (
              <div className="inset-panel text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{template.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {humanize(template.category)}
                  </Badge>
                  {/* Says which of the two states the founder is in. A
                      preselected template is a starting point scored for this
                      app and this goal, and clicking any other card replaces it
                      — but nothing on screen would otherwise distinguish that
                      from a pick they made. */}
                  {!templateChosenByHand.current && (
                    <Badge variant="secondary" className="text-xs">
                      Suggested
                    </Badge>
                  )}
                </div>
                {/* The outcome leads; the mechanic badge above stays as the
                    secondary label. Director-speak (opening_structure) follows
                    in muted text for the founder who wants the how. */}
                {typeof template.outcome === "string" && template.outcome.trim() && (
                  /* Tailored templates are model-written, so this line can open
                     lowercase next to the hand-written copy above it. */
                  <p className="mt-1 text-sm text-foreground/90">{sentenceCase(template.outcome.trim())}</p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{sentenceCase(template.opening_structure)}</p>
                <TemplateShape template={template} />
                {/* The requirement is stated in one line rather than as a
                    checklist. It was a fourth place the same photograph was
                    reported — template card, upload panel, asset row, and the
                    "Attached" block below all showed it — and the photo section
                    immediately underneath is where the photo actually lives, so
                    the card's job is to say whether anything is still owed and
                    point at it. */}
                {template.required_assets?.length > 0 && project && missingIdentity.length > 0 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-2"
                    onClick={scrollToTemplatePhoto}
                  >
                    <ImageIcon className="h-3.5 w-3.5" /> Add your photo below
                  </Button>
                )}
              </div>
            )}

            {effectiveTemplateId && (
              <ComponentThumbs
                component="template"
                question="Is this template a good fit for your customers?"
                hint="Rates the template only. It reorders and reshapes future template suggestions."
                resetKey={effectiveTemplateId}
                refs={{
                  brand_profile_id: profileId,
                  studio_project_id: project?.id,
                  template_id: effectiveTemplateId,
                }}
                testId="template-feedback"
              />
            )}

            {/* The photo upload lives here now rather than on its own step. It
                was the only thing on that step, so a founder picked a template,
                left, uploaded, and came back — and the template step already
                said what was missing and offered a jump. The draft is created
                eagerly from the profile and template (see ensureProject), so by
                the time anyone reaches this there is almost always something to
                attach to. */}
            {/* Second sub-card in the same style, not a divided-off section:
                the parent's gap separates it, the way the angle picker's
                groups sit apart. Same one-line helper at the same size as the
                template card above — the two sit side by side, so a different
                type size read as a different kind of control. The gated
                consequence moved off this line and into the empty state below,
                which is where a founder blocked on a missing template already
                reads why. */}
            <div id="template-photo" className="inset-panel space-y-2">
              <GroupLabel icon={ImageIcon}>Presenter photo</GroupLabel>
              <p className="text-xs text-muted-foreground" data-subtitle="">
                Upload one clear photo of the person you want on camera.
              </p>
              {!templateId ? (
                /* Gated, the card would otherwise be a label and a sentence
                   with nothing under them. This says what is waiting, on the
                   same size and budget as the subtitle above. */
                <p className="text-xs text-muted-foreground" data-subtitle="">
                  Pick a template above first; your photo attaches to it.
                </p>
              ) : !project ? (
                <>
                  <p className="text-sm text-muted-foreground">
                    Preparing the video draft for your photo…
                  </p>
                  <Button variant="secondary" size="sm" disabled={busy} onClick={() => ensureProject()}>
                    {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
                    Try preparing the draft again
                  </Button>
                </>
              ) : (
                <>
                  <AssetLibrary
                    embedded
                    profileId={profileId}
                    projectId={project.id}
                    projectAssets={project.assets}
                    onProjectChanged={(fresh) => setProject(fresh || project)}
                    onChanged={() => {
                      // Re-read the project's attached assets so the picker updates.
                      api.getStudioProject(project.id).then(setProject).catch(() => {});
                    }}
                  />
                </>
              )}
            </div>
          </div>
        </StepShell>
      );
    }

    if (step === 4) {
      return (
        <StepShell
          icon={Sparkles}
          title="Hook + Story"
        >
          <div className="space-y-3">
            {/* No description on this shell. The one it carried was the
                progress rail's sentence almost word for word, followed by the
                piece's scope, which the render panel states itself. Neither
                fact needed a third copy. */}
            {!angle ? (
              /* The render is built around the audience angle, so it is the
                 first thing asked for here. This step used to have no angle
                 control at all: it could only point back at Audience & goal
                 (via the strategy panel) or at Review, leaving the choice
                 stranded on another screen while the founder was here to make
                 it. Same control, same gate, same position as step two. */
              <AngleSelector
                angles={angles}
                angleId={angleId}
                onSelect={setAngleId}
                showAngles={showAngles}
                generating={generatingAngles}
                error={angleError}
                onGenerate={handleGenerateAngles}
                onRegenerate={handleRegenerateAngles}
                notice={angleRegenNotice}
              />
            ) : !canGenerate ? (
              <div className="inset-panel">
                {/* Names what is actually missing, read from the same two
                    values that gated this panel. It used to spell out the
                    whole chain ("choose an App Profile, goal, and template,
                    then review the free plan") — a fourth copy of an
                    instruction the pills and each step already carry. */}
                <p className="text-sm text-muted-foreground">
                  {!profileId
                    ? "Pick an approved App Profile on the first step to continue."
                    : "Pick a template on the Template & photo step to continue."}
                </p>
              </div>
            ) : blockedOnAssets ? (
              <MissingRequirements
                identity={missingIdentity}
                onGoToTemplatePhoto={scrollToTemplatePhoto}
              />
            ) : !project ? (
              <div className="inset-panel">
                <p className="text-sm text-muted-foreground">
                  Preparing the video draft for your photo…
                </p>
                <Button
                  variant="brand"
                  className="mt-3"
                  disabled={busy}
                  onClick={() => {
                    /* Redirect before generating, same rule as every other red
                       button on a gated step: a click that cannot create must
                       take the founder to what is missing instead of dying
                       silently inside ensureProject's early return. The gates
                       above currently guarantee both values here, so these two
                       branches are backstops, not live paths. */
                    if (!profileId) {
                      setStep(0);
                      return;
                    }
                    if (!templateId) {
                      setStep(2);
                      return;
                    }
                    ensureProject();
                  }}
                  data-testid="create-draft-button"
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  Create the draft
                </Button>
              </div>
            ) : (
              <>
                {!project?.script_version ? (
                  <div className="inset-panel">
                    <p className="text-sm text-muted-foreground">
                      There's no plan yet. Generate one on Review first — it is free.
                    </p>
                    <Button
                      variant="brand"
                      className="mt-3 gap-1.5"
                      onClick={() => setStep(3)}
                    >
                      <CheckCircle2 className="h-3.5 w-3.5" /> Go to Review
                    </Button>
                  </div>
                ) : (
                  <>
                    <HookContinuityPanel
                      project={project}
                      onProjectChange={setProject}
                    />
                    {project?.strategy && (
                      <ComponentThumbs
                        component="script"
                        question="Does this script speak to your customers?"
                        hint="Rates the generated script only. It guides future scripts for this app."
                        resetKey={`${project.id}:${project.strategy_version || 0}`}
                        refs={{
                          brand_profile_id: profileId,
                          studio_project_id: project.id,
                          template_id: project.template_id,
                          detail: `strategy v${Number(project.strategy_version) || 0}`,
                        }}
                        testId="script-feedback"
                      />
                    )}
                    {/* The one and only render. It used to sit on the review
                        step, where it let a render run on text the founder had
                        not read yet, and it sat BELOW the segmented chain, which
                        made the chain look like the product.

                        onProjectChange lets the panel build the strategy itself
                        on the way to a render. It was a button above,
                        which meant a founder could skip it and get a
                        generic take without ever being told the specific one
                        existed. */}                    <GenerationPanel
                      project={project}
                      onGenerationChange={() => {}}
                      onProjectChange={setProject}
                    />
                  </>
                )}
              </>
            )}
          </div>
        </StepShell>
      );
    }

if (step === 3) {
      return (
        <StepShell
          icon={CheckCircle2}
          title="Review your script plan"
        >
        {!project?.script_version && planFailed && !busy ? (
          /* A plan attempt ran and failed. The page-level error above says why;
             this offers the retry. Manual and enabled: the auto latch already
             consumed this selection-set, so nothing here fires on its own. The
             photo is not listed: it is required to render, never to plan. */
          <div className="inset-panel space-y-3">
            <p className="text-sm text-muted-foreground">
              The plan didn't generate. Fix what's missing below, then try again — still free.
            </p>
            {(!objective || !angle) && (
              /* The angle is picked here, with the same control every other
                 step uses. `bare` because this panel is already an
                 inset-panel, and a bordered aside inside one is the box-in-a-box
                 the container levels reserve. */
              <>
                <AngleSelector
                  bare
                  angles={angles}
                  angleId={angleId}
                  onSelect={setAngleId}
                  showAngles={showAngles}
                  generating={generatingAngles}
                  error={angleError}
                  onGenerate={handleGenerateAngles}
                  onRegenerate={handleRegenerateAngles}
                  notice={angleRegenNotice}
                />
                <AngleGoalPicker
                  angle={angle}
                  value={objective}
                  onPick={setObjective}
                  options={objectiveOptions}
                  recommendations={recommendedObjectives}
                  outcomes={objectiveOutcomes}
                  fitReasons={objectiveFitReasons}
                  onChooseAngle={() => setStep(1)}
                  suggestions={angle?.goal_suggestions}
                  onRegenerate={handleRegenerateGoals}
                  regenerating={cyclingGoals}
                />
              </>
            )}
            <Button
              variant="brand"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || !objective || !angle}
            >
              <Sparkles className="h-4 w-4" />
              Try again
            </Button>
            <p className="text-xs text-muted-foreground" data-subtitle="">
              Writes hook, script, shots, and demo note. Editable below.
            </p>
          </div>
        ) : !project?.script_version && (busy || loading || (canGenerate && effectiveObjective && angle)) ? (
          /* No plan and nothing wrong: an attempt is in flight, the draft is
             still loading, or every input is present and the auto effect fires
             next — reading the stored goal too, so a draft that already holds
             one spins instead of flashing the picker. Only these three cases
             may show a spinner. */
          <div className="inset-panel space-y-3">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm font-semibold">
                {loading && !busy ? "Loading your draft…" : "Generating your plan…"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {loading && !busy
                ? "Picking up where you left off."
                : <PlanPhaseLine />}
            </p>
          </div>
        ) : !project?.script_version ? (
          /* No plan and the auto effect cannot fire: a profile, a template or
             the goal is missing. Name it and fix it here — choosing the goal
             starts the plan on its own, no button press. */
          <div className="inset-panel space-y-3">
            {/* One red button to the first missing choice, in flow order. The
                two black navigation buttons this replaces named their
                destinations but sat beside two different subtitles, so the
                panel read as three separate asks. The button names where it
                goes; the single subtitle below stays constant. Angle and goal
                stay fixable in place just beneath it. */}
            <GroupLabel icon={ListChecks}>Still missing</GroupLabel>
            <p className="text-xs text-muted-foreground" data-subtitle="">
              Your free plan starts once all required choices are set.
            </p>
            {firstGap && (
              <Button
                variant="brand"
                size="sm"
                onClick={() => setStep(firstGap.step)}
                data-testid="goto-first-gap-button"
              >
                {firstGap.label}
              </Button>
            )}
            {/* The angle is chosen here with the same control every other step
                uses. It sits below the red button because that button jumps
                to another step, while this one IS the choice being made
                right here. */}
            {(!objective || !angle) && (
              <>
                <AngleSelector
                  bare
                  angles={angles}
                  angleId={angleId}
                  onSelect={setAngleId}
                  showAngles={showAngles}
                  generating={generatingAngles}
                  error={angleError}
                  onGenerate={handleGenerateAngles}
                  onRegenerate={handleRegenerateAngles}
                  notice={angleRegenNotice}
                />
                <AngleGoalPicker
                  angle={angle}
                  value={objective}
                  onPick={setObjective}
                  options={objectiveOptions}
                  recommendations={recommendedObjectives}
                  outcomes={objectiveOutcomes}
                  fitReasons={objectiveFitReasons}
                  onChooseAngle={() => setStep(1)}
                  suggestions={angle?.goal_suggestions}
                  onRegenerate={handleRegenerateGoals}
                  regenerating={cyclingGoals}
                />
              </>
            )}
          </div>
        ) : (
          <div className="space-y-4">
            {/* Regenerating replaces a plan that may have been edited and
                approved, so it asks first — the same rule as the strategy
                rebuild, and for the same reason. The status beside it names
                the current version and whether it holds words: a version with
                nothing written is a blank row, never a plan, and says so
                rather than wearing a check it did not earn. */}
            {project?.script_version > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    if (hasEdits) {
                      const ok =
                        typeof window === "undefined" || typeof window.confirm !== "function"
                          ? false
                          : window.confirm(
                              "You have unsaved edits. Generating a new plan replaces this one and " +
                                "your edits are lost. Generate anyway?"
                            );
                      if (!ok) return;
                    } else {
                      const ok =
                        typeof window === "undefined" || typeof window.confirm !== "function"
                          ? true
                          : window.confirm(
                              `Replace plan v${project.script_version} with a new one? The current ` +
                                `plan is discarded.`
                            );
                      if (!ok) return;
                    }
                    handleGeneratePlan();
                  }}
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Regenerate plan
                </Button>
                <p className="text-xs text-muted-foreground" data-testid="plan-version-status">
                  Plan v{project.script_version}
                  {(project.hook_line || project.script)
                    ? " · generated ✓"
                    : " · empty — regenerate to write it"}
                </p>
              </div>
            )}
            <ReviewRevisionsPanel
              project={project}
              edits={edits}
              hasEdits={hasEdits}
              onGoToHookStory={() => setStep(4)}
            />
            <div className="inset-panel space-y-2" data-testid="review-thumb-loop">
              <span className="eyebrow block">Does this plan work?</span>
              <ThumbPair
                value={reviewThumb}
                disabled={busy || !project?.script_version}
                upLabel="Looks good"
                downLabel="Write a better one"
                testId="review-thumb"
                onChange={handleReviewThumb}
              />
              <p className="text-xs text-muted-foreground" data-subtitle="">
                Thumbs up moves on; thumbs down writes a fresh plan for you.
              </p>
            </div>
            <GroupLabel icon={FileText}>Script</GroupLabel>
            {/* What the chosen template is aiming to leave them with, above the
                hook and script it was picked to carry. The plan step showed the
                words and nothing about their intent, so a founder reading a
                hook had no way to tell whether it served the outcome the
                template was chosen for or was about to drift off it. Read-only
                and from the template, not the plan: it does not change when the
                script is edited, and regenerating the plan rewrites the words
                rather than the aim. Renders nothing for a tailored template
                generated before outcomes existed. */}
            {typeof template?.outcome === "string" && template.outcome.trim() && (
              <div className="inset-panel">
                <GroupLabel icon={Target}>What this is aiming to leave them with</GroupLabel>
                <p className="mt-1 text-sm">{sentenceCase(template.outcome.trim())}</p>
                <p className="mt-1 text-xs text-muted-foreground" data-subtitle="">
                  The outcome this template is built for, in their terms.
                </p>
                {/* Its own line, not a clause of the subtitle above: this is the
                    honesty guardrail — the outcome is a framing to write toward,
                    never a promise about what the video will do. Folding it into
                    the subtitle is exactly how it got cut once already, and the
                    budget would have taken it again. */}
                <p className="text-xs text-muted-foreground" data-subtitle="">
                  A framing to aim at, not a result this video can promise.
                </p>
              </div>
            )}
            {/* The arrival clamp, reported. A generated script is measured against the
                middle's seconds and cut to fit before it is stored, so a plan
                arrives renderable rather than needing a repair. When that
                happened the founder is told, with the size of the cut: their
                script is shorter than the model wrote it, and silence about
                that reads as the studio losing words. */}
            {project?.plan_trim?.dropped_chars > 0 && (
              <div className="rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] p-5" data-testid="plan-trimmed-note">
                <p className="text-sm">
                  I shortened your script by {project.plan_trim.dropped_chars} characters so it
                  fits the {project.plan_trim.middle_seconds}-second middle
                  {project.plan_trim.budget
                    ? ` (${project.plan_trim.budget} characters is what that many seconds holds)`
                    : ""}
                  . Everything above is spoken exactly as written.
                </p>
              </div>
            )}
            <div className="space-y-2">
              <label className="text-sm font-semibold">Hook line</label>
              <p className="text-xs text-muted-foreground" data-subtitle="">The opening line spoken in your generated Hook + Story clip.</p>
              <Input
                value={editValue("hook_line", "")}
                onChange={(e) => setEdits({ ...edits, hook_line: e.target.value })}
              />
            </div>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Script</label>
              <p className="text-xs text-muted-foreground" data-subtitle="">The spoken story after the hook — demo and CTA stay yours.</p>
              <Textarea
                value={editValue("script", "")}
                onChange={(e) => setEdits({ ...edits, script: e.target.value })}
                className="min-h-[160px]"
              />
            </div>
            {/* What the middle can actually speak, and what it cannot. The middle's
                seconds hold a fixed number of characters; anything past that is
                dropped from the words reaching the video model, usually the
                payoff sentence. The kept line below is the server's own bound
                text rather than a second implementation of the rule, so what is
                named here is exactly what a render speaks.

                There is no trim control. A generated script is sized to fit
                before it is ever stored (the arrival clamp), so the founder is
                never handed a broken plan to repair by hand — and if they write
                their own over-length words, regenerating the plan is the fix,
                not a second button beside their own editor. */}
            {/* Both spoken lines counted, against the length each one aims at.
                The hook line used to be the one count nothing showed: the middle
                had a budget and the opening line had none, so an over-long hook
                was stored, sent and cut mid-sentence with nothing on screen
                saying so. The numbers here are the server's own
                (spoken_check), measured on the saved plan — which is the plan a
                render validates — rather than a second arithmetic in the
                browser that could disagree with what the render does. */}
            {project?.spoken_check && (
              <div className="inset-panel space-y-2" data-testid="spoken-counts">
                <GroupLabel icon={Ruler}>How the two lines measure up</GroupLabel>
                {[
                  { key: "hook", label: "Hook line" },
                  { key: "script", label: "Script" },
                ].map(({ key, label }) => {
                  const line = project.spoken_check[key] || {};
                  const chars = Number(line.chars) || 0;
                  const target = Number(line.target) || 0;
                  const ceiling = Number(line.ceiling) || 0;
                  const overCeiling = line.verdict === "over_ceiling";
                  return (
                    <p key={key} className="text-xs text-muted-foreground">
                      <span className="font-semibold">{label}: </span>
                      {chars} characters{target ? `, aiming for about ${target}` : ""}
                      {overCeiling
                        ? ` — past the ${ceiling} characters these seconds can speak, so it is cut back before the render.`
                        : chars > target
                          ? " — longer than the target, which is a choice, not a fault."
                          : "."}
                    </p>
                  );
                })}
                <p className="text-xs text-muted-foreground">
                  {project.spoken_check.story?.coherent
                    ? "The hook names the problem and the script closes it."
                    : "The two lines should read as one thought: the hook naming the problem this viewer has, the script answering it."}
                </p>
              </div>
            )}
            {project?.strategy?.hook_line && typeof project?.spoken_middle === "string" && project.spoken_middle && (
              <div className="inset-panel space-y-2" data-testid="spoken-partition">
                <GroupLabel icon={FileText}>What the middle will say</GroupLabel>
                <p className="text-sm">{sentenceCase(project.spoken_middle)}</p>
                {/* What is not spoken is counted by the server, not sliced out
                    of the script here. The kept words are no longer always a
                    prefix of the script — an over-long middle gives up the
                    sentences in the MIDDLE of itself and keeps the one that
                    resolves the hook — so a browser slice would name words that
                    are in fact spoken and miss the ones that are not. */}
                {(Number(project?.spoken_overflow?.dropped_chars) || 0) > 0 ? (
                  <p className="text-xs text-muted-foreground">
                    {project.spoken_overflow.dropped_chars} characters of the script are past the
                    middle&apos;s spoken budget and are not spoken. Regenerate the plan to have it
                    rewritten to fit, or shorten the script above and rebuild the strategy.
                  </p>
                ) : (
                  <p className="text-xs text-muted-foreground" data-subtitle="">
                    Your whole script fits the middle — every word is spoken.
                  </p>
                )}
              </div>
            )}
            {/* `cta` and `feature_emphasis` used to sit here as two editable
                fields. Neither is writable any more and neither is returned, so
                leaving the inputs would have looked like editing something and
                silently thrown it away — the exact class of write that let
                `extend_intent` appear to be toggled while the server ignored it.
                A call to action is the founder's own, added in their editor after
                the demo they record, and an editable feature instruction is a
                product demo being planned, which is footage this product does not
                generate. `demo_brief` replaced the second: the plan works out what
                the founder should record, and it is deliberately never passed to
                the render, so correcting it here cannot smuggle a feature
                instruction back into the video. */}
            <div className="inset-panel space-y-2">
              <label htmlFor="review-demo-brief" className="text-sm font-semibold">
                What you record for the demo
              </label>
              <Textarea
                id="review-demo-brief"
                value={editValue("demo_brief", "")}
                onChange={(e) => setEdits({ ...edits, demo_brief: e.target.value })}
                className="min-h-[70px]"
                placeholder="For example: Record yourself tapping the timer once, hands only"
              />
              <p className="text-xs text-muted-foreground" data-subtitle="">
                A note to you, not the model — never reaches the render.
              </p>
            </div>
            <GroupLabel icon={AudioLines}>Visual &amp; audio direction</GroupLabel>
            <div className="space-y-2">
              <label className="text-sm font-semibold">Visual direction</label>
              <p className="text-xs text-muted-foreground" data-subtitle="">Guidance for the generated clip, not footage of your demo.</p>
              <Textarea
                value={editValue("visual_direction", "")}
                onChange={(e) => setEdits({ ...edits, visual_direction: e.target.value })}
                className="min-h-[90px]"
              />
            </div>

            {/* Read-only, and labelled as such, because it sits among seven
                editable fields in the same visual style and founders will
                otherwise try to type in it. It is also the one block that goes
                STALE the moment the script above is edited — the beats describe
                the plan as generated — so the edits warning is repeated here
                where the damage is visible. */}
            {editValue("beat_timeline", []).length > 0 && (
              <details
                className="inset-panel"
                data-testid="shot-timeline"
              >
                <summary className="flex cursor-pointer flex-wrap items-center gap-2">
                  <GroupLabel icon={ListChecks}>Shot timeline</GroupLabel>
                  <Badge variant="outline" className="text-xs">read-only</Badge>
                </summary>
                <div className="mt-2 space-y-2 text-sm">
                  {editValue("beat_timeline", []).map((b, i) => (
                    <div key={i} className="flex gap-2">
                      <Badge variant="secondary" className="shrink-0 text-xs">
                        {b.start}&ndash;{b.end}s
                      </Badge>
                      <span className="text-muted-foreground">{b.label}: {sentenceCase(b.text)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {hasEdits
                    ? "This still describes the plan as generated. Edit the script above and regenerate to bring it back in line."
                    : "Written by the plan to fit this length. Regenerate the plan to rewrite it."}
                </p>
              </details>
            )}

            {/* Length is shown, not edited, and it is not a founder choice at
                all. The template declares it, the project seeds from it, and the
                shot timeline above is written to it. The server refuses a
                duration change once a plan exists precisely because the beats
                were clamped to that number, so the only way to a different
                length is a different template and a regenerated plan. */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <span className="text-sm font-semibold">Length of the generated piece</span>
                <p className="rounded-lg border border-[color:var(--hairline)] px-3 py-2 text-sm">
                  {pieceSeconds} seconds
                </p>
                <p className="text-xs text-muted-foreground">
                  {project?.script_version
                    ? "The timeline is written to this length. Pick a different template to change it."
                    : "Set by the hook template you pick."}
                </p>
              </div>
              <div className="space-y-2">
                <label htmlFor="review-tone" className="text-sm font-semibold">Tone</label>
                <Input
                  id="review-tone"
                  value={editValue("tone", "")}
                  onChange={(e) => editTone(e.target.value)}
                  placeholder="For example: calm and direct"
                />
              </div>
            </div>

            <div className="space-y-2">
              <label className="text-sm font-semibold">Voice direction</label>
              <Textarea
                value={editValue("voice_direction", "")}
                onChange={(e) => setEdits({ ...edits, voice_direction: e.target.value })}
                className="min-h-[70px]"
              />
            </div>

            <GroupLabel icon={ShieldCheck}>Checks</GroupLabel>
            <SafetyPanel
              report={project.safety_report}
              summary={project.safety_summary}
            />

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="brand" onClick={handleSaveEdits} disabled={busy || !hasEdits}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save edits
              </Button>
              {/* No "Mark ready" button. Approval is not a decision the founder
                  makes by hand here: the plan handler marks the project ready
                  as part of generating, because it has just written the words
                  the founder is about to read. A second button said the same
                  thing twice, and a click that could only ever confirm what the
                  studio already knew was a control with no meaning.

                  Saving an edit re-marks, for the same reason: the founder
                  reviewed the exact text they saved, so the approval still
                  describes it. If the server refuses (a prohibited claim, a
                  missing photograph), the render button below states that real
                  reason instead of sitting disabled behind this control. */}
              {project?.status === "ready_for_generation" && (
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Ready for generation.
                </p>
              )}
            </div>
            {hasEdits && (
              <p className="text-xs text-muted-foreground" data-subtitle="">
                Save your edits before rendering. Edits are claim-checked.
              </p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />

            {/* Nothing that calls the model renders on this step. GenerationPanel
                lives on the step below, so the claim check above has been read
                before any render runs. */}
          </div>
        )}
        </StepShell>
      );
    }

    // Unreachable: every index in STEPS has a branch above. This is a guard
    // against an index out of range rendering an empty page, so it must not
    // read as a step the founder could have ended up in deliberately.
    return null;
  }

  if (loading) {
    return (
      <PageFrame className="space-y-6">
        <div className="flex items-center gap-2">
          {STEPS.map((s) => (
            <Skeleton key={s.key} className="h-7 w-24 shrink-0 rounded-full" />
          ))}
        </div>
        <div className="surface rounded-2xl">
          <div className="w-full space-y-4" aria-label="Loading studio" data-testid="studio-loading">
            <div className="flex items-start gap-3">
              <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
            <Skeleton className="h-24 rounded-2xl" />
            <Skeleton className="h-24 rounded-2xl" />
          </div>
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Clapperboard}
        title="Create Video"
        description="Pick an approved app and goal, then review the script plan."
      />

      {/* Progress that tracks state rather than position.
          The tick used to mean "this step is to the left of the one you are on",
          which is not the same thing at all: jump straight to the last step and
          all five showed a tick while nothing had been done. A founder reading
          that has been told they finished the workflow before they started it.

          Each step now declares what makes it satisfied, and the tick means that.
          Ticks are the only color story here: done steps tick, everything else
          shows the same hollow ring. A step that is waiting on the founder
          used to amber its icon, but the amber read as an error and clashed
          with the rest of the row — and the distinction never needed color,
          because the sentence underneath already names what is waiting and the
          pills already announce it. */}
      <nav aria-label="Progress" className="flex flex-wrap items-center gap-1.5">
        {stepStates.map((s, i) => {
          const active = i === step;
          const Icon = s.state === "done" ? Check : s.step.icon;
          // Resolved once per pill: the tick, the label, and the suffix below
          // must all agree on the same pick.
          const value = s.state === "done" ? pillValue(s.step.key) : null;
          return (
            <button
              key={s.step.key}
              type="button"
              onClick={() => setStep(i)}
              aria-current={active ? "step" : undefined}
              // Announced rather than shown only: the tick is a shape-only cue, and
              // this is the one place the founder looks to answer "what is left".
              aria-label={value
                ? `${s.step.label}: ${value}, done`
                : `${s.step.label}: ${STEP_STATE_COPY[s.state]}`}
              title={STEP_STATE_COPY[s.state]}
              data-state={s.state}
              data-testid={`step-pill-${s.step.key}`}
              className={`pill-studio inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold ${
                active
                  ? "border-[color:var(--indigo-35)] bg-primary/15 text-[color:var(--brand-indigo)] shadow-[0_0_10px_var(--brand-indigo)]"
                  : s.state === "done"
                    ? "border-[color:var(--hairline)] text-foreground/80 hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)] hover:text-foreground"
                    : "border-dashed border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)] hover:text-foreground"
              }`}
            >
              {s.state === "todo" || s.state === "blocked" ? (
                // A hollow ring for anything not done — "not started" and
                // "needs something from you" share it. The difference between
                // the two lives in the sentence underneath and in the announced
                // label, not in color: an amber icon read as an error state.
                <span
                  aria-hidden="true"
                  className="h-3 w-3 rounded-full border border-current opacity-60"
                />
              ) : (
                <Icon className="h-3 w-3" />
              )}
              {s.step.label}
              {value && (
                // The pick beside the tick, truncated: an angle label can be
                // a sentence, and the row wraps rather than scrolling. The
                // full text lives in the title and the aria-label above.
                <span
                  aria-hidden="true"
                  title={value}
                  className="max-w-40 truncate font-normal opacity-70"
                >
                  : {value}
                </span>
              )}
            </button>
          );
        })}
      </nav>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

<div className="surface rounded-2xl">
          {/* The step card is the ONLY card on a step. Its blocks — the angle
              picker, "What you get", and the goal list — were
              `.surface` too, so a card sat inside an identical card: same fill,
              same border, same 24px gutter, 48px of inset before any text and a
              third 24px inside. They are `.inset-panel` asides now (12px
              radius, 16px gutter), which is the level SectionCard's own header
              comment reserves for "a small bordered aside inside a card".

              Full width: the card's own surface padding is the gutter, so the
              step gets the whole frame like the rest of this editor page and
              no second width value is introduced here. */}
          <div className="w-full">{stepContent}</div>
        </div>

      {/* Sequential arrows beside free-jump pills. Back and Next lived here
          before and were removed as pure duplication — but they duplicated
          the jump, while these walk: the arrows move one phase at a time for
          a founder going through in order, the pills land a returning founder
          directly. Different jobs, so both stay. No guards, like the pills:
          these only move. */}
      <div className="flex items-center justify-between gap-2">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => setStep(Math.max(0, step - 1))}
          disabled={step === 0}
          aria-label={step === 0 ? "Back (already on the first step)" : `Back to ${STEPS[step - 1].label}`}
          data-testid="wizard-back-button"
          className="gap-1.5"
        >
          <ChevronLeft className="h-3.5 w-3.5" /> Back
        </Button>
        {step < STEPS.length - 1 && (
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setStep(step + 1)}
            aria-label={`Continue to ${STEPS[step + 1].label}`}
            data-testid="wizard-continue-button"
            className="gap-1.5"
          >
            Continue <ChevronRight className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>

      {/* The one thing the pills cannot do is leave the studio, so the exit
          stays — on the last step only, which is where it already was. */}
      {step === STEPS.length - 1 && project && (
        <div className="flex items-center justify-end">
          <Button variant="ghost" onClick={() => navigate("/app-profiles")}>
            Back to your app
          </Button>
        </div>
      )}
    </PageFrame>
  );
}
