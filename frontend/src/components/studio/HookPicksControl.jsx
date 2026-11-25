import { Focus, HelpCircle, MessagesSquare, RefreshCw } from "lucide-react";
import { AppSelect } from "../AppSelect";
import { Button } from "../ui/button";
import { CONTROL_CLASS } from "../formControls";
import { GroupLabel } from "../SectionCard";

/**
 * The founder's steering picks for the Hook + CTA hook (ADR 0247),
 * standing in the Hook card above the generate action: a focus, a
 * tone, and a shape. Three small choices, each with the app's own
 * choice as its default — an untouched set of picks generates
 * exactly the hook this page has always generated.
 *
 * FOCUS is one of the app profile's own outcome lines — the list
 * below is the whole vocabulary, built from the profile the same
 * way the backend builds it (`profile_focus_lines` in
 * ai_service.py: the evidenced outcome statements first, then the
 * flat desired outcomes they do not already say, with the chopped
 * fragments an old profile still stores filtered out by the
 * completeness bar below, ADR 0307). It is NOT the
 * retired angle picker: no angle is created, stored or scored —
 * the pick names which of the app's outcomes the hook leads with,
 * and the backend proves membership again when the pick saves and
 * when the hook is written, so a line the profile no longer
 * carries steers nothing (and reads here as the app's choice).
 *
 * TONE is a closed set of three — plain, warm, bold — riding the
 * project's tone column; SHAPE is the app's choice, a question, or
 * a statement: Kasra's framing of a good hook — it names a feeling
 * or a pain point fast, as a quick question or a bold statement,
 * and holds the answer back for the demo.
 *
 * The picks are the project's, saved through the same draft PATCH
 * as every other pick on the page; this control only reports
 * choices. Changing a pick never regenerates on its own
 * (click-to-generate only): when a hook is already on file the
 * stale note says the line predates the picks and names the
 * remedy — the one hook button, Generate a new hook, which the
 * founder presses themselves (ADR 0313; ADR 0249's unified
 * control named the suggestion here until the suggestion left
 * the page).
 *
 * The Focus block also carries the outcome refresh (ADR 0288): the
 * host wires a handler that writes a fresh outcome layer onto the
 * profile, and the new lines arrive through focusOptions — this
 * control only asks and shows the wait and the failure.
 */

// The completeness bar (ADR 0249, mirrored from `_outcome_stands_alone`
// in ai_service.py): a lone word names a topic, a conjunction or
// preposition opener is a chopped sentence's tail, and a line ending
// on a conjunction or a comma stops mid-list. The Focus pick never
// offers a line that fails it (ADR 0307) — a profile researched
// before the bar can still store the pieces.
const OUTCOME_FRAGMENT_OPENERS = new Set([
  "and", "but", "or", "nor", "yet", "so",
  "on", "in", "at", "from", "with", "without", "by", "for", "to",
  "of", "over", "under", "after", "before", "into", "through",
  "about", "between", "during", "upon", "within", "toward", "towards",
]);
const OUTCOME_FRAGMENT_ENDERS = new Set(["and", "or", "but", "nor"]);

function outcomeStandsAlone(text) {
  const words = String(text || "").trim().split(/\s+/).filter(Boolean);
  if (words.length < 2) return false;
  const strip = (word) => word.replace(/^["'“”‘’()\[\],]+|["'“”‘’()\[\],]+$/g, "").toLowerCase();
  if (OUTCOME_FRAGMENT_OPENERS.has(strip(words[0]))) return false;
  if (String(text).trim().endsWith(",")) return false;
  if (OUTCOME_FRAGMENT_ENDERS.has(strip(words[words.length - 1]))) return false;
  return true;
}

function storedOutcomeTexts(profile) {
  const texts = [];
  const add = (text) => {
    const line = String(text || "").split(/\s+/).join(" ").trim();
    if (line) texts.push(line);
  };
  for (const entry of profile?.outcome_statements || []) {
    add(typeof entry === "string" ? entry : entry?.outcome);
  }
  const desired = profile?.desired_outcomes;
  if (Array.isArray(desired)) {
    for (const entry of desired) add(entry);
  } else if (desired) {
    add(desired);
  }
  return texts;
}

export function profileOutcomeLines(profile) {
  const lines = [];
  const seen = new Set();
  for (const line of storedOutcomeTexts(profile)) {
    if (outcomeStandsAlone(line) && !seen.has(line)) {
      seen.add(line);
      lines.push(line);
    }
  }
  // Six at a time (Kasra's order, Nov 23 2026, ADR 0307): the first
  // six lines that stand alone, in the profile's own order.
  return lines.slice(0, 6);
}

// A stale menu (ADR 0320): the profile still stores outcome lines
// the completeness bar cannot offer — fragments an older research
// pass left behind ("and growth over time"). The pick quietly
// drops them, so without this test the founder would never know
// the fresh set a Buffet writes is already owed.
export function profileOutcomeMenuStale(profile) {
  return storedOutcomeTexts(profile).some((line) => !outcomeStandsAlone(line));
}

const TONE_OPTIONS = [
  { value: "", label: "App's choice" },
  { value: "plain", label: "Plain" },
  { value: "warm", label: "Warm" },
  { value: "bold", label: "Bold" },
];

const SHAPE_OPTIONS = [
  { value: "auto", label: "App's choice" },
  { value: "question", label: "Question" },
  { value: "statement", label: "Statement" },
];

export function PickPills({ options, current, onChange, disabled, testId, ariaLabel }) {
  return (
    <div className="flex flex-wrap gap-2" role="group" aria-label={ariaLabel}>
      {options.map((option) => (
        <button
          key={option.value || "auto"}
          type="button"
          aria-pressed={current === option.value}
          disabled={disabled}
          onClick={() => onChange?.(option.value)}
          data-testid={`${testId}-${option.value || "auto"}`}
          className={`rounded-full border px-3 py-1 text-xs font-semibold ${
            current === option.value
              ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
              : "border-[color:var(--hairline)] text-muted-foreground"
          }`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

export default function HookPicksControl({
  focusOptions = [],
  focus = "",
  onFocusChange,
  onRefreshFocus,
  focusRefreshing = false,
  focusRefreshError = "",
  focusRefreshAsLink = false,
  hasHook = false,
  focusStale = false,
  tone = "",
  onToneChange,
  shape = "auto",
  onShapeChange,
  stale = false,
  disabled = false,
  testId = "hook-picks",
}) {
  const toneValue = TONE_OPTIONS.some((option) => option.value === tone) ? tone : "";
  const shapeValue = SHAPE_OPTIONS.some((option) => option.value === shape) ? shape : "auto";
  // A saved focus the profile no longer carries steers nothing on
  // the backend; here it reads as what it now is — the app's choice.
  const focusValue = focusOptions.includes(focus) ? focus : "";
  return (
    <div className="space-y-4">
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <GroupLabel icon={Focus}>Focus</GroupLabel>
          {/* The outcome refresh (ADR 0288, Kasra's order): one click
              writes a fresh outcome layer onto the profile from its
              stored facts — the fresh ideas land in this list, and a
              stored list carrying old fragments is replaced whole.
              Offered only where the host wires it. ADR 0308: the
              button is named Buffet and stands on the left, beside
              the label — no button on the right of this row.
              ADR 0320 (Kasra's ruling, Nov 24 2026): the Buffet is
              staged — it stands here once a hook exists to steer, or
              early when the menu itself is stale; before either, it
              would only invite a long refresh nobody needs yet.
              ADR 0325 (Kasra's ruling, Nov 24 2026, superseding
              0320 on the HookSnap surface): a host passing
              focusRefreshAsLink gets the refresh always, wearing
              the page's own "New options" text link — the same
              small underlined link the page's direction picks use —
              in the same left-hand spot, so the page reads as one
              design. The Buffet above is untouched without it. */}
          {onRefreshFocus && focusRefreshAsLink && (
            <button
              type="button"
              onClick={onRefreshFocus}
              disabled={disabled || focusRefreshing}
              data-testid={`${testId}-focus-refresh`}
              className="shrink-0 text-sm text-muted-foreground underline disabled:opacity-50"
            >
              {focusRefreshing ? "Finding new options…" : "New options"}
            </button>
          )}
          {onRefreshFocus && !focusRefreshAsLink && (hasHook || focusStale) && (
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={onRefreshFocus}
              disabled={disabled || focusRefreshing}
              busy={focusRefreshing}
              data-testid={`${testId}-focus-refresh`}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Buffet
            </Button>
          )}
        </div>
        <AppSelect
          id="hook-cta-hook-focus"
          testId={`${testId}-focus`}
          block
          value={focusValue}
          onChange={(value) => onFocusChange?.(value)}
          disabled={disabled}
          className={CONTROL_CLASS}
          options={[
            { value: "", label: "Let the app choose" },
            ...focusOptions.map((line) => ({ value: line, label: line })),
          ]}
        />
        <p className="text-sm text-muted-foreground">
          The outcome the hook leads with — one of your app&rsquo;s own outcomes.
        </p>
        {focusStale && !hasHook && (
          <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-focus-stale-note`}>
            {focusRefreshAsLink
              ? "Some stored outcomes are fragments the menu can’t offer whole — use New options for a fresh set from your profile."
              : "Some stored outcomes are fragments the menu can’t offer whole — Buffet writes a fresh set from your profile."}
          </p>
        )}
        {focusRefreshError && (
          <p role="alert" className="text-sm text-destructive-text" data-testid={`${testId}-focus-refresh-error`}>
            {focusRefreshError}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <GroupLabel icon={MessagesSquare}>Tone</GroupLabel>
        <PickPills
          options={TONE_OPTIONS}
          current={toneValue}
          onChange={onToneChange}
          disabled={disabled}
          testId={`${testId}-tone`}
          ariaLabel="Hook tone"
        />
      </div>

      <div className="space-y-2">
        <GroupLabel icon={HelpCircle}>Shape</GroupLabel>
        <PickPills
          options={SHAPE_OPTIONS}
          current={shapeValue}
          onChange={onShapeChange}
          disabled={disabled}
          testId={`${testId}-shape`}
          ariaLabel="Hook shape"
        />
        <p className="text-sm text-muted-foreground">
          Ask the pain point as a question, or name it as a statement — the answer
          stays withheld either way, for the demo.
        </p>
      </div>

      {stale && (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-stale-note`}>
          The line on file was written before these picks — generate a new hook to
          write it with them.
        </p>
      )}
    </div>
  );
}
