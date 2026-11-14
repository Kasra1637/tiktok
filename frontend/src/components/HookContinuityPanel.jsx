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
 * What a text adds beyond its digest sentence, or "" when it adds nothing.
 *
 * The digest IS the first sentence (see summaryLine), so an expanded group
 * that reprinted the whole text stated its first sentence twice — the
 * duplication the founder named on Nov 14 across the hook concept, the
 * why-it-works and the outcome groups. The expansion shows only what
 * follows the digest sentence; a one-sentence text has nothing behind the
 * click, and its group renders without an expansion at all.
 */
function afterFirstSentence(text) {
  const full = String(text || "").trim().split(/\s+/).join(" ");
  if (!full) return "";
  const firstSentenceIndex = full.search(/[.!?] /);
  if (firstSentenceIndex < 0) return "";
  return full.slice(firstSentenceIndex + 2).trim();
}

/**
 * A collapsed strategy group: a title, a one-line digest of its contents, and
 * the full text behind one click. The panels people ACT on (the two sections,
 * the Location editor, the rating and the render controls) stay open; the
 * explanations do not have to be read to use the page.
 */
function CollapsedGroup({ testId, title, digest, expandable = true, children }) {
  const header = (
    <span className="flex min-w-0 flex-col gap-1 text-left">
      <GroupLabel>{title}</GroupLabel>
      {digest && (
        <span className="text-sm font-normal leading-relaxed text-muted-foreground [overflow-wrap:anywhere]">
          {digest}
        </span>
      )}
    </span>
  );
  // A group whose whole content is its digest has nothing behind the
  // click: it renders as a static header in the same box, so the founder
  // is never offered an expansion that only repeats the summary line.
  if (!expandable) {
    return (
      <div className="group inset-panel space-y-3" data-testid={testId}>
        <div className="flex w-full flex-wrap items-start justify-between gap-2 py-1">
          {header}
        </div>
      </div>
    );
  }
  return (
    <Disclosure
      testId={testId}
      detailsClassName="group inset-panel space-y-3"
      summaryClassName="flex w-full cursor-pointer list-none flex-wrap items-start justify-between gap-2 py-1 [&::-webkit-details-marker]:hidden"
      summary={header}
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

export function HookContinuityPanel({ project, onProjectChange, onActionChange }) {
  const [busy, setBusy] = useState(false);
  const [busyStartedAt, setBusyStartedAt] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  // The direction-change suggestion (ADR 0133): a rebuild click first asks
  // the server whether the saved direction moved since this strategy was
  // built. `suggesting` is that check (a plan generation when it did);
  // `suggestion` is the server's answer waiting on the founder's choice —
  // nothing is applied before Accept. `suggestNote` is the honest fallback
  // line when the suggestion could not be made: the rebuild still runs,
  // with the saved words, and says so.
  const [suggesting, setSuggesting] = useState(false);
  const [suggestion, setSuggestion] = useState(null);
  const [applying, setApplying] = useState(false);
  const [suggestNote, setSuggestNote] = useState(null);

  const projectId = project?.id;
  const strategy = project?.strategy;
  const hasStrategy = Boolean(strategy?.hook_line);
  const assets = project?.assets || [];
  const hasCharacter = assets.some((a) => a.kind === "character_reference");
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

  const runRebuild = async ({ skipConfirm = false } = {}) => {
    // Confirm only when the plan has moved on or the angle has changed. A
    // rebuild then means something specific — it discards a strategy built
    // against an older plan or a different angle, and nothing else on screen
    // says that is what the button does. An ordinary rebuild of a strategy
    // that is already current is harmless and stays one click; interrupting
    // that every time would just teach the founder to dismiss the prompt
    // without reading it. A founder who just answered the suggestion modal
    // has already made this choice with the words in front of them, so the
    // modal paths skip the second prompt (skipConfirm).
    if (!skipConfirm && hasStrategy && (staleStrategy || angleStale)) {
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
    setBusyStartedAt(Date.now());
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
      setBusyStartedAt(null);
    }
  };

  const handleGenerateStrategy = async () => {
    if (busy || suggesting || !projectId || needsAngle) return;
    // A first build has nothing to compare against: no popup, ever.
    if (!hasStrategy) {
      await runRebuild();
      return;
    }
    // ADR 0133: before the rebuild, ask whether the saved direction moved
    // since this strategy was built. The check itself is free (the server
    // answers without a model call when nothing changed); only a real
    // change spends a plan generation on refreshed words. A suggestion
    // waits for the founder's choice in the modal — nothing is applied
    // before it — and any failure falls back to today's rebuild with the
    // saved words, with a note saying suggestions were unavailable.
    setSuggesting(true);
    setBusyStartedAt(Date.now());
    setSuggestNote(null);
    try {
      const answer = await api.suggestStrategyRefresh(projectId);
      if (answer?.suggestion) {
        setSuggestion(answer);
        return;
      }
    } catch (err) {
      setSuggestNote(
        "Direction suggestions were unavailable, so the strategy was rebuilt " +
        "with your saved words."
      );
    } finally {
      setSuggesting(false);
      setBusyStartedAt(null);
    }
    await runRebuild();
  };

  const acceptSuggestion = async () => {
    if (!suggestion || applying) return;
    const words = suggestion.suggestion || {};
    const payload = {};
    if (words.hook_line) payload.hook_line = words.hook_line;
    if (words.script) payload.script = words.script;
    setApplying(true);
    setError(null);
    try {
      // The normal plan-save path: the words land as a plan edit (the plan
      // version bumps), and only then does the rebuild run — once, against
      // the words the founder just accepted.
      const updated = await api.updateStudioProject(projectId, payload);
      onProjectChange?.(updated);
      setSuggestion(null);
      await runRebuild({ skipConfirm: true });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setApplying(false);
    }
  };

  const keepSuggestion = async () => {
    if (applying) return;
    // Keep mine: the saved words stay byte-identical — nothing is written —
    // and the rebuild runs against them, once.
    setSuggestion(null);
    await runRebuild({ skipConfirm: true });
  };

  // The sticky wizard bar carries this panel's one action while Review is
  // the step in view (ADR 0133): the same handler, the same busy anchor,
  // so the bar and the button above are one control in two places, never
  // two competing ones. Registration is keyed on the action's visible
  // state; the click goes through a ref so a re-render never re-registers
  // a stale closure, and unmounting clears the slot.
  const clickRef = useRef(null);
  clickRef.current = handleGenerateStrategy;
  const stableClick = useRef(() => clickRef.current?.()).current;
  const actionLabel = suggesting
    ? "Checking direction"
    : busy
      ? "Building strategy"
      : hasStrategy ? "Rebuild strategy" : "Build the strategy";
  // The bar carries this action only while it is the step's unblocker:
  // no strategy yet, a rebuild owed, an angle still to pick, or a flight
  // in progress. A current strategy's rebuild is optional — the step can
  // proceed as-is — so it never displaces the bar's way forward.
  const barOwed = Boolean(
    busy || suggesting || needsAngle || !hasStrategy || staleStrategy || angleStale
  );
  const barSig = [
    barOwed ? "owed" : "free", actionLabel,
    busy || suggesting ? "busy" : "idle",
    needsAngle ? "needs-angle" : "ready", busyStartedAt || "",
  ].join("|");
  useEffect(() => {
    if (!onActionChange) return;
    onActionChange(barOwed ? {
      label: actionLabel,
      busy: busy || suggesting,
      disabled: busy || suggesting || !projectId || needsAngle,
      etaSeconds: suggesting ? BUSY_ETA_SECONDS.planStrategy : BUSY_ETA_SECONDS.strategy,
      busyStartedAt,
      onClick: stableClick,
    } : null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [barSig]);
  useEffect(() => () => onActionChange?.(null), [onActionChange]);

  // No auto-build: mounting this panel is navigation, and navigation
  // generates nothing (ADR 0122). A project that arrives ready with no
  // strategy shows the empty state and the Build button above, and the
  // founder's click on it is the build — the same discipline as every
  // other section's Generate. A stale strategy likewise waits: rebuilding
  // discards a strategy the founder may have read, so the confirm on the
  // click is the guard, and nothing here spends the call on arrival.

  const sections = plannedSections(strategy);
  // What the two text groups add beyond their digest sentences. The digest
  // is the first sentence, so the expansions below show only these
  // remainders — the whole text used to print its first sentence twice,
  // once as the digest and once as the body's first line.
  const hookConceptRest = afterFirstSentence(strategy?.hook_concept);
  const summaryRest = afterFirstSentence(strategy?.strategy_summary);
  // The outcome rows the expanded block adds beyond its digest. The digest
  // is the first of the three fields that is set, so that field's row
  // keeps only what follows its first sentence — dropped entirely when
  // the field is one sentence — and the other two rows stay whole.
  const outcomeFields = [
    ["The change this supports", "desired_outcome"],
    ["How it works, as a benefit", "mechanism_beat"],
    ["What the viewer is left with", "payoff_beat"],
  ];
  const outcomeDigestField = outcomeFields
    .map(([, field]) => field)
    .find((field) => String(strategy?.[field] || "").trim());
  const outcomeRows = outcomeFields
    .map(([label, field]) => [
      label,
      field === outcomeDigestField
        ? afterFirstSentence(strategy?.[field])
        : strategy?.[field],
    ])
    .filter(([, value]) => String(value || "").trim());
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
  // The scene digest names only how the piece is filmed. It used to
  // concatenate the location and the wardrobe (or the light) ahead of the
  // camera label, and the expanded rows then printed both again verbatim
  // — the founder's Nov 14 screenshot showed the location sentence three
  // times on one page (digest, Location row, and the render panel's
  // editor, which stays as the one editable source). Each fact now lives
  // in exactly one place in this panel: the digest carries the camera
  // setup, the rows carry everything else.
  const sceneDigest = sentenceCase(cameraLabel);

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
      {/* No overflow alert at the top of this panel: the detailed
          spoken-overflow warning in the strategy detail below is the one
          notice for that state (Kasra's one-notice rule) — a red duplicate
          used to sit here saying the same thing in fewer words. */}

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

      {suggestNote && (
        <Alert variant="warning" data-testid="strategy-suggest-note">
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{suggestNote}</AlertDescription>
        </Alert>
      )}

      <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
        <Button
          variant="accent"
          onClick={handleGenerateStrategy}
          disabled={busy || suggesting || applying || !projectId || needsAngle}
          busy={busy || suggesting}
          etaSeconds={suggesting ? BUSY_ETA_SECONDS.planStrategy : BUSY_ETA_SECONDS.strategy}
          busyStartedAt={busyStartedAt}
          data-testid="strategy-build-button"
        >
          <Sparkles className="h-4 w-4" />
          {actionLabel}
        </Button>
        {!busy && !suggesting && needsAngle && (
          <p className="text-sm text-muted-foreground" data-testid="strategy-needs-angle">
            Pick an audience angle on the Audience &amp; template step first — the strategy is built around it.
          </p>
        )}
        {!busy && !suggesting && !hasStrategy && !needsAngle && (
          <p className="text-sm text-muted-foreground">
            Text only. It fixes the concept, the words and the locked scene so
            the one render is about this app rather than a generic take with a
            name in it.
          </p>
        )}
      </div>

      {suggestion && (
        /* The suggestion modal (ADR 0133). The saved words and the refreshed
           pair sit side by side; nothing has been applied — Accept saves the
           new words through the normal plan-save path and then rebuilds,
           Keep mine rebuilds against the words already saved. Closing the
           modal any other way is not offered: the rebuild the founder
           clicked is waiting on this choice. */
        <div
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 px-4"
          data-testid="strategy-suggestion-modal"
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Suggested update"
            className="w-full max-w-2xl rounded-2xl border border-border bg-card p-5 shadow-2xl"
          >
            <h3 className="font-display text-base font-semibold">Suggested update</h3>
            <p className="mt-1 text-sm text-muted-foreground">
              Your direction changed after this strategy was built, so your saved
              words may no longer match the scene. Here is a refreshed pair
              written for the direction as it stands now — take it, or keep
              yours. Either way the strategy is then rebuilt once, against the
              words you choose.
            </p>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <div className="space-y-3">
                <p className="eyebrow">Your saved words</p>
                <div>
                  <p className="text-sm font-semibold">Hook</p>
                  <p className="text-base leading-relaxed" data-testid="suggestion-current-hook">
                    {suggestion.current?.hook_line}
                  </p>
                </div>
                <div>
                  <p className="text-sm font-semibold">Script</p>
                  <p className="text-base leading-relaxed" data-testid="suggestion-current-script">
                    {suggestion.current?.script}
                  </p>
                </div>
              </div>
              <div className="space-y-3">
                <p className="eyebrow">Refreshed for the new direction</p>
                <div>
                  <p className="text-sm font-semibold">Hook</p>
                  <p className="text-base leading-relaxed" data-testid="suggestion-new-hook">
                    {suggestion.suggestion?.hook_line || suggestion.current?.hook_line}
                  </p>
                  {!suggestion.suggestion?.hook_line && (
                    <p className="text-sm text-muted-foreground">
                      Your hook stays — it scored stronger than the refresh.
                    </p>
                  )}
                </div>
                <div>
                  <p className="text-sm font-semibold">Script</p>
                  <p className="text-base leading-relaxed" data-testid="suggestion-new-script">
                    {suggestion.suggestion?.script || suggestion.current?.script}
                  </p>
                </div>
              </div>
            </div>
            <div className="mt-5 flex flex-wrap justify-end gap-2">
              <Button
                variant="secondary"
                onClick={keepSuggestion}
                disabled={applying}
                data-testid="suggestion-keep-button"
              >
                Keep mine
              </Button>
              <Button
                variant="accent"
                onClick={acceptSuggestion}
                disabled={applying}
                busy={applying}
                data-testid="suggestion-accept-button"
              >
                {applying ? "Saving the new words" : "Accept the update"}
              </Button>
            </div>
          </div>
        </div>
      )}

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
            Built on your click — the button above writes it from your saved plan, and a failed build retries from the same button. Read the strategy before rendering. This step creates text, not video.
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
                {/* Only what follows the digest sentence: the concept's
                    first sentence is the digest above, and reprinting it
                    here stated it twice in one group. A one-sentence
                    concept leaves just the note below, which is the
                    expansion's own content. */}
                {hookConceptRest && (
                  <p className="text-base leading-relaxed [overflow-wrap:anywhere]">{sentenceCase(hookConceptRest)}</p>
                )}
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
              expandable={Boolean(summaryRest)}
            >
              {summaryRest && (
                <p className="max-w-3xl text-base leading-relaxed [overflow-wrap:anywhere]">{sentenceCase(summaryRest)}</p>
              )}
            </CollapsedGroup>
          )}

          {/* The three outcome fields, shown because they already govern the
              whole render (generation_planning reads them into the segment
              prompt) and were invisible here. Framed as a change the app
              supports, never a result it promises — the same rule the template
              outcome line and the evidence note follow. The digest is the
              change it supports; the rows below it add only what the digest
              has not already said (outcomeRows), so the change is stated
              once, not once as the digest and again as the first row. */}
          {hasOutcome && (
            <CollapsedGroup
              testId="strategy-viewer-outcome"
              title="What the viewer ends up with"
              digest={summaryLine(strategy.desired_outcome || strategy.mechanism_beat || strategy.payoff_beat)}
              expandable={outcomeRows.length > 0}
            >
              <StrategyBlock
                title="What the viewer ends up with"
                description="How the viewer sees this app: the change, the benefit, and what they are left with — all from the viewer's point of view. The render is written from this framing — aim at it, never promise it as a result."
                icon={Target}
                hideTitle
                rows={outcomeRows}
              />
            </CollapsedGroup>
          )}

          {/* Scene and performance are ONE group, not two: movement and voice
              delivery are locked by exactly the same mechanism as camera angle
              and lighting. The digest names only the camera setup — the
              place, the light and the wardrobe are the rows below, stated
              once each. */}
          {sceneRows.length > 0 && (
            <CollapsedGroup
              testId="strategy-scene-details"
              title="Scene details"
              digest={sceneDigest}
            >
              <StrategyBlock
                title="The scene"
                description="One Location, one render: the hook and the middle can't disagree. Edit the Location in Visual & audio direction on the plan, where the wardrobe is picked too; lighting is set from this video's scene."
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
