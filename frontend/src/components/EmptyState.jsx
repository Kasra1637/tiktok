import { Card } from "./ui/card";

export function EmptyState({ icon: Icon, title, description, action }) {
  return (
    <Card className="flex flex-col items-center justify-center text-center gap-3 p-10 rounded-2xl border-dashed border-2 border-border bg-white/50">
      {Icon && (
        <span className="flex h-12 w-12 items-center justify-center rounded-full bg-[color:rgba(13,148,136,0.10)] text-[color:var(--brand-teal)]">
          <Icon className="h-6 w-6" />
        </span>
      )}
      <h3 className="font-display text-lg font-semibold">{title}</h3>
      {description && <p className="text-sm text-muted-foreground max-w-md">{description}</p>}
      {action}
    </Card>
  );
}
export default EmptyState;
