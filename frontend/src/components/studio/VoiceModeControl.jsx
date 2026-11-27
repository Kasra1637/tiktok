import { Mic } from "lucide-react";
import { Button } from "../ui/button";
import { GroupLabel } from "../SectionCard";

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
 * When silence is picked the note below the pills is part of the
 * feature, not decoration: it tells the founder the character will
 * be silent and names the exact text to paste into TikTok's
 * text-to-speech so TikTok voices the post — the line itself, shown
 * verbatim once it exists. A caller may pass `hideNote` to stand
 * the pills without the note in either mode (ADR 0362: Create's
 * direction section carries no descriptive lines at all, so it
 * opts out; HookSnap passes nothing and keeps the note).
 */
const OPTIONS = [
  { value: "talking", label: "Character talks" },
  { value: "silent", label: "Character stays silent" },
];

export default function VoiceModeControl({
  value = "silent",
  pickedValue,
  onChange,
  silentText = "",
  silentTextName = "the line",
  hideNote = false,
  disabled = false,
  testId = "voice-mode",
}) {
  const current = value === "talking" ? "talking" : "silent";
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
      {/* The pick wears the resolution treatment (ADR 0331): the
          shared Button in a thumb-pair row, brand and
          thumb-selected on the pick, as the 480p / 768p row stands. */}
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
      {!hideNote && (current === "talking" ? (
        <p className="text-sm text-muted-foreground">
          The character speaks the line on camera — voice on, and the lips move with the words.
        </p>
      ) : (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-silent-note`}>
          The character stays silent in this video — no voice, and the mouth never moves.
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
      ))}
    </div>
  );
}
