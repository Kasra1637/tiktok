import { Input } from "../ui/input";

/**
 * The Review hook line field. A one-click clearer rewrite used to be offered
 * beside a vague-hook warning taken from the claim-safety report; that
 * report is gone (ADR 0119), so the field is a plain editor again. The
 * rewrite endpoint still exists server-side, unsurfaced here.
 */
export default function HookLineEditor({ value, onChange }) {
  return (
    <div className="space-y-4">
      <label htmlFor="review-hook_line" className="text-sm font-semibold">Hook line</label>
      <p className="text-sm text-muted-foreground" data-subtitle="">The opening line spoken in your generated Hook + Story clip.</p>
      <Input id="review-hook_line" value={value} onChange={(e) => onChange(e.target.value)} />
    </div>
  );
}
