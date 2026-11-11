import { useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage } from "../lib/api";
import { BUSY_ETA_SECONDS } from "../lib/busyEta";
import { plannedSections } from "../lib/videoLength";
import { sentenceCase } from "../lib/copyCase";
import {
  AlertTriangle, Info, MapPin, ShieldQuestion, Sparkles, Target,
} from "lucide-react";
import { Disclosure } from "./Disclosure";
import { GroupLabel } from "./SectionCard";

/**
 * The strategy review: what the render will be, before anything is rendered.
 *
 * This used to be the whole influencer workflow — strategy, hook, approve,
 * extend, join — and the extend/approve/assemble machinery had a referent
 * because the workflow had one. It does not any more. A video is one render
 * containing a hook and a middle, there is no product demo and no call to
 * action in the generated footage, and the founder assembles the final video
 * themselves: hook, middle, their own demo, their own close. So every control
 * that assumed a chain went with it, and what is left is the part that was
 * always worth keeping — the strategy is what the render is built from,
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
  // A label containing a space is display copy, not a machine key. The outcome
  // rows pass their own wording ("How it works, as a benefit") because
  // title-casing one of those gives "How It Works, As A Benefit" — the
  // snake_case transform exists to rescue model keys, and those are gone by
  // this point in the file.
  if (String(key).includes(" ")) return String(key);
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
 *
 * Tokens still match the shared spec-sheet language: the label is the shared
 * `.eyebrow` and the value the shared body, the same pair the angle details,
 * Post copy and History context use. Only the grid differs — strategy keys
 * are long, so these rows stay stacked while short-labelled rows go two
 * columns — never the label or body itself.
 */
function StrategyBlock({ title, icon: Icon, rows, description, hideTitle = false }) {
  const filled = rows.filter(([, value]) => String(value || "").trim());
  if (!filled.length) return null;
  return (
    <div className={hideTitle ? "space-y-2" : "space-y-4 border-t border-[color:var(--hairline-strong)] pt-5"}>
      {hideTitle ? (
        description && (
          <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
        )
      ) : (
        <div className="space-y-2">
          <GroupLabel icon={Icon}>{title}</GroupLabel>
          {description && (
            <p className="max-w-3xl text-sm leading-relaxed text-muted-foreground">{description}</p>
          )}
        </div>
      )}
      <dl className="max-w-3xl divide-y divide-[color:var(--hairline)]">
        {filled.map(([label, value]) => (
          <div key={label} className="py-3 first:pt-0 last:pb-0" data-testid={`strategy-${String(label).replaceAll("_", "-")}`}>
            <dt className="eyebrow">
              {strategyLabel(label)}
            </dt>
            <dd className="mt-1 text-base leading-relaxed text-foreground/90 [overflow-wrap:anywhere]">{sentenceCase(String(value))}</dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

/**
 * One line of what a collapsed group holds, so the founder can decide whether
 * to open it. Sentence-cased like every other strategy value, cut at a word
 * boundary rather than mid-thought.
 *
 * No lookbehind (`/(?<=[.!?])\s/`): lookbehind throws on Safari < 16.4, and the
 * digest is read on every collapsed group. The first sentence is found by
 * scanning for a punctuation mark followed by a space, which reads the same on
 * every engine.
 */
function summaryLine(text, limit = 108) {
  const full = String(text || "").trim().split(/\s+/).join(" ");
  if (!full) return "";
  const firstSentenceIndex = full.search(/[.!?] /);
  const firstSentence = firstSentenceIndex >= 0
    ? full.slice(0, firstSentenceIndex + 1)
    : full;
  const clipped = firstSentence.length > limit
    ? firstSentence.slice(0, limit + 1).replace(/\s+\S*$/, "") + "…"
    : firstSentence;
  return sentenceCase(clipped);
}

/**
 * A collapsed strategy group: a title, a one-line digest of its contents, and
 * the full text behind one click. The panels people ACT on (the two sections,
 * the Location editor, the rating and the render controls) stay open; the
 * explanations do not have to be read to use the page.
 */
function CollapsedGroup({ testId, title, digest, children }) {
  return (
    <Disclosure
      testId={testId}
      detailsClassName="group inset-panel space-y-3"
      summaryClassName="flex w-full cursor-pointer list-none flex-wrap items-start justify-between gap-2 py-1 [&::-webkit-details-marker]:hidden"
      summary={
        <span className="flex min-w-0 flex-col gap-1 text-left">
          <GroupLabel>{title}</GroupLabel>
          {digest && (
            <span className="text-sm font-normal leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
              {digest}
            </span>
          )}
        </span>
      }
    >
      <div className="space-y-3 border-t border-[color:var(--hairline)] pt-3">
        {children}
      </div>
    </Disclosure>
  );
}

const SECTION_COPY = {
  hook: "The first 2 to 4 seconds. Its whole job is to stop the scroll.",
  middle:
    "Everything after the hook. It develops the point and ends at the moment you'd reach for your phone — which is where your own demo takes over.",
};

// A handheld selfie cannot film a reach for the phone: the camera IS the
// phone in their hand. The middle ends on the words instead, and the last
// second is one short physical beat. The copy says which one it is, so the
// founder is never told to expect a handoff the render will not contain.
const SELFIE_MIDDLE_COPY =
  "Everything after the hook. It develops the point and ends on the payoff words — one short physical beat closes it, never a reach for your phone — which is where your own demo takes over.";

function sectionCopy(role, cameraSetup) {
  if (role !== "middle") return SECTION_COPY[role];
  return cameraSetup === "fixed" ? SECTION_COPY.middle : SELFIE_MIDDLE_COPY;
}

/**
 * One of the two generated sections, described as what it is.
 *
 * Not a numbered beat in a chain, and not something to be extended. The list is
 * always exactly two rows, in render order, because that is what the model was
 * asked for and what the render will produce.
 */
function SectionRow({ section, cameraSetup }) {
  // Model-written, so normalized at display like every other generated field.
  const goal = sentenceCase(section.goal);
  return (
    <li className="max-w-3xl space-y-3 border-l-2 border-[color:var(--indigo-35)] pl-4">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-display text-base font-semibold capitalize">{section.role}</span>
        <Badge variant="outline" className="text-xs">{section.seconds}s</Badge>
      </div>
      <p className="text-sm leading-relaxed text-muted-foreground">{sectionCopy(section.role, cameraSetup)}</p>
      {goal && <p className="text-base leading-relaxed [overflow-wrap:anywhere]">{goal}</p>}
      {section.action && (
        <p className="text-base leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">What they do: {sentenceCase(section.action)}</p>
      )}
      {/* The words the viewer hears, which is the entire point of this panel
          and was missing from it. These are the founder's approved words: the
          strategy is built to deliver the plan, so after a rebuild the hook
          line and the two section scripts come from it verbatim. Before a
          rebuild — a strategy built before the binding existed — they are the
          model's drafts, which is why this line stays even when the words
          read like a draft: it is what will be sent, not what was approved. */}
      {typeof section.script === "string" && section.script.trim() && (
        <p className="text-base leading-relaxed [overflow-wrap:anywhere]" data-testid={`section-spoken-${section.role}`}>
          <span className="font-semibold">What is said here: </span>
          {sentenceCase(section.script.trim())}
        </p>
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
  // Same render gate as the Generate button's: words that cannot be spoken in
  // the piece's seconds refuse the render, recomputed from the live plan. The
  // founder is stopped here too, so the block has to name the Review-step fix
  // rather than only appearing as a strategy-panel warning below.
  const overflowBlocked = (project?.spoken_overflow?.dropped_chars || 0) > 0;
  // The strategy is built from one specific version of the plan. Edit the plan
  // afterwards and the strategy is describing a video that is no longer the
  // approved one, so this reads the flag the server already computes rather
  // than leaving the founder to spend a click and meet a raw error body. Only
  // meaningful once a strategy exists; `_public_project` returns true when
  // either version is 0, which is missing history, not drift.
  const staleStrategy = Boolean(strategy) && project?.strategy_is_current === false;
  // The strategy is built around one audience angle, and strategy_is_current
  // only tracks plan versions — so an angle change after the build would
  // otherwise leave a strategy describing the wrong video with no warning.
  const angleStale =
    hasStrategy &&
    (strategy?.content_angle_id || "") !== (project?.content_angle_id || "");
  const needsAngle = !project?.content_angle_id;

  const handleGenerateStrategy = async () => {
    // Confirm only when the plan has moved on or the angle has changed. A
    // rebuild then means something specific — it discards a strategy built
    // against an older plan or a different angle, and nothing else on screen
    // says that is what the button does. An ordinary rebuild of a strategy
    // that is already current is harmless and stays one click; interrupting
    // that every time would just teach the founder to dismiss the prompt
    // without reading it.
    if (hasStrategy && (staleStrategy || angleStale)) {
      const ok = typeof window === "undefined" || typeof window.confirm !== "function"
        ? true
        : window.confirm(
            angleStale && !staleStrategy
              ? `Rebuild for the newly picked audience angle? This replaces the strategy built ` +
                `for a different angle, and the render will follow the newer one.`
              : `Rebuild from plan v${project?.script_version}? This replaces the strategy built ` +
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
      busy ||
      needsAngle
    ) {
      return;
    }
    autoBuildAttempted.current = true;
    // Fire and forget: errors land in the panel's own error state through
    // handleGenerateStrategy, and the Generate button stays disabled for the
    // real reason (no strategy) rather than silently proceeding.
    handleGenerateStrategy();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleGenerateStrategy is a render-scoped closure; listing it would re-fire the free call on every render.
  }, [project?.status, hasStrategy, projectId, busy, needsAngle]);

  const sections = plannedSections(strategy);
  // The one-line digest of the collapsed scene group: place, camera setup and
  // what the person wears (or the light when the wardrobe is unset). The
  // Location editor itself stays open on the render panel below.
  const scene = strategy?.scene || {};
  const sceneRows = [
    ...Object.entries(scene),
    ...Object.entries(strategy?.performance || {}),
  ].filter(([, value]) => String(value || "").trim());
  const hasOutcome = [
    strategy?.desired_outcome, strategy?.mechanism_beat, strategy?.payoff_beat,
  ].some((value) => String(value || "").trim());
  const cameraLabel = project?.camera_setup === "fixed" ? "fixed camera" : "handheld selfie";
  // Which ending the render can actually film: a fixed camera can show the
  // phone handoff, a handheld selfie cannot (the camera is the phone in their
  // hand), so the copy follows the setup rather than promising one take.
  const cameraSetup = project?.camera_setup === "fixed" ? "fixed" : "handheld";
  const sceneDigest = [
    scene.location,
    cameraLabel,
    scene.wardrobe || scene.lighting,
  ]
    .filter((part) => String(part || "").trim())
    .map((part) => sentenceCase(String(part).trim()))
    .join(", ");

  return (
    <div className="inset-panel space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={Sparkles}>The strategy behind the piece</GroupLabel>
        {strategy && (
          <Badge variant="outline" className="text-xs">strategy v{project.strategy_version}</Badge>
        )}
      </div>

      {/* The demo-and-close caveat is not repeated here. It is stated before
          the render (the panel's "Before you render" summary), after it ("What
          you have, and what is left"), and once at the page level ("This
          studio creates the Hook + Story clip only..."), which is where the
          app's "nothing is published for you" note lives. A fourth copy in the
          strategy header said nothing the other three had not. */}
      <p className="text-sm text-muted-foreground">
        This strategy guides the Hook + Story render.
      </p>

      {error && (
        <Alert variant="destructive" data-testid="strategy-error">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert variant="warning" data-testid="strategy-notice">
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {staleStrategy && (
        <Alert variant="warning">
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Plan edited since this strategy was built</AlertTitle>
          <AlertDescription>
            This strategy was built from plan v{project?.strategy_script_version}, and the plan is
            now v{project?.script_version}. Rendering is blocked until you rebuild it to match your
            saved plan; otherwise the clip would follow the older version.
          </AlertDescription>
        </Alert>
      )}

      {!hasCharacter && (
        <Alert variant="warning">
          <ShieldQuestion className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>No character reference attached</AlertTitle>
          <AlertDescription>
            Attach a presenter photo on the Audience &amp; template step. Rendering is blocked until the photo is attached; the app will not invent a replacement.
          </AlertDescription>
        </Alert>
      )}
      {overflowBlocked && (
        <Alert variant="destructive">
          <AlertTitle>Script too long for this piece</AlertTitle>
          <AlertDescription>
            Trim the script above on Review &amp; submit — the middle&apos;s spoken words are shown
            there, with a button that keeps only what fits. Then rebuild the strategy
            here, because a trim is a plan edit. Rendering is blocked until every approved
            word fits in the piece&apos;s seconds.
          </AlertDescription>
        </Alert>
      )}

      {angleStale && (
        <Alert variant="warning">
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertTitle>Audience angle changed since this strategy was built</AlertTitle>
          <AlertDescription>
            This strategy was built around a different angle. Rendering is blocked until you rebuild
            it for the angle now picked; otherwise the clip would follow the older choice.
          </AlertDescription>
        </Alert>
      )}

      <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
        <Button
          variant="accent"
          onClick={handleGenerateStrategy}
          disabled={busy || !projectId || needsAngle}
          busy={busy}
          etaSeconds={BUSY_ETA_SECONDS.strategy}
          data-testid="strategy-build-button"
        >
          <Sparkles className="h-4 w-4" />
          {busy ? "Building strategy" : hasStrategy ? "Rebuild strategy" : "Build the app-specific strategy"}
        </Button>
        {!busy && needsAngle && (
          <p className="text-sm text-muted-foreground" data-testid="strategy-needs-angle">
            Pick an audience angle on the Audience &amp; template step first — the strategy is built around it.
          </p>
        )}
        {!busy && !hasStrategy && !needsAngle && (
          <p className="text-sm text-muted-foreground">
            Text only. It fixes the concept, the words and the locked scene so
            the one render is about this app rather than a generic take with a
            name in it.
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
            <GroupLabel>What you get</GroupLabel>
            <ol className="space-y-2 text-base">
              {["hook", "middle"].map((role) => (
                <li key={role} className="space-y-1">
                  <span className="flex flex-wrap items-center gap-2">
                    <span className="font-semibold capitalize">{role}</span>
                    <span className="text-sm text-muted-foreground">{sectionCopy(role, cameraSetup)}</span>
                  </span>
                  <p className="text-sm text-muted-foreground">
                    {role === "hook"
                      ? "The opening concept and the words, from the plan you approved."
                      : cameraSetup === "fixed"
                        ? "What the presenter does next, ending where you would reach for your phone."
                        : "What the presenter does next, ending on the payoff words and one short physical beat."}
                  </p>
                </li>
              ))}
            </ol>
          </div>
          <div className="space-y-1">
            <GroupLabel icon={MapPin}>The scene</GroupLabel>
          <p className="text-sm text-muted-foreground">
            One scene and delivery style for both the hook and story, guided by your Review choices. This is generated footage, not a recording of your app.
          </p>
          </div>
          <p className="text-sm text-muted-foreground">
            Built automatically once the saved plan is ready. If the build fails, use the button above to retry, then read the strategy before rendering. This step creates text, not video.
          </p>
        </div>
      )}

      {hasStrategy && (
        <div className="space-y-4 border-t border-[color:var(--hairline-strong)] pt-5">
          {/* The explanations are collapsed by default: they govern the render,
              but the founder acts on the Location editor, the two sections, the
              rating and the render controls below. Each closed group still
              shows one line of what it holds, so nothing is hidden without a
              clue. */}
          {String(strategy.hook_concept || "").trim() && (
            <CollapsedGroup
              testId="strategy-hook-concept"
              title="Hook concept"
              digest={summaryLine(strategy.hook_concept)}
            >
              <div className="max-w-3xl space-y-2 border-l-2 border-[color:var(--indigo-35)] pl-4">
                <p className="text-base leading-relaxed [overflow-wrap:anywhere]">{sentenceCase(strategy.hook_concept)}</p>
                {/* The hook line itself is NOT printed here. It is the same string as
                    the Review step's "Hook line", verbatim, because the strategy
                    prompt is told to echo the founder-approved line rather than write
                    a new one (ai_service.py, the approved-plan rules). Printing it a
                    second time read as though the two could differ, which is the one
                    thing they cannot. `strategy.hook_line` still exists on the
                    strategy and still reaches the render prompt — this is the
                    duplicate display that was removed, not the field. */}
                <p className="text-sm leading-relaxed text-muted-foreground">
                  What is said is the hook line you saved above, spoken as written.
                </p>
              </div>
            </CollapsedGroup>
          )}

          {String(strategy.strategy_summary || "").trim() && (
            <CollapsedGroup
              testId="strategy-why-it-works"
              title="Why this works for this app"
              digest={summaryLine(strategy.strategy_summary)}
            >
              <p className="max-w-3xl text-base leading-relaxed [overflow-wrap:anywhere]">{sentenceCase(strategy.strategy_summary)}</p>
            </CollapsedGroup>
          )}

          {/* The three outcome fields, shown because they already govern the
              whole render (generation_planning reads them into the segment
              prompt) and were invisible here. Framed as a change the app
              supports, never a result it promises — the same rule the template
              outcome line and the evidence note follow. The first row is the
              one-line digest of the closed group: the change it supports. */}
          {hasOutcome && (
            <CollapsedGroup
              testId="strategy-viewer-outcome"
              title="What the viewer ends up with"
              digest={summaryLine(strategy.desired_outcome || strategy.mechanism_beat || strategy.payoff_beat)}
            >
              <StrategyBlock
                title="What the viewer ends up with"
                description="How the viewer sees this app: the change, the benefit, and what they are left with — all from the viewer's point of view. The render is written from this framing — aim at it, never promise it as a result."
                icon={Target}
                hideTitle
                rows={[
                  ["The change this supports", strategy.desired_outcome],
                  ["How it works, as a benefit", strategy.mechanism_beat],
                  ["What the viewer is left with", strategy.payoff_beat],
                ]}
              />
            </CollapsedGroup>
          )}

          {/* Scene and performance are ONE group, not two: movement and voice
              delivery are locked by exactly the same mechanism as camera angle
              and lighting. The digest shows the place, the camera setup and the
              wardrobe/light — "Footbridge at dusk, handheld selfie, olive
              jacket" — so the group reads at a glance without opening. */}
          {sceneRows.length > 0 && (
            <CollapsedGroup
              testId="strategy-scene-details"
              title="Scene details"
              digest={sceneDigest}
            >
              <StrategyBlock
                title="The scene"
                description="One Location, one render: the hook and the middle can't disagree. Edit the Location in Render your Hook + Story below; lighting and wardrobe live on Review & submit."
                icon={MapPin}
                hideTitle
                rows={[
                  ...Object.entries(strategy.scene || {}),
                  ...Object.entries(strategy.performance || {}),
                ]}
              />
            </CollapsedGroup>
          )}

          {/* Exactly two rows, in render order. The old "Segments planned" list
              collapsed runs of continuation beats into ranges and closed by
              saying the hook and the call to action were the two that carried the
              video — a description of a chain with a fixed number of beats to
              segments, none of which exists now. */}
          <div className="space-y-4 border-t border-[color:var(--hairline-strong)] pt-5">
            <GroupLabel icon={Info}>The two sections</GroupLabel>
            <ol className="space-y-6 text-base">
              {sections.map((section) => (
                <SectionRow
                  key={section.role}
                  section={section}
                  cameraSetup={cameraSetup}
                />
              ))}
            </ol>
            {/* The "no demo, no closing card" restatement is gone: the list
                above already ends where the founder's demo takes over, and the
                panel below the render names the demo and the close as theirs. */}
            <p className="text-sm text-muted-foreground">
              That is the whole generated piece, in one render.
            </p>
            {/* Words that do not fit are not spoken. The middle's seconds hold a
                fixed number of characters, and anything past that is dropped
                from the prompt the model reads — usually the payoff sentence,
                which is the last thing the founder wrote. Blocking this in the
                render gate is what stops the spend; showing it here is what
                stops the surprise. The record is recomputed from the live plan
                on every read, so it cannot go stale. A generated plan is
                trimmed to fit on arrival, so this is your own edit above:
                shorten it on Review, or regenerate the plan, then rebuild the
                strategy here. */}
            {project?.spoken_overflow?.dropped_chars > 0 && (
              <Alert variant="warning" data-testid="spoken-overflow-warning">
                <AlertTriangle className="h-4 w-4" />
                <AlertTitle>Your script does not all fit in the middle</AlertTitle>
                <AlertDescription>
                  Your approved script has {project.spoken_overflow.dropped_chars} characters that
                  do not fit in the {project.spoken_overflow.middle_seconds}s middle (spoken budget:
                  {project.spoken_overflow.budget} characters). Anything past that is not spoken in
                  the render. Shorten it above, or press Regenerate plan — a
                  generated plan is trimmed to fit on arrival — then rebuild the strategy here. Or
                  pick a longer template and rebuild.
                </AlertDescription>
              </Alert>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export default HookContinuityPanel;
