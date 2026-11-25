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
 * The branded confirmation for rebuilding a stale strategy (ADR 0212).
 *
 * It wears the same shared Dialog treatment as the delete and
 * regenerate-angles confirmations: one title, one short description,
 * the consequences as a plain list, and the decision in the footer.
 * The copy follows ADR 0203 — each fact once. Nothing is spent while
 * this is open: Cancel is the focused default, and the rebuild runs
 * only from the confirm button. Two wordings share the one card: the
 * plan moved on (both versions are named), or the picked angle changed
 * after the build.
 */
export function StrategyRebuildConfirmDialog({ confirm, onCancel, onConfirm }) {
  const angle = Boolean(confirm?.angle);

  return (
    <Dialog
      open={Boolean(confirm)}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent data-testid="rebuild-strategy-dialog">
        <DialogHeader>
          <DialogTitle>Rebuild the strategy?</DialogTitle>
          <DialogDescription>
            {angle
              ? "Build a fresh strategy for the newly picked audience angle."
              : `Build a fresh strategy from plan v${confirm?.newVersion}.`}
          </DialogDescription>
        </DialogHeader>

        <ul
          className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
          data-testid="rebuild-strategy-consequences"
        >
          <li>
            {angle
              ? "It replaces the strategy built for a different angle."
              : `It replaces the strategy built from plan v${confirm?.oldVersion}.`}
          </li>
          <li>The render will follow the new strategy.</li>
        </ul>

        <DialogFooter>
          <Button
            variant="secondary"
            autoFocus
            onClick={onCancel}
            data-testid="rebuild-strategy-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={onConfirm}
            data-testid="rebuild-strategy-confirm"
          >
            Rebuild strategy
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default StrategyRebuildConfirmDialog;
