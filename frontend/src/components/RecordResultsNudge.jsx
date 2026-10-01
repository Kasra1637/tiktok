import { Link } from "react-router-dom";
import { TrendingUp } from "lucide-react";

/**
 * Ask for the view numbers, at the one moment the founder has them.
 *
 * The learning engine reads proved_hooks, aggregates it honestly — skipping
 * non-manual rows and `views <= 0` so it can never invent a rate — and feeds
 * the result into the next strategy prompt. All of that work was fed by one
 * "Record results" ghost button sitting among eight identically-styled ones on
 * a page two nav hops away, behind seven optional fields. Nothing in the
 * product ever asked.
 *
 * The download is where that has to change. It is a clean, honest terminus:
 * the product never posts for you, never touches your accounts, and therefore
 * has no idea the video is out there. That is also exactly where the only
 * compounding asset it has stops compounding.
 *
 * So this is asked once, immediately after a finished download, and it links
 * straight to the row that carries the result. `recorded` suppresses it the
 * moment the numbers exist, so it never nags someone who already logged them.
 *
 * Both download paths render it: the one-shot GenerationPanel and the
 * segmented HookContinuityPanel. The `generationId` must be a real generation
 * id — never the synthesized `chain-` id the assembler produces, which is not
 * a row in /history.
 */
export function RecordResultsNudge({ generationId, recorded }) {
  if (!generationId || recorded) return null;
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 rounded-lg border border-[color:var(--indigo-25)] bg-[color:var(--indigo-6)] px-3 py-2">
      <TrendingUp className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
      <span className="text-xs text-muted-foreground">
        Posted it? Record the views and the next video for this app will know what
        worked.
      </span>
      <Link
        to={`/history?generation=${encodeURIComponent(generationId)}`}
        className="text-xs font-semibold text-[color:var(--brand-indigo)] hover:underline"
      >
        Record results
      </Link>
    </div>
  );
}
