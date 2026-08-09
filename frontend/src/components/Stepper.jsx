const STEPS = [
  { key: "find", label: "Find Video" },
  { key: "analyze", label: "Analyze Hook" },
  { key: "swap", label: "Face Swap" },
  { key: "video", label: "Generate Video" },
];

export function Stepper({ current }) {
  const idx = STEPS.findIndex((s) => s.key === current);
  return (
    <div className="flex flex-wrap items-center gap-1.5 md:gap-2" data-testid="workflow-stepper">
      {STEPS.map((s, i) => (
        <div key={s.key} className="flex items-center gap-1.5 md:gap-2">
          <div
            className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-semibold transition-colors ${
              i < idx
                ? "bg-[color:var(--brand-indigo)] text-white"
                : i === idx
                ? "bg-[color:var(--brand-coral)] text-white"
                : "bg-secondary border border-border text-muted-foreground"
            }`}
            data-testid={`stepper-step-${s.key}`}
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-black/15 text-xs">
              {i + 1}
            </span>
            {s.label}
          </div>
          {i < STEPS.length - 1 && (
            <div className={`h-px w-4 md:w-6 ${i < idx ? "bg-[color:var(--brand-indigo)]" : "bg-border"}`} />
          )}
        </div>
      ))}
    </div>
  );
}

export default Stepper;
