import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage } from "../lib/api";
import { plannedSections } from "../lib/videoLength";
import {
  Loader2, AlertTriangle, Info, MapPin, ShieldQuestion, Sparkles,
} from "lucide-react";

/**
 * The strategy review: what the render will be, before anything is paid for.
 *
 * This used to be the whole influencer workflow — strategy, hook, approve,
 * extend, join — and the extend/approve/assemble machinery had a referent
 * because the workflow had one. It does not any more. A video is one render
 * containing a hook and a middle, there is no product demo and no call to
 * action in the generated footage, and the founder assembles the final video
 * themselves: hook, middle, their own demo, their own close. So every control
 * that assumed a chain went with it, and what is left is the part that was
 * always worth keeping — the strategy is what the founder is about to spend on,
 * and reading it should not require pressing a button first.
 *
 * The file name is historical. There is no continuity to review: with one
 * render there is no seam between two separately-generated pieces for a
 * continuity contract to govern, and the scene is locked across both sections
 * by a single prompt rather than by a chain of anchored clips.
 */

/**
 * Turn a machine key into something readable.
 *
 * The strategy comes back from the model with snake_case keys, and they were
 * being printed verbatim: "color_palette", "visual_style", "character_positioning".
 * That reads as a debug dump rather than a plan the founder is meant to act on.
 *
 * Only the surviving keys are listed. This map used to carry the deleted
 * "character" block's keys too (age_range, hair_style, body_appearance,
 * facial_features, facial_expression, styling_details) — the model still cannot
 * emit them, so those entries could never match anything again.
 *
 * `ACRONYMS` covers the cases where a plain title-case is wrong. It has no CTA
 * entry: `cta_strategy` was the only strategy key that used the acronym, and it
 * described a closing beat this product does not generate.
 */
const STRATEGY_LABELS = {
  camera_angle: "Camera angle",
  visual_style: "Visual style",
  color_palette: "Colour palette",
  voice_delivery: "Voice delivery",
  character_positioning: "Position in frame",
};

const ACRONYMS = {
  ai: "AI",
  api: "API",
  fps: "FPS",
  hd: "HD",
  us: "US",
  uk: "UK",
  url: "URL",
  vlog: "Vlog",
};

function strategyLabel(key) {
  if (STRATEGY_LABELS[key]) return STRATEGY_LABELS[key];
  return String(key)
    .split("_")
    .filter(Boolean)
    .map((word) => ACRONYMS[word.toLowerCase()] || word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/**
 * A titled group of label/value rows.
 *
 * The label sits on its own line above the value rather than beside it. Side by
 * side, `shrink-0` on the label plus a long value forced the value column to
 * wrap into a ragged narrow strip, which is what made this block hard to scan.
 * Stacked, every value gets the full column width regardless of key length.
 */
function StrategyBlock({ title, icon: Icon, rows, description }) {
  const filled = rows.filter(([, value]) => String(value || "").trim());
  if (!filled.length) return null;
  return (
    <div className="space-y-2">
      <div className="space-y-0.5">
        <span className="eyebrow flex items-center gap-1.5">
          <Icon className="h-3 w-3" /> {title}
        </span>
        {description && (
          <p className="text-xs text-muted-foreground">{description}</p>
        )}
      </div>
      <dl className="space-y-2">
        {filled.map(([label, value]) => (
          <div key={label}>
            <dt className="text-xs font-medium text-muted-foreground">
              {strategyLabel(label)}
            </dt>
            <dd className="mt-0.5 text-sm leading-snug">{String(value)}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const SECTION_COPY = {
  hook: "The first 2 to 4 seconds. Its whole job is to stop the scroll.",
  middle:
    "Everything after the hook. It develops the point and ends at the moment you'd reach for your phone — which is where your own demo takes over.",
};

/**
 * One of the two generated sections, described as what it is.
 *
 * Not a numbered beat in a chain, and not something to be extended. The list is
 * always exactly two rows, in render order, because that is what the model was
 * asked for and what the render will produce.
 */
function SectionRow({ section }) {
  const goal = section.goal;
  return (
    <li className="space-y-1">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium capitalize">{section.role}</span>
        <Badge variant="outline" className="text-[11px]">{section.seconds}s</Badge>
      </div>
      <p className="text-xs text-muted-foreground">{SECTION_COPY[section.role]}</p>
      {goal && <p className="text-sm">{goal}</p>}
      {section.action && (
        <p className="text-sm text-muted-foreground">What they do: {section.action}</p>
      )}
    </li>
  );
}

export function HookContinuityPanel({ project, onProjectChange }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);

  const projectId = project?.id;
  const strategy = project?.strategy;
  const hasStrategy = Boolean(strategy?.hook_line);
  const assets = project?.assets || [];
  const hasCharacter = assets.some((a) => a.kind === "character_reference");
  const blocked = project?.safety_report && project.safety_report.passed === false;
  // The strategy is built from one specific version of the plan. Edit the plan
  // afterwards and the strategy is describing a video that is no longer the
  // approved one, so this reads the flag the server already computes rather
  // than leaving the founder to spend a click and meet a raw error body. Only
  // meaningful once a strategy exists; `_public_project` returns true when
  // either version is 0, which is missing history, not drift.
  const staleStrategy = Boolean(strategy) && project?.strategy_is_current === false;

  const handleGenerateStrategy = async () => {
    // Confirm only when the plan has moved on. A rebuild then means something
    // specific — it discards a strategy built against an older plan, and
    // nothing else on screen says that is what the button does. An ordinary
    // rebuild of a strategy that is already current is harmless and stays one
    // click; interrupting that every time would just teach the founder to
    // dismiss the prompt without reading it.
    if (hasStrategy && staleStrategy) {
      const ok = typeof window === "undefined" || typeof window.confirm !== "function"
        ? true
        : window.confirm(
            `Rebuild from plan v${project?.script_version}? This replaces the strategy built ` +
            `from plan v${project?.strategy_script_version}, and the render will follow the ` +
            `newer one.`
          );
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      // No length is sent: the template declares one and the project already
      // carries it. Sending our own number would let a stale saved value
      // override the template the founder actually picked.
      const updated = await api.generateStrategy(projectId, {});
      onProjectChange?.(updated);
      setNotice(
        `Strategy v${updated.strategy_version} built from this app's profile. Read it and the ` +
        `locked scene below, then render the piece.`
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // Build the strategy automatically once the project is ready and none
  // exists. Without this the Generate button below stays disabled behind a
  // "Build the strategy above" note the founder can jump past via the step
  // pills, which is the other half of "the button sometimes is not clickable".
  // Only fires when there is NO strategy at all -- a stale one still asks,
  // because rebuilding discards a strategy the founder may have read and the
  // confirm dialog is the right guard for that. One attempt per mount: the ref
  // stops a re-render storm from re-triggering a free text call.
  const autoBuildAttempted = useRef(false);
  useEffect(() => {
    if (
      autoBuildAttempted.current ||
      project?.status !== "ready_for_generation" ||
      hasStrategy ||
      !projectId ||
      busy
    ) {
      return;
    }
    autoBuildAttempted.current = true;
    // Fire and forget: errors land in the panel's own error state through
    // handleGenerateStrategy, and the Generate button stays disabled for the
    // real reason (no strategy) rather than silently proceeding.
    handleGenerateStrategy();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleGenerateStrategy is a render-scoped closure; listing it would re-fire the free call on every render.
  }, [project?.status, hasStrategy, projectId, busy]);

  const sections = plannedSections(strategy);

  return (
    <div className="space-y-3 rounded-2xl border border-[color:var(--hairline)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-display text-sm font-semibold">
          <Sparkles className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          The strategy behind the piece
        </span>
        {strategy && (
          <Badge variant="outline" className="text-[11px]">strategy v{project.strategy_version}</Badge>
        )}
      </div>

      <p className="text-xs text-muted-foreground">
        This is what the render follows: a hook, then a middle that develops it and stops at the
        moment you'd reach for your phone. Everything after that is yours to record and add — the
        demo is your own footage and the close is your own words.
      </p>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {staleStrategy && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Plan edited since this strategy was built</AlertTitle>
          <AlertDescription>
            This strategy was built from plan v{project?.strategy_script_version}, and the plan is
            now v{project?.script_version}. Generating is blocked until you rebuild, because the
            render would otherwise follow the words and directions you approved on the older plan.
          </AlertDescription>
        </Alert>
      )}

      {!hasCharacter && (
        <Alert>
          <ShieldQuestion className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>No character reference attached</AlertTitle>
          <AlertDescription>
            Attach a <code>character_reference</code> image on the Template &amp; photo step, or the
            presenter will be invented by the model rather than being you.
          </AlertDescription>
        </Alert>
      )}
      {blocked && (() => {
        // Name the claim at the block site: the full list lives in the
        // review step's SafetyPanel, but the founder is stopped HERE, so
        // "fix the flagged claim" without naming it strands them.
        const blockers = (project?.safety_report?.blocking || []).filter(
          (b) => b && b.claim
        );
        return (
        <Alert variant="destructive">
          <AlertTitle>Prohibited claim present</AlertTitle>
          <AlertDescription>
            {blockers.length > 0 && (
              <>Found in this plan: {blockers.slice(0, 2).map((b) => `“${b.claim}”`).join(", ")}
              {blockers.length > 2 ? `, plus ${blockers.length - 2} more` : ""}. </>
            )}
            Fix the flagged claim in the plan above. Rendering is blocked until the claim check
            passes.
          </AlertDescription>
        </Alert>
        );
      })()}

      <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
        <Button
          variant="brand"
          onClick={handleGenerateStrategy}
          disabled={busy || !projectId}
        >
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {hasStrategy ? "Rebuild strategy" : "Build the app-specific strategy"}
        </Button>
        {!hasStrategy && (
          <p className="text-xs text-muted-foreground">
            Text only, and free. It fixes the concept, the words and the locked scene so the one
            paid render is about this app rather than a generic take with a name in it.
          </p>
        )}
      </div>

      {!hasStrategy && (
        /* The empty state. Everything above this point used to render nothing
           until a strategy existed, so the panel was a paragraph and a button
           with no indication of what either produced — which is why it read as
           a useless control. These are the two sections and the locked scene,
           named up front. The content is not knowable before the call, but the
           SHAPE of what comes back is, and that is what was missing. */
        <div className="space-y-3 rounded-xl border border-dashed border-[color:var(--hairline)] p-3">
          <div className="space-y-1">
            <span className="eyebrow">What you get</span>
            <ol className="space-y-2 text-sm">
              {["hook", "middle"].map((role) => (
                <li key={role} className="space-y-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-medium capitalize">{role}</span>
                    <span className="text-xs text-muted-foreground">{SECTION_COPY[role]}</span>
                  </span>
                  <p className="text-xs text-muted-foreground">
                    {role === "hook"
                      ? "The opening concept and the words, from the plan you approved."
                      : "What the presenter does next, ending where you would reach for your phone."}
                  </p>
                </li>
              ))}
            </ol>
          </div>
          <div className="space-y-1">
            <span className="eyebrow">The scene</span>
            <p className="text-xs text-muted-foreground">
              One locked room and delivery for both sections, taken from the plan's visual and voice
              direction, so the hook and the middle cannot disagree about where they are.
            </p>
          </div>
          <p className="text-xs text-muted-foreground">
            Built automatically when you generate, and shown here before then if you would rather
            read it first. Text only and free either way.
          </p>
        </div>
      )}

      {hasStrategy && (
        <div className="space-y-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
          <div className="space-y-1">
            <span className="eyebrow">Hook concept</span>
            <p className="text-sm">{strategy.hook_concept}</p>
            {/* The hook line itself is NOT printed here. It is the same string as
                the Review step's "Hook line", verbatim, because the strategy
                prompt is told to echo the founder-approved line rather than write
                a new one (ai_service.py, the approved-plan rules). Printing it a
                second time read as though the two could differ, which is the one
                thing they cannot. `strategy.hook_line` still exists on the
                strategy and still reaches the render prompt — this is the
                duplicate display that was removed, not the field. */}
            <p className="text-xs text-muted-foreground">
              What is said is the hook line you approved on the Review step, spoken as written.
            </p>
          </div>
          <div className="space-y-1">
            <span className="eyebrow">Why this works for this app</span>
            <p className="text-sm">{strategy.strategy_summary}</p>
          </div>
          {/* There is no "person" block, and deliberately so. It used to sit
              here listing the model's guess at the founder's face, hair, age and
              wardrobe, under a heading that called it locked for every segment —
              while the actual photograph sat in the project's assets. It read as
              a description of the person they uploaded, and it was invented. The
              on-camera person is copied from the character reference image and
              nothing is written about them.

              Scene and performance are ONE block, not two. They were separate
              headings over four values, and the divider implied a boundary that
              does not exist: `movement` and `voice_delivery` are locked by
              exactly the same mechanism as camera angle and lighting, so
              splitting them made the founder hunt for half the lock in a second
              box. Rows are ordered scene-then-performance, which is the order
              STRATEGY_SCENE_FIELDS and STRATEGY_PERFORMANCE_FIELDS declare.

              The description credits the plan, because these twelve slots are the
              plan's "Visual direction" and "Voice direction" decomposed for the
              render. Nothing in the prompt obliges the model to transcribe that
              paragraph into these fields, so the two can drift — saying so is
              what tells the founder where to fix a disagreement. */}
          <StrategyBlock
            title="The scene"
            description="Locked for both sections, and one render, so the hook and the middle cannot disagree about the room. Built from the plan's visual and voice direction, which you edit on the Review step."
            icon={MapPin}
            rows={[
              ...Object.entries(strategy.scene || {}),
              ...Object.entries(strategy.performance || {}),
            ]}
          />
          {/* Exactly two rows, in render order. The old "Segments planned" list
              collapsed runs of continuation beats into ranges and closed by
              saying the hook and the call to action were the two that carried the
              video — a description of a chain with a fixed number of beats to
              spend, none of which exists now. */}
          <div className="space-y-1.5">
            <span className="eyebrow">The two sections</span>
            <ol className="space-y-3 text-sm">
              {sections.map((section) => (
                <SectionRow key={section.role} section={section} />
              ))}
            </ol>
            <p className="text-xs text-muted-foreground">
              That is the whole generated piece, in one render. There is no product demo in it and
              no closing card: attach your own demo after the middle, add your close after that, and
              post the result yourself.
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default HookContinuityPanel;
