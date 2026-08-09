import { useState } from "react";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "./ui/collapsible";
import { Button } from "./ui/button";
import { ChevronDown, Copy, Check, Braces } from "lucide-react";
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
    <Collapsible open={open} onOpenChange={setOpen} className="surface overflow-hidden rounded-2xl">
      <div className="flex items-center justify-between gap-3 p-4">
        <CollapsibleTrigger asChild>
          <button
            className="group flex min-w-0 items-center gap-2.5 text-left"
            data-testid="toggle-generation-spec-button"
          >
            <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
              <Braces className="h-4 w-4" />
            </span>
            <span className="min-w-0">
              <span className="font-display block truncate text-sm font-semibold">Generation Spec</span>
              <span className="block truncate text-xs text-muted-foreground">
                For the future video-gen API
              </span>
            </span>
            <ChevronDown
              className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${
                open ? "rotate-180" : ""
              }`}
            />
          </button>
        </CollapsibleTrigger>
        <Button
          variant="secondary"
          size="sm"
          onClick={handleCopy}
          className="shrink-0 gap-1.5"
          data-testid="copy-generation-spec-button"
        >
          {copied ? (
            <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
          ) : (
            <Copy className="h-3.5 w-3.5" />
          )}
          {copied ? "Copied" : "Copy"}
        </Button>
      </div>
      <CollapsibleContent>
        <div className="border-t border-[color:var(--hairline)] bg-[hsl(228_14%_6%_/_0.6)]">
          <pre className="max-h-[400px] overflow-x-auto overflow-y-auto whitespace-pre-wrap break-words p-4 font-mono text-xs leading-relaxed text-muted-foreground">
            {JSON.stringify(spec, null, 2)}
          </pre>
        </div>
      </CollapsibleContent>
    </Collapsible>
  );
}
export default JsonSpecPanel;
