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
 * The branded confirmation for regenerating the plan (ADR 0212).
 *
 * A fresh plan discards the one the founder is looking at, so the
 * generation asks first — in the same shared Dialog treatment as the
 * delete and regenerate-angles confirmations: one title, one short
 * description, the consequences as a plain list, and the decision in
 * the footer. The copy keeps ADR 0203's approved facts — discard
 * plan vN, generate a new one — and says each once; with unsaved
 * edits on the plan, the edits and their loss are the facts instead.
 * Nothing is generated while this is open: Cancel is the focused
 * default, and the generation runs only from the confirm button.
 */
export function PlanRegenConfirmDialog({ confirm, onCancel, onConfirm }) {
  const hasEdits = Boolean(confirm?.hasEdits);

  return (
    <Dialog
      open={Boolean(confirm)}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent data-testid="regenerate-plan-dialog">
        <DialogHeader>
          <DialogTitle>Generate a new plan?</DialogTitle>
          <DialogDescription>
            {hasEdits
              ? "You have unsaved edits."
              : `This discards plan v${confirm?.version}.`}
          </DialogDescription>
        </DialogHeader>

        <ul
          className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
          data-testid="regenerate-plan-consequences"
        >
          {hasEdits ? (
            <>
              <li>A new plan replaces this one.</li>
              <li>Your unsaved edits are lost.</li>
            </>
          ) : (
            <li>A new plan is generated in its place.</li>
          )}
        </ul>

        <DialogFooter>
          <Button
            variant="ghost"
            autoFocus
            onClick={onCancel}
            data-testid="regenerate-plan-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={onConfirm}
            data-testid="regenerate-plan-confirm"
          >
            Generate new plan
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default PlanRegenConfirmDialog;
