import { Smile, Hand, Scissors, Volume2, ListChecks, Lightbulb, Check } from "lucide-react";
import { SectionHeading } from "./SectionCard";

const SECTIONS = [
  { key: "facial_expressions", label: "Facial Expressions & Micro-expressions", icon: Smile },
  { key: "body_language_gestures", label: "Body Language & Gestures", icon: Hand },
  { key: "pacing_cuts", label: "Pacing & Cuts", icon: Scissors },
  { key: "audio_cues_inferred", label: "Audio Cues", icon: Volume2 },
];

export function HookBreakdown({ analysis }) {
  return (
    <div className="space-y-4">
      {/* Hook summary — the headline takeaway, given coral emphasis so it
          reads as the conclusion rather than one card among six. */}
      <div className="border-gradient relative rounded-2xl p-[1px]">
        <div className="surface-solid relative overflow-hidden rounded-2xl">
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-0"
            style={{
              background: "radial-gradient(500px circle at 0% 0%, rgba(254,44,85,0.07), transparent 60%)",
            }}
          />
          <div className="relative space-y-2">
            <SectionHeading as="h3" icon={Lightbulb}>Hook summary</SectionHeading>
            <p className="text-sm leading-relaxed">{analysis.hook_summary}</p>
          </div>
        </div>
      </div>

      <div className="surface rounded-2xl" data-testid="replicable-mechanics-checklist">
        <SectionHeading as="h4" icon={ListChecks} className="mb-3">Replicable Mechanics Checklist</SectionHeading>
        <ul className="space-y-2.5">
          {(analysis.replicable_mechanics || []).map((m, i) => (
            <li key={i} className="flex items-start gap-2.5 text-sm">
              <span className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-[color:var(--indigo-15)] text-[color:var(--brand-indigo)]">
                <Check className="h-2.5 w-2.5" />
              </span>
              <span className="min-w-0 break-words leading-relaxed">{m}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        {SECTIONS.map(({ key, label, icon: Icon }) => (
          <div
            key={key}
            className="surface surface-interactive min-w-0 rounded-2xl"
            data-testid={`hook-section-${key}`}
          >
            <SectionHeading as="h4" icon={Icon} className="mb-2 break-words">{label}</SectionHeading>
            <p className="break-words text-sm leading-relaxed text-muted-foreground">{analysis[key]}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
export default HookBreakdown;
