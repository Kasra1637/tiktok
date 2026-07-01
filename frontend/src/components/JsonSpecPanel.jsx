import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { Button } from "./ui/button";
import { ChevronDown, Copy, Check } from "lucide-react";
import { toast } from "sonner";

export function JsonSpecPanel({ spec }) {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    await navigator.clipboard.writeText(JSON.stringify(spec, null, 2));
    setCopied(true);
    toast.success("Generation spec copied to clipboard");
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="rounded-2xl border border-border bg-[color:var(--card)] shadow-[var(--shadow-soft)]"
    >
      <div className="flex items-center justify-between p-4">
        <CollapsibleTrigger asChild>
          <button className="flex items-center gap-2 text-sm font-semibold" data-testid="toggle-generation-spec-button">
            <ChevronDown className={`h-4 w-4 transition-transform ${open ? "rotate-180" : ""}`} />
            Generation Spec (for future video-gen API)
          </button>
        </CollapsibleTrigger>
        <Button variant="secondary" size="sm" onClick={handleCopy} className="gap-1.5 rounded-lg" data-testid="copy-generation-spec-button">
          {copied ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />} Copy
        </Button>
      </div>
      <CollapsibleContent>
        <pre className="font-mono text-xs leading-relaxed p-4 pt-0 overflow-x-auto whitespace-pre-wrap break-words text-muted-foreground max-h-[400px] overflow-y-auto">
          {JSON.stringify(spec, null, 2)}
        </pre>
      </CollapsibleContent>
    </Collapsible>
  );
}
export default JsonSpecPanel;
