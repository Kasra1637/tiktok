import { Mic } from "lucide-react";
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
 * When silence is picked the note below the pills is part of the
 * feature, not decoration: it tells the founder the character will
 * be silent and names the exact text to paste into TikTok's
 * text-to-speech so TikTok voices the post — the line itself, shown
 * verbatim once it exists.
 */
const OPTIONS = [
  { value: "talking", label: "Character talks" },
  { value: "silent", label: "Character stays silent" },
];

export default function VoiceModeControl({
  value = "silent",
  onChange,
  silentText = "",
  silentTextName = "the line",
  disabled = false,
  testId = "voice-mode",
}) {
  const current = value === "talking" ? "talking" : "silent";
  const text = String(silentText || "").trim();
  return (
    <div className="space-y-2">
      <GroupLabel icon={Mic}>Voice</GroupLabel>
      <div className="flex flex-wrap gap-2" role="group" aria-label="Presenter voice">
        {OPTIONS.map((option) => (
          <button
            key={option.value}
            type="button"
            aria-pressed={current === option.value}
            disabled={disabled}
            onClick={() => onChange?.(option.value)}
            data-testid={`${testId}-${option.value}`}
            className={`rounded-full border px-3 py-1 text-xs font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-300 ease-out hover:-translate-y-[1px] active:translate-y-0 motion-reduce:hover:-translate-y-0 ${
              current === option.value
                ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
                : "border-[color:var(--hairline)] text-muted-foreground"
            }`}
          >
            {option.label}
          </button>
        ))}
      </div>
      {current === "talking" ? (
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
      )}
    </div>
  );
}
