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
 * The branded confirmation for generating another video (ADR 0212).
 *
 * A re-roll is a second paid render on a video the founder has already
 * seen, so it asks first — in the same shared Dialog treatment as the
 * delete and regenerate-angles confirmations: one title, one short
 * description, the consequences as a plain list, and the decision in
 * the footer. The copy follows ADR 0203 — each fact once. Nothing is
 * spent while this is open: Cancel is the focused default, and the
 * render runs only from the confirm button.
 */
export function GenerateAnotherConfirmDialog({ confirm, onCancel, onConfirm }) {
  return (
    <Dialog
      open={Boolean(confirm)}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent data-testid="generate-another-dialog">
        <DialogHeader>
          <DialogTitle>Generate another video?</DialogTitle>
          <DialogDescription>
            This runs a second render from this plan.
          </DialogDescription>
        </DialogHeader>

        <ul
          className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
          data-testid="generate-another-consequences"
        >
          <li>The video you already have stays in History.</li>
        </ul>

        <DialogFooter>
          <Button
            variant="ghost"
            autoFocus
            onClick={onCancel}
            data-testid="generate-another-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={onConfirm}
            data-testid="generate-another-confirm"
          >
            Generate another
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default GenerateAnotherConfirmDialog;
