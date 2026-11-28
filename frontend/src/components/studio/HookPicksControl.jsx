import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { Check, Focus, HelpCircle, Maximize2, MessagesSquare, RefreshCw, Rocket, X } from "lucide-react";
import { Button } from "../ui/button";
import { CONTROL_CLASS } from "../formControls";
import { GroupLabel } from "../SectionCard";

/**
 * The founder's steering picks for the Hook + CTA hook (ADR 0247),
 * standing in the Hook card above the generate action: a focus, a
 * tone, and a shape. Three small choices, each with the app's own
 * choice as its default — an untouched set of picks generates
 * exactly the hook this page has always generated. A fourth pick,
 * the opening, joined them on Nov 27 2026 (Kasra's order), and on
 * the HookSnap surface the tone, shape and opening render as drag
 * sliders (the picksAsSliders prop) instead of pill rows.
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
  { value: "command", label: "Command" },
];

// The third pick (Kasra's order, Nov 27 2026): how the hook opens —
// the app's choice, on the verb in motion (Action, the racing
// form), or on the concrete felt sensation (Feeling). It rides the
// project's hook_opening column the same way the shape rides its
// own, and "auto" is the behavior every hook has had until now.
const OPENING_OPTIONS = [
  { value: "auto", label: "App's choice" },
  { value: "action", label: "Action" },
  { value: "feeling", label: "Feeling" },
  { value: "reaction", label: "Reaction" },
];

// The small option sets wear the resolution treatment (ADR 0331,
// Kasra's ruling at the Nov 25 2026 live review): the shared Button
// in a thumb-pair row — brand and thumb-selected on the pick,
// secondary otherwise — exactly as the render panels' 480p / 768p
// row stands, so selection, style, and hover motion read the same
// on every small choice in the app.
export function PickPills({ options, current, onChange, disabled, testId, ariaLabel }) {
  return (
    <div className="thumb-pair flex flex-wrap gap-2" role="group" aria-label={ariaLabel}>
      {options.map((option) => {
        const picked = current === option.value;
        return (
          <Button
            key={option.value || "auto"}
            type="button"
            size="sm"
            variant={picked ? "brand" : "secondary"}
            aria-pressed={picked}
            disabled={disabled}
            onClick={() => onChange?.(option.value)}
            data-testid={`${testId}-${option.value || "auto"}`}
            className={`tap-chip option-btn ${picked ? "thumb-selected" : ""}`}
          >
            {option.label}
          </Button>
        );
      })}
    </div>
  );
}

// The one unified pick slider (Kasra's order, Nov 27 2026, from
// his approved mockups): every pick-one-of-a-few control in the
// app wears this face. The track is a shallow groove at one fixed
// width the component sets, a dot stands at each stop, the groove
// fills with the brand tint up to the knob, and the knob is a
// short pill branded in the app's own selection tokens (the
// indigo family and its glow — coral never carries selection)
// with grip lines, so it reads as a handle. Under the track ONLY
// the current pick's name stands, in the one regular-weight font: there
// is no row naming every stop, and no smaller second line
// repeating the pick — the other stops reveal themselves on the
// change itself. Dragging is never the only way: every stop dot
// is tappable, and the knob itself is a keyboard slider.
export function PickSlider({ options, current, onChange, disabled, testId, ariaLabel, restValue, restLabel }) {
  const trackRef = useRef(null);
  // No explainer line stands under any toggle (Kasra's order,
  // later Nov 27 2026, superseding the same day's explainer
  // rounds): the pick's name under the track is the whole
  // information — "just Garden bench is enough."
  // The switch glide (Kasra's order, Nov 27 2026): while the
  // pointer is down the knob follows the hand directly; the soft
  // ease in index.css applies only when the slider is not being
  // dragged, so a tap, a stop button or a key press settles into
  // its seat instead of snapping, and a drag never lags.
  const [dragging, setDragging] = useState(false);
  const found = options.findIndex((option) => option.value === current);
  // The knob's seat: the pick itself when one stands. A caller
  // whose standing state is not a pick (the voice pick before a
  // click, ADR 0361; a direction pick the current set no longer
  // carries) passes restValue — the knob rests on that stop with
  // no stop reading as picked, and the name under it is restLabel
  // or the rest stop's own name.
  const restFound = options.findIndex((option) => option.value === restValue);
  const index = found >= 0 ? found : restFound >= 0 ? restFound : 0;
  const ratio = options.length > 1 ? index / (options.length - 1) : 0;
  // The knob travels inside the groove: its center runs from half
  // its own width (1.75rem) to the same inset at the far end, and
  // the stop dots and the fill share that travel, so the knob
  // lands exactly on its stop at every seat.
  const seatLeft = (r) => `calc(0.875rem + ${r} * (100% - 1.75rem))`;
  const valueLabel = found >= 0
    ? options[found].label
    : restLabel ?? (restFound >= 0 ? options[restFound].label : "");
  const jump = (next) => {
    const option = options[Math.min(options.length - 1, Math.max(0, next))];
    if (option && option.value !== current) {
      onChange?.(option.value);
    }
  };
  const indexFromClientX = (clientX) => {
    const el = trackRef.current;
    if (!el) return index;
    const rect = el.getBoundingClientRect();
    if (!rect.width) return index;
    // The knob's travel insets 14px (half the knob) at each end of
    // the groove; pointer positions map across that same travel.
    const travel = rect.width - 28;
    const raw = travel > 0 ? (clientX - rect.left - 14) / travel : 0;
    const clamped = Math.min(1, Math.max(0, raw));
    return Math.round(clamped * (options.length - 1));
  };
  const onPointerDown = (event) => {
    if (disabled) return;
    setDragging(true);
    event.currentTarget.setPointerCapture?.(event.pointerId);
    jump(indexFromClientX(event.clientX));
  };
  const onPointerEnd = () => setDragging(false);
  const onPointerMove = (event) => {
    if (disabled || !event.buttons) return;
    jump(indexFromClientX(event.clientX));
  };
  const onKnobKeyDown = (event) => {
    if (disabled) return;
    if (event.key === "ArrowRight" || event.key === "ArrowUp") {
      event.preventDefault();
      jump(index + 1);
    } else if (event.key === "ArrowLeft" || event.key === "ArrowDown") {
      event.preventDefault();
      jump(index - 1);
    } else if (event.key === "Home") {
      event.preventDefault();
      jump(0);
    } else if (event.key === "End") {
      event.preventDefault();
      jump(options.length - 1);
    }
  };
  return (
    <div className={`pick-slider${dragging ? " pick-slider-dragging" : ""}`} data-testid={`${testId}-slider`}>
      <div
        ref={trackRef}
        className="pick-slider-track"
        onPointerDown={onPointerDown}
        onPointerMove={onPointerMove}
        onPointerUp={onPointerEnd}
        onPointerCancel={onPointerEnd}
      >
        <div className="pick-slider-fill" style={{ width: seatLeft(ratio) }} aria-hidden="true" />
        {options.map((option, i) => (
          <button
            key={option.value || "auto"}
            type="button"
            className="pick-slider-stop"
            style={{ left: seatLeft(options.length > 1 ? i / (options.length - 1) : 0) }}
            aria-label={option.label}
            aria-pressed={i === found}
            disabled={disabled}
            onClick={() => jump(i)}
            data-value={option.value}
            data-testid={`${testId}-${option.value || "auto"}`}
          />
        ))}
        <div
          className="pick-slider-knob"
          style={{ left: seatLeft(ratio) }}
          role="slider"
          tabIndex={disabled ? -1 : 0}
          aria-label={ariaLabel}
          aria-valuemin={0}
          aria-valuemax={options.length - 1}
          aria-valuenow={index}
          aria-valuetext={valueLabel}
          onKeyDown={onKnobKeyDown}
          data-testid={`${testId}-knob`}
        >
          <span aria-hidden="true" />
          <span aria-hidden="true" />
          <span aria-hidden="true" />
        </div>
      </div>
      <div className="pick-slider-value" data-testid={`${testId}-value`} key={valueLabel}>
        {valueLabel}
      </div>
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
  opening = "auto",
  onOpeningChange,
  picksAsSliders = false,
  stale = false,
  disabled = false,
  testId = "hook-picks",
}) {
  const toneValue = TONE_OPTIONS.some((option) => option.value === tone) ? tone : "";
  const shapeValue = SHAPE_OPTIONS.some((option) => option.value === shape) ? shape : "auto";
  const openingValue = OPENING_OPTIONS.some((option) => option.value === opening) ? opening : "auto";
  // A saved focus the profile no longer carries steers nothing on
  // the backend; here it reads as what it now is — the app's choice.
  const focusValue = focusOptions.includes(focus) ? focus : "";
  // The Focus pick opens in a centered pop-up (ADR 0334, Kasra's
  // ruling, Nov 25 2026): the old dropdown stretched the full width
  // of its section for one line of text, and its options are whole
  // sentences a founder reads before choosing — the same
  // read-then-pick shape as the angle spec sheet (ADR 0330). The
  // trigger on the page hugs its text instead of spanning the row.
  const [focusOpen, setFocusOpen] = useState(false);
  useEffect(() => {
    if (!focusOpen) return undefined;
    const onKey = (event) => {
      if (event.key === "Escape") setFocusOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focusOpen]);
  const focusRows = [
    { value: "", label: "Let the app choose" },
    ...focusOptions.map((line) => ({ value: line, label: line })),
  ];
  // The slider's STANDING stops cap at four (Kasra's 3–4 range
  // rule, Nov 27 2026): the app's choice plus the first three
  // complete lines. A chosen line outside the standing four takes
  // the fourth seat beside the app's choice and the first two
  // lines, so the pick always stands visible and selected. The
  // pop-up form above keeps the full list — it is a menu, not a
  // standing toggle track.
  const focusSliderRows =
    focusValue && !focusRows.slice(1, 4).some((row) => row.value === focusValue)
      ? [...focusRows.slice(0, 3), focusRows.find((row) => row.value === focusValue)]
      : focusRows.slice(0, 4);
  const focusHeader = (
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
            // ADR 0382: on the Create surface the Buffet is a
            // regenerate too, so it stands as an icon + text link
            // like its HookSnap "New options" twin above — same
            // spot beside the Focus label, same staging.
            <button
              type="button"
              className="inline-flex shrink-0 items-center gap-1.5 text-sm text-muted-foreground underline disabled:opacity-50"
              onClick={onRefreshFocus}
              disabled={disabled || focusRefreshing}
              aria-busy={focusRefreshing || undefined}
              data-testid={`${testId}-focus-refresh`}
            >
              <RefreshCw className="h-3.5 w-3.5" />
              Buffet
            </button>
          )}
        </div>
  );
  return (
    // Layout reset: the pick groups start at the container's
    // inset like everything else in the app; each group's own
    // rows keep their internal order (the Buffet still stands
    // beside its label).
    <div className="space-y-4">
      {!picksAsSliders && (
      <div className="space-y-2">
        {focusHeader}
        <div>
          <button
            type="button"
            data-testid={`${testId}-focus`}
            aria-haspopup="dialog"
            aria-expanded={focusOpen}
            disabled={disabled}
            onClick={() => setFocusOpen((open) => !open)}
            className={`${CONTROL_CLASS.replace("w-full", "w-auto max-w-full")} inline-flex items-center gap-2 text-left`}
          >
            <span className="min-w-0 truncate">{focusValue || "Let the app choose"}</span>
            <Maximize2 className="h-4 w-4 shrink-0 opacity-70" aria-hidden="true" />
          </button>
          {focusOpen && createPortal(
            <div
              className="fixed inset-0 z-[100] flex items-center justify-center p-4"
              role="dialog"
              aria-modal="true"
              aria-label="Focus"
            >
              <button
                type="button"
                aria-label="Close"
                className="absolute inset-0 h-full w-full cursor-default pop-scrim"
                onClick={() => setFocusOpen(false)}
              />
              <div
                className="relative max-h-[85vh] w-full max-w-2xl overflow-y-auto rounded-xl border border-[color:var(--hairline)] bg-card shadow-lg"
                data-testid={`${testId}-focus-popup`}
              >
                <div className="flex items-center justify-between gap-2 border-b border-[color:var(--hairline)] row-pad">
                  <GroupLabel icon={Focus}>Focus</GroupLabel>
                  <button
                    type="button"
                    aria-label="Close"
                    onClick={() => setFocusOpen(false)}
                    className="shrink-0 text-muted-foreground"
                  >
                    <X className="h-4 w-4" aria-hidden="true" />
                  </button>
                </div>
                <div className="row-pad space-y-1" role="listbox" aria-label="Focus options">
                  {focusRows.map((row) => {
                    const picked = focusValue === row.value;
                    return (
                      <button
                        key={row.value || "app-choice"}
                        type="button"
                        role="option"
                        aria-selected={picked}
                        data-value={row.value}
                        onClick={() => {
                          onFocusChange?.(row.value);
                          setFocusOpen(false);
                        }}
                        className={`flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                          picked
                            ? "bg-[color:var(--indigo-15)] font-semibold text-foreground"
                            : "text-muted-foreground hover:bg-[color:var(--indigo-6)] hover:text-foreground"
                        }`}
                      >
                        {picked ? (
                          <Check className="h-4 w-4 shrink-0" aria-hidden="true" />
                        ) : (
                          <span className="h-4 w-4 shrink-0" aria-hidden="true" />
                        )}
                        <span>{row.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </div>,
            document.body
          )}
        </div>
      </div>
      )}

      {/* ADR 0366: Tone and Shape are the card's two comparable
          pick-groups, so they stand side by side in the shared
          .section-pair under the full-width Focus — the same
          spread Create's direction section wears. Focus itself is
          a single wide control and never splits. The descriptive
          lines under Focus and Shape are removed with this round;
          the stale notes below are state and stay.
          The slider form (Kasra's order, Nov 27 2026) supersedes
          the pair on the HookSnap surface only: a host passing
          picksAsSliders gets the picks as drag sliders in the
          section trio, one line with dividers between, exactly
          the spread the page's direction card wears. Later the
          same night Kasra moved Focus onto that same row as its
          first group — four groups on one line (Focus, Tone,
          Shape, Opening), the trio extended to a quad — and the
          full-width Focus block above stands only in the pop-up
          form. Without the prop this block renders the pair of
          pill rows above, unchanged. */}
      {picksAsSliders ? (
        <div className="section-trio section-quad">
          <div className="space-y-2">
            {focusHeader}
            <div data-testid={`${testId}-focus`}>
              <PickSlider
                options={focusSliderRows}
                current={focusValue}
                onChange={onFocusChange}
                disabled={disabled}
                testId={`${testId}-focus`}
                ariaLabel="Focus"
              />
            </div>
          </div>

          <div className="space-y-2">
            <GroupLabel icon={MessagesSquare}>Tone</GroupLabel>
            <PickSlider
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
            <PickSlider
              options={SHAPE_OPTIONS}
              current={shapeValue}
              onChange={onShapeChange}
              disabled={disabled}
              testId={`${testId}-shape`}
              ariaLabel="Hook shape"
            />
          </div>

          <div className="space-y-2">
            <GroupLabel icon={Rocket}>Opening</GroupLabel>
            <PickSlider
              options={OPENING_OPTIONS}
              current={openingValue}
              onChange={onOpeningChange}
              disabled={disabled}
              testId={`${testId}-opening`}
              ariaLabel="Hook opening"
            />
          </div>
        </div>
      ) : (
        <div className="section-pair">
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
          </div>
        </div>
      )}

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
      {stale && (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-stale-note`}>
          The line on file was written before these picks — generate a new hook to
          write it with them.
        </p>
      )}
    </div>
  );
}
