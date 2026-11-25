import { Button } from "../ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "../ui/dialog";

/**
 * The branded confirmation for regenerating angles (ADR 0210).
 *
 * It wears the same shared Dialog treatment as the delete confirmations:
 * one title, one short description, the consequences as a plain list, and
 * the decision in the footer. The copy follows ADR 0203 — each fact once.
 * Nothing is spent while this is open: Cancel is the focused default, and
 * the regeneration runs only from the confirm button.
 */
export function AngleRegenConfirmDialog({ confirm, onCancel, onConfirm }) {
  const affected = confirm?.affected;
  const counted = Number.isFinite(affected) && affected > 0;

  return (
    <Dialog
      open={Boolean(confirm)}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent data-testid="regenerate-angles-dialog">
        <DialogHeader>
          <DialogTitle>Regenerate angles?</DialogTitle>
          <DialogDescription>
            Fresh angles replace the generated ones. Your hand-written angles stay.
          </DialogDescription>
        </DialogHeader>

        <ul
          className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
          data-testid="regenerate-angles-consequences"
        >
          <li>
            {counted
              ? affected === 1
                ? "1 draft keeps its draft but loses its story."
                : `${affected} drafts keep their drafts but lose their stories.`
              : "Drafts built on generated angles keep their drafts but lose their stories."}
          </li>
          <li>Rebuild each affected strategy at Review.</li>
        </ul>

        <DialogFooter>
          <Button
            variant="secondary"
            autoFocus
            onClick={onCancel}
            data-testid="regenerate-angles-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={onConfirm}
            data-testid="regenerate-angles-confirm"
          >
            Regenerate angles
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default AngleRegenConfirmDialog;
