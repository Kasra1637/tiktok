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
 * The branded confirmation for deleting an asset projects still use
 * (ADR 0212).
 *
 * Deleting the file does not rewrite the projects that referenced it,
 * so when a photograph is in use the delete asks first — in the same
 * shared Dialog treatment as the delete-render and regenerate-angles
 * confirmations: one title, one short description naming where the
 * asset is used, the consequence as a plain list, and the decision in
 * the footer. The copy follows ADR 0203 — each fact once. Nothing is
 * deleted while this is open: Cancel is the focused default, and the
 * delete runs only from the confirm button. An unused asset never
 * sees this dialog; it deletes on the click.
 */
export function DeleteAssetConfirmDialog({ confirm, onCancel, onConfirm }) {
  const count = confirm?.count || 0;

  return (
    <Dialog
      open={Boolean(confirm)}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
    >
      <DialogContent data-testid="delete-asset-dialog">
        <DialogHeader>
          <DialogTitle>Delete this asset?</DialogTitle>
          <DialogDescription>
            {`It is used in ${count} project${count === 1 ? "" : "s"} (${confirm?.names}).`}
          </DialogDescription>
        </DialogHeader>

        <ul
          className="list-disc space-y-1 pl-5 text-sm text-muted-foreground"
          data-testid="delete-asset-consequences"
        >
          <li>
            Deleting it removes the face reference from those projects until a
            new one is attached.
          </li>
        </ul>

        <DialogFooter>
          <Button
            variant="secondary"
            autoFocus
            onClick={onCancel}
            data-testid="delete-asset-cancel"
          >
            Cancel
          </Button>
          <Button
            variant="accent"
            onClick={onConfirm}
            data-testid="delete-asset-confirm"
          >
            Delete asset
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default DeleteAssetConfirmDialog;
