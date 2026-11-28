import { Mic } from "lucide-react";
import { Button } from "../ui/button";
import { GroupLabel } from "../SectionCard";
import { PickSlider } from "./HookPicksControl";

/**
 * The presenter voice pick (ADR 0246), shared by the Hook + CTA
 * direction card and Create Video's direction section — the two
 * places movement and direction are set.
 *
 * Three choices (Nov 27 2026): the app's choice (resolves at
 * generation — talking unless the angle or profile carries a
 * silent direction), the character talks (voice, lips moving
 * with the words), or the character stays silent (no voice, and
 * NO lip movement at all: the mouth stays closed and still for
 * the whole clip, while the opening and closing actions still
 * happen). A fourth stop, Voiceover, stood here for a few hours
 * the same day and Kasra ordered it removed — TikTok itself
 * offers a voiceover, so the pick duplicated the platform; a
 * project still stored as "voiceover" heals to talking on read
 * and at generation. Three stops sit inside Kasra's 3–4 range
 * for every toggle, so no replacement stop stands.
 *
 * The words are gender-neutral (ADR 0248): the founder uploads
 * the face, and the app does not know — or presume — whose it
 * is, so the pick says "character", never a pronoun. The same
 * neutrality ADR 0089 already required of the render directions.
 *
 * The pick is the project's, saved through the same draft PATCH
 * as every other direction pick; this control only reports the
 * choice. A caller may pass `pickedValue` to say which choice
 * the buttons show as picked, separately from the mode `value`
 * (ADR 0361: Create passes "" while a project stands on its
 * defaults, so no button reads as chosen before a click).
 *
 * No line stands under this pick (Kasra's orders, Nov 27 2026):
 * the text-to-speech handover note that rose on changing onto
 * silent is removed whole — it duplicated what the silent pick
 * already says — and the brief explainer line every toggle
 * carried the same day is removed with all the others: the
 * pick's name is the whole information.
 */
const OPTIONS = [
  { value: "auto", label: "App's choice" },
  { value: "talking", label: "Character talks" },
  { value: "silent", label: "Character stays silent" },
];

export default function VoiceModeControl({
  value = "talking",
  pickedValue,
  onChange,
  disabled = false,
  testId = "voice-mode",
  asSlider = false,
}) {
  // The current mode the slider names and rests on: the stored
  // pick itself when it is one of the three stops — an "auto"
  // pick stands as the app's choice, its resolution happening at
  // generation — and the talking default for an unset or
  // unrecognized value (a legacy "voiceover" included), never
  // silence.
  const current = OPTIONS.some((option) => option.value === value) ? value : "talking";
  // Which choice the buttons may show as picked (ADR 0361): a
  // caller that tracks picks separately from the effective mode
  // passes pickedValue — "" stands for no pick made, so neither
  // button wears the picked face. A caller that passes nothing
  // keeps the original face: the buttons follow the value itself.
  const pickedCurrent = pickedValue === undefined ? current : pickedValue;
  return (
    // Layout reset: the group starts at its area's inset like
    // everything else in the app — label and pick row on the
    // container's one line, nothing centered.
    <div className="space-y-2">
      <GroupLabel icon={Mic}>Voice</GroupLabel>
      {/* The pick wears the resolution treatment (ADR 0331) in its
          default form: the shared Button in a thumb-pair row, brand
          and thumb-selected on the pick. The slider form (Kasra's
          order, Nov 27 2026) supersedes the row wherever a host
          passes asSlider — HookSnap first, then Create too, when
          the unified toggle spread app-wide: the same three choices
          as the one groove slider, the knob resting on the mode
          that will render while no pick stands (ADR 0361's
          unpicked state, restValue), a click or drag earning the
          pick exactly as a pill click does (ADR 0373's repair
          rides the same onChange). */}
      {asSlider ? (
        <PickSlider
          options={OPTIONS}
          current={pickedCurrent}
          restValue={current}
          onChange={onChange}
          disabled={disabled}
          testId={testId}
          ariaLabel="Presenter voice"
        />
      ) : (
        <div className="thumb-pair flex flex-wrap gap-2" role="group" aria-label="Presenter voice">
          {OPTIONS.map((option) => {
            const picked = pickedCurrent === option.value;
            return (
              <Button
                key={option.value}
                type="button"
                size="sm"
                variant={picked ? "brand" : "secondary"}
                aria-pressed={picked}
                disabled={disabled}
                onClick={() => onChange?.(option.value)}
                data-testid={`${testId}-${option.value}`}
                className={`tap-chip option-btn ${picked ? "thumb-selected" : ""}`}
              >
                {option.label}
              </Button>
            );
          })}
        </div>
      )}
    </div>
  );
}
