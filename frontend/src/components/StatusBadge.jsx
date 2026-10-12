import { Badge } from "./ui/badge";

const STATUS = {
  submitted: ["Queued", "secondary"],
  generating: ["Generating", "indigo"],
  completed: ["Completed", "indigo"],
  failed: ["Failed", "destructive"],
  archived: ["Archived", "secondary"],
};

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** A render's status, worded and coloured the same on every page. */
export function StatusBadge({ status }) {
  const [label, variant] = STATUS[status] || [humanize(status), "secondary"];
  return <Badge variant={variant} className="text-xs">{label}</Badge>;
}

export default StatusBadge;
