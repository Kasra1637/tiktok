import { useEffect, useRef, useState } from "react";
import { Button } from "../ui/button";
import { GroupLabel } from "../SectionCard";
import { PickSlider } from "./HookPicksControl";

/**
 * One profile-aware set of option buttons for a direction field (the
 * section sits on the Audience & template step since ADR 0220; this
 * file keeps the name it shares with the plan-phase narration below).
 *
 * The options come from the profile's category group (no free typing), and
 * picking only fills the draft — saving still validates like any edit
 * and the strategy still needs a rebuild, exactly as with typed notes.
 *
 * The label stands as a plain bold span unless the caller passes
 * `labelIcon`, in which case it wears the shared GroupLabel face —
 * the uppercase eyebrow with the icon at its left (ADR 0362:
 * Create's direction section unifies its four group headings on
 * that face; ADR 0364: HookSnap's card passes its icons too, so
 * both pages' Location and Wardrobe wear the face). The "New
 * options" action sits beside the label either way.
 */
// Kasra's cap (ADR 0332): a direction button's text never runs
// past 25 characters, so the row stays a row of buttons instead
// of a wall of prose. The full option still applies underneath —
// The button label stays inside Kasra's 25 characters
// (ADR 0332), shortened the safe way (ADR 0337, his ruling,
// Nov 25 2026): the old trim backed off to the last whole word
// and still amputated phrases mid-thought on his screen —
// "Calm living room with a", "Balcony with a simple". A
// shortened label must still read as a complete phrase with
// its spelling, meaning and grammar intact, so the trim cuts
// at a word boundary and then drops any trailing word still
// waiting for the rest of its phrase: articles, prepositions
// and conjunctions, and an article + describing word whose
// noun was cut away. The pick stores the whole string; only
// the button's text is shortened, and it never wears dots.
const DIRECTION_BUTTON_MAX = 25;
const DANGLING_END_WORDS = new Set([
  "a", "an", "the", "with", "in", "on", "at", "by", "of", "for",
  "to", "and", "or", "but", "beside", "near", "under", "over",
  "from", "into", "onto", "behind", "between", "against",
]);
function directionButtonLabel(option) {
  const text = String(option);
  if (text.length <= DIRECTION_BUTTON_MAX) return text;
  const cut = text.slice(0, DIRECTION_BUTTON_MAX);
  const lastSpace = cut.lastIndexOf(" ");
  const words = (lastSpace > 0 ? cut.slice(0, lastSpace) : cut).trimEnd().split(/\s+/);
  while (words.length > 1) {
    const last = words[words.length - 1].toLowerCase();
    if (DANGLING_END_WORDS.has(last)) {
      words.pop();
      continue;
    }
    const prev = (words[words.length - 2] || "").toLowerCase();
    if (prev === "a" || prev === "an" || prev === "the") {
      words.splice(words.length - 2, 2);
      continue;
    }
    break;
  }
  return words.join(" ");
}

export function DirectionSelect({
  id,
  testId,
  label,
  labelIcon = null,
  value,
  onPick,
  options,
  placeholder,
  disabled,
  // Fresh-list generation for this field alone. When provided, the
  // "New options" action beside the label spends one text model call
  // for four new options grounded in the profile and the selected
  // angle — the static category list repeats itself across videos, and
  // a founder who has seen all four has nowhere else to go.
  // { onRefresh, refreshing, refreshTestId }.
  refresh = null,
  // The slider form (Kasra's order, Nov 27 2026): the standing
  // picks stand as the unified slider's stops instead of buttons
  // — first on HookSnap's surface, then on Create's too, when
  // the unified toggle spread app-wide. The reveal is untouched
  // — New options still opens the full set as the pill row
  // below, and a pick from it seats into the slider's stops by
  // the same last-seat rule when the row stands collapsed again.
  asSlider = false,
}) {
  // The options stand side by side wearing the resolution
  // treatment (ADR 0331): the shared Button in a thumb-pair row,
  // brand and thumb-selected on the pick, exactly as the render
  // panels' 480p / 768p row stands — spaced by the row's gap,
  // never stuck together.
  //
  // FOUR picks stand by default (Kasra's order, Nov 27 2026,
  // superseding ADR 0365's two-standing rule for these fields —
  // his 3–4 range rule now reaches Location and Wardrobe). The
  // rest of the set stands only once the founder presses "New
  // options": the press reveals the set in place, and the
  // refreshed set that lands in answer stays revealed. A set
  // that arrives any other way — a profile or camera change
  // re-reads the lists — starts collapsed at four again. The
  // last-seat rule survives at the wider width: a saved pick
  // outside the standing four takes the FOURTH seat beside the
  // first three options, so what applies is always on a lit
  // button and never hides behind the reveal.
  const all = options || [];
  const [revealed, setRevealed] = useState(false);
  const revealEarnedRef = useRef(false);
  const optionsSeenRef = useRef(options);
  useEffect(() => {
    if (optionsSeenRef.current !== options) {
      optionsSeenRef.current = options;
      if (!revealEarnedRef.current) setRevealed(false);
      revealEarnedRef.current = false;
    }
  }, [options]);
  const wasRefreshingRef = useRef(false);
  useEffect(() => {
    // A refresh that fails lands no new set: its press must not
    // keep a later, unrelated set revealed. Once the flight
    // settles, the earned reveal is spent — the options effect
    // above has already honored it if a set landed with it.
    if (wasRefreshingRef.current && !refresh?.refreshing) {
      revealEarnedRef.current = false;
    }
    wasRefreshingRef.current = Boolean(refresh?.refreshing);
  }, [refresh?.refreshing]);
  let shown = revealed ? all : all.slice(0, 4);
  if (!revealed && value && all.includes(value) && !shown.includes(value)) {
    shown = [...all.slice(0, 3), value];
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2">
        {labelIcon ? (
          <GroupLabel icon={labelIcon} id={`${id}-label`}>{label}</GroupLabel>
        ) : (
          <span id={`${id}-label`} className="text-sm font-semibold">{label}</span>
        )}
        {refresh && (
          <button
            type="button"
            onClick={() => {
              revealEarnedRef.current = true;
              setRevealed(true);
              refresh.onRefresh();
            }}
            disabled={disabled || refresh.refreshing}
            data-testid={refresh.refreshTestId}
            className="shrink-0 text-sm text-muted-foreground underline disabled:opacity-50"
          >
            {refresh.refreshing ? "Finding new options…" : "New options"}
          </button>
        )}
      </div>
      {asSlider && options && !revealed ? (
        <div data-testid={testId} data-value={value || ""}>
          <PickSlider
            options={shown.map((option) => ({ value: option, label: directionButtonLabel(option) }))}
            current={value || ""}
            restValue={shown[0]}
            restLabel={value ? directionButtonLabel(value) : undefined}
            onChange={onPick}
            disabled={disabled}
            testId={`${testId}-slider`}
            ariaLabel={label}
          />
        </div>
      ) : (
      <div
        className="thumb-pair"
        role="group"
        aria-labelledby={`${id}-label`}
        data-testid={testId}
        data-value={value || ""}
      >
        {!options ? (
          <span className="text-sm text-muted-foreground">Loading options…</span>
        ) : (
          shown.map((option) => {
            const picked = value === option;
            return (
              <Button
                key={option}
                type="button"
                size="sm"
                variant={picked ? "brand" : "secondary"}
                aria-pressed={picked}
                data-value={option}
                disabled={disabled}
                onClick={() => onPick(option)}
                className={`tap-chip option-btn direction-btn ${picked ? "thumb-selected" : ""}`}
                title={option}
              >
                {directionButtonLabel(option)}
              </Button>
            );
          })
        )}
      </div>
      )}
    </div>
  );
}

/**
 * The plan writes in one call with no observable intermediate stages, and
 * the Review step now carries the wait on the progress button itself
 * ("Generating your plan" with a looping sweep) instead of a phase line
 * cycling invented stage names. The export keeps the name the page imports
 * so the panel wiring does not churn; it renders nothing — the button is
 * the only narrator while the plan writes.
 */
export function PlanPhaseLine() {
  return null;
}
