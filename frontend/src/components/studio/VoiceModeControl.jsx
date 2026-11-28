import { useState } from "react";
import { Mic } from "lucide-react";
import { Button } from "../ui/button";
import { GroupLabel } from "../SectionCard";
import { PickSlider } from "./HookPicksControl";
import { VOICE_EXPLAINERS } from "../../lib/pickExplainers";

/**
 * The presenter voice pick (ADR 0246), shared by the Hook + CTA
 * direction card and Create Video's direction section — the two
 * places movement and direction are set.
 *
 * Exactly two choices, Kasra's settled binary: the character talks
 * (voice, lips moving with the words — the behavior every render
 * used to have by default), or the character stays silent (no
 * voice, and NO lip movement at all: the mouth stays closed and
 * still for the whole clip, while the opening and closing actions
 * still happen). There is no voiceover middle option.
 *
 * The words are gender-neutral (ADR 0248): the founder uploads the
 * face, and the app does not know — or presume — whose it is, so
 * the pick says "character", never a pronoun. The same neutrality
 * ADR 0089 already required of the render directions.
 *
 * The pick is the project's, saved through the same draft PATCH as
 * every other direction pick; this control only reports the choice.
 * A caller may pass `pickedValue` to say which choice the buttons
 * show as picked, separately from the mode `value` the note names
 * (ADR 0361: Create passes "" while a project stands on its
 * defaults, so no button reads as chosen before a click).
 * When the user changes the pick onto silence the note below is
 * part of the feature, not decoration: it names the exact text to
 * paste into TikTok's text-to-speech so TikTok voices the post —
 * the line itself, shown verbatim once it exists. The note belongs
 * to the change, never to a standing saved pick (Kasra's order,
 * Nov 27 2026). What silence MEANS is the slider's own brief
 * explainer now (lib/pickExplainers, the shared band) — the long
 * sentence that used to open this note is replaced by it, and
 * only the text-to-speech handover stands here. Talking mode
 * carries no line of its own (Nov 27 2026: the descriptive
 * sentence that stood under the pills in talking mode is removed
 * whole). A caller may pass `hideNote` to stand the pills without
 * the silent note (ADR 0362: Create's direction section carries
 * no descriptive lines at all, so it opts out; HookSnap passes
 * nothing and keeps the note).
 */
const OPTIONS = [
  { value: "talking", label: "Character talks" },
  { value: "silent", label: "Character stays silent" },
];

export default function VoiceModeControl({
  value = "talking",
  pickedValue,
  onChange,
  silentText = "",
  silentTextName = "the line",
  hideNote = false,
  disabled = false,
  testId = "voice-mode",
  asSlider = false,
}) {
  // The silent note belongs to the change, not to the standing
  // state (Kasra's order, Nov 27 2026): it renders only after the
  // user changes this control during this page session and lands
  // on silent. A saved silent pick standing on the page shows no
  // note on its own; sliding to silent brings the note up, and
  // sliding back to talking takes it away. The record of the
  // change is local interaction state, never derived from the
  // saved value alone.
  const [changedTo, setChangedTo] = useState(null);
  const reportChange = (next) => {
    setChangedTo(next);
    onChange?.(next);
  };
  // The unset state resolves to the left stop (Kasra's order,
  // Nov 27 2026: every toggle rests on the left by default):
  // only an explicit silent pick reads as silent — an unset or
  // unrecognized value is the talking default, never silence.
  const current = value === "silent" ? "silent" : "talking";
  // Which choice the buttons may show as picked (ADR 0361): a
  // caller that tracks picks separately from the effective mode
  // passes pickedValue — "" stands for no pick made, so neither
  // button wears the picked face while the note below still names
  // the mode that will render. A caller that passes nothing keeps
  // the original face: the buttons follow the value itself.
  const pickedCurrent = pickedValue === undefined ? current : pickedValue;
  const text = String(silentText || "").trim();
  return (
    // Layout reset: the group starts at its area's inset like
    // everything else in the app — label, pick row and note on
    // the container's one line, nothing centered.
    <div className="space-y-2">
      <GroupLabel icon={Mic}>Voice</GroupLabel>
      {/* The pick wears the resolution treatment (ADR 0331) in its
          default form: the shared Button in a thumb-pair row, brand
          and thumb-selected on the pick. The slider form (Kasra's
          order, Nov 27 2026) supersedes the row wherever a host
          passes asSlider — HookSnap first, then Create too, when
          the unified toggle spread app-wide: the same two choices
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
          onChange={reportChange}
          disabled={disabled}
          testId={testId}
          ariaLabel="Presenter voice"
          explainers={VOICE_EXPLAINERS}
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
                onClick={() => reportChange(option.value)}
                data-testid={`${testId}-${option.value}`}
                className={`tap-chip option-btn ${picked ? "thumb-selected" : ""}`}
              >
                {option.label}
              </Button>
            );
          })}
        </div>
      )}
      {/* Nov 27 2026 (Kasra's order): talking mode stands with no
          line under the pills — the long descriptive sentence that
          stood there is removed whole, on every caller. The silent
          note below is a different line in a different role (it
          hands over the exact text for TikTok's text-to-speech)
          and stays — but only once the user changes this control
          onto silent in this session: a standing saved pick shows
          no note on load, sliding to silent brings it up, and
          sliding back takes it away. */}
      {!hideNote && current === "silent" && changedTo === "silent" && (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-silent-note`}>
          For a voice on TikTok, paste this line into TikTok&rsquo;s text-to-speech:{" "}
          {text ? (
            <span className="font-semibold text-foreground">&ldquo;{text}&rdquo;</span>
          ) : (
            <span>
              {silentTextName.charAt(0).toUpperCase() + silentTextName.slice(1)} will
              appear here once it is written.
            </span>
          )}
        </p>
      )}
    </div>
  );
}
