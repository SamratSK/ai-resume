import type { ReactNode } from "react";

export function EmptyState({
  icon,
  title,
  description,
  action,
}: {
  icon?: ReactNode;
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-lavender/35 bg-surface-raised/70 px-8 py-16 text-center">
      {icon && <div className="text-ink-faint">{icon}</div>}
      <h3 className="text-lg font-medium text-ink">{title}</h3>
      {description && <p className="measure text-sm text-ink-soft">{description}</p>}
      {action && <div className="mt-2">{action}</div>}
    </div>
  );
}
