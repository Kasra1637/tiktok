import { Card } from "./ui/card";
import { mediaUrl } from "../lib/api";

export function SideBySideCompare({ originalUrl, generatedUrl }) {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
      <Card className="overflow-hidden rounded-2xl border-border" data-testid="original-frame-image">
        <div className="px-4 py-2 text-xs font-medium text-muted-foreground border-b border-border">Original Hook Frame</div>
        <img src={mediaUrl(originalUrl)} alt="Original hook frame" className="w-full object-contain bg-black/5 max-h-[480px]" />
      </Card>
      <Card className="overflow-hidden rounded-2xl border-[color:var(--brand-indigo)]" data-testid="generated-preview-image">
        <div className="px-4 py-2 text-xs font-medium text-[color:var(--brand-indigo-dark)] border-b border-border">Your Customized Preview</div>
        <img src={mediaUrl(generatedUrl)} alt="Generated customized preview" className="w-full object-contain bg-black/5 max-h-[480px]" />
      </Card>
    </div>
  );
}
export default SideBySideCompare;
