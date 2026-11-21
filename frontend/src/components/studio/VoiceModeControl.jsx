import { Mic } from "lucide-react";
import { GroupLabel } from "../SectionCard";

/**
 * The presenter voice pick (ADR 0246), shared by the Hook + CTA
 * direction card and Create Video's direction section — the two
 * places movement and direction are set.
 *
 * Exactly two choices, Kasra's settled binary: she talks (her voice,
 * her lips moving with the words — the behavior every render has
 * had), or she stays silent (no voice, and NO lip movement at all:
 * her mouth stays closed and still for the whole clip, while the
 * opening and closing actions still happen). There is no voiceover
 * middle option.
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
  { value: "talking", label: "She talks" },
  { value: "silent", label: "She stays silent" },
];

export default function VoiceModeControl({
  value = "talking",
  onChange,
  silentText = "",
  silentTextName = "the line",
  disabled = false,
  testId = "voice-mode",
}) {
  const current = value === "silent" ? "silent" : "talking";
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
      {current === "talking" ? (
        <p className="text-sm text-muted-foreground">
          She speaks the line on camera — her voice, and her lips move with the words.
        </p>
      ) : (
        <p role="status" className="text-sm text-muted-foreground" data-testid={`${testId}-silent-note`}>
          She stays silent in this video — no voice, and her mouth does not move at
          all. For a voice on TikTok, paste this text into TikTok&rsquo;s
          text-to-speech so TikTok reads it aloud:
          {text ? (
            <span className="mt-1 block font-semibold text-foreground">&ldquo;{text}&rdquo;</span>
          ) : (
            <span className="mt-1 block">
              {silentTextName} will show here once it is written — that exact text
              is the one to paste.
            </span>
          )}
        </p>
      )}
    </div>
  );
}
