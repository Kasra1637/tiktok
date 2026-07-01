import { useEffect, useState } from "react";
import { Progress } from "./ui/progress";
import { CheckCircle2, Loader2, Circle } from "lucide-react";

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
    <div className="space-y-3" data-testid="generation-progress">
      <Progress value={progressPct} className="h-2" />
      <ul className="space-y-2">
        {stages.map((stage, idx) => (
          <li key={stage} className="flex items-center gap-2 text-sm">
            {idx < stepIndex ? (
              <CheckCircle2 className="h-4 w-4 text-[color:var(--brand-teal)]" />
            ) : idx === stepIndex ? (
              <Loader2 className="h-4 w-4 animate-spin text-[color:var(--brand-teal)]" />
            ) : (
              <Circle className="h-4 w-4 text-muted-foreground" />
            )}
            <span className={idx <= stepIndex ? "text-foreground" : "text-muted-foreground"}>{stage}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
export default GenerationProgress;
