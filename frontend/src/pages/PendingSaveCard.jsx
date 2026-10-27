import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import { api } from "../lib/api";
import {
  AlertTriangle,
  ChevronRight,
  Download,
  RotateCcw,
} from "lucide-react";
import {
  clearPendingSave,
  getPendingBlob,
  retryPendingSave,
} from "../demoCta/saveOutbox";
import { historyActionError } from "./historyRepair";

/**
 * One failed export that created no server row, repaired from the outbox.
 *
 * The bytes live in the editor tab's memory: while this tab is that tab,
 * Download keeps the clip and Retry save files it for real (success reloads
 * the list below). After a reload or in another tab the bytes are gone, so
 * the card says so and sends the founder back to re-export instead of
 * offering buttons that cannot act.
 */
export function PendingSaveCard({ entry, onResolved }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const hasBytes = Boolean(getPendingBlob(entry.id));
  const [url, setUrl] = useState(null);
  useEffect(() => {
    if (!hasBytes) return undefined;
    const objectUrl = URL.createObjectURL(getPendingBlob(entry.id));
    setUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [entry.id, hasBytes]);
  const retry = async () => {
    setBusy(true);
    setError(null);
    try {
      await retryPendingSave(entry.id, (generationId, blob, filename) =>
        api.saveDemoCtaExport(generationId, blob, filename)
      );
      onResolved?.();
    } catch (err) {
      setError(historyActionError(err, "retry this save"));
    } finally {
      setBusy(false);
    }
  };
  const dismiss = () => {
    clearPendingSave(entry.id);
    onResolved?.();
  };
  return (
    <Alert data-testid={`pending-save-${entry.id}`}>
      <AlertTriangle className="h-4 w-4" />
      <AlertDescription className="flex flex-col gap-2">
        <span className="font-medium text-foreground">
          {entry.filename || "demo-cta.mp4"} couldn&apos;t be saved — the file is kept.
        </span>
        {entry.message ? <span className="text-muted-foreground">{entry.message}</span> : null}
        <span className="text-muted-foreground">
          {hasBytes
            ? "Download it here so nothing is lost, then press Retry save."
            : "The file bytes left with the editor tab, so re-export it from Demo + CTA."}
        </span>
        {error ? <span role="alert" className="text-destructive">{error}</span> : null}
        <span className="flex flex-wrap items-center gap-2">
          {url ? (
            <Button variant="secondary" size="sm" asChild>
              <a href={url} download={entry.filename || "demo-cta.mp4"} data-testid={`pending-save-download-${entry.id}`}>
                <Download className="h-3.5 w-3.5" /> Download
              </a>
            </Button>
          ) : null}
          {hasBytes ? (
            <Button variant="secondary" size="sm" disabled={busy} onClick={retry} data-testid={`pending-save-retry-${entry.id}`}>
              <RotateCcw className="h-3.5 w-3.5" /> {busy ? "Retrying…" : "Retry save"}
            </Button>
          ) : (
            <Button variant="secondary" size="sm" asChild>
              <Link to="/demo-cta" data-testid={`pending-save-reexport-${entry.id}`}>
                Open Demo + CTA <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          )}
          <Button variant="secondary" size="sm" disabled={busy} onClick={dismiss} data-testid={`pending-save-dismiss-${entry.id}`}>
            Dismiss
          </Button>
        </span>
      </AlertDescription>
    </Alert>
  );
}
