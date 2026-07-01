import { Card } from "./ui/card";
import { Smile, Hand, Scissors, Type, Volume2, ListChecks, Lightbulb } from "lucide-react";

const SECTIONS = [
  { key: "facial_expressions", label: "Facial Expressions & Micro-expressions", icon: Smile },
  { key: "body_language_gestures", label: "Body Language & Gestures", icon: Hand },
  { key: "pacing_cuts", label: "Pacing & Cuts", icon: Scissors },
  { key: "text_overlays_timing", label: "Text Overlays & Timing", icon: Type },
  { key: "audio_cues_inferred", label: "Audio Cues", icon: Volume2 },
];

export function HookBreakdown({ analysis }) {
  return (
    <div className="space-y-4">
      <Card className="p-4 md:p-5 rounded-2xl border-border bg-[color:var(--card)] shadow-[var(--shadow-soft)]">
        <div className="flex items-start gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-full bg-[color:rgba(249,115,22,0.15)] text-[color:#9A3412] shrink-0">
            <Lightbulb className="h-4 w-4" />
          </span>
          <div>
            <h3 className="text-sm font-semibold text-muted-foreground">Hook Summary</h3>
            <p className="text-base leading-relaxed mt-1">{analysis.hook_summary}</p>
          </div>
        </div>
      </Card>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {SECTIONS.map(({ key, label, icon: Icon }) => (
          <Card
            key={key}
            className="p-4 md:p-5 rounded-2xl border-border bg-[color:var(--card)] shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-tight)] transition-shadow"
            data-testid={`hook-section-${key}`}
          >
            <div className="flex items-center gap-2 mb-2">
              <Icon className="h-4 w-4 text-[color:var(--brand-teal)]" />
              <h4 className="text-sm font-semibold">{label}</h4>
            </div>
            <p className="text-sm text-muted-foreground leading-relaxed">{analysis[key]}</p>
          </Card>
        ))}
      </div>

      <Card className="p-4 md:p-5 rounded-2xl border-border bg-[color:var(--card)] shadow-[var(--shadow-soft)]">
        <div className="flex items-center gap-2 mb-3">
          <ListChecks className="h-4 w-4 text-[color:var(--brand-teal)]" />
          <h4 className="text-sm font-semibold">Replicable Mechanics Checklist</h4>
        </div>
        <ul className="space-y-2">
          {(analysis.replicable_mechanics || []).map((m, i) => (
            <li key={i} className="flex items-start gap-2 text-sm">
              <span className="mt-1.5 h-1.5 w-1.5 rounded-full bg-[color:var(--brand-teal)] shrink-0" />
              <span>{m}</span>
            </li>
          ))}
        </ul>
      </Card>
    </div>
  );
}
export default HookBreakdown;
