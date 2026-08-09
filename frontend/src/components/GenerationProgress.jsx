import { useEffect, useState } from "react";
import { Progress } from "./ui/progress";
import { Check, Loader2 } from "lucide-react";

export function GenerationProgress({ stages, active }) {
  const [stepIndex, setStepIndex] = useState(0);

  useEffect(() => {
    if (!active) {
      setStepIndex(0);
      return;
    }
    setStepIndex(0);
    const interval = setInterval(() => {
      setStepIndex((prev) => (prev < stages.length - 1 ? prev + 1 : prev));
    }, 2800);
    return () => clearInterval(interval);
  }, [active, stages.length]);

  if (!active) return null;

  const progressPct = ((stepIndex + 1) / stages.length) * 100;

  return (
    <div className="space-y-4" data-testid="generation-progress">
      <div className="flex items-center justify-between gap-3">
        <span className="eyebrow">
          Step {stepIndex + 1} of {stages.length}
        </span>
        <span className="font-mono text-xs text-[color:var(--brand-indigo)]">
          {Math.round(progressPct)}%
        </span>
      </div>

      <Progress value={progressPct} />

      <ol className="space-y-0.5">
        {stages.map((stage, idx) => {
          const done = idx < stepIndex;
          const current = idx === stepIndex;
          return (
            <li key={stage} className="flex items-start gap-3">
              <div className="flex flex-col items-center">
                <span
                  className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-full border transition-colors ${
                    done
                      ? "border-transparent bg-[color:var(--brand-indigo)] text-white"
                      : current
                      ? "border-[color:var(--brand-indigo)] text-[color:var(--brand-indigo)]"
                      : "border-[color:var(--hairline-strong)] text-muted-foreground"
                  }`}
                >
                  {done ? (
                    <Check className="h-3 w-3" />
                  ) : current ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <span className="h-1.5 w-1.5 rounded-full bg-current opacity-50" />
                  )}
                </span>
                {/* Connector so the stages read as one continuous run. */}
                {idx < stages.length - 1 && (
                  <span
                    aria-hidden="true"
                    className={`my-0.5 w-px flex-1 ${
                      done ? "bg-[color:var(--brand-indigo)]" : "bg-border"
                    }`}
                    style={{ minHeight: "0.75rem" }}
                  />
                )}
              </div>
              <span
                className={`pb-2 text-sm leading-5 ${
                  current ? "font-medium text-foreground" : done ? "text-foreground/80" : "text-muted-foreground"
                }`}
              >
                {stage}
              </span>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
export default GenerationProgress;
